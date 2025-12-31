"""
Detect the "beat drop" - the first strong downbeat after intro silence/ambient.

The beat drop is where the main rhythm kicks in. This module provides:
1. Metadata-based detection (uses filename timestamps when available)
2. Audio analysis fallback (energy-based detection)

For AI-generated beats with melodic intros, the metadata approach is more reliable
since the energy profile is often consistent throughout.
"""
import numpy as np
import librosa
from pathlib import Path
from typing import Tuple, List, Optional

# Import the filename parser for metadata extraction
try:
    from .filename_parser import parse_filename
except ImportError:
    parse_filename = None


def compute_rms_envelope(y: np.ndarray, sr: int, hop_length: int = 512) -> np.ndarray:
    """Compute RMS energy envelope of audio."""
    return librosa.feature.rms(y=y, hop_length=hop_length)[0]


def compute_onset_envelope(y: np.ndarray, sr: int, hop_length: int = 512) -> np.ndarray:
    """Compute onset strength envelope."""
    return librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)


def get_bar_times(bpm: float, beats_per_bar: int = 4, max_bars: int = 16) -> List[float]:
    """Calculate timestamps for bar boundaries given BPM."""
    bar_duration = (60.0 / bpm) * beats_per_bar
    return [bar_duration * i for i in range(1, max_bars + 1)]


