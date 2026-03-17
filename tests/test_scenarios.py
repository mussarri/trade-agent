import pytest

from backtest.runner import run_fixture_backtest
from scenarios import load_all_scenarios


@pytest.mark.asyncio
async def test_fixture_backtest_produces_stats():
    result = await run_fixture_backtest("tests/fixtures/candles.json")
    assert "stats" in result
    assert "scenarios" in result["stats"]
    assert "symbols" in result["stats"]


def test_v2_scenarios_load():
    scenarios = load_all_scenarios()
    assert isinstance(scenarios, list)
    assert len(scenarios) == 1
    assert scenarios[0].name == "htf_pullback_continuation"
