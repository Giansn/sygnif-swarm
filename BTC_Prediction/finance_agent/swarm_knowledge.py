#!/usr/bin/env python3
"""
Swarm knowledge: fuse BTC file sidecars + optional Bybit **mainnet** and **demo (btc_future)** reads into one score + JSON.

**This module never posts orders.** Venue execution lives in ``trade_overseer/bybit_linear_hedge.py`` and
ACK-gated scripts. **Auto-trading with Swarm** is enabled by running ``scripts/btc_predict_protocol_loop.py``
with ``SYGNIF_SWARM_GATE_LOOP=1`` (see ``scripts/swarm_auto_predict_protocol_loop.py``): each iteration
calls ``compute_swarm()`` + fusion, then ``swarm_fusion_allows`` gates **entries**; ``swarm_knowledge`` itself
still never calls ``POST /v5/order/*``.

Sources (votes in {-1, 0, +1} unless noted):
  - File: ML, channel, sidecar, TA (same as before).
  - ``mn`` — public ``GET /v5/market/tickers`` (no keys).
  - ``ac`` — signed ``GET /v5/position/list`` (linear) when ``SYGNIF_SWARM_BYBIT_ACCOUNT=1``
    **or** ``SYGNIF_SWARM_BYBIT_MODE=admin``.
  - ``bf`` (**btc_future**) — signed **Bybit API demo** linear ``position/list`` via
    ``trade_overseer/bybit_linear_hedge.py`` when ``SYGNIF_SWARM_BTC_FUTURE=1`` and
    ``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET`` are set. Same vote mapping as ``ac``;
    **demo host only** (not mainnet). Read-only. JSON includes ``btc_future.position`` (TP/SL,
    size, PnL, …) from ``linear_position_snapshot_from_response``.

**Admin tier** (expanded **read** scope, still **no writes**):
  ``SYGNIF_SWARM_BYBIT_MODE=admin`` (alias: ``SYGNIF_SWARM_BYBIT_ADMIN=1``) — same as enabling
  signed **position** plus **unified wallet** ``GET /v5/account/wallet-balance`` (USDT available parsed
  like ``btc_asap_predict_core.parse_usdt_available``). Briefing shows **banded** liquidity (e.g. ``~12k``),
  not exact balances.

**Sealed output** (optional at-rest packaging): ``SYGNIF_SWARM_FERNET_KEY`` + ``pip install cryptography``;
see ``swarm_crypto.py``. ``SYGNIF_SWARM_OUTPUT`` = ``plaintext`` | ``sealed`` | ``both``.

Env (public mainnet tickers): ``SYGNIF_SWARM_BYBIT_MAINNET``, ``SYGNIF_SWARM_BYBIT_SYMBOL``,
``SYGNIF_SWARM_BYBIT_CATEGORY``, ``SYGNIF_SWARM_BYBIT_24H_PCT_THR``, timeouts, cache TTLs.

Env (signed reads): ``BYBIT_API_KEY`` / ``BYBIT_API_SECRET``, ``SYGNIF_SWARM_BYBIT_ACCOUNT``,
``SYGNIF_SWARM_BYBIT_ACCOUNT_CACHE_SEC``, ``SYGNIF_SWARM_WALLET_CACHE_SEC`` (default ``60``),
``SYGNIF_SWARM_WALLET_ROUND_USDT`` (default ``1000``).

Env (**btc_future** / demo linear position vote): ``SYGNIF_SWARM_BTC_FUTURE=1``,
``SYGNIF_SWARM_BTC_FUTURE_SYMBOL`` (default ``BTCUSDT``), ``SYGNIF_SWARM_BTC_FUTURE_CACHE_SEC`` (default ``60``).
Optional debug (no secret): ``SYGNIF_SWARM_PRINT_DEMO_API_KEY_HINT=1`` adds ``demo_api_key_hint`` (masked
``BYBIT_DEMO_API_KEY``) under ``btc_future`` so you can confirm which key Swarm loaded.

**Truthcoin Drivechain (Bitcoin Hivemind)** (read-only CLI; see `Truthcoin README
<https://github.com/LayerTwo-Labs/truthcoin-dc/blob/master/README.md>`__): when enabled, ``compute_swarm`` may fetch
``hivemind_explore`` (``slot-status``, ``slot-list --status voting``, ``status``, ``market-list``) and attach it under
``btc_future`` when ``SYGNIF_SWARM_BTC_FUTURE=1``, plus top-level ``hivemind_explore`` when the Truthcoin integration is
active. **Processing core:** ``SYGNIF_SWARM_CORE_ENGINE=hivemind`` drives ``swarm_mean`` / ``swarm_label`` from the
Hivemind liveness vote when the node is reachable; otherwise Python mean over file + venue sources. **``hm`` vote:**
``SYGNIF_SWARM_HIVEMIND_VOTE=1`` or ``hivemind`` core appends ``sources.hm``. **Host visibility (not UNIX root):**
``SYGNIF_SWARM_FULL_ROOT_ACCESS=1`` adds ``swarm_processing_roots`` (``/`` and ``$HOME`` top-level names, capped).
Configure ``SYGNIF_TRUTHCOIN_DC_ROOT``, ``SYGNIF_TRUTHCOIN_DC_CLI``, ``SYGNIF_TRUTHCOIN_DC_RPC_PORT`` (default ``6013``),
``SYGNIF_TRUTHCOIN_DC_TIMEOUT_SEC``, ``SYGNIF_TRUTHCOIN_DC_CACHE_SEC``.

**Open trades report:** ``SYGNIF_SWARM_OPEN_TRADES=1`` (default **on**) adds ``open_trades`` — tries
``GET {OVERSEER_URL}/trades`` (trade-overseer), else SQLite (read-only).

**Scope (ignore archived multi-pair DBs by default):** ``SYGNIF_SWARM_OPEN_TRADES_SCOPE=btc_docker`` (default) only reads
``tradesv3-futures-btc01-demo.sqlite`` + ``tradesv3-btc-spot.sqlite`` (BTC Docker / BTC_Strategy_0_1 paths in compose) and
**only** rows where ``pair`` starts with ``BTC/``. Set to ``all`` to include legacy ``tradesv3.sqlite`` +
``tradesv3-futures.sqlite`` (archived-main-traders / multi-coin). ``SYGNIF_SWARM_OPEN_TRADES_BTC_ONLY=0`` disables the
``BTC/`` filter when scope is ``all``.

**Closed PnL history (USDT linear):** ``SYGNIF_SWARM_BYBIT_CLOSED_PNL=1`` adds ``bybit_closed_pnl`` — signed read-only
``GET /v5/position/closed-pnl`` via ``trade_overseer/bybit_linear_hedge.closed_pnl_linear`` (same host/keys as hedge:
**demo** ``BYBIT_DEMO_*`` by default, or **mainnet** ``BYBIT_API_*`` when ``OVERSEER_BYBIT_HEDGE_MAINNET`` +
``OVERSEER_HEDGE_LIVE_OK``). Env: ``SYGNIF_SWARM_BYBIT_CLOSED_PNL_SYMBOL`` (default: ``SYGNIF_SWARM_BYBIT_SYMBOL`` or
``BTCUSDT``), ``SYGNIF_SWARM_BYBIT_CLOSED_PNL_MAX_ROWS`` (fetch cap, default ``200``),
``SYGNIF_SWARM_BYBIT_CLOSED_PNL_MAX_LIST`` (rows in JSON, default ``50``), ``SYGNIF_SWARM_BYBIT_CLOSED_PNL_CACHE_SEC``
(default ``120``).

**Open (unrealised) P/L:** ``SYGNIF_SWARM_BYBIT_OPEN_PNL=1`` (default **on**) adds ``bybit_open_pnl`` — parses
``unrealisedPnl`` from **existing** ``GET /v5/position/list`` responses (``btc_future.position`` on demo when
``SYGNIF_SWARM_BTC_FUTURE=1``, and mainnet ``ac`` snapshot when ``SYGNIF_SWARM_BYBIT_ACCOUNT`` or admin mode). No extra
HTTP calls. Set ``SYGNIF_SWARM_BYBIT_OPEN_PNL=0`` to omit.

Optional **demo key bootstrap** (HTTPS only; used before ``bf`` when ``BYBIT_DEMO_*`` unset):
``SYGNIF_SWARM_DEMO_KEYS_WEBHOOK_URL``, ``SYGNIF_SWARM_DEMO_KEYS_WEBHOOK_TOKEN``,
``SYGNIF_SWARM_DEMO_KEYS_WEBHOOK_HEADER``, ``SYGNIF_SWARM_DEMO_KEYS_WEBHOOK_TTL_SEC`` — see ``swarm_demo_keys_fetch.py``.

``GET /briefing`` appendix: ``ruleprediction_briefing`` + ``SYGNIF_BRIEFING_INCLUDE_SWARM=1``.

**PyTorch fusion (optional):** ``SYGNIF_SWARM_PYTORCH=1`` uses ``swarm_pytorch_fusion`` for vectorized
mean / conflict (optional ``SYGNIF_SWARM_PT_WEIGHTS``). Requires ``torch`` (e.g. SYGNIF ``.venv``).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BYBIT_TICKER_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_BYBIT_ACCOUNT_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_BYBIT_WALLET_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_BYBIT_DEMO_BF_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_BYBIT_CLOSED_PNL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
BYBIT_MAINNET_API = "https://api.bybit.com/v5/market/tickers"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _finance_agent_dir() -> Path:
    return Path(__file__).resolve().parent


def _prediction_agent_dir() -> Path:
    for key in ("PREDICTION_AGENT_DIR", "SYGNIF_PREDICTION_AGENT_DIR"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            return Path(raw).expanduser()
    return _repo_root() / "prediction_agent"


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


def _masked_api_key_hint(raw: str, *, head: int = 4, tail: int = 4) -> str:
    """
    Non-secret fingerprint for Swarm JSON (which credential is loaded). Never log the full key.
    """
    s = (raw or "").strip()
    n = len(s)
    if n == 0:
        return ""
    if n <= head + tail:
        return s[:2] + "..." if n > 2 else "**"
    return f"{s[:head]}...{s[-tail:]}"


def _admin_tier_enabled() -> bool:
    m = os.environ.get("SYGNIF_SWARM_BYBIT_MODE", "").strip().lower()
    if m == "admin":
        return True
    return _env_truthy("SYGNIF_SWARM_BYBIT_ADMIN")


def _include_signed_position() -> bool:
    return _env_truthy("SYGNIF_SWARM_BYBIT_ACCOUNT") or _admin_tier_enabled()


def _parse_usdt_available_wallet(resp: dict[str, Any]) -> float | None:
    """Match ``btc_asap_predict_core.parse_usdt_available`` (UNIFIED wallet-balance shape)."""
    if resp.get("retCode") != 0:
        return None
    lst = (resp.get("result") or {}).get("list") or []
    if not lst:
        return None
    coins = lst[0].get("coin") or []
    if not isinstance(coins, list):
        return None
    for c in coins:
        if not isinstance(c, dict):
            continue
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


def wallet_usdt_band_label(usdt: float | None, *, step: float) -> str:
    """Compact briefing token; no exact balance."""
    if usdt is None:
        return "?"
    st = max(1.0, float(step))
    if usdt < st * 0.5:
        return "~0"
    q = int(usdt // st) * int(st)
    if q >= 1_000_000:
        return f"~{q // 1_000_000}M"
    if q >= 10_000:
        return f"~{q // 1000}k"
    if q >= 1000:
        return f"~{q // 1000}k"
    return f"~{int(q)}"


def _btc_data_dir() -> Path:
    raw = (os.environ.get("NAUTILUS_BTC_OHLCV_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _repo_root() / "finance_agent" / "btc_specialist" / "data"


def _consensus_to_vote(val: Any) -> int:
    if not isinstance(val, str):
        return 0
    v = val.upper().strip()
    if v in ("BULLISH", "STRONG_BULLISH"):
        return 1
    if v in ("BEARISH", "STRONG_BEARISH"):
        return -1
    return 0


def _vote_ml_enhanced(data: dict[str, Any]) -> tuple[int, str]:
    preds = data.get("predictions") if isinstance(data.get("predictions"), dict) else {}
    enh = preds.get("consensus_nautilus_enhanced")
    if enh is None:
        enh = preds.get("consensus")
    vote = _consensus_to_vote(enh)
    return vote, str(enh or "?")


def _vote_channel(recognition: dict[str, Any]) -> tuple[int, str]:
    try:
        up = float(recognition.get("last_bar_probability_up_pct") or 0.0)
        dn = float(recognition.get("last_bar_probability_down_pct") or 0.0)
    except (TypeError, ValueError):
        return 0, "?"
    if up >= 55.0 and up > dn:
        return 1, f"up{up:.0f}"
    if dn >= 55.0 and dn > up:
        return -1, f"dn{dn:.0f}"
    return 0, f"flat{up:.0f}/{dn:.0f}"


def _vote_sidecar(raw: dict[str, Any]) -> tuple[int, str]:
    b = raw.get("bias")
    if not isinstance(b, str):
        return 0, "?"
    bl = b.lower().strip()
    if bl == "long":
        return 1, "long"
    if bl == "short":
        return -1, "short"
    return 0, "neutral"


def _vote_ta(raw: dict[str, Any]) -> tuple[int, str]:
    try:
        sc = float(raw.get("ta_score") or 50.0)
    except (TypeError, ValueError):
        return 0, "?"
    if sc >= 55.0:
        return 1, f"s{sc:.0f}"
    if sc <= 45.0:
        return -1, f"s{sc:.0f}"
    return 0, f"s{sc:.0f}"


def vote_bybit_mainnet_from_row(
    row: dict[str, Any] | None,
    *,
    thr_pct: float,
) -> tuple[int, str]:
    """
    Map Bybit v5 ticker row to vote from **signed** 24h %% (``price24hPcnt`` is a decimal fraction
    in API responses; we convert to percent like ``update_movers.py``).
    """
    if not row:
        return 0, "unavailable"
    try:
        pfrac = float(row.get("price24hPcnt") or 0.0)
        pct = pfrac * 100.0
    except (TypeError, ValueError):
        return 0, "bad_pct"
    try:
        lp = float(row.get("lastPrice") or 0.0)
    except (TypeError, ValueError):
        lp = 0.0
    try:
        fr = float(row.get("fundingRate") or 0.0) * 100.0
    except (TypeError, ValueError):
        fr = 0.0
    t = max(0.01, float(thr_pct))
    if pct >= t:
        v = 1
    elif pct <= -t:
        v = -1
    else:
        v = 0
    detail = f"24h{pct:+.2f}%|px{lp:.0f}|f{fr:.4f}%"
    return v, detail[:100]


def fetch_bybit_mainnet_ticker_row(
    *,
    category: str,
    symbol: str,
    timeout_sec: float,
    cache_sec: float,
) -> dict[str, Any] | None:
    """Public mainnet HTTPS only; no auth. Cached per (category, symbol)."""
    cat = (category or "linear").strip().lower()
    if cat not in ("linear", "spot"):
        cat = "linear"
    sym = (symbol or "BTCUSDT").upper().strip() or "BTCUSDT"
    key = f"{cat}:{sym}"
    now = time.time()
    ent = _BYBIT_TICKER_CACHE.get(key)
    ttl = max(5.0, float(cache_sec))
    if ent is not None and now - ent[0] < ttl:
        return ent[1]

    q = urllib.parse.urlencode({"category": cat, "symbol": sym})
    url = f"{BYBIT_MAINNET_API}?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "SYGNIF-swarm-knowledge/1"})
    row_out: dict[str, Any] | None = None
    try:
        with urllib.request.urlopen(req, timeout=max(1.0, float(timeout_sec))) as r:
            data = json.loads(r.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        _BYBIT_TICKER_CACHE[key] = (now, None)
        return None
    if data.get("retCode") != 0:
        _BYBIT_TICKER_CACHE[key] = (now, None)
        return None
    rows = (data.get("result") or {}).get("list") or []
    if rows and isinstance(rows[0], dict):
        row_out = rows[0]
    _BYBIT_TICKER_CACHE[key] = (now, row_out)
    return row_out


def vote_account_position_from_response(resp: dict[str, Any] | None) -> tuple[int, str]:
    """Map Bybit ``/v5/position/list`` JSON to {-1,0,+1} from first non-zero linear leg."""
    if resp is None:
        return 0, "no_creds"
    if resp.get("retCode") != 0:
        rc = resp.get("retCode")
        return 0, f"err{rc}"
    rows = (resp.get("result") or {}).get("list") or []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            sz = abs(float(r.get("size") or 0.0))
        except (TypeError, ValueError):
            continue
        if sz < 1e-12:
            continue
        side = str(r.get("side") or "").strip().upper()
        if side == "BUY":
            return 1, "posL"
        if side == "SELL":
            return -1, "posS"
        return 0, "pos?"
    return 0, "flat"


# Subset of Bybit v5 linear position row (TP/SL/size/PnL) — always embedded under ``btc_future.position``.
_LINEAR_POSITION_SNAPSHOT_KEYS: tuple[str, ...] = (
    "symbol",
    "side",
    "size",
    "leverage",
    "avgPrice",
    "markPrice",
    "liqPrice",
    "breakEvenPrice",
    "takeProfit",
    "stopLoss",
    "trailingStop",
    "tpslMode",
    "unrealisedPnl",
    "cumRealisedPnl",
    "curRealisedPnl",
    "positionValue",
    "positionStatus",
    "positionIdx",
    "riskLimitValue",
    "adlRankIndicator",
)


def linear_position_snapshot_from_response(resp: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Extract one **open** linear leg from ``/v5/position/list`` for UI/Swarm/fusion.

    Returns ``{"flat": true}`` when no position; ``None`` when response missing/error.
    """
    if resp is None:
        return None
    if resp.get("retCode") != 0:
        return None
    rows = (resp.get("result") or {}).get("list") or []
    if not rows:
        return {"flat": True, "open": False}
    chosen: dict[str, Any] | None = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            sz = abs(float(r.get("size") or 0.0))
        except (TypeError, ValueError):
            continue
        if sz >= 1e-12:
            chosen = r
            break
    if chosen is None:
        return {"flat": True, "open": False}
    out: dict[str, Any] = {"flat": False, "open": True}
    for k in _LINEAR_POSITION_SNAPSHOT_KEYS:
        if k in chosen and chosen[k] is not None:
            out[k] = chosen[k]
    return out


