const OVERLAY_ID = "webcontrol-overlay";
const HIDE_DELAY_MS = 1500;
let hideTimer;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.source !== "webcontrol") return;
  const overlay = ensureOverlay();
  overlay.textContent = msg.type;
  overlay.style.opacity = "1";
  overlay.style.transform = "translateY(0)";
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    overlay.style.opacity = "0";
    overlay.style.transform = "translateY(6px)";
  }, HIDE_DELAY_MS);
});

function ensureOverlay() {
  let el = document.getElementById(OVERLAY_ID);
  if (el) return el;

  el = document.createElement("div");
  el.id = OVERLAY_ID;
  Object.assign(el.style, {
    position:      "fixed",
    right:         "20px",
    bottom:        "20px",
    padding:       "8px 16px",
    background:    "rgba(13, 14, 18, .88)",
    backdropFilter: "blur(12px)",
    color:         "#f59e0b",
    fontFamily:    "'JetBrains Mono', 'Fira Code', monospace",
    fontSize:      "12px",
    fontWeight:    "600",
    letterSpacing: "1px",
    textTransform: "uppercase",
    borderRadius:  "6px",
    border:        "1px solid rgba(245, 158, 11, .25)",
    boxShadow:     "0 4px 24px rgba(0, 0, 0, .4), 0 0 12px rgba(245, 158, 11, .08)",
    zIndex:        "2147483647",
    transition:    "opacity .25s ease, transform .25s ease",
    pointerEvents: "none",
    opacity:       "0",
    transform:     "translateY(6px)",
  });

  document.body.appendChild(el);
  return el;
}
