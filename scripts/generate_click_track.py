#!/usr/bin/env python3
"""
Generate a click track overlay for verification.

Creates an MP3 with click sounds at each detected beat,
allowing manual verification of beat detection accuracy.

Usage:
    python scripts/generate_click_track.py song.mp3 song.json
    python scripts/generate_click_track.py song.mp3 song.json --output verification.mp3
"""
import click
import json
import sys
import numpy as np
import soundfile as sf
import librosa
from pathlib import Path
from scipy import signal


def generate_click_sound(sr: int = 22050, freq: float = 1000, duration: float = 0.05) -> np.ndarray:
    """Generate a short click/beep sound."""
    t = np.linspace(0, duration, int(sr * duration), False)
    click_sound = np.sin(2 * np.pi * freq * t)
    # Apply envelope
    envelope = np.exp(-t * 30)
    return click_sound * envelope * 0.5


def generate_downbeat_click(sr: int = 22050) -> np.ndarray:
    """Generate a higher-pitched click for downbeats."""
    return generate_click_sound(sr, freq=1500, duration=0.08)


@click.command()
@click.argument('audio_file', type=click.Path(exists=True))
@click.argument('json_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output audio file')
@click.option('--click-volume', default=0.3, help='Volume of click track (0-1)')
def main(audio_file: str, json_file: str, output: str, click_volume: float):
    """Generate click track overlay for beat verification."""

    # Load metadata
    with open(json_file) as f:
        metadata = json.load(f)

    beats = metadata['beats']
    downbeats = set(metadata['downbeats'])

    # Load audio
    y, sr = librosa.load(audio_file, sr=22050, mono=True)

    # Generate click sounds
    beat_click = generate_click_sound(sr)
    downbeat_click = generate_downbeat_click(sr)

    # Create click track
    click_track = np.zeros_like(y)

    for beat_time in beats:
        sample_idx = int(beat_time * sr)
        if sample_idx + len(beat_click) < len(click_track):
            # Use downbeat click for beat 1
            if beat_time in downbeats:
                click_sound = downbeat_click
            else:
                click_sound = beat_click

            end_idx = min(sample_idx + len(click_sound), len(click_track))
            click_track[sample_idx:end_idx] += click_sound[:end_idx - sample_idx]

    # Mix original audio with click track
    mixed = y + click_track * click_volume

    # Normalize to prevent clipping
    max_val = np.max(np.abs(mixed))
    if max_val > 1.0:
        mixed = mixed / max_val * 0.95

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = Path(audio_file).with_stem(
            Path(audio_file).stem + '_verification'
        )

    # Save as WAV (or MP3 if ffmpeg available)
    sf.write(str(output_path.with_suffix('.wav')), mixed, sr)

    click.echo(f"Verification audio written to: {output_path.with_suffix('.wav')}")
    click.echo(f"  Total beats: {len(beats)}")
    click.echo(f"  Downbeats marked with higher pitch")


if __name__ == '__main__':
    main()
