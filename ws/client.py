"""
WebSocket Client — Connects Agent to VRBOT Hub (wss://ws.vrbot.me)
Reports status, receives commands from Dashboard
"""

import json
import asyncio
import logging
import time
from typing import Optional, Callable, Dict, Any

try:
    import websockets
except ImportError:
    websockets = None

log = logging.getLogger("vrbot.ws")


class WSClient:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self._ws = None
        self._connected = False
        self._handlers: Dict[str, Callable] = {}
        self._reconnect_delay = 5

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None

    def on(self, msg_type: str, handler: Callable):
        """Register a message handler"""
        self._handlers[msg_type] = handler

    async def send(self, msg_type: str, data: dict = None):
        """Send message to hub"""
        if not self.connected:
            return
        payload = {"type": msg_type, **(data or {})}
        try:
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            log.warning(f"Send failed: {e}")

    async def report_status(self, status: str, task: str = "", extra: dict = None):
        """Report agent status to dashboard"""
        await self.send("agent:status", {
            "status": status,
            "currentTask": task,
            "timestamp": int(time.time() * 1000),
            **(extra or {}),
        })

    async def report_task(self, task_id: str, status: str, message: str = ""):
        """Report task completion/failure"""
        await self.send("agent:task", {
            "taskId": task_id,
            "status": status,
            "message": message,
            "timestamp": int(time.time() * 1000),
        })

    async def report_log(self, level: str, message: str):
        """Send log line to dashboard"""
        await self.send("agent:log", {
            "level": level,
            "message": message,
            "timestamp": int(time.time() * 1000),
        })

    async def run(self, shutdown: asyncio.Event):
        """Main WebSocket loop with auto-reconnect"""
        if websockets is None:
            log.error("websockets package not installed. Run: pip install websockets")
            return

        while not shutdown.is_set():
            try:
                ws_url = f"{self.url}?token={self.token}&role=agent"
                log.info(f"Connecting to {self.url}...")

                async with websockets.connect(ws_url, ping_interval=30) as ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnect_delay = 5
                    log.info("WebSocket connected")

                    await self.report_status("online")

                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            msg_type = msg.get("type", "")

                            if msg_type in self._handlers:
                                await self._handlers[msg_type](msg)
                            elif msg_type == "command":
                                log.info(f"Command received: {msg.get('action')}")
                                if msg.get("action") in self._handlers:
                                    await self._handlers[msg["action"]](msg)

                        except json.JSONDecodeError:
                            pass

            except Exception as e:
                log.warning(f"WebSocket error: {e}")

            self._connected = False
            self._ws = None

            if not shutdown.is_set():
                log.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(60, self._reconnect_delay * 1.5)

    async def close(self):
        if self._ws:
            try:
                await self.report_status("offline")
                await self._ws.close()
            except Exception:
                pass
        self._connected = False
