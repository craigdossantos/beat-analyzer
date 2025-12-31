#!/usr/bin/env python3
"""
Batch analyze all MP3 files in a directory.

Usage:
    python scripts/batch_analyze.py path/to/songs/
    python scripts/batch_analyze.py path/to/songs/ --output-dir path/to/output/
"""
import click
import json
import sys
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import analyze_song


@click.command()
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False))
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory for JSON files')
@click.option('--skip-existing', is_flag=True, help='Skip files that already have JSON output')
def main(input_dir: str, output_dir: str, skip_existing: bool):
    """Batch analyze all MP3 files in a directory."""

    input_path = Path(input_dir)
    output_path = Path(output_dir) if output_dir else input_path

    # Find all audio files
    audio_extensions = {'.mp3', '.wav', '.flac', '.ogg'}
    audio_files = [f for f in input_path.iterdir()
                   if f.suffix.lower() in audio_extensions]

    if not audio_files:
        click.echo(f"No audio files found in {input_path}")
        sys.exit(0)

    click.echo(f"Found {len(audio_files)} audio files")

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)

    # Process each file
    results = []
    errors = []

    for audio_file in tqdm(audio_files, desc="Analyzing"):
        json_path = output_path / f"{audio_file.stem}.json"

        if skip_existing and json_path.exists():
            continue

        try:
            result = analyze_song(str(audio_file))
            json_path.write_text(result.model_dump_json(indent=2))
            results.append(result)
        except Exception as e:
            errors.append((audio_file.name, str(e)))

    # Summary
    click.echo(f"\nSuccessfully analyzed: {len(results)} files")

    if errors:
        click.echo(f"Errors: {len(errors)} files")
        for filename, error in errors:
            click.echo(f"  - {filename}: {error}")


if __name__ == '__main__':
    main()
