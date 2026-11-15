"""个股五档快照 — 按 depth5 能力路由取数, 供盘口面板/接口共用。

与 depth_service 的区别: depth_service 只针对涨停/跌停标的批量取数算封单并落盘;
本模块服务「任意一只标的、当场要五档」的查看场景, 不落盘、不做封单计算。

数据源可切换: provider 为空时跟随 设置 → 数据源 → 五档盘口 的路由, 也可显式指定
某个声明了 depth5 的源 (TickFlow / 插件 / 自定义源), 失败即报错, 不跨源回退。
"""

from __future__ import annotations

import logging

from app.services import preferences

logger = logging.getLogger(__name__)


class DepthUnavailableError(RuntimeError):
    """当前五档数据源不可用或未返回该标的。"""


def _provider_fetcher(provider_name: str):
    """解析源 → (显示用名, get_depth_batch)。不可用时抛 DepthUnavailableError。"""
    if provider_name == "tickflow":
        from app.data_providers.registry import get_provider

        provider = get_provider("tickflow")
    else:
        from app.data_providers import custom as custom_sources

        try:
            if not custom_sources.provider_has_dataset(provider_name, "depth5"):
                raise DepthUnavailableError(f"数据源 {provider_name} 未声明五档盘口能力")
            provider = custom_sources.get_provider(provider_name)
        except DepthUnavailableError:
            raise
        except Exception as exc:
            raise DepthUnavailableError(f"数据源 {provider_name} 不可用: {exc}") from exc

    fetcher = getattr(provider, "get_depth_batch", None)
    if not callable(fetcher):
        raise DepthUnavailableError(f"数据源 {provider_name} 未实现五档取数")
    return fetcher


def resolve_provider_name(provider_name: str | None = None) -> str:
    """显式传入优先, 否则跟随五档路由偏好。"""
    name = (provider_name or "").strip()
    if name:
        return name
    return preferences.get_depth5_data_provider() or "tickflow"


def fetch_symbol_depth(symbol: str, provider_name: str | None = None) -> dict:
    """取单只标的五档。

    返回 {symbol, provider, bid_prices, bid_volumes, ask_prices, ask_volumes, timestamp};
    数组按「买一→买五 / 卖一→卖五」顺序, 数量单位手 (provider 契约)。
    """
    name = resolve_provider_name(provider_name)
    fetcher = _provider_fetcher(name)
    try:
        payload = fetcher([symbol]) or {}
    except Exception as exc:
        raise DepthUnavailableError(f"{name} 取五档失败: {exc}") from exc

    entry = payload.get(symbol) if isinstance(payload, dict) else None
    if not entry:
        raise DepthUnavailableError(f"{name} 未返回 {symbol} 的五档数据")

    return {
        "symbol": symbol,
        "provider": name,
        "bid_prices": list(entry.get("bid_prices") or []),
        "bid_volumes": list(entry.get("bid_volumes") or []),
        "ask_prices": list(entry.get("ask_prices") or []),
        "ask_volumes": list(entry.get("ask_volumes") or []),
        "timestamp": entry.get("timestamp"),
    }
