"""
VRBOT Socket.IO Client v1.0
==============================
Real-time communication with vrbot-site dashboard.

Features:
  - Auto-connect with reconnection
  - Bot state broadcasting (state, task, cycle, stats)
  - Remote commands: start, stop, pause, resume, run_task
  - Dynamic config updates from dashboard
  - Heartbeat for connection monitoring

Usage:
  from socketio_client import VRBotSocketClient
  client = VRBotSocketClient("https://vrbot-site.vercel.app")
  client.connect()
  client.emit_status(bot_state.get_status())
"""

import os
import time
import json
import logging
import threading
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger("vrbot.socketio")


class VRBotSocketClient:
    """Socket.IO client for vrbot-site real-time communication."""

    def __init__(self, server_url: str = None, agent_id: str = None,
                 auth_token: str = None):
        """
        Args:
            server_url: WebSocket server URL (e.g., https://vrbot-site.vercel.app)
            agent_id: Unique identifier for this bot agent
            auth_token: Authentication token for secure connection
        """
        self.server_url = server_url or os.environ.get(
            "VRBOT_WS_URL", "https://vrbot-site.vercel.app")
        self.agent_id = agent_id or os.environ.get(
            "VRBOT_AGENT_ID", f"agent_{os.getpid()}")
        self.auth_token = auth_token or os.environ.get("VRBOT_WS_TOKEN", "")

        self.sio = None
        self.connected = False
        self._running = False
        self._heartbeat_thread = None
        self._reconnect_delay = 1  # seconds, doubles on failure (max 60)

        # Command handlers
        self._command_handlers: Dict[str, Callable] = {}

        # Status cache (for reconnection)
        self._last_status: Dict[str, Any] = {}

    def connect(self) -> bool:
        """Connect to the Socket.IO server."""
        try:
            import socketio
        except ImportError:
            logger.warning("python-socketio not installed. Run: pip install python-socketio[client]")
            return False

        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # infinite
            reconnection_delay=2,
            reconnection_delay_max=60,
            logger=False,
        )

        # === Event Handlers ===

        @self.sio.event
        def connect():
            self.connected = True
            self._reconnect_delay = 1
            logger.info(f"Connected to {self.server_url}")
            # Register agent
            self.sio.emit("agent:register", {
                "agent_id": self.agent_id,
                "auth_token": self.auth_token,
                "timestamp": time.time(),
            })
            # Send cached status
            if self._last_status:
                self.emit_status(self._last_status)

        @self.sio.event
        def disconnect():
            self.connected = False
            logger.warning("Disconnected from server")

        @self.sio.event
        def connect_error(data):
            logger.error(f"Connection error: {data}")

        # === Command Handlers from Dashboard ===

        @self.sio.on("command")
        def on_command(data):
            cmd = data.get("command", "")
            params = data.get("params", {})
            logger.info(f"Received command: {cmd} params={params}")
            handler = self._command_handlers.get(cmd)
            if handler:
                try:
                    result = handler(params)
                    self.sio.emit("command:result", {
                        "agent_id": self.agent_id,
                        "command": cmd,
                        "success": True,
                        "result": result,
                    })
                except Exception as e:
                    logger.error(f"Command {cmd} failed: {e}")
                    self.sio.emit("command:result", {
                        "agent_id": self.agent_id,
                        "command": cmd,
                        "success": False,
                        "error": str(e),
                    })
            else:
                logger.warning(f"No handler for command: {cmd}")

        @self.sio.on("config:update")
        def on_config_update(data):
            """Dynamic config update from dashboard."""
            logger.info(f"Config update received: {list(data.keys())}")
            handler = self._command_handlers.get("config_update")
            if handler:
                handler(data)

        @self.sio.on("task:run")
        def on_task_run(data):
            """Remote task execution request."""
            task_name = data.get("task")
            logger.info(f"Remote task request: {task_name}")
            handler = self._command_handlers.get("run_task")
            if handler:
                handler({"task": task_name})

        # === Connect ===
        try:
            self.sio.connect(
                self.server_url,
                transports=["websocket", "polling"],
                wait_timeout=10,
            )
            self._running = True
            self._start_heartbeat()
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from server."""
        self._running = False
        if self.sio:
            try:
                self.sio.emit("agent:disconnect", {
                    "agent_id": self.agent_id
                })
                self.sio.disconnect()
            except Exception:
                pass
        self.connected = False
        logger.info("Socket.IO client disconnected")

    # === Emit Methods ===

    def emit_status(self, status: dict):
        """Send bot status to dashboard."""
        self._last_status = status
        if not self.connected:
            return
        try:
            self.sio.emit("agent:status", {
                "agent_id": self.agent_id,
                "timestamp": time.time(),
                **status,
            })
        except Exception as e:
            logger.debug(f"Status emit error: {e}")

    def emit_task_update(self, task_name: str, state: str, details: dict = None):
        """Send task execution update."""
        if not self.connected:
            return
        try:
            payload = {
                "agent_id": self.agent_id,
                "task": task_name,
                "state": state,
                "timestamp": time.time(),
            }
            if details:
                payload.update(details)
            self.sio.emit("agent:task_update", payload)
        except Exception as e:
            logger.debug(f"Task update emit error: {e}")

    def emit_task_result(self, task_name: str, success: bool, duration: float):
        """Send task result to dashboard."""
        if not self.connected:
            return
        try:
            self.sio.emit("agent:task_result", {
                "agent_id": self.agent_id,
                "task": task_name,
                "success": success,
                "duration": round(duration, 1),
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.debug(f"Task result emit error: {e}")

    def emit_log(self, level: str, message: str):
        """Send log message to dashboard."""
        if not self.connected:
            return
        try:
            self.sio.emit("agent:log", {
                "agent_id": self.agent_id,
                "level": level,
                "message": message,
                "timestamp": time.time(),
            })
        except Exception as e:
            pass  # don't log errors about logging

    def emit_alert(self, alert_type: str, message: str, data: dict = None):
        """Send alert (captcha, error, restart) to dashboard."""
        if not self.connected:
            return
        try:
            payload = {
                "agent_id": self.agent_id,
                "type": alert_type,
                "message": message,
                "timestamp": time.time(),
            }
            if data:
                payload.update(data)
            self.sio.emit("agent:alert", payload)
        except Exception as e:
            logger.debug(f"Alert emit error: {e}")

    # === Command Registration ===

    def on_command(self, command_name: str, handler: Callable):
        """Register a handler for a remote command."""
        self._command_handlers[command_name] = handler

    # === Heartbeat ===

    def _start_heartbeat(self):
        """Start heartbeat thread to keep connection alive."""
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="ws-heartbeat")
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Send heartbeat every 30 seconds."""
        while self._running:
            if self.connected:
                try:
                    self.sio.emit("agent:heartbeat", {
                        "agent_id": self.agent_id,
                        "timestamp": time.time(),
                        "status": self._last_status.get("state", "unknown"),
                    })
                except Exception:
                    pass
            time.sleep(30)


# ═══════════════════════════════════════════════════════════════════
# Integration Helper — wire into BotStateManager
# ═══════════════════════════════════════════════════════════════════

def integrate_socketio(bot_state_manager, server_url: str = None) -> Optional[VRBotSocketClient]:
    """Connect Socket.IO client and wire it to BotStateManager.

    Args:
        bot_state_manager: BotStateManager instance from vrbot_main
        server_url: WebSocket server URL (optional)

    Returns:
        VRBotSocketClient if connected, None otherwise
    """
    client = VRBotSocketClient(server_url=server_url)

    # Wire bot state events to Socket.IO
    def on_state_event(event: str, data: dict):
        if event == "state_change":
            client.emit_status(data)
        elif event == "task_update":
            client.emit_task_update(data.get("task", ""), data.get("task_state", ""))
        elif event == "task_result":
            client.emit_task_result(
                data.get("task", ""),
                data.get("success", False),
                data.get("duration", 0),
            )

    bot_state_manager.add_listener(on_state_event)

    if client.connect():
        logger.info("Socket.IO integrated with BotStateManager")
        return client
    else:
        logger.warning("Socket.IO connection failed — running offline")
        return None
