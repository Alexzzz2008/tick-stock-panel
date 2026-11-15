"""minute-batch 权限门禁: 以当前分钟源可用性为准, 不是 TickFlow 档位。

回归场景: 用户把「分钟K」路由到自定义插件 (设置页显示已适配), 但 TickFlow 是
None/Free 档 → 旧实现只看 capset.has(KLINE_MINUTE_BATCH), 详情页 5/10/20 日
分时回补一律 403「需要 Pro+ 权限」。
"""
from __future__ import annotations

import pytest

from app.api import kline as kline_api
from app.tickflow.capabilities import Cap, CapabilitySet


class _Healthy:
    def is_healthy(self) -> bool:
        return True


class _Sick:
    def is_healthy(self) -> bool:
        return False


@pytest.fixture()
def provider(monkeypatch):
    def _set(name: str) -> None:
        monkeypatch.setattr(kline_api.kline_sync, "_selected_minute_provider_name", lambda: name)

    return _set


def test_tickflow_without_cap_is_denied(provider):
    provider("tickflow")
    assert kline_api._minute_batch_denial(CapabilitySet(), None) == "需要 Pro+ 权限 (kline.minute.batch)"


def test_custom_minute_provider_is_allowed(provider, monkeypatch):
    provider("tencent_minute")
    monkeypatch.setattr(kline_api, "_minute_allowed", lambda capset: True)
    assert kline_api._minute_batch_denial(CapabilitySet(), None) is None


def test_custom_provider_unavailable_reports_config_hint(provider, monkeypatch):
    provider("tencent_minute")
    monkeypatch.setattr(kline_api, "_minute_allowed", lambda capset: False)
    detail = kline_api._minute_batch_denial(CapabilitySet(), None)
    assert detail == "当前分钟数据源不可用, 请先在设置中配置可用数据源"


def test_healthy_full_minute_service_opens_gate(provider, monkeypatch):
    provider("tickflow")
    monkeypatch.setattr(kline_api, "_minute_allowed", lambda capset: False)
    assert kline_api._minute_batch_denial(CapabilitySet(), _Healthy()) is None


def test_sick_full_minute_service_does_not_open_gate(provider, monkeypatch):
    provider("tickflow")
    monkeypatch.setattr(kline_api, "_minute_allowed", lambda capset: False)
    assert kline_api._minute_batch_denial(CapabilitySet(), _Sick()) is not None


def test_capability_alone_still_passes(provider):
    provider("tickflow")
    capset = CapabilitySet()
    capset.grant(Cap.KLINE_MINUTE_BATCH)
    assert kline_api._minute_batch_denial(capset, None) is None
