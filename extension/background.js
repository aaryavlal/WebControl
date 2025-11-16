const DEFAULT_SERVER_URL = "ws://127.0.0.1:8765";
const RECONNECT_DELAY_MS = 2000;
let currentBridge;

async function ensureDefaults() {
  const stored = await chrome.storage.sync.get({ gestureServerUrl: DEFAULT_SERVER_URL });
  if (!stored.gestureServerUrl) {
    await chrome.storage.sync.set({ gestureServerUrl: DEFAULT_SERVER_URL });
  }
  return stored.gestureServerUrl || DEFAULT_SERVER_URL;
}

async function init() {
  const url = await ensureDefaults();
  connect(url);
}

function connect(url) {
  if (currentBridge) {
    currentBridge.close();
  }
  currentBridge = new GestureBridge(url);
}

class GestureBridge {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.connect();
  }

  connect() {
    this.socket = new WebSocket(this.url);
    this.socket.addEventListener("open", () => console.log("WebControl connected"));
    this.socket.addEventListener("message", (evt) => this.handle(evt));
    this.socket.addEventListener("close", () => this.scheduleReconnect());
    this.socket.addEventListener("error", (err) => {
      console.error("WebControl bridge error", err);
      this.socket?.close();
    });
  }

  close() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.close();
    }
  }

  scheduleReconnect() {
    setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
  }

  handle(evt) {
    try {
      const payload = JSON.parse(evt.data);
      if (!payload?.type) return;
      applyGestureCommand(payload);
    } catch (err) {
      console.error("Invalid gesture payload", err);
    }
  }
}

async function applyGestureCommand({ type, data }) {
  switch (type) {
    case "swipe_left":
      await focusTabDelta(1);
      break;
    case "swipe_right":
      await focusTabDelta(-1);
      break;
    case "pinch":
      await chrome.tabs.create({ url: data?.url || "chrome://newtab" });
      break;
    case "closed_fist":
      await chrome.tabs.remove(data?.tabId || (await getActiveTab())?.id);
      break;
    default:
      console.warn("Unhandled gesture", type);
  }
  notifyContent(type, data);
}

async function focusTabDelta(delta) {
  const tabs = await chrome.tabs.query({ currentWindow: true });
  if (!tabs.length) return;
  const activeIndex = tabs.findIndex((tab) => tab.active);
  const nextIndex = (activeIndex + delta + tabs.length) % tabs.length;
  await chrome.tabs.highlight({ tabs: nextIndex });
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function notifyContent(type, data) {
  const tab = await getActiveTab();
  if (!tab?.id) return;
  chrome.tabs.sendMessage(tab.id, { source: "webcontrol", type, data });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({ gestureServerUrl: DEFAULT_SERVER_URL });
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "sync" || !changes.gestureServerUrl) return;
  connect(changes.gestureServerUrl.newValue || DEFAULT_SERVER_URL);
});

init();
