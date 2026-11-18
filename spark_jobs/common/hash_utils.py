"""
Hashing utilities for deterministic record fingerprinting in SentraFlow.
"""

import hashlib
import json
from typing import Any


def compute_record_hash(
    record_dict: dict[str, Any], exclude_keys: list[str] | None = None
) -> str:
    """
    Computes a deterministic SHA-256 hash across record attributes.
    Sorts dictionary keys and ignores ephemeral metadata fields.
    """
    if exclude_keys is None:
        exclude_keys = [
            "_ingest_ts",
            "_source_file",
            "_batch_id",
            "_schema_version",
            "_record_hash",
            "ingest_date",
        ]

    # Filter out excluded keys and serialize values deterministically
    filtered = {
        k: str(v) if v is not None else ""
        for k, v in sorted(record_dict.items())
        if k not in exclude_keys
    }

    serialized = json.dumps(filtered, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
