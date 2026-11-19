"""Le rapport Power BI ne doit lire que des colonnes documentées du modèle."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("pbip_generator")


def documented_columns() -> dict[str, set[str]]:
    doc = (ROOT / "docs" / "data_model.md").read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for block in re.split(r"\n## ", doc)[1:]:
        name = re.match(r"`(\w+)`", block).group(1)
        tables[name] = set(re.findall(r"^\| `([^`]+)` \|", block, flags=re.MULTILINE))
    return tables


def test_report_columns_exist_in_model():
    import sys

    sys.path.insert(0, str(ROOT / "powerbi"))
    from build_report import SCHEMA

    doc = documented_columns()
    for table, (_, columns) in SCHEMA.items():
        assert table in doc, f"{table} absent de docs/data_model.md"
        missing = {c for c, _ in columns} - doc[table]
        assert not missing, f"{table} : colonnes absentes du modèle {missing}"
