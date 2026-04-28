"""Gesture detection service that streams commands to the Chrome extension."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional

import cv2
import mediapipe as mp
import numpy as np
import websockets

LOG_LEVEL = os.environ.get("WEBCONTROL_LOG_LEVEL", "INFO").upper()
LOGGER = logging.getLogger("webcontrol.service")
LOGGER.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


@dataclass
class GestureEvent:
  """Serializable event passed to the extension."""

  type: str
  data: Optional[Dict[str, Any]] = None
  timestamp: float = field(default_factory=time.time)

  def to_dict(self) -> Dict[str, Any]:
    return {"type": self.type, "data": self.data or {}, "ts": self.timestamp}


class WebSocketHub:
  """Tracks connected extension instances and broadcasts gesture events."""

  def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
    self.host = host
    self.port = port
    self._clients: set[websockets.WebSocketServerProtocol] = set()
    self._total_connections = 0
    self._total_broadcasts = 0
    self._total_failed_sends = 0

  @property
  def client_count(self) -> int:
    return len(self._clients)

  @property
  def stats(self) -> Dict[str, Any]:
    return {
      "active_clients": self.client_count,
      "total_connections": self._total_connections,
      "total_broadcasts": self._total_broadcasts,
      "total_failed_sends": self._total_failed_sends,
    }

  async def handler(self, websocket: websockets.WebSocketServerProtocol) -> None:
    self._total_connections += 1
    LOGGER.info(
      "Client connected: %s (total active: %d, lifetime: %d)",
      websocket.remote_address,
      self.client_count + 1,
      self._total_connections,
    )
    self._clients.add(websocket)
    try:
      async for _ in websocket:
        continue  # Extension currently only receives data.
    except websockets.ConnectionClosedOK:
      LOGGER.debug("Client closed cleanly: %s", websocket.remote_address)
    except websockets.ConnectionClosedError as exc:
      LOGGER.warning("Client connection lost: %s (code=%s)", websocket.remote_address, exc.code)
    finally:
      self._clients.discard(websocket)
      LOGGER.info("Client disconnected: %s (remaining: %d)", websocket.remote_address, self.client_count)

  async def broadcast(self, event: GestureEvent) -> None:
    if not self._clients:
      LOGGER.debug("No clients connected, skipping broadcast of %s", event.type)
      return
    self._total_broadcasts += 1
    payload = json.dumps(event.to_dict())
    LOGGER.debug("Broadcasting %s to %d client(s)", event.type, self.client_count)
    dead: list[websockets.WebSocketServerProtocol] = []
    for ws in list(self._clients):
      try:
        await ws.send(payload)
      except websockets.ConnectionClosed:
        self._total_failed_sends += 1
        LOGGER.warning("Send failed to %s, marking for removal", ws.remote_address)
        dead.append(ws)
    for ws in dead:
      self._clients.discard(ws)


class GestureDetector:
  """Runs MediaPipe Hands and emits gesture labels."""

  def __init__(self, camera_index: int = 0) -> None:
    self.camera_index = camera_index
    self.history = deque(maxlen=6)
    self.cooldown_frames = 10
    self.cooldown = 0
    self.pinch_active = False
    self.fist_active = False

  def run(self, callback: Callable[[GestureEvent], None], stop_signal: threading.Event) -> None:
    LOGGER.info("Starting gesture detector on camera index %d", self.camera_index)
    cap = cv2.VideoCapture(self.camera_index)
    if not cap.isOpened():
      raise RuntimeError("Unable to open webcam. Check camera permissions and index.")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    LOGGER.info("Camera opened: %dx%d @ %.1f fps", width, height, fps)

    hands = mp.solutions.hands.Hands(
      model_complexity=0,
      max_num_hands=1,
      min_detection_confidence=0.6,
    )
    frames_processed = 0
    gestures_detected = 0
    start_time = time.monotonic()

    try:
      while not stop_signal.is_set():
        ok, frame = cap.read()
        if not ok:
          LOGGER.warning("Camera frame grab failed; retrying…")
          continue
        frames_processed += 1
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)
        if not result.multi_hand_landmarks:
          self.history.clear()
          self._tick_cooldown()
          continue
        landmark = result.multi_hand_landmarks[0]
        coords = np.array([(lm.x, lm.y, lm.z) for lm in landmark.landmark])
        event = self._interpret(coords)
        if event:
          gestures_detected += 1
          LOGGER.info("Gesture detected: %s (#%d)", event.type, gestures_detected)
          callback(event)
    finally:
      elapsed = time.monotonic() - start_time
      avg_fps = frames_processed / elapsed if elapsed > 0 else 0
      LOGGER.info(
        "Detector stopped: %d frames in %.1fs (avg %.1f fps), %d gestures detected",
        frames_processed, elapsed, avg_fps, gestures_detected,
      )
      cap.release()
      hands.close()

  def _tick_cooldown(self) -> None:
    self.cooldown = max(0, self.cooldown - 1)

  def _interpret(self, coords: np.ndarray) -> Optional[GestureEvent]:
    index_tip = coords[8]
    thumb_tip = coords[4]
    wrist = coords[0]
    self.history.append(index_tip[0])
    event: Optional[GestureEvent] = None

    # Swipe detection
    if len(self.history) == self.history.maxlen and self.cooldown == 0:
      delta = self.history[-1] - self.history[0]
      LOGGER.debug("Swipe delta: %.4f (threshold: 0.15)", delta)
      if abs(delta) > 0.15:
        direction = "swipe_left" if delta < 0 else "swipe_right"
        event = GestureEvent(direction, {"delta": float(delta)})

    # Pinch detection
    pinch_distance = float(np.linalg.norm(index_tip[:2] - thumb_tip[:2]))
    LOGGER.debug("Pinch distance: %.4f (active: %s)", pinch_distance, self.pinch_active)
    if pinch_distance < 0.03 and not self.pinch_active:
      self.pinch_active = True
      strength = float(max(0.0, 0.05 - pinch_distance) * 20)
      event = event or GestureEvent("pinch", {"strength": strength, "distance": pinch_distance})
    elif pinch_distance >= 0.04:
      self.pinch_active = False

    # Fist detection
    folded = self._folded_fingers(coords)
    LOGGER.debug("Folded fingers: %d (active: %s)", folded, self.fist_active)
    if folded >= 3 and not self.fist_active:
      self.fist_active = True
      event = event or GestureEvent("closed_fist", {"folded_count": folded})
    elif folded < 3:
      self.fist_active = False

    if event:
      self.cooldown = self.cooldown_frames
      self.history.clear()
      return event

    self._tick_cooldown()
    return None

  @staticmethod
  def _folded_fingers(coords: np.ndarray) -> int:
    tips = [8, 12, 16, 20]
    bases = [6, 10, 14, 18]
    count = 0
    for tip, base in zip(tips, bases):
      if coords[tip][1] > coords[base][1]:
        count += 1
    return count


async def main(host: str = "127.0.0.1", port: int = 8765) -> None:
  log_fmt = "[%(asctime)s %(levelname)s] %(name)s: %(message)s"
  logging.basicConfig(level=LOG_LEVEL, format=log_fmt, datefmt="%H:%M:%S")
  LOGGER.info("Starting WebControl service (log level: %s)", LOG_LEVEL)

  hub = WebSocketHub(host, port)
  stop_event = asyncio.Event()
  loop = asyncio.get_running_loop()
  service_start = time.monotonic()

  for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
    if sig is None:
      continue
    try:
      loop.add_signal_handler(sig, stop_event.set)
    except NotImplementedError:
      pass

  server = await websockets.serve(hub.handler, host, port)
  LOGGER.info("WebSocket listening on ws://%s:%s", host, port)

  camera_index = int(os.environ.get("WEBCONTROL_CAMERA", "0"))
  detector = GestureDetector(camera_index=camera_index)
  detector_stop = threading.Event()

  def detector_callback(event: GestureEvent) -> None:
    asyncio.run_coroutine_threadsafe(hub.broadcast(event), loop)

  async def detector_worker() -> None:
    try:
      await asyncio.to_thread(detector.run, detector_callback, detector_stop)
    except Exception:
      LOGGER.exception("Gesture detector stopped unexpectedly")
      stop_event.set()

  worker_task = asyncio.create_task(detector_worker())
  await stop_event.wait()

  LOGGER.info("Shutdown signal received, cleaning up…")
  detector_stop.set()
  await worker_task
  server.close()
  await server.wait_closed()

  uptime = time.monotonic() - service_start
  LOGGER.info("Service stopped after %.1fs uptime. Hub stats: %s", uptime, hub.stats)


if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    pass
