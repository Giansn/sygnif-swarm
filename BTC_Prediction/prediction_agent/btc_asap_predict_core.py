"""
Shared **live 5m predict + sizing** helpers for ``btc_predict_asap_order`` and
``btc_predict_protocol_loop`` (Bybit demo REST paths).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from btc_analysis_order_signal import r01_bearish_from_training
from btc_predict_live import fetch_linear_5m_klines
from btc_predict_live import fit_predict_live


def env_int(name: str, default: int, *, lo: int, hi: int) -> int:
    raw = os.environ.get(name, str(default)).strip() or str(default)
    try:
        v = int(float(raw))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default)).strip() or str(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def parse_usdt_available(resp: dict[str, Any]) -> float | None:
    if resp.get("retCode") != 0:
        return None
    lst = (resp.get("result") or {}).get("list") or []
    if not lst:
        return None
    coins = lst[0].get("coin") or []
    for c in coins:
        if str(c.get("coin", "")).upper() != "USDT":
            continue
        for key in ("availableToWithdraw", "availableBalance", "transferBalance"):
            raw = c.get(key)
            if raw is not None and str(raw).strip() != "":
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    pass
        try:
            return float(c.get("walletBalance") or 0.0)
        except (TypeError, ValueError):
            return None
    return None


def move_pct_and_close(out: dict[str, Any]) -> tuple[float, float]:
    close = float(out.get("current_close") or 0.0)
    preds = out.get("predictions") or {}
    rf = preds.get("random_forest") or {}
    xg = preds.get("xgboost") or {}
    try:
        d1 = abs(float(rf.get("delta") or 0.0))
        d2 = abs(float(xg.get("delta") or 0.0))
    except (TypeError, ValueError):
        d1, d2 = 0.0, 0.0
    mean_abs = (d1 + d2) / 2.0
    if close <= 0:
        return 0.0, close
    return (mean_abs / close) * 100.0, close


def leverage_from_move_pct(move_pct: float) -> tuple[int, float]:
    lo = env_int("BYBIT_DEMO_ORDER_MIN_LEVERAGE", 5, lo=1, hi=125)
    hi = env_int("BYBIT_DEMO_ORDER_MAX_LEVERAGE", 25, lo=1, hi=125)
    if lo > hi:
        lo, hi = hi, lo
    floor_p = max(1e-6, env_float("ASAP_MOVE_LEV_FLOOR_PCT", 0.03))
    cap_p = max(floor_p + 1e-6, env_float("ASAP_MOVE_LEV_CAP_PCT", 1.0))
    t = (move_pct - floor_p) / (cap_p - floor_p)
    t = max(0.0, min(1.0, t))
    lev = int(round(hi - t * (hi - lo)))
    return max(lo, min(hi, lev)), t


def decide_side(out: dict[str, Any], training: dict[str, Any] | None) -> tuple[str | None, str]:
    preds = out.get("predictions") or {}
    rf = preds.get("random_forest") or {}
    xg = preds.get("xgboost") or {}
    dlr = preds.get("direction_logistic") or {}
    try:
        d_rf = float(rf.get("delta") or 0.0)
        d_xg = float(xg.get("delta") or 0.0)
    except (TypeError, ValueError):
        d_rf, d_xg = 0.0, 0.0
    label = str(dlr.get("label", "") or "").strip().upper()
    try:
        conf = float(dlr.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0

    v = 0
    if d_rf > 0:
        v += 1
    elif d_rf < 0:
        v -= 1
    if d_xg > 0:
        v += 1
    elif d_xg < 0:
        v -= 1
    thr = env_float("ASAP_LOGREG_VOTE_CONF", 52.0)
    if label == "UP" and conf >= thr:
        v += 1
    if label == "DOWN" and conf >= thr:
        v -= 1

    bear = r01_bearish_from_training(training if isinstance(training, dict) else {})

    if v > 0:
        if bear:
            return None, "long blocked (R01 bearish stack)"
        return "long", f"vote={v} RFΔ={d_rf:.2f} XGBΔ={d_xg:.2f} logreg={label}/{conf:.1f}%"
    if v < 0:
        return "short", f"vote={v} RFΔ={d_rf:.2f} XGBΔ={d_xg:.2f} logreg={label}/{conf:.1f}%"

    brk = env_float("ASAP_LOGREG_TIEBREAK_CONF", 58.0)
    if label == "UP" and conf >= brk:
        if bear:
            return None, "tiebreak long blocked (R01 bearish stack)"
        return "long", f"tiebreak logreg UP {conf:.1f}%"
    if label == "DOWN" and conf >= brk:
        return "short", f"tiebreak logreg DOWN {conf:.1f}%"
    return None, f"no edge (vote=0 logreg={label}/{conf:.1f}%)"


def qty_btc(
    *,
    free_usdt: float,
    close: float,
    t_move: float,
    logreg_conf: float,
) -> tuple[str, float]:
    min_q = max(1e-9, env_float("BYBIT_DEMO_ORDER_MIN_QTY", 0.001))
    max_q = max(1e-9, env_float("BYBIT_DEMO_ORDER_MAX_QTY", 0.08))
    if max_q < min_q:
        max_q = min_q
    base_frac = max(1e-6, min(1.0, env_float("BYBIT_DEMO_ORDER_STAKE_FRAC", 0.002)))
    move_boost = 0.45 + 0.55 * t_move
    conf_floor = env_float("ASAP_LOGREG_VOTE_CONF", 52.0)
    span = max(1.0, 100.0 - conf_floor)
    conf_t = max(0.0, min(1.0, (logreg_conf - conf_floor) / span))
    conv = 0.55 + 0.45 * conf_t
    eff = base_frac * move_boost * conv
    eff = min(eff, 0.25)
    notional = free_usdt * eff
    if close <= 0:
        return "", eff
    raw_qty = notional / close
    raw_qty = max(min_q, min(max_q, raw_qty))
    step = 0.001
    q = math.floor(raw_qty / step) * step
    if q + 1e-12 < min_q:
        return "", eff
    s = f"{q:.6f}".rstrip("0").rstrip(".")
    return (s if s else str(min_q)), eff


def run_live_fit(
    *,
    symbol: str,
    kline_limit: int,
    window: int,
    data_dir: str,
    rf_trees: int,
    xgb_estimators: int,
    write_json_path: str | None,
) -> tuple[bool, str, dict[str, Any], float]:
    """
    Fetch klines, ``fit_predict_live``, return (allow_buy, enhanced, out_dict, predict_ms).
    """
    import time

    t0 = time.perf_counter()
    df = fetch_linear_5m_klines(symbol, limit=min(1000, max(120, kline_limit)))
    allow_buy, enhanced, out = fit_predict_live(
        df,
        window=max(3, window),
        data_dir=data_dir,
        rf_trees=rf_trees,
        xgb_estimators=xgb_estimators,
        write_json_path=write_json_path,
    )
    pred_ms = (time.perf_counter() - t0) * 1000.0
    return allow_buy, enhanced, out, pred_ms


def parse_linear_position(
    resp: dict[str, Any],
    symbol: str,
) -> tuple[str | None, float, str]:
    """
    Return (side: long|short|None, abs size, raw size string for close orders).
    """
    sym = symbol.upper().strip()
    if resp.get("retCode") != 0:
        return None, 0.0, ""
    best_raw = ""
    best_sz = 0.0
    best_side: str | None = None
    for row in (resp.get("result") or {}).get("list") or []:
        if str(row.get("symbol", "")).upper() != sym:
            continue
        raw_sz = str(row.get("size") or "").strip()
        try:
            sz = float(raw_sz)
        except (TypeError, ValueError):
            continue
        if abs(sz) < 1e-12:
            continue
        side_api = str(row.get("side") or "").strip().lower()
        if side_api == "buy":
            s = "long"
        elif side_api == "sell":
            s = "short"
        else:
            continue
        if abs(sz) > best_sz:
            best_sz = abs(sz)
            best_side = s
            best_raw = raw_sz
    return best_side, best_sz, best_raw


def logreg_confidence(out: dict[str, Any]) -> float:
    dlr = (out.get("predictions") or {}).get("direction_logistic") or {}
    try:
        return float(dlr.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0
