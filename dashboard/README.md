# Dashboard Power BI

Le fichier `.pbix` sera versionné ici.

## Import des données
1. Power BI Desktop → Obtenir les données → Texte/CSV
2. Importer les 17 fichiers de `data/model/` (encodage UTF-8, détecté automatiquement grâce au BOM)
3. Relations (Vue Modèle) :
   - `fact_* [tournament]`  →  `dim_tournament [tournament]`  (plusieurs-à-un)
   - `fact_agent_picks / fact_team_agent_map / fact_multikills [agent(s)]`  →  `dim_agent [agent]`
   - `fact_* [map]`  →  `dim_map [map]`
   - `fact_* [team]`  →  `dim_team [team]`
   - `fact_player_* [player]`  →  `dim_player [player]`
4. Trier `dim_tournament[tournament]` par `season_order` (Colonne → Trier par colonne)
   pour que les axes temporels respectent la chronologie de la saison.

## Garde-fous
- Ne jamais importer les CSV de `data/raw/` directement : ils contiennent des
  lignes d'agrégats qui faussent toutes les mesures (voir README racine).
- `fact_agent_picks.pick_rate` est déjà un pourcentage par tournoi/stage/match_type/map :
  l'agréger à un niveau supérieur exige une moyenne pondérée par maps jouées
  (via `fact_map_stats.total_maps_played`), pas une moyenne simple.
