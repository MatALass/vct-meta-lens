import pandas as pd

from src.build_model import (
    build_dim_tournament,
    build_fact_agent_picks,
    build_fact_match_team,
    detail_only,
    ensure_members,
    explode_agents,
    single_agent,
)

KEYS = {"tournament": "T", "stage": "S", "match_type": "M"}


def test_detail_only_drops_aggregates_and_flags():
    df = pd.DataFrame(
        {
            "map": ["All Maps", "Ascent", "Bind"],
            "is_map_agg": [True, False, False],
            "is_stage_agg": [False, False, True],
        }
    )
    out = detail_only(df)
    assert out["map"].tolist() == ["Ascent"]
    assert not any(c.startswith("is_") for c in out.columns)


def test_agent_picks_get_maps_played_weight():
    picks = pd.DataFrame([{**KEYS, "map": "Ascent", "agent": "Omen ", "pick_rate": 50}])
    stats = pd.DataFrame([{**KEYS, "map": "Ascent", "total_maps_played": 4}])
    out = build_fact_agent_picks(picks, stats)
    assert out.loc[0, "maps_played"] == 4
    assert out.loc[0, "agent"] == "omen"


def test_single_agent_keeps_first_value():
    out = single_agent(pd.DataFrame({"agents": ["jett", "Raze, sova"]}))
    assert out["agent"].tolist() == ["jett", "raze"]
    assert "agents" not in out.columns


def test_explode_agents_builds_bridge():
    df = pd.DataFrame([{**KEYS, "player": "aspas", "agents": "jett, raze"}])
    bridge = explode_agents(df, ["tournament", "stage", "match_type", "player"])
    assert sorted(bridge["agent"]) == ["jett", "raze"]


def test_match_team_has_one_row_per_team():
    scores = pd.DataFrame(
        [{**KEYS, "match_name": "A vs B", "team_a": "A", "team_b": "B", "team_a_score": 2, "team_b_score": 1}]
    )
    out = build_fact_match_team(scores)
    assert len(out) == 2
    assert out.set_index("team")["won"].to_dict() == {"A": True, "B": False}


def test_ensure_members_adds_orphans():
    dim = pd.DataFrame({"player": ["aspas"]})
    fact = pd.DataFrame({"player": ["aspas", "Derke"]})
    assert ensure_members(dim, "player", fact)["player"].tolist() == ["aspas", "Derke"]


def test_dim_tournament_is_complete_and_ordered():
    dim = build_dim_tournament()
    assert len(dim) == 15
    assert dim["season_order"].is_unique
    assert dim["tournament_short"].notna().all()


def test_case_insensitive_duplicates_are_renamed():
    from src.build_model import case_insensitive_names, check_unique_for_powerbi

    dim = pd.DataFrame({"player": ["f0rsakeN", "f0rsaken", "aspas"], "player_id": [9801.0, 12088.0, 8480.0]})
    fact = pd.DataFrame({"player": ["f0rsakeN"] * 5 + ["f0rsaken"]})
    out, renames = case_insensitive_names(dim, "player", [fact], "player_id")
    assert renames == {"f0rsaken": "f0rsaken (12088)"}  # the most used spelling keeps its name
    assert out["player"].tolist() == ["f0rsakeN", "f0rsaken (12088)", "aspas"]
    check_unique_for_powerbi(out, "player", "dim_player")


def test_powerbi_key_check_catches_case_and_trailing_spaces():
    import pytest

    from src.build_model import check_unique_for_powerbi

    with pytest.raises(ValueError, match="clé valide"):
        check_unique_for_powerbi(pd.DataFrame({"team": ["NRG", "nrg"]}), "team", "dim_team")
    with pytest.raises(ValueError, match="clé valide"):
        check_unique_for_powerbi(pd.DataFrame({"team": ["NRG", "NRG "]}), "team", "dim_team")


def test_player_map_drops_all_maps_rows():
    from src.build_model import build_fact_player_map

    overview = pd.DataFrame(
        {
            "map": ["All Maps", "Ascent"],
            "side": ["both", "both"],
            "agents": ["jett", "jett"],
            "kills": [40, 20],
            "is_map_agg": [True, False],
        }
    )
    out = build_fact_player_map(overview)
    assert out["map"].tolist() == ["Ascent"]


def test_eco_rounds_tournament_names_are_normalized():
    from src.build_model import normalize_tournament
    from src.config import TOURNAMENT_META

    for raw in [
        "Champions Tour 2025: EMEA Stage 1",
        "Champions Tour 2025: Masters Bangkok",
        "Champions Tour 2025: Americas Kickoff",
        "Valorant Masters Toronto 2025",
    ]:
        assert normalize_tournament(raw) in TOURNAMENT_META
