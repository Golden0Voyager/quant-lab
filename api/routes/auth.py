"""
用户认证API路由
提供注册、登录、登出等功能
"""

import logging
import re
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required

from api.models.database import User, UserRole, db

bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


def validate_email(email):
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    """验证密码强度"""
    if len(password) < 6:
        return False, "密码长度至少6位"
    return True, ""


@bp.route('/register', methods=['POST'])
def register():
    """
    用户注册

    请求体:
    {
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
        "phone": "13800138000"  // 可选
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        # 获取参数
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        phone = data.get('phone', '').strip()

        # 验证必填字段
        if not username or not email or not password:
            return jsonify({
                'success': False,
                'error': 'Missing required fields',
                'message': 'username, email and password are required'
            }), 400

        # 验证邮箱格式
        if not validate_email(email):
            return jsonify({
                'success': False,
                'error': 'Invalid email',
                'message': 'Please provide a valid email address'
            }), 400

        # 验证密码强度
        is_valid, msg = validate_password(password)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid password',
                'message': msg
            }), 400

        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            return jsonify({
                'success': False,
                'error': 'Username exists',
                'message': 'Username already taken'
            }), 409

        # 检查邮箱是否已存在
        if User.query.filter_by(email=email).first():
            return jsonify({
                'success': False,
                'error': 'Email exists',
                'message': 'Email already registered'
            }), 409

        # 创建新用户
        user = User(
            username=username,
            email=email,
            phone=phone if phone else None,
            role=UserRole.FREE,
            fast_reports_quota=3,  # 注册送3次快速分析
            deep_reports_quota=1   # 注册送1次深度分析
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        # 生成JWT tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        logger.info(f"新用户注册: {username} (ID: {user.id})")

        return jsonify({
            'success': True,
            'data': {
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            },
            'message': '注册成功！已赠送3次快速分析和1次深度分析'
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"注册失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Registration failed',
            'message': str(e)
        }), 500


@bp.route('/login', methods=['POST'])
def login():
    """
    用户登录

    请求体:
    {
        "username": "testuser",  // 或者使用email
        "password": "password123"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        # 获取参数
        username_or_email = data.get('username', '').strip()
        password = data.get('password', '')

        if not username_or_email or not password:
            return jsonify({
                'success': False,
                'error': 'Missing credentials',
                'message': 'username and password are required'
            }), 400

        # 查找用户（支持用户名或邮箱登录）
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email.lower())
        ).first()

        if not user or not user.check_password(password):
            return jsonify({
                'success': False,
                'error': 'Invalid credentials',
                'message': 'Invalid username or password'
            }), 401

        # 检查账户状态
        if not user.is_active:
            return jsonify({
                'success': False,
                'error': 'Account disabled',
                'message': 'Your account has been disabled'
            }), 403

        # 更新最后登录时间
        user.last_login = datetime.now()
        db.session.commit()

        # 生成JWT tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        logger.info(f"用户登录: {user.username} (ID: {user.id})")

        return jsonify({
            'success': True,
            'data': {
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }
        })

    except Exception as e:
        logger.error(f"登录失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Login failed',
            'message': str(e)
        }), 500


@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """刷新access token"""
    try:
        current_user_id = int(get_jwt_identity())
        access_token = create_access_token(identity=str(current_user_id))

        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token
            }
        })

    except Exception as e:
        logger.error(f"刷新token失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Refresh failed',
            'message': str(e)
        }), 500


@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """获取当前用户信息"""
    try:
        current_user_id = int(get_jwt_identity())
        user = User.query.get(current_user_id)

        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'message': 'User not found'
            }), 404

        return jsonify({
            'success': True,
            'data': {
                'user': user.to_dict()
            }
        })

    except Exception as e:
        logger.error(f"获取用户信息失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get user',
            'message': str(e)
        }), 500


@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """用户登出"""
    try:
        current_user_id = int(get_jwt_identity())
        logger.info(f"用户登出: ID {current_user_id}")

        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })

    except Exception as e:
        logger.error(f"登出失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Logout failed',
            'message': str(e)
        }), 500
