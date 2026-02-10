#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   VRBOT Agent v2.0 — Viking Rise Automation                ║
║   LDPlayer + ADB + OpenCV + Anti-Ban + Rotation            ║
║   Inspired by GnBots architecture with VRBOT improvements  ║
╚══════════════════════════════════════════════════════════════╝
"""
import asyncio
import sys
import signal
import logging
import time
import threading
import base64
from datetime import datetime

from config import Config
from adb.controller import ADBController
from ocr.vision import Vision
from antiban.humanizer import Humanizer
from rotation.manager import RotationManager
from rules.engine import RulesEngine
from scheduler import Scheduler
from tasks import ALL_TASKS
from ws import WSClient

# ─── Logging Setup ────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/vrbot.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("vrbot")

# ─── Global State ─────────────────────────────────────────────

shutdown_event = asyncio.Event()
bot_running = False
bot_paused = False


def handle_signal(*_):
    log.info("🛑 Shutdown signal received")
    shutdown_event.set()


class VRBotAgent:
    """Main bot agent orchestrating all systems."""

    def __init__(self):
        self.cfg = Config.load()

        # Core systems
        self.adb = ADBController(
            host=self.cfg.adb["host"],
            port=self.cfg.adb["port"],
            ldplayer_path=self.cfg.adb.get("ldplayer_path"),
            ldconsole=self.cfg.adb.get("ldconsole"),
        )
        self.vision = Vision(self.adb, self.cfg.vision)
        self.human = Humanizer(self.cfg.antiban)
        self.rules = RulesEngine()
        self.rotation = RotationManager(self.adb, self.cfg.rotation)
        self.scheduler = Scheduler(self.human, self.rules, self.cfg.scheduler)
        self.ws = WSClient(
            url=self.cfg.ws["url"],
            token=self.cfg.ws.get("token", ""),
            reconnect_delay=self.cfg.ws.get("reconnect_delay", 5),
            heartbeat_interval=self.cfg.ws.get("heartbeat_interval", 30),
        )

        self._cycle_count = 0
        self._total_tasks_done = 0
        self._start_time = None

    async def start(self):
        """Start the bot agent."""
        global bot_running
        self._start_time = datetime.now()

        self._print_banner()
        log.info("Initializing VRBOT Agent v2.0...")

        # Connect ADB
        if not self.adb.connect():
            log.error("❌ Cannot connect to LDPlayer. Is it running?")
            log.info("💡 Start LDPlayer first, then run this agent again.")
            return

        # Load templates
        template_count = self.vision.load_all_templates()
        log.info(f"📷 Loaded {template_count} templates")

        # Register WS event handlers
        self._register_ws_handlers()

        # Start WS connection in background
        ws_task = None
        if self.cfg.ws.get("token"):
            ws_task = asyncio.create_task(self.ws.connect())
            log.info("📡 WebSocket connecting to Hub...")
        else:
            log.info("📡 WebSocket disabled (no token configured)")

        bot_running = True

        # Main bot loop
        try:
            await self._main_loop()
        except KeyboardInterrupt:
            log.info("Keyboard interrupt")
        finally:
            bot_running = False
            if ws_task:
                await self.ws.disconnect()
            self.adb.disconnect()
            self._print_stats()

    async def _main_loop(self):
        """Main bot loop — runs rotation cycles."""
        global bot_paused

        while not shutdown_event.is_set():
            # Check sleep time
            if self.human.should_sleep():
                log.info("💤 Sleep hours active. Waiting...")
                self.ws.send_sync("agent:status", {"state": "sleeping"})
                await asyncio.sleep(300)  # Check every 5 min
                continue

            # Check pause
            if bot_paused:
                log.info("⏸ Bot paused. Waiting for resume...")
                await asyncio.sleep(5)
                continue

            # Check session
            if self.human.session_expired():
                log.info("⏰ Session limit reached. Resting before new session...")
                self.human.take_rest()
                self.human.reset_session()
                continue

            # === Rotation Mode ===
            if self.cfg.rotation.get("enabled") and len(self.rotation.accounts) > 0:
                await self._run_rotation_cycle()
            else:
                # Single account mode
                await self._run_single_cycle()

            self._cycle_count += 1

            # Cooldown between cycles
            cooldown = self.cfg.rotation.get("cooldown_between_rotations", 60)
            log.info(f"⏳ Cycle {self._cycle_count} done. Next in {cooldown}s...")
            self.ws.send_sync("agent:status", {
                "state": "cooldown",
                "cycle": self._cycle_count,
                "next_in": cooldown,
            })
            await asyncio.sleep(cooldown)

    async def _run_single_cycle(self):
        """Run one cycle on current account."""
        log.info(f"🔄 Starting cycle {self._cycle_count + 1}")

        # Ensure game is running
        if not self.adb.is_app_running():
            log.info("Launching Viking Rise...")
            self.adb.launch_app()
            await asyncio.sleep(10)
            self.vision.wait_loading(timeout=60)

        # Build and run task queue
        queue = self.scheduler.build_task_queue(ALL_TASKS, self.vision, self.adb)
        completed, failed = self.scheduler.run_cycle(queue)

        self._total_tasks_done += completed
        log.info(f"Cycle result: {completed} ✅ / {failed} ❌")

        # Send status
        self.ws.send_sync("agent:cycle_complete", {
            "cycle": self._cycle_count + 1,
            "completed": completed,
            "failed": failed,
            "total": self._total_tasks_done,
        })

    async def _run_rotation_cycle(self):
        """Run one rotation through all accounts."""
        accounts = self.rotation.get_next_accounts()

        if not accounts:
            log.info("No accounts eligible for this rotation")
            return

        for account in accounts:
            log.info(f"═══ Account: {account.name} ═══")

            # Switch to account instance
            if not self.rotation.switch_to_account(account):
                self.rotation.mark_failed(account, "Instance switch failed")
                continue

            # Wait for emulator and game
            await asyncio.sleep(5)
            if not self.adb.is_app_running():
                self.adb.launch_app()
                await asyncio.sleep(10)
                self.vision.wait_loading(timeout=60)

            # Build task queue with account-specific rules
            queue = self.scheduler.build_task_queue(
                ALL_TASKS, self.vision, self.adb, account_id=account.id
            )
            completed, failed = self.scheduler.run_cycle(queue, account_id=account.id)

            self._total_tasks_done += completed
            self.rotation.mark_completed(account, tasks_done=completed)

            # Reset retries for next account
            self.scheduler.reset_retries()

            # Delay between accounts
            delay = self.cfg.rotation.get("rotation_delay", 10)
            log.info(f"Next account in {delay}s...")
            await asyncio.sleep(delay)

        log.info(f"Rotation complete. {len(accounts)} accounts processed.")

    # ─── WebSocket Handlers ───────────────────────────────────

    def _register_ws_handlers(self):
        """Register handlers for dashboard commands."""

        def on_pause(data):
            global bot_paused
            bot_paused = True
            log.info("⏸ Paused by dashboard")

        def on_resume(data):
            global bot_paused
            bot_paused = False
            log.info("▶ Resumed by dashboard")

        def on_stop(data):
            shutdown_event.set()
            log.info("🛑 Stopped by dashboard")

        def on_screenshot_request(data):
            png = self.adb.screenshot()
            if png:
                b64 = base64.b64encode(png).decode()
                self.ws.send_sync("agent:screenshot", {"image": b64})

        def on_status_request(data):
            self.ws.send_sync("agent:status", self._get_full_status())

        self.ws.on("dashboard:pause", on_pause)
        self.ws.on("dashboard:resume", on_resume)
        self.ws.on("dashboard:stop", on_stop)
        self.ws.on("dashboard:screenshot", on_screenshot_request)
        self.ws.on("dashboard:status", on_status_request)

    def _get_full_status(self):
        """Get comprehensive agent status."""
        return {
            "state": "paused" if bot_paused else "running",
            "uptime_minutes": round((datetime.now() - self._start_time).total_seconds() / 60, 1) if self._start_time else 0,
            "cycle_count": self._cycle_count,
            "total_tasks_done": self._total_tasks_done,
            "humanizer": self.human.stats,
            "rotation": self.rotation.stats,
            "scheduler": self.scheduler.stats,
            "adb_connected": self.adb.connected,
            "ws_connected": self.ws.connected,
        }

    # ─── Display ──────────────────────────────────────────────

    def _print_banner(self):
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ██╗   ██╗██████╗ ██████╗  ██████╗ ████████╗               ║
║   ██║   ██║██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝               ║
║   ██║   ██║██████╔╝██████╔╝██║   ██║   ██║                  ║
║   ╚██╗ ██╔╝██╔══██╗██╔══██╗██║   ██║   ██║                  ║
║    ╚████╔╝ ██║  ██║██████╔╝╚██████╔╝   ██║                  ║
║     ╚═══╝  ╚═╝  ╚═╝╚═════╝  ╚═════╝    ╚═╝                  ║
║                                                              ║
║   Viking Rise Bot Agent v2.0                                 ║
║   ADB + OpenCV + Anti-Ban + Rotation                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        print(banner)

    def _print_stats(self):
        log.info("═" * 50)
        log.info("📊 Session Summary")
        log.info(f"   Cycles: {self._cycle_count}")
        log.info(f"   Tasks completed: {self._total_tasks_done}")
        if self._start_time:
            elapsed = (datetime.now() - self._start_time).total_seconds() / 3600
            log.info(f"   Runtime: {elapsed:.1f} hours")
        log.info(f"   Humanizer: {self.human.stats}")
        log.info("═" * 50)


# ─── Entry Point ──────────────────────────────────────────────

def main():
    import os
    os.makedirs("logs", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    os.makedirs("config", exist_ok=True)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    agent = VRBotAgent()
    asyncio.run(agent.start())


if __name__ == "__main__":
    main()

