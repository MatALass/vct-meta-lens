# VCT Meta Lens

**How the Valorant pro meta evolved across the 2025 VCT season** : un pipeline de données et un dashboard Power BI couvrant 15 tournois, 59 équipes, 349 joueurs et plus de 100 000 kills (données VLR.gg, du Kickoff jusqu'à Valorant Champions 2025).

## Le projet

Les sites de stats esport (VLR.gg en tête) montrent des photographies instantanées. Ce projet reconstruit la **dynamique d'une saison complète** : montée et chute des agents dans le méta (Tejo, Waylay, Vyse…), équilibre attaque/défense des maps, conversion économique des équipes, performances joueurs, le tout comparable entre les 4 régions (Americas, EMEA, Pacific, China) et les événements internationaux.

```
Kaggle (CSV VLR.gg)  →  src/clean.py  →  data/processed/ (parquet typés)
                                       →  src/build_model.py  →  data/model/ (étoile, CSV)
                                                              →  powerbi/build_report.py
                                                              →  powerbi/VCTMetaLens (PBIP)
```

## Structure

```
vct-meta-lens/
├── data/
│   ├── raw/vct_2025/        # CSV bruts Kaggle (non versionnés, voir src/ingest.py)
│   ├── processed/           # parquet nettoyés, toutes granularités conservées
│   └── model/               # modèle en étoile (CSV UTF-8 BOM) → import Power BI
├── src/
│   ├── config.py            # référentiels : ordre des tournois, régions, rôles d'agents
│   ├── ingest.py            # téléchargement reproductible depuis Kaggle
│   ├── clean.py             # typage, %→float, crédits→int, flags d'agrégats
│   ├── build_model.py       # dimensions + faits, contrôles d'intégrité
│   └── document_model.py    # régénère docs/data_model.md
├── powerbi/
│   ├── build_report.py      # le rapport décrit en code (modèle, mesures, pages)
│   └── VCTMetaLens/         # projet PBIP généré (TMDL + PBIR), s'ouvre dans Power BI
├── tests/                   # pytest : nettoyage, modèle, cohérence du rapport
├── notebooks/
│   └── 01_exploration.ipynb # validation du pipeline + premières tendances méta
├── docs/
│   └── data_model.md        # dictionnaire des tables du modèle
└── .github/workflows/       # CI : tests + projet PBIP à jour
```

## Démarrage rapide

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m src.ingest        # télécharge les données Kaggle dans data/raw/
python -m src.clean         # → data/processed/*.parquet
python -m src.build_model   # → data/model/*.csv
pytest -q                   # tests du pipeline et du rapport
```

Puis ouvrir `powerbi/VCTMetaLens/VCTMetaLens.pbip` dans Power BI Desktop et cliquer sur **Actualiser** (détails dans [`powerbi/README.md`](powerbi/README.md)).

## Les pièges du dataset (et comment ils sont traités)

Le dataset VLR.gg est riche mais piégeux ; un `groupby` naïf produit des chiffres faux.

1. **Agrégats mélangés au détail.** `agents_pick_rates`, `maps_stats`, `players_stats` et `teams_picked_agents` contiennent des lignes `All Maps` / `All Stages` / `All Match Types` au milieu des lignes détaillées → double comptage garanti. `clean.py` pose des flags `is_*_agg` ; `build_model.py` n'exporte que le détail dans les tables de faits.
2. **Types texte.** Les pourcentages sont des strings (`"95%"`), les crédits aussi (`"3.9k"`), les durées mélangent `MM:SS` et `H:MM:SS`. Tout est converti en numérique.
3. **NaN structurels.** Dans `overview`, chaque joueur a jusqu'à 3 lignes par carte (`side` = both/attack/defend) et les stats par side sont partiellement absentes. `fact_player_map` ne garde que `side == "both"` ; le détail par side reste dans `data/processed/overview.parquet`.
4. **Pourcentages moyennés à tort.** `pick_rate` est un pourcentage par map et par stage : la moyenne simple donne autant de poids à une map jouée une fois qu'à une map jouée 40 fois. `fact_agent_picks` porte donc `maps_played` et la mesure Power BI pondère.
5. **Référentiels incomplets.** L'ordre chronologique des tournois et les rôles des agents n'existent pas dans la source : ils sont maintenus dans `src/config.py`. Les équipes hors circuit (showmatchs) absentes de `team_mapping` sont ajoutées à `dim_team` avec un warning.

## Modèle de données (étoile)

| Dimensions | Faits |
|---|---|
| `dim_tournament` (ordre saison, région, tier) | `fact_agent_picks` · `fact_map_stats` · `fact_team_agent_map` |
| `dim_agent` (rôle) | `fact_player_map` · `fact_player_stage` |
| `dim_map` · `dim_team` · `dim_player` | `fact_match` · `fact_map_score` · `fact_draft` |
| | `fact_eco` · `fact_eco_rounds` · `fact_round_methods` · `fact_multikills` |
| | `bridge_player_stage_agent` (agents joués par joueur et par stage) |

Détail des colonnes : [`docs/data_model.md`](docs/data_model.md).

## Rapport Power BI

Quatre pages, générées par `powerbi/build_report.py` :

1. **Méta agents** : pick rate pondéré par rôle au fil de la saison, agents les plus joués, winrate des compositions.
2. **Maps** : winrate attaque et défense par map, méthodes de victoire des rounds, picks et bans.
3. **Équipes** : classement (winrate, maps gagnées, pistols, conversion éco), taux de victoire par type d'achat.
4. **Joueurs** : nuage Rating × ACS (10 maps minimum), classement des joueurs.

Le choix du PBIP plutôt qu'un `.pbix` : le modèle et le rapport sont du texte, donc chaque mesure se relit et se compare dans une pull request.

## Source des données

[Valorant Champion Tour, VLR.gg scrapes (Kaggle)](https://www.kaggle.com/datasets/ryanluong1/valorant-champion-tour-2021-2023-data), saison 2025. Données © Riot Games / VLR.gg, usage analytique non commercial.
