from datetime import datetime, timedelta, timezone
import pytest
from app.api.schemas import CompanionProfileUpsert, CompanionSwipeRequest
from app.services.companions import music_affinity_service

def test_affinity_score_is_deterministic_and_explains_shared_public_interests():
    result = music_affinity_service.score(["Indie Rock", "electrónica"], ["indie rock", "pop"])
    assert (result.score, result.level, result.reasons) == (35, "bajo", ["Coinciden en indie rock"])

def test_history_recency_complements_public_score_without_events():
    now = datetime(2026, 9, 22, tzinfo=timezone.utc)
    result = music_affinity_service.score([], [], use_history=True, now=now, own_history=[("post-punk", now - timedelta(days=2))], candidate_history=[("post-punk", now - timedelta(days=3))])
    assert (result.score, result.reasons) == (30, ["Coinciden en post-punk"])

def test_profile_and_swipe_payload_validation():
    profile = CompanionProfileUpsert(display_name="  Luli  ", city="  La Plata ", adult_confirmed=True, public_interests=[" indie rock ", "Indie   Rock", "electrónica"])
    assert (profile.display_name, profile.public_interests) == ("Luli", ["indie rock", "electrónica"])
    with pytest.raises(ValueError): CompanionSwipeRequest(target_user_id="not-a-uuid", action="wave")
