const form = document.getElementById("settings-form");
const statusLabel = document.getElementById("status");
const input = document.getElementById("server-url");

async function restore() {
  const { gestureServerUrl } = await chrome.storage.sync.get("gestureServerUrl");
  input.value = gestureServerUrl || "ws://127.0.0.1:8765";
}

async function save(evt) {
  evt.preventDefault();
  const url = input.value.trim();
  await chrome.storage.sync.set({ gestureServerUrl: url });
  statusLabel.textContent = "Saved";
  setTimeout(() => (statusLabel.textContent = ""), 1500);
}

form.addEventListener("submit", save);
restore();
