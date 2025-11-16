# WebControl architecture

The project is split into two cooperating pieces:

1. **Gesture service** (`gesture-service/`)
   - Captures webcam frames through OpenCV.
   - Uses MediaPipe Hands to derive 3D keypoints and applies lightweight heuristics to emit `swipe_left`, `swipe_right`, `pinch`, and `closed_fist` events.
   - Broadcasts JSON blobs over a localhost WebSocket running on port `8765` by default.

2. **Chrome extension** (`extension/`)
   - Background service worker opens a WebSocket connection to the gesture service and translates gesture events into Chrome tab commands.
   - Content script shows a transient overlay on top of the active site so users receive haptic-free feedback.
   - Options UI lets you point the extension to a different WebSocket URL if you run the gesture service on another machine.

The system intentionally avoids Chrome native messaging to stay cross-platform. Communication is a simple JSON document:

```json
{
  "type": "swipe_left",
  "data": { "strength": 0.67 }
}
```

Supporting a new gesture only requires modifying `gesture-service/app.py` to emit the label and teaching `extension/background.js` how to respond.
