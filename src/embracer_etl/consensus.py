from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceObservation:
    source: str
    field: str
    value: str
    confidence: float


@dataclass(frozen=True)
class ConsensusResult:
    field: str
    value: str | None
    confidence: float
    sources: tuple[str, ...]
    review_required: bool
    reason: str | None = None


def weighted_consensus(
    field: str,
    observations: Iterable[SourceObservation],
    source_weights: dict[str, float],
    *,
    accept_threshold: float = 0.60,
    quorum_min_sources: int = 2,
) -> ConsensusResult:
    grouped: dict[str, list[SourceObservation]] = defaultdict(list)

    for observation in observations:
        if observation.field != field or not observation.value:
            continue
        grouped[observation.value].append(observation)

    if not grouped:
        return ConsensusResult(
            field=field,
            value=None,
            confidence=0.0,
            sources=(),
            review_required=True,
            reason="no_observations",
        )

    scored: list[tuple[str, float, tuple[str, ...]]] = []
    total_weight = 0.0

    for value, items in grouped.items():
        value_weight = 0.0
        sources = []
        for item in items:
            weight = source_weights.get(item.source, 0.0) * max(
                0.0, min(item.confidence, 1.0)
            )
            value_weight += weight
            total_weight += weight
            sources.append(item.source)
        scored.append((value, value_weight, tuple(sorted(set(sources)))))

    scored.sort(key=lambda item: item[1], reverse=True)
    winner, winner_weight, winner_sources = scored[0]
    confidence = winner_weight / total_weight if total_weight else 0.0

    reasons = []
    if len(winner_sources) < quorum_min_sources:
        reasons.append("insufficient_quorum")
    if confidence < accept_threshold:
        reasons.append("below_confidence_threshold")

    return ConsensusResult(
        field=field,
        value=winner if not reasons else None,
        confidence=round(confidence, 4),
        sources=winner_sources,
        review_required=bool(reasons),
        reason=";".join(reasons) if reasons else None,
    )


def provenance_rows(
    record_id: str,
    observations: Iterable[SourceObservation],
) -> list[dict[str, str | float]]:
    return [
        {
            "record_id": record_id,
            "field": observation.field,
            "value": observation.value,
            "source": observation.source,
            "source_confidence": observation.confidence,
        }
        for observation in observations
    ]
