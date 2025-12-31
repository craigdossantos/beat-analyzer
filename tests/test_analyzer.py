"""
Tests for the beat analyzer.
"""
import pytest
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schemas import SongBeatData


class TestSongBeatData:
    """Test the Pydantic schema."""

    def test_valid_song_beat_data(self):
        """Test creating valid SongBeatData."""
        data = SongBeatData(
            song_id="test_song",
            filename="test_song.mp3",
            bpm=120.0,
            beats_per_measure=4,
            beat_drop_time=5.0,
            beats=[0.5, 1.0, 1.5, 2.0, 2.5],
            downbeats=[0.5, 2.5],
            duration=180.0,
            confidence=0.95
        )
        assert data.song_id == "test_song"
        assert data.bpm == 120.0
        assert len(data.beats) == 5
        assert data.confidence == 0.95

    def test_bpm_bounds(self):
        """Test BPM validation."""
        # Valid BPM
        data = SongBeatData(
            song_id="test",
            filename="test.mp3",
            bpm=96.0,
            beat_drop_time=0.0,
            beats=[0.5],
            downbeats=[0.5],
            duration=60.0,
            confidence=0.8
        )
        assert data.bpm == 96.0

        # BPM too low
        with pytest.raises(ValueError):
            SongBeatData(
                song_id="test",
                filename="test.mp3",
                bpm=10.0,  # Below 20 minimum
                beat_drop_time=0.0,
                beats=[0.5],
                downbeats=[0.5],
                duration=60.0,
                confidence=0.8
            )

        # BPM too high
        with pytest.raises(ValueError):
            SongBeatData(
                song_id="test",
                filename="test.mp3",
                bpm=350.0,  # Above 300 maximum
                beat_drop_time=0.0,
                beats=[0.5],
                downbeats=[0.5],
                duration=60.0,
                confidence=0.8
            )

    def test_confidence_bounds(self):
        """Test confidence validation."""
        # Valid confidence
        data = SongBeatData(
            song_id="test",
            filename="test.mp3",
            bpm=120.0,
            beat_drop_time=0.0,
            beats=[0.5],
            downbeats=[0.5],
            duration=60.0,
            confidence=0.5
        )
        assert data.confidence == 0.5

        # Confidence too low
        with pytest.raises(ValueError):
            SongBeatData(
                song_id="test",
                filename="test.mp3",
                bpm=120.0,
                beat_drop_time=0.0,
                beats=[0.5],
                downbeats=[0.5],
                duration=60.0,
                confidence=-0.1
            )

        # Confidence too high
        with pytest.raises(ValueError):
            SongBeatData(
                song_id="test",
                filename="test.mp3",
                bpm=120.0,
                beat_drop_time=0.0,
                beats=[0.5],
                downbeats=[0.5],
                duration=60.0,
                confidence=1.5
            )

    def test_json_serialization(self):
        """Test JSON export."""
        data = SongBeatData(
            song_id="test_song",
            filename="test_song.mp3",
            bpm=120.0,
            beats_per_measure=4,
            beat_drop_time=5.0,
            beats=[0.5, 1.0, 1.5],
            downbeats=[0.5],
            duration=180.0,
            confidence=0.95
        )
        json_str = data.model_dump_json()
        assert "test_song" in json_str
        assert "120.0" in json_str


class TestConfidenceEstimation:
    """Test confidence estimation logic."""

    def test_estimate_confidence_import(self):
        """Test that estimate_confidence can be imported."""
        from src.analyzer import estimate_confidence
        import numpy as np

        # Regular beats should have high confidence
        beats = np.array([0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
        bpm = 120.0  # 0.5 second intervals
        confidence = estimate_confidence(beats, bpm)
        assert confidence > 0.9

    def test_estimate_confidence_irregular(self):
        """Test confidence with irregular beats."""
        from src.analyzer import estimate_confidence
        import numpy as np

        # Irregular beats should have lower confidence
        beats = np.array([0.5, 1.2, 1.4, 2.5, 2.8, 3.0])
        bpm = 120.0
        confidence = estimate_confidence(beats, bpm)
        assert confidence < 0.9

    def test_estimate_confidence_few_beats(self):
        """Test confidence with very few beats."""
        from src.analyzer import estimate_confidence
        import numpy as np

        # Few beats should return default confidence
        beats = np.array([0.5, 1.0])
        bpm = 120.0
        confidence = estimate_confidence(beats, bpm)
        assert confidence == 0.5
