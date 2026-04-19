# NeuroLinked + Bybit feed + systemd (sygnif-swarm)

This bundle ships **NeuroLinked** under `third_party/neurolinked/` (dashboard + HTTP API on **8889** by default), a **Bybit mainnet market → NeuroLinked** poller (`scripts/bybit_nl_market_feed.py`), and **systemd unit templates** under `deploy/systemd/`.

## Layout

- Clone this repository as `~/sygnif-swarm` (or edit the unit files: they use `%h/sygnif-swarm/...`).
- Python venv at **`~/sygnif-swarm/.venv`** (repo root), with `pip install -r requirements.txt` from the clone root.
- Code + env live in **`~/sygnif-swarm/BTC_Prediction/`** (`SYGNIF_REPO_ROOT` in `tools/env.sh`).

## Env files

| File | Purpose |
|------|---------|
| `BTC_Prediction/.env` | Bybit keys, optional Anthropic, etc. (copy from `.env.example`). |
| `BTC_Prediction/swarm_operator.env` | Operator overrides for Swarm + predict loop (copy from `swarm_operator.env.example`). |
| `BTC_Prediction/neurolinked.service.env` | Optional NeuroLinked tuning (copy from `neurolinked.service.env.example`). |

Useful knobs (see examples for full list):

- **`SYGNIF_NEUROLINKED_HTTP_TIMEOUT_SEC`** — predict-loop POST to NeuroLinked (default in hook: 15s; raise under disk I/O).
- **`BYBIT_NL_POST_TIMEOUT_SEC`** — Bybit feed POST timeout (default 25s in script).
- **`SYGNIF_NEUROLINKED_SIM_TARGET_HZ`** — lower simulation Hz if the HTTP stack stalls (GIL / uvicorn).
- **`SYGNIF_NEUROLINKED_MAX_CONCURRENT_BRAIN_IO`** — cap concurrent `asyncio.to_thread` brain ingest.

## Install systemd units

```bash
sudo cp ~/sygnif-swarm/BTC_Prediction/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sygnif-neurolinked sygnif-bybit-nl-feed sygnif-swarm-predict-loop
```

**Ports:** NeuroLinked defaults to **8889** (`0.0.0.0`). Open the security group / firewall if you need the dashboard on the public IP. Do not run another service on the same port (e.g. a futures dashboard).

**Venue safety:** `sygnif-swarm-predict-loop` runs the predict protocol with **`--execute`** only when `SYGNIF_PREDICT_PROTOCOL_LOOP_ACK=YES` and valid **`BYBIT_DEMO_*`** are set in `swarm_operator.env` (see example file).

## HTTP stack notes

NeuroLinked’s `run.py` uses **uvicorn** with **`http="h11"`** and a short **`timeout_graceful_shutdown`** so `systemctl restart` does not hang on open WebSocket clients. The FastAPI app uses **`asyncio.to_thread`** for heavy POST ingest and caps concurrent brain I/O with a semaphore.
