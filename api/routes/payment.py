"""
支付和订单API路由
"""

import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from api.config.payment import PaymentMethod
from api.config.products import ProductType, get_all_products, get_product_by_sku
from api.models.database import Order, OrderStatus, OrderType, User, UserRole, db
from api.utils.payment import PaymentError, PaymentService, generate_order_no

bp = Blueprint('payment', __name__)
logger = logging.getLogger(__name__)

# 初始化支付服务（使用mock模式用于开发测试）
payment_service = PaymentService(provider="mock")


@bp.route('/products', methods=['GET'])
def list_products():
    """
    获取所有产品列表

    响应:
    {
        "success": true,
        "data": {
            "single_reports": [...],
            "subscriptions": [...]
        }
    }
    """
    try:
        all_products = get_all_products()

        single_reports = []
        subscriptions = []

        for key, product in all_products.items():
            product_dict = product.to_dict()
            product_dict["key"] = key

            if product.product_type == ProductType.SINGLE_REPORT:
                single_reports.append(product_dict)
            else:
                subscriptions.append(product_dict)

        return jsonify({
            'success': True,
            'data': {
                'single_reports': single_reports,
                'subscriptions': subscriptions
            }
        })

    except Exception as e:
        logger.error(f"获取产品列表失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get products',
            'message': str(e)
        }), 500


@bp.route('/orders/create', methods=['POST'])
@jwt_required()
def create_order():
    """
    创建订单

    请求体:
    {
        "product_sku": "REPORT_FAST_001",
        "payment_method": "wechat"  // wechat/alipay
    }

    响应:
    {
        "success": true,
        "data": {
            "order": {...},
            "payment": {
                "pay_url": "...",
                "qr_code": "..."
            }
        }
    }
    """
    try:
        current_user_id = int(get_jwt_identity())
        user = User.query.get(current_user_id)

        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        # 获取参数
        product_sku = data.get('product_sku', '')
        payment_method_str = data.get('payment_method', 'wechat')

        # 验证产品
        product = get_product_by_sku(product_sku)
        if not product:
            return jsonify({
                'success': False,
                'error': 'Invalid product',
                'message': f'Product not found: {product_sku}'
            }), 404

        # 验证支付方式
        try:
            payment_method = PaymentMethod(payment_method_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid payment method',
                'message': f'Unsupported payment method: {payment_method_str}'
            }), 400

        # 生成订单号
        order_no = generate_order_no()

        # 确定订单类型
        order_type = OrderType.SINGLE_REPORT if product.product_type == ProductType.SINGLE_REPORT else OrderType.SUBSCRIPTION

        # 创建订单
        order = Order(
            order_no=order_no,
            user_id=user.id,
            order_type=order_type,
            product_name=product.name,
            product_sku=product.sku,
            amount=product.price,
            discount_amount=0.0,
            final_amount=product.price,
            payment_method=payment_method.value,
            status=OrderStatus.PENDING
        )

        db.session.add(order)
        db.session.commit()

        # 创建支付
        try:
            payment_info = payment_service.create_payment(
                order_no=order_no,
                amount=product.price,
                subject=product.name,
                payment_method=payment_method
            )

            logger.info(f"订单创建成功: {order_no}, 用户: {user.username}, 产品: {product.name}")

            return jsonify({
                'success': True,
                'data': {
                    'order': order.to_dict(),
                    'payment': payment_info
                },
                'message': '订单创建成功，请完成支付'
            }), 201

        except PaymentError as e:
            # 支付创建失败，取消订单
            order.status = OrderStatus.CANCELLED
            order.notes = f"支付创建失败: {str(e)}"
            db.session.commit()

            return jsonify({
                'success': False,
                'error': 'Payment creation failed',
                'message': str(e)
            }), 500

    except Exception as e:
        db.session.rollback()
        logger.error(f"创建订单失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Order creation failed',
            'message': str(e)
        }), 500


