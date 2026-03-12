"""
VRBOT Agent — Configuration
"""
import json
import os

DEFAULT_CONFIG = {
    # LDPlayer ADB
    "adb": {
        "host": "127.0.0.1",
        "port": 5555,
        "ldplayer_path": r"C:\LDPlayer\LDPlayer9",
        "ldconsole": r"C:\LDPlayer\LDPlayer9\ldconsole.exe",
        "screen_width": 1280,
        "screen_height": 720,
    },
    # WebSocket Hub
    "ws": {
        "url": "wss://ws.vrbot.me",
        "token": "",
        "reconnect_delay": 5,
        "heartbeat_interval": 30,
    },
    # Anti-Ban Settings
    "antiban": {
        "min_click_delay": 800,
        "max_click_delay": 3500,
        "pixel_offset": 12,
        "rest_interval_min": 30,
        "rest_interval_max": 60,
        "rest_duration_min": 5,
        "rest_duration_max": 15,
        "session_max_hours": 8,
        "sleep_hours_start": 23,
        "sleep_hours_end": 7,
        "swipe_speed_variation": 0.3,
        "action_order_shuffle": True,
        "human_scroll_enabled": True,
    },
    # Rotation Settings
    "rotation": {
        "enabled": False,
        "accounts_at_once": 1,
        "rotation_delay": 10,
        "max_accounts": 50,
        "skip_failed_accounts": True,
        "cooldown_between_rotations": 60,
    },
    # Vision / OCR
    "vision": {
        "template_threshold": 0.80,
        "ocr_lang": "eng",
        "screenshot_method": "adb",
        "match_method": "TM_CCOEFF_NORMED",
        "multi_scale": True,
        "scales": [0.8, 0.9, 1.0, 1.1, 1.2],
    },
    # Scheduler
    "scheduler": {
        "task_queue_size": 100,
        "priority_enabled": True,
        "retry_failed_tasks": True,
        "max_retries": 3,
    },
    # Logging
    "logging": {
        "level": "INFO",
        "file_enabled": True,
        "max_file_size_mb": 10,
        "console_colors": True,
    },
}


class Config:
    """Configuration manager with file persistence."""

    _instance = None
    CONFIG_FILE = "config/vrbot_config.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
        return cls._instance

    @classmethod
    def load(cls):
        cfg = cls()
        if os.path.exists(cls.CONFIG_FILE):
            with open(cls.CONFIG_FILE, "r") as f:
                saved = json.load(f)
            cfg._data = cls._deep_merge(DEFAULT_CONFIG, saved)
        else:
            cfg._data = DEFAULT_CONFIG.copy()
            cfg.save()
        return cfg

    @classmethod
    def _deep_merge(cls, base, override):
        result = base.copy()
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = cls._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def save(self):
        os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, section, key=None):
        if key is None:
            return self._data.get(section, {})
        return self._data.get(section, {}).get(key)

    def set(self, section, key, value):
        if section not in self._data:
            self._data[section] = {}
        self._data[section][key] = value
        self.save()

    @property
    def adb(self):
        return self._data["adb"]

    @property
    def ws(self):
        return self._data["ws"]

    @property
    def antiban(self):
        return self._data["antiban"]

    @property
    def rotation(self):
        return self._data["rotation"]

    @property
    def vision(self):
        return self._data["vision"]

    @property
    def scheduler(self):
        return self._data["scheduler"]

