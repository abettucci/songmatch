import pytest

from app.api.schemas import SpotifyPlaylistGenreCreateRequest, SpotifyPlaylistGenreRequest
from app.services.spotify import SpotifyClient


def test_playlist_genre_requests_allow_only_spotify_ids_and_normalize_genres():
    playlist_id = "3cEYpjA9oz9GiPac4AsH4n"
    assert SpotifyPlaylistGenreRequest(playlist_id=playlist_id).playlist_id == playlist_id
    request = SpotifyPlaylistGenreCreateRequest(
        playlist_id=playlist_id,
        genre="  indie   pop ",
        confirmation_token="x" * 32,
    )
    assert request.genre == "indie pop"

    with pytest.raises(ValueError):
        SpotifyPlaylistGenreRequest(playlist_id="../etc/passwd")


@pytest.mark.asyncio
async def test_analyze_playlist_genres_deduplicates_collaborator_genres_and_preserves_counts(monkeypatch):
    client = SpotifyClient()
    tracks = [
        {
            "uri": "spotify:track:one",
            "type": "track",
            "artists": [{"id": "artist-one"}, {"id": "artist-two"}],
        },
        {
            "uri": "spotify:track:two",
            "type": "track",
            "artists": [{"id": "artist-one"}],
        },
    ]

    async def get_playlist_tracks(access_token, playlist_id):
        return "Source playlist", tracks

    async def get_artists_genres(artist_ids):
        assert artist_ids == ["artist-one", "artist-two", "artist-one"]
        return {
            "artist-one": ["indie pop", "pop"],
            "artist-two": ["indie pop", "electropop"],
        }

    monkeypatch.setattr(client, "get_playlist_tracks", get_playlist_tracks)
    monkeypatch.setattr(client, "get_artists_genres", get_artists_genres)

    result = await client.analyze_playlist_genres("token", "3cEYpjA9oz9GiPac4AsH4n")

    assert result["playlist_name"] == "Source playlist"
    assert result["genres"] == [
        {"name": "indie pop", "track_count": 2},
        {"name": "pop", "track_count": 2},
        {"name": "electropop", "track_count": 1},
    ]
    assert [(group["name"], len(group["tracks"])) for group in result["genre_tracks"]] == [
        ("indie pop", 2),
        ("pop", 2),
        ("electropop", 1),
    ]
