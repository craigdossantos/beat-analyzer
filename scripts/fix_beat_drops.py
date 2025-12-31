#!/usr/bin/env python3
"""
Batch fix beat drop times in JSON files based on filename metadata.
Snaps beat_drop_time to the nearest downbeat within tolerance of the filename timestamp.
"""

import json
import re
import sys
from pathlib import Path


def parse_timestamp(ts: str) -> float:
    """Parse timestamp like '00;20.1' or '00:20.1' to seconds."""
    ts = ts.replace(":", ";")
    parts = ts.split(";")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(ts)


def parse_filename_metadata(filename: str) -> dict | None:
    """Extract BPM and beat drop time from filename like 'Song (96 BPM - 00;20.1 - 03;21.0).mp3'"""
    # Remove extension
    name = Path(filename).stem

    # Pattern: Name (BPM - start_time - end_time)
    pattern = r'^(.+?)\s*\((\d+\.?\d*)\s*BPM\s*-?\s*(\d+[;:]\d+\.?\d*)\s*-\s*(\d+[;:]\d+\.?\d*)\)'
    match = re.match(pattern, name, re.IGNORECASE)

    if not match:
        return None

    return {
        "song_name": match.group(1).strip(),
        "bpm": float(match.group(2)),
        "beat_drop_time": parse_timestamp(match.group(3)),
        "end_time": parse_timestamp(match.group(4)),
    }


def find_nearest_downbeat(target_time: float, downbeats: list[float], tolerance: float = 10.0) -> float | None:
    """Find the downbeat nearest to target_time within tolerance."""
    if not downbeats:
        return None

    nearby = [t for t in downbeats if abs(t - target_time) <= tolerance]
    if not nearby:
        return None

    return min(nearby, key=lambda t: abs(t - target_time))


def fix_json_file(json_path: Path, dry_run: bool = False) -> dict:
    """Fix a single JSON file. Returns status dict."""
    result = {
        "file": json_path.name,
        "status": "skipped",
        "old_value": None,
        "new_value": None,
        "reason": None,
    }

    # Find matching audio file
    audio_extensions = [".mp3", ".wav", ".ogg", ".flac"]
    audio_file = None
    for ext in audio_extensions:
        candidate = json_path.with_suffix(ext)
        if candidate.exists():
            audio_file = candidate
            break

    if not audio_file:
        result["reason"] = "No matching audio file found"
        return result

    # Parse filename metadata
    metadata = parse_filename_metadata(audio_file.name)
    if not metadata:
        result["reason"] = "Could not parse filename metadata"
        return result

    # Load JSON
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        result["reason"] = f"Could not read JSON: {e}"
        return result

    # Get downbeats
    downbeats = data.get("downbeats", [])
    if not downbeats:
        result["reason"] = "No downbeats in JSON"
        return result

    # Find nearest downbeat to filename timestamp
    target_time = metadata["beat_drop_time"]
    nearest = find_nearest_downbeat(target_time, downbeats)

    if nearest is None:
        result["reason"] = f"No downbeat within 10s of {target_time:.1f}s"
        return result

    old_value = data.get("beat_drop_time")
    result["old_value"] = old_value
    result["new_value"] = nearest

    # Check if already correct
    if old_value is not None and abs(old_value - nearest) < 0.001:
        result["status"] = "already_correct"
        result["reason"] = f"Already at {nearest:.3f}s"
        return result

    # Update the value
    data["beat_drop_time"] = nearest

    if not dry_run:
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)
        result["status"] = "fixed"
        result["reason"] = f"Changed {old_value:.3f}s → {nearest:.3f}s (target: {target_time:.1f}s)"
    else:
        result["status"] = "would_fix"
        result["reason"] = f"Would change {old_value:.3f}s → {nearest:.3f}s (target: {target_time:.1f}s)"

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fix beat drop times based on filename metadata")
    parser.add_argument("folder", help="Folder containing JSON files to fix")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without modifying files")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser()
    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        sys.exit(1)

    json_files = list(folder.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {folder}")
        sys.exit(0)

    print(f"Processing {len(json_files)} JSON files in {folder}")
    if args.dry_run:
        print("(DRY RUN - no files will be modified)\n")
    else:
        print()

    stats = {"fixed": 0, "already_correct": 0, "skipped": 0, "would_fix": 0}

    for json_path in sorted(json_files):
        result = fix_json_file(json_path, dry_run=args.dry_run)
        stats[result["status"]] = stats.get(result["status"], 0) + 1

        # Color output
        status = result["status"]
        if status == "fixed":
            icon = "✅"
        elif status == "would_fix":
            icon = "🔄"
        elif status == "already_correct":
            icon = "✓ "
        else:
            icon = "⏭️"

        print(f"{icon} {result['file']}: {result['reason']}")

    print(f"\nSummary:")
    if args.dry_run:
        print(f"  Would fix: {stats.get('would_fix', 0)}")
    else:
        print(f"  Fixed: {stats.get('fixed', 0)}")
    print(f"  Already correct: {stats.get('already_correct', 0)}")
    print(f"  Skipped: {stats.get('skipped', 0)}")


if __name__ == "__main__":
    main()
