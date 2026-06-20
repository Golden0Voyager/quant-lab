"""
Quant Lab API 应用入口
提供个股分析和自选股监控的RESTful API
"""

import logging
import os
from datetime import timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置
app.config['JSON_AS_ASCII'] = False  # 支持中文
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///quant_lab.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# JWT配置
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)  # access token有效期1小时
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)  # refresh token有效期30天

# 初始化数据库
from api.models.database import db

db.init_app(app)

# 初始化JWT
jwt = JWTManager(app)

# 配置限流器
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],  # 默认限流：每天200次，每小时50次
    storage_uri="memory://",  # 使用内存存储（生产环境建议使用Redis）
)

# 导入路由
from api.routes import analyze, auth, health, payment

# 注册蓝图
app.register_blueprint(health.bp)
app.register_blueprint(auth.bp, url_prefix='/api/auth')
app.register_blueprint(payment.bp, url_prefix='/api/payment')
app.register_blueprint(analyze.bp, url_prefix='/api')

# 全局错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'API endpoint not found',
        'message': 'Please check the API documentation'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'Please contact support if this persists'
    }), 500

# 请求前后钩子（记录日志）
@app.before_request
def log_request():
    logger.info(f"Request: {request.method} {request.path}")

@app.after_request
def log_response(response):
    logger.info(f"Response: {response.status_code}")
    return response

if __name__ == '__main__':
    # 开发模式运行
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
