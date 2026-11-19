"""Nettoyage des CSV bruts VLR.gg -> parquet typés dans data/processed/.

Corrige les quatre pièges du dataset :
  1. Pourcentages stockés en string ("95%", "62%")  -> float (0-100)
  2. Crédits stockés en string ("3.9k")             -> int (3900)
  3. Lignes d'agrégats ("All Maps", "All Stages", "All Match Types")
     mélangées aux lignes de détail                  -> colonnes booléennes
     is_*_agg pour filtrer explicitement
  4. Colonnes hétérogènes                            -> noms snake_case,
     types cohérents

Les parquet de data/processed/ conservent TOUTES les lignes (détail +
agrégats, tous les sides) : c'est build_model.py qui applique les filtres
métier pour produire les tables du modèle en étoile.

Usage:
    python -m src.clean
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from src.config import AGG_MAP, AGG_MATCH_TYPE, AGG_STAGE, PROCESSED_DIR, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de conversion
# ---------------------------------------------------------------------------
def snake_case(name: str) -> str:
    """'Average Combat Score' -> 'average_combat_score' ; 'Headshot %' -> 'headshot'.

    La ponctuation est retirée AVANT le strip : sinon 'Headshot %' laisse un
    espace final et devient 'headshot_', et les renommages ne s'appliquent pas.
    """
    name = re.sub(r"[^\w\s]", "", name).strip()
    return re.sub(r"\s+", "_", name).lower()


def pct_to_float(series: pd.Series) -> pd.Series:
    """'95%' -> 95.0 (float, NaN conservés)."""
    return pd.to_numeric(
        series.astype("string").str.rstrip("%"), errors="coerce"
    )


def credits_to_int(series: pd.Series) -> pd.Series:
    """'3.9k' -> 3900 (Int64 nullable, NaN conservés)."""
    numeric = pd.to_numeric(
        series.astype("string").str.lower().str.rstrip("k"), errors="coerce"
    )
    return (numeric * 1000).round().astype("Int64")


def duration_to_seconds(series: pd.Series) -> pd.Series:
    """'48:56' -> 2936 s ; '1:02:33' -> 3753 s (Int64 nullable).

    Les cartes avec overtime long dépassent l'heure, d'où le format mixte
    MM:SS / H:MM:SS dans la même colonne.
    """

    def parse(value) -> int | None:
        if pd.isna(value):
            return None
        parts = str(value).split(":")
        try:
            numbers = [int(p) for p in parts]
        except ValueError:
            return None
        seconds = 0
        for n in numbers:
            seconds = seconds * 60 + n
        return seconds

    return series.map(parse).astype("Int64")


def add_agg_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute is_map_agg / is_stage_agg / is_match_type_agg si applicable."""
    if "map" in df.columns:
        df["is_map_agg"] = df["map"] == AGG_MAP
    if "stage" in df.columns:
        df["is_stage_agg"] = df["stage"] == AGG_STAGE
    if "match_type" in df.columns:
        df["is_match_type_agg"] = df["match_type"] == AGG_MATCH_TYPE
    return df


def load_raw(relative_path: str) -> pd.DataFrame:
    """Charge un CSV brut et normalise les noms de colonnes en snake_case."""
    df = pd.read_csv(RAW_DIR / relative_path)
    df.columns = [snake_case(c) for c in df.columns]
    return df


def save(df: pd.DataFrame, name: str) -> None:
    path = PROCESSED_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False)
    log.info("%-28s %6d lignes -> %s", name, len(df), path.name)


# ---------------------------------------------------------------------------
# Nettoyage table par table
# ---------------------------------------------------------------------------
def clean_agents_pick_rates() -> pd.DataFrame:
    df = load_raw("agents/agents_pick_rates.csv")
    df["pick_rate"] = pct_to_float(df["pick_rate"])
    return add_agg_flags(df)


def clean_maps_stats() -> pd.DataFrame:
    df = load_raw("agents/maps_stats.csv")
    for col in ("attacker_side_win_percentage", "defender_side_win_percentage"):
        df[col] = pct_to_float(df[col])
    return add_agg_flags(df)


