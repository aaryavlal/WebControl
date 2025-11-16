# Gesture vocabulary

| Gesture       | Trigger condition (service)                                     | Chrome behavior                         |
| ------------- | ---------------------------------------------------------------- | --------------------------------------- |
| `swipe_left`  | Index x-history decreases > 0.15 within ~6 frames                | Focuses the next tab to the right       |
| `swipe_right` | Index x-history increases > 0.15 within ~6 frames                | Focuses the previous tab                |
| `pinch`       | Distance between thumb and index tips < 0.03 (normalized)        | Opens a new tab (or provided URL)       |
| `closed_fist` | Three or more fingertips folded beneath their proximal knuckle   | Closes the active tab                   |

## Improving recognition

- Adjust thresholds inside `GestureDetector._interpret` once you have real-world data; the defaults favor sensitivity for demos.
- Replace the heuristic classifier with a model stored under `gesture-service/models/` and load it inside `GestureDetector` when you outgrow MediaPipe-only calculations.
- Debounce gestures in `extension/background.js` if you add rapid-fire actions (e.g., volume scrub).
