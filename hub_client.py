"""
VRBOT Hub Client
================
Connects the Python VRBOT Agent to the WebSocket Hub.
Receives task commands from the dashboard and reports status back.

Usage:
    from hub_client import HubClient

    hub = HubClient(user_id="your-supabase-user-id")
    hub.on_run_tasks = my_run_tasks_handler
    hub.on_stop_tasks = my_stop_handler
    hub.connect()
"""

import json
import time
import threading
import socket
import logging

logger = logging.getLogger("HubClient")

try:
    import websocket  # pip install websocket-client
except ImportError:
    print("ERROR: pip install websocket-client")
    raise

WS_URL = "wss://ws.vrbot.me/ws"


class HubClient:
    def __init__(self, user_id: str, device_id: str = None, token: str = None):
        self.user_id = user_id
        self.device_id = device_id or socket.gethostname()
        self.token = token  # Optional agent auth token (vrbot_xxx)
        self.ws = None
        self.connected = False
        self.running = False
        self._thread = None
        self._reconnect_delay = 3

        # Callbacks - set these from your agent
        self.on_run_tasks = None  # def handler(farm_id, tasks, from_client): ...
        self.on_stop_tasks = None  # def handler(): ...
        self.on_pause = None      # def handler(): ...
        self.on_resume = None     # def handler(): ...
        self.on_get_status = None # def handler() -> dict: ...
        self.on_connected = None  # def handler(): ...
        self.on_disconnected = None  # def handler(): ...

    def connect(self):
        """Start connection in background thread"""
        self.running = True
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()
        logger.info(f"Hub client starting... connecting to {WS_URL}")

    def disconnect(self):
        """Stop connection"""
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        self.connected = False

    def _run_forever(self):
        """Reconnection loop"""
        while self.running:
            try:
                self._connect_once()
            except Exception as e:
                logger.error(f"Connection error: {e}")

            if self.running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                time.sleep(self._reconnect_delay)

    def _connect_once(self):
        """Single connection attempt"""
        self.ws = websocket.WebSocketApp(
            WS_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error,
        )
        self.ws.run_forever(ping_interval=30, ping_timeout=10)

    def _on_open(self, ws):
        """Send auth on connect"""
        auth_msg = {
            "type": "auth",
            "role": "agent",
            "userId": self.user_id,
            "deviceId": self.device_id,
        }
        if self.token:
            auth_msg["token"] = self.token
        ws.send(json.dumps(auth_msg))
        logger.info("Connected to Hub, sending auth...")

    def _on_message(self, ws, raw):
        """Handle messages from Hub"""
        try:
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "welcome":
                logger.info(f"Hub: {msg.get('message', '')}")

            elif msg_type == "auth_ok":
                self.connected = True
                logger.info(f"Authenticated as agent (id: {msg.get('clientId', '')})")
                if self.on_connected:
                    self.on_connected()

            elif msg_type == "run_tasks":
                payload = msg.get("payload", {})
                farm_id = payload.get("farmId", "")
                tasks = payload.get("tasks", [])
                from_client = msg.get("from", "")

                logger.info(f"Received tasks: {tasks} for farm: {farm_id}")

                # Report that we received the command
                self.send_status("tasks_received", {
                    "farmId": farm_id,
                    "tasks": tasks,
                })

                # Execute callback
                if self.on_run_tasks:
                    try:
                        self.on_run_tasks(farm_id, tasks, from_client)
                    except Exception as e:
                        logger.error(f"Task execution error: {e}")
                        self.send_error(str(e), farm_id)

            elif msg_type == "stop_tasks":
                logger.info("Received STOP command")
                if self.on_stop_tasks:
                    self.on_stop_tasks()

            elif msg_type == "pause":
                logger.info("Received PAUSE command")
                if self.on_pause:
                    self.on_pause()

            elif msg_type == "resume":
                logger.info("Received RESUME command")
                if self.on_resume:
                    self.on_resume()

            elif msg_type == "get_status":
                logger.info("Received GET_STATUS request")
                if self.on_get_status:
                    status = self.on_get_status()
                    self.send_agent_status(status or {})

            elif msg_type == "pong":
                pass  # Heartbeat response

            elif msg_type == "error":
                logger.warning(f"Hub error: {msg.get('message', '')}")

            else:
                logger.debug(f"Unknown message: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {raw[:100]}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        logger.info(f"Disconnected from Hub (code: {close_status_code})")
        if self.on_disconnected:
            self.on_disconnected()

    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")

    # ===== SEND METHODS =====

    def send(self, data: dict):
        """Send raw message to Hub"""
        if self.ws and self.connected:
            try:
                self.ws.send(json.dumps(data))
            except Exception as e:
                logger.error(f"Send error: {e}")

    def send_status(self, status: str, data: dict = None):
        """Report task status to dashboard"""
        self.send({
            "type": "task_status",
            "payload": {
                "status": status,
                **(data or {}),
            },
        })

    def send_task_complete(self, task_name: str, result: dict = None):
        """Report task completion"""
        self.send({
            "type": "task_complete",
            "payload": {
                "task": task_name,
                "result": result or {},
            },
        })

    def send_error(self, error_msg: str, farm_id: str = None):
        """Report error"""
        self.send({
            "type": "task_error",
            "payload": {
                "error": error_msg,
                "farmId": farm_id,
            },
        })

    def send_log(self, message: str, level: str = "info"):
        """Send log message to dashboard"""
        self.send({
            "type": "log",
            "payload": {
                "message": message,
                "level": level,
            },
        })

    def send_agent_status(self, status: dict):
        """Send agent status (CPU, memory, running tasks, etc.)"""
        self.send({
            "type": "agent_status",
            "payload": status,
        })

    def send_alert(self, alert_type: str, message: str, data: dict = None):
        """Send alert (captcha, error_recovery, task_final_failure) to dashboard"""
        self.send({
            "type": "agent_alert",
            "payload": {
                "alert_type": alert_type,
                "message": message,
                **(data or {}),
            },
        })

    def send_heartbeat(self, status: dict = None):
        """Send heartbeat with optional status snapshot"""
        self.send({
            "type": "agent_heartbeat",
            "payload": status or {},
        })


# ═══════════════════════════════════════════════════════════════════
# Integration Helper — wire BotStateManager → Hub WebSocket
# ═══════════════════════════════════════════════════════════════════

def integrate_hub(bot_state_manager, user_id: str = None):
    """Connect HubClient and wire it to BotStateManager.

    Replaces the old socketio_client integration. Routes all state
    changes, task results, and alerts through ws_hub.py relay.

    Args:
        bot_state_manager: BotStateManager instance from vrbot_main
        user_id: Supabase user ID for Hub authentication

    Returns:
        HubClient if connected, None otherwise
    """
    import os
    uid = user_id or os.environ.get("VRBOT_USER_ID", "agent-default")
    agent_token = os.environ.get("VRBOT_AGENT_TOKEN", "")

    hub = HubClient(user_id=uid, token=agent_token or None)

    # Wire BotStateManager events → Hub messages
    def on_state_event(event: str, data: dict):
        if event == "state_change":
            hub.send_agent_status(data)
        elif event == "task_update":
            hub.send_status(data.get("task_state", "running"), {
                "task": data.get("task", ""),
                "currentTask": data.get("task", ""),
            })
        elif event == "task_result":
            task = data.get("task", "")
            if data.get("success"):
                hub.send_task_complete(task, {
                    "success": True,
                    "duration": data.get("duration", 0),
                })
            else:
                hub.send_error(f"{task} failed", None)
        elif event == "alert":
            hub.send_alert(
                data.get("type", "unknown"),
                data.get("message", ""),
                data,
            )

    bot_state_manager.add_listener(on_state_event)

    # Start heartbeat that sends full status every 30s
    def heartbeat_loop():
        import time as _time
        while hub.running:
            if hub.connected:
                hub.send_heartbeat(bot_state_manager.get_status())
            _time.sleep(30)

    hub.connect()
    # Give it a moment to auth
    import time as _time
    _time.sleep(2)

    if hub.connected:
        ht = threading.Thread(target=heartbeat_loop, daemon=True, name="hub-heartbeat")
        ht.start()
        logger.info("Hub WebSocket integrated with BotStateManager")
        return hub
    else:
        logger.warning("Hub connection pending — will retry in background")
        # Still return hub; it auto-reconnects
        ht = threading.Thread(target=heartbeat_loop, daemon=True, name="hub-heartbeat")
        ht.start()
        return hub


# ===== EXAMPLE USAGE =====
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    # Replace with your actual Supabase user ID
    USER_ID = "YOUR_SUPABASE_USER_ID"

    def handle_run_tasks(farm_id, tasks, from_client):
        """Called when dashboard sends tasks to run"""
        print(f"\n{'='*50}")
        print(f"RUN TASKS:")
        print(f"  Farm: {farm_id}")
        print(f"  Tasks: {tasks}")
        print(f"{'='*50}\n")

        # Here you would call your VRBOT task functions
        # Example:
        # for task in tasks:
        #     if task == "Gather Resources":
        #         gather_resources()
        #     elif task == "Kill Monster":
        #         kill_monster()
        #     ...

        # Report progress
        hub.send_status("running", {"farmId": farm_id, "currentTask": tasks[0] if tasks else ""})

        # Simulate work
        import time
        for i, task in enumerate(tasks):
            print(f"  Executing: {task}...")
            hub.send_log(f"Running: {task}")
            time.sleep(2)  # Replace with actual task execution
            hub.send_task_complete(task, {"success": True})
            print(f"  Completed: {task}")

        hub.send_status("idle", {"farmId": farm_id})

    def handle_stop():
        """Called when dashboard sends stop command"""
        print("\n⏹ STOP COMMAND RECEIVED\n")
        # Here you would stop your running tasks
        hub.send_status("stopped")

    # Create and connect
    hub = HubClient(user_id=USER_ID)
    hub.on_run_tasks = handle_run_tasks
    hub.on_stop_tasks = handle_stop
    hub.connect()

    print("VRBOT Agent running... Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        hub.disconnect()