@bp.route('/notify', methods=['POST'])
def payment_notify():
    """
    支付回调接口
    由支付服务商调用，不需要JWT认证

    请求体: 根据不同支付服务商有不同格式
    """
    try:
        # 获取回调数据
        if request.is_json:
            notify_data = request.get_json()
        else:
            notify_data = request.form.to_dict()

        logger.info(f"收到支付回调: {notify_data}")

        # 验证签名
        if not payment_service.verify_notify(notify_data):
            logger.warning("支付回调签名验证失败")
            return "FAIL", 400

        # 获取订单号（不同支付服务商字段名可能不同）
        order_no = notify_data.get('out_trade_no') or notify_data.get('order_no')
        if not order_no:
            logger.warning("支付回调缺少订单号")
            return "FAIL", 400

        # 查询订单
        order = Order.query.filter_by(order_no=order_no).first()
        if not order:
            logger.warning(f"订单不存在: {order_no}")
            return "FAIL", 404

        # 检查订单状态
        if order.status == OrderStatus.PAID:
            logger.info(f"订单已支付，跳过处理: {order_no}")
            return "SUCCESS", 200

        # 更新订单状态
        order.status = OrderStatus.PAID
        order.paid_at = datetime.now()
        order.payment_no = notify_data.get('payjs_order_id') or notify_data.get('transaction_id')

        # 处理订单：为用户充值额度
        user = User.query.get(order.user_id)
        if user:
            product = get_product_by_sku(order.product_sku)
            if product:
                # 充值额度
                quota = product.quota
                user.fast_reports_quota += quota.get('fast', 0)
                user.deep_reports_quota += quota.get('deep', 0)

                # 如果是订阅包，更新订阅信息
                if product.product_type == ProductType.SUBSCRIPTION:
                    days = quota.get('days', 30)
                    if user.subscription_expires and user.subscription_expires > datetime.now():
                        # 续订：在现有基础上延长
                        user.subscription_expires += timedelta(days=days)
                    else:
                        # 新订阅：从现在开始计算
                        user.subscription_expires = datetime.now() + timedelta(days=days)

                    # 更新用户角色
                    if product.sku == "SUB_BASIC_MONTH":
                        user.role = UserRole.BASIC
                    elif product.sku == "SUB_PRO_MONTH":
                        user.role = UserRole.PRO
                    elif product.sku == "SUB_PREMIUM_MONTH":
                        user.role = UserRole.PREMIUM

                user.total_spent += order.final_amount

                logger.info(f"订单处理成功: {order_no}, 用户: {user.username}, 额度已充值")

        order.status = OrderStatus.COMPLETED
        db.session.commit()

        return "SUCCESS", 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"支付回调处理失败: {e}", exc_info=True)
        return "FAIL", 500


@bp.route('/orders/<order_no>', methods=['GET'])
@jwt_required()
def get_order(order_no):
    """
    查询订单详情

    响应:
    {
        "success": true,
        "data": {
            "order": {...}
        }
    }
    """
    try:
        current_user_id = get_jwt_identity()

        order = Order.query.filter_by(order_no=order_no).first()
        if not order:
            return jsonify({
                'success': False,
                'error': 'Order not found'
            }), 404

        # 检查权限：只能查询自己的订单
        if order.user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403

        return jsonify({
            'success': True,
            'data': {
                'order': order.to_dict()
            }
        })

    except Exception as e:
        logger.error(f"查询订单失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get order',
            'message': str(e)
        }), 500


@bp.route('/orders', methods=['GET'])
@jwt_required()
def list_orders():
    """
    获取用户订单列表

    Query参数:
    - page: 页码（默认1）
    - per_page: 每页数量（默认20）
    - status: 订单状态过滤（可选）

    响应:
    {
        "success": true,
        "data": {
            "orders": [...],
            "total": 100,
            "page": 1,
            "per_page": 20
        }
    }
    """
    try:
        current_user_id = get_jwt_identity()

        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = min(per_page, 100)  # 最多100条

        # 构建查询
        query = Order.query.filter_by(user_id=current_user_id)

        # 状态过滤
        status = request.args.get('status')
        if status:
            try:
                query = query.filter_by(status=OrderStatus(status))
            except ValueError:
                pass

        # 分页
        pagination = query.order_by(Order.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        orders = [order.to_dict() for order in pagination.items]

        return jsonify({
            'success': True,
            'data': {
                'orders': orders,
                'total': pagination.total,
                'page': page,
                'per_page': per_page,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        logger.error(f"获取订单列表失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get orders',
            'message': str(e)
        }), 500


@bp.route('/orders/<order_no>/check', methods=['POST'])
@jwt_required()
def check_order_status(order_no):
    """
    主动查询订单支付状态
    用于轮询检查订单是否已支付

    响应:
    {
        "success": true,
        "data": {
            "order": {...},
            "paid": true/false
        }
    }
    """
    try:
        current_user_id = get_jwt_identity()

        order = Order.query.filter_by(order_no=order_no).first()
        if not order:
            return jsonify({
                'success': False,
                'error': 'Order not found'
            }), 404

        # 检查权限
        if order.user_id != current_user_id:
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403

        # 如果订单已支付，直接返回
        if order.status in [OrderStatus.PAID, OrderStatus.COMPLETED]:
            return jsonify({
                'success': True,
                'data': {
                    'order': order.to_dict(),
                    'paid': True
                }
            })

        # 主动查询支付状态
        try:
            payment_status = payment_service.query_order(order_no)

            # 根据查询结果更新订单
            if payment_status.get('paid') or payment_status.get('return_code') == 1:
                # 订单已支付，更新状态（这里简化处理，实际应该通过回调处理）
                order.status = OrderStatus.PAID
                order.paid_at = datetime.now()
                db.session.commit()

                return jsonify({
                    'success': True,
                    'data': {
                        'order': order.to_dict(),
                        'paid': True
                    },
                    'message': '支付成功'
                })

        except Exception as e:
            logger.warning(f"查询支付状态失败: {e}")

        # 订单未支付
        return jsonify({
            'success': True,
            'data': {
                'order': order.to_dict(),
                'paid': False
            }
        })

    except Exception as e:
        logger.error(f"检查订单状态失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to check order',
            'message': str(e)
        }), 500
