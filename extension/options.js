const form = document.getElementById("settings-form");
const statusLabel = document.getElementById("status");
const input = document.getElementById("server-url");
const testBtn = document.getElementById("test-btn");
const connDot = document.getElementById("conn-dot");
const connLabel = document.getElementById("conn-label");
const sensitivitySlider = document.getElementById("sensitivity");
const sensitivityValue = document.getElementById("sensitivity-value");
const cooldownInput = document.getElementById("cooldown");
const overlayToggle = document.getElementById("overlay-toggle");
const hapticToggle = document.getElementById("haptic-toggle");
const notifyToggle = document.getElementById("notify-toggle");

// ── Restore saved settings ──────────────────────────────────────────

async function restore() {
  const data = await chrome.storage.sync.get([
    "gestureServerUrl",
    "confidenceThreshold",
    "gestureCooldown",
    "showOverlay",
    "hapticFeedback",
    "showNotification",
  ]);

  input.value = data.gestureServerUrl || "ws://127.0.0.1:8765";
  sensitivitySlider.value = data.confidenceThreshold ?? 60;
  sensitivityValue.textContent = sensitivitySlider.value + "%";
  cooldownInput.value = data.gestureCooldown ?? 500;
  overlayToggle.checked = data.showOverlay ?? true;
  hapticToggle.checked = data.hapticFeedback ?? false;
  notifyToggle.checked = data.showNotification ?? true;
}

// ── Save all settings ───────────────────────────────────────────────

async function saveAll(evt) {
  if (evt) evt.preventDefault();

  await chrome.storage.sync.set({
    gestureServerUrl: input.value.trim(),
    confidenceThreshold: Number(sensitivitySlider.value),
    gestureCooldown: Number(cooldownInput.value),
    showOverlay: overlayToggle.checked,
    hapticFeedback: hapticToggle.checked,
    showNotification: notifyToggle.checked,
  });

  showStatus("All settings saved", "success");
}

// ── Connection test ─────────────────────────────────────────────────

function testConnection() {
  const url = input.value.trim();
  if (!url) return;

  connDot.className = "dot";
  connLabel.textContent = "Connecting\u2026";

  let ws;
  const timeout = setTimeout(() => {
    ws.close();
    connDot.className = "dot disconnected";
    connLabel.textContent = "Timed out";
    showStatus("Connection timed out after 5 s", "error");
  }, 5000);

  try {
    ws = new WebSocket(url);
  } catch {
    clearTimeout(timeout);
    connDot.className = "dot disconnected";
    connLabel.textContent = "Invalid URL";
    showStatus("Could not parse WebSocket URL", "error");
    return;
  }

  ws.addEventListener("open", () => {
    clearTimeout(timeout);
    connDot.className = "dot connected";
    connLabel.textContent = "Connected";
    showStatus("Connection successful", "success");
    ws.close();
  });

  ws.addEventListener("error", () => {
    clearTimeout(timeout);
    connDot.className = "dot disconnected";
    connLabel.textContent = "Unreachable";
    showStatus("Could not reach gesture service", "error");
  });
}

// ── Helpers ─────────────────────────────────────────────────────────

function showStatus(msg, type) {
  statusLabel.textContent = msg;
  statusLabel.className = "status " + type;
  setTimeout(() => {
    statusLabel.textContent = "";
    statusLabel.className = "status";
  }, 3000);
}

// ── Event listeners ─────────────────────────────────────────────────

form.addEventListener("submit", saveAll);
testBtn.addEventListener("click", testConnection);

sensitivitySlider.addEventListener("input", () => {
  sensitivityValue.textContent = sensitivitySlider.value + "%";
});

// Auto-save toggles and sliders on change
for (const el of [sensitivitySlider, cooldownInput, overlayToggle, hapticToggle, notifyToggle]) {
  el.addEventListener("change", () => saveAll());
}

restore();
