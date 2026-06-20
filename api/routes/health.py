"""
健康检查路由
用于监控服务状态
"""

import sys
from datetime import datetime

from flask import Blueprint, jsonify

bp = Blueprint('health', __name__)

@bp.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0-mvp',
        'python_version': sys.version.split()[0]
    })

@bp.route('/ping', methods=['GET'])
def ping():
    """简单的ping接口"""
    return jsonify({'pong': True})