def fetch_mainnet_linear_position_list(
    symbol: str,
    *,
    cache_sec: float,
) -> dict[str, Any] | None:
    """
    Signed **mainnet** ``GET /v5/position/list`` (read-only). Uses ``BYBIT_API_*`` only
    (not demo keys). No orders.
    """
    key = os.environ.get("BYBIT_API_KEY", "").strip()
    sec = os.environ.get("BYBIT_API_SECRET", "").strip()
    if not key or not sec:
        return None
    sym = (symbol or "BTCUSDT").upper().strip() or "BTCUSDT"
    ck = f"acct:{sym}"
    now = time.time()
    ttl = max(15.0, float(cache_sec))
    ent = _BYBIT_ACCOUNT_CACHE.get(ck)
    if ent is not None and now - ent[0] < ttl:
        return ent[1]

    td = _repo_root() / "trade_overseer"
    tds = str(td)
    if tds not in sys.path:
        sys.path.insert(0, tds)
    try:
        import bybit_linear_hedge as blh  # noqa: PLC0415
    except ImportError:
        _BYBIT_ACCOUNT_CACHE[ck] = (now, None)
        return None

    resp = blh._get_with_creds(
        "/v5/position/list",
        {"category": "linear", "symbol": sym},
        key,
        sec,
        "https://api.bybit.com",
    )
    _BYBIT_ACCOUNT_CACHE[ck] = (now, resp)
    return resp


