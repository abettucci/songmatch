from app.services.playlist_suggestions import build_playlist_profile, rank_playlists_for_track


def _track(track_id, artist_ids):
    return {
        "id": track_id,
        "spotify_id": track_id,
        "artists": [{"id": artist_id, "name": artist_id} for artist_id in artist_ids],
    }


def test_profile_collects_artists_genres_and_track_ids():
    tracks = [_track("t1", ["a1"]), _track("t2", ["a2"])]
    profile = build_playlist_profile(tracks, {"a1": ["Indie Rock"], "a2": ["  indie rock ", "shoegaze"]})

    assert profile["artist_ids"] == {"a1", "a2"}
    assert profile["genres"] == {"indie rock", "shoegaze"}
    assert profile["track_ids"] == {"t1", "t2"}


def test_shared_artist_outranks_shared_genre_and_playlist_with_track_is_skipped():
    candidate = _track("new", ["a1"])
    playlists = [
        {"playlist_id": "p-genre", "playlist_name": "Solo género",
         "profile": build_playlist_profile([_track("x", ["zz"])], {"zz": ["indie rock"]})},
        {"playlist_id": "p-artist", "playlist_name": "Con artista",
         "profile": build_playlist_profile([_track("y", ["a1"])], {"a1": ["indie rock"]})},
        {"playlist_id": "p-has", "playlist_name": "Ya la tiene",
         "profile": build_playlist_profile([_track("new", ["a1"])], {"a1": ["indie rock"]})},
    ]

    ranked = rank_playlists_for_track(candidate, ["Indie Rock"], playlists, limit=5)

    assert [item["playlist_id"] for item in ranked] == ["p-artist", "p-genre"]
    assert ranked[0]["score"] == 4  # artist (3) + genre (1)
    assert "comparte artista" in ranked[0]["reasons"]
    assert ranked[1]["reasons"] == ["géneros en común: indie rock"]


def test_no_overlap_returns_no_suggestions():
    playlists = [
        {"playlist_id": "p", "playlist_name": "Otra",
         "profile": build_playlist_profile([_track("x", ["zz"])], {"zz": ["techno"]})},
    ]
    assert rank_playlists_for_track(_track("new", ["a1"]), ["jazz"], playlists) == []
