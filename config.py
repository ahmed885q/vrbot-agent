"""
VRBOT Agent Configuration
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

CONFIG_FILE = "vrbot_config.json"


@dataclass
class AntiBanConfig:
    # Tap delay range (ms)
    tap_delay_min: int = 800
    tap_delay_max: int = 3500
    # Tap position offset (pixels)
    tap_offset_min: int = 3
    tap_offset_max: int = 12
    # Rest break every N minutes
    rest_every_min: int = 35
    rest_every_max: int = 65
    # Rest duration (minutes)
    rest_duration_min: int = 3
    rest_duration_max: int = 8
    # Session max hours (then long break)
    session_max_hours: float = 4.0
    session_break_min: int = 20
    session_break_max: int = 45
    # Swipe humanization
    swipe_steps_min: int = 8
    swipe_steps_max: int = 20
    swipe_duration_min: int = 200
    swipe_duration_max: int = 600
    # Enabled
    enabled: bool = True


@dataclass
class Config:
    # ADB
    adb_host: str = "127.0.0.1"
    adb_port: int = 5555  # LDPlayer default
    adb_path: str = ""  # auto-detect

    # WebSocket
    ws_url: str = "wss://ws.vrbot.me/ws"
    ws_token: str = ""

    # OCR
    ocr_lang: str = "eng"
    screenshot_method: str = "screencap"  # screencap or minicap

    # Game resolution (LDPlayer)
    screen_width: int = 1280
    screen_height: int = 720

    # Anti-ban
    antiban: AntiBanConfig = field(default_factory=AntiBanConfig)

    # Tasks enable/disable
    enabled_tasks: list = field(default_factory=lambda: ["all"])
    disabled_tasks: list = field(default_factory=list)

    # License
    license_key: str = ""
    device_id: str = ""

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()

        # Load from file
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                if k == "antiban" and isinstance(v, dict):
                    cfg.antiban = AntiBanConfig(**v)
                elif hasattr(cfg, k):
                    setattr(cfg, k, v)

        # Environment overrides
        cfg.adb_host = os.getenv("VRBOT_ADB_HOST", cfg.adb_host)
        cfg.adb_port = int(os.getenv("VRBOT_ADB_PORT", str(cfg.adb_port)))
        cfg.ws_url = os.getenv("VRBOT_WS_URL", cfg.ws_url)
        cfg.ws_token = os.getenv("VRBOT_WS_TOKEN", cfg.ws_token)
        cfg.license_key = os.getenv("VRBOT_LICENSE_KEY", cfg.license_key)

        # Auto-detect LDPlayer ADB path
        if not cfg.adb_path:
            ldplayer_paths = [
                r"C:\LDPlayer\LDPlayer9\adb.exe",
                r"C:\LDPlayer\LDPlayer4.0\adb.exe",
                r"C:\Program Files\LDPlayer\LDPlayer9\adb.exe",
                os.path.expanduser(r"~\LDPlayer\LDPlayer9\adb.exe"),
            ]
            for p in ldplayer_paths:
                if os.path.exists(p):
                    cfg.adb_path = p
                    break
            if not cfg.adb_path:
                cfg.adb_path = "adb"  # system PATH

        return cfg

    def save(self):
        data = {
            "adb_host": self.adb_host,
            "adb_port": self.adb_port,
            "ws_url": self.ws_url,
            "ws_token": self.ws_token,
            "license_key": self.license_key,
            "device_id": self.device_id,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "enabled_tasks": self.enabled_tasks,
            "disabled_tasks": self.disabled_tasks,
            "antiban": {
                "tap_delay_min": self.antiban.tap_delay_min,
                "tap_delay_max": self.antiban.tap_delay_max,
                "tap_offset_min": self.antiban.tap_offset_min,
                "tap_offset_max": self.antiban.tap_offset_max,
                "rest_every_min": self.antiban.rest_every_min,
                "rest_every_max": self.antiban.rest_every_max,
                "rest_duration_min": self.antiban.rest_duration_min,
                "rest_duration_max": self.antiban.rest_duration_max,
                "enabled": self.antiban.enabled,
            },
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
