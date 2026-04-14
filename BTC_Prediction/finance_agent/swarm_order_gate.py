"""
Gating helpers for Swarm + Nautilus/ML/**btc_future** fusion before predict-protocol demo orders.

When ``SWARM_ORDER_REQUIRE_FUSION_ALIGN=1`` (default in ``swarm_gated_predict_protocol_order``):

- ``SWARM_ORDER_FUSION_ALIGN_LABEL`` (default on): fused sum-label must be lean/strong long or short.
- ``SWARM_ORDER_FUSION_ALIGN_BTC_FUTURE`` (on in that script): ``vote_btc_future`` must align with the
  protocol target (demo position **bf** vote). Set ``SWARM_ORDER_BTC_FUTURE_FLAT_PASS=1`` to allow
  ``vote_btc_future==0`` with long/short.

Optional **raw Swarm hm vote** (Truthcoin Hivemind liveness, ``sources.hm``):

- ``SWARM_ORDER_REQUIRE_HIVEMIND_VOTE=1`` — long requires **hm** ``>= 1``, short requires ``<= -1``.
  ``SWARM_ORDER_HIVEMIND_VOTE_FLAT_PASS=1`` allows ``hm`` vote ``0``.

Optional **raw Swarm bf vote** (from ``swarm_knowledge_output.json`` ``sources.bf``), before fusion:

- ``SYGNIF_SWARM_BTC_FUTURE_GOVERNANCE=1`` — shorthand for **btc_future-governed** entries: same as
  ``SWARM_ORDER_REQUIRE_BTC_FUTURE_VOTE=1`` (override off with ``SWARM_ORDER_REQUIRE_BTC_FUTURE_VOTE=0``).
- ``SWARM_ORDER_REQUIRE_BTC_FUTURE_VOTE=1`` — long requires **bf** vote ``>= 1``, short requires ``<= -1``.
  ``SWARM_ORDER_BTC_FUTURE_VOTE_FLAT_PASS=1`` allows ``bf`` vote ``0`` (demo flat).

See ``scripts/swarm_gated_predict_protocol_order.py`` and ``scripts/swarm_auto_predict_protocol_loop.py``.
"""
from __future__ import annotations

import os
from typing import Any


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _require_btc_future_ok() -> bool:
    v = os.environ.get("SWARM_ORDER_REQUIRE_BTC_FUTURE", "1").strip().lower()
    return v in ("1", "true", "yes", "on", "")


