# VRBOT Agent v2.0

Viking Rise automation bot — LDPlayer + ADB + OpenCV + Anti-Ban + Multi-Account Rotation

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    VRBOT Agent v2.0                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐  │
│  │   ADB   │  │ Vision  │  │ Anti-Ban │  │   Rotation   │  │
│  │Controller│  │ (OpenCV)│  │(Humanizer│  │  (Accounts)  │  │
│  └────┬────┘  └────┬────┘  └────┬─────┘  └──────┬───────┘  │
│       │            │            │                │           │
│  ┌────┴────────────┴────────────┴────────────────┴───────┐  │
│  │              Scheduler + Rules Engine                  │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │           Tasks (Viking Rise Actions)                  │  │
│  │  Collect · Build · Train · Gather · Mail · Quests     │  │
│  │  Alliance · Shield · Research · Hero · Tribe · Trial  │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │              WebSocket Client → Hub → Dashboard        │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
         │                                    │
    ┌────┴────┐                         ┌─────┴─────┐
    │ LDPlayer│                         │  VRBOT.me │
    │Emulator │                         │ Dashboard │
    └─────────┘                         └───────────┘
```

## Quick Start

1. Install Python 3.10+ and LDPlayer 9
2. Run `install.bat`
3. Start LDPlayer and open Viking Rise
4. Run `start.bat`

## Project Structure

```
vrbot-agent/
├── main.py              # Entry point
├── config/
│   ├── settings.py      # Configuration manager
│   ├── accounts.example.json
│   └── vrbot_config.json (auto-generated)
├── adb/
│   └── controller.py    # LDPlayer ADB control + multi-instance
├── ocr/
│   └── vision.py        # OpenCV template matching + OCR
├── antiban/
│   └── humanizer.py     # Human behavior simulation
├── rotation/
│   └── manager.py       # Multi-account rotation (GnBots-style)
├── rules/
│   └── engine.py        # Per-account task rules
├── scheduler/
│   └── __init__.py      # Priority task scheduler
├── tasks/
│   └── __init__.py      # Viking Rise tasks (13 tasks)
├── ws/
│   └── __init__.py      # WebSocket client for Dashboard
├── templates/           # Template images for matching
├── screenshots/         # Debug screenshots
├── logs/                # Log files
├── install.bat
├── start.bat
└── requirements.txt
```

## Features

- **ADB Control**: Full LDPlayer control (tap, swipe, screenshot)
- **OpenCV Vision**: Template matching + multi-scale + OCR
- **Anti-Ban**: Human-like delays, fatigue system, sleep hours, random idle
- **Rotation**: Multi-account cycling (GnBots-style)
- **Rules Engine**: Per-account task scheduling and overrides
- **WebSocket**: Real-time dashboard monitoring
- **13 Tasks**: Collect, Build, Train, Gather, Mail, Quests, Alliance, Shield, Research, Hero, Tribe, Viking Trial

## Adding Templates

Place PNG screenshots of game buttons/UI in the `templates/` folder:
- `btn_upgrade_confirm.png`
- `btn_train.png`
- `icon_resource_ready.png`
- etc.

