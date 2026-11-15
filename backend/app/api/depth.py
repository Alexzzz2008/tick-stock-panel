"""五档盘口 API — 单只标的的买卖五档快照。

数据源可切换: 不传 provider 时跟随「设置 → 数据源 → 五档盘口」的路由,
传了就用该源; 源不可用或未返回该标的时 503, 不跨源回退 (避免口径混乱)。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.depth_quote import DepthUnavailableError, fetch_symbol_depth

router = APIRouter(prefix="/api/depth", tags=["depth"])


@router.get("/levels")
def depth_levels(
    symbol: str = Query(..., min_length=1, description="标的代码, 如 600519.SH"),
    provider: str | None = Query(None, description="五档数据源; 省略则跟随设置"),
):
    """单只标的五档 (买一→买五 / 卖一→卖五, 数量单位手)。"""
    try:
        return fetch_symbol_depth(symbol.strip(), provider)
    except DepthUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
