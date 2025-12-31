# Beat Analyzer

Analyze audio files for beats, downbeats, and beat drops. Includes a web-based verification UI for manual correction.

## Features

- **Beat Detection** - Detect beats and downbeats using librosa
- **Beat Drop Detection** - Automatically find the beat drop with confidence scoring
- **Filename Parsing** - Extract BPM and timestamps from filenames like `Song (120 BPM - 00;15.0 - 03;30.0).mp3`
- **JSON Export** - Export full beat timing data for use in other applications
- **Web Verification UI** - Visual interface to verify and correct beat drop positions

## Installation

```bash
# Clone the repository
git clone https://github.com/craigdossantos/beat-analyzer.git
cd beat-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Analyze a Single Song

```bash
python scripts/analyze_song.py path/to/song.mp3
```

### Batch Analyze Multiple Songs

```bash
python scripts/batch_analyze.py path/to/music/folder
```

### Output Format

Analysis results are saved as JSON:

```json
{
  "song_id": "song_name",
  "bpm": 120.5,
  "beats": [0.5, 1.0, 1.5, ...],
  "downbeats": [0.5, 2.5, 4.5, ...],
  "beat_drop_time": 15.234,
  "confidence": 0.95,
  "beats_per_measure": 4
}
```

## Verification UI

A web-based interface for verifying and correcting beat analysis results.

### Running the UI

Open `verification-ui/index.html` in your browser.

### Features

- **Multi-file Support** - Load multiple audio files with auto-matching JSON metadata
- **Waveform Visualization** - See the waveform with beat markers overlay
- **Click Track** - Audio click on each beat with adjustable volume
- **Region Selection** - Shift+drag to select a region and pick the correct beat drop
- **Auto-snap** - Automatically snaps beat drop to nearest downbeat based on filename
- **Zoom Controls** - Pinch/scroll to zoom, pan when zoomed
- **Quick Save** - One-click download of corrected JSON

### Keyboard Shortcuts

| Key        | Action             |
| ---------- | ------------------ |
| Space      | Play/Pause         |
| S          | Stop               |
| Left/Right | Skip 5 seconds     |
| D          | Jump to beat drop  |
| C          | Toggle click track |
| Esc        | Clear selection    |
| Cmd/Ctrl + | Zoom in            |
| Cmd/Ctrl - | Zoom out           |
| Cmd/Ctrl 0 | Reset zoom         |

### Status Indicators

- 🟢 Green - Has JSON metadata
- 🟡 Yellow - No JSON (needs metadata)
- 🔵 Blue - Modified (unsaved changes)

## Project Structure

```
beat-analyzer/
├── src/
│   ├── analyzer.py      # Core beat analysis
│   ├── beat_drop.py     # Beat drop detection
│   ├── filename_parser.py
│   └── schemas.py       # Data models
├── scripts/
│   ├── analyze_song.py  # Single file analysis
│   └── batch_analyze.py # Batch processing
├── verification-ui/
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── tests/
```

## License

MIT
