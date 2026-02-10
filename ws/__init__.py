"""
VRBOT Agent — WebSocket Client
Connects to WSS Hub for remote monitoring and control from Dashboard.
"""
import asyncio
import json
import logging
import time

log = logging.getLogger("vrbot.ws")


class WSClient:
    """WebSocket client for VRBOT Hub communication."""

    def __init__(self, url, token, reconnect_delay=5, heartbeat_interval=30):
        self.url = url
        self.token = token
        self.reconnect_delay = reconnect_delay
        self.heartbeat_interval = heartbeat_interval
        self._ws = None
        self._connected = False
        self._handlers = {}
        self._send_queue = asyncio.Queue()

    async def connect(self):
        """Connect to WSS Hub."""
        try:
            import websockets
        except ImportError:
            log.error("websockets not installed. Run: pip install websockets")
            return False

        while True:
            try:
                self._ws = await websockets.connect(
                    self.url,
                    extra_headers={"Authorization": f"Bearer {self.token}"},
                    ping_interval=20,
                    ping_timeout=10,
                )
                self._connected = True
                log.info(f"✅ Connected to WSS Hub: {self.url}")

                # Send auth
                await self.send("auth", {"token": self.token, "type": "agent"})

                # Start listeners
                await asyncio.gather(
                    self._receive_loop(),
                    self._send_loop(),
                    self._heartbeat_loop(),
                )

            except Exception as e:
                self._connected = False
                log.warning(f"WS connection failed: {e}. Retrying in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)

    async def send(self, event, data=None):
        """Send message to Hub."""
        msg = json.dumps({"event": event, "data": data or {}})
        await self._send_queue.put(msg)

    def send_sync(self, event, data=None):
        """Synchronous send (for use in non-async task code)."""
        msg = json.dumps({"event": event, "data": data or {}})
        try:
            self._send_queue.put_nowait(msg)
        except Exception:
            pass

    def on(self, event, handler):
        """Register event handler."""
        self._handlers[event] = handler

    async def send_status(self, status_data):
        """Send agent status update."""
        await self.send("agent:status", status_data)

    async def send_task_update(self, task_info):
        """Send task completion/failure update."""
        await self.send("agent:task_update", task_info)

    async def send_screenshot(self, png_base64):
        """Send screenshot to dashboard."""
        await self.send("agent:screenshot", {"image": png_base64})

    @property
    def connected(self):
        return self._connected

    # ─── Internal Loops ───────────────────────────────────────

    async def _receive_loop(self):
        """Listen for incoming messages."""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    event = data.get("event", "")
                    payload = data.get("data", {})

                    log.debug(f"WS received: {event}")

                    handler = self._handlers.get(event)
                    if handler:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(payload)
                        else:
                            handler(payload)

                except json.JSONDecodeError:
                    log.warning(f"Invalid WS message: {message[:100]}")
        except Exception as e:
            log.warning(f"WS receive error: {e}")
            self._connected = False

    async def _send_loop(self):
        """Process outgoing message queue."""
        while self._connected:
            try:
                msg = await asyncio.wait_for(self._send_queue.get(), timeout=1)
                if self._ws and self._connected:
                    await self._ws.send(msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.warning(f"WS send error: {e}")

    async def _heartbeat_loop(self):
        """Send periodic heartbeat."""
        while self._connected:
            await asyncio.sleep(self.heartbeat_interval)
            await self.send("heartbeat", {"timestamp": int(time.time())})

    async def disconnect(self):
        """Close connection."""
        self._connected = False
        if self._ws:
            await self._ws.close()
        log.info("WS disconnected")

