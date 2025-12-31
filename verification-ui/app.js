/**
 * Beat Verification UI
 * Allows accurate verification of beat detection results.
 * Supports multi-file browsing and manual beat drop selection.
 */

// ============================================
// FILE STATE MANAGEMENT
// ============================================
const FileState = {
  files: new Map(), // Map<filename, FileEntry>
  activeFile: null, // Currently selected audio filename
  modifiedFiles: new Set(), // Files with unsaved changes
};

// ============================================
// FILENAME METADATA PARSER
// ============================================
/**
 * Parse metadata from filenames like:
 * "Song Name (96 BPM - 00;20.1 - 03;21.0).mp3"
 */
function parseFilenameMetadata(filename) {
  const pattern =
    /^(.+?)\s*\((\d+\.?\d*)\s*BPM\s*-?\s*(\d+[;:]\d+\.?\d*)\s*-\s*(\d+[;:]\d+\.?\d*)\)/i;
  const baseName = filename.replace(/\.[^/.]+$/, "");
  const match = baseName.match(pattern);
  if (!match) return null;
  return {
    songName: match[1].trim(),
    bpm: parseFloat(match[2]),
    beatDropTime: parseTimestampStr(match[3]),
    endTime: parseTimestampStr(match[4]),
  };
}

function parseTimestampStr(ts) {
  ts = ts.replace(":", ";");
  const parts = ts.split(";");
  if (parts.length === 2) {
    return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
  }
  return parseFloat(ts);
}

/**
 * Find the nearest downbeat to a target time within a tolerance window
 */
function snapToNearestDownbeat(targetTime, downbeats, tolerance = 10) {
  if (!downbeats || downbeats.length === 0) return null;

  // Filter downbeats within tolerance window
  const nearby = downbeats.filter((t) => Math.abs(t - targetTime) <= tolerance);
  if (nearby.length === 0) return null;

  // Find closest
  return nearby.reduce((closest, t) =>
    Math.abs(t - targetTime) < Math.abs(closest - targetTime) ? t : closest,
  );
}

// FileEntry structure:
// {
//   audioFile: File,
//   audioBuffer: AudioBuffer | null,
//   jsonFile: File | null,
//   metadata: Object | null,
//   originalBeatDrop: number | null, // For tracking modifications
// }

// ============================================
// SELECTION STATE
// ============================================
const SelectionState = {
  isSelecting: false,
  startX: null,
  startTime: null,
  endTime: null,
  downbeatsInRange: [],
};

// ============================================
// ZOOM STATE
// ============================================
const ZoomState = {
  level: 1, // 1 = full view, higher = more zoomed in
  viewStart: 0, // Start time of visible window (in seconds)
  minLevel: 1,
  maxLevel: 50,
};

function getVisibleDuration() {
  if (!audioBuffer) return 0;
  return audioBuffer.duration / ZoomState.level;
}

function getViewEnd() {
  return ZoomState.viewStart + getVisibleDuration();
}

function timeToPixel(time) {
  if (!audioBuffer) return 0;
  const width = elements.waveformContainer.offsetWidth;
  const visibleDuration = getVisibleDuration();
  return ((time - ZoomState.viewStart) / visibleDuration) * width;
}

function pixelToTime(pixel) {
  if (!audioBuffer) return 0;
  const width = elements.waveformContainer.offsetWidth;
  const visibleDuration = getVisibleDuration();
  return ZoomState.viewStart + (pixel / width) * visibleDuration;
}

function clampViewStart() {
  if (!audioBuffer) return;
  const visibleDuration = getVisibleDuration();
  const maxStart = Math.max(0, audioBuffer.duration - visibleDuration);
  ZoomState.viewStart = Math.max(0, Math.min(ZoomState.viewStart, maxStart));
}

function zoomAt(centerTime, factor) {
  if (!audioBuffer) return;

  const oldLevel = ZoomState.level;
  const newLevel = Math.max(
    ZoomState.minLevel,
    Math.min(ZoomState.maxLevel, oldLevel * factor),
  );

  if (newLevel === oldLevel) return;

  // Calculate new view start to keep centerTime at same pixel position
  const oldVisibleDuration = audioBuffer.duration / oldLevel;
  const newVisibleDuration = audioBuffer.duration / newLevel;

  // Where was centerTime in the old view (0-1)?
  const centerRatio = (centerTime - ZoomState.viewStart) / oldVisibleDuration;

  // New view start to maintain that ratio
  ZoomState.level = newLevel;
  ZoomState.viewStart = centerTime - centerRatio * newVisibleDuration;

  clampViewStart();
  redrawZoomedView();
}

function panBy(deltaTime) {
  if (!audioBuffer) return;
  ZoomState.viewStart += deltaTime;
  clampViewStart();
  redrawZoomedView();
}

function resetZoom() {
  ZoomState.level = 1;
  ZoomState.viewStart = 0;
  redrawZoomedView();
}

