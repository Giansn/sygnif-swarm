#!/usr/bin/env python3
"""
Fuse **Nautilus research sidecar** (``nautilus_strategy_signal.json``) + **BTC ML JSON**
(``btc_prediction_output.json``) + optional **btc_future** / **bf** (Bybit API **demo** linear position when
``SYGNIF_SWARM_BTC_FUTURE`` is truthy demo mode, or **mainnet** linear position when ``SYGNIF_SWARM_BTC_FUTURE=trade`` —
via ``finance_agent.swarm_knowledge``) + optional **predict-protocol
loop tick** + **swarm_keypoints** (annotations from ``swarm_knowledge_output.json`` when present)
into one **sidecar** for swarm / briefing / dashboards.

``fusion.vote_btc_future`` is the **bf** position vote (demo or trade mode); ``fusion.btc_future_direction``
is ``long`` / ``short`` / ``flat`` for quick alignment with swarm.orders.

- **Write path:** ``prediction_agent/swarm_nautilus_protocol_sidecar.json`` (override
  ``SYGNIF_NAUTILUS_FUSION_PATH``).
- **Sync:** ``python3 prediction_agent/nautilus_protocol_fusion.py sync``
- **Briefing:** ``SYGNIF_BRIEFING_INCLUDE_NAUTILUS_FUSION=1`` in ``ruleprediction_briefing`` (compact line).

Nautilus loop hook: set ``NAUTILUS_FUSION_SIDECAR_SYNC=1`` in ``nautilus_sidecar_strategy`` environment
so each sidecar refresh also refreshes this file (host layout with SYGNIF repo next to ``research/``).

Protocol loop hook: ``SYGNIF_PROTOCOL_FUSION_TICK=1`` → each iteration updates ``predict_protocol_loop`` in
the same JSON (no venue writes here).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2  # optional swarm_keypoints + fusion.btc_future_direction (same major)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def fused_sidecar_path(repo_root: Path | None = None) -> Path:
    raw = (os.environ.get("SYGNIF_NAUTILUS_FUSION_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser()
    base = repo_root or _repo_root()
    return base / "prediction_agent" / "swarm_nautilus_protocol_sidecar.json"


def _btc_data_dir(repo_root: Path) -> Path:
    raw = (os.environ.get("NAUTILUS_BTC_OHLCV_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return repo_root / "finance_agent" / "btc_specialist" / "data"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _vote_nautilus_bias(raw: dict[str, Any]) -> tuple[int, str]:
    b = raw.get("bias")
    if not isinstance(b, str):
        return 0, "?"
    bl = b.lower().strip()
    if bl == "long":
        return 1, "long"
    if bl == "short":
        return -1, "short"
    return 0, "neutral"


def _btc_future_fusion_vote(repo_root: Path) -> tuple[int, str, dict[str, Any]]:
    """
    Same **bf** vote as ``swarm_knowledge.compute_swarm`` when ``SYGNIF_SWARM_BTC_FUTURE`` is **demo** or **trade**.
    Read-only; no orders.
    """
    rs = str(repo_root.resolve())
    if rs not in sys.path:
        sys.path.insert(0, rs)
    try:
        from finance_agent import swarm_knowledge as sk  # noqa: PLC0415
    except ImportError:
        return 0, "swarm_sk_missing", {"enabled": True, "ok": False}

    mode = sk.sygnif_swarm_btc_future_mode()
    if mode == "off":
        return 0, "off", {"enabled": False}

    sym = os.environ.get("SYGNIF_SWARM_BTC_FUTURE_SYMBOL", "BTCUSDT").strip().upper() or "BTCUSDT"
    try:
        cache_sec = float(os.environ.get("SYGNIF_SWARM_BTC_FUTURE_CACHE_SEC", "60") or 60)
    except ValueError:
        cache_sec = 60.0
    ttl = max(15.0, cache_sec)

    if mode == "demo":
        has_demo = bool(
            os.environ.get("BYBIT_DEMO_API_KEY", "").strip()
            and os.environ.get("BYBIT_DEMO_API_SECRET", "").strip()
        )
        if not has_demo:
            return 0, "no_demo_creds", {"enabled": True, "ok": False, "has_demo_keys": False, "profile": "btc_future"}

        resp = sk.fetch_demo_linear_position_list(sym, cache_sec=ttl)
        v, d = sk.vote_account_position_from_response(resp)
        ok = resp is not None and resp.get("retCode") == 0
        meta: dict[str, Any] = {
            "enabled": True,
            "ok": ok,
            "has_demo_keys": True,
            "symbol": sym,
            "profile": "btc_future",
            "mode": "demo",
        }
        snap = sk.linear_position_snapshot_from_response(resp)
        if snap is not None:
            meta["position"] = snap
        return v, d, meta

    has_trade = bool(
        os.environ.get("BYBIT_API_KEY", "").strip()
        and os.environ.get("BYBIT_API_SECRET", "").strip()
    )
    if not has_trade:
        return 0, "no_trade_creds", {"enabled": True, "ok": False, "has_trade_keys": False, "profile": "trade"}

    resp = sk.fetch_mainnet_linear_position_list(sym, cache_sec=ttl)
    v, d = sk.vote_account_position_from_response(resp)
    ok = resp is not None and resp.get("retCode") == 0
    meta = {
        "enabled": True,
        "ok": ok,
        "has_trade_keys": True,
        "symbol": sym,
        "profile": "trade",
        "mode": "trade",
        "mainnet": True,
    }
    snap = sk.linear_position_snapshot_from_response(resp)
    if snap is not None:
        meta["position"] = snap
    return v, d, meta


def _btc_future_direction(v: int) -> str:
    """Semantic direction from linear position vote (same as swarm ``bf``)."""
    if v >= 1:
        return "long"
    if v <= -1:
        return "short"
    return "flat"


def _swarm_keypoints_for_fusion(repo_root: Path) -> list[dict[str, Any]]:
    """Annotations from ``swarm_knowledge_output.json`` (full ``compute_swarm`` JSON)."""
    p = repo_root / "prediction_agent" / "swarm_knowledge_output.json"
    sw = _read_json(p)
    if not sw:
        return []
    try:
        from swarm_annotations import build_swarm_keypoints  # noqa: PLC0415
    except ImportError:
        return []
    return build_swarm_keypoints(sw)


def _vote_ml_consensus(pred: dict[str, Any]) -> tuple[int, str]:
    pr = pred.get("predictions") if isinstance(pred.get("predictions"), dict) else {}
    raw = str(pr.get("consensus_nautilus_enhanced") or pr.get("consensus") or "").strip().upper()
    if raw in ("BULLISH", "STRONG_BULLISH"):
        return 1, raw
    if raw in ("BEARISH", "STRONG_BEARISH"):
        return -1, raw
    if raw == "MIXED":
        return 0, "MIXED"
    dlr = pr.get("direction_logistic") if isinstance(pr.get("direction_logistic"), dict) else {}
    lab = str(dlr.get("label") or "").strip().upper()
    try:
        conf = float(dlr.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf >= 65.0:
        if lab == "UP":
            return 1, f"LRup{conf:.0f}"
        if lab == "DOWN":
            return -1, f"LRdn{conf:.0f}"
    return 0, raw or "?"


def _atomic_write(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def build_fusion_payload(
    repo_root: Path,
    *,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data_dir = _btc_data_dir(repo_root)
    naut = _read_json(data_dir / "nautilus_strategy_signal.json")
    pred = _read_json(repo_root / "prediction_agent" / "btc_prediction_output.json")

    vn, nlab = _vote_nautilus_bias(naut or {})
    vm, mlab = _vote_ml_consensus(pred or {})
    v_bf, bf_lab, bf_meta = _btc_future_fusion_vote(repo_root)
    fused = vn + vm + v_bf
    if fused >= 2:
        label = "strong_long"
    elif fused <= -2:
        label = "strong_short"
    elif fused == 1:
        label = "lean_long"
    elif fused == -1:
        label = "lean_short"
    else:
        label = "neutral"

    prev_tick = None
    if isinstance(previous, dict):
        ppl = previous.get("predict_protocol_loop")
        if isinstance(ppl, dict):
            prev_tick = ppl

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nautilus_strategy_signal_path": str((data_dir / "nautilus_strategy_signal.json").resolve()),
        "nautilus_sidecar": naut,
        "btc_prediction_path": str((repo_root / "prediction_agent" / "btc_prediction_output.json").resolve()),
        "btc_prediction": pred,
        "fusion": {
            "vote_nautilus": vn,
            "vote_ml": vm,
            "vote_btc_future": v_bf,
            "btc_future_direction": _btc_future_direction(int(v_bf)),
            "sum": fused,
            "label": label,
            "nautilus_detail": nlab,
            "ml_detail": mlab,
            "btc_future_detail": bf_lab,
            "btc_future_meta": bf_meta,
        },
        "swarm_keypoints": _swarm_keypoints_for_fusion(repo_root),
    }
    if prev_tick:
        out["predict_protocol_loop"] = prev_tick
    return out


def write_fused_sidecar(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    path = fused_sidecar_path(root)
    prev = _read_json(path)
    doc = build_fusion_payload(root, previous=prev)
    _atomic_write(path, doc)
    return doc


def record_protocol_tick(repo_root: Path, tick: dict[str, Any]) -> dict[str, Any] | None:
    """Merge ``predict_protocol_loop`` from live loop; preserves other keys when possible."""
    path = fused_sidecar_path(repo_root)
    prev = _read_json(path)
    if prev is None:
        doc = build_fusion_payload(repo_root, previous=None)
    else:
        doc = build_fusion_payload(repo_root, previous=prev)
    doc["predict_protocol_loop"] = {
        "recorded_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **tick,
    }
    _atomic_write(path, doc)
    return doc


def briefing_line_nautilus_fusion(*, max_chars: int, repo_root: Path | None = None) -> str:
    if not _env_truthy("SYGNIF_BRIEFING_INCLUDE_NAUTILUS_FUSION"):
        return ""
    root = repo_root or _repo_root()
    path = fused_sidecar_path(root)
    if not path.is_file():
        return ""
    try:
        age_s = time.time() - path.stat().st_mtime
    except OSError:
        return ""
    try:
        max_h = float(os.environ.get("SYGNIF_BRIEFING_NAUTILUS_FUSION_MAX_AGE_H", "24"))
    except ValueError:
        max_h = 24.0
    if age_s > max(60.0, max_h * 3600.0):
        return ""
    data = _read_json(path)
    if not data:
        return ""
    gen = str(data.get("generated_utc", "?"))[:19]
    fus = data.get("fusion") or {}
    lab = fus.get("label", "?")
    line = (
        f"NAU_FUSE|utc={gen}|fuse={lab}|n={fus.get('nautilus_detail')}|ml={fus.get('ml_detail')}"
        f"|bf={fus.get('btc_future_detail', '?')}"
    )
    ppl = data.get("predict_protocol_loop")
    if isinstance(ppl, dict) and ppl.get("target_side") is not None:
        ts = str(ppl.get("recorded_utc", "?"))[:16]
        line += f"|loop@{ts} tgt={ppl.get('target_side')}"
    if len(line) > max_chars:
        line = line[: max_chars - 3] + "..."
    return line


def main() -> int:
    ap = argparse.ArgumentParser(description="Nautilus + BTC predict + protocol fusion sidecar")
    ap.add_argument("cmd", nargs="?", default="sync", choices=("sync", "print-briefing"))
    args = ap.parse_args()
    root = _repo_root()
    if args.cmd == "sync":
        doc = write_fused_sidecar(root)
        print(json.dumps({"ok": True, "path": str(fused_sidecar_path(root)), "fusion": doc.get("fusion")}))
        return 0
    line = briefing_line_nautilus_fusion(max_chars=400, repo_root=root)
    print(line or "(empty — enable SYGNIF_BRIEFING_INCLUDE_NAUTILUS_FUSION for briefing consumer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
