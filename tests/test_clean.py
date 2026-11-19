import pandas as pd

from src.clean import add_agg_flags, credits_to_int, duration_to_seconds, pct_to_float, snake_case


def test_snake_case_drops_trailing_punctuation():
    # Bug corrigé : 'Headshot %' donnait 'headshot_' et les renommages ratés.
    assert snake_case("Headshot %") == "headshot"
    assert snake_case("Kill, Assist, Trade, Survive %") == "kill_assist_trade_survive"
    assert snake_case("Clutch Success %") == "clutch_success"
    assert snake_case("Average Combat Score") == "average_combat_score"
    assert snake_case("Clutches (won/played)") == "clutches_wonplayed"


def test_pct_to_float():
    out = pct_to_float(pd.Series(["95%", "7%", None]))
    assert out.tolist()[:2] == [95.0, 7.0]
    assert pd.isna(out.iloc[2])


def test_credits_to_int():
    assert credits_to_int(pd.Series(["3.9k", "0.5k"])).tolist() == [3900, 500]


def test_duration_to_seconds_handles_hours():
    assert duration_to_seconds(pd.Series(["48:56", "1:02:33"])).tolist() == [2936, 3753]


def test_add_agg_flags():
    df = add_agg_flags(pd.DataFrame({"map": ["All Maps", "Ascent"], "stage": ["All Stages", "Playoffs"]}))
    assert df["is_map_agg"].tolist() == [True, False]
    assert df["is_stage_agg"].tolist() == [True, False]
