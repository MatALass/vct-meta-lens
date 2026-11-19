"""Construction du modèle en étoile pour Power BI -> data/model/ (CSV).

À partir des parquet nettoyés de data/processed/, produit :

Dimensions
    dim_tournament   tournoi, libellé court, ordre saison, région, tier
    dim_agent        agent, rôle (Duelist/Controller/Initiator/Sentinel)
    dim_map          maps jouées sur la saison
    dim_team         nom complet + abréviation + team_id
    dim_player       joueur + player_id

Faits (granularité détail uniquement : agrégats "All *" exclus partout)
    fact_agent_picks      pick rate par tournoi/stage/match_type/map/agent,
                          avec le nombre de maps jouées pour pondérer
    fact_map_stats        winrate ATK/DEF par tournoi/stage/match_type/map
    fact_team_agent_map   W/L par équipe/agent/map
    fact_player_map       stats joueur par carte (side = both), un agent
    fact_player_stage     stats joueur agrégées par tournoi/stage
    fact_match            résultats de matchs (BO) + vainqueur
    fact_match_team       une ligne par équipe et par match (pour les winrates)
    fact_map_score        scores par carte + vainqueur + durée
    fact_eco              rounds éco initiés/gagnés par catégorie d'achat
    fact_eco_rounds       détail round par round (loadout, outcome)
    fact_round_methods    méthode de fin de round, round par round
    fact_multikills       multikills (2k-5k), clutchs, plants/defuses
    fact_draft            picks/bans de maps

Power BI lit ces CSV via le projet powerbi/VCTMetaLens (voir powerbi/README.md).

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
    TIER_ORDER,
    TOURNAMENT_META,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

MATCH_KEYS = ["tournament", "stage", "match_type"]


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
            mask &= ~df[flag].fillna(False).astype(bool)
    return df.loc[mask].drop(
        columns=[c for c in df.columns if c.startswith("is_") and c.endswith("_agg")]
    )


def single_agent(df: pd.DataFrame, column: str = "agents") -> pd.DataFrame:
    """Ramène une colonne d'agents à une colonne `agent` reliable à dim_agent.

    Au niveau d'une carte, un joueur ne joue qu'un agent : la colonne `agents`
    de la source ne contient alors qu'une valeur. Si plusieurs valeurs sont
    présentes (séparées par des virgules), on garde la première et on le signale.
    """
    if column not in df.columns:
        return df
    parts = df[column].astype("string").str.lower().str.split(",")
    multi = parts.str.len().fillna(0).gt(1)
    if multi.any():
        log.warning("%d lignes avec plusieurs agents dans %s : premier conservé", multi.sum(), column)
    out = df.drop(columns=[column])
    out["agent"] = parts.str[0].str.strip()
    return out


def explode_agents(df: pd.DataFrame, keys: list[str], column: str = "agents") -> pd.DataFrame:
    """Table pont (une ligne par clé et par agent) pour une colonne multi-valeurs."""
    bridge = df[keys + [column]].copy()
    bridge["agent"] = bridge[column].astype("string").str.lower().str.split(",")
    bridge = bridge.explode("agent").drop(columns=[column])
    bridge["agent"] = bridge["agent"].str.strip()
    return bridge.dropna(subset=["agent"]).loc[lambda d: d["agent"] != ""].drop_duplicates()


def ensure_members(dim: pd.DataFrame, key: str, *facts: pd.DataFrame) -> pd.DataFrame:
    """Ajoute à la dimension les valeurs vues dans les faits mais absentes.

    Sans ça, Power BI rattache ces lignes à une ligne vide et les visuels
    affichent « (Vide) ».
    """
    seen: set = set()
    for fact in facts:
        if key in fact.columns:
            seen |= set(fact[key].dropna())
    missing = sorted(seen - set(dim[key]))
    if missing:
        log.warning("Valeurs de %s absentes de la dimension, ajoutées : %s", key, missing)
        dim = pd.concat([dim, pd.DataFrame({key: missing})], ignore_index=True)
    return dim


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
def build_dim_tournament() -> pd.DataFrame:
    rows = [{"tournament": name, **meta} for name, meta in TOURNAMENT_META.items()]
    df = pd.DataFrame(rows).rename(columns={"order": "season_order", "short": "tournament_short"})
    df["phase_order"] = df["tier"].map(TIER_ORDER)
    return df[["tournament", "tournament_short", "season_order", "region", "tier", "phase_order"]]


def build_dim_agent(*facts: pd.DataFrame) -> pd.DataFrame:
    agents: set = set()
    for fact in facts:
        if "agent" in fact.columns:
            agents |= set(fact["agent"].dropna())
    df = pd.DataFrame({"agent": sorted(agents)})
    df["role"] = df["agent"].map(AGENT_ROLES).fillna("Unknown")
    df["agent_label"] = df["agent"].str.title().str.replace("Kayo", "KAY/O")
    unknown = df.loc[df["role"] == "Unknown", "agent"].tolist()
    if unknown:
        log.warning("Agents sans rôle dans config.AGENT_ROLES : %s", unknown)
    return df


def build_dim_map(*facts: pd.DataFrame) -> pd.DataFrame:
    maps: set = set()
    for fact in facts:
        if "map" in fact.columns:
            maps |= {m for m in fact["map"].dropna() if m != AGG_MAP}
    return pd.DataFrame({"map": sorted(maps)})


def build_dim_team(observed_teams: pd.Series) -> pd.DataFrame:
    """Union du référentiel team_mapping et des équipes observées dans les faits.

    Certaines équipes hors circuit principal (ex. showmatch 'Mega Minors')
    apparaissent dans les données sans figurer dans team_mapping : elles sont
    ajoutées avec abréviation/ID manquants pour garantir l'intégrité
    référentielle côté Power BI.
    """
    mapping = load("team_mapping").rename(columns={"abbreviated": "team_abbr", "full_name": "team"})
    ids = load("teams_ids")
    dim = mapping.merge(ids, on="team", how="left")[["team", "team_abbr", "team_id"]]
    dim = dim.drop_duplicates(subset=["team"])

    extra = sorted(set(observed_teams.dropna()) - set(dim["team"]))
    if extra:
        log.warning("Équipes hors team_mapping ajoutées à dim_team : %s", extra)
        dim = pd.concat([dim, pd.DataFrame({"team": extra})], ignore_index=True)
    return dim.sort_values("team").reset_index(drop=True)


def build_dim_player(*facts: pd.DataFrame) -> pd.DataFrame:
    dim = load("players_ids")[["player", "player_id"]].drop_duplicates(subset=["player"])
    return ensure_members(dim, "player", *facts)


# ---------------------------------------------------------------------------
# Faits
# ---------------------------------------------------------------------------
def build_fact_agent_picks(pick_rates: pd.DataFrame, maps_stats: pd.DataFrame) -> pd.DataFrame:
    """Pick rates de détail + nombre de maps jouées sur la même granularité.

    pick_rate est un pourcentage calculé par tournoi/stage/match_type/map :
    pour l'agréger plus haut, il faut le pondérer par maps_played.
    """
    picks = detail_only(pick_rates)
    weights = detail_only(maps_stats)[MATCH_KEYS + ["map", "total_maps_played"]]
    weights = weights.rename(columns={"total_maps_played": "maps_played"})
    out = picks.merge(weights, on=MATCH_KEYS + ["map"], how="left")
    missing = out["maps_played"].isna().sum()
    if missing:
        log.warning("%d pick rates sans nombre de maps jouées (pondération à 0)", missing)
    out["maps_played"] = out["maps_played"].fillna(0).astype(int)
    out["agent"] = out["agent"].str.lower().str.strip()
    return out


def build_fact_player_map(overview: pd.DataFrame) -> pd.DataFrame:
    """Stats joueur par carte. Une seule ligne par joueur/carte (side='both').

    Les lignes attack/defend restent disponibles dans
    data/processed/overview.parquet pour des analyses par side.
    """
    df = overview.loc[overview["side"] == "both"].drop(columns=["side"])
    return single_agent(df)


def build_fact_match_team(scores: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par équipe et par match : base des winrates d'équipe.

    fact_match garde team_a / team_b sur la même ligne, ce qui oblige à deux
    relations vers dim_team (dont une inactive). Ce format long n'en demande qu'une.
    """
    keys = MATCH_KEYS + ["match_name"]
    side_a = scores[keys + ["team_a", "team_b", "team_a_score", "team_b_score"]].rename(
        columns={"team_a": "team", "team_b": "opponent", "team_a_score": "maps_won", "team_b_score": "maps_lost"}
    )
    side_b = scores[keys + ["team_b", "team_a", "team_b_score", "team_a_score"]].rename(
        columns={"team_b": "team", "team_a": "opponent", "team_b_score": "maps_won", "team_a_score": "maps_lost"}
    )
    out = pd.concat([side_a, side_b], ignore_index=True)
    out["won"] = out["maps_won"] > out["maps_lost"]
    return out.sort_values(keys + ["team"]).reset_index(drop=True)


