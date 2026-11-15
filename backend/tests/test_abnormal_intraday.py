"""盘中异动聚合测试 (build_intraday, 不依赖真实网络/enriched)。

覆盖: 信号命中过滤、counts 计数、优先级排序 (涨停 > 炸板 > …)、
多信号行、limit 截断、空快照与缺信号列的降级。
"""

from __future__ import annotations

from datetime import date

import polars as pl

from app.services.abnormal_moves import build_intraday


class _FakeRepo:
    def __init__(self, df: pl.DataFrame):
        self._df = df

    def get_enriched_latest(self):
        return self._df, date(2026, 8, 28)


def _df(rows: list[dict]) -> pl.DataFrame:
    cols = ["symbol", "name", "close", "change_pct", "amplitude", "vol_ratio_5d",
            "turnover_rate", "consecutive_limit_ups",
            "signal_limit_up", "signal_broken_limit_up", "signal_limit_down_recovery",
            "signal_limit_down", "signal_n_day_high", "signal_n_day_low",
            "signal_volume_surge"]
    base = {c: [] for c in cols}
    for r in rows:
        for c in cols:
            base[c].append(r.get(c))
    return pl.DataFrame(base)


def test_counts_filter_and_priority():
    repo = _FakeRepo(_df([
        {"symbol": "A1", "name": "甲", "close": 10.0, "change_pct": 0.1,
         "signal_limit_up": True, "signal_n_day_high": True},
        {"symbol": "B1", "name": "乙", "close": 5.0, "change_pct": -0.05,
         "signal_limit_down": True},
        {"symbol": "C1", "name": "丙", "close": 8.0, "change_pct": 0.02,
         "signal_volume_surge": True},
        {"symbol": "D1", "name": "丁", "close": 7.0, "change_pct": None},  # 无信号 → 不出现
    ]))
    out = build_intraday(repo)
    assert out["cache_date"] == "2026-08-28"
    assert out["counts"] == {"limit_up": 1, "broken": 0, "recovery": 0,
                             "limit_down": 1, "new_high": 1, "new_low": 0,
                             "volume_surge": 1}
    syms = [r["symbol"] for r in out["rows"]]
    assert syms == ["A1", "B1", "C1"]  # 优先级: 涨停 > 跌停 > 放量; 无信号被过滤
    assert out["rows"][0]["signals"] == ["limit_up", "new_high"]  # 多信号按优先级序


def test_limit_truncates():
    repo = _FakeRepo(_df([
        {"symbol": f"S{i}", "signal_volume_surge": True, "change_pct": 0.01} for i in range(10)
    ]))
    out = build_intraday(repo, limit=3)
    assert len(out["rows"]) == 3
    assert out["counts"]["volume_surge"] == 10  # counts 不受 limit 影响


def test_empty_snapshot():
    repo = _FakeRepo(pl.DataFrame({"symbol": [], "name": []}))
    out = build_intraday(repo)
    assert out["rows"] == [] and out["counts"] == {}


def test_missing_signal_columns_degrades():
    repo = _FakeRepo(pl.DataFrame({"symbol": ["A1"], "name": ["甲"]}))
    out = build_intraday(repo)
    assert out["rows"] == [] and out["counts"] == {}


class _FakeRepoNoName(_FakeRepo):
    """enriched 快照没有 name 列 (真实仓库 15 列基础数据的形态), 名称只能取维表。"""

    def __init__(self, df: pl.DataFrame, names: dict[str, str]):
        super().__init__(df)
        self._names = names

    def get_name_map(self, symbols=None):
        wanted = set(symbols or ())
        return {s: n for s, n in self._names.items() if not wanted or s in wanted}


def test_names_filled_from_instruments_when_enriched_has_no_name():
    df = pl.DataFrame({
        "symbol": ["600519.SH", "000001.SZ"],
        "close": [1400.0, 12.0],
        "change_pct": [0.01, -0.02],
        "vol_ratio_5d": [2.1, 3.0],
        "signal_limit_up": [True, False],
        "signal_volume_surge": [False, True],
    })
    repo = _FakeRepoNoName(df, {"600519.SH": "贵州茅台", "000001.SZ": "平安银行"})
    out = build_intraday(repo)
    names = {r["symbol"]: r["name"] for r in out["rows"]}
    assert names == {"600519.SH": "贵州茅台", "000001.SZ": "平安银行"}


def test_name_lookup_failure_does_not_break_rows():
    df = pl.DataFrame({
        "symbol": ["600519.SH"],
        "close": [1400.0],
        "change_pct": [0.01],
        "signal_limit_up": [True],
    })

    class _Broken(_FakeRepo):
        def get_name_map(self, symbols=None):
            raise RuntimeError("instruments 维表不可读")

    out = build_intraday(_Broken(df))
    assert out["rows"][0]["symbol"] == "600519.SH"
    assert out["rows"][0]["name"] is None
