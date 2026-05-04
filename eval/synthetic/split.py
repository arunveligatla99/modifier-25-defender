"""Deterministic 70/15/15 train/dev/test split (AC-001-8).

The split is computed from a stable hash of the encounter ID so it is fixed
across regenerations of the dataset, even when the generator changes. Train
gets 70%, dev gets 15%, test gets 15%.
"""

from __future__ import annotations

import hashlib

from eval.schemas import SplitName


def split_for(encounter_id: str) -> SplitName:
    """Return the deterministic split assignment for an encounter ID."""
    digest = hashlib.sha1(encounter_id.encode("utf-8")).hexdigest()
    bucket = int(digest, 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "dev"
    return "test"