function redrawZoomedView() {
  drawWaveform();
  drawBeatMarkers();
  updateSelectionOverlay();
  updateDisplay();
}

// ============================================
// AUDIO STATE
// ============================================
let audioContext = null;
let audioBuffer = null;
let sourceNode = null;
let metadata = null;

// Playback state
let isPlaying = false;
let playbackStartTime = 0;
let playbackOffset = 0;

// Click track
let clickBuffer = null;
let downbeatClickBuffer = null;
let lastTriggeredBeatIndex = -1;

// Animation
let rafId = null;

// ============================================
// DOM ELEMENTS
// ============================================
const $ = (id) => document.getElementById(id);

const elements = {
  // Sidebar
  fileInput: $("fileInput"),
  fileList: $("fileList"),
  exportAllBtn: $("exportAllBtn"),

  // Player
  player: $("player"),
  emptyState: $("emptyState"),
  waveform: $("waveform"),
  playhead: $("playhead"),
  beatMarkers: $("beatMarkers"),
  selectionOverlay: $("selectionOverlay"),
  beatIndicator: $("beatIndicator"),
  currentBeat: $("currentBeat"),
  beatsPerMeasure: $("beatsPerMeasure"),
  currentMeasure: $("currentMeasure"),

  // Beat drop picker
  beatDropPicker: $("beatDropPicker"),
  pickerTimeRange: $("pickerTimeRange"),
  clearSelection: $("clearSelection"),
  downbeatOptions: $("downbeatOptions"),

  // Controls
  playBtn: $("playBtn"),
  stopBtn: $("stopBtn"),
  skipBack: $("skipBack"),
  skipForward: $("skipForward"),
  currentTime: $("currentTime"),
  duration: $("duration"),
  clickTrack: $("clickTrack"),
  clickVolume: $("clickVolume"),

  // Metadata
  bpm: $("bpm"),
  beatDrop: $("beatDrop"),
  setDropBtn: $("setDropBtn"),
  confidence: $("confidence"),
  totalBeats: $("totalBeats"),
  totalDownbeats: $("totalDownbeats"),
  songId: $("songId"),

  // Actions
  jumpDrop: $("jumpDrop"),
  jumpStart: $("jumpStart"),
  exportBtn: $("exportBtn"),
  loadJsonBtn: $("loadJsonBtn"),
  manualJsonInput: $("manualJsonInput"),

  // Container references
  waveformContainer: document.querySelector(".waveform-container"),
};

// ============================================
// AUDIO INITIALIZATION
// ============================================
function initAudio() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    createClickSounds();
  }
  if (audioContext.state === "suspended") {
    audioContext.resume();
  }
}

function createClickSounds() {
  const sr = audioContext.sampleRate;
  clickBuffer = makeClick(sr, 1000, 0.03);
  downbeatClickBuffer = makeClick(sr, 1500, 0.05);
}

function makeClick(sr, freq, dur) {
  const len = Math.floor(sr * dur);
  const buf = audioContext.createBuffer(1, len, sr);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) {
    const t = i / sr;
    data[i] = Math.sin(2 * Math.PI * freq * t) * Math.exp(-t * 40) * 0.5;
  }
  return buf;
}

function playClickSound(isDownbeat) {
  if (!elements.clickTrack.checked) return;
  const buf = isDownbeat ? downbeatClickBuffer : clickBuffer;
  const src = audioContext.createBufferSource();
  src.buffer = buf;
  const gain = audioContext.createGain();
  gain.gain.value = elements.clickVolume.value / 100;
  src.connect(gain).connect(audioContext.destination);
  src.start();
}

// ============================================
// FILE MANAGEMENT
// ============================================
// Add Files button click handler
const addFilesBtn = document.getElementById("addFilesBtn");
addFilesBtn?.addEventListener("click", () => {
  elements.fileInput.click();
});

elements.fileInput.addEventListener("change", async (e) => {
  const files = Array.from(e.target.files);
  if (!files.length) return;

  await processFiles(files);
  renderFileList();

  // Auto-select first audio file if none selected
  if (!FileState.activeFile) {
    const firstAudio = Array.from(FileState.files.keys())[0];
    if (firstAudio) {
      await selectFile(firstAudio);
    }
  }

  // Clear input so same files can be re-selected
  e.target.value = "";
});

