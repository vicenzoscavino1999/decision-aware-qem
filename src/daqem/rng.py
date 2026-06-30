"""Deterministic random-number policy.

TODO: A2
"""

from __future__ import annotations

import hashlib

import numpy as np


ROOT_SEED = 260616
BIT_GENERATOR = "PCG64DXSM"


def make_rng(
    *,
    instance_id: str = "",
    method: str = "",
    budget: int = 0,
    replicate_id: int = 0,
    stream: str = "",
) -> np.random.Generator:
    """Create a deterministic generator from PAP identifiers."""

    payload = "|".join(
        [
            str(ROOT_SEED),
            str(instance_id),
            str(method),
            str(int(budget)),
            str(int(replicate_id)),
            str(stream),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return np.random.Generator(np.random.PCG64DXSM(seed))
