# BTC Prediction — Swarm + predict protocol

Portable slice: **5m live fit**, **Bybit demo** hooks, **Swarm / Truthcoin Hivemind** core, **Nautilus** fusion sidecar.

| Path | Role |
|------|------|
| `scripts/` | Predict loop, swarm auto launcher, gated order, scans, **Bybit→NeuroLinked feed** |
| `prediction_agent/` | ASAP fit, fusion writer, ML JSON |
| `finance_agent/` | Swarm knowledge, gates, Truthcoin bridge, **NeuroLinked predict-loop hook** |
| `trade_overseer/` | Bybit linear REST |
| `third_party/neurolinked/` | **NeuroLinked** brain UI + HTTP ingest (`run.py`, port **8889**) |
| `deploy/systemd/` | Unit templates: predict loop, NeuroLinked, Bybit NL feed |
| `docs/NEUROLINKED_SYSTEMD.md` | NeuroLinked + systemd + env tuning |
| `letscrash/` | R01 registry JSON |
| `network/` | Docker external bridge overlay |

From **repository root**:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp BTC_Prediction/.env.example BTC_Prediction/.env
source tools/env.sh
cd "$SYGNIF_REPO_ROOT"
python3 scripts/btc_predict_protocol_loop.py --help
```

Docker bridge: create `sygnif_network` once; merge `network/docker-compose.sygnif-network.yml` with your compose file.