async function processFiles(files) {
  const audioFiles = [];
  const jsonFiles = [];

  // Separate audio and JSON files (case-insensitive extension check)
  for (const file of files) {
    if (file.name.toLowerCase().endsWith(".json")) {
      jsonFiles.push(file);
    } else {
      audioFiles.push(file);
    }
  }

  console.log(
    `Processing ${audioFiles.length} audio files and ${jsonFiles.length} JSON files`,
  );

  // Process audio files
  for (const audioFile of audioFiles) {
    const baseName = getBaseName(audioFile.name);

    // Find matching JSON by basename
    const matchingJson = jsonFiles.find((json) => {
      const jsonBase = getBaseName(json.name);
      const matches = jsonBase.toLowerCase() === baseName.toLowerCase();
      if (matches) {
        console.log(`  Matched: ${audioFile.name} <-> ${json.name}`);
      }
      return matches;
    });

    // Also check for song_id match if no direct match
    let matchedJson = matchingJson;
    if (!matchedJson) {
      for (const json of jsonFiles) {
        try {
          const text = await json.text();
          const data = JSON.parse(text);
          if (
            data.song_id &&
            baseName.toLowerCase().includes(data.song_id.toLowerCase())
          ) {
            matchedJson = json;
            break;
          }
        } catch {
          // Ignore parse errors
        }
      }
    }

    let jsonMetadata = null;
    if (matchedJson) {
      try {
        const text = await matchedJson.text();
        jsonMetadata = JSON.parse(text);
      } catch {
        // Ignore parse errors
      }
    }

    FileState.files.set(audioFile.name, {
      audioFile,
      audioBuffer: null,
      jsonFile: matchedJson || null,
      metadata: jsonMetadata,
      originalBeatDrop: jsonMetadata?.beat_drop_time || null,
    });
  }

  // Process orphaned JSON files (no matching audio)
  for (const json of jsonFiles) {
    const jsonBase = getBaseName(json.name);
    const hasMatch = Array.from(FileState.files.values()).some(
      (entry) =>
        entry.jsonFile === json ||
        getBaseName(entry.audioFile.name).toLowerCase() ===
          jsonBase.toLowerCase(),
    );

    if (!hasMatch) {
      // Store JSON for potential later matching
      console.log(`Orphaned JSON: ${json.name}`);
    }
  }
}

function getBaseName(filename) {
  return filename.replace(/\.[^/.]+$/, "");
}

function renderFileList() {
  const container = elements.fileList;

  if (FileState.files.size === 0) {
    container.innerHTML = '<div class="empty-state">No files loaded</div>';
    return;
  }

  container.innerHTML = "";

  for (const [filename, entry] of FileState.files) {
    const item = document.createElement("div");
    item.className = "file-item";
    if (filename === FileState.activeFile) {
      item.classList.add("active");
    }

    // Determine status
    let statusClass = "no-json";
    if (FileState.modifiedFiles.has(filename)) {
      statusClass = "modified";
    } else if (entry.metadata) {
      statusClass = "has-json";
    }

    item.innerHTML = `
      <div class="status-dot ${statusClass}"></div>
      <span class="file-name" title="${filename}">${filename}</span>
      ${FileState.modifiedFiles.has(filename) ? '<span class="file-badge">Modified</span>' : ""}
    `;

    item.addEventListener("click", () => selectFile(filename));
    container.appendChild(item);
  }

  // Update export all button
  elements.exportAllBtn.disabled = FileState.modifiedFiles.size === 0;
}

async function selectFile(filename) {
  const entry = FileState.files.get(filename);
  if (!entry) return;

  // Stop current playback
  stop();

  FileState.activeFile = filename;

  // Load audio buffer if needed
  if (!entry.audioBuffer) {
    initAudio();
    const arrayBuf = await entry.audioFile.arrayBuffer();
    entry.audioBuffer = await audioContext.decodeAudioData(arrayBuf);
  }

  audioBuffer = entry.audioBuffer;
  metadata = entry.metadata;

  // Update UI
  elements.duration.textContent = formatTime(audioBuffer.duration);
  drawWaveform();

  if (metadata) {
    // Try to auto-snap beat drop based on filename metadata
    const filenameMeta = parseFilenameMetadata(filename);
    if (filenameMeta && metadata.downbeats && metadata.downbeats.length > 0) {
      const expectedDrop = filenameMeta.beatDropTime;
      const snappedDrop = snapToNearestDownbeat(
        expectedDrop,
        metadata.downbeats,
        10,
      );

      if (snappedDrop !== null && snappedDrop !== metadata.beat_drop_time) {
        const oldDrop = metadata.beat_drop_time;
        metadata.beat_drop_time = snappedDrop;

        // Mark as modified since we changed the beat drop
        FileState.modifiedFiles.add(filename);

        showToast(
          `Beat drop auto-snapped: ${formatTime(oldDrop, true)} → ${formatTime(snappedDrop, true)}`,
        );
        console.log(
          `Auto-snapped beat drop from ${oldDrop.toFixed(3)}s to ${snappedDrop.toFixed(3)}s (filename expected: ${expectedDrop.toFixed(1)}s)`,
        );
      }
    }

    elements.bpm.textContent = metadata.bpm.toFixed(1);
    elements.beatDrop.value = metadata.beat_drop_time.toFixed(3);
    elements.confidence.textContent = `${(metadata.confidence * 100).toFixed(0)}%`;
    elements.totalBeats.textContent = metadata.beats.length;
    elements.totalDownbeats.textContent = metadata.downbeats.length;
    elements.songId.textContent = metadata.song_id;
    elements.beatsPerMeasure.textContent = metadata.beats_per_measure || 4;
    drawBeatMarkers();
  } else {
    elements.bpm.textContent = "--";
    elements.beatDrop.value = "";
    elements.confidence.textContent = "--";
    elements.totalBeats.textContent = "--";
    elements.totalDownbeats.textContent = "--";
    elements.songId.textContent = "--";
    elements.beatsPerMeasure.textContent = "4";
    elements.beatMarkers.innerHTML = "";
  }

  // Show player, hide empty state
  elements.player.classList.remove("hidden");
  elements.emptyState.classList.add("hidden");

  // Reset zoom and clear selection
  ZoomState.level = 1;
  ZoomState.viewStart = 0;
  clearSelection();

  // Re-render file list to update active state
  renderFileList();
  updateDisplay();
}

