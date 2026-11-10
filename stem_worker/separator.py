"""Run Demucs in process and write all six mixer stems as MP3."""

from pathlib import Path

from demucs.api import Separator
from demucs.audio import save_audio

STEMS = ("vocals", "drums", "bass", "other", "guitar", "piano")


def separate_all(audio_path: Path, output_dir: Path) -> dict[str, Path]:
    separator = Separator(
        model="htdemucs_6s",
        device="cuda",
        shifts=1,
        overlap=0.25,
        progress=False,
    )
    _, sources = separator.separate_audio_file(audio_path)
    output_paths: dict[str, Path] = {}
    for stem in STEMS:
        source = sources.get(stem)
        if source is None:
            raise RuntimeError("A required stem was not produced")
        output_path = output_dir / f"{stem}.mp3"
        save_audio(source.cpu(), output_path, separator.samplerate, bitrate=192, preset=2)
        output_paths[stem] = output_path
    return output_paths
