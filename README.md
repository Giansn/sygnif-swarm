# Sygnif Swarm

Reproducible **BTC Prediction** + **Swarm** bundle (Bybit demo, optional Truthcoin Hivemind). See [`BTC_Prediction/README.md`](BTC_Prediction/README.md).

## Quick reproduce

```bash
git clone https://github.com/Giansn/sygnif-swarm.git
cd sygnif-swarm
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp BTC_Prediction/.env.example BTC_Prediction/.env
chmod +x tools/env.sh
source tools/env.sh
cd "$SYGNIF_REPO_ROOT"
python3 scripts/swarm_auto_predict_protocol_loop.py --help
python3 scripts/btc_predict_protocol_loop.py
```

Live trading still needs `SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES`, valid `BYBIT_DEMO_*`, and `--execute` on the loop scripts.

## NeuroLinked (optional)

The bundle includes **NeuroLinked** (`BTC_Prediction/third_party/neurolinked/`), the **Bybit market → NeuroLinked** script (`BTC_Prediction/scripts/bybit_nl_market_feed.py`), and **systemd unit templates** (`BTC_Prediction/deploy/systemd/*.service.in`). Install for **any clone path** with **`BTC_Prediction/deploy/install_systemd_units.sh`** (see [`BTC_Prediction/docs/NEUROLINKED_SYSTEMD.md`](BTC_Prediction/docs/NEUROLINKED_SYSTEMD.md)).

## Docker network

`BTC_Prediction/network/docker-compose.sygnif-network.yml` — external network `sygnif_network` (override with `SYGNIF_EXTERNAL_NETWORK_NAME`).

## Disaster recovery (GitHub + off-repo backup)

GitHub is a **source backup**: clone + install reproduces *software and layout*. **Secrets and live state** must exist in a second place (password manager, S3 snapshot, encrypted USB, etc.).

### 1. Back up outside Git (before you need it)

| Item | Typical path (bundle) | Notes |
|------|------------------------|--------|
| Bybit / API secrets | `BTC_Prediction/.env` | Copy from `BTC_Prediction/.env.example`; never commit real keys. |
| Swarm / loop ACK + demo | `BTC_Prediction/swarm_operator.env` | From `swarm_operator.env.example`; includes `SYGNIF_PREDICT_PROTOCOL_LOOP_ACK`, `BYBIT_DEMO_*`. |
| NeuroLinked tuning | `BTC_Prediction/neurolinked.service.env` | From `neurolinked.service.env.example`. |
| Optional: journals / ML state | `prediction_agent/*.jsonl`, large JSON, `third_party/neurolinked/brain_state/` | Only if you need historical continuity; Git may omit or shrink these by policy. |
| Optional: overseer state | `trade_overseer/data/` | Machine-local; back up if you rely on it. |

### 2. After total loss (order of operations)

1. **Clone** this repo to the target path you will use in production.
2. **Python**: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. **Restore secrets** into `BTC_Prediction/.env`, `swarm_operator.env`, `neurolinked.service.env` (from your secure backup, not from Git).
4. **Paths**: set `SYGNIF_REPO_ROOT` to the absolute path of **`BTC_Prediction`** (see `BTC_Prediction/.env.example`). Run `chmod +x tools/env.sh && source tools/env.sh` from repo root.
5. **Optional data**: copy any backed-up `prediction_agent/` / `brain_state/` / `trade_overseer/data/` files into the same relative locations.
6. **NeuroLinked + loops (optional)**: install systemd units — `BTC_Prediction/deploy/install_systemd_units.sh` and [`BTC_Prediction/docs/NEUROLINKED_SYSTEMD.md`](BTC_Prediction/docs/NEUROLINKED_SYSTEMD.md); then `sudo systemctl daemon-reload` and enable/start the units you use.
7. **Truthcoin / Bee / other URLs**: restore whatever you had in `.env` (`SYGNIF_TRUTHCOIN_*`, `BEE_URL`, etc.); Git only documents names, not values.

### 3. Smoke checks

```bash
source .venv/bin/activate && source tools/env.sh && cd "$SYGNIF_REPO_ROOT"
python3 scripts/swarm_auto_predict_protocol_loop.py --help
curl -sS --max-time 5 http://127.0.0.1:8889/healthz   # if NeuroLinked is up
```

Live orders still require explicit loop flags (e.g. `SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES`, `--execute`) — same as on the primary host.

## Upstream

Extracted from the Sygnif monorepo; full strategy stack lives there separately.
