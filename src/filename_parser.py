"""
Parse metadata from filenames following the convention:
    SongName (BPM_VALUE BPM - MM;SS.S - MM;SS.S).mp3
    SongName (BPM_VALUEBPM MM;SS.S - MM;SS.S).mp3

Where:
    - First timestamp: Beat drop time (when the beat kicks in)
    - Second timestamp: End time / song duration
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FilenameMetadata:
    """Metadata extracted from filename."""
    song_name: str
    bpm: float
    beat_drop_time: float  # seconds
    end_time: float  # seconds

    def __repr__(self):
        return (f"FilenameMetadata(song='{self.song_name}', bpm={self.bpm}, "
                f"drop={self.beat_drop_time:.1f}s, end={self.end_time:.1f}s)")


def parse_timestamp(timestamp: str) -> float:
    """
    Parse timestamp from MM;SS.S format to seconds.

    Examples:
        "00;20.1" -> 20.1
        "03;21.0" -> 201.0
        "02;49.8" -> 169.8
    """
    # Handle both ; and : as separators
    timestamp = timestamp.replace(":", ";")

    # Split by semicolon
    parts = timestamp.split(";")

    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    elif len(parts) == 1:
        # Just seconds
        return float(parts[0])
    else:
        raise ValueError(f"Cannot parse timestamp: {timestamp}")


def parse_filename(filename: str) -> Optional[FilenameMetadata]:
    """
    Extract metadata from filename.

    Supports multiple formats:
        - "Song Name (96 BPM - 00;20.1 - 03;21.0).mp3"
        - "Song Name (96BPM 00;20.1 - 03;21.0).mp3"
        - "Song Name (96.5 BPM- 00;20.1 - 03;21.0).mp3"

    Returns:
        FilenameMetadata if parsing succeeds, None otherwise
    """
    # Remove extension
    name = Path(filename).stem

    # Pattern to match: Song Name (BPM_INFO TIMESTAMPS)
    # BPM can be: "96 BPM", "96BPM", "96.5BPM", "96.5 BPM"
    # Timestamps are: MM;SS.S - MM;SS.S

    pattern = r'^(.+?)\s*\((\d+\.?\d*)\s*BPM\s*-?\s*(\d+;\d+\.?\d*)\s*-\s*(\d+;\d+\.?\d*)\)'

    match = re.match(pattern, name, re.IGNORECASE)

    if not match:
        return None

    song_name = match.group(1).strip()
    bpm = float(match.group(2))
    beat_drop_str = match.group(3)
    end_time_str = match.group(4)

    try:
        beat_drop_time = parse_timestamp(beat_drop_str)
        end_time = parse_timestamp(end_time_str)
    except ValueError:
        return None

    return FilenameMetadata(
        song_name=song_name,
        bpm=bpm,
        beat_drop_time=beat_drop_time,
        end_time=end_time
    )


def extract_ground_truth_from_directory(directory: str) -> dict[str, FilenameMetadata]:
    """
    Extract ground truth metadata from all audio files in a directory.

    Returns:
        Dict mapping filename to FilenameMetadata
    """
    directory = Path(directory)
    results = {}

    for audio_file in directory.glob("*.mp3"):
        metadata = parse_filename(audio_file.name)
        if metadata:
            results[audio_file.name] = metadata

    return results


if __name__ == "__main__":
    # Test the parser
    test_files = [
        "Are We Cooked (96 BPM - 00;20.1 - 03;21.0).mp3",
        "Beep Boo Boo Bop (140BPM 00;13.9 - 03;01.7).mp3",
        "Bop Squad (87.5 BPM - 00;11.4 - 03;07.0).mp3",
        "Something Bout You (141.6BPM 00;13.8 - 02;49.8).mp3",
        "Summers Cool (89 BPM- 00;21.7 - 03;25.3).mp3",
    ]

    print("Testing filename parser:\n")
    for filename in test_files:
        result = parse_filename(filename)
        print(f"  {filename}")
        print(f"    -> {result}\n")
