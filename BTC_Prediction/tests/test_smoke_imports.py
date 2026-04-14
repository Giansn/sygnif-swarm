from __future__ import annotations


def test_import_swarm_knowledge() -> None:
    import swarm_knowledge  # noqa: F401


def test_import_predict_core() -> None:
    from btc_asap_predict_core import run_live_fit  # noqa: F401


def test_import_bybit_hedge() -> None:
    import bybit_linear_hedge  # noqa: F401
