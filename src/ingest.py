"""Téléchargement du dataset VCT 2025 (VLR.gg) depuis Kaggle.

Le dossier data/raw/ n'est pas versionné dans Git (~52 Mo de CSV).
Ce script rend le repo reproductible : il télécharge le dataset via
kagglehub et le copie dans data/raw/vct_2025/.

Usage:
    python -m src.ingest

Prérequis:
    pip install kagglehub
    (un compte Kaggle configuré : ~/.kaggle/kaggle.json ou variables
     d'environnement KAGGLE_USERNAME / KAGGLE_KEY)
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from src.config import RAW_DIR

# Slug du dataset Kaggle "Valorant Champions Tour 2025" (exports VLR.gg).
# Si le dataset change de propriétaire/nom, mettre à jour ici.
KAGGLE_DATASET = "ryanluong1/valorant-champion-tour-2021-2023-data"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    if RAW_DIR.exists() and any(RAW_DIR.rglob("*.csv")):
        log.info("Données déjà présentes dans %s : rien à faire.", RAW_DIR)
        log.info("Supprimez le dossier pour forcer un re-téléchargement.")
        return

    try:
        import kagglehub  # import tardif : dépendance optionnelle
    except ImportError:
        log.error("kagglehub n'est pas installé : pip install kagglehub")
        sys.exit(1)

    log.info("Téléchargement du dataset Kaggle '%s'…", KAGGLE_DATASET)
    download_path = Path(kagglehub.dataset_download(KAGGLE_DATASET))

    # Le dataset Kaggle peut contenir plusieurs saisons : on ne copie que vct_2025.
    src_2025 = next(download_path.rglob("vct_2025"), None)
    if src_2025 is None:
        log.error("Dossier vct_2025 introuvable dans %s", download_path)
        sys.exit(1)

    RAW_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_2025, RAW_DIR, dirs_exist_ok=True)
    n_csv = len(list(RAW_DIR.rglob("*.csv")))
    log.info("OK : %d fichiers CSV copiés dans %s", n_csv, RAW_DIR)


if __name__ == "__main__":
    main()
