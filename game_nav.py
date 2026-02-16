"""
VRBOT Agent — Game Navigation System
Handles screen detection, navigation between game screens,
and common UI interactions using real template matching.
"""
import time
import logging

log = logging.getLogger("vrbot.nav")


# ═══════════════════════════════════════════════════════════════
# Screen Definitions — templates that identify each screen
# ═══════════════════════════════════════════════════════════════

SCREENS = {
    "city": {
        "markers": ["btn_compass", "btn_mail", "btn_shield", "btn_quests"],
        "toolbar": True,
        "description": "Main city view"
    },
    "world_map": {
        "markers": ["btn_worldmap_search", "btn_worldmap_tools"],
        "toolbar": False,
        "description": "World/kingdom map"
    },
    "mail": {
        "markers": ["screen_mail_title", "btn_read_claim_all"],
        "toolbar": False,
        "description": "Mail screen"
    },
    "tribe": {
        "markers": ["screen_tribe", "btn_tribe_assist"],
        "toolbar": False,
        "description": "Tribe/Alliance screen"
    },
    "hero": {
        "markers": ["screen_hero", "btn_hero_grade"],
        "toolbar": False,
        "description": "Hero management"
    },
    "technology": {
        "markers": ["screen_research_title", "btn_research_queue_idle"],
        "toolbar": False,
        "description": "Research/technology tree"
    },
    "daily_quests": {
        "markers": ["screen_daily_quests", "tab_daily_quests"],
        "toolbar": False,
        "description": "Daily quests list"
    },
    "staging_post": {
        "markers": ["screen_staging_post", "btn_complete_all"],
        "toolbar": False,
        "description": "Staging Post quests"
    },
    "search_panel": {
        "markers": ["tile_farm_search", "tile_monster_search", "tile_sawmill_search"],
        "toolbar": False,
        "description": "World map search (resource tiles)"
    },
    "research": {
        "markers": ["screen_research_title", "btn_research_queue1"],
        "toolbar": False,
        "description": "Research/Academy screen"
    },
    "upgrade_screen": {
        "markers": ["screen_upgrade_power"],
        "toolbar": False,
        "description": "Building upgrade screen"
    },
    "city_event_report": {
        "markers": ["screen_city_event_report"],
        "toolbar": False,
        "description": "City event notifications"
    },
    "arena_select": {
        "markers": ["icon_arena", "icon_mystic_realm"],
        "toolbar": False,
        "description": "Arena / Mystic Realm / Drill Ground"
    },
}

# ═══════════════════════════════════════════════════════════════
# Toolbar Button Positions (bottom bar on city/world screens)
# Mapped from template matching results
# ═══════════════════════════════════════════════════════════════

TOOLBAR = {
    "mail":     "btn_mail",
    "quests":   "btn_quests",
    "alliance": "btn_alliance",
    "heroes":   "btn_heroes",
    "more":     "btn_more",
    "items":    "btn_items",
    "shield":   "btn_shield",
}

# Fixed toolbar button positions (fallback when template matching is unreliable)
# Based on 1280x720 resolution testing
TOOLBAR_POS = {
    "mail":     (870, 660),
    "quests":   (935, 660),
    "alliance": (1020, 660),
    "heroes":   (1085, 660),
    "more":     (1145, 660),
    "items":    (1200, 660),
    "shield":   (1245, 660),
}

# ═══════════════════════════════════════════════════════════════
# Resource Tile Templates
# ═══════════════════════════════════════════════════════════════

RESOURCE_TILES = {
    "food":     "tile_farm_search",
    "wood":     "tile_sawmill_search",
    "stone":    "tile_quarry_search",
    "gold":     "tile_goldmine_search",
    "monster":  "tile_monster_search",
    "niflung":  "tile_niflung_search",
}