// Manual JSON load for current file
elements.loadJsonBtn?.addEventListener("click", () => {
  elements.manualJsonInput.click();
});

elements.manualJsonInput?.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file || !FileState.activeFile) return;

  try {
    const text = await file.text();
    const jsonData = JSON.parse(text);

    const entry = FileState.files.get(FileState.activeFile);
    if (entry) {
      entry.jsonFile = file;
      entry.metadata = jsonData;
      entry.originalBeatDrop = jsonData.beat_drop_time;
      metadata = jsonData;

      // Update display
      elements.bpm.textContent = metadata.bpm.toFixed(1);
      elements.beatDrop.value = metadata.beat_drop_time.toFixed(3);
      elements.confidence.textContent = `${(metadata.confidence * 100).toFixed(0)}%`;
      elements.totalBeats.textContent = metadata.beats.length;
      elements.totalDownbeats.textContent = metadata.downbeats.length;
      elements.songId.textContent = metadata.song_id;
      elements.beatsPerMeasure.textContent = metadata.beats_per_measure || 4;

      drawBeatMarkers();
      renderFileList();
    }
  } catch (err) {
    console.error("Failed to load JSON:", err);
    alert("Failed to parse JSON file");
  }

  e.target.value = "";
});

// ============================================
// WAVEFORM DRAWING
// ============================================
function drawWaveform() {
  const canvas = elements.waveform;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;

  const w = canvas.offsetWidth;
  const h = canvas.offsetHeight;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  const data = audioBuffer.getChannelData(0);
  const sampleRate = audioBuffer.sampleRate;
  const totalSamples = data.length;
  const duration = audioBuffer.duration;

  // Calculate visible range based on zoom
  const visibleDuration = getVisibleDuration();
  const startSample = Math.floor(
    (ZoomState.viewStart / duration) * totalSamples,
  );
  const endSample = Math.floor((getViewEnd() / duration) * totalSamples);
  const visibleSamples = endSample - startSample;

  const step = Math.max(1, Math.ceil(visibleSamples / w));

  ctx.fillStyle = "#0a1628";
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "#3b82f6";
  ctx.lineWidth = 1;
  ctx.beginPath();

  const mid = h / 2;
  for (let i = 0; i < w; i++) {
    let min = 1,
      max = -1;
    const base = startSample + i * step;
    for (let j = 0; j < step && base + j < totalSamples; j++) {
      const v = data[base + j];
      if (v < min) min = v;
      if (v > max) max = v;
    }
    ctx.moveTo(i, mid + min * mid * 0.85);
    ctx.lineTo(i, mid + max * mid * 0.85);
  }
  ctx.stroke();

  // Draw zoom indicator if zoomed in
  if (ZoomState.level > 1) {
    ctx.fillStyle = "rgba(255, 255, 255, 0.7)";
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`${ZoomState.level.toFixed(1)}x`, w - 8, 16);
  }
}

function drawBeatMarkers() {
  if (!metadata || !audioBuffer) return;

  const container = elements.beatMarkers;
  container.innerHTML = "";

  const width = elements.waveformContainer.offsetWidth;
  const downbeatSet = new Set(metadata.downbeats.map((d) => d.toFixed(3)));
  const viewStart = ZoomState.viewStart;
  const viewEnd = getViewEnd();

  // Beat markers - only draw visible ones
  for (const t of metadata.beats) {
    // Skip beats outside visible range
    if (t < viewStart - 0.1 || t > viewEnd + 0.1) continue;

    const el = document.createElement("div");
    el.className = "beat-marker";
    if (downbeatSet.has(t.toFixed(3))) {
      el.classList.add("downbeat");
    }
    el.style.left = `${timeToPixel(t)}px`;
    container.appendChild(el);
  }

  // Beat drop marker - always show if in view
  const dropTime = metadata.beat_drop_time;
  if (dropTime >= viewStart - 0.5 && dropTime <= viewEnd + 0.5) {
    const dropEl = document.createElement("div");
    dropEl.className = "beat-marker drop";
    dropEl.style.left = `${timeToPixel(dropTime)}px`;
    container.appendChild(dropEl);
  }
}

