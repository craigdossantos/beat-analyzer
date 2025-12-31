"""
Beat Analyzer - Extract beat timing metadata from audio files.
"""

from .schemas import SongBeatData
from .analyzer import analyze_song

__version__ = "0.1.0"
__all__ = ["SongBeatData", "analyze_song"]
