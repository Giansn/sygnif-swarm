#!/usr/bin/env python3
"""
Apply **TP / SL / trailing** to the open Bybit **demo** linear position from ``btc_prediction_output.json``.

**Not** part of ``compute_swarm()`` (read-only Swarm). This module **POST**s
``/v5/position/trading-stop`` when enabled.

Env:

- ``SYGNIF_SWARM_BTC_FUTURE_AUTO_TPSL=1`` — run apply (default **on** when ``swarm_sync_protocol`` sets it).
- ``SYGNIF_SWARM_TPSL_SYMBOL`` — default ``BTCUSDT``.
- ``SYGNIF_SWARM_TPSL_PROFILE`` — ``default`` | ``reward_risk``. **reward_risk** = wider TP fallback, tighter SL,
  slightly higher trail (favor asymmetric R:R vs legacy defaults). Per-key env vars still override the profile base.
- ``SYGNIF_SWARM_TPSL_TP_PCT`` — fallback TP distance from avg entry (%%); profile default if unset.
- ``SYGNIF_SWARM_TPSL_SL_PCT`` — SL distance from avg entry (%%); profile default if unset.
- ``SYGNIF_SWARM_TPSL_TRAIL_USD`` / ``SYGNIF_SWARM_TPSL_TRAIL_FRAC`` — trailing; profile defaults if unset.
- ``SYGNIF_SWARM_TPSL_CHANNEL_ADJUST=1`` — nudge TP/SL from ``training_channel_output.json`` ``recognition``
  probabilities (channel training **ch** vote, aligned with btc-specialist bundle). Default **on**.
- ``SYGNIF_SWARM_TPSL_SKIP_ON_SWARM_CONFLICT=1`` — skip if ``swarm_knowledge_output.json`` has
  ``swarm_conflict`` (default **on**).

Writes ``prediction_agent/swarm_btc_future_tpsl_last.json`` with the last run result (no secrets).

**Consulting:** use Cursor **Task** ``subagent_type=finance-agent`` after sync; feed paths to
``swarm_knowledge_output.json``, ``btc_prediction_output.json``, ``training_channel_output.json``,
and ``finance_agent/btc_specialist/data/manifest.json``. See ``scripts/swarm_channel_finance_consult.sh``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dotenv_file(path: Path, *, override: bool = False) -> None:
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if not k:
            continue
        v = v.strip().strip('"').strip("'")
        if override:
            os.environ[k] = v
        else:
            os.environ.setdefault(k, v)


def load_repo_env() -> None:
    """Same merge order as ``scripts/swarm_sync_protocol.py`` (secrets + demo keys)."""
    raw = (os.environ.get("SYGNIF_SECRETS_ENV_FILE") or "").strip()
    if raw:
        _load_dotenv_file(Path(raw).expanduser())
    _load_dotenv_file(Path.home() / "xrp_claude_bot" / ".env")
    _load_dotenv_file(_repo_root() / ".env")


def _prediction_dir() -> Path:
    for key in ("PREDICTION_AGENT_DIR", "SYGNIF_PREDICTION_AGENT_DIR"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            return Path(raw).expanduser()
    return _repo_root() / "prediction_agent"


def _env_truthy(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def base_tpsl_from_profile() -> tuple[float, float, float, float]:
    """
    Defaults for TP/SL/trail when individual env vars are unset.

    ``reward_risk``: wider TP fallback, tighter SL, slightly more trail — favors payoff vs
    legacy ``default`` (still subject to Bybit mark clamp for shorts).
    """
    prof = (os.environ.get("SYGNIF_SWARM_TPSL_PROFILE") or "").strip().lower()
    if prof in ("reward_risk", "rr"):
        return 0.75, 0.22, 200.0, 0.2
    return 0.5, 0.35, 150.0, 0.25


def channel_adjust_tpsl(
    side: str,
    tp_pct: float,
    sl_pct: float,
    trail_usd: float,
) -> tuple[float, float, float, dict[str, Any]]:
    """
    Nudge TP/SL/trail from ``training_channel_output.json`` (``ch`` / channel recognition).

    When channel probability **aligns** with the open leg (up for long, down for short), slightly
    widen TP target and loosen risk (tighter SL). When misaligned / low confidence, tighten SL.
    """
    meta: dict[str, Any] = {"enabled": False}
    if not _env_truthy("SYGNIF_SWARM_TPSL_CHANNEL_ADJUST", default=True):
        meta["reason"] = "SYGNIF_SWARM_TPSL_CHANNEL_ADJUST_off"
        return tp_pct, sl_pct, trail_usd, meta
    ch = _read_json(_prediction_dir() / "training_channel_output.json")
    if not ch:
        meta["reason"] = "missing_training_channel_output.json"
        return tp_pct, sl_pct, trail_usd, meta
    rec = ch.get("recognition") if isinstance(ch.get("recognition"), dict) else {}
    try:
        up = float(rec.get("last_bar_probability_up_pct") or 50.0)
        dn = float(rec.get("last_bar_probability_down_pct") or 50.0)
    except (TypeError, ValueError):
        up, dn = 50.0, 50.0
    su = (side or "").strip().upper()
    meta["enabled"] = True
    meta["channel_up_pct"] = round(up, 4)
    meta["channel_down_pct"] = round(dn, 4)
    note = ""
    if su == "BUY":
        if up >= 58.0:
            tp_pct *= 1.12
            sl_pct *= 0.92
            trail_usd *= 1.08
            note = "align_long_channel_up"
        elif up < 45.0:
            sl_pct *= 0.88
            note = "tighten_sl_channel_uncertain_long"
    elif su == "SELL":
        if dn >= 58.0:
            tp_pct *= 1.12
            sl_pct *= 0.92
            trail_usd *= 1.08
            note = "align_short_channel_down"
        elif dn < 45.0:
            sl_pct *= 0.88
            note = "tighten_sl_channel_uncertain_short"
    tp_pct = max(0.12, min(2.5, tp_pct))
    sl_pct = max(0.12, min(0.85, sl_pct))
    trail_usd = max(0.0, float(trail_usd))
    meta["tp_pct_adj"] = round(tp_pct, 6)
    meta["sl_pct_adj"] = round(sl_pct, 6)
    meta["trail_usd_adj"] = round(trail_usd, 4)
    if note:
        meta["note"] = note
    return tp_pct, sl_pct, trail_usd, meta


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _fmt_price(x: float) -> str:
    if x >= 1000:
        return f"{x:.2f}"
    if x >= 1:
        return f"{x:.4f}"
    return f"{x:.6f}"


def _pick_open_position(rows: list[Any]) -> dict[str, Any] | None:
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            sz = abs(float(r.get("size") or 0.0))
        except (TypeError, ValueError):
            continue
        if sz >= 1e-12:
            return r
    return None


def consensus_mid_and_close(pred: dict[str, Any]) -> tuple[float, float]:
    """Return (mid_next_mean, current_close) for TP/SL anchoring."""
    close = 0.0
    try:
        close = float(pred.get("current_close") or 0.0)
    except (TypeError, ValueError):
        pass
    pr = pred.get("predictions") if isinstance(pred.get("predictions"), dict) else {}
    rf = pr.get("random_forest") if isinstance(pr.get("random_forest"), dict) else {}
    xg = pr.get("xgboost") if isinstance(pr.get("xgboost"), dict) else {}
    try:
        rf_m = float(rf.get("next_mean") or 0.0)
    except (TypeError, ValueError):
        rf_m = 0.0
    try:
        xg_m = float(xg.get("next_mean") or 0.0)
    except (TypeError, ValueError):
        xg_m = 0.0
    if rf_m > 0 and xg_m > 0:
        mid = (rf_m + xg_m) / 2.0
    elif rf_m > 0:
        mid = rf_m
    elif xg_m > 0:
        mid = xg_m
    else:
        mid = close
    return mid, close


def compute_tpsl_strings(
    *,
    side: str,
    avg: float,
    mid: float,
    mark: float,
    tp_pct: float,
    sl_pct: float,
    trail_usd: float,
    trail_frac: float,
) -> dict[str, Any]:
    """
    Build Bybit price strings for Full position TP/SL + trailing distance.

    Long: TP toward ``mid`` when ``mid > avg``; else minimal TP above entry.
    Short: TP toward ``mid`` when ``mid < avg``; else minimal TP below entry.

    Bybit v5: for **Buy**, TP must be **above** ``mark``; for **Sell**, TP must be **below** ``mark``
    (``base_price`` in API errors). We clamp to satisfy that.
    """
    su = (side or "").strip().upper()
    tp_pct_f = max(0.01, float(tp_pct))
    sl_pct_f = max(0.01, float(sl_pct))
    mk = float(mark) if mark and mark > 0 else 0.0
    # ~1 bp cushion vs mark (tick-size rounding handled by string formatting)
    eps = 1e-4

    if su == "BUY":
        if mid > avg:
            tp = mid
            tp_note = "tp=consensus_mid_above_avg"
        else:
            tp = avg * (1.0 + tp_pct_f / 100.0)
            tp_note = "tp=fallback_pct_long"
        sl = avg * (1.0 - sl_pct_f / 100.0)
        if mk > 0 and tp <= mk:
            tp = mk * (1.0 + eps)
            tp_note += "|clamped_gt_mark"
    else:
        if mid < avg:
            tp = mid
            tp_note = "tp=consensus_mid_below_avg"
        else:
            tp = avg * (1.0 - tp_pct_f / 100.0)
            tp_note = "tp=fallback_pct_short"
        sl = avg * (1.0 + sl_pct_f / 100.0)
        if mk > 0 and tp >= mk:
            tp = mk * (1.0 - eps)
            tp_note += "|clamped_lt_mark"

    dist = abs(mid - avg) if mid > 0 and avg > 0 else 0.0
    trail = max(0.0, float(trail_usd) + trail_frac * dist)
    trail_s = f"{trail:.2f}" if trail > 0 else ""

    return {
        "take_profit": _fmt_price(tp),
        "stop_loss": _fmt_price(sl),
        "trailing_stop": trail_s,
        "tp_note": tp_note,
        "mid_next_mean": mid,
        "avg_entry": avg,
        "mark_price": mk if mk > 0 else None,
    }


def apply_btc_future_tpsl(*, dry_run: bool = False) -> dict[str, Any]:
    """
    If enabled and demo keys + open position + prediction file: POST trading-stop.

    Returns a dict with ``ok``, ``skipped`` (reason or None), ``detail``, ``bybit`` (last response).
    """
    out: dict[str, Any] = {
        "ok": False,
        "skipped": None,
        "detail": {},
        "bybit": None,
    }
    if not _env_truthy("SYGNIF_SWARM_BTC_FUTURE_AUTO_TPSL", default=False):
        out["skipped"] = "SYGNIF_SWARM_BTC_FUTURE_AUTO_TPSL_off"
        return out

    has_demo = bool(
        os.environ.get("BYBIT_DEMO_API_KEY", "").strip()
        and os.environ.get("BYBIT_DEMO_API_SECRET", "").strip()
    )
    if not has_demo:
        out["skipped"] = "no_BYBIT_DEMO_keys"
        return out

    sym = os.environ.get("SYGNIF_SWARM_TPSL_SYMBOL", "BTCUSDT").strip().upper() or "BTCUSDT"
    pred_path = _prediction_dir() / "btc_prediction_output.json"
    pred = _read_json(pred_path)
    if not pred:
        out["skipped"] = "missing_btc_prediction_output.json"
        return out

    swarm_path = _prediction_dir() / "swarm_knowledge_output.json"
    swarm = _read_json(swarm_path)
    if swarm and _env_truthy("SYGNIF_SWARM_TPSL_SKIP_ON_SWARM_CONFLICT", default=True):
        if bool(swarm.get("swarm_conflict")):
            out["skipped"] = "swarm_conflict"
            return out

    td = _repo_root() / "trade_overseer"
    tds = str(td)
    if tds not in sys.path:
        sys.path.insert(0, tds)
    import bybit_linear_hedge as blh  # noqa: PLC0415

    try:
        resp = blh.position_list(sym)
    except RuntimeError as e:
        out["skipped"] = "credentials_error"
        out["detail"] = {"error": str(e)}
        return out

    if resp.get("retCode") != 0:
        out["skipped"] = "position_list_error"
        out["detail"] = {"retCode": resp.get("retCode"), "retMsg": resp.get("retMsg")}
        return out

    rows = (resp.get("result") or {}).get("list") or []
    pos = _pick_open_position(rows)
    if not pos:
        out["skipped"] = "flat"
        out["detail"] = {"symbol": sym}
        return out

    side = str(pos.get("side") or "")
    try:
        avg = float(pos.get("avgPrice") or 0.0)
    except (TypeError, ValueError):
        avg = 0.0
    if avg <= 0:
        out["skipped"] = "invalid_avg_price"
        return out

    try:
        mark = float(pos.get("markPrice") or 0.0)
    except (TypeError, ValueError):
        mark = 0.0
    if mark <= 0:
        mark = avg

    try:
        pidx = int(pos.get("positionIdx") or 0)
    except (TypeError, ValueError):
        pidx = 0

    mid, _close = consensus_mid_and_close(pred)
    b_tp, b_sl, b_tr, b_tf = base_tpsl_from_profile()
    tp_pct = _env_float("SYGNIF_SWARM_TPSL_TP_PCT", b_tp)
    sl_pct = _env_float("SYGNIF_SWARM_TPSL_SL_PCT", b_sl)
    trail_usd = _env_float("SYGNIF_SWARM_TPSL_TRAIL_USD", b_tr)
    trail_frac = _env_float("SYGNIF_SWARM_TPSL_TRAIL_FRAC", b_tf)
    tp_pct, sl_pct, trail_usd, ch_meta = channel_adjust_tpsl(side, tp_pct, sl_pct, trail_usd)

    comp = compute_tpsl_strings(
        side=side,
        avg=avg,
        mid=mid,
        mark=mark,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        trail_usd=trail_usd,
        trail_frac=trail_frac,
    )
    tp_s = comp["take_profit"]
    sl_s = comp["stop_loss"]
    trail_s = comp["trailing_stop"]

    out["detail"] = {
        "symbol": sym,
        "side": side,
        "positionIdx": pidx,
        "take_profit": tp_s,
        "stop_loss": sl_s,
        "trailing_stop": trail_s or None,
        "tp_note": comp.get("tp_note"),
        "mid_next_mean": comp.get("mid_next_mean"),
        "avg_entry": comp.get("avg_entry"),
        "mark_price": comp.get("mark_price"),
        "tpsl_profile": (os.environ.get("SYGNIF_SWARM_TPSL_PROFILE") or "default").strip() or "default",
        "channel_tpsl": ch_meta,
    }

    if dry_run:
        out["ok"] = True
        out["skipped"] = "dry_run"
        return out

    kwargs: dict[str, Any] = {
        "position_idx": pidx,
        "take_profit": tp_s,
        "stop_loss": sl_s,
    }
    if trail_s:
        kwargs["trailing_stop"] = trail_s

    api_r = blh.set_trading_stop_linear(sym, **kwargs)
    out["bybit"] = api_r
    out["ok"] = api_r.get("retCode") == 0
    if not out["ok"]:
        out["skipped"] = "bybit_error"
    return out


def _write_last(repo: Path, payload: dict[str, Any]) -> None:
    dest = _prediction_dir() / "swarm_btc_future_tpsl_last.json"
    try:
        dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Set demo linear TP/SL from btc_prediction_output.json (swarm sync helper)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Compute only; do not POST")
    args = ap.parse_args()

    load_repo_env()
    repo = _repo_root()
    result = apply_btc_future_tpsl(dry_run=args.dry_run)
    result["schema_version"] = 1
    _write_last(repo, result)
    print(json.dumps(result, indent=2))
    br = result.get("bybit")
    if isinstance(br, dict) and br.get("retCode") not in (0, None):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
