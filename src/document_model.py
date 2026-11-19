"""Régénère docs/data_model.md à partir des CSV de data/model/.

Usage:
    python -m src.document_model
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import MODEL_DIR, PROJECT_ROOT

DOC = PROJECT_ROOT / "docs" / "data_model.md"


def describe(path: Path) -> str:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    lines = [f"## `{path.stem}` : {len(df):,} lignes".replace(",", " "), "", "| Colonne | Type |", "|---|---|"]
    lines += [f"| `{col}` | {dtype} |" for col, dtype in df.dtypes.astype(str).items()]
    return "\n".join(lines) + "\n"


def main() -> None:
    files = sorted(MODEL_DIR.glob("*.csv"), key=lambda p: (not p.stem.startswith("dim_"), p.stem))
    if not files:
        raise SystemExit(f"Aucun CSV dans {MODEL_DIR} : lancer d'abord python -m src.build_model")
    header = (
        "# Dictionnaire du modèle de données\n\n"
        "Tables de `data/model/` (générées par `src/build_model.py`, fichier régénéré par "
        "`python -m src.document_model`).\n"
        "Granularité : lignes de détail uniquement, agrégats `All *` exclus.\n\n"
    )
    DOC.write_text(header + "\n".join(describe(p) for p in files), encoding="utf-8")
    print(f"{DOC} : {len(files)} tables")


if __name__ == "__main__":
    main()
