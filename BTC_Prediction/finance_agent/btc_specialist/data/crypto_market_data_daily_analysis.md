# Crypto Market Data — daily analysis snapshot

_Generated (UTC): 2026-04-14T03:15:02Z_

_Source: [ErcinDedeoglu/crypto-market-data](https://github.com/ErcinDedeoglu/crypto-market-data) (CC BY 4.0). Not Sygnif TA; not Bybit OHLC. Daily bars._

## BTC exchange / whales

- **BTC Exchange Inflow Total** _(Decimal (BTC))_ (`btc_exchange_inflow_total.json`): `1.29k`; Δ≈-94.6% vs 7d window — _Signal hint:_ High spike → Panic selling risk or whale accumulation.
- **BTC Exchange Netflow** _(Decimal (BTC))_ (`btc_exchange_netflow.json`): `-203.8`; Δ≈+93.5% vs 7d window — _Signal hint:_ Positive → Bearish (Dump risk). Negative → Bullish (Supply squeeze).
- **BTC Exchange Outflow Total** _(Decimal (BTC))_ (`btc_exchange_outflow_total.json`): `1.5k`; Δ≈-94.5% vs 7d window — _Signal hint:_ High spike → Confidence buying or whale hodling. Confirms bullish moves.
- **BTC Exchange Reserve** _(Decimal (BTC))_ (`btc_exchange_reserve.json`): `2.69M`; Δ≈-0.5% vs 7d window — _Signal hint:_ Declining trend → Bullish (Whales removing supply). Increasing trend → Bearish (Whales accumulating to dump).
- **BTC Exchange Reserve USD** _(Decimal (USD))_ (`btc_exchange_reserve_usd.json`): `239B`; Δ≈-0.5% vs 7d window — _Signal hint:_ High → Sellers have ammunition. Low → Market is tight (big moves on small orders).
- **BTC Exchange Stablecoins Ratio** _(Decimal)_ (`btc_exchange_stablecoins_ratio.json`): `2.198e-05`; Δ≈-2.5% vs 7d window — _Signal hint:_ Low (<0.1) → Extreme bullish (Massive buying power ready). High (>1.5) → Bearish (Few buyers, lots of sellers).
- **BTC Exchange Stablecoins Ratio USD** _(Decimal)_ (`btc_exchange_stablecoins_ratio_usd.json`): `1.636`; Δ≈+5.4% vs 7d window — _Signal hint:_ Low → Buyers have advantage. High → Sellers have advantage.
- **BTC Exchange Whale Ratio** _(Decimal (0-1))_ (`btc_exchange_whale_ratio.json`): `0.5454`; Δ≈+2.3% vs 7d window — _Signal hint:_ >0.7 → Whales are consolidating (strong signal, trust it). <0.3 → Retail noise (ignore or fade it).

## Stablecoin (CEX)

- **Stablecoin Exchange Inflow Total** _(Decimal (USD))_ (`stablecoin_exchange_inflow_total.json`): `236M`; Δ≈-92.2% vs 7d window — _Signal hint:_ High spike → Buying pressure building. Combined with BTC inflow = volatility indicator.
- **Stablecoin Exchange Netflow** _(Decimal (USD))_ (`stablecoin_exchange_netflow.json`): `102M`; Δ≈+144.6% vs 7d window — _Signal hint:_ Positive → Bullish (Cash ready). Negative → Bearish (Profit-taking).
- **Stablecoin Exchange Outflow Total** _(Decimal (USD))_ (`stablecoin_exchange_outflow_total.json`): `134M`; Δ≈-95.5% vs 7d window — _Signal hint:_ High spike → Profit-taking phase or de-risking.
- **Stablecoin Exchange Reserve** _(Decimal (USD))_ (`stablecoin_exchange_reserve.json`): `67.5B`; Δ≈+1.9% vs 7d window — _Signal hint:_ High reserve → Market strength (buyers standing by). Low reserve → Capitulation or deployment phase.
- **Stablecoin Exchange Supply Ratio** _(Decimal (%))_ (`stablecoin_exchange_supply_ratio.json`): `0.4298`; Δ≈+1.7% vs 7d window — _Signal hint:_ High → Buyers armed. Low → Cash off-exchange (long-term hold mentality).

## Miners

- **BTC Miner Netflow Total** _(Decimal (BTC))_ (`btc_miner_netflow_total.json`): `-159`; Δ≈-114.7% vs 7d window — _Signal hint:_ Positive & rising → Miners dumping (Bearish). Negative & falling → Miners accumulating (Bullish).
- **BTC Miners Position Index** _(Decimal)_ (`btc_miners_position_index.json`): `-0.8364`; Δ≈+19.8% vs 7d window — _Signal hint:_ >2.0 → Miner dump risk (Bearish, veto longs). <0.5 → Miner confidence (Bullish confirmation).
- **BTC Puell Multiple** _(Decimal)_ (`btc_puell_multiple.json`): `0.7538`; Δ≈+19.6% vs 7d window — _Signal hint:_ >6 → Historical top (miners rich, will dump). <0.4 → Historical bottom (miners desperate).

## Derivatives

- **BTC Funding Rates** _(Decimal (%))_ (`btc_funding_rates.json`): `-0.02048`; Δ≈-4119.0% vs 7d window — _Signal hint:_ >0.05% → Market overheated (Longs will be liquidated). <-0.05% → Market capitulated (Shorts will be liquidated, reversal coming).
- **BTC Long Liquidations** _(Decimal (BTC))_ (`btc_long_liquidations.json`): `0`; Δ≈-100.0% vs 7d window — _Signal hint:_ Spike → Forced selling, price accelerates down. High > short liq → Bears winning.
- **BTC Long Liquidations USD** _(Decimal (USD))_ (`btc_long_liquidations_usd.json`): `0`; Δ≈-100.0% vs 7d window — _Signal hint:_ High spike → Significant long pain. Confirms bearish move.
- **BTC Open Interest** _(Decimal (USD))_ (`btc_open_interest.json`): `24.6B`; Δ≈+8.9% vs 7d window — _Signal hint:_ Extremely high + funding rates spike → Extreme volatility risk. Reduce size.
- **BTC Short Liquidations** _(Decimal (BTC))_ (`btc_short_liquidations.json`): `0`; Δ≈-100.0% vs 7d window — _Signal hint:_ Spike → Forced buying, price accelerates up. High > long liq → Bulls winning.
- **BTC Short Liquidations USD** _(Decimal (USD))_ (`btc_short_liquidations_usd.json`): `0`; Δ≈-100.0% vs 7d window — _Signal hint:_ High spike → Significant short pain. Confirms bullish move.
- **BTC Taker Buy Sell Ratio** _(Decimal)_ (`btc_taker_buy_sell_ratio.json`): `1.03`; Δ≈-8.9% vs 7d window — _Signal hint:_ >1.2 → Extreme bullish sentiment (be cautious, extended rally). <0.8 → Extreme bearish sentiment (be cautious, extended drop).

## Valuation

- **BTC MVRV Ratio** _(Decimal)_ (`btc_mvrv_ratio.json`): `1.374`; Δ≈+8.0% vs 7d window — _Signal hint:_ >3.7 → Use half position size (expensive). <1 → Use 1.5x size (cheap). Not for entry timing.

## Liquidity / context

- **BTC Exchange Supply Ratio** _(Decimal (%))_ (`btc_exchange_supply_ratio.json`): `0.1327`; Δ≈-0.6% vs 7d window — _Signal hint:_ High (>8%) → Dump risk. Low (<3%) → Squeeze risk (illiquid, big moves).
- **BTC Fund Flow Ratio** _(Decimal (%))_ (`btc_fund_flow_ratio.json`): `0.1076`; Δ≈+41.3% vs 7d window — _Signal hint:_ High (>0.15) → Market is active, expect whipsaw. Low (<0.05) → Market is calm.

## Institutional

- **BTC Coinbase Premium Gap** _(Decimal (USD))_ (`btc_coinbase_premium_gap.json`): `28.01`; Δ≈+56120.0% vs 7d window — _Signal hint:_ Wide positive gap → Institutional demand strong. Wide negative gap → Institutional supply strong.
- **BTC Coinbase Premium Index** _(Decimal (%))_ (`btc_coinbase_premium_index.json`): `0.03764`; Δ≈+51929.7% vs 7d window — _Signal hint:_ Positive & rising → Institutions confident (trust the move). Negative & falling → Institutions exiting (warning sign).
- **BTC Korea Premium Index** _(Decimal (%))_ (`btc_korea_premium_index.json`): `-0.58`; Δ≈-866.7% vs 7d window — _Signal hint:_ >5% → Korean retail FOMOing (market top risk, contrarian exit). <0% → Korean retail fearful (market bottom risk, contrarian buy).

---

_On-chain/derivatives daily:_ [Crypto Market Data](https://github.com/ErcinDedeoglu/crypto-market-data) (Ercin Dedeoglu, **CC BY 4.0**) — not Sygnif TA / not Bybit OHLC.