// ============================================
// SELECTION HANDLING
// ============================================
function initSelectionHandlers() {
  const container = elements.waveformContainer;

  container.addEventListener("mousedown", (e) => {
    if (!audioBuffer) return;

    // Only start selection on Shift+Click
    if (!e.shiftKey) return;

    e.preventDefault();
    SelectionState.isSelecting = true;
    SelectionState.startX = e.clientX;

    const rect = container.getBoundingClientRect();
    const pixelX = e.clientX - rect.left;
    SelectionState.startTime = pixelToTime(pixelX);
    SelectionState.endTime = SelectionState.startTime;

    updateSelectionOverlay();
  });

  document.addEventListener("mousemove", (e) => {
    if (!SelectionState.isSelecting || !audioBuffer) return;

    const rect = container.getBoundingClientRect();
    const pixelX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    SelectionState.endTime = pixelToTime(pixelX);

    updateSelectionOverlay();
  });

  document.addEventListener("mouseup", () => {
    if (!SelectionState.isSelecting) return;

    SelectionState.isSelecting = false;

    // Check minimum selection (0.5s)
    const start = Math.min(SelectionState.startTime, SelectionState.endTime);
    const end = Math.max(SelectionState.startTime, SelectionState.endTime);

    if (end - start < 0.5) {
      // Too short, clear selection
      clearSelection();
      return;
    }

    // Normalize times
    SelectionState.startTime = start;
    SelectionState.endTime = end;

    // Show beat drop picker
    showBeatDropPicker();
  });

  // Waveform click to seek (without shift)
  container.addEventListener("click", (e) => {
    if (e.shiftKey || SelectionState.isSelecting) return;
    if (!audioBuffer) return;

    const rect = container.getBoundingClientRect();
    const pixelX = e.clientX - rect.left;
    seekTo(pixelToTime(pixelX));
  });
}

function updateSelectionOverlay() {
  const overlay = elements.selectionOverlay;

  if (
    SelectionState.startTime === null ||
    SelectionState.endTime === null ||
    !audioBuffer
  ) {
    overlay.classList.add("hidden");
    return;
  }

  overlay.classList.remove("hidden");

  const start = Math.min(SelectionState.startTime, SelectionState.endTime);
  const end = Math.max(SelectionState.startTime, SelectionState.endTime);

  const leftPx = timeToPixel(start);
  const rightPx = timeToPixel(end);

  overlay.style.left = `${leftPx}px`;
  overlay.style.width = `${rightPx - leftPx}px`;
}

function clearSelection() {
  SelectionState.startTime = null;
  SelectionState.endTime = null;
  SelectionState.downbeatsInRange = [];

  elements.selectionOverlay.classList.add("hidden");
  elements.beatDropPicker.classList.add("hidden");
}

elements.clearSelection?.addEventListener("click", clearSelection);

// ============================================
// BEAT DROP PICKER
// ============================================
function showBeatDropPicker() {
  if (!metadata || !audioBuffer) {
    clearSelection();
    return;
  }

  const start = SelectionState.startTime;
  const end = SelectionState.endTime;

  // Find downbeats in range
  SelectionState.downbeatsInRange = metadata.downbeats.filter(
    (t) => t >= start && t <= end,
  );

  // If no downbeats, use regular beats
  if (SelectionState.downbeatsInRange.length === 0) {
    SelectionState.downbeatsInRange = metadata.beats.filter(
      (t) => t >= start && t <= end,
    );
  }

  if (SelectionState.downbeatsInRange.length === 0) {
    alert("No beats found in selected range");
    clearSelection();
    return;
  }

  // Update picker UI
  elements.pickerTimeRange.textContent = `${formatTime(start, true)} - ${formatTime(end, true)}`;

  const optionsContainer = elements.downbeatOptions;
  optionsContainer.innerHTML = "";

  for (const time of SelectionState.downbeatsInRange) {
    const option = document.createElement("div");
    option.className = "downbeat-option";
    option.innerHTML = `
      <span class="time">${formatTime(time, true)}</span>
      <button class="preview-btn" title="Preview">&#9658;</button>
    `;

    // Click to set as beat drop
    option.addEventListener("click", (e) => {
      if (e.target.classList.contains("preview-btn")) return;
      setBeatDrop(time);
    });

    // Preview button
    option.querySelector(".preview-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      previewBeatDrop(time);
    });

    optionsContainer.appendChild(option);
  }

  elements.beatDropPicker.classList.remove("hidden");
}

