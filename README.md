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

## Upstream

Extracted from the Sygnif monorepo; full strategy stack lives there separately.