def _require_btc_future_vote_align() -> bool:
    """
    When set, require **bf** (demo linear position vote) to agree with the protocol target.

    Long  → vote >= +1; short → vote <= -1. Use ``SWARM_ORDER_BTC_FUTURE_VOTE_FLAT_PASS=1`` to allow bf==0.

    ``SYGNIF_SWARM_BTC_FUTURE_GOVERNANCE=1`` enables vote alignment unless
    ``SWARM_ORDER_REQUIRE_BTC_FUTURE_VOTE`` is explicitly ``0``/``off``.
    """
    raw = os.environ.get("SWARM_ORDER_REQUIRE_BTC_FUTURE_VOTE", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if _env_truthy("SYGNIF_SWARM_BTC_FUTURE_GOVERNANCE"):
        return True
    if not raw:
        return False
    return raw in ("1", "true", "yes", "on")


def _btc_future_vote_flat_pass() -> bool:
    return _env_truthy("SWARM_ORDER_BTC_FUTURE_VOTE_FLAT_PASS")


def _require_hivemind_vote_align() -> bool:
    """When set, require ``sources.hm`` (Truthcoin Hivemind liveness vote) to agree with target."""
    return _env_truthy("SWARM_ORDER_REQUIRE_HIVEMIND_VOTE")


def _hivemind_vote_flat_pass() -> bool:
    return _env_truthy("SWARM_ORDER_HIVEMIND_VOTE_FLAT_PASS")


def _fusion_align_label_on() -> bool:
    """Default True when unset (label gate is part of fusion aligner)."""
    raw = os.environ.get("SWARM_ORDER_FUSION_ALIGN_LABEL", "").strip()
    if not raw:
        return True
    return raw.lower() in ("1", "true", "yes", "on")


def _fusion_align_btc_future_on() -> bool:
    """Default False unless set — ``swarm_gated_predict_protocol_order`` sets it to 1."""
    raw = os.environ.get("SWARM_ORDER_FUSION_ALIGN_BTC_FUTURE", "").strip()
    if not raw:
        return False
    return raw.lower() in ("1", "true", "yes", "on")


def swarm_fusion_allows(
    *,
    target: str | None,
    swarm: dict[str, Any],
    fusion_doc: dict[str, Any] | None,
) -> tuple[bool, str]:
    if target is None:
        return False, "no_edge"
    min_long = _env_float("SWARM_ORDER_MIN_MEAN_LONG", 0.0)
    max_short = _env_float("SWARM_ORDER_MAX_MEAN_SHORT", 0.0)
    try:
        mean = float(swarm.get("swarm_mean") or 0.0)
    except (TypeError, ValueError):
        mean = 0.0
    conflict = bool(swarm.get("swarm_conflict"))
    label = str(swarm.get("swarm_label") or "")

    if _env_truthy("SWARM_ORDER_BLOCK_CONFLICT") and conflict:
        return False, "swarm_conflict"

    bf = swarm.get("btc_future") if isinstance(swarm.get("btc_future"), dict) else {}
    if _require_btc_future_ok() and bf.get("enabled") and not bf.get("ok"):
        return False, "btc_future_not_ok"

    if _require_btc_future_vote_align():
        src = swarm.get("sources") if isinstance(swarm.get("sources"), dict) else {}
        bf_src = src.get("bf") if isinstance(src.get("bf"), dict) else {}
        try:
            v_bf_src = int(bf_src.get("vote") or 0)
        except (TypeError, ValueError):
            v_bf_src = 0
        flat_ok = _btc_future_vote_flat_pass()
        if target == "long":
            if v_bf_src >= 1:
                pass
            elif v_bf_src == 0 and flat_ok:
                pass
            else:
                return False, f"swarm_bf_vote={v_bf_src}_need_long_or_flat_ok"
        elif target == "short":
            if v_bf_src <= -1:
                pass
            elif v_bf_src == 0 and flat_ok:
                pass
            else:
                return False, f"swarm_bf_vote={v_bf_src}_need_short_or_flat_ok"

    if _require_hivemind_vote_align():
        src = swarm.get("sources") if isinstance(swarm.get("sources"), dict) else {}
        hm_src = src.get("hm") if isinstance(src.get("hm"), dict) else {}
        try:
            v_hm_src = int(hm_src.get("vote") or 0)
        except (TypeError, ValueError):
            v_hm_src = 0
        hm_flat = _hivemind_vote_flat_pass()
        if target == "long":
            if v_hm_src >= 1:
                pass
            elif v_hm_src == 0 and hm_flat:
                pass
            else:
                return False, f"swarm_hm_vote={v_hm_src}_need_long_or_flat_ok"
        elif target == "short":
            if v_hm_src <= -1:
                pass
            elif v_hm_src == 0 and hm_flat:
                pass
            else:
                return False, f"swarm_hm_vote={v_hm_src}_need_short_or_flat_ok"

    if target == "long":
        if mean < min_long:
            return False, f"swarm_mean {mean:.3f} < SWARM_ORDER_MIN_MEAN_LONG ({min_long})"
        if "BEAR" in label.upper() and _env_truthy("SWARM_ORDER_BLOCK_SWARM_BEAR_LABEL"):
            return False, "swarm_label_bear"
    elif target == "short":
        if mean > max_short:
            return False, f"swarm_mean {mean:.3f} > SWARM_ORDER_MAX_MEAN_SHORT ({max_short})"
        if _env_truthy("SWARM_ORDER_BLOCK_SWARM_BULL_LABEL") and "BULL" in label.upper():
            return False, "swarm_label_bull"

    # --- Nautilus+ML+btc_future fusion aligner (``swarm_nautilus_protocol_sidecar.json``) ---
    if not _env_truthy("SWARM_ORDER_REQUIRE_FUSION_ALIGN"):
        return True, "ok"
    if not fusion_doc:
        return False, "fusion_doc_missing"

    fus = fusion_doc.get("fusion") if isinstance(fusion_doc.get("fusion"), dict) else {}

    # Sum-based label (Nautilus + ML + **btc_future** vote)
    if _fusion_align_label_on():
        flab = str(fus.get("label") or "")
        if target == "long" and flab not in ("strong_long", "lean_long"):
            return False, f"fusion_label={flab!r}_want_long"
        if target == "short" and flab not in ("strong_short", "lean_short"):
            return False, f"fusion_label={flab!r}_want_short"

    # **btc_future** (demo position) vote — venue anchor for swarm.orders
    if _fusion_align_btc_future_on():
        try:
            v_bf = int(fus.get("vote_btc_future") or 0)
        except (TypeError, ValueError):
            v_bf = 0
        flat_ok = _env_truthy("SWARM_ORDER_BTC_FUTURE_FLAT_PASS")
        if target == "long":
            if v_bf >= 1:
                pass
            elif v_bf == 0 and flat_ok:
                pass
            else:
                return False, f"btc_future_vote={v_bf}_need_long_or_flat_ok"
        elif target == "short":
            if v_bf <= -1:
                pass
            elif v_bf == 0 and flat_ok:
                pass
            else:
                return False, f"btc_future_vote={v_bf}_need_short_or_flat_ok"

    return True, "ok"
