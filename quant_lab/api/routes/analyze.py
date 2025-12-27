"""
股票分析API路由
提供快速分析、深度分析、自选股监控等功能
"""

from flask import Blueprint, jsonify, request
import logging
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.utils.analyzer import StockAnalyzer
from api.utils.validators import validate_stock_code, validate_analysis_mode

bp = Blueprint('analyze', __name__)
logger = logging.getLogger(__name__)

# 初始化分析器
analyzer = StockAnalyzer()

# 导入限流器（从app中）
from api.app import limiter


@bp.route('/analyze/fast', methods=['POST'])
@limiter.limit("30 per hour")  # 快速分析：每小时30次
def analyze_fast():
    """
    快速分析接口

    请求体:
    {
        "stock_code": "600519",
        "stock_name": "贵州茅台"  // 可选
    }

    响应:
    {
        "success": true,
        "data": {
            "summary": "...",
            "report_id": "...",
            "generated_at": "..."
        }
    }
    """
    try:
        # 获取请求参数
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        stock_code = data.get('stock_code', '').strip()
        stock_name = data.get('stock_name', '')

        # 验证股票代码
        is_valid, error_msg = validate_stock_code(stock_code)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid stock code',
                'message': error_msg
            }), 400

        # 执行快速分析
        logger.info(f"Fast analysis requested for {stock_code}")
        result = analyzer.analyze_fast(stock_code, stock_name)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Fast analysis failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Analysis failed',
            'message': str(e)
        }), 500


@bp.route('/analyze/deep', methods=['POST'])
@limiter.limit("10 per hour")  # 深度分析：每小时10次（消耗更多资源）
def analyze_deep():
    """
    深度分析接口

    请求体:
    {
        "stock_code": "600519",
        "stock_name": "贵州茅台",  // 可选
        "prompt_version": "professional"  // 可选: professional/value_first/quant_hybrid
    }

    响应:
    {
        "success": true,
        "data": {
            "report_markdown": "...",
            "report_id": "...",
            "strategies": ["professional", "value_first", "quant_hybrid"],
            "generated_at": "..."
        }
    }
    """
    try:
        # 获取请求参数
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        stock_code = data.get('stock_code', '').strip()
        stock_name = data.get('stock_name', '')
        prompt_version = data.get('prompt_version', 'professional')

        # 验证参数
        is_valid, error_msg = validate_stock_code(stock_code)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid stock code',
                'message': error_msg
            }), 400

        is_valid, error_msg = validate_analysis_mode(prompt_version)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid prompt version',
                'message': error_msg
            }), 400

        # 执行深度分析
        logger.info(f"Deep analysis requested for {stock_code} with {prompt_version}")
        result = analyzer.analyze_deep(stock_code, stock_name, prompt_version)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Deep analysis failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Analysis failed',
            'message': str(e)
        }), 500


@bp.route('/analyze/multi-strategy', methods=['POST'])
@limiter.limit("5 per hour")  # 多策略分析：每小时5次（最消耗资源）
def analyze_multi_strategy():
    """
    多策略对比分析接口（MVP核心功能）

    请求体:
    {
        "stock_code": "600519",
        "stock_name": "贵州茅台"  // 可选
    }

    响应:
    {
        "success": true,
        "data": {
            "comparison_report": "...",  // 3种策略对比报告
            "report_id": "...",
            "generated_at": "..."
        }
    }
    """
    try:
        # 获取请求参数
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        stock_code = data.get('stock_code', '').strip()
        stock_name = data.get('stock_name', '')

        # 验证股票代码
        is_valid, error_msg = validate_stock_code(stock_code)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid stock code',
                'message': error_msg
            }), 400

        # 执行多策略分析
        logger.info(f"Multi-strategy analysis requested for {stock_code}")
        result = analyzer.analyze_multi_strategy(stock_code, stock_name)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Multi-strategy analysis failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Analysis failed',
            'message': str(e)
        }), 500


@bp.route('/analyze/watchlist', methods=['POST'])
@limiter.limit("10 per hour")  # 自选股分析：每小时10次
def analyze_watchlist():
    """
    自选股监控分析接口

    请求体:
    {
        "stocks": [
            {"code": "600519", "name": "贵州茅台"},
            {"code": "600760", "name": "中航沈飞"}
        ],
        "mode": "daily"  // daily: 日报, weekly: 周报
    }

    响应:
    {
        "success": true,
        "data": {
            "report": "...",
            "highlights": [...],  // 异动股票
            "generated_at": "..."
        }
    }
    """
    try:
        # 获取请求参数
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        stocks = data.get('stocks', [])
        mode = data.get('mode', 'daily')

        # 验证参数
        if not stocks or not isinstance(stocks, list):
            return jsonify({
                'success': False,
                'error': 'Invalid stocks',
                'message': 'stocks must be a non-empty array'
            }), 400

        if mode not in ['daily', 'weekly']:
            return jsonify({
                'success': False,
                'error': 'Invalid mode',
                'message': 'mode must be "daily" or "weekly"'
            }), 400

        # 验证股票数量限制
        max_stocks = 30 if mode == 'weekly' else 10
        if len(stocks) > max_stocks:
            return jsonify({
                'success': False,
                'error': 'Too many stocks',
                'message': f'{mode} mode supports maximum {max_stocks} stocks'
            }), 400

        # 执行自选股分析
        logger.info(f"Watchlist analysis requested: {len(stocks)} stocks, mode={mode}")
        result = analyzer.analyze_watchlist(stocks, mode)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Watchlist analysis failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Analysis failed',
            'message': str(e)
        }), 500


@bp.route('/analyze/valuation', methods=['POST'])
@limiter.limit("30 per hour")  # 估值分析：每小时30次
def analyze_valuation():
    """
    估值分析接口

    请求体:
    {
        "stock_code": "600519",
        "stock_name": "贵州茅台"  // 可选
    }

    响应:
    {
        "success": true,
        "data": {
            "metrics": {...},  // 估值指标
            "summary": "...",
            "generated_at": "..."
        }
    }
    """
    try:
        # 获取请求参数
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body is required'
            }), 400

        stock_code = data.get('stock_code', '').strip()
        stock_name = data.get('stock_name', '')

        # 验证股票代码
        is_valid, error_msg = validate_stock_code(stock_code)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid stock code',
                'message': error_msg
            }), 400

        # 执行估值分析
        logger.info(f"Valuation analysis requested for {stock_code}")
        result = analyzer.analyze_valuation(stock_code, stock_name)

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"Valuation analysis failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Analysis failed',
            'message': str(e)
        }), 500
