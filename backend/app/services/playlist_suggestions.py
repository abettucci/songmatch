"""Pure helpers that suggest which existing playlist a liked track fits in.

A playlist is summarized by the artists it contains, the genres of those
artists, and the track ids it already holds. A track is scored against each
playlist: shared artists weigh more than shared genres, and a playlist that
already contains the track is skipped.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

ARTIST_WEIGHT = 3
GENRE_WEIGHT = 1
MAX_REASON_GENRES = 3


def _normalize_genre(genre: str) -> str:
    return " ".join(genre.split()).casefold()


def build_playlist_profile(
    tracks: List[Dict[str, Any]], genres_by_artist: Dict[str, List[str]]
) -> Dict[str, Set[str]]:
    """Summarize a playlist from its raw Spotify tracks and artist genres."""
    artist_ids: Set[str] = set()
    genres: Set[str] = set()
    track_ids: Set[str] = set()
    for track in tracks:
        if track.get("id"):
            track_ids.add(track["id"])
        for artist in track.get("artists", []):
            artist_id = artist.get("id")
            if not artist_id:
                continue
            artist_ids.add(artist_id)
            for genre in genres_by_artist.get(artist_id, []):
                normalized = _normalize_genre(genre)
                if normalized:
                    genres.add(normalized)
    return {"artist_ids": artist_ids, "genres": genres, "track_ids": track_ids}


def score_track_against_playlist(
    track_id: Optional[str],
    artist_ids: Set[str],
    track_genres: Set[str],
    profile: Dict[str, Set[str]],
) -> Optional[Tuple[int, List[str]]]:
    """Return (score, reasons) or None when the playlist should not be suggested."""
    if track_id and track_id in profile["track_ids"]:
        return None

    shared_artists = artist_ids & profile["artist_ids"]
    shared_genres = track_genres & profile["genres"]
    score = ARTIST_WEIGHT * len(shared_artists) + GENRE_WEIGHT * len(shared_genres)
    if score == 0:
        return None

    reasons: List[str] = []
    if shared_artists:
        reasons.append("comparte artista")
    if shared_genres:
        reasons.append("géneros en común: " + ", ".join(sorted(shared_genres)[:MAX_REASON_GENRES]))
    return score, reasons


def rank_playlists_for_track(
    track: Dict[str, Any],
    track_genres: List[str],
    playlists: List[Dict[str, Any]],
    limit: int = 2,
) -> List[Dict[str, Any]]:
    """Rank candidate playlists for one track.

    `playlists` items look like {"playlist_id", "playlist_name", "profile"}.
    """
    artist_ids = {artist.get("id") for artist in track.get("artists", []) if artist.get("id")}
    genres = {_normalize_genre(genre) for genre in track_genres if _normalize_genre(genre)}

    ranked: List[Dict[str, Any]] = []
    for playlist in playlists:
        result = score_track_against_playlist(
            track.get("spotify_id") or track.get("id"),
            artist_ids,
            genres,
            playlist["profile"],
        )
        if result is None:
            continue
        score, reasons = result
        ranked.append(
            {
                "playlist_id": playlist["playlist_id"],
                "playlist_name": playlist["playlist_name"],
                "score": score,
                "reasons": reasons,
            }
        )

    ranked.sort(key=lambda item: (-item["score"], item["playlist_name"].casefold()))
    return ranked[:limit]
