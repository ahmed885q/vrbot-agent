"""
City Rush Task for Viking Rise - Automates Chief Hall upgrade from Level 1 to Level 17

This is the most critical automation for new farms. Every new account needs to reach
Chief Hall Level 17 to unlock all buildings and game features. The script handles:
- Tutorial completion (Lv1-5)
- Growth phase with auto-upgrades (Lv5-10)
- Rush phase with resource management (Lv10-17)
"""

import time
import re
from base_task import BaseTask


class TaskCityRush(BaseTask):
    """Automate Chief Hall upgrade from Level 1 to Level 17 in Viking Rise"""
    
    name = "City Rush"
    tag = "city_rush"
    description = "Upgrade Chief Hall from Level 1 to Level 17 automatically"
    cooldown_hours = 0  # No cooldown - continuous until done
    max_steps = 500
    max_stuck = 15
    
    def setup(self, bot):
        """Initialize task state"""
        self.phase = "tutorial"  # tutorial, growth, rush
        self.target_level = 17
        self.current_level = 1
        self.stuck_count = 0
        self.last_screen = None
        self.tutorial_complete = False
        self.phase_transitions = {
            5: "growth",
            10: "rush"
        }
        self.prerequisite_buildings = {
            # Building name: (required_level, priority)
            "Barracks": (3, 1),
            "Storage": (2, 2),
            "Farm": (1, 3),
            "Gold Mine": (5, 2),
        }
        print(f"[CITY_RUSH] Task initialized - Target: Chief Hall Level {self.target_level}")
    
    def step(self, bot, step_num):
        """Execute one step of the city rush automation"""
        try:
            # Take screenshot for analysis
            screenshot = bot.screenshot_b64()
            
            # Detect screen state
            screen_info = bot.detect_screen()
            print(f"[CITY_RUSH] Step {step_num} | Phase: {self.phase} | Level: {self.current_level}")
            
            # Check if we're stuck
            if screen_info == self.last_screen:
                self.stuck_count += 1
                print(f"[CITY_RUSH] Stuck detection: {self.stuck_count}/{self.max_stuck}")
                if self.stuck_count >= self.max_stuck:
                    print("[CITY_RUSH] Task stuck - attempting recovery")
                    self._recover_from_stuck(bot)
                    self.stuck_count = 0
            else:
                self.stuck_count = 0
                self.last_screen = screen_info
            
            # Route based on phase
            if self.phase == "tutorial":
                self._handle_tutorial(bot)
            elif self.phase == "growth":
                self._handle_growth_phase(bot)
            elif self.phase == "rush":
                self._handle_rush_phase(bot)
            
            # Check if task is complete
            if self.current_level >= self.target_level:
                print(f"[CITY_RUSH] SUCCESS! Chief Hall Level {self.current_level} reached!")
                return True
            
            return False
            
        except Exception as e:
            print(f"[CITY_RUSH] Error in step {step_num}: {e}")
            return False
    
    def _handle_tutorial(self, bot):
        """Phase 1: Handle tutorial completion (Level 1-5)"""
        print("[CITY_RUSH] Tutorial phase active")
        
        # Check if tutorial is already complete (city view visible)
        screenshot = bot.screenshot_b64()
        
        # Look for tutorial arrows/highlights
        tutorial_arrows = bot.yolo_find("tutorial_arrow", screenshot)
        if tutorial_arrows:
            print(f"[CITY_RUSH] Tutorial arrow detected at {tutorial_arrows[0]}")
            # Tap the arrow or the highlighted area
            x, y = tutorial_arrows[0]
            bot.tap(x, y)
            time.sleep(1)
            return
        
        # Look for "Agree" or "OK" buttons
        agree_buttons = bot.yolo_find("button_agree", screenshot)
        if agree_buttons:
            print("[CITY_RUSH] Agree button found - tapping")
            bot.tap(agree_buttons[0][0], agree_buttons[0][1])
            time.sleep(1)
            return
        
        # Look for Chief Hall upgrade button in tutorial
        upgrade_btns = bot.yolo_find("button_upgrade", screenshot)
        if upgrade_btns:
            print("[CITY_RUSH] Upgrade button found - tapping for tutorial")
            bot.tap(upgrade_btns[0][0], upgrade_btns[0][1])
            time.sleep(1.5)
            return
        
        # Use AI to understand tutorial
        print("[CITY_RUSH] Asking AI about tutorial state")
        prompt = """Analyze this Viking Rise game screen. What does the tutorial want me to do?
        Look for: arrows, highlighted areas, tutorial text, buttons with "Next", "Tap here", etc.
        Respond with: 'tutorial: <action>' or 'city_view: <description>' if tutorial complete."""
        
        ai_response = bot.ask_ai(prompt, screenshot)
        print(f"[CITY_RUSH] AI response: {ai_response}")
        
        if "city_view" in ai_response.lower():
            # Tutorial complete - check level and move to growth phase
            self.current_level = self._detect_chief_hall_level(bot)
            if self.current_level >= 5:
                print(f"[CITY_RUSH] Tutorial complete at Level {self.current_level}")
                self.phase = "growth"
                self.tutorial_complete = True
        else:
            # Try blind tap in center of screen for tutorial
            print("[CITY_RUSH] Blind tap on screen for tutorial")
            bot.tap(640, 360)
            time.sleep(0.5)
    
    def _handle_growth_phase(self, bot):
        """Phase 2: Handle growth phase (Level 5-10)"""
        print(f"[CITY_RUSH] Growth phase | Current: {self.current_level}")
        
        # Check for popups first
        if self._handle_popups(bot):
            return
        
        # Detect current Chief Hall level
        self.current_level = self._detect_chief_hall_level(bot)
        
        # Transition to rush phase if needed
        if self.current_level >= 10:
            self.phase = "rush"
            print(f"[CITY_RUSH] Transitioning to rush phase at Level {self.current_level}")
            return
        
        # Check if Chief Hall is currently upgrading
        if self._is_chief_hall_upgrading(bot):
            print("[CITY_RUSH] Chief Hall is upgrading - waiting")
            time.sleep(2)
            return
        
        # Try to upgrade Chief Hall
        if self._upgrade_chief_hall(bot):
            print(f"[CITY_RUSH] Chief Hall upgrade initiated - now Level {self.current_level + 1}")
            time.sleep(1)
            return
        
        # If upgrade failed, try to build/upgrade prerequisites
        print("[CITY_RUSH] Chief Hall upgrade not available - checking prerequisites")
        if self._handle_prerequisites(bot):
            return
        
        # Gather resources if needed
        if self._should_gather_resources(bot):
            print("[CITY_RUSH] Gathering resources")
            self._gather_resources(bot)
            return
        
        # Wait for resources
        print("[CITY_RUSH] Waiting for resources to accumulate")
        time.sleep(3)
    
    def _handle_rush_phase(self, bot):
        """Phase 3: Handle rush phase (Level 10-17)"""
        print(f"[CITY_RUSH] Rush phase | Current: {self.current_level}")
        
        # Check for popups
        if self._handle_popups(bot):
            return
        
        # Detect current level
        self.current_level = self._detect_chief_hall_level(bot)
        
        # Check completion
        if self.current_level >= self.target_level:
            print(f"[CITY_RUSH] SUCCESS! Reached Level {self.current_level}")
            return
        
        # Check upgrade status
        if self._is_chief_hall_upgrading(bot):
            print("[CITY_RUSH] Chief Hall upgrading - checking for speedup opportunity")
            # Optionally use speedups for high levels
            if self.current_level >= 15:
                self._use_speedups(bot)
            time.sleep(2)
            return
        
        # Try upgrade
        if self._upgrade_chief_hall(bot):
            print(f"[CITY_RUSH] Level {self.current_level + 1} upgrade started")
            time.sleep(1)
            return
        
        # Handle prerequisites
        if self._handle_prerequisites(bot):
            return
        
        # Gather if needed
        if self._should_gather_resources(bot):
            self._gather_resources(bot)
            return
        
        time.sleep(3)
    
    def _detect_chief_hall_level(self, bot):
        """
        Detect current Chief Hall level from the screen.
        Uses multiple methods to avoid AI hallucination.
        """
        screenshot = bot.screenshot_b64()
        
        # Method 1: Look for level text on Chief Hall building
        prompt = """Look at the Chief Hall building in the center of the screen.
        Find the level number displayed on or near it. Return only the number (1-17).
        Format: level: <number>"""
        
        try:
            response = bot.ask_ai(prompt, screenshot)
            match = re.search(r'level:\s*(\d+)', response.lower())
            if match:
                level = int(match.group(1))
                if 1 <= level <= 17:
                    print(f"[CITY_RUSH] Detected Chief Hall Level {level}")
                    return level
        except Exception as e:
            print(f"[CITY_RUSH] Error detecting level: {e}")
        
        # Method 2: Try to find level indicator with YOLO
        level_indicators = bot.yolo_find("level_indicator", screenshot)
        if level_indicators:
            print(f"[CITY_RUSH] Found level indicator at {level_indicators[0]}")
        
        # Fallback: return last known level
        return self.current_level
    
    def _upgrade_chief_hall(self, bot):
        """
        Attempt to upgrade the Chief Hall.
        Navigate to Chief Hall and initiate upgrade.
        """
        print("[CITY_RUSH] Attempting Chief Hall upgrade")
        
        # Go to city view
        bot.go_to_city()
        time.sleep(1)
        
        # Look for Chief Hall building (usually in center)
        screenshot = bot.screenshot_b64()
        chief_hall = bot.yolo_find("chief_hall", screenshot)
        
        if not chief_hall:
            print("[CITY_RUSH] Chief Hall not found - using center tap")
            chief_hall = [(640, 360)]
        
        # Tap Chief Hall
        x, y = chief_hall[0]
        print(f"[CITY_RUSH] Tapping Chief Hall at ({x}, {y})")
        bot.tap(x, y)
        time.sleep(1)
        
        # Look for upgrade button
        screenshot = bot.screenshot_b64()
        upgrade_buttons = bot.yolo_find("button_upgrade", screenshot)
        
        if upgrade_buttons:
            bot.tap(upgrade_buttons[0][0], upgrade_buttons[0][1])
            print("[CITY_RUSH] Upgrade button tapped")
            time.sleep(1.5)
            
            # Check for confirmation dialog
            screenshot = bot.screenshot_b64()
            confirm_btns = bot.yolo_find("button_confirm", screenshot)
            if confirm_btns:
                bot.tap(confirm_btns[0][0], confirm_btns[0][1])
                print("[CITY_RUSH] Upgrade confirmed")
                self.current_level += 1
                return True
            
            return True
        
        # Look for "Insufficient Resources" or "Upgrade in Progress"
        prompt = "Is there an upgrade in progress or insufficient resources message?"
        response = bot.ask_ai(prompt, screenshot)
        if "insufficient" in response.lower() or "not enough" in response.lower():
            print("[CITY_RUSH] Insufficient resources for upgrade")
            return False
        
        if "progress" in response.lower() or "upgrading" in response.lower():
            print("[CITY_RUSH] Upgrade already in progress")
            return False
        
        print("[CITY_RUSH] Could not find upgrade button")
        return False
    
    def _is_chief_hall_upgrading(self, bot):
        """Check if Chief Hall is currently upgrading"""
        screenshot = bot.screenshot_b64()
        
        # Look for timer/progress
        prompt = "Is the Chief Hall currently upgrading? Look for a timer or progress bar on the building."
        response = bot.ask_ai(prompt, screenshot)
        
        return "yes" in response.lower() or "upgrading" in response.lower()
    
    def _handle_popups(self, bot):
        """
        Handle random popups (events, offers, tutorials, etc.)
        Returns True if a popup was handled.
        """
        screenshot = bot.screenshot_b64()
        
        # Look for close/X buttons
        close_buttons = bot.yolo_find("button_close", screenshot)
        if close_buttons:
            print("[CITY_RUSH] Popup detected - closing")
            bot.tap(close_buttons[0][0], close_buttons[0][1])
            time.sleep(0.5)
            return True
        
        # Check with AI
        prompt = "Is there a popup or modal dialog on the screen? What does it say?"
        response = bot.ask_ai(prompt, screenshot)
        
        if "popup" in response.lower() or "modal" in response.lower():
            print(f"[CITY_RUSH] Popup detected: {response}")
            
            # Try to close it
            if "close" in response.lower() or "x" in response.lower():
                # Tap top-right corner for X button
                bot.tap(1250, 50)
                time.sleep(0.5)
                return True
            
            # Tap outside popup to close
            bot.tap(100, 100)
            time.sleep(0.5)
            return True
        
        return False
    
    def _handle_prerequisites(self, bot):
        """
        Build or upgrade prerequisite buildings if Chief Hall upgrade is blocked.
        Returns True if an action was taken.
        """
        print("[CITY_RUSH] Checking prerequisites")
        screenshot = bot.screenshot_b64()
        
        # Check what building is needed
        prompt = f"""Chief Hall upgrade is not available. What prerequisite building needs to be 
        upgraded? Current level is {self.current_level}. Return format: building: <name>"""
        
        response = bot.ask_ai(prompt, screenshot)
        print(f"[CITY_RUSH] Prerequisite check: {response}")
        
        # Try to find and upgrade a building
        for building_name in self.prerequisite_buildings.keys():
            if building_name.lower() in response.lower():
                print(f"[CITY_RUSH] Need to upgrade {building_name}")
                # Tap on that building or navigate to it
                bot.go_to_city()
                time.sleep(1)
                # Generic attempt to find and tap building
                buildings = bot.yolo_find(f"building_{building_name.lower()}", screenshot)
                if buildings:
                    bot.tap(buildings[0][0], buildings[0][1])
                    time.sleep(1)
                    return True
        
        return False
    
    def _should_gather_resources(self, bot):
        """Check if we need to gather resources"""
        screenshot = bot.screenshot_b64()
        
        prompt = """Check the resource bars (Food, Wood, Stone, Gold).
        Are they critically low (less than 25% of capacity)? Answer yes or no."""
        
        response = bot.ask_ai(prompt, screenshot)
        return "yes" in response.lower()
    
    def _gather_resources(self, bot):
        """Send troops to gather resources"""
        print("[CITY_RUSH] Gathering resources")
        screenshot = bot.screenshot_b64()
        
        # Look for gather button or resource nodes
        gather_btns = bot.yolo_find("button_gather", screenshot)
        if gather_btns:
            bot.tap(gather_btns[0][0], gather_btns[0][1])
            time.sleep(1)
            return
        
        # Navigate to world map
        bot.tap(640, 360)  # Tap to close any menus
        time.sleep(0.5)
    
    def _use_speedups(self, bot):
        """Use available speedup items"""
        print("[CITY_RUSH] Attempting to use speedups")
        screenshot = bot.screenshot_b64()
        
        # Look for speedup items
        speedup_btns = bot.yolo_find("button_speedup", screenshot)
        if speedup_btns:
            print("[CITY_RUSH] Speedup item found - using")
            bot.tap(speedup_btns[0][0], speedup_btns[0][1])
            time.sleep(1)
            return True
        
        return False
    
    def _recover_from_stuck(self, bot):
        """Recover from stuck state"""
        print("[CITY_RUSH] Recovery attempt: closing menus and returning to city")
        
        # Try to get back to city view
        bot.go_to_city()
        time.sleep(1)
        
        # Close any popups
        bot.tap(1250, 50)  # Try X button top-right
        time.sleep(0.5)
        
        # Tap center to reset
        bot.tap(640, 360)
        time.sleep(0.5)
        
        print("[CITY_RUSH] Recovery complete - continuing task")
    
    def _detect_completion(self, bot):
        """Detect if task is complete"""
        self.current_level = self._detect_chief_hall_level(bot)
        return self.current_level >= self.target_level


# Task entry point
def create_task():
    """Factory function to create the task"""
    return TaskCityRush()


if __name__ == "__main__":
    # For testing purposes
    print("City Rush Task Module")
    print(f"Task: {TaskCityRush.name}")
    print(f"Tag: {TaskCityRush.tag}")
    print("Ready to run with VRBOT framework")
