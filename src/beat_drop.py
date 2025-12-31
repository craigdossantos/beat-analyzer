"""
Detect the "beat drop" - the first strong downbeat where bass/drums kick in.

The beat drop is where the main rhythm kicks in. This module detects it by analyzing:
1. Sub-bass energy (low frequencies 20-120 Hz)
2. Percussive content (drums/kicks)
3. Spectral changes (new frequency content appearing)

For AI-generated beats with melodic intros, this works better than overall energy
since the intro often has similar loudness but lacks bass/drums.
"""
import numpy as np
import librosa
from pathlib import Path
from typing import Tuple, List, Optional


def compute_subbass_energy(y: np.ndarray, sr: int, hop_length: int = 512) -> np.ndarray:
    """
    Compute energy in the sub-bass range (20-120 Hz).
    This is where kick drums and bass live.
    """
    # Use STFT to get frequency content
    S = np.abs(librosa.stft(y, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr)

    # Find bins in sub-bass range (20-120 Hz)
    subbass_mask = (freqs >= 20) & (freqs <= 120)

    # Sum energy in sub-bass range for each frame
    subbass_energy = np.sum(S[subbass_mask, :], axis=0)

    return subbass_energy


def compute_percussive_energy(y: np.ndarray, sr: int, hop_length: int = 512) -> np.ndarray:
    """
    Extract percussive component and compute its energy.
    Drums/kicks will show up strongly in the percussive component.
    """
    # Harmonic-percussive separation
    y_harmonic, y_percussive = librosa.effects.hpss(y)

    # RMS energy of percussive component
    perc_rms = librosa.feature.rms(y=y_percussive, hop_length=hop_length)[0]

    return perc_rms


def compute_spectral_flux(y: np.ndarray, sr: int, hop_length: int = 512) -> np.ndarray:
    """
    Compute spectral flux - measures how much the spectrum changes over time.
    Large values indicate new frequency content appearing.
    """
    S = np.abs(librosa.stft(y, hop_length=hop_length))

    # Compute difference between consecutive frames
    flux = np.zeros(S.shape[1])
    for i in range(1, S.shape[1]):
        # Only count positive changes (new content appearing)
        diff = S[:, i] - S[:, i-1]
        flux[i] = np.sum(np.maximum(0, diff))

    return flux


def compute_onset_envelope(y: np.ndarray, sr: int, hop_length: int = 512) -> np.ndarray:
    """Compute onset strength envelope."""
    return librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)


