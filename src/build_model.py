"""Construction du modèle en étoile pour Power BI -> data/model/ (CSV).

À partir des parquet nettoyés de data/processed/, produit :

Dimensions
    dim_tournament   tournoi, ordre chronologique saison, région, tier
    dim_agent        agent, rôle (Duelist/Controller/Initiator/Sentinel)
    dim_map          maps jouées sur la saison
    dim_team         nom complet + abréviation + team_id
    dim_player       joueur + player_id

Faits (granularité détail uniquement — agrégats "All *" exclus)
    fact_agent_picks      pick rate par tournoi/stage/match_type/map/agent
    fact_map_stats        winrate ATK/DEF par tournoi/stage/match_type/map
    fact_team_agent_map   W/L par équipe/agent/map
    fact_player_map       stats joueur par carte (side = both)
    fact_player_stage     stats joueur agrégées par tournoi/stage
    fact_match            résultats de matchs (BO) + vainqueur
    fact_map_score        scores par carte + vainqueur + durée
    fact_eco              rounds éco initiés/gagnés par catégorie d'achat
    fact_eco_rounds       détail round par round (loadout, outcome)
    fact_round_methods    méthode de fin de round, round par round
    fact_multikills       multikills (2k-5k), clutchs, plants/defuses
    fact_draft            picks/bans de maps

Power BI lit ces CSV directement (Obtenir les données > Texte/CSV) ;
les relations se font sur les colonnes tournament / agent / map / team /
player vers les dimensions.

Usage:
    python -m src.build_model
"""

from __future__ import annotations

import logging

import pandas as pd

from src.config import (
    AGENT_ROLES,
    AGG_MAP,
    ECO_TYPE_LABELS,
    MODEL_DIR,
    PROCESSED_DIR,
    TOURNAMENT_META,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")


def save(df: pd.DataFrame, name: str) -> None:
    path = MODEL_DIR / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")  # BOM : accents OK dans Power BI
    log.info("%-22s %6d lignes -> %s", name, len(df), path.name)


def detail_only(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les lignes d'agrégats 'All *' (flags posés par clean.py)."""
    mask = pd.Series(True, index=df.index)
    for flag in ("is_map_agg", "is_stage_agg", "is_match_type_agg"):
        if flag in df.columns:
            mask &= ~df[flag]
    return df.loc[mask].drop(
        columns=[c for c in df.columns if c.startswith("is_") and c.endswith("_agg")]
    )


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
def build_dim_tournament() -> pd.DataFrame:
    rows = [
        {"tournament": name, **meta} for name, meta in TOURNAMENT_META.items()
    ]
    return pd.DataFrame(rows).rename(columns={"order": "season_order"})


def build_dim_agent(pick_rates: pd.DataFrame) -> pd.DataFrame:
    agents = sorted(pick_rates["agent"].dropna().unique())
    df = pd.DataFrame({"agent": agents})
    df["role"] = df["agent"].map(AGENT_ROLES).fillna("Unknown")
    unknown = df.loc[df["role"] == "Unknown", "agent"].tolist()
    if unknown:
        log.warning("Agents sans rôle dans config.AGENT_ROLES : %s", unknown)
    return df


def build_dim_map(pick_rates: pd.DataFrame) -> pd.DataFrame:
    maps = sorted(m for m in pick_rates["map"].dropna().unique() if m != AGG_MAP)
    return pd.DataFrame({"map": maps})


def build_dim_team(observed_teams: pd.Series) -> pd.DataFrame:
    """Union du référentiel team_mapping et des équipes observées dans les faits.

    Certaines équipes hors circuit principal (ex. showmatch 'Mega Minors')
    apparaissent dans les données sans figurer dans team_mapping : elles sont
    ajoutées avec abréviation/ID manquants pour garantir l'intégrité
    référentielle côté Power BI.
    """
    mapping = load("team_mapping").rename(
        columns={"abbreviated": "team_abbr", "full_name": "team"}
    )
    ids = load("teams_ids")
    dim = mapping.merge(ids, on="team", how="left")[["team", "team_abbr", "team_id"]]

    extra = sorted(set(observed_teams.dropna()) - set(dim["team"]))
    if extra:
        log.warning("Équipes hors team_mapping ajoutées à dim_team : %s", extra)
        dim = pd.concat(
            [dim, pd.DataFrame({"team": extra})], ignore_index=True
        )
    return dim.sort_values("team").reset_index(drop=True)


def build_dim_player() -> pd.DataFrame:
    return load("players_ids")[["player", "player_id"]]


# ---------------------------------------------------------------------------
# Faits
# ---------------------------------------------------------------------------
def build_fact_player_map(overview: pd.DataFrame) -> pd.DataFrame:
    """Stats joueur par carte. Une seule ligne par joueur/carte (side='both').

    Les lignes attack/defend restent disponibles dans
    data/processed/overview.parquet pour des analyses par side.
    """
    df = overview.loc[overview["side"] == "both"].drop(columns=["side"])
    return df


def build_fact_eco(eco_stats: pd.DataFrame) -> pd.DataFrame:
    df = eco_stats.copy()
    df["buy_category"] = df["type"].map(ECO_TYPE_LABELS).fillna(df["type"])
    df = df.drop(columns=["type"])
    df["win_rate"] = (df["won"] / df["initiated"]).where(df["initiated"] > 0)
    return df


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    pick_rates = load("agents_pick_rates")

    # Dimensions
    save(build_dim_tournament(), "dim_tournament")
    save(build_dim_agent(pick_rates), "dim_agent")
    save(build_dim_map(pick_rates), "dim_map")
    observed_teams = pd.concat(
        [
            load("teams_picked_agents")["team"],
            load("overview")["team"],
            load("scores")["team_a"],
            load("scores")["team_b"],
        ],
        ignore_index=True,
    )
    save(build_dim_team(observed_teams), "dim_team")
    save(build_dim_player(), "dim_player")

    # Faits
    save(detail_only(pick_rates), "fact_agent_picks")
    save(detail_only(load("maps_stats")), "fact_map_stats")
    save(detail_only(load("teams_picked_agents")), "fact_team_agent_map")
    save(build_fact_player_map(load("overview")), "fact_player_map")
    save(detail_only(load("players_stats")), "fact_player_stage")
    save(load("scores"), "fact_match")
    save(load("maps_scores"), "fact_map_score")
    save(build_fact_eco(load("eco_stats")), "fact_eco")
    save(load("eco_rounds"), "fact_eco_rounds")
    save(load("win_loss_methods_round_number"), "fact_round_methods")
    save(load("kills_stats"), "fact_multikills")
    save(load("draft_phase"), "fact_draft")

    log.info("Modèle en étoile prêt -> %s (à importer dans Power BI)", MODEL_DIR)


if __name__ == "__main__":
    main()
