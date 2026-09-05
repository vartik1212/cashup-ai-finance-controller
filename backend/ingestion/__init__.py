"""
ReconAI Ingestion Package
"""

from .profiler import profile_csv
from .detector import detect_file_type, disambiguate_batch_file_types
from .schema_mapper import (
    map_columns_deterministic,
    map_columns_hybrid,
    map_columns_with_ai,
    get_canonical_schema,
    CANONICAL_SCHEMAS,
)
from .validator import validate_records
from .normalizer import normalize_and_store

__all__ = [
    "profile_csv",
    "detect_file_type",
    "disambiguate_batch_file_types",
    "map_columns_deterministic",
    "map_columns_hybrid",
    "map_columns_with_ai",
    "get_canonical_schema",
    "CANONICAL_SCHEMAS",
    "validate_records",
    "normalize_and_store",
]
