"""
Core beat detection using librosa (with optional madmom for enhanced accuracy).

librosa is used as the primary beat tracker since it's compatible with all Python versions.
madmom can be optionally installed for improved neural-network-based beat tracking.
"""
import numpy as np
import librosa
from pathlib import Path
from typing import Tuple

from .schemas import SongBeatData

# Try to import madmom (optional, for enhanced beat tracking)
try:
    import madmom
    MADMOM_AVAILABLE = True
except ImportError:
    MADMOM_AVAILABLE = False


def load_audio(file_path: str, sr: int = 22050) -> Tuple[np.ndarray, int]:
    """Load audio file and return samples + sample rate."""
    y, sr = librosa.load(file_path, sr=sr, mono=True)
    return y, sr


def normalize_tempo(bpm: float, beats: np.ndarray, min_bpm: float = 70, max_bpm: float = 165) -> Tuple[float, np.ndarray]:
    """
    Normalize tempo to a reasonable range by halving or doubling.

    Hip-hop and most popular music typically falls in the 70-160 BPM range.
    If detected tempo is outside this range, adjust by halving/doubling.

    Args:
        bpm: Detected tempo
        beats: Array of beat timestamps
        min_bpm: Minimum reasonable BPM (default 70)
        max_bpm: Maximum reasonable BPM (default 160)

    Returns:
        normalized_bpm: Tempo adjusted to reasonable range
        normalized_beats: Beat array adjusted accordingly
    """
    normalized_bpm = bpm
    normalized_beats = beats

    # If BPM is too high, halve it (take every other beat)
    while normalized_bpm > max_bpm and len(normalized_beats) > 1:
        normalized_bpm /= 2
        normalized_beats = normalized_beats[::2]

    # If BPM is too low, double it (interpolate beats)
    while normalized_bpm < min_bpm and normalized_bpm > 0:
        normalized_bpm *= 2
        # Interpolate new beats between existing ones
        if len(normalized_beats) > 1:
            new_beats = []
            for i in range(len(normalized_beats) - 1):
                new_beats.append(normalized_beats[i])
                mid_point = (normalized_beats[i] + normalized_beats[i + 1]) / 2
                new_beats.append(mid_point)
            new_beats.append(normalized_beats[-1])
            normalized_beats = np.array(new_beats)

    return normalized_bpm, normalized_beats


def detect_beats_and_tempo_librosa(y: np.ndarray, sr: int) -> Tuple[float, np.ndarray]:
    """
    Detect BPM and beat positions using librosa.

    Args:
        y: Audio samples
        sr: Sample rate

    Returns:
        bpm: Estimated tempo in beats per minute
        beats: Array of beat timestamps in seconds
    """
    # Get tempo and beat frames
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units='frames')

    # Convert tempo to scalar if it's an array
    if hasattr(tempo, '__len__'):
        bpm = float(tempo[0]) if len(tempo) > 0 else 120.0
    else:
        bpm = float(tempo)

    # Convert beat frames to timestamps
    beats = librosa.frames_to_time(beat_frames, sr=sr)

    # Normalize to reasonable tempo range (fixes double-time detection)
    bpm, beats = normalize_tempo(bpm, beats)

    return bpm, beats


def detect_beats_and_tempo_madmom(file_path: str) -> Tuple[float, np.ndarray]:
    """
    Detect BPM and beat positions using madmom's neural network.

    This is more accurate than librosa but requires madmom to be installed.

    Returns:
        bpm: Estimated tempo in beats per minute
        beats: Array of beat timestamps in seconds
    """
    if not MADMOM_AVAILABLE:
        raise ImportError("madmom is not installed")

    # Use madmom's RNN-based beat processor with DBN post-processing
    proc = madmom.features.beats.DBNBeatTrackingProcessor(fps=100)
    act = madmom.features.beats.RNNBeatProcessor()(file_path)
    beats = proc(act)

    # Calculate BPM from median beat interval
    if len(beats) > 1:
        intervals = np.diff(beats)
        median_interval = np.median(intervals)
        bpm = 60.0 / median_interval
    else:
        bpm = 120.0  # Fallback

    # Normalize to reasonable tempo range (fixes double-time detection)
    bpm, beats = normalize_tempo(bpm, beats)

    return bpm, beats


def detect_beats_and_tempo(file_path: str, y: np.ndarray = None, sr: int = 22050) -> Tuple[float, np.ndarray]:
    """
    Detect BPM and beat positions using the best available method.

    Uses madmom if available, otherwise falls back to librosa.

    Args:
        file_path: Path to audio file
        y: Pre-loaded audio samples (optional)
        sr: Sample rate

    Returns:
        bpm: Estimated tempo in beats per minute
        beats: Array of beat timestamps in seconds
    """
    if MADMOM_AVAILABLE:
        try:
            return detect_beats_and_tempo_madmom(file_path)
        except Exception:
            # Fall back to librosa if madmom fails
            pass

    # Use librosa
    if y is None:
        y, sr = load_audio(file_path, sr)
    return detect_beats_and_tempo_librosa(y, sr)


