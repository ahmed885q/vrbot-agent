#!/usr/bin/env python3
"""
VRBOT Agent v1.0 — Viking Rise Bot (LDPlayer + ADB + OCR)
"""

import asyncio
import sys
import signal
import logging
from config import Config
from adb.controller import ADBController
from ocr.vision import Vision
from antiban.humanizer import Humanizer
from ws.client import WSClient
from scheduler.engine import Scheduler
from tasks import ALL_TASKS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("vrbot")

shutdown_event = asyncio.Event()


def handle_signal(*_):
    log.info("Shutdown signal received")
    shutdown_event.set()


async def main():
    log.info("=" * 50)
    log.info("  VRBOT Agent v1.0 — Viking Rise Automation")
    log.info("=" * 50)

    cfg = Config.load()
    log.info(f"LDPlayer ADB: {cfg.adb_host}:{cfg.adb_port}")
    log.info(f"WS Hub: {cfg.ws_url}")

    # Core modules
    adb = ADBController(cfg.adb_host, cfg.adb_port)
    vision = Vision(adb)
    humanizer = Humanizer(cfg.antiban)
    ws = WSClient(cfg.ws_url, cfg.ws_token)
    scheduler = Scheduler(humanizer)

    # Connect ADB to LDPlayer
    if not adb.connect():
        log.error("Cannot connect to LDPlayer ADB. Is it running?")
        log.error(f"Make sure LDPlayer is open and ADB is on port {cfg.adb_port}")
        sys.exit(1)
    log.info(f"ADB connected: {adb.device_name()}")

    # Register all tasks
    for task_cls in ALL_TASKS:
        task = task_cls(adb=adb, vision=vision, humanizer=humanizer, ws=ws, config=cfg)
        scheduler.register(task)
    log.info(f"{len(ALL_TASKS)} tasks registered")

    # Connect WebSocket to dashboard
    asyncio.create_task(ws.run(shutdown_event))

    # Run scheduler loop
    try:
        await scheduler.run(shutdown_event)
    except KeyboardInterrupt:
        pass
    finally:
        log.info("Shutting down...")
        adb.disconnect()
        await ws.close()
        log.info("VRBOT Agent stopped")


if __name__ == "__main__":
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_signal)
        except (OSError, ValueError):
            pass
    asyncio.run(main())