def get_window_energy(signal: np.ndarray, center_frame: int, window_frames: int) -> float:
    """Get average energy in a window around center_frame."""
    start = max(0, center_frame - window_frames // 2)
    end = min(len(signal), center_frame + window_frames // 2)
    if start >= end:
        return 0.0
    return float(np.mean(signal[start:end]))


def analyze_downbeat_features(
    subbass: np.ndarray,
    percussive: np.ndarray,
    spectral_flux: np.ndarray,
    onset: np.ndarray,
    downbeats: np.ndarray,
    sr: int,
    hop_length: int,
    min_time: float = 5.0,
    max_time: float = 60.0
) -> List[dict]:
    """
    Analyze multiple features at each downbeat to find where the beat kicks in.

    Returns list of dicts with downbeat analysis.
    """
    valid_downbeats = downbeats[(downbeats >= min_time) & (downbeats <= max_time)]

    results = []
    window_seconds = 2.0
    window_frames = int(window_seconds * sr / hop_length)

    for db_time in valid_downbeats:
        frame = int(db_time * sr / hop_length)
        before_frame = int((db_time - 2.5) * sr / hop_length)
        after_frame = int((db_time + 1.0) * sr / hop_length)

        # Get features BEFORE this downbeat
        subbass_before = get_window_energy(subbass, before_frame, window_frames)
        perc_before = get_window_energy(percussive, before_frame, window_frames)
        flux_before = get_window_energy(spectral_flux, before_frame, window_frames)
        onset_before = get_window_energy(onset, before_frame, window_frames)

        # Get features AFTER this downbeat
        subbass_after = get_window_energy(subbass, after_frame, window_frames)
        perc_after = get_window_energy(percussive, after_frame, window_frames)
        flux_after = get_window_energy(spectral_flux, after_frame, window_frames)
        onset_after = get_window_energy(onset, after_frame, window_frames)

        # Calculate ratios (how much each feature increases)
        eps = 0.001  # Avoid division by zero
        subbass_ratio = subbass_after / (subbass_before + eps)
        perc_ratio = perc_after / (perc_before + eps)
        flux_ratio = flux_after / (flux_before + eps)
        onset_ratio = onset_after / (onset_before + eps)

        # Combined score emphasizing bass and percussion
        # Weight sub-bass and percussion more heavily
        combined_score = (
            subbass_ratio * 2.0 +  # Bass is very important
            perc_ratio * 2.0 +      # Percussion is very important
            flux_ratio * 1.0 +      # Spectral change matters
            onset_ratio * 1.0       # Onset strength
        ) / 6.0

        results.append({
            'time': db_time,
            'subbass_ratio': subbass_ratio,
            'perc_ratio': perc_ratio,
            'flux_ratio': flux_ratio,
            'onset_ratio': onset_ratio,
            'combined_score': combined_score,
            'subbass_after': subbass_after,
            'perc_after': perc_after,
        })

    return results


def find_beat_drop_advanced(
    file_path: str,
    downbeats: np.ndarray,
    min_intro_length: float = 5.0,
    max_intro_length: float = 60.0,
    bpm: float = None
) -> Tuple[float, dict]:
    """
    Find the beat drop by analyzing bass/percussion at downbeats.

    Strategy for AI-generated beats:
    1. These tracks often have consistent loudness throughout
    2. The "drop" is when BASS specifically kicks in (kick drum, sub-bass)
    3. Look for the FIRST downbeat where sub-bass is consistently high
    4. Use a "sustained high bass" approach rather than ratio-based

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

    # Compute features - focus on low frequencies
    subbass = compute_subbass_energy(y, sr, hop_length)
    percussive = compute_percussive_energy(y, sr, hop_length)
    onset = compute_onset_envelope(y, sr, hop_length)

    # Get valid downbeats in range
    # Start looking from 5s minimum, but we'll analyze relative to earlier content
    valid_downbeats = downbeats[(downbeats >= min_intro_length) & (downbeats <= max_intro_length)]

    if len(valid_downbeats) == 0:
        return min_intro_length, {'error': 'no_downbeats'}

    # Also get downbeats from very early (2-5s) to compare against
    early_downbeats = downbeats[(downbeats >= 2.0) & (downbeats < min_intro_length)]

    # Calculate baseline levels from first few seconds (likely intro)
    intro_end_frame = int(min_intro_length * sr / hop_length)
    intro_subbass = np.mean(subbass[:intro_end_frame]) if intro_end_frame > 0 else 0
    intro_subbass_std = np.std(subbass[:intro_end_frame]) if intro_end_frame > 0 else 0
    intro_perc = np.mean(percussive[:intro_end_frame]) if intro_end_frame > 0 else 0

    # Calculate the 75th percentile of sub-bass (represents "full bass" level)
    subbass_p75 = np.percentile(subbass, 75)
    perc_p75 = np.percentile(percussive, 75)

    # For each downbeat, check multiple features
    window_frames = int(2.0 * sr / hop_length)

    results = []
    for db_time in valid_downbeats:
        frame = int(db_time * sr / hop_length)

        # Get features AFTER this downbeat (next 2 seconds)
        start = frame
        end = min(len(subbass), frame + window_frames)
        if end <= start:
            continue

        subbass_level = np.mean(subbass[start:end])
        subbass_std = np.std(subbass[start:end])  # Variance indicates "punchy" bass
        perc_level = np.mean(percussive[start:end]) if end <= len(percussive) else 0

        # Is sub-bass at "full" level?
        subbass_full = subbass_level >= subbass_p75 * 0.7

        # Compare to intro baseline
        subbass_vs_intro = subbass_level / (intro_subbass + 0.001)
        perc_vs_intro = perc_level / (intro_perc + 0.001)

        # Bass "punchiness" - high variance means kick drum pattern (vs sustained bass)
        bass_punchiness = subbass_std / (subbass_level + 0.001)

        # Combined score: bass level + percussion + punchiness
        combined = (
            subbass_vs_intro * 0.4 +
            perc_vs_intro * 0.4 +
            (bass_punchiness * 10) * 0.2  # Scale punchiness
        )

        results.append({
            'time': db_time,
            'subbass_level': subbass_level,
            'subbass_full': subbass_full,
            'subbass_vs_intro': subbass_vs_intro,
            'perc_level': perc_level,
            'perc_vs_intro': perc_vs_intro,
            'bass_punchiness': bass_punchiness,
            'combined': combined,
        })

    if not results:
        return min_intro_length, {'error': 'no_analysis'}

    # NEW STRATEGY: Look for the biggest TRANSITION (change between consecutive downbeats)
    # The drop is where the biggest positive change in features happens

    # Calculate change between consecutive downbeats
    for i in range(1, len(results)):
        prev = results[i-1]
        curr = results[i]

        # Calculate the jump in features from previous to current
        subbass_jump = curr['subbass_level'] - prev['subbass_level']
        perc_jump = curr['perc_level'] - prev['perc_level']

        # Normalize jumps relative to overall levels
        subbass_jump_norm = subbass_jump / (np.mean([r['subbass_level'] for r in results]) + 0.001)
        perc_jump_norm = perc_jump / (np.mean([r['perc_level'] for r in results]) + 0.001)

        # Store the transition score
        results[i]['transition_score'] = max(0, subbass_jump_norm) + max(0, perc_jump_norm)

    # First result has no transition
    results[0]['transition_score'] = 0

    # Strategy 1: Find first downbeat with significant transition AND high absolute level
    drop_time = None
    drop_info = None

    transition_scores = [r['transition_score'] for r in results]
    if max(transition_scores) > 0:
        trans_p75 = np.percentile(transition_scores, 75)

        for r in results:
            # Drop when there's a significant transition AND bass is now high
            if r['transition_score'] >= trans_p75 and r['subbass_full']:
                drop_time = r['time']
                drop_info = r
                break

    # Strategy 2: First downbeat where bass and percussion are BOTH significantly higher than intro
    if drop_time is None:
        for r in results:
            if r['subbass_vs_intro'] > 1.2 and r['perc_vs_intro'] > 1.2:
                drop_time = r['time']
                drop_info = r
                break

    # Strategy 3: First downbeat with full bass
    if drop_time is None:
        for r in results:
            if r['subbass_full']:
                drop_time = r['time']
                drop_info = r
                break

    # Fallback: Downbeat with highest transition score, or highest combined if no transitions
    if drop_time is None:
        if max(transition_scores) > 0:
            best = max(results, key=lambda x: x['transition_score'])
        else:
            best = max(results, key=lambda x: x['combined'])
        drop_time = best['time']
        drop_info = best

    debug_info = {
        'bpm': round(bpm, 1),
        'drop_time': round(drop_time, 3),
        'subbass_vs_intro': round(drop_info.get('subbass_vs_intro', 0), 2) if drop_info else 0,
        'perc_vs_intro': round(drop_info.get('perc_vs_intro', 0), 2) if drop_info else 0,
        'combined': round(drop_info.get('combined', 0), 2) if drop_info else 0,
    }

    return drop_time, debug_info


def find_beat_drop(
    file_path: str,
    downbeats: np.ndarray,
    energy_threshold_percentile: float = 70,
    max_intro_length: float = 60.0,
    use_filename_metadata: bool = False  # Disabled by default now
) -> float:
    """
    Find the beat drop time - first strong downbeat where bass/drums kick in.

    Args:
        file_path: Path to audio file
        downbeats: Array of downbeat timestamps
        energy_threshold_percentile: (deprecated)
        max_intro_length: Maximum intro length to search
        use_filename_metadata: If True, try to extract from filename first (disabled)

    Returns:
        Beat drop time in seconds
    """
    # Use audio analysis (no filename cheating!)
    drop_time, _ = find_beat_drop_advanced(
        file_path, downbeats,
        min_intro_length=5.0,
        max_intro_length=min(60.0, max_intro_length)
    )
    return drop_time


def find_beat_drop_simple(downbeats: np.ndarray, default_time: float = 0.0) -> float:
    """Simple fallback: just use the first downbeat."""
    if len(downbeats) > 0:
        return float(downbeats[0])
    return default_time
