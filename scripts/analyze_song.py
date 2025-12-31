#!/usr/bin/env python3
"""
Analyze a single MP3 file and output beat metadata JSON.

Usage:
    python scripts/analyze_song.py path/to/song.mp3
    python scripts/analyze_song.py path/to/song.mp3 --output path/to/output.json
    python scripts/analyze_song.py path/to/song.mp3 --pretty
"""
import click
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import analyze_song


@click.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file path')
@click.option('--pretty', is_flag=True, help='Pretty-print JSON output')
def main(input_file: str, output: str, pretty: bool):
    """Analyze a single MP3 file for beat timing metadata."""

    input_path = Path(input_file)

    if not input_path.suffix.lower() in ['.mp3', '.wav', '.flac', '.ogg']:
        click.echo(f"Error: Unsupported file format: {input_path.suffix}", err=True)
        sys.exit(1)

    click.echo(f"Analyzing: {input_path.name}...")

    try:
        result = analyze_song(str(input_path))
    except Exception as e:
        click.echo(f"Error analyzing file: {e}", err=True)
        sys.exit(1)

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = input_path.with_suffix('.json')

    # Write JSON
    indent = 2 if pretty else None
    json_str = result.model_dump_json(indent=indent)

    output_path.write_text(json_str)
    click.echo(f"Output written to: {output_path}")

    # Print summary
    click.echo(f"  BPM: {result.bpm}")
    click.echo(f"  Beat drop: {result.beat_drop_time}s")
    click.echo(f"  Total beats: {len(result.beats)}")
    click.echo(f"  Confidence: {result.confidence:.0%}")


if __name__ == '__main__':
    main()