class GameNavigator:
    """Handles all navigation between game screens."""

    def __init__(self, vision, adb, humanizer):
        self.vision = vision
        self.adb = adb
        self.human = humanizer
        self._current_screen = None

    # ─── Screen Detection ──────────────────────────────────

    def detect_screen(self):
        """Detect which game screen we're currently on."""
        self.vision.capture(fresh=True)

        # Check specific screens first (most unique markers)
        # World map has unique buttons not found in city
        if (self.vision.exists("btn_worldmap_search", threshold=0.78) or
            self.vision.exists("btn_worldmap_tools", threshold=0.78)):
            self._current_screen = "world_map"
            log.debug("Screen detected: world_map")
            return "world_map"

        # City has compass button (not on world map)
        if (self.vision.exists("btn_compass", threshold=0.78) or
            self.vision.exists("btn_city_compass", threshold=0.78)):
            self._current_screen = "city"
            log.debug("Screen detected: city (compass found)")
            return "city"

        # Check other screens by markers
        for screen_name, info in SCREENS.items():
            if screen_name in ("city", "world_map"):
                continue  # Already checked
            markers = info["markers"]
            for marker in markers:
                if self.vision.exists(marker, threshold=0.78):
                    self._current_screen = screen_name
                    log.debug(f"Screen detected: {screen_name}")
                    return screen_name

        # Fallback: if toolbar buttons visible but no compass/worldmap,
        # check if it's city by toolbar presence
        if (self.vision.exists("btn_mail", threshold=0.85) and
            self.vision.exists("btn_shield", threshold=0.85)):
            self._current_screen = "city"
            log.debug("Screen detected: city (toolbar fallback)")
            return "city"

        self._current_screen = "unknown"
        return "unknown"

    def is_on_screen(self, screen_name):
        """Check if we're on a specific screen."""
        return self.detect_screen() == screen_name

    def wait_for_screen(self, screen_name, timeout=15):
        """Wait until we're on the expected screen."""
        start = time.time()
        while time.time() - start < timeout:
            if self.detect_screen() == screen_name:
                return True
            time.sleep(1)
        log.warning(f"Timeout waiting for screen: {screen_name}")
        return False

    # ─── Navigation Actions ────────────────────────────────

    def go_to_city(self, timeout=10):
        """Navigate to main city view."""
        if self.is_on_screen("city"):
            return True

        # Handle exit dialog or Chief Profile if visible
        self._dismiss_exit_dialog()
        self._close_chief_profile()

        # If on world map, tap the city return button (bottom-left badge)
        if self.is_on_screen("world_map"):
            # Method 1: Tap the city return badge (bottom-left)
            if self.vision.tap_on("btn_return_city", wait=False, threshold=0.70):
                log.info("Tapped city return button")
                self.human.delay("normal")
                if self.wait_for_screen("city", timeout=8):
                    return True

            # Method 2: Tap known position of return button
            self.adb.tap(65, 655, offset=10)
            self.human.delay("normal")
            self._dismiss_exit_dialog()
            self._close_chief_profile()
            if self.wait_for_screen("city", timeout=5):
                return True

        # For other screens, try close buttons
        for _ in range(5):
            current = self.detect_screen()
            if current == "city":
                return True

            self._dismiss_exit_dialog()
            self._close_chief_profile()

            # Close any popup/screen
            if self.vision.tap_on("btn_close_x", wait=False):
                self.human.delay("fast")
                continue
            if self.vision.tap_on("btn_popup_close_x", wait=False):
                self.human.delay("fast")
                continue
            if self.vision.tap_on("btn_close_x_panel", wait=False):
                self.human.delay("fast")
                continue
            if self.vision.tap_on("btn_back", wait=False):
                self.human.delay("fast")
                continue

            # Android back (careful - might trigger exit dialog)
            self.adb.go_back()
            self.human.delay("fast")
            self._dismiss_exit_dialog()

        return self.is_on_screen("city")

    def _dismiss_exit_dialog(self):
        """If 'exit game' dialog appears, tap Cancel."""
        time.sleep(0.3)
        self.vision.capture(fresh=True)
        if self.vision.exists("dialog_note_title", threshold=0.75):
            log.info("Exit dialog detected — tapping Cancel")
            if self.vision.tap_on("btn_cancel_blue", wait=False, threshold=0.70):
                self.human.delay("fast")
                return True
            self.adb.tap(490, 485, offset=10)
            self.human.delay("fast")
            return True
        return False

    def _close_chief_profile(self):
        """If Chief Profile screen is open, close it."""
        time.sleep(0.3)
        self.vision.capture(fresh=True)
        # Chief Profile has "Personal Info", "Settings" etc on left side
        # Best way: press Android back to close it
        if self.vision.exists("icon_profile_avatar", threshold=0.85,
                               region=(200, 100, 500, 500)):
            log.info("Chief Profile detected — closing")
            self.adb.go_back()
            self.human.delay("fast")
            self._dismiss_exit_dialog()
            return True
        return False

        # Try pressing back repeatedly
        for _ in range(5):
            current = self.detect_screen()
            if current == "city":
                return True

            # Close any popup/screen
            if self.vision.tap_on("btn_close_x", wait=False):
                self.human.delay("fast")
                continue
            if self.vision.tap_on("btn_popup_close_x", wait=False):
                self.human.delay("fast")
                continue
            if self.vision.tap_on("btn_back", wait=False):
                self.human.delay("fast")
                continue

            # Press Android back key
            self.adb.go_back()
            self.human.delay("fast")

        return self.is_on_screen("city")

    def go_to_world_map(self, timeout=10):
        """Navigate to world map."""
        if self.is_on_screen("world_map"):
            return True

        # From city, tap compass button (bottom-left)
        if self.is_on_screen("city"):
            if (self.vision.tap_on("btn_city_compass", wait=False, threshold=0.70) or
                self.vision.tap_on("btn_compass", wait=False, threshold=0.70)):
                self.human.delay("normal")
                if self.wait_for_screen("world_map", timeout=timeout):
                    return True

        # Try going to city first, then world map
        self.go_to_city()
        if (self.vision.tap_on("btn_city_compass", wait=False, threshold=0.70) or
            self.vision.tap_on("btn_compass", wait=False, threshold=0.70)):
            self.human.delay("normal")
            return self.wait_for_screen("world_map", timeout=timeout)

        return False

    def open_mail(self):
        """Open mail screen."""
        if self.is_on_screen("mail"):
            return True
        self.go_to_city()
        time.sleep(0.5)
        # btn_mail is in bottom toolbar, roughly at x=870-910, y=640-680
        # Use region constraint to avoid matching heroes button
        self.vision.capture(fresh=True)
        result = self.vision.find("btn_mail", threshold=0.80,
                                   region=(830, 620, 120, 80))
        if result:
            log.info(f"Mail button found at ({result[0]},{result[1]}) conf={result[2]:.1%}")
            self.adb.tap(result[0], result[1], offset=5)
            self.human.delay("normal")
            if self.wait_for_screen("mail", timeout=10):
                return True
        # Fallback: tap known mail button position
        log.info("Fallback: tapping mail at (870, 660)")
        self.adb.tap(870, 660, offset=5)
        self.human.delay("normal")
        return self.wait_for_screen("mail", timeout=10)

    def open_heroes(self):
        """Open hero management."""
        if self.is_on_screen("hero"):
            return True
        self.go_to_city()
        time.sleep(0.5)
        # btn_heroes is at roughly x=1060-1110, y=640-680
        self.vision.capture(fresh=True)
        result = self.vision.find("btn_heroes", threshold=0.75,
                                   region=(1040, 620, 100, 80))
        if result:
            log.info(f"Heroes button at ({result[0]},{result[1]})")
            self.adb.tap(result[0], result[1], offset=5)
        else:
            log.info("Fallback: tapping heroes at (1085, 660)")
            self.adb.tap(1085, 660, offset=5)
        self.human.delay("normal")
        return self.wait_for_screen("hero", timeout=10)

    def open_tribe(self):
        """Open tribe/alliance screen."""
        if self.is_on_screen("tribe"):
            return True
        self.go_to_city()
        time.sleep(0.5)
        # btn_alliance is at roughly x=1000-1040, y=640-680
        self.vision.capture(fresh=True)
        result = self.vision.find("btn_alliance", threshold=0.70,
                                   region=(980, 620, 100, 80))
        if result:
            log.info(f"Alliance button at ({result[0]},{result[1]})")
            self.adb.tap(result[0], result[1], offset=5)
        else:
            log.info("Fallback: tapping alliance at (1020, 660)")
            self.adb.tap(1020, 660, offset=5)
        self.human.delay("normal")
        return self.wait_for_screen("tribe", timeout=10)

    def open_daily_quests(self):
        """Open daily quests."""
        if self.is_on_screen("daily_quests"):
            return True
        self.go_to_city()
        time.sleep(0.5)
        # btn_quests is at roughly x=910-960, y=640-680
        self.vision.capture(fresh=True)
        result = self.vision.find("btn_quests", threshold=0.80,
                                   region=(890, 620, 100, 80))
        if result:
            log.info(f"Quests button at ({result[0]},{result[1]})")
            self.adb.tap(result[0], result[1], offset=5)
        else:
            log.info("Fallback: tapping quests at (935, 660)")
            self.adb.tap(935, 660, offset=5)
        self.human.delay("normal")
        return self.wait_for_screen("daily_quests", timeout=10)

    def open_items(self):
        """Open items/inventory."""
        self.go_to_city()
        return self.vision.tap_on("btn_items", wait=False, timeout=5)

    def open_search_panel(self):
        """Open world map search panel (resource finder)."""
        if self.is_on_screen("search_panel"):
            return True
        if not self.is_on_screen("world_map"):
            self.go_to_world_map()
        if self.vision.tap_on("btn_worldmap_search", wait=False, timeout=5):
            self.human.delay("normal")
            return self.wait_for_screen("search_panel", timeout=10)
        return False

    # ─── Common UI Actions ─────────────────────────────────

    def close_popup(self):
        """Close any open popup/dialog."""
        closed = False
        if self.vision.tap_on("btn_close_x", wait=False):
            closed = True
        elif self.vision.tap_on("btn_popup_close_x", wait=False):
            closed = True
        elif self.vision.tap_on("btn_close_x_panel", wait=False):
            closed = True
        elif self.vision.tap_on("btn_close_x_upgrade", wait=False):
            closed = True
        if closed:
            self.human.delay("fast")
        return closed

    def tap_back(self):
        """Press back button (in-game or Android)."""
        if self.vision.tap_on("btn_back", wait=False):
            self.human.delay("fast")
            return True
        self.adb.go_back()
        self.human.delay("fast")
        return True

    def tap_go(self):
        """Tap a 'Go' button (common in quests/events)."""
        return (self.vision.tap_on("btn_go_blue", wait=False) or
                self.vision.tap_on("btn_go_event", wait=False) or
                self.vision.tap_on("btn_go_requirement", wait=False) or
                self.vision.tap_on("btn_quest_go", wait=False))

    def tap_claim(self):
        """Tap a 'Claim' button."""
        return (self.vision.tap_on("btn_claim_green", wait=False) or
                self.vision.tap_on("btn_quest_claim", wait=False))

    def tap_ok(self):
        """Tap OK button."""
        return self.vision.tap_on("btn_ok_green", wait=False)

    def tap_gather(self):
        """Tap Gather button on resource popup."""
        return self.vision.tap_on("btn_gather", wait=False, timeout=5)

    def tap_search(self):
        """Tap Search button."""
        return (self.vision.tap_on("btn_search_blue", wait=False) or
                self.vision.tap_on("btn_search_conquest", wait=False) or
                self.vision.tap_on("btn_search_monster", wait=False))

    # ─── Resource Helpers ──────────────────────────────────

    def select_resource_tile(self, resource_type):
        """Select a resource tile type from search panel."""
        template = RESOURCE_TILES.get(resource_type)
        if template:
            return self.vision.tap_on(template, wait=False, timeout=5)
        return False

    def read_resources(self):
        """Read current resource values from top bar."""
        resources = {}
        for name, template in [
            ("food", "icon_resource_food"),
            ("wood", "icon_resource_wood"),
            ("stone", "icon_resource_stone"),
            ("iron", "icon_resource_iron"),
            ("gems", "icon_resource_gems"),
        ]:
            pos = self.vision.find(template, threshold=0.90)
            if pos:
                # Read number to the right of icon
                x, y, _ = pos
                value = self.vision.read_number(region=(x + 30, y - 5, 100, 25))
                resources[name] = value
        return resources

    # ─── Building Interaction ──────────────────────────────

    def tap_building(self, building_icon):
        """Tap a building icon in the city."""
        return self.vision.tap_on(building_icon, wait=False, threshold=0.80)

    def upgrade_building(self):
        """Click upgrade button on a building popup."""
        return self.vision.tap_on("btn_building_upgrade", wait=False, timeout=5)

    # ─── State Checks ─────────────────────────────────────

    def has_notification(self, button_name):
        """Check if a toolbar button has a red notification badge."""
        pos = self.vision.find(button_name, threshold=0.80)
        if pos:
            x, y, _ = pos
            # Check for red pixel near top-right of button
            return self.vision.check_pixel_color(
                x + 20, y - 20,
                expected_bgr=(50, 50, 200),  # Red in BGR
                tolerance=60
            )
        return False

    def is_event_active(self):
        """Check if there's an active event banner."""
        return (self.vision.exists("banner_kingdom_mayhem", threshold=0.80) or
                self.vision.exists("banner_kings_return", threshold=0.80))
