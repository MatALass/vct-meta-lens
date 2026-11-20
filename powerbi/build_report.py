"""Génère le projet Power BI (PBIP) de VCT Meta Lens à partir du schéma du modèle.

Le rapport est décrit ici, en code : tables, colonnes, relations, mesures DAX
et pages. pbip-generator écrit ensuite les fichiers TMDL (modèle) et PBIR
(rapport) qui s'ouvrent dans Power BI Desktop. Aucune donnée n'est lue : le
projet charge les CSV de data/model/ au premier « Actualiser ».

Usage :
    pip install -r powerbi/requirements.txt
    python powerbi/build_report.py                       # -> powerbi/VCTMetaLens/
    python powerbi/build_report.py --data-folder "D:\\vct-meta-lens\\data\\model\\"

Le chemin --data-folder est celui où se trouvent les CSV sur la machine qui
ouvre le projet. Il reste modifiable ensuite dans Power BI (Transformer les
données > Paramètres > DataFolder).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pbip_generator import mquery
from pbip_generator.builder import write_project
from pbip_generator.model import (
    Column,
    DataType,
    FieldRef,
    Measure,
    Page,
    Project,
    Relationship,
    Source,
    Table,
    TableRole,
    Visual,
)

NAME = "VCTMetaLens"
DEFAULT_DATA_FOLDER = "C:\\pbip\\vct-meta-lens\\data\\model\\"
OUT_DIR = Path(__file__).resolve().parent
THEME = OUT_DIR / "theme.json"

S, I, D, B = DataType.STRING, DataType.INT64, DataType.DOUBLE, DataType.BOOLEAN
MATCH = [("tournament", S), ("stage", S), ("match_type", S)]

# --------------------------------------------------------------------------- #
# Schéma : seules les colonnes utiles au rapport sont chargées.
# Les noms suivent la sortie de src/build_model.py (voir docs/data_model.md).
# --------------------------------------------------------------------------- #
SCHEMA: dict[str, tuple[TableRole, list[tuple[str, DataType]]]] = {
    "dim_tournament": (
        TableRole.DIMENSION,
        [
            ("tournament", S),
            ("tournament_short", S),
            ("season_order", I),
            ("region", S),
            ("tier", S),
            ("phase_order", I),
        ],
    ),
    "dim_agent": (TableRole.DIMENSION, [("agent", S), ("agent_label", S), ("role", S)]),
    "dim_map": (TableRole.DIMENSION, [("map", S)]),
    "dim_team": (TableRole.DIMENSION, [("team", S), ("team_abbr", S)]),
    "dim_player": (TableRole.DIMENSION, [("player", S)]),
    "fact_agent_picks": (
        TableRole.FACT,
        MATCH + [("map", S), ("agent", S), ("pick_rate", D), ("maps_played", I)],
    ),
    "fact_map_stats": (
        TableRole.FACT,
        MATCH
        + [
            ("map", S),
            ("total_maps_played", I),
            ("attacker_side_win_percentage", D),
            ("defender_side_win_percentage", D),
        ],
    ),
    "fact_team_agent_map": (
        TableRole.FACT,
        MATCH
        + [
            ("map", S),
            ("team", S),
            ("agent", S),
            ("total_wins_by_map", I),
            ("total_maps_played", I),
        ],
    ),
    "fact_player_map": (
        TableRole.FACT,
        MATCH
        + [
            ("match_name", S),
            ("map", S),
            ("player", S),
            ("team", S),
            ("agent", S),
            ("rating", D),
            ("average_combat_score", D),
            ("kills", D),
            ("deaths", D),
            ("assists", D),
            ("average_damage_per_round", D),
            ("first_kills", D),
            ("first_deaths", D),
            ("headshot_pct", D),
            ("kast_pct", D),
        ],
    ),
    "fact_match_team": (
        TableRole.FACT,
        MATCH
        + [
            ("match_name", S),
            ("team", S),
            ("opponent", S),
            ("maps_won", I),
            ("maps_lost", I),
            ("won", B),
        ],
    ),
    "fact_eco": (
        TableRole.FACT,
        MATCH + [("match_name", S), ("map", S), ("team", S), ("buy_category", S), ("initiated", D), ("won", D)],
    ),
    "fact_round_methods": (
        TableRole.FACT,
        MATCH + [("match_name", S), ("map", S), ("round_number", I), ("team", S), ("method", S), ("outcome", S)],
    ),
    "fact_draft": (
        TableRole.FACT,
        MATCH + [("match_name", S), ("team", S), ("action", S), ("map", S)],
    ),
    "fact_multikills": (
        TableRole.FACT,
        MATCH
        + [
            ("match_name", S),
            ("map", S),
            ("team", S),
            ("player", S),
            ("agent", S),
            ("2k", D),
            ("3k", D),
            ("4k", D),
            ("5k", D),
            ("1v1", D),
            ("1v2", D),
            ("1v3", D),
            ("1v4", D),
            ("1v5", D),
            ("spike_plants", I),
            ("spike_defuses", I),
        ],
    ),
    "fact_map_score": (
        TableRole.FACT,
        MATCH
        + [
            ("match_name", S),
            ("map", S),
            ("team_a_score", I),
            ("team_b_score", I),
            ("team_a_overtime_score", D),
            ("team_b_overtime_score", D),
            ("duration_seconds", D),
        ],
    ),
}

# Chaque fait est relié aux dimensions dont il porte la clé.
DIM_KEYS = {
    "tournament": "dim_tournament",
    "map": "dim_map",
    "agent": "dim_agent",
    "team": "dim_team",
    "player": "dim_player",
}

# Libellés triés par une colonne d'ordre (chronologie de la saison).
SORT_BY = {("dim_tournament", "tournament_short"): "season_order", ("dim_tournament", "tier"): "phase_order"}


# --------------------------------------------------------------------------- #
# Mesures (DAX). Les pourcentages de la source sont sur 0-100 : on divise par 100.
# --------------------------------------------------------------------------- #
MEASURES: dict[str, list[Measure]] = {
    "fact_agent_picks": [
        Measure(
            "Pick rate %",
            "DIVIDE (\n"
            "    SUMX ( fact_agent_picks, fact_agent_picks[pick_rate] * fact_agent_picks[maps_played] ),\n"
            "    SUM ( fact_agent_picks[maps_played] )\n"
            ") / 100",
            "0.0%",
            "Méta agents",
            "Pick rate pondéré par le nombre de maps jouées (jamais une moyenne simple des pourcentages).",
        ),
        Measure(
            "Agents joués",
            "CALCULATE ( DISTINCTCOUNT ( fact_agent_picks[agent] ), fact_agent_picks[pick_rate] > 0 )",
            "0",
            "Méta agents",
        ),
    ],
    "fact_map_stats": [
        Measure("Maps jouées", "SUM ( fact_map_stats[total_maps_played] )", "#,0", "Maps"),
        Measure(
            "Winrate attaque %",
            "DIVIDE (\n"
            "    SUMX ( fact_map_stats, fact_map_stats[attacker_side_win_percentage] * fact_map_stats[total_maps_played] ),\n"
            "    [Maps jouées]\n"
            ") / 100",
            "0.0%",
            "Maps",
        ),
        Measure(
            "Winrate défense %",
            "DIVIDE (\n"
            "    SUMX ( fact_map_stats, fact_map_stats[defender_side_win_percentage] * fact_map_stats[total_maps_played] ),\n"
            "    [Maps jouées]\n"
            ") / 100",
            "0.0%",
            "Maps",
        ),
        Measure("Écart DEF - ATK (pts)", "( [Winrate défense %] - [Winrate attaque %] ) * 100", "+0.0;-0.0;0.0", "Maps"),
    ],
    "fact_round_methods": [
        Measure(
            "Rounds gagnés",
            'CALCULATE ( COUNTROWS ( fact_round_methods ), fact_round_methods[outcome] = "Win" )',
            "#,0",
            "Maps",
        ),
        Measure(
            "Part des rounds gagnés %",
            "DIVIDE ( [Rounds gagnés], CALCULATE ( [Rounds gagnés], REMOVEFILTERS ( fact_round_methods[method] ) ) )",
            "0.0%",
            "Maps",
        ),
    ],
    "fact_draft": [
        Measure("Actions de draft", "COUNTROWS ( fact_draft )", "#,0", "Maps"),
    ],
    "fact_match_team": [
        Measure("Matchs", "COUNTROWS ( fact_match_team )", "#,0", "Équipes"),
        Measure(
            "Victoires", "CALCULATE ( COUNTROWS ( fact_match_team ), fact_match_team[won] = TRUE () )", "#,0", "Équipes"
        ),
        Measure("Winrate matchs %", "DIVIDE ( [Victoires], [Matchs] )", "0.0%", "Équipes"),
        Measure(
            "Maps gagnées %",
            "DIVIDE (\n"
            "    SUM ( fact_match_team[maps_won] ),\n"
            "    SUM ( fact_match_team[maps_won] ) + SUM ( fact_match_team[maps_lost] )\n"
            ")",
            "0.0%",
            "Équipes",
        ),
    ],
    "fact_eco": [
        Measure("Rounds éco joués", "SUM ( fact_eco[initiated] )", "#,0", "Équipes"),
        Measure("Conversion éco %", "DIVIDE ( SUM ( fact_eco[won] ), SUM ( fact_eco[initiated] ) )", "0.0%", "Équipes"),
        Measure(
            "Pistols gagnés %",
            'CALCULATE ( [Conversion éco %], fact_eco[buy_category] = "Pistol" )',
            "0.0%",
            "Équipes",
        ),
    ],
    "fact_multikills": [
        Measure(
            "Clutchs gagnés",
            "SUM ( fact_multikills[1v1] ) + SUM ( fact_multikills[1v2] ) + SUM ( fact_multikills[1v3] )\n"
            "    + SUM ( fact_multikills[1v4] ) + SUM ( fact_multikills[1v5] )",
            "#,0",
            "Duels",
        ),
        Measure(
            "Clutchs 1v3+",
            "SUM ( fact_multikills[1v3] ) + SUM ( fact_multikills[1v4] ) + SUM ( fact_multikills[1v5] )",
            "#,0",
            "Duels",
        ),
        Measure(
            "Clutchs par map",
            "DIVIDE ( [Clutchs gagnés], COUNTROWS ( fact_multikills ) )",
            "0.00",
            "Duels",
            "Une ligne de fact_multikills = un joueur sur une map.",
        ),
        Measure("Multikills 2K", "SUM ( fact_multikills[2k] )", "#,0", "Duels"),
        Measure("Multikills 3K", "SUM ( fact_multikills[3k] )", "#,0", "Duels"),
        Measure("Multikills 4K", "SUM ( fact_multikills[4k] )", "#,0", "Duels"),
        Measure("Aces", "SUM ( fact_multikills[5k] )", "#,0", "Duels"),
        Measure("Multikills 3K+", "[Multikills 3K] + [Multikills 4K] + [Aces]", "#,0", "Duels"),
        Measure("Spikes plantés", "SUM ( fact_multikills[spike_plants] )", "#,0", "Duels"),
        Measure("Spikes désamorcés", "SUM ( fact_multikills[spike_defuses] )", "#,0", "Duels"),
    ],
    "fact_map_score": [
        Measure("Maps (scores)", "COUNTROWS ( fact_map_score )", "#,0", "Maps"),
        Measure("Durée moyenne (min)", "AVERAGE ( fact_map_score[duration_seconds] ) / 60", "0.0", "Maps"),
        Measure(
            "Prolongations %",
            "DIVIDE (\n"
            "    COUNTROWS (\n"
            "        FILTER (\n"
            "            fact_map_score,\n"
            "            fact_map_score[team_a_overtime_score] + fact_map_score[team_b_overtime_score] > 0\n"
            "        )\n"
            "    ),\n"
            "    [Maps (scores)]\n"
            ")",
            "0.0%",
            "Maps",
            "Part des maps allées en prolongation (au moins un round d'overtime).",
        ),
        Measure(
            "Écart de score moyen",
            "AVERAGEX ( fact_map_score, ABS ( fact_map_score[team_a_score] - fact_map_score[team_b_score] ) )",
            "0.0",
            "Maps",
        ),
        Measure(
            "Rounds par map",
            "AVERAGEX ( fact_map_score, fact_map_score[team_a_score] + fact_map_score[team_b_score] )",
            "0.0",
            "Maps",
        ),
    ],
    "fact_team_agent_map": [
        Measure(
            "Maps avec l'agent",
            "SUM ( fact_team_agent_map[total_maps_played] )",
            "#,0",
            "Méta agents",
            "Maps où l'équipe a aligné l'agent (une map compte une fois par agent de la compo).",
        ),
        Measure(
            "Winrate compo %",
            "DIVIDE ( SUM ( fact_team_agent_map[total_wins_by_map] ), SUM ( fact_team_agent_map[total_maps_played] ) )",
            "0.0%",
            "Méta agents",
            "Part des maps gagnées quand l'équipe joue l'agent.",
        ),
    ],
    "fact_player_map": [
        Measure("Maps joueur", "COUNTROWS ( fact_player_map )", "#,0", "Joueurs"),
        Measure("Rating moyen", "AVERAGE ( fact_player_map[rating] )", "0.00", "Joueurs"),
        Measure("ACS moyen", "AVERAGE ( fact_player_map[average_combat_score] )", "0", "Joueurs"),
        Measure("ADR moyen", "AVERAGE ( fact_player_map[average_damage_per_round] )", "0", "Joueurs"),
        Measure("K/D", "DIVIDE ( SUM ( fact_player_map[kills] ), SUM ( fact_player_map[deaths] ) )", "0.00", "Joueurs"),
        Measure(
            "FK/FD",
            "DIVIDE ( SUM ( fact_player_map[first_kills] ), SUM ( fact_player_map[first_deaths] ) )",
            "0.00",
            "Joueurs",
        ),
        Measure("HS %", "AVERAGE ( fact_player_map[headshot_pct] ) / 100", "0.0%", "Joueurs"),
        Measure("KAST %", "AVERAGE ( fact_player_map[kast_pct] ) / 100", "0.0%", "Joueurs"),
        Measure(
            "Rating (10 maps min.)",
            "IF ( [Maps joueur] >= 10, [Rating moyen] )",
            "0.00",
            "Joueurs",
            "Vide sous 10 maps : évite qu'un remplaçant à 2 maps domine le classement.",
        ),
        Measure("ACS (10 maps min.)", "IF ( [Maps joueur] >= 10, [ACS moyen] )", "0", "Joueurs"),
    ],
}


# --------------------------------------------------------------------------- #
# Construction du modèle
# --------------------------------------------------------------------------- #
def build_project(data_folder: str) -> Project:
    tables: list[Table] = []
    for name, (role, cols) in SCHEMA.items():
        columns = []
        for cname, dtype in cols:
            numeric = dtype in (DataType.INT64, DataType.DOUBLE)
            is_key = cname in DIM_KEYS and role == TableRole.FACT
            columns.append(
                Column(
                    cname,
                    dtype,
                    # Clés des faits et colonnes numériques brutes masquées : le
                    # rapport passe par les mesures, jamais par une somme implicite.
                    is_hidden=is_key or cname in ("season_order", "phase_order") or (numeric and role == TableRole.FACT),
                    summarize_by="sum" if numeric and not cname.endswith("_order") and cname != "round_number" else "none",
                    sort_by_column=SORT_BY.get((name, cname)),
                )
            )
        table = Table(name, columns, Source(kind="csv", file_name=f"{name}.csv"), role=role)
        table.measures = list(MEASURES.get(name, []))
        tables.append(table)

    relationships = [
        Relationship(name, col, DIM_KEYS[col], col)
        for name, (role, cols) in SCHEMA.items()
        if role == TableRole.FACT
        for col, _ in cols
        if col in DIM_KEYS
    ]
    check_unique_names(tables)
    project = Project(NAME, tables, relationships, culture="fr-FR", data_folder=data_folder)
    project.theme = json.loads(THEME.read_text(encoding="utf-8"))
    project.pages = build_pages()
    return project


# --------------------------------------------------------------------------- #
# Pages (1280 x 720)
# --------------------------------------------------------------------------- #
def check_unique_names(tables: list[Table]) -> None:
    """Échoue si deux objets du modèle portent le même nom.

    Le moteur tabulaire compare les noms sans tenir compte de la casse : une
    mesure '2K' et une colonne '2k' de la même table se heurtent, et Power BI
    refuse d'ouvrir le projet. Les noms de mesures sont aussi uniques sur tout
    le modèle.
    """
    errors: list[str] = []
    seen_measures: dict[str, str] = {}
    for table in tables:
        seen_columns = {c.name.casefold(): c.name for c in table.columns}
        for measure in table.measures:
            key = measure.name.casefold()
            if key in seen_columns:
                errors.append(f"{table.name} : la mesure '{measure.name}' a le même nom que la colonne '{seen_columns[key]}'")
            if key in seen_measures:
                errors.append(f"la mesure '{measure.name}' existe déjà dans {seen_measures[key]}")
            seen_measures[key] = table.name
    if errors:
        raise ValueError("Noms en double dans le modèle (casse ignorée) :\n  " + "\n  ".join(errors))


def col(table: str, name: str) -> FieldRef:
    return FieldRef(table, name)


def mes(table: str, name: str) -> FieldRef:
    return FieldRef(table, name, is_measure=True)


W, H, M, G = 1280, 720, 16, 16
SLICER_H, CARD_H = 60, 96


def page_title(text: str) -> Visual:
    return Visual("textbox", {}, M, M, 520, SLICER_H, text=text, text_size=24)


def slicers(*fields: tuple[FieldRef, str]) -> list[Visual]:
    """Segments alignés à droite du bandeau supérieur."""
    width = 220
    start = W - M - len(fields) * width - (len(fields) - 1) * G
    return [
        Visual("slicer", {"Values": [field]}, start + i * (width + G), M, width, SLICER_H, title=label)
        for i, (field, label) in enumerate(fields)
    ]


def cards(refs: list[FieldRef], y: float) -> list[Visual]:
    n = len(refs)
    w = (W - 2 * M - (n - 1) * G) / n
    return [Visual("card", {"Values": [r]}, M + i * (w + G), y, w, CARD_H, title=r.name) for i, r in enumerate(refs)]


TOURNOI = col("dim_tournament", "tournament_short")
REGION = col("dim_tournament", "region")
TIER = col("dim_tournament", "tier")
ROLE = col("dim_agent", "role")
AGENT = col("dim_agent", "agent_label")
MAP = col("dim_map", "map")
TEAM = col("dim_team", "team")
PLAYER = col("dim_player", "player")


def build_pages() -> list[Page]:
    top = M + SLICER_H + G
    body = top + CARD_H + G
    half = (W - 2 * M - G) / 2
    body_h = H - body - M

    meta = Page("Méta agents")
    meta.visuals.append(page_title("Méta des agents"))
    meta.visuals += slicers((REGION, "Région"), (TIER, "Phase"), (MAP, "Map"))
    meta.visuals += cards(
        [mes("fact_agent_picks", "Agents joués"), mes("fact_map_stats", "Maps jouées"), mes("fact_team_agent_map", "Winrate compo %")],
        top,
    )
    meta.visuals += [
        Visual(
            "lineChart",
            {"Category": [TOURNOI], "Y": [mes("fact_agent_picks", "Pick rate %")], "Series": [ROLE]},
            M,
            body,
            half,
            body_h,
            title="Pick rate par rôle au fil de la saison",
            sort_by=TOURNOI,
            sort_descending=False,
        ),
        Visual(
            "clusteredBarChart",
            {"Category": [AGENT], "Y": [mes("fact_agent_picks", "Pick rate %")]},
            M + half + G,
            body,
            half,
            body_h,
            title="Agents les plus joués",
            sort_by=mes("fact_agent_picks", "Pick rate %"),
        ),
    ]

    maps = Page("Maps")
    maps.visuals.append(page_title("Maps"))
    maps.visuals += slicers((REGION, "Région"), (TIER, "Phase"))
    maps.visuals += cards(
        [
            mes("fact_map_stats", "Maps jouées"),
            mes("fact_map_stats", "Winrate attaque %"),
            mes("fact_map_stats", "Winrate défense %"),
            mes("fact_map_stats", "Écart DEF - ATK (pts)"),
        ],
        top,
    )
    third = (W - 2 * M - 2 * G) / 3
    maps.visuals += [
        Visual(
            "clusteredBarChart",
            {"Category": [MAP], "Y": [mes("fact_map_stats", "Winrate attaque %"), mes("fact_map_stats", "Winrate défense %")]},
            M,
            body,
            third,
            body_h,
            title="Winrate attaque et défense par map",
            sort_by=mes("fact_map_stats", "Winrate défense %"),
        ),
        Visual(
            "clusteredColumnChart",
            {"Category": [col("fact_round_methods", "method")], "Y": [mes("fact_round_methods", "Part des rounds gagnés %")]},
            M + third + G,
            body,
            third,
            body_h,
            title="Comment les rounds sont gagnés",
            sort_by=mes("fact_round_methods", "Part des rounds gagnés %"),
        ),
        Visual(
            "clusteredBarChart",
            {
                "Category": [MAP],
                "Y": [mes("fact_draft", "Actions de draft")],
                "Series": [col("fact_draft", "action")],
            },
            M + 2 * (third + G),
            body,
            third,
            body_h,
            title="Picks et bans par map",
            sort_by=mes("fact_draft", "Actions de draft"),
        ),
    ]

    teams = Page("Équipes")
    teams.visuals.append(page_title("Équipes"))
    teams.visuals += slicers((REGION, "Région"), (TIER, "Phase"))
    teams.visuals += cards(
        [
            mes("fact_match_team", "Matchs"),
            mes("fact_match_team", "Winrate matchs %"),
            mes("fact_eco", "Pistols gagnés %"),
            mes("fact_eco", "Conversion éco %"),
        ],
        top,
    )
    wide = (W - 2 * M - G) * 0.6
    teams.visuals += [
        Visual(
            "tableEx",
            {
                "Values": [
                    TEAM,
                    mes("fact_match_team", "Matchs"),
                    mes("fact_match_team", "Winrate matchs %"),
                    mes("fact_match_team", "Maps gagnées %"),
                    mes("fact_eco", "Pistols gagnés %"),
                    mes("fact_eco", "Conversion éco %"),
                ]
            },
            M,
            body,
            wide,
            body_h,
            title="Classement des équipes",
            sort_by=mes("fact_match_team", "Winrate matchs %"),
        ),
        Visual(
            "clusteredBarChart",
            {"Category": [col("fact_eco", "buy_category")], "Y": [mes("fact_eco", "Conversion éco %")]},
            M + wide + G,
            body,
            W - 2 * M - G - wide,
            body_h,
            title="Taux de victoire selon l'achat",
            sort_by=mes("fact_eco", "Conversion éco %"),
        ),
    ]

    players = Page("Joueurs")
    players.visuals.append(page_title("Joueurs"))
    players.visuals += slicers((REGION, "Région"), (TIER, "Phase"), (ROLE, "Rôle"))
    players.visuals += cards(
        [
            mes("fact_player_map", "Maps joueur"),
            mes("fact_player_map", "Rating moyen"),
            mes("fact_player_map", "ACS moyen"),
            mes("fact_player_map", "K/D"),
        ],
        top,
    )
    players.visuals += [
        Visual(
            "scatterChart",
            {
                "Category": [PLAYER],
                "X": [mes("fact_player_map", "ACS (10 maps min.)")],
                "Y": [mes("fact_player_map", "Rating (10 maps min.)")],
                "Size": [mes("fact_player_map", "Maps joueur")],
            },
            M,
            body,
            half,
            body_h,
            title="Rating et ACS (10 maps minimum)",
        ),
        Visual(
            "tableEx",
            {
                "Values": [
                    PLAYER,
                    mes("fact_player_map", "Maps joueur"),
                    mes("fact_player_map", "Rating (10 maps min.)"),
                    mes("fact_player_map", "ACS moyen"),
                    mes("fact_player_map", "K/D"),
                    mes("fact_player_map", "FK/FD"),
                    mes("fact_player_map", "HS %"),
                ]
            },
            M + half + G,
            body,
            half,
            body_h,
            title="Meilleurs joueurs",
            sort_by=mes("fact_player_map", "Rating (10 maps min.)"),
        ),
    ]
    duels = Page("Duels et clutchs")
    duels.visuals.append(page_title("Duels et clutchs"))
    duels.visuals += slicers((REGION, "Région"), (TIER, "Phase"), (ROLE, "Rôle"))
    duels.visuals += cards(
        [
            mes("fact_multikills", "Clutchs gagnés"),
            mes("fact_multikills", "Clutchs 1v3+"),
            mes("fact_multikills", "Multikills 3K+"),
            mes("fact_multikills", "Aces"),
            mes("fact_multikills", "Spikes plantés"),
        ],
        top,
    )
    duels.visuals += [
        Visual(
            "tableEx",
            {
                "Values": [
                    PLAYER,
                    mes("fact_multikills", "Clutchs gagnés"),
                    mes("fact_multikills", "Clutchs 1v3+"),
                    mes("fact_multikills", "Clutchs par map"),
                    mes("fact_multikills", "Multikills 3K"),
                    mes("fact_multikills", "Multikills 4K"),
                    mes("fact_multikills", "Aces"),
                ]
            },
            M,
            body,
            wide,
            body_h,
            title="Joueurs décisifs",
            sort_by=mes("fact_multikills", "Clutchs gagnés"),
        ),
        Visual(
            "clusteredBarChart",
            {"Category": [AGENT], "Y": [mes("fact_multikills", "Clutchs par map")]},
            M + wide + G,
            body,
            W - 2 * M - G - wide,
            body_h,
            title="Clutchs par map selon l'agent",
            sort_by=mes("fact_multikills", "Clutchs par map"),
        ),
    ]

    scores = Page("Scores et durée")
    scores.visuals.append(page_title("Scores et durée des maps"))
    scores.visuals += slicers((REGION, "Région"), (TIER, "Phase"))
    scores.visuals += cards(
        [
            mes("fact_map_score", "Maps (scores)"),
            mes("fact_map_score", "Durée moyenne (min)"),
            mes("fact_map_score", "Prolongations %"),
            mes("fact_map_score", "Écart de score moyen"),
        ],
        top,
    )
    scores.visuals += [
        Visual(
            "clusteredBarChart",
            {"Category": [MAP], "Y": [mes("fact_map_score", "Durée moyenne (min)")]},
            M,
            body,
            third,
            body_h,
            title="Durée moyenne par map (min)",
            sort_by=mes("fact_map_score", "Durée moyenne (min)"),
        ),
        Visual(
            "clusteredBarChart",
            {"Category": [MAP], "Y": [mes("fact_map_score", "Prolongations %")]},
            M + third + G,
            body,
            third,
            body_h,
            title="Maps les plus serrées (prolongations)",
            sort_by=mes("fact_map_score", "Prolongations %"),
        ),
        Visual(
            "lineChart",
            {"Category": [TOURNOI], "Y": [mes("fact_map_score", "Rounds par map")]},
            M + 2 * (third + G),
            body,
            third,
            body_h,
            title="Rounds par map au fil de la saison",
            sort_by=TOURNOI,
            sort_descending=False,
        ),
    ]

    player = Page("Fiche joueur")
    player.visuals.append(page_title("Fiche joueur"))
    player.visuals += slicers((PLAYER, "Joueur"), (TIER, "Phase"))
    player.visuals += cards(
        [
            mes("fact_player_map", "Maps joueur"),
            mes("fact_player_map", "Rating moyen"),
            mes("fact_player_map", "ACS moyen"),
            mes("fact_player_map", "ADR moyen"),
            mes("fact_player_map", "KAST %"),
            mes("fact_player_map", "FK/FD"),
        ],
        top,
    )
    player.visuals += [
        Visual(
            "lineChart",
            {"Category": [TOURNOI], "Y": [mes("fact_player_map", "Rating moyen")]},
            M,
            body,
            half,
            body_h,
            title="Rating au fil de la saison",
            sort_by=TOURNOI,
            sort_descending=False,
        ),
        Visual(
            "clusteredBarChart",
            {"Category": [AGENT], "Y": [mes("fact_player_map", "Maps joueur")]},
            M + half + G,
            body,
            half,
            body_h,
            title="Agents joués",
            sort_by=mes("fact_player_map", "Maps joueur"),
        ),
    ]

    team = Page("Fiche équipe")
    team.visuals.append(page_title("Fiche équipe"))
    team.visuals += slicers((TEAM, "Équipe"), (TIER, "Phase"))
    team.visuals += cards(
        [
            mes("fact_match_team", "Matchs"),
            mes("fact_match_team", "Winrate matchs %"),
            mes("fact_match_team", "Maps gagnées %"),
            mes("fact_eco", "Pistols gagnés %"),
            mes("fact_eco", "Conversion éco %"),
        ],
        top,
    )
    team.visuals += [
        Visual(
            "clusteredBarChart",
            {"Category": [MAP], "Y": [mes("fact_team_agent_map", "Winrate compo %")]},
            M,
            body,
            third,
            body_h,
            title="Winrate par map",
            sort_by=mes("fact_team_agent_map", "Winrate compo %"),
        ),
        Visual(
            "clusteredBarChart",
            {
                "Category": [MAP],
                "Y": [mes("fact_draft", "Actions de draft")],
                "Series": [col("fact_draft", "action")],
            },
            M + third + G,
            body,
            third,
            body_h,
            title="Picks et bans de l'équipe",
            sort_by=mes("fact_draft", "Actions de draft"),
        ),
        Visual(
            "clusteredBarChart",
            {"Category": [AGENT], "Y": [mes("fact_team_agent_map", "Maps avec l'agent")]},
            M + 2 * (third + G),
            body,
            third,
            body_h,
            title="Agents les plus alignés",
            sort_by=mes("fact_team_agent_map", "Maps avec l'agent"),
        ),
    ]
    return [meta, maps, teams, players, duels, scores, player, team]


# --------------------------------------------------------------------------- #
# Power Query : ne garder que les colonnes déclarées, dans l'ordre déclaré.
# --------------------------------------------------------------------------- #
_original_table_expression = mquery.table_expression


def _select_then_type(project: Project, table: Table) -> str:
    """Ajoute Table.SelectColumns entre l'en-tête et le typage.

    Les CSV du pipeline contiennent plus de colonnes que le rapport n'en
    utilise : sans cette étape, Power BI chargerait des colonnes absentes du
    modèle et l'actualisation échouerait.
    """
    expr = _original_table_expression(project, table)
    names = ", ".join(mquery.m_string(c.source_column) for c in table.columns)
    select = f'    #"Selected Columns" = Table.SelectColumns(#"Promoted Headers", {{{names}}}),'
    anchor = '    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers",'
    if anchor not in expr:
        raise RuntimeError("Expression Power Query inattendue : pbip-generator a changé de format")
    return expr.replace(anchor, select + '\n    #"Changed Type" = Table.TransformColumnTypes(#"Selected Columns",')


mquery.table_expression = _select_then_type


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-folder", default=DEFAULT_DATA_FOLDER)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    folder = args.data_folder if args.data_folder.endswith(("\\", "/")) else args.data_folder + "\\"
    root = write_project(build_project(folder), args.out, overwrite=True, strict=True)
    print(f"Projet Power BI écrit dans {root}")


if __name__ == "__main__":
    main()
