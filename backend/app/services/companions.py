"""Deterministic, privacy-preserving musical affinity scoring."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


@dataclass(frozen=True)
class AffinityResult:
    score: int
    level: str
    reasons: list[str]


@dataclass(frozen=True)
class ConcertDraft:
    artist: str
    venue: str
    city: str
    starts_at: datetime


class ConcertSource(Protocol):
    """Adapter boundary for a future event provider; v1 uses manual input."""

    async def upcoming(self, city: str) -> list[ConcertDraft]: ...


class MusicAffinityService:
    """Scores only aggregated data; it never exposes listening events."""

    @staticmethod
    def _history_weights(history: Iterable[tuple[str, datetime]], now: datetime) -> dict[str, float]:
        weights: dict[str, float] = defaultdict(float)
        for genre, played_at in history:
            term = _normalized(genre)
            if not term:
                continue
            age_days = max(0.0, (now - played_at.astimezone(timezone.utc)).total_seconds() / 86400)
            weights[term] += 1 / (1 + age_days / 30)
        return weights

    def score(
        self,
        own_interests: Iterable[str],
        candidate_interests: Iterable[str],
        *,
        own_history: Iterable[tuple[str, datetime]] = (),
        candidate_history: Iterable[tuple[str, datetime]] = (),
        use_history: bool = False,
        now: datetime | None = None,
    ) -> AffinityResult:
        now = now or datetime.now(timezone.utc)
        own_public = {_normalized(item) for item in own_interests if _normalized(item)}
        candidate_public = {_normalized(item) for item in candidate_interests if _normalized(item)}
        shared_public = sorted(own_public & candidate_public)
        public_score = round(70 * len(shared_public) / max(len(own_public), len(candidate_public), 1))

        shared_history: list[str] = []
        history_score = 0
        if use_history:
            own_weights = self._history_weights(own_history, now)
            candidate_weights = self._history_weights(candidate_history, now)
            keys = set(own_weights) | set(candidate_weights)
            denominator = sum(max(own_weights.get(key, 0), candidate_weights.get(key, 0)) for key in keys)
            numerator = sum(min(own_weights.get(key, 0), candidate_weights.get(key, 0)) for key in keys)
            history_score = round(30 * numerator / denominator) if denominator else 0
            shared_history = sorted(
                set(own_weights) & set(candidate_weights),
                key=lambda key: min(own_weights[key], candidate_weights[key]),
                reverse=True,
            )

        score = min(100, public_score + history_score)
        level = "alto" if score >= 70 else "medio" if score >= 40 else "bajo"
        reasons = [f"Coinciden en {term}" for term in (shared_public + shared_history)[:3]]
        return AffinityResult(score=score, level=level, reasons=reasons)


music_affinity_service = MusicAffinityService()
