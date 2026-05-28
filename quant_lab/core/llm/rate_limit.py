"""Provider 级速率限制器：防止触发第三方 API 限流."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """令牌桶 + 滑动窗口双层限流.

    Args:
        qps: 每秒请求数上限.
        rpm: 每分钟请求数上限.
        name: 日志标识.
    """

    qps: float
    rpm: float
    name: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _last_call: float = field(default=0.0, repr=False)
    _window: list[float] = field(default_factory=list, repr=False)

    def acquire(self) -> None:
        """阻塞直到允许发起请求."""
        with self._lock:
            now = time.monotonic()

            # 1) QPS：距上次调用不足 1/qps 秒则等待
            min_interval = 1.0 / self.qps
            elapsed = now - self._last_call
            if elapsed < min_interval:
                wait = min_interval - elapsed
                logger.debug("⏳ [%s] QPS 限流，等待 %.2fs", self.name, wait)
                time.sleep(wait)
                now = time.monotonic()

            # 2) RPM：滑动窗口，清理 60s 前的记录
            cutoff = now - 60.0
            self._window = [t for t in self._window if t > cutoff]

            if len(self._window) >= self.rpm:
                # 等到窗口中最早的记录过期
                wait = self._window[0] - cutoff + 0.05
                logger.info("⏳ [%s] RPM 限流 (%d/%d)，等待 %.1fs",
                            self.name, len(self._window), int(self.rpm), wait)
                time.sleep(wait)
                now = time.monotonic()
                self._window = [t for t in self._window if t > now - 60.0]

            self._window.append(now)
            self._last_call = now


# 全局单例，按 provider 共享
_LIMITERS: dict[str, RateLimiter] = {}
_LIMITERS_LOCK = threading.Lock()


def get_limiter(provider: str) -> RateLimiter | None:
    """返回指定 provider 的限流器；无限流策略则返回 None."""

    # 按 provider 定义限流参数
    configs: dict[str, tuple[float, float]] = {
        # (qps, rpm)
        "sensenova": (1, 5),       # 官方限制 1 QPS / 6 RPM，留 1 RPM 余量
    }

    if provider not in configs:
        return None

    with _LIMITERS_LOCK:
        if provider not in _LIMITERS:
            qps, rpm = configs[provider]
            _LIMITERS[provider] = RateLimiter(qps=qps, rpm=rpm, name=provider)
        return _LIMITERS[provider]
