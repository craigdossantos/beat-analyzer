#!/usr/bin/env python3
"""
Test the beat drop detection algorithm against filename ground truth.
Does NOT use filename metadata during detection - pure audio analysis.
"""

import json
import re
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import analyze_song
from src.filename_parser import parse_filename


def parse_timestamp(ts: str) -> float:
    """Parse timestamp like '00;20.1' or '00:20.1' to seconds."""
    ts = ts.replace(":", ";")
    parts = ts.split(";")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(ts)


def get_expected_drop_from_filename(filename: str) -> float | None:
    """Extract expected beat drop time from filename."""
    metadata = parse_filename(filename)
    if metadata:
        return metadata.beat_drop_time
    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test beat drop detection accuracy")
    parser.add_argument("folder", help="Folder containing audio files to test")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        sys.exit(1)

    # Find audio files
    audio_files = []
    for ext in [".mp3", ".wav", ".ogg", ".flac"]:
        audio_files.extend(folder.glob(f"*{ext}"))

    if not audio_files:
        print(f"No audio files found in {folder}")
        sys.exit(0)

    print(f"Testing beat drop detection on {len(audio_files)} files")
    print("=" * 80)
    print()

    results = []
    total_error = 0
    good_count = 0
    close_count = 0

    for audio_path in sorted(audio_files):
        filename = audio_path.name
        expected = get_expected_drop_from_filename(filename)

        if expected is None:
            print(f"SKIP {filename}: No timestamp in filename")
            continue

        print(f"Analyzing: {filename}")
        print(f"  Expected drop (from filename): {expected:.1f}s")

        try:
            # Run analysis (this uses the NEW algorithm, no filename hints)
            result = analyze_song(str(audio_path))
            detected = result.beat_drop_time

            error = abs(detected - expected)
            total_error += error

            # Determine accuracy
            if error <= 1.0:
                status = "EXCELLENT"
                good_count += 1
                close_count += 1
            elif error <= 5.0:
                status = "GOOD"
                close_count += 1
            elif error <= 10.0:
                status = "CLOSE"
            else:
                status = "MISS"

            print(f"  Detected drop: {detected:.3f}s")
            print(f"  Error: {error:.1f}s  [{status}]")

            results.append({
                'file': filename,
                'expected': expected,
                'detected': detected,
                'error': error,
                'status': status
            })

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                'file': filename,
                'expected': expected,
                'detected': None,
                'error': None,
                'status': 'ERROR'
            })

        print()

    # Summary
    tested = len([r for r in results if r['error'] is not None])
    if tested > 0:
        avg_error = total_error / tested
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"  Files tested: {tested}")
        print(f"  Excellent (<=1s): {good_count} ({100*good_count/tested:.0f}%)")
        print(f"  Good (<=5s): {close_count} ({100*close_count/tested:.0f}%)")
        print(f"  Average error: {avg_error:.1f}s")
        print()

        # Show misses
        misses = [r for r in results if r['status'] == 'MISS']
        if misses:
            print("MISSES (>10s error):")
            for m in misses:
                print(f"  {m['file']}: expected {m['expected']:.1f}s, got {m['detected']:.1f}s")


if __name__ == "__main__":
    main()
