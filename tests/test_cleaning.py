import json
from pathlib import Path

import pandas as pd

from pm_efficiency.data.clean import extract_outcomes, normalize_candles, normalize_markets
from pm_efficiency.data.validate import validate_candles, validate_outcomes

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_normalizes_current_and_historical_candle_shapes():
    current = normalize_candles([_fixture("candle_current.json")], "CURRENT")
    historical = normalize_candles([_fixture("candle_historical.json")], "HISTORICAL")
    assert current.loc[0, "probability_mid"] == 0.44
    assert historical.loc[0, "probability_mid"] == 0.345
    assert current.loc[0, "volume_interval"] == 27
    assert historical.loc[0, "open_interest"] == 99
    assert validate_candles(pd.concat([current, historical])).ok


def test_outcomes_keep_exceptional_resolutions_but_mark_them_invalid():
    valid = _fixture("market_current.json")
    invalid = {**valid, "ticker": "VOID", "result": "void", "settlement_ts": None}
    markets = normalize_markets([valid, invalid], retrieved_at="2026-06-21T00:00:00Z")
    outcomes = extract_outcomes(markets)
    yes = outcomes.loc[outcomes.market_id.str.startswith("KX")].iloc[0]
    void = outcomes.loc[outcomes.market_id == "VOID"].iloc[0]
    assert yes.outcome == 1 and bool(yes.is_valid_resolution)
    assert pd.isna(void.outcome) and not bool(void.is_valid_resolution)
    report = validate_outcomes(outcomes)
    assert report.ok and report.warnings
    assert str(markets.loc[markets.market_id.str.startswith("KX"), "event_date"].iloc[0]) == (
        "2026-06-19"
    )


def test_crossed_quote_is_rejected():
    candle = _fixture("candle_current.json")
    candle["yes_bid"]["close_dollars"] = "0.60"
    candles = normalize_candles([candle], "BAD")
    assert not validate_candles(candles).ok