def detect_downbeats_madmom(file_path: str) -> np.ndarray:
    """
    Detect downbeats (beat 1 of each measure) using madmom.

    Returns:
        downbeats: Array of downbeat timestamps in seconds
    """
    if not MADMOM_AVAILABLE:
        raise ImportError("madmom is not installed")

    proc = madmom.features.downbeats.DBNDownBeatTrackingProcessor(
        beats_per_bar=[4, 3],  # Support 4/4 and 3/4 time
        fps=100
    )
    act = madmom.features.downbeats.RNNDownBeatProcessor()(file_path)
    results = proc(act)

    # Filter to only beat 1 (downbeats)
    downbeats = np.array([r[0] for r in results if r[1] == 1])

    return downbeats


def detect_downbeats_librosa(beats: np.ndarray, beats_per_measure: int = 4) -> np.ndarray:
    """
    Estimate downbeats from beat positions (librosa fallback).

    Since librosa doesn't detect downbeats directly, we assume the first beat
    is a downbeat and mark every Nth beat as a downbeat.

    Args:
        beats: Array of beat timestamps
        beats_per_measure: Number of beats per measure (default 4)

    Returns:
        downbeats: Array of estimated downbeat timestamps
    """
    if len(beats) == 0:
        return np.array([])

    # Take every Nth beat starting from the first
    downbeats = beats[::beats_per_measure]
    return downbeats


def detect_downbeats(file_path: str, beats: np.ndarray = None, beats_per_measure: int = 4) -> np.ndarray:
    """
    Detect downbeats using the best available method.

    Args:
        file_path: Path to audio file
        beats: Pre-detected beat timestamps (for librosa fallback)
        beats_per_measure: Number of beats per measure

    Returns:
        downbeats: Array of downbeat timestamps
    """
    if MADMOM_AVAILABLE:
        try:
            return detect_downbeats_madmom(file_path)
        except Exception:
            pass

    # Fall back to librosa estimation
    if beats is not None:
        return detect_downbeats_librosa(beats, beats_per_measure)

    return np.array([])


def estimate_confidence(beats: np.ndarray, bpm: float) -> float:
    """
    Estimate confidence based on beat regularity.

    High confidence = consistent intervals matching expected BPM.
    """
    if len(beats) < 4:
        return 0.5

    expected_interval = 60.0 / bpm
    intervals = np.diff(beats)

    # Calculate how much intervals deviate from expected
    deviations = np.abs(intervals - expected_interval) / expected_interval
    mean_deviation = np.mean(deviations)

    # Convert to 0-1 confidence (lower deviation = higher confidence)
    confidence = max(0, 1 - mean_deviation * 2)
    return round(confidence, 3)


def analyze_song(file_path: str) -> SongBeatData:
    """
    Complete analysis pipeline for a single song.

    Args:
        file_path: Path to MP3 file

    Returns:
        SongBeatData with all extracted metadata
    """
    file_path = Path(file_path)

    # Load audio for duration and librosa analysis
    y, sr = load_audio(str(file_path))
    duration = len(y) / sr

    # Detect beats and tempo
    bpm, beats = detect_beats_and_tempo(str(file_path), y, sr)

    # Detect downbeats
    downbeats = detect_downbeats(str(file_path), beats)

    # If we don't have downbeats, estimate from beats
    if len(downbeats) == 0 and len(beats) > 0:
        downbeats = detect_downbeats_librosa(beats, beats_per_measure=4)

    # Import beat drop detection
    from .beat_drop import find_beat_drop
    beat_drop_time = find_beat_drop(str(file_path), downbeats)

    # Estimate confidence
    confidence = estimate_confidence(beats, bpm)

    # Determine beats per measure from downbeat spacing
    if len(downbeats) > 1:
        downbeat_intervals = np.diff(downbeats)
        avg_downbeat_interval = np.median(downbeat_intervals)
        beat_interval = 60.0 / bpm
        beats_per_measure = round(avg_downbeat_interval / beat_interval)
        beats_per_measure = max(3, min(7, beats_per_measure))
    else:
        beats_per_measure = 4

    # Generate song_id from filename
    song_id = file_path.stem.lower().replace(" ", "_").replace("-", "_")

    return SongBeatData(
        song_id=song_id,
        filename=file_path.name,
        bpm=round(bpm, 1),
        beats_per_measure=beats_per_measure,
        beat_drop_time=round(beat_drop_time, 3),
        beats=[round(b, 3) for b in beats.tolist()],
        downbeats=[round(d, 3) for d in downbeats.tolist()],
        duration=round(duration, 1),
        confidence=confidence
    )