def fetch_mainnet_wallet_balance_usdt(*, cache_sec: float) -> dict[str, Any] | None:
    """Signed **mainnet** ``GET /v5/account/wallet-balance`` (UNIFIED, coin USDT). Read-only."""
    key = os.environ.get("BYBIT_API_KEY", "").strip()
    sec = os.environ.get("BYBIT_API_SECRET", "").strip()
    if not key or not sec:
        return None
    ck = "wallet:USDT"
    now = time.time()
    ttl = max(15.0, float(cache_sec))
    ent = _BYBIT_WALLET_CACHE.get(ck)
    if ent is not None and now - ent[0] < ttl:
        return ent[1]

    td = _repo_root() / "trade_overseer"
    tds = str(td)
    if tds not in sys.path:
        sys.path.insert(0, tds)
    try:
        import bybit_linear_hedge as blh  # noqa: PLC0415
    except ImportError:
        _BYBIT_WALLET_CACHE[ck] = (now, None)
        return None

    resp = blh._get_with_creds(
        "/v5/account/wallet-balance",
        {"accountType": "UNIFIED", "coin": "USDT"},
        key,
        sec,
        "https://api.bybit.com",
    )
    _BYBIT_WALLET_CACHE[ck] = (now, resp)
    return resp


def fetch_demo_linear_position_list(
    symbol: str,
    *,
    cache_sec: float,
) -> dict[str, Any] | None:
    """
    Signed **Bybit API demo** ``GET /v5/position/list`` (USDT linear) via ``bybit_linear_hedge``.

    Uses ``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET`` on ``api-demo.bybit.com`` unless
    ``OVERSEER_BYBIT_HEDGE_MAINNET`` + ``OVERSEER_HEDGE_LIVE_OK`` force mainnet (same as hedge module).
    Read-only; no orders.
    """
    sym = (symbol or "BTCUSDT").upper().strip() or "BTCUSDT"
    ck = f"demo_bf:{sym}"
    now = time.time()
    ttl = max(15.0, float(cache_sec))
    ent = _BYBIT_DEMO_BF_CACHE.get(ck)
    if ent is not None and now - ent[0] < ttl:
        return ent[1]

    td = _repo_root() / "trade_overseer"
    tds = str(td)
    if tds not in sys.path:
        sys.path.insert(0, tds)
    try:
        import bybit_linear_hedge as blh  # noqa: PLC0415
    except ImportError:
        _BYBIT_DEMO_BF_CACHE[ck] = (now, None)
        return None

    try:
        resp = blh.position_list(sym)
    except RuntimeError:
        _BYBIT_DEMO_BF_CACHE[ck] = (now, None)
        return None
    except OSError:
        _BYBIT_DEMO_BF_CACHE[ck] = (now, None)
        return None

    _BYBIT_DEMO_BF_CACHE[ck] = (now, resp)
    return resp if isinstance(resp, dict) else None


