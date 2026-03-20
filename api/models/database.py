"""
数据库模型
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import enum

db = SQLAlchemy()


class UserRole(enum.Enum):
    """用户角色枚举"""
    FREE = "free"  # 免费用户
    BASIC = "basic"  # 入门包
    PRO = "pro"  # 专业包
    PREMIUM = "premium"  # 旗舰包


class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)

    # 用户角色和套餐
    role = db.Column(db.Enum(UserRole), default=UserRole.FREE, nullable=False)
    subscription_expires = db.Column(db.DateTime, nullable=True)  # 订阅到期时间

    # 使用额度（针对免费和订阅包用户）
    fast_reports_quota = db.Column(db.Integer, default=0)  # 快速分析剩余次数
    deep_reports_quota = db.Column(db.Integer, default=0)  # 深度分析剩余次数

    # 账户信息
    balance = db.Column(db.Float, default=0.0)  # 账户余额
    total_spent = db.Column(db.Float, default=0.0)  # 累计消费

    # 状态
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # 关系
    orders = db.relationship('Order', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    reports = db.relationship('Report', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def can_use_service(self, service_type='fast'):
        """检查是否可以使用服务"""
        # 旗舰包无限制
        if self.role == UserRole.PREMIUM:
            return True

        # 检查订阅是否过期
        if self.subscription_expires and self.subscription_expires < datetime.now():
            return False

        # 检查额度
        if service_type == 'fast':
            return self.fast_reports_quota > 0
        elif service_type == 'deep':
            return self.deep_reports_quota > 0

        return False

    def consume_quota(self, service_type='fast', amount=1):
        """消耗额度"""
        if service_type == 'fast' and self.fast_reports_quota > 0:
            self.fast_reports_quota -= amount
        elif service_type == 'deep' and self.deep_reports_quota > 0:
            self.deep_reports_quota -= amount

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'role': self.role.value if self.role else 'free',
            'subscription_expires': self.subscription_expires.isoformat() if self.subscription_expires else None,
            'fast_reports_quota': self.fast_reports_quota,
            'deep_reports_quota': self.deep_reports_quota,
            'balance': self.balance,
            'total_spent': self.total_spent,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class OrderStatus(enum.Enum):
    """订单状态枚举"""
    PENDING = "pending"  # 待支付
    PAID = "paid"  # 已支付
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消
    REFUNDED = "refunded"  # 已退款


class OrderType(enum.Enum):
    """订单类型枚举"""
    SINGLE_REPORT = "single_report"  # 单次报告
    SUBSCRIPTION = "subscription"  # 订阅包


class Order(db.Model):
    """订单模型"""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False, index=True)  # 订单号
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # 订单信息
    order_type = db.Column(db.Enum(OrderType), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)  # 产品名称
    product_sku = db.Column(db.String(50), nullable=False)  # 产品SKU

    # 金额
    amount = db.Column(db.Float, nullable=False)  # 订单金额
    discount_amount = db.Column(db.Float, default=0.0)  # 折扣金额
    final_amount = db.Column(db.Float, nullable=False)  # 实付金额

    # 支付信息
    payment_method = db.Column(db.String(20), nullable=True)  # 支付方式（wechat/alipay）
    payment_no = db.Column(db.String(64), nullable=True)  # 支付流水号
    paid_at = db.Column(db.DateTime, nullable=True)  # 支付时间

    # 状态
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)

    # 备注
    notes = db.Column(db.Text, nullable=True)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'order_no': self.order_no,
            'user_id': self.user_id,
            'order_type': self.order_type.value if self.order_type else None,
            'product_name': self.product_name,
            'product_sku': self.product_sku,
            'amount': self.amount,
            'discount_amount': self.discount_amount,
            'final_amount': self.final_amount,
            'payment_method': self.payment_method,
            'payment_no': self.payment_no,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'status': self.status.value if self.status else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class ReportType(enum.Enum):
    """报告类型枚举"""
    FAST = "fast"  # 快速分析
    DEEP = "deep"  # 深度分析
    MULTI_STRATEGY = "multi_strategy"  # 多策略对比
    WATCHLIST = "watchlist"  # 自选股监控
    VALUATION = "valuation"  # 估值分析


class Report(db.Model):
    """报告模型"""
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(64), unique=True, nullable=False, index=True)  # 报告ID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # 报告信息
    report_type = db.Column(db.Enum(ReportType), nullable=False)
    stock_code = db.Column(db.String(20), nullable=True, index=True)  # 股票代码
    stock_name = db.Column(db.String(100), nullable=True)  # 股票名称

    # 报告内容
    content = db.Column(db.Text, nullable=True)  # 报告内容（Markdown格式）
    summary = db.Column(db.Text, nullable=True)  # 报告摘要

    # 报告文件
    file_path = db.Column(db.String(255), nullable=True)  # 文件路径
    file_url = db.Column(db.String(255), nullable=True)  # 文件URL

    # 统计信息
    view_count = db.Column(db.Integer, default=0)  # 查看次数

    # 时间戳
    generated_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # 过期时间

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'report_id': self.report_id,
            'user_id': self.user_id,
            'report_type': self.report_type.value if self.report_type else None,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'summary': self.summary,
            'file_url': self.file_url,
            'view_count': self.view_count,
            'generated_at': self.generated_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