def get_energy_at_time(energy: np.ndarray, time: float, sr: int, hop_length: int,
                       window_seconds: float = 2.0) -> float:
    """Get average energy in a window around a specific time."""
    frame = int(time * sr / hop_length)
    window_frames = int(window_seconds * sr / hop_length)
    start = max(0, frame - window_frames // 2)
    end = min(len(energy), frame + window_frames // 2)
    if start >= end:
        return 0.0
    return float(np.mean(energy[start:end]))


def analyze_downbeat_energy(
    rms: np.ndarray,
    onset: np.ndarray,
    downbeats: np.ndarray,
    sr: int,
    hop_length: int,
    min_time: float = 5.0,
    max_time: float = 40.0
) -> List[dict]:
    """
    Analyze energy at each downbeat to find where the beat kicks in.

    Returns list of dicts with downbeat analysis.
    """
    valid_downbeats = downbeats[(downbeats >= min_time) & (downbeats <= max_time)]

    results = []
    for i, db_time in enumerate(valid_downbeats):
        # Get energy BEFORE this downbeat (previous 4 beats = ~1 bar)
        before_time = db_time - 2.5
        rms_before = get_energy_at_time(rms, before_time, sr, hop_length, 2.0)
        onset_before = get_energy_at_time(onset, before_time, sr, hop_length, 2.0)

        # Get energy AFTER this downbeat (next 4 beats)
        after_time = db_time + 1.0
        rms_after = get_energy_at_time(rms, after_time, sr, hop_length, 2.0)
        onset_after = get_energy_at_time(onset, after_time, sr, hop_length, 2.0)

        # Calculate ratios
        rms_ratio = rms_after / (rms_before + 0.001)
        onset_ratio = onset_after / (onset_before + 0.001)

        results.append({
            'time': db_time,
            'rms_ratio': rms_ratio,
            'onset_ratio': onset_ratio,
            'combined': rms_ratio * onset_ratio,
            'rms_after': rms_after,
            'onset_after': onset_after
        })

    return results


def find_beat_drop_advanced(
    file_path: str,
    downbeats: np.ndarray,
    min_intro_length: float = 5.0,
    max_intro_length: float = 40.0,
    bpm: float = None
) -> Tuple[float, dict]:
    """
    Find the beat drop by analyzing energy at downbeats and bar boundaries.

    Strategy:
    1. Analyze energy ratio at each detected downbeat
    2. Find the FIRST downbeat where:
       - Combined (RMS * onset) ratio exceeds threshold, OR
       - Energy level after downbeat is high (above median) AND ratio > 1.0
    3. Snap to the actual downbeat time

    Args:
        file_path: Path to audio file
        downbeats: Array of downbeat timestamps
        min_intro_length: Minimum expected intro
        max_intro_length: Maximum expected intro
        bpm: Known BPM (optional)

    Returns:
        Tuple of (beat_drop_time, debug_info)
    """
    y, sr = librosa.load(file_path, sr=22050, mono=True)
    hop_length = 512

    # Estimate BPM if not provided
    if bpm is None:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        if hasattr(tempo, '__len__'):
            bpm = float(tempo[0]) if len(tempo) > 0 else 90.0
        else:
            bpm = float(tempo)
        while bpm > 165:
            bpm /= 2
        while bpm < 70:
            bpm *= 2

    # Compute features
    rms = compute_rms_envelope(y, sr, hop_length)
    onset = compute_onset_envelope(y, sr, hop_length)

    # Analyze energy at each downbeat
    db_analysis = analyze_downbeat_energy(
        rms, onset, downbeats, sr, hop_length,
        min_intro_length, max_intro_length
    )

    if not db_analysis:
        # Fallback if no valid downbeats
        return min_intro_length, {'error': 'no_downbeats'}

    # Calculate median energy levels (for "high energy" threshold)
    all_rms_after = [d['rms_after'] for d in db_analysis]
    all_onset_after = [d['onset_after'] for d in db_analysis]
    median_rms = np.median(all_rms_after)
    median_onset = np.median(all_onset_after)

    # Find the FIRST downbeat that looks like a drop
    # Criteria: High combined ratio OR (high energy AND some increase)
    drop_time = None
    drop_info = None

    for analysis in db_analysis:
        # Check if this looks like the drop
        combined = analysis['combined']
        rms_ratio = analysis['rms_ratio']
        onset_ratio = analysis['onset_ratio']
        rms_high = analysis['rms_after'] >= median_rms * 0.9
        onset_high = analysis['onset_after'] >= median_onset * 0.9

        # Drop detection rules:
        # 1. Combined ratio is significant (both RMS and onset increase)
        # 2. OR energy is high AND there's at least some increase
        is_drop = (
            combined > 1.35 or  # Clear energy jump
            (rms_high and onset_high and rms_ratio > 1.05 and onset_ratio > 1.05)  # High energy with increase
        )

        if is_drop:
            drop_time = analysis['time']
            drop_info = analysis
            break

    # Fallback: use downbeat with highest combined ratio
    if drop_time is None:
        best = max(db_analysis, key=lambda x: x['combined'])
        drop_time = best['time']
        drop_info = best

    debug_info = {
        'bpm': round(bpm, 1),
        'drop_time': round(drop_time, 3),
        'rms_ratio': round(drop_info['rms_ratio'], 2) if drop_info else 0,
        'onset_ratio': round(drop_info['onset_ratio'], 2) if drop_info else 0,
        'combined': round(drop_info['combined'], 2) if drop_info else 0,
        'final_drop': round(drop_time, 3)
    }

    return drop_time, debug_info


def find_beat_drop_from_filename(file_path: str, downbeats: np.ndarray) -> Optional[float]:
    """
    Try to extract beat drop time from filename metadata.

    Many AI-generated beat files encode the drop time in the filename, e.g.:
        "Song Name (96 BPM - 00;20.1 - 03;21.0).mp3"

    Returns the drop time snapped to nearest downbeat, or None if no metadata.
    """
    if parse_filename is None:
        return None

    filename = Path(file_path).name
    metadata = parse_filename(filename)

    if metadata is None:
        return None

    # Got metadata - snap to nearest downbeat
    expected_drop = metadata.beat_drop_time

    if len(downbeats) == 0:
        return expected_drop

    # Find closest downbeat to the expected drop time
    idx = np.argmin(np.abs(downbeats - expected_drop))
    return float(downbeats[idx])


def find_beat_drop(
    file_path: str,
    downbeats: np.ndarray,
    energy_threshold_percentile: float = 70,
    max_intro_length: float = 60.0,
    use_filename_metadata: bool = True
) -> float:
    """
    Find the beat drop time - first strong downbeat after intro.

    Args:
        file_path: Path to audio file
        downbeats: Array of downbeat timestamps
        energy_threshold_percentile: (deprecated)
        max_intro_length: Maximum intro length to search
        use_filename_metadata: If True, try to extract from filename first

    Returns:
        Beat drop time in seconds
    """
    # Strategy 1: Try to get from filename metadata (most accurate for labeled files)
    if use_filename_metadata:
        metadata_drop = find_beat_drop_from_filename(file_path, downbeats)
        if metadata_drop is not None:
            return metadata_drop

    # Strategy 2: Fall back to audio analysis
    drop_time, _ = find_beat_drop_advanced(
        file_path, downbeats,
        min_intro_length=5.0,
        max_intro_length=min(40.0, max_intro_length)
    )
    return drop_time


def find_beat_drop_simple(downbeats: np.ndarray, default_time: float = 0.0) -> float:
    """Simple fallback: just use the first downbeat."""
    if len(downbeats) > 0:
        return float(downbeats[0])
    return default_time


# Legacy function for compatibility
def find_energy_threshold_crossing(
    rms: np.ndarray,
    sr: int,
    hop_length: int,
    threshold_percentile: float = 75,
    min_time: float = 0.5
) -> float:
    """Find first time RMS exceeds threshold. (Legacy method)"""
    threshold = np.percentile(rms, threshold_percentile)
    min_frame = int(min_time * sr / hop_length)

    for i in range(min_frame, len(rms)):
        if rms[i] > threshold:
            return i * hop_length / sr

    return min_time
