"""个股五档取数 (services/depth_quote) 与 /api/depth/levels 契约测试。

不依赖真实网络: 用假的 depth5 provider 注入, 验证路由跟随、显式切换、
缺数据与上游异常都转成可展示的 DepthUnavailableError (接口层映射 503)。
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api import depth as depth_api
from app.data_providers import custom as custom_sources
from app.services import depth_quote, preferences

_SYMBOL = "600519.SH"
_LEVELS = {
    _SYMBOL: {
        "bid_prices": [1435.0, 1434.8, 1434.68, 1434.6, 1434.55],
        "bid_volumes": [1, 1, 1, 1, 1],
        "ask_prices": [1435.26, 1435.27, 1435.38, 1435.49, 1435.5],
        "ask_volumes": [2, 3, 6, 9, 9],
        "timestamp": 1_794_557_695_000,
    }
}


class _Provider:
    def __init__(self, payload):
        self._payload = payload

    def get_depth_batch(self, symbols):
        return {s: self._payload[s] for s in symbols if s in self._payload}


@pytest.fixture()
def fake_custom(monkeypatch):
    """把 provider_name 映射到假实例; 默认声明支持 depth5。"""
    providers: dict[str, object] = {}
    datasets: dict[str, set[str]] = {}

    monkeypatch.setattr(custom_sources, "provider_has_dataset",
                        lambda name, ds: ds in datasets.get(name, {"depth5"}))
    monkeypatch.setattr(custom_sources, "get_provider", lambda name: providers[name])

    def _set(name: str, provider, datasets_supported=("depth5",)):
        providers[name] = provider
        datasets[name] = set(datasets_supported)

    return _set


def test_follows_routing_preference(monkeypatch, fake_custom):
    monkeypatch.setattr(preferences, "get_depth5_data_provider", lambda: "tencent_minute")
    fake_custom("tencent_minute", _Provider(_LEVELS))

    out = depth_quote.fetch_symbol_depth(_SYMBOL)

    assert out["provider"] == "tencent_minute"
    assert out["bid_prices"][0] == 1435.0
    assert out["ask_volumes"][0] == 2
    assert out["timestamp"] == 1_794_557_695_000


def test_explicit_provider_overrides_preference(monkeypatch, fake_custom):
    monkeypatch.setattr(preferences, "get_depth5_data_provider", lambda: "tencent_minute")
    fake_custom("tencent_minute", _Provider({}))
    fake_custom("other_depth", _Provider(_LEVELS))

    out = depth_quote.fetch_symbol_depth(_SYMBOL, "other_depth")
    assert out["provider"] == "other_depth"


def test_missing_symbol_raises(monkeypatch, fake_custom):
    monkeypatch.setattr(preferences, "get_depth5_data_provider", lambda: "tencent_minute")
    fake_custom("tencent_minute", _Provider({}))
    with pytest.raises(depth_quote.DepthUnavailableError):
        depth_quote.fetch_symbol_depth(_SYMBOL)


def test_provider_without_dataset_is_rejected(monkeypatch, fake_custom):
    monkeypatch.setattr(preferences, "get_depth5_data_provider", lambda: "no_depth")
    fake_custom("no_depth", _Provider(_LEVELS), datasets_supported=("minute",))
    with pytest.raises(depth_quote.DepthUnavailableError):
        depth_quote.fetch_symbol_depth(_SYMBOL)


def test_upstream_exception_becomes_unavailable(monkeypatch, fake_custom):
    monkeypatch.setattr(preferences, "get_depth5_data_provider", lambda: "tencent_minute")

    class _Boom:
        def get_depth_batch(self, symbols):
            raise RuntimeError("上游 502")

    fake_custom("tencent_minute", _Boom())
    with pytest.raises(depth_quote.DepthUnavailableError):
        depth_quote.fetch_symbol_depth(_SYMBOL)


def test_endpoint_maps_unavailable_to_503(monkeypatch, fake_custom):
    monkeypatch.setattr(preferences, "get_depth5_data_provider", lambda: "tencent_minute")
    fake_custom("tencent_minute", _Provider({}))
    with pytest.raises(HTTPException) as exc:
        depth_api.depth_levels(symbol=_SYMBOL, provider=None)
    assert exc.value.status_code == 503


def test_endpoint_returns_levels(monkeypatch, fake_custom):
    monkeypatch.setattr(preferences, "get_depth5_data_provider", lambda: "tencent_minute")
    fake_custom("tencent_minute", _Provider(_LEVELS))
    payload = depth_api.depth_levels(symbol=f"  {_SYMBOL}  ", provider="tencent_minute")
    assert payload["symbol"] == _SYMBOL
    assert payload["provider"] == "tencent_minute"
    assert len(payload["ask_prices"]) == 5
