import pytest

from app.services.spotify import SpotifyClient


@pytest.mark.asyncio
async def test_saved_tracks_are_formatted_newest_first(monkeypatch):
    client = SpotifyClient()

    class Response:
        status_code = 200

        def json(self):
            return {
                "items": [
                    {
                        "added_at": "2026-09-20T12:00:00Z",
                        "track": {
                            "id": "track-one",
                            "name": "A liked song",
                            "artists": [{"id": "artist-one", "name": "Artist"}],
                            "album": {"name": "Album", "images": []},
                            "external_urls": {"spotify": "https://open.spotify.com/track/track-one"},
                        },
                    }
                ]
            }

    class HttpClient:
        async def get(self, *args, **kwargs):
            assert kwargs["params"] == {"limit": 20, "offset": 0}
            return Response()

    async def get_client():
        return HttpClient()

    monkeypatch.setattr(client, "_get_client", get_client)
    tracks = await client.get_user_saved_tracks("token")

    assert tracks[0]["spotify_id"] == "track-one"
    assert tracks[0]["added_at"].isoformat() == "2026-09-20T12:00:00+00:00"
