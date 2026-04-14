#!/usr/bin/env python3
"""
**Bitcoin Truthcoin / Hivemind** as an optional **Swarm processing core**.

When ``SYGNIF_SWARM_CORE_ENGINE=hivemind`` and the Truthcoin CLI snapshot is **reachable**,
``compute_swarm()`` drives ``swarm_mean`` / ``swarm_label`` / ``swarm_conflict`` from the Hivemind
signal only (file + Bybit votes remain in ``sources`` for audit). When the node is down, Swarm
falls back to the usual Python mean over all sources (including optional ``hm``).

**Full root access** (operator visibility, read-only): ``SYGNIF_SWARM_FULL_ROOT_ACCESS=1`` adds
``swarm_processing_roots`` and ``swarm_host_root_manifest`` top-level entries — first-level names
under ``/`` and ``$HOME`` (capped). This does **not** run Python as UNIX ``root``; use container
capabilities if you need privileged ports.

Env (core):

- ``SYGNIF_SWARM_CORE_ENGINE`` — ``python`` (default) or ``hivemind``.
- ``SYGNIF_SWARM_HIVEMIND_VOTE`` — ``1`` appends ``sources.hm`` even when core is ``python``.
- ``SYGNIF_SWARM_HM_VOTE_MIN_VOTING_SLOTS`` — minimum ``slots_voting_n`` for ``hm`` vote ``+1`` (default ``1``).
- ``SYGNIF_TRUTHCOIN_DC_ROOT`` — Truthcoin repo root (default ``~/truthcoin-dc``).

Env (gate — see ``swarm_order_gate``): ``SWARM_ORDER_REQUIRE_HIVEMIND_VOTE``,
``SWARM_ORDER_HIVEMIND_VOTE_FLAT_PASS``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def swarm_core_engine() -> str:
    return (os.environ.get("SYGNIF_SWARM_CORE_ENGINE") or "python").strip().lower()


def sygnif_repo_root() -> Path:
    raw = (os.environ.get("SYGNIF_REPO_ROOT") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def processing_roots() -> list[Path]:
    """Configured processing trees (SYGNIF + Truthcoin + optional colon list)."""
    from finance_agent.truthcoin_dc_swarm_bridge import truthcoin_dc_repo_root

    seen: set[Path] = set()
    roots: list[Path] = []
    for p in (sygnif_repo_root(), truthcoin_dc_repo_root()):
        p = p.resolve()
        if p.is_dir() and p not in seen:
            seen.add(p)
            roots.append(p)
    raw = (os.environ.get("SYGNIF_SWARM_PROCESSING_ROOTS") or "").strip()
    if raw:
        for part in raw.split(":"):
            part = part.strip()
            if not part:
                continue
            p = Path(part).expanduser().resolve()
            if p.is_dir() and p not in seen:
                seen.add(p)
                roots.append(p)
    return roots


def hivemind_explore_needed() -> bool:
    """Whether to call the Truthcoin CLI snapshot this tick."""
    if _env_truthy("SYGNIF_SWARM_TRUTHCOIN_DC"):
        return True
    if _env_truthy("SYGNIF_SWARM_HIVEMIND_VOTE"):
        return True
    return swarm_core_engine() == "hivemind"


def vote_hivemind_from_explore(doc: dict[str, Any]) -> tuple[int, str]:
    """
    Map ``hivemind_explore_snapshot()`` → Swarm vote in ``{-1, 0, +1}``.

    Heuristic: active decision slots in **voting** imply live Hivemind activity → ``+1``;
    otherwise ``0``. (Directional BTC signal still comes from ``bf`` / ML; ``hm`` is protocol liveness.)
    """
    if not doc.get("ok"):
        return 0, "hivemind_unreachable"
    try:
        thr = int(os.environ.get("SYGNIF_SWARM_HM_VOTE_MIN_VOTING_SLOTS", "1") or 1)
    except ValueError:
        thr = 1
    n = int(doc.get("slots_voting_n") or 0)
    nm = int(doc.get("markets_trading_n") or 0)
    if n >= thr:
        return 1, f"hivemind_active_slots_voting={n}_markets_trading={nm}"
    return 0, f"hivemind_quiet_slots_voting={n}_markets_trading={nm}"


def build_processing_roots_manifest() -> dict[str, Any] | None:
    if not _env_truthy("SYGNIF_SWARM_FULL_ROOT_ACCESS"):
        return None
    from finance_agent.truthcoin_dc_swarm_bridge import truthcoin_dc_repo_root

    roots_paths = processing_roots()
    roots = [str(p) for p in roots_paths]
    manifest: dict[str, Any] = {
        "sygnif_repo": str(sygnif_repo_root()),
        "truthcoin_dc_root": str(truthcoin_dc_repo_root()),
        "processing_roots": roots,
    }
    try:
        root_entries = sorted(os.listdir("/"))[:200]
        manifest["host_root_entries"] = root_entries
    except OSError as exc:
        manifest["host_root_error"] = str(exc)
    try:
        home = Path.home()
        manifest["home_entries"] = sorted(os.listdir(home))[:200]
    except OSError as exc:
        manifest["home_entries_error"] = str(exc)
    return manifest