function setBeatDrop(time) {
  if (!metadata || !FileState.activeFile) return;

  // Update metadata
  metadata.beat_drop_time = time;

  // Update UI
  elements.beatDrop.value = time.toFixed(3);

  // Mark file as modified
  const entry = FileState.files.get(FileState.activeFile);
  if (entry && entry.originalBeatDrop !== time) {
    FileState.modifiedFiles.add(FileState.activeFile);
  } else if (entry && entry.originalBeatDrop === time) {
    FileState.modifiedFiles.delete(FileState.activeFile);
  }

  // Redraw markers
  drawBeatMarkers();

  // Update file list
  renderFileList();

  // Clear selection
  clearSelection();
}

function previewBeatDrop(time) {
  // Play 2.5 seconds starting from 1 second before the beat
  const previewStart = Math.max(0, time - 1);
  seekTo(previewStart);
  play();

  // Stop after 2.5 seconds
  setTimeout(() => {
    if (isPlaying) {
      pause();
    }
  }, 2500);
}

// ============================================
// PLAYBACK CONTROLS
// ============================================
function getCurrentTime() {
  if (!audioContext || !audioBuffer) return 0;
  if (isPlaying) {
    return playbackOffset + (audioContext.currentTime - playbackStartTime);
  }
  return playbackOffset;
}

function play() {
  if (!audioBuffer || isPlaying) return;

  initAudio();

  sourceNode = audioContext.createBufferSource();
  sourceNode.buffer = audioBuffer;
  sourceNode.connect(audioContext.destination);

  sourceNode.onended = () => {
    if (isPlaying) {
      stop();
    }
  };

  const offset = Math.max(0, Math.min(playbackOffset, audioBuffer.duration));
  playbackStartTime = audioContext.currentTime;
  sourceNode.start(0, offset);

  isPlaying = true;
  lastTriggeredBeatIndex = -1;
  elements.playBtn.textContent = "Pause";

  startAnimationLoop();
}

function pause() {
  if (!isPlaying) return;

  playbackOffset = getCurrentTime();

  if (sourceNode) {
    sourceNode.onended = null;
    try {
      sourceNode.stop();
    } catch (e) {}
    sourceNode = null;
  }

  isPlaying = false;
  elements.playBtn.textContent = "Play";

  stopAnimationLoop();
  updateDisplay();
}

function stop() {
  if (sourceNode) {
    sourceNode.onended = null;
    try {
      sourceNode.stop();
    } catch (e) {}
    sourceNode = null;
  }

  isPlaying = false;
  playbackOffset = 0;
  lastTriggeredBeatIndex = -1;
  elements.playBtn.textContent = "Play";

  stopAnimationLoop();
  updateDisplay();
}

function togglePlay() {
  if (isPlaying) {
    pause();
  } else {
    play();
  }
}

function seekTo(time) {
  if (!audioBuffer) return;

  const wasPlaying = isPlaying;

  if (sourceNode) {
    sourceNode.onended = null;
    try {
      sourceNode.stop();
    } catch (e) {}
    sourceNode = null;
  }

  isPlaying = false;
  playbackOffset = Math.max(0, Math.min(time, audioBuffer.duration));
  lastTriggeredBeatIndex = -1;

  updateDisplay();

  if (wasPlaying) {
    play();
  }
}

function skip(seconds) {
  seekTo(getCurrentTime() + seconds);
}

// ============================================
// ANIMATION LOOP
// ============================================
function startAnimationLoop() {
  stopAnimationLoop();
  rafId = requestAnimationFrame(animationLoop);
}

