"""
Pydantic models defining the output JSON schema.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class SongBeatData(BaseModel):
    """Beat metadata for a single song."""

    # Identification
    song_id: str = Field(..., description="Unique identifier derived from filename")
    filename: str = Field(..., description="Original MP3 filename")

    # Tempo
    bpm: float = Field(..., ge=20, le=300, description="Beats per minute")
    beats_per_measure: int = Field(default=4, description="Time signature numerator (usually 4)")

    # Core timing data (all in seconds)
    beat_drop_time: float = Field(..., ge=0, description="First strong downbeat after intro")
    beats: List[float] = Field(..., min_length=1, description="All beat timestamps")
    downbeats: List[float] = Field(..., min_length=1, description="Beat 1 of each measure")

    # Metadata
    duration: float = Field(..., gt=0, description="Total song duration in seconds")
    confidence: float = Field(..., ge=0, le=1, description="Analysis confidence score")

    # Optional: for songs with defined end points
    end_time: Optional[float] = Field(default=None, description="When to stop playback")

    model_config = {
        "json_schema_extra": {
            "example": {
                "song_id": "are_we_cooked",
                "filename": "are_we_cooked.mp3",
                "bpm": 96.0,
                "beats_per_measure": 4,
                "beat_drop_time": 20.1,
                "beats": [20.1, 20.725, 21.35, 21.975, 22.6],
                "downbeats": [20.1, 22.6, 25.1],
                "duration": 201.0,
                "confidence": 0.94,
                "end_time": 198.0
            }
        }
    }
