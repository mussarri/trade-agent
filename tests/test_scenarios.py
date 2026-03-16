import pytest

from backtest.runner import run_fixture_backtest


@pytest.mark.asyncio
async def test_fixture_backtest_produces_stats():
    result = await run_fixture_backtest("tests/fixtures/candles.json")
    assert "stats" in result
    assert "scenarios" in result["stats"]
    assert "symbols" in result["stats"]


def test_v2_scenarios_load():
    from scenarios import load_all_scenarios
    scenarios = load_all_scenarios(enabled=["bos_continuation", "fvg_retrace", "liquidity_sweep"])
    assert len(scenarios) == 3
    names = {s.name for s in scenarios}
    assert names == {"bos_continuation", "fvg_retrace", "liquidity_sweep"}