function stopAnimationLoop() {
  if (rafId) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

function animationLoop() {
  updateDisplay();
  if (isPlaying) {
    rafId = requestAnimationFrame(animationLoop);
  }
}

function updateDisplay() {
  if (!audioBuffer) return;

  const time = getCurrentTime();

  elements.currentTime.textContent = formatTime(time, true);

  // Position playhead using zoom-aware calculation
  const playheadPx = timeToPixel(time);
  const width = elements.waveformContainer.offsetWidth;
  elements.playhead.style.left = `${(playheadPx / width) * 100}%`;

  // Auto-scroll to keep playhead visible when zoomed and playing
  if (isPlaying && ZoomState.level > 1) {
    const viewEnd = getViewEnd();
    const visibleDuration = getVisibleDuration();
    // If playhead is past 80% of the visible area, scroll forward
    if (time > ZoomState.viewStart + visibleDuration * 0.8) {
      ZoomState.viewStart = time - visibleDuration * 0.2;
      clampViewStart();
      drawWaveform();
      drawBeatMarkers();
      updateSelectionOverlay();
    }
  }

  if (!metadata) return;

  let beatIdx = -1;
  for (let i = 0; i < metadata.beats.length; i++) {
    if (metadata.beats[i] <= time) {
      beatIdx = i;
    } else {
      break;
    }
  }

  if (beatIdx >= 0) {
    const bpm = metadata.beats_per_measure || 4;
    elements.currentBeat.textContent = (beatIdx % bpm) + 1;
    elements.currentMeasure.textContent = Math.floor(beatIdx / bpm) + 1;

    if (isPlaying && beatIdx !== lastTriggeredBeatIndex) {
      lastTriggeredBeatIndex = beatIdx;
      const beatTime = metadata.beats[beatIdx];
      const isDownbeat = metadata.downbeats.some(
        (d) => Math.abs(d - beatTime) < 0.02,
      );
      playClickSound(isDownbeat);
      flashIndicator(isDownbeat);
    }
  } else {
    elements.currentBeat.textContent = "-";
    elements.currentMeasure.textContent = "-";
  }
}

function flashIndicator(isDownbeat) {
  const el = elements.beatIndicator;
  el.classList.remove("flash", "flash-down");
  void el.offsetWidth;
  el.classList.add(isDownbeat ? "flash-down" : "flash");
}

function formatTime(sec, showMs = false) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  const ms = Math.floor((sec % 1) * 1000);
  if (showMs) {
    return `${m}:${s.toString().padStart(2, "0")}.${ms.toString().padStart(3, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ============================================
// BATCH EXPORT
// ============================================
elements.exportAllBtn?.addEventListener("click", () => {
  for (const filename of FileState.modifiedFiles) {
    const entry = FileState.files.get(filename);
    if (!entry || !entry.metadata) continue;

    exportSingleFile(entry.metadata, filename);
  }

  // Clear modified state
  FileState.modifiedFiles.clear();
  renderFileList();
});

elements.exportBtn?.addEventListener("click", () => {
  if (!metadata) return;

  // Update beat_drop_time from input
  metadata.beat_drop_time = parseFloat(elements.beatDrop.value);

  exportSingleFile(metadata, FileState.activeFile || "beat_metadata");

  // Clear modified state for this file
  if (FileState.activeFile) {
    const entry = FileState.files.get(FileState.activeFile);
    if (entry) {
      entry.originalBeatDrop = metadata.beat_drop_time;
    }
    FileState.modifiedFiles.delete(FileState.activeFile);
    renderFileList();
  }
});

function exportSingleFile(data, originalFilename) {
  const baseName = getBaseName(originalFilename);
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${baseName}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// Track beat drop changes
elements.beatDrop?.addEventListener("change", () => {
  if (!FileState.activeFile || !metadata) return;

  const newValue = parseFloat(elements.beatDrop.value);
  const entry = FileState.files.get(FileState.activeFile);

  if (entry) {
    metadata.beat_drop_time = newValue;

    if (entry.originalBeatDrop !== newValue) {
      FileState.modifiedFiles.add(FileState.activeFile);
    } else {
      FileState.modifiedFiles.delete(FileState.activeFile);
    }

    drawBeatMarkers();
    renderFileList();
  }
});

// ============================================
// EVENT LISTENERS
// ============================================
elements.playBtn?.addEventListener("click", togglePlay);
elements.stopBtn?.addEventListener("click", stop);
elements.skipBack?.addEventListener("click", () => skip(-5));
elements.skipForward?.addEventListener("click", () => skip(5));
elements.jumpStart?.addEventListener("click", () => seekTo(0));
elements.jumpDrop?.addEventListener("click", () => {
  seekTo(parseFloat(elements.beatDrop.value) || 0);
});
elements.setDropBtn?.addEventListener("click", () => {
  const time = getCurrentTime();
  elements.beatDrop.value = time.toFixed(3);

  // Trigger change event to track modification
  elements.beatDrop.dispatchEvent(new Event("change"));
});

// Keyboard shortcuts
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;

  // Zoom keyboard shortcuts (Cmd on Mac, Ctrl on Windows)
  if (e.metaKey || e.ctrlKey) {
    switch (e.code) {
      case "Equal": // Cmd/Ctrl + = (plus)
      case "NumpadAdd":
        e.preventDefault();
        zoomAt(getCurrentTime(), 1.5);
        return;
      case "Minus": // Cmd/Ctrl + -
      case "NumpadSubtract":
        e.preventDefault();
        zoomAt(getCurrentTime(), 0.67);
        return;
      case "Digit0": // Cmd/Ctrl + 0
      case "Numpad0":
        e.preventDefault();
        resetZoom();
        return;
    }
  }

  switch (e.code) {
    case "Space":
      e.preventDefault();
      togglePlay();
      break;
    case "ArrowLeft":
      e.preventDefault();
      skip(-5);
      break;
    case "ArrowRight":
      e.preventDefault();
      skip(5);
      break;
    case "KeyS":
      e.preventDefault();
      stop();
      break;
    case "KeyD":
      e.preventDefault();
      seekTo(parseFloat(elements.beatDrop.value) || 0);
      break;
    case "KeyC":
      e.preventDefault();
      elements.clickTrack.checked = !elements.clickTrack.checked;
      break;
    case "Escape":
      e.preventDefault();
      clearSelection();
      break;
  }
});

// Resize handler
window.addEventListener("resize", () => {
  if (audioBuffer) {
    drawWaveform();
    drawBeatMarkers();
    updateSelectionOverlay();
  }
});

// ============================================
// ZOOM EVENT HANDLERS
// ============================================
function initZoomHandlers() {
  const container = elements.waveformContainer;

  // Wheel handler for zoom and pan
  container.addEventListener(
    "wheel",
    (e) => {
      if (!audioBuffer) return;

      // Pinch-to-zoom on Mac trackpad sends ctrlKey with wheel
      // Cmd+scroll also zooms
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();

        // Get mouse position for zoom center
        const rect = container.getBoundingClientRect();
        const pixelX = e.clientX - rect.left;
        const centerTime = pixelToTime(pixelX);

        // Zoom factor - negative deltaY = zoom in, positive = zoom out
        const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
        zoomAt(centerTime, zoomFactor);
      } else if (ZoomState.level > 1) {
        // Pan when zoomed - use horizontal scroll or vertical scroll for horizontal pan
        e.preventDefault();

        const visibleDuration = getVisibleDuration();
        // Use deltaX for horizontal scroll, fall back to deltaY for vertical scroll
        const delta = e.deltaX !== 0 ? e.deltaX : e.deltaY;
        // Pan by a fraction of visible duration
        const panAmount = (delta / 500) * visibleDuration;
        panBy(panAmount);
      }
    },
    { passive: false },
  );
}

initZoomHandlers();

// ============================================
// TOAST NOTIFICATIONS
// ============================================
function showToast(message, duration = 3000) {
  // Remove existing toast
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ============================================
// HELP PANEL
// ============================================
function toggleHelp() {
  const panel = elements.helpPanel;
  if (panel) {
    panel.classList.toggle("hidden");
    localStorage.setItem("helpVisible", !panel.classList.contains("hidden"));
  }
}

function initHelpPanel() {
  // Restore help panel state from localStorage
  const helpVisible = localStorage.getItem("helpVisible") === "true";
  const panel = elements.helpPanel;
  if (panel && helpVisible) {
    panel.classList.remove("hidden");
  }
}

// ============================================
// SAVE WORKFLOW
// ============================================
async function quickSave() {
  if (!metadata || !FileState.activeFile) return;

  // Update beat_drop_time from input
  metadata.beat_drop_time = parseFloat(elements.beatDrop.value);

  const baseName = getBaseName(FileState.activeFile);
  const blob = new Blob([JSON.stringify(metadata, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${baseName}.json`;
  a.click();
  URL.revokeObjectURL(url);

  // Update original beat drop and clear modified state
  const entry = FileState.files.get(FileState.activeFile);
  if (entry) {
    entry.originalBeatDrop = metadata.beat_drop_time;
  }
  FileState.modifiedFiles.delete(FileState.activeFile);
  renderFileList();

  showToast(`Downloaded ${baseName}.json - replace original file to save`);
}

async function saveAs() {
  if (!metadata || !FileState.activeFile) return;

  // Update beat_drop_time from input
  metadata.beat_drop_time = parseFloat(elements.beatDrop.value);

  const baseName = getBaseName(FileState.activeFile);
  const blob = new Blob([JSON.stringify(metadata, null, 2)], {
    type: "application/json",
  });

  // Try File System Access API (Chrome/Edge)
  if ("showSaveFilePicker" in window) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: `${baseName}.json`,
        types: [
          {
            description: "JSON Files",
            accept: { "application/json": [".json"] },
          },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();

      // Update original beat drop and clear modified state
      const entry = FileState.files.get(FileState.activeFile);
      if (entry) {
        entry.originalBeatDrop = metadata.beat_drop_time;
      }
      FileState.modifiedFiles.delete(FileState.activeFile);
      renderFileList();

      showToast(`Saved ${baseName}.json`);
      return;
    } catch (err) {
      if (err.name === "AbortError") return; // User cancelled
      console.error("File System Access API failed:", err);
    }
  }

  // Fallback to standard download
  quickSave();
}

// ============================================
// INITIALIZATION
// ============================================
initSelectionHandlers();
initHelpPanel();

// Add help panel element reference
elements.helpPanel = $("helpPanel");
elements.helpBtn = $("helpBtn");
elements.quickSaveBtn = $("quickSaveBtn");
elements.saveAsBtn = $("saveAsBtn");

// Help button handler
elements.helpBtn?.addEventListener("click", toggleHelp);

// Save button handlers
elements.quickSaveBtn?.addEventListener("click", quickSave);
elements.saveAsBtn?.addEventListener("click", saveAs);
