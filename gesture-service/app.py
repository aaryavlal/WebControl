"""Gesture detection service that streams commands to the Chrome extension."""
from __future__ import annotations

import asyncio
import json
import logging
import signal
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

import cv2
import mediapipe as mp
import numpy as np
import websockets

LOGGER = logging.getLogger("webcontrol.service")


@dataclass
class GestureEvent:
  """Serializable event passed to the extension."""

  type: str
  data: Optional[Dict[str, Any]] = None

  def to_dict(self) -> Dict[str, Any]:
    return {"type": self.type, "data": self.data or {}}


class WebSocketHub:
  """Tracks connected extension instances and broadcasts gesture events."""

  def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
    self.host = host
    self.port = port
    self._clients: set[websockets.WebSocketServerProtocol] = set()

  async def handler(self, websocket: websockets.WebSocketServerProtocol) -> None:
    LOGGER.info("Client connected: %s", websocket.remote_address)
    self._clients.add(websocket)
    try:
      async for _ in websocket:
        continue  # Extension currently only receives data.
    except websockets.ConnectionClosedOK:
      pass
    finally:
      self._clients.discard(websocket)
      LOGGER.info("Client disconnected: %s", websocket.remote_address)

  async def broadcast(self, event: GestureEvent) -> None:
    if not self._clients:
      return
    payload = json.dumps(event.to_dict())
    dead: list[websockets.WebSocketServerProtocol] = []
    for ws in list(self._clients):
      try:
        await ws.send(payload)
      except websockets.ConnectionClosed:
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
    cap = cv2.VideoCapture(self.camera_index)
    if not cap.isOpened():
      raise RuntimeError("Unable to open webcam. Check camera permissions and index.")
    hands = mp.solutions.hands.Hands(model_complexity=0, max_num_hands=1, min_detection_confidence=0.6)
    try:
      while not stop_signal.is_set():
        ok, frame = cap.read()
        if not ok:
          LOGGER.warning("Camera frame grab failed; retrying…")
          continue
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
          callback(event)
    finally:
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

    if len(self.history) == self.history.maxlen and self.cooldown == 0:
      delta = self.history[-1] - self.history[0]
      if abs(delta) > 0.15:
        event = GestureEvent("swipe_left" if delta < 0 else "swipe_right")
    pinch_distance = np.linalg.norm(index_tip[:2] - thumb_tip[:2])
    if pinch_distance < 0.03 and not self.pinch_active:
      self.pinch_active = True
      event = event or GestureEvent("pinch", {"strength": float(max(0.0, 0.05 - pinch_distance) * 20)})
    elif pinch_distance >= 0.04:
      self.pinch_active = False

    folded = self._folded_fingers(coords)
    if folded >= 3 and not self.fist_active:
      self.fist_active = True
      event = event or GestureEvent("closed_fist")
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
  logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
  hub = WebSocketHub(host, port)
  stop_event = asyncio.Event()
  loop = asyncio.get_running_loop()

  for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
    if sig is None:
      continue
    try:
      loop.add_signal_handler(sig, stop_event.set)
    except NotImplementedError:
      pass

  server = await websockets.serve(hub.handler, host, port)
  LOGGER.info("WebSocket listening on ws://%s:%s", host, port)

  detector = GestureDetector()
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
  detector_stop.set()
  await worker_task
  server.close()
  await server.wait_closed()


if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    pass
