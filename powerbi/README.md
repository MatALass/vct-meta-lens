# Rapport Power BI

Le rapport est décrit en code dans `build_report.py` : tables, relations, mesures DAX et pages. Le script écrit le projet `VCTMetaLens/` au format PBIP (modèle en TMDL, rapport en PBIR), lisible et comparable dans Git, contrairement à un `.pbix`.

## Ouvrir le rapport

1. Générer les données du modèle :
   ```powershell
   python -m src.ingest
   python -m src.clean
   python -m src.build_model      # -> data/model/*.csv
   ```
2. Dans Power BI Desktop, activer les préversions **Format de projet Power BI (.pbip)**, **TMDL** et **PBIR** (Fichier > Options > Fonctionnalités en préversion), puis redémarrer.
3. Ouvrir `powerbi/VCTMetaLens/VCTMetaLens.pbip`.
4. Si le dépôt n'est pas cloné dans `C:\pbip\vct-meta-lens\`, changer le paramètre `DataFolder` (Transformer les données > Gérer les paramètres) vers le dossier `data\model\` du dépôt, avec le `\` final.
5. Cliquer sur **Actualiser**. Le projet s'ouvre sans données, c'est normal.

Pour un fichier unique à partager : Fichier > Enregistrer sous > `.pbix`.

## Modifier le rapport

Modifier `build_report.py` (ou `theme.json` pour les couleurs), puis :

```powershell
pip install -r powerbi/requirements.txt
python powerbi/build_report.py --data-folder "D:\mon\chemin\vct-meta-lens\data\model\"
```

La CI régénère le projet et échoue si le dossier `VCTMetaLens/` ne correspond plus au script : on ne modifie donc pas les fichiers générés à la main.

## Pages

| Page | Question | Visuels |
|---|---|---|
| Méta agents | Quels agents dominent, et comment ça évolue sur la saison ? | pick rate par rôle et par tournoi, top agents, winrate des compos |
| Maps | Quelles maps favorisent l'attaque ou la défense ? | winrate ATK/DEF par map, méthodes de victoire des rounds, picks et bans |
| Équipes | Qui gagne, et qui convertit les rounds éco ? | classement (winrate, maps, pistols, éco), taux de victoire par type d'achat |
| Joueurs | Qui performe sur la durée ? | nuage Rating × ACS (10 maps minimum), classement des joueurs |

Les segments Région et Phase filtrent toutes les pages, via `dim_tournament`.

## Thème

`theme.json` : rouge Valorant pour l'accent, fond sable clair, cartes à bordure rouge, en-têtes de tableau sombres. Il est intégré au projet, donc le rapport s'ouvre déjà en couleurs.

## Choix de modélisation

- **Pick rate pondéré.** `pick_rate` est un pourcentage par tournoi, stage, type de match et map. Une moyenne simple donnerait le même poids à une map jouée une fois et à une map jouée 40 fois, donc la mesure `Pick rate %` pondère par `maps_played`.
- **Une ligne par équipe et par match** (`fact_match_team`) plutôt que `team_a` / `team_b` sur la même ligne : une seule relation vers `dim_team`, et le winrate devient un simple ratio.
- **Seuil de 10 maps** sur le nuage et le classement des joueurs, sinon un remplaçant avec 2 bonnes maps passe devant tout le monde.
- **Colonnes brutes masquées** dans les faits : on passe par les mesures, jamais par une somme implicite de pourcentages.
- **Libellés triés par la chronologie** : `tournament_short` est trié par `season_order`, donc les axes suivent la saison et pas l'ordre alphabétique.

## Limites connues

- Power BI compare les clés texte sans tenir compte de la casse : `f0rsakeN` et `f0rsaken` (deux joueurs distincts dans la source) sont une seule clé pour lui. `src/build_model.py` renomme la graphie la moins fréquente (`f0rsaken (12088)`) et fait échouer le pipeline si une dimension a encore une clé en double au sens de Power BI.
