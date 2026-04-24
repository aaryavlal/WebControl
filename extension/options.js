const form = document.getElementById("settings-form");
const statusEl = document.getElementById("status");
const urlInput = document.getElementById("server-url");
const testBtn = document.getElementById("test-btn");
const connDot = document.getElementById("conn-dot");
const connLabel = document.getElementById("conn-label");
const sensitivitySlider = document.getElementById("sensitivity");
const sensitivityValue = document.getElementById("sensitivity-value");
const cooldownInput = document.getElementById("cooldown");
const overlayToggle = document.getElementById("overlay-toggle");
const hapticToggle = document.getElementById("haptic-toggle");
const notifyToggle = document.getElementById("notify-toggle");

// ── Storage keys ────────────────────────────────────────────────────
const KEYS = [
  "gestureServerUrl",
  "confidenceThreshold",
  "gestureCooldown",
  "showOverlay",
  "hapticFeedback",
  "showNotification",
];

// ── Restore ─────────────────────────────────────────────────────────
async function restore() {
  const d = await chrome.storage.sync.get(KEYS);
  urlInput.value          = d.gestureServerUrl    || "ws://127.0.0.1:8765";
  sensitivitySlider.value = d.confidenceThreshold ?? 60;
  sensitivityValue.textContent = sensitivitySlider.value + "%";
  cooldownInput.value     = d.gestureCooldown     ?? 500;
  overlayToggle.checked   = d.showOverlay         ?? true;
  hapticToggle.checked    = d.hapticFeedback      ?? false;
  notifyToggle.checked    = d.showNotification    ?? true;
}

// ── Save ────────────────────────────────────────────────────────────
async function saveAll(evt) {
  if (evt) evt.preventDefault();
  await chrome.storage.sync.set({
    gestureServerUrl:    urlInput.value.trim(),
    confidenceThreshold: Number(sensitivitySlider.value),
    gestureCooldown:     Number(cooldownInput.value),
    showOverlay:         overlayToggle.checked,
    hapticFeedback:      hapticToggle.checked,
    showNotification:    notifyToggle.checked,
  });
  flash("settings saved", "ok");
}

// ── Connection test ─────────────────────────────────────────────────
function testConnection() {
  const url = urlInput.value.trim();
  if (!url) return;

  connDot.className = "conn-dot";
  connLabel.textContent = "connecting\u2026";

  let ws;
  const timeout = setTimeout(() => {
    ws.close();
    connDot.className = "conn-dot fail";
    connLabel.textContent = "timed out";
    flash("connection timed out after 5 s", "err");
  }, 5000);

  try {
    ws = new WebSocket(url);
  } catch {
    clearTimeout(timeout);
    connDot.className = "conn-dot fail";
    connLabel.textContent = "invalid url";
    flash("could not parse websocket url", "err");
    return;
  }

  ws.addEventListener("open", () => {
    clearTimeout(timeout);
    connDot.className = "conn-dot ok";
    connLabel.textContent = "connected";
    flash("connection successful", "ok");
    ws.close();
  });

  ws.addEventListener("error", () => {
    clearTimeout(timeout);
    connDot.className = "conn-dot fail";
    connLabel.textContent = "unreachable";
    flash("could not reach gesture service", "err");
  });
}

// ── Helpers ─────────────────────────────────────────────────────────
function flash(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = "status-msg " + type;
  setTimeout(() => {
    statusEl.textContent = "";
    statusEl.className = "status-msg";
  }, 3000);
}

// ── Events ──────────────────────────────────────────────────────────
form.addEventListener("submit", saveAll);
testBtn.addEventListener("click", testConnection);

sensitivitySlider.addEventListener("input", () => {
  sensitivityValue.textContent = sensitivitySlider.value + "%";
});

for (const el of [sensitivitySlider, cooldownInput, overlayToggle, hapticToggle, notifyToggle]) {
  el.addEventListener("change", () => saveAll());
}

restore();
