#!/usr/bin/env python3
"""
**Swarm + predict-protocol auto trading (Bybit demo)** — launcher for ``btc_predict_protocol_loop.py``.

Sets operator env so each loop iteration:

- runs ``compute_swarm()`` + ``write_fused_sidecar`` + ``swarm_fusion_allows`` (``SYGNIF_SWARM_GATE_LOOP=1``)
- requires **btc_future** branch in Swarm (``SYGNIF_SWARM_BTC_FUTURE=1``) and fusion **bf** alignment
  (same as ``swarm_gated_predict_protocol_order.py``)
- **btc_future governance:** ``SYGNIF_SWARM_BTC_FUTURE_GOVERNANCE=1`` + raw **bf** vote alignment
  (``SWARM_ORDER_REQUIRE_BTC_FUTURE_VOTE``); flat demo allowed if ``SWARM_ORDER_BTC_FUTURE_VOTE_FLAT_PASS=1``
- **~USDT take-profit** after open: ``SYGNIF_SWARM_TP_USDT_TARGET`` (default **50** for a **$50** TP distance target)

**letscrash / BTC-0.1 first:** ``decide_side`` already applies **R01** bearish stack from
``letscrash/btc_strategy_0_1_rule_registry.json`` (via ``r01_registry_bridge``). The loop can **clip** USDT
notional to ``rule_proof_bucket.notional_cap_usdt`` when ``SYGNIF_LETSCRASH_NOTIONAL_CAP=1`` (default in launcher).

**Open as soon as prediction completes:** default ``SYGNIF_PREDICT_OPEN_IMMEDIATE=1`` injects ``--interval-sec 0``
(back-to-back predict → gate → venue). Use ``--paced`` or ``SYGNIF_PREDICT_OPEN_IMMEDIATE=0`` for ``--interval-sec 300``
(5m bar spacing).

**Defaults injected** when you omit flags: ``--interval-sec`` per immediate setting, ``--manual-notional-usdt 2000``,
``--manual-leverage 50`` (50× linear). **Leverage / size** still follow prediction when you omit manual flags (loop uses
``leverage_from_move_pct`` + stake math from ``btc_asap_predict_core``).

**Eligible timeframe:** candle interval is **5m** for ``run_live_fit``. Use ``--eligible-scan`` for a quick
historical eligibility snapshot (subsampling), or ``scripts/predict_protocol_eligible_scan.py`` for a deeper scan.

**Safety:** still requires ``SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES`` and ``--execute`` on the loop.
This script does **not** remove human ACK — it only configures Swarm + sizing defaults.

**Instance / multi-repo:** dotenv + optional ``PYTHONPATH`` for sibling projects under ``$HOME`` are handled by
``finance_agent/swarm_instance_paths.py`` (``SYGNIF_SWARM_LINK_INSTANCE``, ``SYGNIF_INSTANCE_ROOTS``,
``SYGNIF_INSTANCE_ROOTS_SCAN``, ``SYGNIF_SWARM_EXTEND_PYTHONPATH``). See that module for precedence.
This launcher **defaults** ``SYGNIF_INSTANCE_ROOTS_SCAN=1``, ``SYGNIF_SWARM_EXTEND_PYTHONPATH=1``,
``SYGNIF_INSTANCE_ROOTS_EXCLUDE=logs:intel``, ``SYGNIF_SWARM_TRUTHCOIN_DC=1``,
``SYGNIF_SWARM_CORE_ENGINE=hivemind``, ``SYGNIF_SWARM_HIVEMIND_VOTE=1``, ``SYGNIF_SWARM_FULL_ROOT_ACCESS=1``
(Truthcoin Hivemind drives ``swarm_mean`` when the node is up; see ``finance_agent/truthcoin_hivemind_swarm_core.py``);
override in ``.env`` / ``swarm_operator.env``.

Examples::

  SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES \\
    python3 scripts/swarm_auto_predict_protocol_loop.py --execute

  python3 scripts/swarm_auto_predict_protocol_loop.py --eligible-scan

  SYGNIF_SWARM_TP_USDT_TARGET=75 python3 scripts/swarm_auto_predict_protocol_loop.py --execute \\
    --manual-notional-usdt 2000 --manual-leverage 50 --interval-sec 300

  # 5m pacing instead of immediate:
  python3 scripts/swarm_auto_predict_protocol_loop.py --paced --execute
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "finance_agent"))
from swarm_instance_paths import (  # noqa: E402
    apply_swarm_instance_env,
    subprocess_env_with_instance_pythonpath,
)


def _repo() -> Path:
    return _REPO


def _predict_open_immediate() -> bool:
    """Default **immediate** (interval 0) unless ``SYGNIF_PREDICT_OPEN_IMMEDIATE=0``."""
    raw = (os.environ.get("SYGNIF_PREDICT_OPEN_IMMEDIATE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _merge_loop_defaults(rest: list[str]) -> list[str]:
    """Prepend pacing + sizing defaults unless already present."""
    joined = " ".join(rest)
    out = list(rest)
    if "--interval-sec" not in joined:
        iv = "0" if _predict_open_immediate() else "300"
        out = ["--interval-sec", iv] + out
    if "--manual-notional-usdt" not in joined:
        out = ["--manual-notional-usdt", "2000"] + out
    if "--manual-leverage" not in joined:
        out = ["--manual-leverage", "50"] + out
    return out


def load_swarm_demo_env(*, extra_env_file: Path | None = None) -> None:
    apply_swarm_instance_env(_repo(), extra_env_file=extra_env_file)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Launch predict-protocol loop with Swarm gate + btc_future fusion defaults",
    )
    ap.add_argument(
        "--env-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Optional .env loaded last (overrides); use for BYBIT_DEMO_* keys",
    )
    ap.add_argument(
        "--no-tp-target",
        action="store_true",
        help="Do not default SYGNIF_SWARM_TP_USDT_TARGET=50",
    )
    ap.add_argument(
        "--eligible-scan",
        action="store_true",
        help="Run a fast predict_protocol_eligible_scan (5m / window=5) and exit",
    )
    ap.add_argument(
        "--paced",
        action="store_true",
        help="5m pacing: set SYGNIF_PREDICT_OPEN_IMMEDIATE=0 so loop uses --interval-sec 300",
    )
    args, rest = ap.parse_known_args()

    load_swarm_demo_env(extra_env_file=args.env_file)
    # Multi-repo + Truthcoin context (override in .env / swarm_operator.env if undesired)
    os.environ.setdefault("SYGNIF_INSTANCE_ROOTS_SCAN", "1")
    os.environ.setdefault("SYGNIF_SWARM_EXTEND_PYTHONPATH", "1")
    os.environ.setdefault("SYGNIF_INSTANCE_ROOTS_EXCLUDE", "logs:intel")
    os.environ.setdefault("SYGNIF_SWARM_TRUTHCOIN_DC", "1")
    os.environ.setdefault("SYGNIF_SWARM_CORE_ENGINE", "hivemind")
    os.environ.setdefault("SYGNIF_SWARM_HIVEMIND_VOTE", "1")
    os.environ.setdefault("SYGNIF_SWARM_FULL_ROOT_ACCESS", "1")

    if args.paced:
        os.environ["SYGNIF_PREDICT_OPEN_IMMEDIATE"] = "0"

    if args.eligible_scan:
        scan = _repo() / "scripts" / "predict_protocol_eligible_scan.py"
        argv_scan = [
            sys.executable,
            str(scan),
            "--kline-limit",
            "320",
            "--step",
            "20",
            "--window",
            "5",
            "--manual-notional-usdt",
            "2000",
            "--manual-leverage",
            "50",
        ]
        print(
            "[swarm-auto] eligible timeframe: protocol uses 5m klines; interval-sec 300 aligns loop with new bar.",
            flush=True,
        )
        print(f"[swarm-auto] exec {' '.join(argv_scan)}", flush=True)
        return int(
            subprocess.run(
                argv_scan,
                cwd=str(_repo()),
                env=subprocess_env_with_instance_pythonpath(_repo()),
            ).returncode
        )

    os.environ.setdefault("SYGNIF_PREDICT_OPEN_IMMEDIATE", "1")
    os.environ.setdefault("SYGNIF_LETSCRASH_NOTIONAL_CAP", "1")
    os.environ.setdefault("SYGNIF_SWARM_AUTO_TRADING", "1")
    os.environ.setdefault("SYGNIF_SWARM_GATE_LOOP", "1")
    os.environ.setdefault("SYGNIF_SWARM_BTC_FUTURE", "1")
    os.environ.setdefault("SYGNIF_SWARM_BTC_FUTURE_GOVERNANCE", "1")
    os.environ.setdefault("SWARM_ORDER_REQUIRE_BTC_FUTURE", "1")
    os.environ.setdefault("SWARM_ORDER_REQUIRE_FUSION_ALIGN", "1")
    os.environ.setdefault("SWARM_ORDER_FUSION_ALIGN_BTC_FUTURE", "1")
    os.environ.setdefault("SWARM_ORDER_REQUIRE_BTC_FUTURE_VOTE", "1")
    os.environ.setdefault("SWARM_ORDER_BTC_FUTURE_VOTE_FLAT_PASS", "1")
    if not args.no_tp_target:
        os.environ.setdefault("SYGNIF_SWARM_TP_USDT_TARGET", "50")

    loop = _repo() / "scripts" / "btc_predict_protocol_loop.py"
    rest_merged = _merge_loop_defaults(rest)
    argv = [sys.executable, str(loop), *rest_merged]
    print(f"[swarm-auto] exec {' '.join(argv)}", flush=True)
    r = subprocess.run(
        argv,
        cwd=str(_repo()),
        env=subprocess_env_with_instance_pythonpath(_repo()),
    )
    return int(r.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
