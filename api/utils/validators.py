"""
API参数验证器
"""

import re


def validate_stock_code(code: str) -> tuple[bool, str]:
    """
    验证股票代码格式

    Args:
        code: 股票代码

    Returns:
        (是否有效, 错误信息)
    """
    if not code:
        return False, "股票代码不能为空"

    code = code.strip()

    # 支持的格式:
    # - 6位数字 (如 600519, 000001)
    # - 带交易所前缀 (如 SH600519, SZ000001)
    # - 美股/港股 (如 AAPL, 00700)

    # 6位数字
    if re.match(r'^\d{6}$', code):
        return True, ""

    # 带交易所前缀
    if re.match(r'^(SH|SZ|sh|sz)\d{6}$', code, re.IGNORECASE):
        return True, ""

    # 港股5位数字
    if re.match(r'^\d{5}$', code):
        return True, ""

    # 美股字母代码
    if re.match(r'^[A-Z]{1,5}$', code):
        return True, ""

    return False, f"无效的股票代码格式: {code}"


def validate_analysis_mode(mode: str) -> tuple[bool, str]:
    """
    验证分析模式

    Args:
        mode: 分析模式

    Returns:
        (是否有效, 错误信息)
    """
    valid_modes = ['professional', 'value_first', 'quant_hybrid']

    if mode not in valid_modes:
        return False, f"无效的分析模式: {mode}，支持的模式: {', '.join(valid_modes)}"

    return True, ""


def validate_watchlist_mode(mode: str) -> tuple[bool, str]:
    """
    验证自选股监控模式

    Args:
        mode: 监控模式

    Returns:
        (是否有效, 错误信息)
    """
    valid_modes = ['daily', 'weekly']

    if mode not in valid_modes:
        return False, f"无效的监控模式: {mode}，支持的模式: {', '.join(valid_modes)}"

    return True, ""
