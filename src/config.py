"""Configuration centrale du projet VCT Meta Lens.

Contient les chemins, les métadonnées des tournois (ordre chronologique,
région, tier) et le mapping agent -> rôle. Ces référentiels n'existent pas
dans les données brutes VLR.gg : ils sont maintenus ici manuellement.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "vct_2025"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = DATA_DIR / "model"

# ---------------------------------------------------------------------------
# Tokens d'agrégats présents dans les CSV bruts (à exclure des tables de faits)
# ---------------------------------------------------------------------------
AGG_MAP = "All Maps"
AGG_STAGE = "All Stages"
AGG_MATCH_TYPE = "All Match Types"

# ---------------------------------------------------------------------------
# Référentiel tournois : ordre chronologique, région, tier
# (ordre = position dans la saison 2025, utilisé pour trier les axes temporels)
# ---------------------------------------------------------------------------
TOURNAMENT_META: dict[str, dict] = {
    "VCT 2025: Americas Kickoff":    {"order": 1,  "region": "Americas",      "tier": "Kickoff"},
    "VCT 2025: EMEA Kickoff":        {"order": 2,  "region": "EMEA",          "tier": "Kickoff"},
    "VCT 2025: Pacific Kickoff":     {"order": 3,  "region": "Pacific",       "tier": "Kickoff"},
    "VCT 2025: China Kickoff":       {"order": 4,  "region": "China",         "tier": "Kickoff"},
    "Valorant Masters Bangkok 2025": {"order": 5,  "region": "International", "tier": "Masters"},
    "VCT 2025: Americas Stage 1":    {"order": 6,  "region": "Americas",      "tier": "Stage 1"},
    "VCT 2025: EMEA Stage 1":        {"order": 7,  "region": "EMEA",          "tier": "Stage 1"},
    "VCT 2025: Pacific Stage 1":     {"order": 8,  "region": "Pacific",       "tier": "Stage 1"},
    "VCT 2025: China Stage 1":       {"order": 9,  "region": "China",         "tier": "Stage 1"},
    "Valorant Masters Toronto 2025": {"order": 10, "region": "International", "tier": "Masters"},
    "VCT 2025: Americas Stage 2":    {"order": 11, "region": "Americas",      "tier": "Stage 2"},
    "VCT 2025: EMEA Stage 2":        {"order": 12, "region": "EMEA",          "tier": "Stage 2"},
    "VCT 2025: Pacific Stage 2":     {"order": 13, "region": "Pacific",       "tier": "Stage 2"},
    "VCT 2025: China Stage 2":       {"order": 14, "region": "China",         "tier": "Stage 2"},
    "Valorant Champions 2025":       {"order": 15, "region": "International", "tier": "Champions"},
}

# Ordre "phase de saison" (pour comparer les 4 régions au même moment)
TIER_ORDER: dict[str, int] = {
    "Kickoff": 1,
    "Masters": 2,   # Bangkok=2, Toronto réaffecté plus finement via order
    "Stage 1": 3,
    "Stage 2": 4,
    "Champions": 5,
}

# ---------------------------------------------------------------------------
# Référentiel agents : rôle (état du jeu sur la saison 2025)
# ---------------------------------------------------------------------------
AGENT_ROLES: dict[str, str] = {
    # Duelists
    "jett": "Duelist", "raze": "Duelist", "reyna": "Duelist", "yoru": "Duelist",
    "phoenix": "Duelist", "neon": "Duelist", "iso": "Duelist", "waylay": "Duelist",
    # Controllers
    "omen": "Controller", "viper": "Controller", "brimstone": "Controller",
    "astra": "Controller", "harbor": "Controller", "clove": "Controller",
    # Initiators
    "sova": "Initiator", "skye": "Initiator", "breach": "Initiator",
    "kayo": "Initiator", "fade": "Initiator", "gekko": "Initiator",
    "tejo": "Initiator",
    # Sentinels
    "killjoy": "Sentinel", "cypher": "Sentinel", "sage": "Sentinel",
    "chamber": "Sentinel", "deadlock": "Sentinel", "vyse": "Sentinel",
}

# Libellés lisibles des catégories économiques (eco_stats.csv)
ECO_TYPE_LABELS: dict[str, str] = {
    "Pistol Won": "Pistol",
    "Eco (won)": "Eco (0-5k)",
    "$ (won)": "Semi-eco (5-10k)",
    "$$ (won)": "Semi-buy (10-20k)",
    "$$$ (won)": "Full buy (20k+)",
}
