# Dictionnaire du modèle de données

Tables de `data/model/` (générées par `src/build_model.py`).
Granularité : lignes de détail uniquement, agrégats `All *` exclus.

## `dim_agent` — 27 lignes

| Colonne | Type |
|---|---|
| `agent` | str |
| `role` | str |

## `dim_map` — 11 lignes

| Colonne | Type |
|---|---|
| `map` | str |

## `dim_player` — 349 lignes

| Colonne | Type |
|---|---|
| `player` | str |
| `player_id` | float64 |

## `dim_team` — 59 lignes

| Colonne | Type |
|---|---|
| `team` | str |
| `team_abbr` | str |
| `team_id` | float64 |

## `dim_tournament` — 15 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `season_order` | int64 |
| `region` | str |
| `tier` | str |

## `fact_agent_picks` — 22 005 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `map` | str |
| `agent` | str |
| `pick_rate` | int64 |

## `fact_draft` — 2 988 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `team` | str |
| `action` | str |
| `map` | str |
| `is_map_agg` | bool |
| `is_stage_agg` | bool |
| `is_match_type_agg` | bool |

## `fact_eco` — 13 940 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `map` | str |
| `team` | str |
| `initiated` | float64 |
| `won` | int64 |
| `buy_category` | str |
| `win_rate` | float64 |

## `fact_eco_rounds` — 25 182 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `map` | str |
| `round_number` | int64 |
| `team` | str |
| `loadout_value` | float64 |
| `remaining_credits` | int64 |
| `type` | str |
| `outcome` | str |
| `won` | bool |

## `fact_map_score` — 1 277 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `map` | str |
| `team_a` | str |
| `team_a_score` | int64 |
| `team_a_attacker_score` | int64 |
| `team_a_defender_score` | int64 |
| `team_a_overtime_score` | float64 |
| `team_b` | str |
| `team_b_score` | int64 |
| `team_b_attacker_score` | int64 |
| `team_b_defender_score` | int64 |
| `team_b_overtime_score` | float64 |
| `duration` | str |
| `duration_seconds` | float64 |
| `winner` | str |

## `fact_map_stats` — 815 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `map` | str |
| `total_maps_played` | int64 |
| `attacker_side_win_percentage` | int64 |
| `defender_side_win_percentage` | int64 |

## `fact_match` — 503 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `team_a` | str |
| `team_b` | str |
| `team_a_score` | int64 |
| `team_b_score` | int64 |
| `match_result` | str |
| `winner` | str |

## `fact_multikills` — 13 912 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `map` | str |
| `team` | str |
| `player` | str |
| `agents` | str |
| `2k` | float64 |
| `3k` | float64 |
| `4k` | float64 |
| `5k` | float64 |
| `1v1` | float64 |
| `1v2` | float64 |
| `1v3` | float64 |
| `1v4` | float64 |
| `1v5` | float64 |
| `econ` | int64 |
| `spike_plants` | int64 |
| `spike_defuses` | int64 |
| `is_map_agg` | bool |
| `is_stage_agg` | bool |
| `is_match_type_agg` | bool |

## `fact_player_map` — 17 742 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `map` | str |
| `player` | str |
| `team` | str |
| `agents` | str |
| `rating` | float64 |
| `average_combat_score` | float64 |
| `kills` | float64 |
| `deaths` | float64 |
| `assists` | float64 |
| `kd_diff` | float64 |
| `kill_assist_trade_survive_` | str |
| `average_damage_per_round` | float64 |
| `headshot_` | str |
| `first_kills` | float64 |
| `first_deaths` | float64 |
| `fkd_diff` | float64 |

## `fact_player_stage` — 13 705 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `player` | str |
| `teams` | str |
| `agents` | str |
| `rounds_played` | int64 |
| `rating` | float64 |
| `average_combat_score` | float64 |
| `kd_ratio` | float64 |
| `kill_assist_trade_survive_` | str |
| `average_damage_per_round` | float64 |
| `kills_per_round` | float64 |
| `assists_per_round` | float64 |
| `first_kills_per_round` | float64 |
| `first_deaths_per_round` | float64 |
| `headshot_` | str |
| `clutch_success_` | str |
| `clutches_wonplayed` | str |
| `maximum_kills_in_a_single_map` | int64 |
| `kills` | int64 |
| `deaths` | int64 |
| `assists` | int64 |
| `first_kills` | int64 |
| `first_deaths` | int64 |

## `fact_round_methods` — 53 950 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `match_name` | str |
| `map` | str |
| `round_number` | int64 |
| `team` | str |
| `method` | str |
| `outcome` | str |
| `is_map_agg` | bool |
| `is_stage_agg` | bool |
| `is_match_type_agg` | bool |

## `fact_team_agent_map` — 12 590 lignes

| Colonne | Type |
|---|---|
| `tournament` | str |
| `stage` | str |
| `match_type` | str |
| `map` | str |
| `team` | str |
| `agent` | str |
| `total_wins_by_map` | int64 |
| `total_loss_by_map` | int64 |
| `total_maps_played` | int64 |