def build_fact_eco(eco_stats: pd.DataFrame) -> pd.DataFrame:
    df = eco_stats.copy()
    df["buy_category"] = df["type"].map(ECO_TYPE_LABELS).fillna(df["type"])
    df = df.drop(columns=["type"])
    df["win_rate"] = (df["won"] / df["initiated"]).where(df["initiated"] > 0)
    return detail_only(df)


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Faits d'abord : les dimensions sont complétées avec les valeurs observées.
    facts = {
        "fact_agent_picks": build_fact_agent_picks(load("agents_pick_rates"), load("maps_stats")),
        "fact_map_stats": detail_only(load("maps_stats")),
        "fact_team_agent_map": detail_only(load("teams_picked_agents")).assign(
            agent=lambda d: d["agent"].str.lower().str.strip()
        ),
        "fact_player_map": build_fact_player_map(load("overview")),
        "fact_player_stage": detail_only(load("players_stats")),
        "fact_match": load("scores"),
        "fact_match_team": build_fact_match_team(load("scores")),
        "fact_map_score": load("maps_scores"),
        "fact_eco": build_fact_eco(load("eco_stats")),
        "fact_eco_rounds": detail_only(load("eco_rounds")),
        "fact_round_methods": detail_only(load("win_loss_methods_round_number")),
        "fact_multikills": single_agent(detail_only(load("kills_stats"))),
        "fact_draft": detail_only(load("draft_phase")),
    }
    # Agents joués par joueur et par stage : colonne multi-valeurs -> table pont.
    bridge = explode_agents(facts["fact_player_stage"], MATCH_KEYS + ["player"])
    facts["fact_player_stage"] = facts["fact_player_stage"].drop(columns=["agents", "teams"], errors="ignore")

    all_facts = list(facts.values()) + [bridge]
    save(build_dim_tournament(), "dim_tournament")
    save(build_dim_agent(*all_facts), "dim_agent")
    save(build_dim_map(*all_facts), "dim_map")
    observed_teams = pd.concat([f["team"] for f in all_facts if "team" in f.columns], ignore_index=True)
    save(build_dim_team(observed_teams), "dim_team")
    save(build_dim_player(*all_facts), "dim_player")

    for name, df in facts.items():
        save(df, name)
    save(bridge, "bridge_player_stage_agent")

    log.info("Modèle en étoile prêt -> %s (à importer dans Power BI)", MODEL_DIR)


if __name__ == "__main__":
    main()
