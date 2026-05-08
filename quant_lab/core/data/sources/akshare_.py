"""Backwards-compatibility shim — DO NOT add new code here.

All functions live in eastmoney.py, xueqiu.py, sina.py. This file will
be deleted in a follow-up task once all dimension imports are migrated.
"""

from quant_lab.core.data.sources.eastmoney import (
    fetch_eastmoney_kline,
    fetch_financial_report,
    fetch_stock_info_eastmoney,
)
from quant_lab.core.data.sources.sina import fetch_sina_kline
from quant_lab.core.data.sources.xueqiu import fetch_xueqiu_spot

__all__ = [
    "fetch_eastmoney_kline",
    "fetch_financial_report",
    "fetch_sina_kline",
    "fetch_stock_info_eastmoney",
    "fetch_xueqiu_spot",
]
