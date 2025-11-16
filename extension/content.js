const OVERLAY_ID = "webcontrol-overlay";
const HIDE_DELAY_MS = 1500;
let hideTimer;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.source !== "webcontrol") return;
  const overlay = ensureOverlay();
  overlay.textContent = `Gesture: ${msg.type}`;
  overlay.style.opacity = "1";
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    overlay.style.opacity = "0";
  }, HIDE_DELAY_MS);
});

function ensureOverlay() {
  let el = document.getElementById(OVERLAY_ID);
  if (el) return el;
  el = document.createElement("div");
  el.id = OVERLAY_ID;
  el.style.position = "fixed";
  el.style.right = "16px";
  el.style.bottom = "16px";
  el.style.padding = "8px 12px";
  el.style.background = "rgba(0,0,0,.7)";
  el.style.color = "#fff";
  el.style.fontSize = "14px";
  el.style.borderRadius = "6px";
  el.style.zIndex = "2147483647";
  el.style.transition = "opacity .2s ease";
  el.style.pointerEvents = "none";
  el.style.opacity = "0";
  document.body.appendChild(el);
  return el;
}