def clean_teams_picked_agents() -> pd.DataFrame:
    df = load_raw("agents/teams_picked_agents.csv")
    return add_agg_flags(df)


def clean_overview() -> pd.DataFrame:
    df = load_raw("matches/overview.csv")
    df = df.rename(
        columns={
            "kills_deaths_kd": "kd_diff",
            "kill_assist_trade_survive": "kast_pct",
            "kills_deaths_fkd": "fkd_diff",
        }
    )
    for col in ("kast_pct", "headshot"):
        if col in df.columns:
            df[col] = pct_to_float(df[col])
    df = df.rename(columns={"headshot": "headshot_pct"})
    # overview contient aussi une ligne 'All Maps' par joueur et par match (le total
    # du match) : sans flag, les stats joueur sont comptées deux fois.
    return add_agg_flags(df)


def clean_players_stats() -> pd.DataFrame:
    df = load_raw("players_stats/players_stats.csv")
    df = df.rename(
        columns={
            "kill_assist_trade_survive": "kast_pct",
            "killsdeaths": "kd_ratio",
        }
    )
    for col in ("kast_pct", "headshot", "clutch_success"):
        if col in df.columns:
            df[col] = pct_to_float(df[col])
    df = df.rename(columns={"headshot": "headshot_pct", "clutch_success": "clutch_success_pct"})
    return add_agg_flags(df)


def clean_eco_rounds() -> pd.DataFrame:
    df = load_raw("matches/eco_rounds.csv")
    df["loadout_value"] = credits_to_int(df["loadout_value"])
    df["remaining_credits"] = credits_to_int(df["remaining_credits"])
    df["won"] = df["outcome"] == "Win"
    return df


def clean_eco_stats() -> pd.DataFrame:
    return add_agg_flags(load_raw("matches/eco_stats.csv"))


def clean_scores() -> pd.DataFrame:
    df = load_raw("matches/scores.csv")
    # 'Paper Rex won' -> colonne winner exploitable
    df["winner"] = df["match_result"].astype("string").str.removesuffix(" won")
    return df


def clean_maps_scores() -> pd.DataFrame:
    df = load_raw("matches/maps_scores.csv")
    df["duration_seconds"] = duration_to_seconds(df["duration"])
    df["winner"] = df["team_a"].where(df["team_a_score"] > df["team_b_score"], df["team_b"])
    return df


def clean_passthrough(relative_path: str) -> pd.DataFrame:
    """Tables propres à la source : simple normalisation des colonnes."""
    return add_agg_flags(load_raw(relative_path))


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    save(clean_agents_pick_rates(), "agents_pick_rates")
    save(clean_maps_stats(), "maps_stats")
    save(clean_teams_picked_agents(), "teams_picked_agents")
    save(clean_overview(), "overview")
    save(clean_players_stats(), "players_stats")
    save(clean_eco_rounds(), "eco_rounds")
    save(clean_eco_stats(), "eco_stats")
    save(clean_scores(), "scores")
    save(clean_maps_scores(), "maps_scores")

    save(clean_passthrough("matches/draft_phase.csv"), "draft_phase")
    save(clean_passthrough("matches/kills.csv"), "kills")
    save(clean_passthrough("matches/kills_stats.csv"), "kills_stats")
    save(clean_passthrough("matches/maps_played.csv"), "maps_played")
    save(clean_passthrough("matches/rounds_kills.csv"), "rounds_kills")
    save(clean_passthrough("matches/team_mapping.csv"), "team_mapping")
    save(clean_passthrough("matches/win_loss_methods_count.csv"), "win_loss_methods_count")
    save(
        clean_passthrough("matches/win_loss_methods_round_number.csv"),
        "win_loss_methods_round_number",
    )

    save(clean_passthrough("ids/players_ids.csv"), "players_ids")
    save(clean_passthrough("ids/teams_ids.csv"), "teams_ids")
    save(
        clean_passthrough("ids/tournaments_stages_matches_games_ids.csv"),
        "tournaments_games_ids",
    )

    log.info("Nettoyage terminé -> %s", PROCESSED_DIR)


if __name__ == "__main__":
    main()