def _overseer_url() -> str:
    return (os.environ.get("OVERSEER_URL") or "http://127.0.0.1:8090").rstrip("/")


def _fetch_overseer_trades_json() -> dict[str, Any] | None:
    """GET trade-overseer ``/trades`` (open list + profit aggregates)."""
    try:
        url = f"{_overseer_url()}/trades"
        req = urllib.request.Request(url, headers={"User-Agent": "SYGNIF-swarm-knowledge/1"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError, TypeError):
        return None


def _open_trades_scope_files() -> list[tuple[str, str]]:
    """
    (filename, label) under ``user_data/`` for SQLite open-trade scan.

    Default **btc_docker**: BTC-only Docker DBs (see ``docker-compose.yml`` BTC_Strategy_0_1 + btc-spot).
    **all**: legacy multi-pair archives (``archived-main-traders`` stack).
    """
    raw = (os.environ.get("SYGNIF_SWARM_OPEN_TRADES_SCOPE") or "btc_docker").strip().lower()
    if raw in ("all", "legacy", "archive"):
        return (
            ("tradesv3.sqlite", "spot_archive"),
            ("tradesv3-futures.sqlite", "futures_archive"),
        )
    custom = (os.environ.get("SYGNIF_SWARM_OPEN_TRADES_SQLITE_FILES") or "").strip()
    if custom:
        parts = [p.strip() for p in custom.split(",") if p.strip()]
        return [(p, "custom") for p in parts]
    return (
        ("tradesv3-futures-btc01-demo.sqlite", "futures_btc01_demo"),
        ("tradesv3-btc-spot.sqlite", "btc_spot"),
    )


def _open_trades_btc_sql_clause() -> str:
    """Restrict to BTC linear/spot pair prefix (not WBTC)."""
    btc_only = os.environ.get("SYGNIF_SWARM_OPEN_TRADES_BTC_ONLY", "1").strip().lower()
    if btc_only in ("0", "false", "no", "off", "all"):
        return ""
    return " AND pair LIKE 'BTC/%'"


def _sqlite_open_trades_brief() -> dict[str, Any]:
    """Read-only summary from selected Freqtrade DBs under ``user_data/``."""
    ud = _repo_root() / "user_data"
    out: dict[str, Any] = {"ok": False, "dbs": [], "scope": (os.environ.get("SYGNIF_SWARM_OPEN_TRADES_SCOPE") or "btc_docker")}
    if not ud.is_dir():
        return out
    extra = _open_trades_btc_sql_clause()
    for fname, label in _open_trades_scope_files():
        p = ud / fname
        if not p.is_file():
            continue
        try:
            con = sqlite3.connect(str(p))
            cur = con.execute(f"SELECT COUNT(*) FROM trades WHERE is_open = 1{extra}")
            n = int(cur.fetchone()[0] or 0)
            cur = con.execute(
                f"SELECT pair, COALESCE(enter_tag,''), is_short FROM trades "
                f"WHERE is_open = 1{extra} ORDER BY id LIMIT 40"
            )
            rows = [
                {"pair": r[0], "enter_tag": r[1] or "", "is_short": bool(r[2])}
                for r in cur.fetchall()
            ]
            con.close()
            out["dbs"].append({"file": fname, "label": label, "open_n": n, "trades": rows})
        except (OSError, sqlite3.Error) as e:
            out["dbs"].append({"file": fname, "error": str(e)[:160]})
    out["ok"] = bool(out["dbs"])
    return out


def build_open_trades_report() -> dict[str, Any]:
    """
    Freqtrade open positions for Swarm JSON: overseer when up, else SQLite brief.

    No secrets; safe for ``swarm_knowledge_output.json``.
    """
    rep: dict[str, Any] = {"enabled": True}
    data = _fetch_overseer_trades_json()
    if data is not None and isinstance(data.get("trades"), list):
        trades = list(data["trades"])
        btc_only = os.environ.get("SYGNIF_SWARM_OPEN_TRADES_BTC_ONLY", "1").strip().lower()
        scope = (os.environ.get("SYGNIF_SWARM_OPEN_TRADES_SCOPE") or "btc_docker").strip().lower()
        if btc_only not in ("0", "false", "no", "off", "all") and scope not in ("all", "legacy", "archive"):
            trades = [t for t in trades if str(t.get("pair") or "").upper().startswith("BTC/")]
        rep["source"] = "overseer"
        rep["overseer_url"] = _overseer_url()
        rep["open_n"] = len(trades)
        rep["trades"] = trades[:60]
        rep["profits"] = data.get("profits") if isinstance(data.get("profits"), list) else []
        return rep
    sq = _sqlite_open_trades_brief()
    rep["source"] = "sqlite"
    rep["sqlite"] = sq
    rep["open_n"] = sum(int(d.get("open_n") or 0) for d in sq.get("dbs") or [])
    return rep


def _num_closed_scalar(val: Any) -> float | None:
    try:
        if val is None or val == "":
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _closed_ts_ms(row: dict[str, Any]) -> int:
    for k in ("createdTime", "updatedTime"):
        v = row.get(k)
        if v is None or v == "":
            continue
        try:
            return int(float(v))
        except (TypeError, ValueError):
            continue
    return 0


def _bybit_signed_venue_label() -> str:
    m = os.environ.get("OVERSEER_BYBIT_HEDGE_MAINNET", "").strip().lower() in ("1", "true", "yes", "on")
    live = os.environ.get("OVERSEER_HEDGE_LIVE_OK", "").strip().upper() == "YES"
    if m and live:
        return "mainnet"
    return "demo"


def _has_bybit_signed_creds() -> bool:
    """Match ``bybit_linear_hedge._credentials()`` routing (demo vs live mainnet)."""
    demo = bool(os.environ.get("BYBIT_DEMO_API_KEY", "").strip() and os.environ.get("BYBIT_DEMO_API_SECRET", "").strip())
    mn = bool(os.environ.get("BYBIT_API_KEY", "").strip() and os.environ.get("BYBIT_API_SECRET", "").strip())
    if _bybit_signed_venue_label() == "mainnet":
        return mn
    return demo


def build_bybit_closed_pnl_report() -> dict[str, Any]:
    """
    Signed **read-only** USDT-linear closed PnL history (``GET /v5/position/closed-pnl``).

    Same credential host as ``bybit_linear_hedge`` (demo ``api-demo`` vs mainnet ``api.bybit.com``).
    """
    if not _env_truthy("SYGNIF_SWARM_BYBIT_CLOSED_PNL"):
        return {"enabled": False}
    sym = (os.environ.get("SYGNIF_SWARM_BYBIT_CLOSED_PNL_SYMBOL") or "").strip().upper()
    if not sym:
        sym = (os.environ.get("SYGNIF_SWARM_BYBIT_SYMBOL", "BTCUSDT") or "BTCUSDT").strip().upper() or "BTCUSDT"
    max_rows = int(max(1, min(5000, _env_float("SYGNIF_SWARM_BYBIT_CLOSED_PNL_MAX_ROWS", 200))))
    max_list = int(max(1, min(500, _env_float("SYGNIF_SWARM_BYBIT_CLOSED_PNL_MAX_LIST", 50))))
    page_lim = int(max(1, min(100, _env_float("SYGNIF_SWARM_BYBIT_CLOSED_PNL_PAGE", 100))))
    cache_sec = max(15.0, _env_float("SYGNIF_SWARM_BYBIT_CLOSED_PNL_CACHE_SEC", 120))
    venue = _bybit_signed_venue_label()
    ck = f"closed_pnl:{venue}:{sym}:{max_rows}"
    now = time.time()
    cached = _BYBIT_CLOSED_PNL_CACHE.get(ck)
    if cached is not None and now - cached[0] < cache_sec:
        return cached[1]

    if not _has_bybit_signed_creds():
        rep = {
            "enabled": True,
            "ok": False,
            "venue": venue,
            "symbol": sym,
            "detail": "missing_bybit_credentials_for_venue",
        }
        _BYBIT_CLOSED_PNL_CACHE[ck] = (now, rep)
        return rep

    td = _repo_root() / "trade_overseer"
    tds = str(td)
    if tds not in sys.path:
        sys.path.insert(0, tds)
    try:
        import bybit_linear_hedge as blh  # noqa: PLC0415
    except ImportError:
        rep = {
            "enabled": True,
            "ok": False,
            "venue": venue,
            "symbol": sym,
            "detail": "bybit_linear_hedge_import_failed",
        }
        _BYBIT_CLOSED_PNL_CACHE[ck] = (now, rep)
        return rep

    rows_raw: list[dict[str, Any]] = []
    cursor = ""
    try:
        while len(rows_raw) < max_rows:
            r = blh.closed_pnl_linear(sym, limit=str(page_lim), cursor=cursor)
            if r.get("retCode") != 0:
                rep = {
                    "enabled": True,
                    "ok": False,
                    "venue": venue,
                    "symbol": sym,
                    "retCode": r.get("retCode"),
                    "retMsg": r.get("retMsg"),
                }
                _BYBIT_CLOSED_PNL_CACHE[ck] = (now, rep)
                return rep
            res = r.get("result") or {}
            batch = res.get("list") or []
            rows_raw.extend(batch)
            cursor = (res.get("nextPageCursor") or "").strip()
            if not cursor or not batch:
                break
    except RuntimeError as exc:
        rep = {"enabled": True, "ok": False, "venue": venue, "symbol": sym, "detail": str(exc)[:200]}
        _BYBIT_CLOSED_PNL_CACHE[ck] = (now, rep)
        return rep

    parsed: list[dict[str, Any]] = []
    for row in rows_raw[:max_rows]:
        if not isinstance(row, dict):
            continue
        ts = _closed_ts_ms(row)
        pnl = _num_closed_scalar(row.get("closedPnl"))
        parsed.append(
            {
                "created_ms": ts,
                "closed_pnl": pnl,
                "side": str(row.get("side") or ""),
                "qty": _num_closed_scalar(row.get("closedSize") or row.get("qty")),
                "avg_entry": _num_closed_scalar(row.get("avgEntryPrice")),
                "avg_exit": _num_closed_scalar(row.get("avgExitPrice")),
                "order_id": str(row.get("orderId") or "").strip(),
            }
        )
    parsed.sort(key=lambda x: x["created_ms"])
    wins = sum(1 for x in parsed if (x.get("closed_pnl") or 0) > 1e-9)
    losses = sum(1 for x in parsed if (x.get("closed_pnl") or 0) < -1e-9)
    total = sum(float(x.get("closed_pnl") or 0) for x in parsed)
    recent = parsed[-max_list:] if len(parsed) > max_list else parsed
    rep = {
        "enabled": True,
        "ok": True,
        "venue": venue,
        "symbol": sym,
        "n_closed": len(parsed),
        "sum_closed_pnl_usdt": round(total, 6),
        "wins": wins,
        "losses": losses,
        "recent": recent,
    }
    _BYBIT_CLOSED_PNL_CACHE[ck] = (now, rep)
    return rep


def _bybit_open_pnl_enabled() -> bool:
    """Default **on** unless explicitly disabled."""
    raw = (os.environ.get("SYGNIF_SWARM_BYBIT_OPEN_PNL") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def _unrealised_usdt_from_snap(snap: dict[str, Any]) -> tuple[float | None, bool | None]:
    """
    Parse ``unrealisedPnl`` from ``linear_position_snapshot_from_response`` output.

    Returns ``(unrealised_usdt, is_flat)``. ``is_flat`` is ``True`` when no open size; ``None`` for unknown.
    """
    if snap.get("flat"):
        return 0.0, True
    raw = snap.get("unrealisedPnl")
    try:
        return float(raw), False
    except (TypeError, ValueError):
        return None, False


def build_bybit_open_pnl_report(
    *,
    btc_future_meta: dict[str, Any],
    account_meta: dict[str, Any],
    resp_ac: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    **Open** (unrealised) USDT P/L from **existing** linear ``position/list`` snapshots — no extra HTTP calls.

    ``demo`` uses ``btc_future_meta["position"]`` (when ``SYGNIF_SWARM_BTC_FUTURE=1``).
    ``mainnet`` uses ``resp_ac`` when ``SYGNIF_SWARM_BYBIT_ACCOUNT`` or admin tier.
    """
    if not _bybit_open_pnl_enabled():
        return {"enabled": False}
    rep: dict[str, Any] = {"enabled": True, "venues": {}}
    sums: list[float] = []

    # --- demo (Bybit API demo linear) ---
    ven_d: dict[str, Any] = {"venue": "demo"}
    pos_bf = btc_future_meta.get("position") if isinstance(btc_future_meta.get("position"), dict) else None
    if btc_future_meta.get("enabled"):
        ven_d["symbol"] = btc_future_meta.get("symbol")
        ven_d["ok"] = bool(btc_future_meta.get("ok"))
        if pos_bf is not None:
            u, is_flat = _unrealised_usdt_from_snap(pos_bf)
            ven_d["flat"] = is_flat
            if u is not None:
                ven_d["unrealised_pnl_usdt"] = round(u, 6)
                sums.append(u)
        else:
            ven_d["detail"] = "no_position_snapshot"
    else:
        ven_d["skipped"] = True
        ven_d["reason"] = "SYGNIF_SWARM_BTC_FUTURE_off"
    rep["venues"]["demo"] = ven_d

    # --- mainnet (signed ``ac``) ---
    ven_m: dict[str, Any] = {"venue": "mainnet"}
    if account_meta.get("enabled"):
        ven_m["symbol"] = account_meta.get("symbol")
        ven_m["ok"] = bool(account_meta.get("ok"))
        snap_ac = linear_position_snapshot_from_response(resp_ac) if resp_ac is not None else None
        if snap_ac is not None:
            u, is_flat = _unrealised_usdt_from_snap(snap_ac)
            ven_m["flat"] = is_flat
            if u is not None:
                ven_m["unrealised_pnl_usdt"] = round(u, 6)
                sums.append(u)
        else:
            ven_m["detail"] = "no_position_snapshot"
    else:
        ven_m["skipped"] = True
        ven_m["reason"] = "signed_mainnet_position_off"
    rep["venues"]["mainnet"] = ven_m

    if sums:
        rep["sum_unrealised_pnl_usdt"] = round(sum(sums), 6)
    return rep


def _try_fetch_demo_keys_for_swarm() -> None:
    """Populate BYBIT_DEMO_* from optional HTTPS webhook (see swarm_demo_keys_fetch)."""
    try:
        import swarm_demo_keys_fetch as _sdk  # noqa: PLC0415
    except ImportError:
        try:
            from finance_agent import swarm_demo_keys_fetch as _sdk  # noqa: PLC0415
        except ImportError:
            return
    _sdk.ensure_demo_keys_from_webhook()


def compute_swarm(
    *,
    pred_path: Path | None = None,
    train_path: Path | None = None,
    sidecar_path: Path | None = None,
    ta_path: Path | None = None,
) -> dict[str, Any]:
    _try_fetch_demo_keys_for_swarm()
    pred_path = pred_path or (_prediction_agent_dir() / "btc_prediction_output.json")
    train_path = train_path or (_prediction_agent_dir() / "training_channel_output.json")
    sidecar_path = sidecar_path or (_btc_data_dir() / "nautilus_strategy_signal.json")
    ta_path = ta_path or (_btc_data_dir() / "btc_sygnif_ta_snapshot.json")

    votes: list[tuple[str, int, str]] = []
    missing: list[str] = []

    if pred_path.is_file():
        try:
            pred = json.loads(pred_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pred = {}
        v, d = _vote_ml_enhanced(pred if isinstance(pred, dict) else {})
        votes.append(("ml", v, d))
    else:
        missing.append("btc_prediction_output.json")

    if train_path.is_file():
        try:
            train = json.loads(train_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            train = {}
        rec = train.get("recognition") if isinstance(train.get("recognition"), dict) else {}
        v, d = _vote_channel(rec)
        votes.append(("ch", v, d))
    else:
        missing.append("training_channel_output.json")

    if sidecar_path.is_file():
        try:
            sc = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            sc = {}
        v, d = _vote_sidecar(sc if isinstance(sc, dict) else {})
        votes.append(("sc", v, d))
    else:
        missing.append("nautilus_strategy_signal.json")

    if ta_path.is_file():
        try:
            ta = json.loads(ta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ta = {}
        v, d = _vote_ta(ta if isinstance(ta, dict) else {})
        votes.append(("ta", v, d))
    else:
        missing.append("btc_sygnif_ta_snapshot.json")

    explore_doc: dict[str, Any] = {}
    try:
        from finance_agent.truthcoin_hivemind_swarm_core import hivemind_explore_needed as _hivemind_needed
    except Exception:
        _hivemind_needed = lambda: False  # type: ignore[assignment, misc]
    if _hivemind_needed():
        try:
            from finance_agent.truthcoin_dc_swarm_bridge import hivemind_explore_snapshot

            explore_doc = hivemind_explore_snapshot()
        except Exception as exc:
            explore_doc = {"enabled": True, "ok": False, "detail": f"hivemind_prefetch:{exc!r}"}

    bybit_meta: dict[str, Any] = {"enabled": False}
    if _env_truthy("SYGNIF_SWARM_BYBIT_MAINNET"):
        sym = os.environ.get("SYGNIF_SWARM_BYBIT_SYMBOL", "BTCUSDT").strip().upper() or "BTCUSDT"
        cat = os.environ.get("SYGNIF_SWARM_BYBIT_CATEGORY", "linear").strip().lower() or "linear"
        thr = _env_float("SYGNIF_SWARM_BYBIT_24H_PCT_THR", 0.25)
        to = _env_float("SYGNIF_SWARM_BYBIT_TIMEOUT_SEC", 6.0)
        cache_ttl = _env_float("SYGNIF_SWARM_BYBIT_CACHE_SEC", 45.0)
        bybit_meta = {
            "enabled": True,
            "base": "https://api.bybit.com",
            "category": cat,
            "symbol": sym,
            "thr_pct_24h": thr,
        }
        row = fetch_bybit_mainnet_ticker_row(
            category=cat,
            symbol=sym,
            timeout_sec=to,
            cache_sec=cache_ttl,
        )
        v_mn, d_mn = vote_bybit_mainnet_from_row(row, thr_pct=thr)
        votes.append(("mn", v_mn, d_mn))
        bybit_meta["ok"] = row is not None

    account_meta: dict[str, Any] = {"enabled": False}
    wallet_meta: dict[str, Any] = {"enabled": False}
    resp_ac_main: dict[str, Any] | None = None
    if _include_signed_position():
        sym_ac = os.environ.get("SYGNIF_SWARM_BYBIT_SYMBOL", "BTCUSDT").strip().upper() or "BTCUSDT"
        ac_ttl = _env_float("SYGNIF_SWARM_BYBIT_ACCOUNT_CACHE_SEC", 60.0)
        account_meta = {
            "enabled": True,
            "mainnet": True,
            "symbol": sym_ac,
            "admin_tier": _admin_tier_enabled(),
            "has_mainnet_keys": bool(
                os.environ.get("BYBIT_API_KEY", "").strip()
                and os.environ.get("BYBIT_API_SECRET", "").strip()
            ),
        }
        resp_ac = fetch_mainnet_linear_position_list(sym_ac, cache_sec=ac_ttl)
        resp_ac_main = resp_ac
        v_ac, d_ac = vote_account_position_from_response(resp_ac)
        votes.append(("ac", v_ac, d_ac))
        account_meta["ok"] = (
            resp_ac is not None
            and resp_ac.get("retCode") == 0
            and account_meta["has_mainnet_keys"]
        )

    btc_future_meta: dict[str, Any] = {"enabled": False}
    if _env_truthy("SYGNIF_SWARM_BTC_FUTURE"):
        sym_bf = os.environ.get("SYGNIF_SWARM_BTC_FUTURE_SYMBOL", "BTCUSDT").strip().upper() or "BTCUSDT"
        bf_ttl = _env_float("SYGNIF_SWARM_BTC_FUTURE_CACHE_SEC", 60.0)
        has_demo = bool(
            os.environ.get("BYBIT_DEMO_API_KEY", "").strip()
            and os.environ.get("BYBIT_DEMO_API_SECRET", "").strip()
        )
        btc_future_meta = {
            "enabled": True,
            "profile": "btc_future",
            "demo": True,
            "symbol": sym_bf,
            "has_demo_keys": has_demo,
        }
        if has_demo and _env_truthy("SYGNIF_SWARM_PRINT_DEMO_API_KEY_HINT"):
            kdemo = os.environ.get("BYBIT_DEMO_API_KEY", "").strip()
            if kdemo:
                btc_future_meta["demo_api_key_hint"] = _masked_api_key_hint(kdemo)
        if not has_demo:
            votes.append(("bf", 0, "no_demo_creds"))
            btc_future_meta["ok"] = False
        else:
            resp_bf = fetch_demo_linear_position_list(sym_bf, cache_sec=bf_ttl)
            v_bf, d_bf = vote_account_position_from_response(resp_bf)
            votes.append(("bf", v_bf, d_bf))
            btc_future_meta["ok"] = (
                resp_bf is not None
                and resp_bf.get("retCode") == 0
                and has_demo
            )
            snap = linear_position_snapshot_from_response(resp_bf)
            if snap is not None:
                btc_future_meta["position"] = snap
        if explore_doc:
            btc_future_meta["hivemind_explore"] = explore_doc

    if _admin_tier_enabled():
        wb_ttl = _env_float("SYGNIF_SWARM_WALLET_CACHE_SEC", 60.0)
        step = _env_float("SYGNIF_SWARM_WALLET_ROUND_USDT", 1000.0)
        wallet_meta = {
            "enabled": True,
            "mainnet": True,
            "admin_tier": True,
            "has_mainnet_keys": bool(
                os.environ.get("BYBIT_API_KEY", "").strip()
                and os.environ.get("BYBIT_API_SECRET", "").strip()
            ),
            "round_usdt": int(max(1.0, step)),
        }
        resp_wb = fetch_mainnet_wallet_balance_usdt(cache_sec=wb_ttl)
        avail = _parse_usdt_available_wallet(resp_wb) if resp_wb else None
        wallet_meta["ok"] = (
            resp_wb is not None
            and resp_wb.get("retCode") == 0
            and wallet_meta["has_mainnet_keys"]
        )
        wallet_meta["usdt_available_briefing"] = wallet_usdt_band_label(avail, step=step)

    try:
        from finance_agent.truthcoin_hivemind_swarm_core import (  # noqa: PLC0415
            hivemind_explore_needed,
            swarm_core_engine,
            vote_hivemind_from_explore,
        )

        if hivemind_explore_needed() and (
            _env_truthy("SYGNIF_SWARM_HIVEMIND_VOTE") or swarm_core_engine() == "hivemind"
        ):
            v_hm, d_hm = vote_hivemind_from_explore(explore_doc)
            votes.append(("hm", v_hm, d_hm))
    except Exception:
        pass

    n = len(votes)
    vote_ints = [v for _, v, _ in votes]
    use_pt = _env_truthy("SYGNIF_SWARM_PYTORCH")
    if use_pt:
        try:
            fad = str(_finance_agent_dir())
            if fad not in sys.path:
                sys.path.insert(0, fad)
            import swarm_pytorch_fusion as _pt  # noqa: PLC0415

            if _pt.torch_available():
                stats = _pt.aggregate_vote_stats(vote_ints)
                mean = stats["mean"]
                label = stats["label"]
                conflict = stats["conflict"]
                engine = "pytorch"
                engine_detail = stats.get("engine_detail", "pytorch")
            else:
                mean = sum(vote_ints) / n if n else 0.0
                if mean > 0.25:
                    label = "SWARM_BULL"
                elif mean < -0.25:
                    label = "SWARM_BEAR"
                else:
                    label = "SWARM_MIXED"
                active = [v for v in vote_ints if v != 0]
                spread = (max(active) - min(active)) if len(active) >= 2 else 0
                conflict = spread >= 2
                engine = "python"
                engine_detail = "torch_missing_fallback"
        except Exception:
            mean = sum(vote_ints) / n if n else 0.0
            if mean > 0.25:
                label = "SWARM_BULL"
            elif mean < -0.25:
                label = "SWARM_BEAR"
            else:
                label = "SWARM_MIXED"
            active = [v for v in vote_ints if v != 0]
            spread = (max(active) - min(active)) if len(active) >= 2 else 0
            conflict = spread >= 2
            engine = "python"
            engine_detail = "pytorch_error_fallback"
    else:
        mean = sum(vote_ints) / n if n else 0.0
        if mean > 0.25:
            label = "SWARM_BULL"
        elif mean < -0.25:
            label = "SWARM_BEAR"
        else:
            label = "SWARM_MIXED"
        active = [v for v in vote_ints if v != 0]
        spread = (max(active) - min(active)) if len(active) >= 2 else 0
        conflict = spread >= 2
        engine = "python"
        engine_detail = "python_mean"

    try:
        from finance_agent.truthcoin_hivemind_swarm_core import (  # noqa: PLC0415
            swarm_core_engine as _swarm_core_engine,
            vote_hivemind_from_explore as _vote_hivemind_from_explore,
        )

        _core = _swarm_core_engine()
        if _core == "hivemind" and isinstance(explore_doc, dict) and explore_doc.get("ok"):
            v_hm, _d_hm = _vote_hivemind_from_explore(explore_doc)
            mean = float(v_hm)
            if mean > 0.25:
                label = "SWARM_BULL"
            elif mean < -0.25:
                label = "SWARM_BEAR"
            else:
                label = "SWARM_MIXED"
            conflict = False
            engine = "hivemind"
            engine_detail = "truthcoin_dc_hivemind_core"
        elif _core == "hivemind":
            engine_detail = f"{engine_detail}+truthcoin_dc_unreachable"
    except Exception:
        pass

    out: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "swarm_mean": round(mean, 4),
        "swarm_label": label,
        "swarm_conflict": conflict,
        "swarm_engine": engine,
        "swarm_engine_detail": engine_detail,
        "sources": {name: {"vote": v, "detail": d} for name, v, d in votes},
        "sources_n": n,
        "missing_files": missing,
    }
    try:
        from finance_agent.truthcoin_hivemind_swarm_core import (  # noqa: PLC0415
            build_processing_roots_manifest,
            swarm_core_engine as _core_engine_out,
        )

        out["swarm_core_engine"] = _core_engine_out()
        pr = build_processing_roots_manifest()
        if pr:
            out["swarm_processing_roots"] = pr
    except Exception:
        pass
    try:
        if explore_doc and _hivemind_needed():
            out["hivemind_explore"] = explore_doc
    except Exception:
        pass
    if bybit_meta.get("enabled"):
        out["bybit_mainnet"] = bybit_meta
    if account_meta.get("enabled"):
        out["bybit_account"] = account_meta
    if btc_future_meta.get("enabled"):
        out["btc_future"] = btc_future_meta
    if wallet_meta.get("enabled"):
        out["bybit_wallet"] = wallet_meta
    if os.environ.get("SYGNIF_SWARM_OPEN_TRADES", "1").strip().lower() not in ("0", "false", "no", "off"):
        try:
            out["open_trades"] = build_open_trades_report()
        except Exception:
            out["open_trades"] = {"enabled": True, "source": "error", "detail": "build_open_trades_report_failed"}
    if _env_truthy("SYGNIF_SWARM_BYBIT_CLOSED_PNL"):
        try:
            out["bybit_closed_pnl"] = build_bybit_closed_pnl_report()
        except Exception:
            out["bybit_closed_pnl"] = {"enabled": True, "ok": False, "detail": "build_bybit_closed_pnl_report_failed"}
    if _bybit_open_pnl_enabled():
        try:
            out["bybit_open_pnl"] = build_bybit_open_pnl_report(
                btc_future_meta=btc_future_meta,
                account_meta=account_meta,
                resp_ac=resp_ac_main,
            )
        except Exception:
            out["bybit_open_pnl"] = {"enabled": True, "ok": False, "detail": "build_bybit_open_pnl_report_failed"}
    return out


def briefing_line_swarm(*, max_chars: int = 120) -> str:
    if os.environ.get("SYGNIF_BRIEFING_INCLUDE_SWARM", "").lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return ""
    sk = compute_swarm()
    parts = sk["sources"]
    ml = parts.get("ml", {})
    line = (
        f"BTC_SWARM|mean={sk['swarm_mean']:+.2f}|{sk['swarm_label']}|"
        f"ml={ml.get('detail', '?')}|"
        f"ch={parts.get('ch', {}).get('detail', '?')}|"
        f"sc={parts.get('sc', {}).get('detail', '?')}|"
        f"ta={parts.get('ta', {}).get('detail', '?')}"
    )
    if "mn" in parts:
        line += f"|mn={parts['mn'].get('detail', '?')}"
    if "ac" in parts:
        line += f"|ac={parts['ac'].get('detail', '?')}"
    if "bf" in parts:
        line += f"|bf={parts['bf'].get('detail', '?')}"
    if "hm" in parts:
        line += f"|hm={parts['hm'].get('detail', '?')}"
    bw = sk.get("bybit_wallet") if isinstance(sk.get("bybit_wallet"), dict) else {}
    if bw.get("enabled") and bw.get("usdt_available_briefing"):
        line += f"|wb={bw.get('usdt_available_briefing')}"
    if sk.get("swarm_conflict"):
        line += "|CONFLICT"
    ot = sk.get("open_trades") if isinstance(sk.get("open_trades"), dict) else {}
    if ot.get("source") and ot.get("source") != "error":
        try:
            line += f"|ot={int(ot.get('open_n') or 0)}"
        except (TypeError, ValueError):
            pass
    cp = sk.get("bybit_closed_pnl") if isinstance(sk.get("bybit_closed_pnl"), dict) else {}
    if cp.get("ok"):
        try:
            line += f"|cpnl={float(cp.get('sum_closed_pnl_usdt') or 0):+.0f}n{int(cp.get('n_closed') or 0)}"
        except (TypeError, ValueError):
            pass
    op = sk.get("bybit_open_pnl") if isinstance(sk.get("bybit_open_pnl"), dict) else {}
    if op.get("enabled") and op.get("sum_unrealised_pnl_usdt") is not None:
        try:
            line += f"|upnl={float(op['sum_unrealised_pnl_usdt']):+.1f}"
        except (TypeError, ValueError):
            pass
    if len(line) > max_chars:
        line = line[: max_chars - 3] + "..."
    return line


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute swarm_knowledge JSON from Sygnif BTC sidecars.")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON (default: PREDICTION_AGENT_DIR/swarm_knowledge_output.json)",
    )
    ap.add_argument(
        "--sealed-out",
        type=Path,
        default=None,
        help="Write Fernet envelope JSON (default: PREDICTION_AGENT_DIR/swarm_knowledge_sealed.json)",
    )
    ap.add_argument("--print-json", action="store_true", help="Print JSON to stdout")
    args = ap.parse_args()
    out = compute_swarm()
    if args.print_json:
        print(json.dumps(out, indent=2))
    dest = args.out
    if dest is None:
        dest = _prediction_agent_dir() / "swarm_knowledge_output.json"
    sealed_dest = args.sealed_out
    if sealed_dest is None:
        sealed_dest = _prediction_agent_dir() / "swarm_knowledge_sealed.json"

    out_mode = os.environ.get("SYGNIF_SWARM_OUTPUT", "plaintext").strip().lower()
    if out_mode not in ("plaintext", "sealed", "both"):
        out_mode = "plaintext"

    key_set = bool(os.environ.get("SYGNIF_SWARM_FERNET_KEY", "").strip())
    write_plain = out_mode in ("plaintext", "both") or not key_set
    write_sealed = out_mode in ("sealed", "both") and key_set

    if write_plain:
        try:
            dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
            print(f"[swarm] wrote {dest}", flush=True)
        except OSError as exc:
            print(f"[swarm] write failed: {exc}", flush=True)
            return 1

    if write_sealed:
        try:
            from finance_agent import swarm_crypto as sc  # noqa: PLC0415

            tok = sc.seal_swarm_dict(out)
            env = sc.wrap_sealed_envelope(tok)
            sealed_dest.write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
            print(f"[swarm] sealed {sealed_dest}", flush=True)
        except Exception as exc:
            print(f"[swarm] seal failed: {exc}", flush=True)
            return 1
    elif out_mode == "sealed" and not key_set:
        print("[swarm] SYGNIF_SWARM_OUTPUT=sealed but SYGNIF_SWARM_FERNET_KEY missing", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
