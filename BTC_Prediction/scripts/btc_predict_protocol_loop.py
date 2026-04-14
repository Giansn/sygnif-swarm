#!/usr/bin/env python3
"""
**Circular predict protocol:** repeat **live 5m fit → target side → reconcile venue** on a timer.

Delegates **entries and exits** to the same signal as ``btc_predict_asap_order`` (``decide_side`` from
``btc_asap_predict_core``):

- **Flat** + target **long/short** → market **open** (set leverage, then Buy/Sell).
- **Size:** ``--manual-qty`` (BTC) **or** ``--manual-notional-usdt`` (USDT notional ≈ qty×last close from the fit).
- **High leverage:** ``--manual-leverage N`` uses cap ``BYBIT_DEMO_MANUAL_LEVERAGE_MAX`` (default **100**, max 125), not the auto band max (``BYBIT_DEMO_ORDER_MAX_LEVERAGE``).
- **Long** + target **not long** (short or no-edge) → **Sell** ``reduceOnly`` full size.
- **Short** + target **not short** (long or no-edge) → **Buy** ``reduceOnly`` full size.
- **Flip** (e.g. long → short): **close** then **open** opposite in the same iteration (brief pause after
  close for venue consistency).

Uses **Bybit demo** REST (``trade_overseer/bybit_linear_hedge.py``), not Nautilus OMS — same family as
the ASAP script, optimised for **closed-loop** automation.

**Run**
- Dry-run (predict + planned actions only): ``python3 scripts/btc_predict_protocol_loop.py``
- Live: ``SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES`` and ``--execute``
- Runs **until SIGINT/SIGTERM** when ``PREDICT_LOOP_MAX_ITERATIONS=0`` (default): one continuous circular
  protocol with no mandatory pause between cycles unless you set a positive interval.

**Env**
- ``SYGNIF_SWARM_GATE_LOOP`` — when ``1``/``true`` with ``--execute``, run ``compute_swarm()`` +
  ``write_fused_sidecar`` + ``swarm_fusion_allows`` each iteration before **new** entries; flips/exits still
  follow ``decide_side``. Set ``SYGNIF_SWARM_BTC_FUTURE=1`` (defaulted when gate is on). See
  ``scripts/swarm_auto_predict_protocol_loop.py``.
- ``SYGNIF_SWARM_TP_USDT_TARGET`` — optional (e.g. ``50``): after a successful **open**, set a take-profit
  on the linear leg so that **approx.** ``qty * |TP - entry| ≈`` this USDT (Bybit demo REST).
- ``SYGNIF_SWARM_AUTO_TRADING`` — marker env set by the auto launcher (for operators / dashboards only).
- ``SYGNIF_LETSCRASH_NOTIONAL_CAP`` (default **on** in ``swarm_auto``) — clip ``--manual-notional-usdt`` to
  ``letscrash/btc_strategy_0_1_rule_registry.json`` → ``rule_proof_bucket.notional_cap_usdt``. Set ``0`` to disable.
- ``PREDICT_LOOP_REFRESH_ALIGNED_EVERY_N`` — see above; ``0`` disables aligned refresh.
- ``SYGNIF_PREDICT_PROTOCOL_TEST_TAG_ORDER`` — ``1``/``true``: same as CLI ``--test-tag-order`` (with ``--execute`` + ACK).
- ``PREDICT_LOOP_INTERVAL_SEC`` (default **0**) — extra sleep after each iteration before the next predict.
  **0** = seamless back-to-back loop (no artificial gap; only predict + venue time). Set e.g. **300** to
  pace on 5m bars or reduce API/CPU load.
- ``PREDICT_LOOP_POST_CLOSE_SLEEP_SEC`` (default **0.75**) — pause after a reduce-only close before open.
- ``PREDICT_LOOP_MAX_ITERATIONS`` — **0** = run until SIGINT/SIGTERM.
- ``PREDICT_LOOP_ERROR_SLEEP_SEC`` (default **2**) — when ``interval`` is **0**, sleep this many seconds
  only after a thrown exception (avoids a tight spin on persistent failures). Set **0** to retry immediately.
- **Resource guard (letscrash):** ``letscrash/btc_strategy_0_1_rule_registry.json`` → ``tuning.predict_loop_resource``
  (``enabled``, ``mem_available_min_mb``, ``loadavg_max``, ``cooldown_sec``). When enabled, skips ``run_live_fit``
  under low **MemAvailable** or high **loadavg** and logs ``SYGNIF_LOOP_RESOURCE_HOLD``. Env overrides:
  ``SYGNIF_PREDICT_RESOURCE_GUARD``, ``SYGNIF_RESOURCE_MEM_MIN_MB``, ``SYGNIF_RESOURCE_LOAD_MAX``,
  ``SYGNIF_RESOURCE_COOLDOWN_SEC``.
- ``PREDICT_LOOP_HOLD_ON_NO_EDGE`` (default **1**) — when truthy, **do not** flatten on a **no-edge**
  signal (``decide_side`` → ``None``); only **exit on an opposite** long/short target (reduces chop).
  Set to ``0`` or use ``--exit-on-no-edge`` to restore flatten-every-cycle on no-edge.
- ``PREDICT_LOOP_REFRESH_ALIGNED_EVERY_N`` (default **1**) — every **N** iterations, if the venue
  position **already matches** the model target, **close + re-open** the same side so orders still
  flow when signals stay aligned (set **0** or ``--refresh-aligned-every 0`` to only trade on flips /
  flat entries).

**One prediction fit:** wall time is logged as ``predict_ms`` on each ``SYGNIF_LOOP_PREDICT`` line — typically
**~2–8 s** with default ASAP kline/trees (network + sklearn/xgb on the last row); raise trees/kline for
accuracy at the cost of latency.

Requires **Nautilus venv** (sklearn/xgboost) and ``PYTHONPATH`` to ``prediction_agent``; ``BYBIT_DEMO_*``
for live mode.

**Tag verification (dashboard PREDICT):** one-shot minimal **Buy** open + reduce-only close (account must be
**flat** first): ``SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES`` ``python3 scripts/btc_predict_protocol_loop.py
--execute --test-tag-order`` or set env ``SYGNIF_PREDICT_PROTOCOL_TEST_TAG_ORDER=1`` with ``--execute``.
Optional: ``SYGNIF_TEST_TAG_ORDER_QTY`` (default ``0.001``), ``SYGNIF_TEST_TAG_ORDER_SLEEP_SEC`` (default ``1``),
``SYGNIF_TEST_TAG_ORDER_OPEN_WAIT_SEC`` (default **8**) — poll ``position/list`` after open until size appears.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PA = _REPO / "prediction_agent"
_DATA = _REPO / "finance_agent" / "btc_specialist" / "data"
sys.path.insert(0, str(_PA))
sys.path.insert(0, str(_REPO / "finance_agent"))
sys.path.insert(0, str(_REPO / "trade_overseer"))

import bybit_linear_hedge as blh  # noqa: E402
import btc_iface_trade_tags as iface_tags  # noqa: E402
from btc_asap_predict_core import decide_side  # noqa: E402
from btc_asap_predict_core import env_float  # noqa: E402
from btc_asap_predict_core import env_int  # noqa: E402
from btc_asap_predict_core import leverage_from_move_pct  # noqa: E402
from btc_asap_predict_core import logreg_confidence  # noqa: E402
from btc_asap_predict_core import move_pct_and_close  # noqa: E402
from btc_asap_predict_core import parse_linear_position  # noqa: E402
from btc_asap_predict_core import parse_usdt_available  # noqa: E402
from btc_asap_predict_core import qty_btc  # noqa: E402
from btc_asap_predict_core import run_live_fit  # noqa: E402

try:
    from letscrash_predict_loop_guard import (  # noqa: E402
        load_guard_config,
        resource_snapshot,
        should_skip_iteration,
    )
except ImportError:
    from finance_agent.letscrash_predict_loop_guard import (  # noqa: E402
        load_guard_config,
        resource_snapshot,
        should_skip_iteration,
    )

_STOP = False


def _letscrash_notional_cap_enabled() -> bool:
    raw = (os.environ.get("SYGNIF_LETSCRASH_NOTIONAL_CAP") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _letscrash_notional_cap_usdt() -> float | None:
    try:
        p = _REPO / "letscrash" / "btc_strategy_0_1_rule_registry.json"
        raw = json.loads(p.read_text(encoding="utf-8"))
        cap = (raw.get("rule_proof_bucket") or {}).get("notional_cap_usdt")
        if cap is None:
            return None
        return float(cap)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _clip_manual_notional_letscrash(mn: float) -> float:
    if not _letscrash_notional_cap_enabled():
        return float(mn)
    cap = _letscrash_notional_cap_usdt()
    if cap is not None and cap > 0:
        return min(float(mn), cap)
    return float(mn)


def _on_signal(_sig, _frame) -> None:
    global _STOP
    _STOP = True


def _hold_on_no_edge_from_env() -> bool:
    v = os.environ.get("PREDICT_LOOP_HOLD_ON_NO_EDGE", "1").strip().lower()
    return v not in ("0", "false", "no", "off", "")


def _default_refresh_aligned_every() -> int:
    raw = (os.environ.get("PREDICT_LOOP_REFRESH_ALIGNED_EVERY_N", "1") or "1").strip().lower()
    if raw in ("0", "off", "false", "no", ""):
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def need_close_position(
    pos_side: str | None,
    target: str | None,
    *,
    hold_on_no_edge: bool,
) -> bool:
    """
    Whether to reduce-only close an open position before (optionally) opening the target side.

    - Opposite signal always closes (long+short or short+long).
    - If ``hold_on_no_edge``: **no-edge** (``target is None``) does **not** close — hold through chop.
    - If not ``hold_on_no_edge``: no-edge closes (legacy aggressive flatten).
    """
    if pos_side is None:
        return False
    if target is None:
        return not hold_on_no_edge
    if pos_side == "long" and target == "short":
        return True
    if pos_side == "short" and target == "long":
        return True
    return False


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        o = json.loads(path.read_text(encoding="utf-8"))
        return o if isinstance(o, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _close_qty_str(raw_api: str, abs_float: float) -> str:
    s = (raw_api or "").strip()
    if s:
        return s
    step = 0.001
    q = math.floor(abs_float / step) * step
    return f"{q:.6f}".rstrip("0").rstrip(".") or str(step)


def _env_truthy_swarm(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _avg_entry_from_position_list(pr: dict, symbol: str) -> float | None:
    """Dominant linear leg ``avgPrice`` for TP math (USDT linear)."""
    sym = (symbol or "").replace("/", "").upper().strip() or "BTCUSDT"
    if pr.get("retCode") != 0:
        return None
    best: float | None = None
    best_sz = 0.0
    for row in (pr.get("result") or {}).get("list") or []:
        if str(row.get("symbol", "")).upper() != sym:
            continue
        try:
            sz = float(str(row.get("size") or "0").strip() or 0)
        except (TypeError, ValueError):
            continue
        if abs(sz) <= 1e-9:
            continue
        if abs(sz) > best_sz:
            best_sz = abs(sz)
            try:
                best = float(str(row.get("avgPrice") or 0).strip() or 0)
            except (TypeError, ValueError):
                best = None
    return best if best and best > 0 else None


def _iteration(
    *,
    args: argparse.Namespace,
    training: dict | None,
    execute: bool,
    iter_count: int,
    hold_on_no_edge: bool,
    refresh_aligned_every: int,
) -> int:
    """Return 0 ok, nonzero severe error (caller may continue loop)."""
    _rg = load_guard_config(_REPO)
    _skip, _rg_reason, _rg_sleep = should_skip_iteration(_rg)
    if _skip:
        _snap = resource_snapshot()
        print(
            "SYGNIF_LOOP_RESOURCE_HOLD "
            + json.dumps(
                {"iter": iter_count, "reason": _rg_reason, **_snap},
                separators=(",", ":"),
            ),
            flush=True,
        )
        time.sleep(_rg_sleep)
        return 0

    wj = str(args.write_json).strip() if not args.no_write_json else ""
    wpath = wj or None
    allow_buy, enhanced, out, pred_ms = run_live_fit(
        symbol=args.symbol,
        kline_limit=args.kline_limit,
        window=args.window,
        data_dir=str(args.data_dir),
        rf_trees=args.rf_trees,
        xgb_estimators=args.xgb_estimators,
        write_json_path=wpath,
    )
    target, why = decide_side(out, training)
    entry_blocked = False
    swarm_gate_ok: bool | None = None
    swarm_reason = ""
    if execute and _env_truthy_swarm("SYGNIF_SWARM_GATE_LOOP"):
        os.environ.setdefault("SYGNIF_SWARM_BTC_FUTURE", "1")
        try:
            from swarm_knowledge import compute_swarm  # noqa: PLC0415
        except ImportError:
            from finance_agent.swarm_knowledge import compute_swarm  # noqa: PLC0415
        from nautilus_protocol_fusion import write_fused_sidecar  # noqa: PLC0415
        try:
            from swarm_order_gate import swarm_fusion_allows  # noqa: PLC0415
        except ImportError:
            from finance_agent.swarm_order_gate import swarm_fusion_allows  # noqa: PLC0415
        swarm = compute_swarm()
        fusion_doc = write_fused_sidecar(_REPO)
        swarm_gate_ok, swarm_reason = swarm_fusion_allows(
            target=target,
            swarm=swarm,
            fusion_doc=fusion_doc,
        )
        if not swarm_gate_ok and target in ("long", "short"):
            entry_blocked = True
        _sources = swarm.get("sources") if isinstance(swarm.get("sources"), dict) else {}
        _bf = _sources.get("bf") if isinstance(_sources.get("bf"), dict) else {}
        _btc_fut = swarm.get("btc_future") if isinstance(swarm.get("btc_future"), dict) else {}
        _bf_line: dict[str, object] = {"iter": iter_count, "swarm_gate_ok": swarm_gate_ok}
        if _bf:
            _bf_line["bf_vote"] = _bf.get("vote")
            _bf_line["bf_detail"] = _bf.get("detail")
        if _btc_fut:
            _bf_line["btc_future_enabled"] = _btc_fut.get("enabled")
            _bf_line["btc_future_ok"] = _btc_fut.get("ok")
        print(
            f"SYGNIF_LOOP_BTC_FUTURE {json.dumps(_bf_line, separators=(',', ':'), default=str)}",
            flush=True,
        )

    mn_usdt = getattr(args, "manual_notional_usdt", None)
    if mn_usdt is not None:
        try:
            mn0 = float(mn_usdt)
            if mn0 > 0:
                mn1 = _clip_manual_notional_letscrash(mn0)
                if mn1 != mn0:
                    print(
                        f"SYGNIF_LOOP_LETSCRASH notional_usdt {mn0} -> {mn1} "
                        f"(rule_proof_bucket.notional_cap_usdt)",
                        flush=True,
                    )
                    args.manual_notional_usdt = mn1
        except (TypeError, ValueError):
            pass

    open_target = None if entry_blocked else target
    move_pct, close = move_pct_and_close(out)
    lev, t_move = leverage_from_move_pct(move_pct)
    if args.manual_leverage is not None:
        # Manual override: cap by BYBIT_DEMO_MANUAL_LEVERAGE_MAX (default 100), not auto band (often 5–25).
        lo = env_int("BYBIT_DEMO_ORDER_MIN_LEVERAGE", 1, lo=1, hi=125)
        hi_manual = env_int("BYBIT_DEMO_MANUAL_LEVERAGE_MAX", 100, lo=1, hi=125)
        lev = max(lo, min(hi_manual, int(round(float(args.manual_leverage)))))
    lconf = logreg_confidence(out)

    mn_arg = getattr(args, "manual_notional_usdt", None)
    planned_qty_from_notional: float | None = None
    if mn_arg is not None and float(mn_arg) > 0 and close > 0:
        step = 0.001
        planned_qty_from_notional = math.floor((float(mn_arg) / close) / step) * step

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = {
        "ts_utc": ts,
        "iter": iter_count,
        "predict_ms": round(pred_ms, 1),
        "allow_buy": allow_buy,
        "enhanced": enhanced,
        "target_side": target,
        "target_reason": why,
        "leverage_would": lev,
        "move_pct": round(move_pct, 6),
        "hold_on_no_edge": hold_on_no_edge,
    }
    if swarm_gate_ok is not None:
        line["swarm_gate_ok"] = swarm_gate_ok
        line["swarm_reason"] = swarm_reason
        line["entry_blocked"] = entry_blocked
        line["open_target_side"] = open_target
    if mn_arg is not None:
        line["manual_notional_usdt"] = float(mn_arg)
    if planned_qty_from_notional is not None:
        line["planned_qty_from_notional"] = planned_qty_from_notional
    print(f"SYGNIF_LOOP_PREDICT {json.dumps(line, separators=(',', ':'))}", flush=True)
    if entry_blocked:
        print(f"SYGNIF_LOOP_SWARM_BLOCK model_target={target!r} reason={swarm_reason!r}", flush=True)

    if (
        os.environ.get("SYGNIF_PROTOCOL_FUSION_TICK", "").strip().lower()
        in ("1", "true", "yes", "on")
    ):
        try:
            from nautilus_protocol_fusion import record_protocol_tick  # noqa: PLC0415

            record_protocol_tick(_REPO, {**line, "execute": execute})
        except Exception as exc:  # noqa: BLE001
            print(f"SYGNIF_LOOP_WARN fusion_tick: {exc}", flush=True)

    if not execute:
        try:
            pr = blh.position_list(args.symbol)
        except RuntimeError:
            pos_side, pos_sz, pos_raw = None, 0.0, ""
        else:
            pos_side, pos_sz, pos_raw = parse_linear_position(pr, args.symbol)
        nc = need_close_position(pos_side, target, hold_on_no_edge=hold_on_no_edge)
        extra_sz = ""
        if planned_qty_from_notional is not None:
            extra_sz = f" planned_qty≈{planned_qty_from_notional} (from notional)"
        print(
            f"SYGNIF_LOOP_DRY position={pos_side!r} sz={pos_sz} target={target!r} "
            f"would_close={nc} hold_on_no_edge={hold_on_no_edge}{extra_sz} "
            f"(set SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES --execute for venue)",
            flush=True,
        )
        return 0

    # --- live reconcile ---
    try:
        pr = blh.position_list(args.symbol)
    except RuntimeError as exc:
        print(f"SYGNIF_LOOP_ERR position_list: {exc}", flush=True)
        return 3

    pos_side, pos_sz, pos_raw = parse_linear_position(pr, args.symbol)
    close_sleep = max(0.0, env_float("PREDICT_LOOP_POST_CLOSE_SLEEP_SEC", 0.75))
    pidx = args.position_idx
    sym_u = (args.symbol or "").replace("/", "").upper().strip() or "BTCUSDT"

    def _exit_kind_for_close() -> str:
        if target is None:
            return "no_edge_flat"
        if pos_side == "long" and target == "short":
            return "opposite_signal"
        if pos_side == "short" and target == "long":
            return "opposite_signal"
        return "reconcile"

    def _do_close(exit_kind: str, pos_meta: dict) -> bool:
        nonlocal pos_side, pos_sz, pos_raw
        if pos_side is None or pos_sz <= 0:
            return True
        qclose = _close_qty_str(pos_raw, pos_sz)
        if pos_side == "long":
            side_venue = "Sell"
        else:
            side_venue = "Buy"
        link_c = iface_tags.order_link_close(iter_count)
        mo = blh.create_market_order(
            args.symbol,
            side_venue,
            qclose,
            pidx,
            reduce_only=True,
            order_link_id=link_c,
        )
        print(f"SYGNIF_LOOP_CLOSE {json.dumps(mo, default=str)}", flush=True)
        if mo.get("retCode") != 0:
            return False
        c_oid = iface_tags.order_id_from_create_response(mo)
        if c_oid:
            iface_tags.append_journal(
                {
                    "symbol": sym_u,
                    "action": "close",
                    "order_id": c_oid,
                    "order_link_id": link_c,
                    "open_tag": (pos_meta.get("open_tag") or "predict_loop"),
                    "close_tag": "predict_loop_close",
                    "exit_kind": exit_kind,
                    "open_order_id": pos_meta.get("open_order_id") or "",
                    "open_detail": (pos_meta.get("open_detail") or "")[:2000],
                }
            )
        iface_tags.clear_position_symbol(sym_u)
        time.sleep(close_sleep)
        pr2 = blh.position_list(args.symbol)
        pos_side, pos_sz, pos_raw = parse_linear_position(pr2, args.symbol)
        return True

    # Exit / flip: opposite target, or no-edge when not holding through chop
    need_flat = need_close_position(pos_side, target, hold_on_no_edge=hold_on_no_edge)
    if pos_side is not None and need_flat:
        pos_meta = iface_tags.load_position_meta().get(sym_u, {})
        if not _do_close(_exit_kind_for_close(), pos_meta):
            return 4
        # re-fetch after close
        pr = blh.position_list(args.symbol)
        pos_side, pos_sz, pos_raw = parse_linear_position(pr, args.symbol)

    # When model and venue already agree, optionally close+reopen so orders still run (demo / iface tags).
    ren = max(0, int(refresh_aligned_every))
    if (
        ren > 0
        and pos_side is not None
        and open_target == pos_side
        and open_target in ("long", "short")
        and pos_sz > 1e-9
        and iter_count % ren == 0
    ):
        pos_meta = iface_tags.load_position_meta().get(sym_u, {})
        print(
            f"SYGNIF_LOOP_REFRESH aligned iter={iter_count} every={ren} side={pos_side!r} "
            "— close then re-enter",
            flush=True,
        )
        if not _do_close("aligned_refresh", pos_meta):
            return 4
        pr = blh.position_list(args.symbol)
        pos_side, pos_sz, pos_raw = parse_linear_position(pr, args.symbol)

    # Entry: flat and have target (Swarm may block **entry** only; exits/flips still use ``target`` above)
    if open_target in ("long", "short") and (pos_side is None or pos_sz < 1e-9):
        try:
            w = blh.wallet_balance_unified_coin("USDT")
            free = parse_usdt_available(w)
        except RuntimeError as exc:
            print(f"SYGNIF_LOOP_ERR wallet: {exc}", flush=True)
            return 5
        if free is None or free <= 0:
            print("SYGNIF_LOOP_ERR no free USDT", flush=True)
            return 5
        mn = getattr(args, "manual_notional_usdt", None)
        if mn is not None and float(mn) > 0:
            if close <= 0:
                print(f"SYGNIF_LOOP_ERR manual-notional needs positive close, got {close}", flush=True)
                return 6
            raw_qty = float(mn) / close
            step = 0.001
            q = math.floor(raw_qty / step) * step
            min_q = max(1e-9, env_float("BYBIT_DEMO_ORDER_MIN_QTY", 0.001))
            if q + 1e-12 < min_q:
                print(
                    f"SYGNIF_LOOP_ERR notional→qty below min_qty {min_q} (got {q})",
                    flush=True,
                )
                return 6
            qty_s = f"{q:.6f}".rstrip("0").rstrip(".") or str(min_q)
        elif args.manual_qty is not None and str(args.manual_qty).strip():
            qty_s = str(args.manual_qty).strip()
        else:
            qty_s, _eff = qty_btc(free_usdt=free, close=close, t_move=t_move, logreg_conf=lconf)
        if not qty_s:
            print("SYGNIF_LOOP_ERR qty below min", flush=True)
            return 6
        lr = blh.set_linear_leverage(args.symbol, str(lev))
        print(f"SYGNIF_LOOP_LEV {json.dumps(lr, default=str)}", flush=True)
        lrc = lr.get("retCode")
        # Bybit: 110043 = leverage already at requested value — safe to continue
        if lrc not in (0, 110043):
            return 7
        order_side = "Buy" if open_target == "long" else "Sell"
        link_o = iface_tags.order_link_open(iter_count, open_target == "long")
        mo = blh.create_market_order(
            args.symbol,
            order_side,
            qty_s,
            pidx,
            reduce_only=False,
            order_link_id=link_o,
        )
        print(f"SYGNIF_LOOP_OPEN {json.dumps(mo, default=str)}", flush=True)
        if mo.get("retCode") != 0:
            return 8
        o_oid = iface_tags.order_id_from_create_response(mo)
        if o_oid:
            detail = (why or "")[:2000]
            iface_tags.append_journal(
                {
                    "symbol": sym_u,
                    "action": "open",
                    "order_id": o_oid,
                    "order_link_id": link_o,
                    "open_tag": "predict_loop",
                    "side": order_side,
                    "open_detail": detail,
                }
            )
            iface_tags.set_position_open(
                sym_u,
                open_tag="predict_loop",
                open_detail=detail,
                open_order_id=o_oid,
                open_order_link_id=link_o,
                pos_side=open_target or "",
            )
            tp_tgt = env_float("SYGNIF_SWARM_TP_USDT_TARGET", 0.0)
            if tp_tgt > 0:
                try:
                    pr_tp = blh.position_list(args.symbol)
                    avg_px = _avg_entry_from_position_list(pr_tp, args.symbol)
                    qf = float(qty_s)
                    if avg_px and qf > 1e-12:
                        delta = tp_tgt / qf
                        if open_target == "long":
                            tp_px = avg_px + delta
                        else:
                            tp_px = avg_px - delta
                        tp_s = f"{tp_px:.2f}"
                        tsr = blh.set_trading_stop_linear(
                            args.symbol,
                            position_idx=pidx,
                            take_profit=tp_s,
                            tp_trigger_by="MarkPrice",
                        )
                        print(f"SYGNIF_LOOP_TP {json.dumps(tsr, default=str)} target_usdt={tp_tgt}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"SYGNIF_LOOP_WARN tp_target: {exc}", flush=True)

    elif pos_side == target and target is not None:
        print(f"SYGNIF_LOOP_HOLD {pos_side!r} aligned with target", flush=True)
    elif pos_side is not None and target is None and hold_on_no_edge:
        print(
            f"SYGNIF_LOOP_HOLD {pos_side!r} no-edge signal — keeping position (hold_on_no_edge)",
            flush=True,
        )

    return 0


def run_test_tag_order(args: argparse.Namespace) -> int:
    """
    Place minimal linear **Buy** (open / net-long), then **reduce-only** close on the **actual** venue leg
    (Sell if long, Buy if short) with ``predict_loop`` journal rows for BTC Interface **PREDICT** tags.
    """
    sym_u = (args.symbol or "").replace("/", "").upper().strip() or "BTCUSDT"
    pidx = args.position_idx
    qty_s = (os.environ.get("SYGNIF_TEST_TAG_ORDER_QTY", "0.001") or "0.001").strip()
    detail = (
        os.environ.get("SYGNIF_TEST_TAG_ORDER_DETAIL", "").strip()
        or "SYGNIF_TEST_TAG_ORDER verify predict_loop → dashboard PREDICT badge"
    )[:2000]
    sleep_mid = max(0.25, float(os.environ.get("SYGNIF_TEST_TAG_ORDER_SLEEP_SEC", "1") or 1))

    try:
        pr = blh.position_list(args.symbol)
    except RuntimeError as exc:
        print(f"SYGNIF_TEST_TAG_ERR position_list {exc}", flush=True)
        return 3

    pos_side, pos_sz, pos_raw = parse_linear_position(pr, args.symbol)
    if pos_sz and pos_sz > 1e-9:
        print(
            f"SYGNIF_TEST_TAG_ERR not flat (side={pos_side!r} sz={pos_sz}); flatten first",
            flush=True,
        )
        return 10

    lev = env_int("BYBIT_DEMO_ORDER_MIN_LEVERAGE", 5, lo=1, hi=125)
    lr = blh.set_linear_leverage(args.symbol, str(lev))
    print(f"SYGNIF_TEST_TAG_LEV {json.dumps(lr, default=str)}", flush=True)
    if lr.get("retCode") not in (0, 110043):
        return 7

    link_o = iface_tags.order_link_verify_open()
    mo = blh.create_market_order(
        args.symbol,
        "Buy",
        qty_s,
        pidx,
        reduce_only=False,
        order_link_id=link_o,
    )
    print(f"SYGNIF_TEST_TAG_OPEN {json.dumps(mo, default=str)}", flush=True)
    if mo.get("retCode") != 0:
        return 8
    o_oid = iface_tags.order_id_from_create_response(mo)
    if not o_oid:
        print("SYGNIF_TEST_TAG_ERR missing open orderId", flush=True)
        return 12
    iface_tags.append_journal(
        {
            "symbol": sym_u,
            "action": "open",
            "order_id": o_oid,
            "order_link_id": link_o,
            "open_tag": "predict_loop",
            "side": "Buy",
            "open_detail": detail,
        }
    )
    iface_tags.set_position_open(
        sym_u,
        open_tag="predict_loop",
        open_detail=detail,
        open_order_id=o_oid,
        open_order_link_id=link_o,
        pos_side="long",
    )

    open_wait = max(sleep_mid, float(os.environ.get("SYGNIF_TEST_TAG_ORDER_OPEN_WAIT_SEC", "8") or 8))
    deadline = time.time() + open_wait
    pos_side, pos_sz, pos_raw = None, 0.0, ""
    while time.time() < deadline:
        time.sleep(0.25)
        try:
            pr = blh.position_list(args.symbol)
        except RuntimeError as exc:
            print(f"SYGNIF_TEST_TAG_WARN position_list after open {exc}", flush=True)
            continue
        pos_side, pos_sz, pos_raw = parse_linear_position(pr, args.symbol)
        if pos_side is not None and pos_sz > 1e-9:
            break
    if pos_side is None or pos_sz < 1e-9:
        print("SYGNIF_TEST_TAG_ERR no position after open (increase SYGNIF_TEST_TAG_ORDER_OPEN_WAIT_SEC?)", flush=True)
        iface_tags.clear_position_symbol(sym_u)
        return 11

    if pos_side != "long":
        print(
            f"SYGNIF_TEST_TAG_WARN after Buy open, venue reports side={pos_side!r} (one-way reduce of prior short?); "
            "closing with matching reduce-only side",
            flush=True,
        )

    pos_meta = iface_tags.load_position_meta().get(sym_u, {})
    mo2: dict = {}
    close_link_used = ""
    for attempt in range(5):
        try:
            prc = blh.position_list(args.symbol)
        except RuntimeError as exc:
            print(f"SYGNIF_TEST_TAG_WARN pre-close position_list {exc}", flush=True)
            time.sleep(0.2)
            continue
        pos_side, pos_sz, pos_raw = parse_linear_position(prc, args.symbol)
        if pos_side is None or pos_sz < 1e-9:
            if attempt == 0:
                print(
                    "SYGNIF_TEST_TAG_WARN flat before close (external flatten?); open journal only",
                    flush=True,
                )
                iface_tags.clear_position_symbol(sym_u)
                return 0
            print(
                "SYGNIF_TEST_TAG_WARN flat during close retries; assuming external close",
                flush=True,
            )
            iface_tags.clear_position_symbol(sym_u)
            return 0
        qclose = _close_qty_str(pos_raw, pos_sz)
        close_venue = "Sell" if pos_side == "long" else "Buy"
        close_link_used = iface_tags.order_link_verify_close()
        mo2 = blh.create_market_order(
            args.symbol,
            close_venue,
            qclose,
            pidx,
            reduce_only=True,
            order_link_id=close_link_used,
        )
        print(f"SYGNIF_TEST_TAG_CLOSE {json.dumps(mo2, default=str)}", flush=True)
        if mo2.get("retCode") == 0:
            break
        if mo2.get("retCode") == 110017:
            time.sleep(0.25)
            continue
        return 4
    else:
        return 4
    c_oid = iface_tags.order_id_from_create_response(mo2)
    if c_oid:
        iface_tags.append_journal(
            {
                "symbol": sym_u,
                "action": "close",
                "order_id": c_oid,
                "order_link_id": close_link_used,
                "open_tag": (pos_meta.get("open_tag") or "predict_loop"),
                "close_tag": "predict_loop_close",
                "exit_kind": "test_tag_verify",
                "open_order_id": pos_meta.get("open_order_id") or "",
                "open_detail": (pos_meta.get("open_detail") or detail)[:2000],
            }
        )
    iface_tags.clear_position_symbol(sym_u)

    close_sleep = max(0.0, env_float("PREDICT_LOOP_POST_CLOSE_SLEEP_SEC", 0.75))
    time.sleep(close_sleep)

    print(
        "SYGNIF_TEST_TAG_OK open+close journal written; check BTC Interface "
        f"(PREDICT tags; order_ids open={o_oid} close={c_oid or '?'})",
        flush=True,
    )
    return 0


def main() -> int:
    global _STOP
    ap = argparse.ArgumentParser(description="Predict protocol loop: auto entries and exits (Bybit demo)")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument(
        "--kline-limit",
        type=int,
        default=max(120, min(1000, int(os.environ.get("ASAP_KLINE_LIMIT", "320") or 320))),
    )
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--rf-trees", type=int, default=max(10, int(os.environ.get("ASAP_RF_TREES", "32") or 32)))
    ap.add_argument(
        "--xgb-estimators",
        type=int,
        default=max(20, int(os.environ.get("ASAP_XGB_N_ESTIMATORS", "60") or 60)),
    )
    ap.add_argument("--data-dir", type=Path, default=_DATA)
    ap.add_argument("--training-json", type=Path, default=_PA / "training_channel_output.json")
    ap.add_argument(
        "--write-json",
        default=str(_PA / "btc_prediction_output.json"),
        metavar="PATH",
    )
    ap.add_argument("--no-write-json", action="store_true")
    ap.add_argument(
        "--manual-qty",
        default=None,
        help="Fixed linear order qty in base coin (e.g. BTC for BTCUSDT). Mutually exclusive with --manual-notional-usdt.",
    )
    ap.add_argument(
        "--manual-notional-usdt",
        type=float,
        default=None,
        metavar="USDT",
        help="Target approximate USDT notional: qty ≈ USDT / last close from the live fit. Mutually exclusive with --manual-qty.",
    )
    ap.add_argument(
        "--manual-leverage",
        type=float,
        default=None,
        help="Override leverage; clamped 1..BYBIT_DEMO_MANUAL_LEVERAGE_MAX (default 100).",
    )
    ap.add_argument(
        "--position-idx",
        type=int,
        default=int(os.environ.get("BYBIT_DEMO_POSITION_IDX", "0") or 0),
    )
    ap.add_argument(
        "--interval-sec",
        type=float,
        default=float(os.environ.get("PREDICT_LOOP_INTERVAL_SEC", "0") or 0),
        help="Extra sleep after each iteration (default 0=seamless; env PREDICT_LOOP_INTERVAL_SEC)",
    )
    ap.add_argument(
        "--max-iterations",
        type=int,
        default=int(os.environ.get("PREDICT_LOOP_MAX_ITERATIONS", "0") or 0),
        help="0 = unlimited until signal",
    )
    ap.add_argument("--execute", action="store_true")
    ap.add_argument(
        "--exit-on-no-edge",
        action="store_true",
        help="Flatten when decide_side returns no-edge (disables hold-on-no-edge for this run)",
    )
    ap.add_argument(
        "--test-tag-order",
        action="store_true",
        help=(
            "One-shot: minimal Buy open + reduce-only Sell close on demo to verify iface tags "
            "(journal predict_loop; requires --execute + SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES; account flat)"
        ),
    )
    ap.add_argument(
        "--refresh-aligned-every",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Every N iterations, if position matches target, close+reopen same side (0=off). "
            "Default: env PREDICT_LOOP_REFRESH_ALIGNED_EVERY_N or 1."
        ),
    )
    args = ap.parse_args()
    mq = args.manual_qty is not None and str(args.manual_qty).strip() != ""
    mn = args.manual_notional_usdt is not None and float(args.manual_notional_usdt) > 0
    if mq and mn:
        ap.error("use either --manual-qty or --manual-notional-usdt, not both")
    if args.refresh_aligned_every is None:
        args.refresh_aligned_every = _default_refresh_aligned_every()
    else:
        args.refresh_aligned_every = max(0, int(args.refresh_aligned_every))

    if os.environ.get("SYGNIF_PREDICT_PROTOCOL_TEST_TAG_ORDER", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        args.test_tag_order = True

    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _on_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _on_signal)

    training = _load_json(args.training_json)
    execute = bool(args.execute)
    hold_on_no_edge = _hold_on_no_edge_from_env() and not bool(args.exit_on_no_edge)

    if args.test_tag_order:
        if not execute:
            print("Refusing --test-tag-order without --execute", file=sys.stderr)
            return 2
        if os.environ.get("SYGNIF_PREDICT_PROTOCOL_LOOP_ACK", "").strip().upper() != "YES":
            print(
                "Refusing --test-tag-order: set SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES",
                file=sys.stderr,
            )
            return 2
        return run_test_tag_order(args)

    if execute and os.environ.get("SYGNIF_PREDICT_PROTOCOL_LOOP_ACK", "").strip().upper() != "YES":
        print(
            "Refusing --execute: set SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES",
            file=sys.stderr,
        )
        return 2

    interval = max(0.0, float(args.interval_sec))
    max_iter = max(0, int(args.max_iterations))
    err_sleep = max(0.0, float(os.environ.get("PREDICT_LOOP_ERROR_SLEEP_SEC", "2") or 2))

    n = 0
    while not _STOP:
        n += 1
        had_exc = False
        try:
            rc = _iteration(
                args=args,
                training=training,
                execute=execute,
                iter_count=n,
                hold_on_no_edge=hold_on_no_edge,
                refresh_aligned_every=args.refresh_aligned_every,
            )
        except Exception as exc:
            print(f"SYGNIF_LOOP_EXC {exc!r}", flush=True)
            rc = 9
            had_exc = True
        if rc >= 7:
            print(f"SYGNIF_LOOP_WARN iteration rc={rc}", flush=True)

        if _STOP:
            break
        if max_iter > 0 and n >= max_iter:
            break

        if interval > 0 and not _STOP:
            t0 = time.monotonic()
            while not _STOP:
                elapsed = time.monotonic() - t0
                if elapsed >= interval:
                    break
                rem = interval - elapsed
                time.sleep(min(1.0, rem))
        elif had_exc and err_sleep > 0 and not _STOP:
            time.sleep(err_sleep)

    print("SYGNIF_LOOP_STOP", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
