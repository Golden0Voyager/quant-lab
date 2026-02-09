"""
智能缓存管理模块
支持分层缓存策略，减少API调用，提升性能
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)


class QuantJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理numpy、pandas、日期等类型"""
    def default(self, obj):
        # 处理日期对象
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        
        # 处理 pandas 的 NA 和 Timestamp
        try:
            import pandas as pd
            if pd.isna(obj):
                return None
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
        except ImportError:
            pass

        # 处理 numpy 数据类型
        try:
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
        except ImportError:
            pass
            
        return str(obj) # 最后的兜底方案：转为字符串避免报错


class DataCache:
    """数据缓存管理器"""

    def __init__(self, db_path: str = None):
        """
        初始化缓存管理器

        Args:
            db_path: SQLite数据库路径（默认: cache/quant_cache.db）
        """
        if db_path is None:
            # 默认使用 cache/ 目录下的数据库
            script_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(script_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, "quant_cache.db")

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 启用 WAL 模式，提升多线程并发读写性能
        cursor.execute("PRAGMA journal_mode=WAL")

        # 创建缓存主表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            data_type TEXT NOT NULL,
            data_json TEXT NOT NULL,
            cached_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            UNIQUE(symbol, data_type)
        )
        """)

        # 创建索引（加速查询）
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_type
        ON data_cache(symbol, data_type)
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_expires
        ON data_cache(expires_at)
        """)

        # 创建历史数据表（用于计算分位数）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_valuation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date DATE NOT NULL,
            pe_ttm REAL,
            pb REAL,
            ps_ttm REAL,
            dividend_yield REAL,
            UNIQUE(symbol, date)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_hist_symbol_date
        ON historical_valuation(symbol, date)
        """)

        conn.commit()
        conn.close()

        logger.info(f"✅ 缓存数据库初始化完成: {self.db_path}")

    def get(self, symbol: str, data_type: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取数据

        Args:
            symbol: 股票代码
            data_type: 数据类型（valuation/performance/sentiment等）

        Returns:
            缓存的数据字典，如果不存在或过期返回None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
            SELECT data_json, expires_at
            FROM data_cache
            WHERE symbol = ? AND data_type = ?
            """, (symbol, data_type))

            result = cursor.fetchone()

            if result is None:
                logger.debug(f"缓存未命中: {symbol} - {data_type}")
                return None

            data_json, expires_at_str = result
            expires_at = datetime.fromisoformat(expires_at_str)

            # 检查是否过期
            if datetime.now() > expires_at:
                logger.debug(f"缓存已过期: {symbol} - {data_type}")
                # 删除过期缓存
                cursor.execute("""
                DELETE FROM data_cache
                WHERE symbol = ? AND data_type = ?
                """, (symbol, data_type))
                conn.commit()
                return None

            # 缓存命中
            logger.info(f"✅ 缓存命中: {symbol} - {data_type}")
            return json.loads(data_json)

        except Exception as e:
            logger.error(f"缓存读取失败: {e}")
            return None
        finally:
            conn.close()

    def set(self, symbol: str, data_type: str, data: Dict[str, Any], ttl_seconds: int):
        """
        写入缓存

        Args:
            symbol: 股票代码
            data_type: 数据类型
            data: 要缓存的数据字典
            ttl_seconds: 缓存有效期（秒）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            # 使用自定义编码器，确保 numpy 数据类型、布尔值和日期能正确序列化
            data_json = json.dumps(data, ensure_ascii=False, cls=QuantJSONEncoder)

            # UPSERT操作（如果存在则更新，不存在则插入）
            cursor.execute("""
            INSERT INTO data_cache (symbol, data_type, data_json, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol, data_type)
            DO UPDATE SET
                data_json = excluded.data_json,
                cached_at = CURRENT_TIMESTAMP,
                expires_at = excluded.expires_at
            """, (symbol, data_type, data_json, expires_at.isoformat()))

            conn.commit()
            logger.info(f"✅ 数据已缓存: {symbol} - {data_type} (TTL: {ttl_seconds}s)")

        except Exception as e:
            logger.error(f"缓存写入失败: {e}")
        finally:
            conn.close()

    def save_historical_valuation(self, symbol: str, date: str, valuation_data: Dict[str, Any]):
        """
        保存历史估值数据（用于计算分位数）

        Args:
            symbol: 股票代码
            date: 日期 (YYYY-MM-DD)
            valuation_data: 估值数据
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 提取估值指标
            pe_ttm = self._parse_float(valuation_data.get('pe_ttm'))
            pb = self._parse_float(valuation_data.get('pb'))
            ps_ttm = self._parse_float(valuation_data.get('ps'))
            dividend_yield = self._parse_float(valuation_data.get('dividend_yield', '0').rstrip('%'))

            cursor.execute("""
            INSERT INTO historical_valuation (symbol, date, pe_ttm, pb, ps_ttm, dividend_yield)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date)
            DO UPDATE SET
                pe_ttm = excluded.pe_ttm,
                pb = excluded.pb,
                ps_ttm = excluded.ps_ttm,
                dividend_yield = excluded.dividend_yield
            """, (symbol, date, pe_ttm, pb, ps_ttm, dividend_yield))

            conn.commit()
            logger.debug(f"历史估值已保存: {symbol} - {date}")

        except Exception as e:
            logger.error(f"历史估值保存失败: {e}")
        finally:
            conn.close()

    def get_historical_valuation(self, symbol: str, days: int = 365 * 3) -> list:
        """
        获取历史估值数据

        Args:
            symbol: 股票代码
            days: 获取最近多少天的数据（默认3年）

        Returns:
            历史估值数据列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            start_date = (datetime.now() - timedelta(days=days)).date()

            cursor.execute("""
            SELECT date, pe_ttm, pb, ps_ttm, dividend_yield
            FROM historical_valuation
            WHERE symbol = ? AND date >= ?
            ORDER BY date DESC
            """, (symbol, start_date))

            rows = cursor.fetchall()

            return [
                {
                    'date': row[0],
                    'pe_ttm': row[1],
                    'pb': row[2],
                    'ps_ttm': row[3],
                    'dividend_yield': row[4]
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"历史估值读取失败: {e}")
            return []
        finally:
            conn.close()

    def clean_expired(self):
        """清理过期缓存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
            DELETE FROM data_cache
            WHERE expires_at < ?
            """, (datetime.now().isoformat(),))

            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                logger.info(f"✅ 已清理 {deleted_count} 条过期缓存")

        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
        finally:
            conn.close()

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 总缓存数
            cursor.execute("SELECT COUNT(*) FROM data_cache")
            total_count = cursor.fetchone()[0]

            # 有效缓存数
            cursor.execute("""
            SELECT COUNT(*) FROM data_cache
            WHERE expires_at > ?
            """, (datetime.now().isoformat(),))
            valid_count = cursor.fetchone()[0]

            # 各类型缓存数量
            cursor.execute("""
            SELECT data_type, COUNT(*)
            FROM data_cache
            WHERE expires_at > ?
            GROUP BY data_type
            """, (datetime.now().isoformat(),))
            type_counts = dict(cursor.fetchall())

            # 历史数据点数
            cursor.execute("SELECT COUNT(*) FROM historical_valuation")
            historical_count = cursor.fetchone()[0]

            return {
                'total_cache': total_count,
                'valid_cache': valid_count,
                'expired_cache': total_count - valid_count,
                'type_distribution': type_counts,
                'historical_points': historical_count
            }

        except Exception as e:
            logger.error(f"统计信息获取失败: {e}")
            return {}
        finally:
            conn.close()

    @staticmethod
    def _parse_float(value: Any) -> Optional[float]:
        """安全地将值转换为float"""
        if value is None or value == 'N/A':
            return None
        try:
            # 移除百分号
            if isinstance(value, str):
                value = value.rstrip('%')
            return float(value)
        except (ValueError, TypeError):
            return None


# ==================== 缓存策略配置 ====================

class CacheStrategy:
    """缓存策略配置"""

    # TTL配置（秒）
    TTL_REALTIME = 5 * 60           # 5分钟（实时行情）
    TTL_HOUR = 60 * 60              # 1小时（新闻、汇率）
    TTL_DAY = 24 * 60 * 60          # 24小时（估值、资金流向）
    TTL_WEEK = 7 * 24 * 60 * 60     # 7天（业绩数据）
    TTL_MONTH = 30 * 24 * 60 * 60   # 30天（股东数据）

    # 数据类型映射到TTL
    TYPE_TTL_MAP = {
        'valuation': TTL_DAY,         # 估值数据（PE/PB/PS）
        'performance': TTL_WEEK,      # 业绩数据（财报）
        'sentiment_realtime': TTL_REALTIME,  # 实时行情（量比/换手率）
        'sentiment_daily': TTL_DAY,   # 日度资金流向
        'sentiment_holder': TTL_MONTH,  # 股东数据
        'news': TTL_HOUR,             # 新闻舆情
        'macro': TTL_HOUR,            # 宏观数据（汇率）
        'etf_premium': TTL_REALTIME,  # ETF折溢价
        'tech_daily': TTL_DAY,        # 日K线
        # 新增数据维度
        'consensus': TTL_WEEK,        # 分析师一致预期（7天）
        'market_env': TTL_DAY,        # 大盘/板块环境（盘中5分钟，盘后24小时）
        'lockup': TTL_WEEK,           # 解禁/减持风险（7天）
        'chip': TTL_DAY,              # 筹码分布（24小时）
        'institution': TTL_MONTH,     # 机构持仓变化（30天，季度数据）
        'competitor': TTL_WEEK,       # 竞争对手对比（7天）
    }

    @classmethod
    def get_ttl(cls, data_type: str) -> int:
        """
        智能获取数据类型对应的TTL

        对于交易日相关数据（stock_base, valuation, sentiment_daily），
        使用智能TTL策略，避免跨交易日使用过期数据
        """
        # 交易日相关数据类型（需要智能TTL）
        trading_day_types = {'stock_base', 'valuation', 'sentiment_daily', 'tech_daily', 'market_env', 'chip'}

        if data_type in trading_day_types:
            return cls._get_smart_ttl_for_trading_data()
        else:
            # 其他数据类型使用固定TTL
            return cls.TYPE_TTL_MAP.get(data_type, cls.TTL_DAY)

    @classmethod
    def _get_smart_ttl_for_trading_data(cls) -> int:
        """
        为交易日相关数据计算智能TTL

        策略：
        1. 交易时间内（9:30-15:00）：5分钟（实时更新）
        2. 收盘后（15:00-次日9:00）：缓存到次日9:00
        3. 周末/节假日：缓存到下一个交易日9:00

        Returns:
            TTL秒数
        """
        now = datetime.now()
        current_time = now.time()

        # 定义交易时段
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("15:00", "%H:%M").time()

        # 1. 如果在交易时间内 -> 5分钟TTL（实时更新）
        if now.weekday() < 5 and market_open <= current_time < market_close:
            return 5 * 60  # 5分钟

        # 2. 非交易时间 -> 缓存到下一个交易日的9:00
        next_trading_day_9am = cls._get_next_trading_day_9am(now)
        ttl_seconds = int((next_trading_day_9am - now).total_seconds())

        # 确保TTL至少为60秒
        return max(ttl_seconds, 60)

    @staticmethod
    def _get_next_trading_day_9am(now: datetime) -> datetime:
        """
        计算下一个交易日的9:00

        Args:
            now: 当前时间

        Returns:
            下一个交易日9:00的datetime对象
        """
        current_time = now.time()
        market_open = datetime.strptime("09:00", "%H:%M").time()

        # 如果当前是工作日且未到9:00，下一个交易日就是今天
        if now.weekday() < 5 and current_time < market_open:
            next_day = now
        else:
            # 否则找下一个工作日
            next_day = now + timedelta(days=1)
            while next_day.weekday() >= 5:  # 跳过周末
                next_day += timedelta(days=1)

        # 设置为9:00
        return next_day.replace(hour=9, minute=0, second=0, microsecond=0)

    @staticmethod
    def is_trading_time() -> bool:
        """判断是否在交易时间内（用于决定是否更新实时数据）"""
        now = datetime.now()

        # 周末不交易
        if now.weekday() >= 5:
            return False

        # 交易时间：9:30-11:30, 13:00-15:00
        time_now = now.time()
        morning_start = datetime.strptime("09:30", "%H:%M").time()
        morning_end = datetime.strptime("11:30", "%H:%M").time()
        afternoon_start = datetime.strptime("13:00", "%H:%M").time()
        afternoon_end = datetime.strptime("15:00", "%H:%M").time()

        return (morning_start <= time_now <= morning_end) or \
               (afternoon_start <= time_now <= afternoon_end)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 初始化缓存
    cache = DataCache("test_cache.db")

    # 测试写入
    test_data = {
        'pe_ttm': '15.32',
        'pb': '1.85',
        'ps': '0.78',
        'dividend_yield': '3.5%'
    }

    print("测试缓存写入...")
    cache.set("002683", "valuation", test_data, CacheStrategy.TTL_DAY)

    # 测试读取
    print("\n测试缓存读取...")
    cached_data = cache.get("002683", "valuation")
    print(f"读取结果: {cached_data}")

    # 保存历史数据
    print("\n测试历史数据保存...")
    cache.save_historical_valuation("002683", "2024-12-21", test_data)

    # 获取历史数据
    print("\n测试历史数据读取...")
    history = cache.get_historical_valuation("002683", days=30)
    print(f"历史数据点数: {len(history)}")

    # 缓存统计
    print("\n缓存统计信息:")
    stats = cache.get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 清理测试
    print("\n清理过期缓存...")
    cache.clean_expired()

    print("\n✅ 缓存系统测试完成！")
