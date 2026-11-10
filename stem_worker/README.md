# Songmatch AI Stem Worker

This Modal app runs the existing Demucs flow for Songmatch. It accepts authenticated jobs from the Songmatch API, separates six stems with `htdemucs_6s`, uploads temporary MP3s to the private artifact bucket, and reports job state through a short-lived signed S3 object.

## Deploy

Create a Modal secret named `songmatch-stem-worker` with:

- `SONGMATCH_WORKER_TOKEN`: the same random bearer token configured as the API's `MODAL_STEM_TOKEN`.
- `STEM_ARTIFACTS_BUCKET`: the bucket name printed by the Songmatch Terraform output.
- `AWS_REGION`: the bucket's region, normally `us-east-1`.
- Optional `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` for spotdl.
- Optional `YOUTUBE_COOKIES` if the YouTube Music resolver requires authentication.

Deploy with `modal deploy stem_worker/modal_app.py`. Copy the generated `start-stem-job` endpoint to `MODAL_STEM_ENDPOINT` in the API Terraform variables. Never commit the Modal token or cookies.

The Spotify path keeps the existing spotdl behavior: it resolves a Spotify track and obtains audio from YouTube Music or YouTube. If that cannot produce valid audio, the Songmatch UI offers a local file upload. Uploaded sources support MP3, WAV, and M4A up to 100 MB and ten minutes.
