# WebControl

Control Chrome with hand gestures. This repo contains:

- `extension/` – a Manifest V3 Chrome extension that connects to the local gesture service over WebSocket, translates recognized gestures into tab commands, and shows a lightweight in-page overlay for feedback.
- `gesture-service/` – a Python service that uses MediaPipe Hands + OpenCV to detect simple gestures (`swipe_left`, `swipe_right`, `pinch`, `closed_fist`) and streams them as JSON to any connected extension instance.
- `docs/` – architecture notes and gesture definitions.

## Getting started

1. **Install the gesture service dependencies**

   ```bash
   cd gesture-service
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```

   The service listens on `ws://127.0.0.1:8765` by default. Edit `gesture-service/app.py` if you need a different host/port.

2. **Load the Chrome extension**

   - Open `chrome://extensions`.
   - Enable _Developer mode_.
   - Click _Load unpacked_ and point Chrome to the `extension/` directory.
   - Optionally open the extension’s options page to change the WebSocket URL.

3. **Navigate with gestures**

   With both pieces running, the background service worker receives gesture events and issues tab navigation commands:

   - Swipe left/right → move across tabs.
   - Pinch → open a new tab (or the URL provided by the service).
   - Closed fist → close the current tab.

See `docs/` for deeper architecture notes and ideas for expanding the gesture vocabulary.
