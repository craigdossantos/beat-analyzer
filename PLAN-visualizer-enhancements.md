# Enhanced Beat Visualizer - Multi-File & Manual Beat Drop Selection

## Summary

Enhance the web visualizer to support:

1. **Multi-file browsing** - Load multiple audio files, browse in sidebar, auto-match JSON metadata
2. **Click-drag beat drop selection** - Highlight a region on waveform to manually mark beat drop
3. **Downbeat picker** - Show all downbeats in selected region, let user pick the correct one

## Files to Modify

| File                         | Changes                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| `verification-ui/index.html` | Add sidebar, selection overlay, beat drop picker panel             |
| `verification-ui/app.js`     | Add FileState, SelectionState, file management, selection handlers |
| `verification-ui/styles.css` | Two-panel layout, file list, selection overlay, picker styles      |

---

## Implementation Phases

### Phase 1: State Management Refactoring

Add structured state objects to manage multiple files and selections:

```javascript
const FileState = {
  files: new Map(), // Map<filename, FileEntry>
  activeFile: null, // Currently selected file
  modifiedFiles: new Set(), // Files with unsaved changes
};

const SelectionState = {
  isSelecting: false,
  startTime: null,
  endTime: null,
  downbeatsInRange: [],
};
```

### Phase 2: UI Layout - Two-Panel Design

```
+------------------------------------------------------------------+
| File Sidebar (280px)    |   Main Content (existing player)        |
| +---------------------+ |  +------------------------------------+  |
| | [+ Add Files]       | |  | Waveform + Selection Overlay       |  |
| | [Export All]        | |  +------------------------------------+  |
| +---------------------+ |  | Controls (existing)                 |  |
| | song1.mp3  [green]  | |  +------------------------------------+  |
| | song2.mp3  [yellow] | |  | Beat Drop Picker (when selecting)  |  |
| | song3.mp3  [blue]   | |  +------------------------------------+  |
+------------------------------------------------------------------+
```

**Status Indicators:**

- Green = Has JSON metadata
- Yellow = No JSON (needs metadata)
- Blue = Modified (unsaved changes)

### Phase 3: Multi-File Support

1. Replace single file inputs with `<input type="file" multiple>`
2. Process files: separate audio vs JSON, auto-match by filename
3. Render file list in sidebar with status indicators
4. Click file to load it (lazy-load audio buffer on selection)
5. Manual JSON load button for files without matches

**File Matching Logic:**

- `song.mp3` matches `song.json` (case-insensitive)
- Falls back to `song_id` field in JSON matching audio basename

### Phase 4: Region Selection on Waveform

**Interaction:**

1. **Shift+Click+Drag** on waveform to select time range
2. Blue semi-transparent overlay shows selected region
3. Release mouse to finalize selection
4. **Escape** to clear selection

**Implementation:**

- Add selection overlay div inside waveform container
- Track mouse events (mousedown/move/up) when Shift held
- Calculate start/end times from pixel positions
- Minimum 0.5s selection required

### Phase 5: Beat Drop Picker Panel

When region is selected, show panel with:

- Time range display (e.g., "0:15.0 - 0:18.0")
- Grid of downbeat options within that range
- Each option shows timestamp + preview button
- Click option to set as beat drop (updates marker immediately)
- Preview button plays 2.5s snippet around that downbeat

### Phase 6: Batch Export

- Track which files have been modified
- "Export All" button downloads all modified JSONs
- Visual indicator on modified files in sidebar

---

## Key User Interactions

| Action             | Trigger                      | Result                                   |
| ------------------ | ---------------------------- | ---------------------------------------- |
| Add files          | Click "+ Add Files"          | Opens multi-file picker                  |
| Switch file        | Click file in sidebar        | Loads audio + JSON, updates waveform     |
| Start selection    | Shift+Click+Drag on waveform | Blue highlight appears                   |
| Finalize selection | Release mouse                | Beat drop picker appears                 |
| Set beat drop      | Click downbeat option        | Updates beat_drop_time, refreshes marker |
| Preview downbeat   | Click preview button         | Plays 2.5s around that time              |
| Clear selection    | Press Escape                 | Dismisses selection and picker           |
| Export all         | Click "Export All"           | Downloads all modified JSONs             |

---

## Updated Keyboard Shortcuts

| Key                  | Action                |
| -------------------- | --------------------- |
| Space                | Play/Pause            |
| S                    | Stop                  |
| Left/Right           | Skip 5s               |
| D                    | Jump to beat drop     |
| C                    | Toggle click track    |
| **Shift+Click+Drag** | Select region (NEW)   |
| **Escape**           | Clear selection (NEW) |

---

## Implementation Order

1. **State refactoring** - Add FileState/SelectionState, preserve existing functionality
2. **HTML structure** - Add sidebar, selection overlay, picker panel
3. **CSS styling** - Two-panel layout, file list, selection styles
4. **File management** - Multi-file input, matching, sidebar rendering
5. **Selection handlers** - Mouse events, overlay updates, time calculation
6. **Beat drop picker** - Downbeat options, selection, preview playback
7. **Batch export** - Modification tracking, export all function
8. **Polish** - Help text updates, edge case handling, testing
