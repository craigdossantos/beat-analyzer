#!/usr/bin/env python3
"""
Validate beat drop detection against ground truth from filenames.

This script:
1. Parses ground truth from filenames (beat drop time encoded in name)
2. Runs the beat drop detector on each file
3. Compares detected vs expected times
4. Reports accuracy metrics
"""
import json
from pathlib import Path
from typing import Optional
import numpy as np

from .filename_parser import parse_filename, FilenameMetadata
from .beat_drop import find_beat_drop_advanced
from .analyzer import detect_beats_and_tempo, detect_downbeats, load_audio


def validate_single_file(audio_path: Path, verbose: bool = True) -> Optional[dict]:
    """
    Validate beat drop detection for a single file.

    Returns dict with expected, detected, and error info.
    """
    # Parse ground truth from filename
    metadata = parse_filename(audio_path.name)
    if metadata is None:
        if verbose:
            print(f"  SKIP: Cannot parse metadata from '{audio_path.name}'")
        return None

    expected_drop = metadata.beat_drop_time

    # Load existing JSON analysis if available (for downbeats)
    json_path = audio_path.with_suffix('.json')
    if json_path.exists():
        with open(json_path) as f:
            analysis = json.load(f)
        downbeats = np.array(analysis.get('downbeats', []))
    else:
        # Run beat detection
        y, sr = load_audio(str(audio_path))
        _, beats = detect_beats_and_tempo(str(audio_path), y, sr)
        downbeats = detect_downbeats(str(audio_path), beats)

    # Run improved beat drop detection
    detected_drop, debug_info = find_beat_drop_advanced(str(audio_path), downbeats)

    # Calculate error
    error = detected_drop - expected_drop
    abs_error = abs(error)

    result = {
        'filename': audio_path.name,
        'song_name': metadata.song_name,
        'expected_bpm': metadata.bpm,
        'expected_drop': expected_drop,
        'detected_drop': detected_drop,
        'error': error,
        'abs_error': abs_error,
        'debug': debug_info
    }

    if verbose:
        status = "OK" if abs_error < 2.0 else "MISS"
        print(f"  [{status}] {metadata.song_name}")
        print(f"       Expected: {expected_drop:.1f}s | Detected: {detected_drop:.1f}s | Error: {error:+.1f}s")
        print(f"       Debug: bpm={debug_info.get('bpm', 0):.0f}, rms_r={debug_info.get('rms_ratio', 0):.2f}, onset_r={debug_info.get('onset_ratio', 0):.2f}, combined={debug_info.get('combined', 0):.2f}")

    return result


def validate_directory(directory: str, verbose: bool = True) -> dict:
    """
    Validate all audio files in a directory.

    Returns summary statistics.
    """
    directory = Path(directory)
    results = []

    print(f"\nValidating beat drop detection in: {directory}\n")
    print("=" * 70)

    for audio_file in sorted(directory.glob("*.mp3")):
        result = validate_single_file(audio_file, verbose)
        if result:
            results.append(result)
        print()

    if not results:
        print("No files with parseable metadata found.")
        return {}

    # Calculate statistics
    errors = [r['abs_error'] for r in results]
    mean_error = np.mean(errors)
    median_error = np.median(errors)
    max_error = np.max(errors)

    # Count how many are within tolerance
    within_1s = sum(1 for e in errors if e < 1.0)
    within_2s = sum(1 for e in errors if e < 2.0)
    within_5s = sum(1 for e in errors if e < 5.0)

    print("=" * 70)
    print(f"\nSUMMARY ({len(results)} files)")
    print(f"  Mean absolute error:   {mean_error:.2f}s")
    print(f"  Median absolute error: {median_error:.2f}s")
    print(f"  Max absolute error:    {max_error:.2f}s")
    print(f"\n  Accuracy:")
    print(f"    Within 1s: {within_1s}/{len(results)} ({100*within_1s/len(results):.0f}%)")
    print(f"    Within 2s: {within_2s}/{len(results)} ({100*within_2s/len(results):.0f}%)")
    print(f"    Within 5s: {within_5s}/{len(results)} ({100*within_5s/len(results):.0f}%)")

    return {
        'results': results,
        'mean_error': mean_error,
        'median_error': median_error,
        'max_error': max_error,
        'within_1s': within_1s,
        'within_2s': within_2s,
        'within_5s': within_5s,
        'total': len(results)
    }


if __name__ == "__main__":
    import sys

    # Default to aibeats directory
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        # Find aibeats relative to this script
        script_dir = Path(__file__).parent.parent.parent
        directory = script_dir / "aibeats"

    validate_directory(str(directory))
