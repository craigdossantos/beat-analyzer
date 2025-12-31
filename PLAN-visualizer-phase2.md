# Visualizer Enhancement Plan - Phase 2

## User Requests

1. **Show instructions on page** - Add visible help/shortcuts panel
2. **Fix auto-matching** - JSON files with same name not being matched
3. **Improve save workflow** - One-click overwrite instead of file picker
4. **Auto-snap beat drop** - Use filename metadata to auto-select nearest downbeat

---

## 1. Instructions Panel

**Goal:** Add a toggleable help panel showing all shortcuts and instructions

**Implementation:**

- Add "?" button in the header that toggles a help overlay/panel
- Panel shows:
  - Keyboard shortcuts (Space, S, Arrow keys, D, C, Escape)
  - Selection instructions (Shift+Click+Drag)
  - Status dot legend (Green=has JSON, Yellow=no JSON, Blue=modified)
- Save preference to localStorage

**Files:** `index.html`, `styles.css`, `app.js`

---

## 2. Fix Auto-Matching

**Root cause identified:** The file extension check is case-sensitive (`.json` only)

**Current code (line 185):**

```javascript
if (file.name.endsWith(".json")) {
```

**Fix:**

```javascript
if (file.name.toLowerCase().endsWith(".json")) {
```

**Additional improvements:**

- Add console logging to debug matching attempts
- Show match status in UI (e.g., "Matched: filename.json")

**Files:** `app.js` (processFiles function)

---

## 3. Improved Save Workflow

**Goal:** Provide flexible save options - quick download or file picker

**Implementation:** Two buttons with different behaviors:

### "Quick Save" button (primary)

- Downloads JSON with exact same filename as the original
- Shows toast: "Downloaded {filename}.json - replace original to save"
- Fast workflow for batch processing

### "Save As" button (secondary)

- Uses File System Access API where supported (Chrome/Edge)
- Falls back to standard download with file picker on Safari/Firefox
- Pre-fills original filename

**UI Changes:**

- Replace "Export JSON" with "Quick Save" (primary style)
- Add "Save As" button next to it (secondary style)
- Remove `_corrected` suffix from exported filenames

**Files:** `app.js` (exportSingleFile function, add new handlers), `index.html` (update buttons)

---

## 4. Auto-Snap Beat Drop from Filename

**Goal:** When loading a file with metadata in the filename, automatically find the nearest downbeat within ±5-10 seconds

**Implementation:**

### 4.1 Port filename parser to JavaScript

```javascript
function parseFilenameMetadata(filename) {
  const pattern =
    /^(.+?)\s*\((\d+\.?\d*)\s*BPM\s*-?\s*(\d+;\d+\.?\d*)\s*-\s*(\d+;\d+\.?\d*)\)/i;
  const match = filename.replace(/\.[^/.]+$/, "").match(pattern);
  if (!match) return null;
  return {
    songName: match[1].trim(),
    bpm: parseFloat(match[2]),
    beatDropTime: parseTimestamp(match[3]),
    endTime: parseTimestamp(match[4]),
  };
}

function parseTimestamp(ts) {
  ts = ts.replace(":", ";");
  const [min, sec] = ts.split(";");
  return parseInt(min) * 60 + parseFloat(sec);
}
```

### 4.2 Add snap-to-downbeat function

```javascript
function snapToNearestDownbeat(targetTime, downbeats, tolerance = 10) {
  // Filter downbeats within tolerance window
  const nearby = downbeats.filter((t) => Math.abs(t - targetTime) <= tolerance);
  if (nearby.length === 0) return null;

  // Find closest
  return nearby.reduce((closest, t) =>
    Math.abs(t - targetTime) < Math.abs(closest - targetTime) ? t : closest,
  );
}
```

### 4.3 Integration into file loading flow

In `selectFile()` after loading metadata:

1. Parse filename for expected beat drop time
2. If metadata exists with downbeats, find nearest downbeat within ±10s
3. If found and different from current beat_drop_time, auto-update and mark as modified
4. Show notification: "Beat drop auto-snapped from {X}s to {Y}s (nearest downbeat)"

**Files:** `app.js` (add parser functions, modify selectFile)

---

## Implementation Order

1. **Fix auto-matching** (quick fix, high impact)
2. **Add filename parser** (foundation for #4)
3. **Auto-snap beat drop** (uses parser)
4. **Instructions panel** (independent)
5. **Improve save workflow** (independent)

---

## Files to Modify

| File                         | Changes                                                       |
| ---------------------------- | ------------------------------------------------------------- |
| `verification-ui/app.js`     | Fix matching, add parser, auto-snap logic, Quick Save/Save As |
| `verification-ui/index.html` | Add help button/panel, Quick Save/Save As buttons             |
| `verification-ui/styles.css` | Help panel styling, toast notifications                       |
