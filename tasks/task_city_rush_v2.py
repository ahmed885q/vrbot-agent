const chunk = "City Rush Task content here...";        self.target_level = 17
        self.current_level = 1
        self.stuck_count = 0
        self.last_action = None
        self.last_quest_text = None
        self.upgrade_queue = []
        self.resources = {"food": 0, "wood": 0, "stone": 0}
        self.upgrading_building = None
        self.step_counter = 0
        self.consecutive_same_action = 0

    def step(self, bot):
        """Main step - called repeatedly by the task scheduler"""
        self.step_counter += 1...            self.stuck_count = 0
            return

        # Check for train buttons
        train_btns = bot.yolo_find("button_train", screenshot)
        if train_btns:
            print("[CITY_RUSH] Train button found - tapping")
            bot.tap(train_btns[0][0], train_btns[0][1])
            time.sleep(2)
            self.stuck_count = 0
            return...                print(f"[CITY_RUSH] Tapping ({x}, {y})")
                bot.tap(x, y)
                time.sleep(1.5)
                return

        # Gather food
        if "gather_food" in response_lower:
            print("[CITY_RUSH] Gathering food...")
            self._tutorial_gather(bot, "food")
            return...            print("[CITY_RUSH] Fallback: going to map to gather")
            self._tutorial_gather(bot, "any")
        else:
            # Go to city and try tapping around
            print("[CITY_RUSH] Fallback: exploring city")
            bot.go_to_city()
            time.sleep(2)

        if self.stuck_count > 30:
            print("[CITY_RUSH] Too many stuck, forcing growth phase")
            self.phase = "growth"...        bot.go_to_city()\n        time.sleep(1)\n\n        # Ask AI to find the building\n        screenshot = bot.screenshot_b64()\n        prompt = (\n            f'I need to find and tap on building in this Viking Rise city.'\n        )\n        response = bot.ask_ai(prompt, screenshot)                    print(f'[CITY_RUSH] Tapping button')\n                    bot.tap(btns[0][0], btns[0][1])\n                    time.sleep(1)\n                    break\n            else:\n                # AI fallback for gather button\n                prompt2 = (\n                    'I tapped on a resource tile. Where is the Gather or March button? '\n                )\n                response2 = bot.ask_ai(prompt2, screenshot2)            return\n\n        time.sleep(3)\n\n    # Prerequisite System\n\n    def _check_and_upgrade_prerequisites(self, bot, reqs):\n        """Check and upgrade prerequisite buildings. Returns True if all met."""\n        for building_name, required_level in reqs['buildings']:\n            current_bldg_level = self._get_building_level(bot, building_name)\n            if current_bldg_level is not None and current_bldg_level < required_level:\n                print(f'[CITY_RUSH] Prereq: {building_name}')        return False\n\n    def _handle_sub_prerequisites(self, bot, building_name, target_level):\n        """Handle sub-prerequisites for a building"""\n        screenshot = bot.screenshot_b64()\n        prompt = (\n            f'Upgrading {building_name} is blocked. What requirement is shown?'\n        )\n        response = bot.ask_ai(prompt, screenshot)\n        print(f'[CITY_RUSH] Sub-prereq: {response}')        bot.tap(60, 600)\n        time.sleep(2)\n\n        screenshot = bot.screenshot_b64()\n        prompt = (\n            'World map: find nearest resource tile to gather from. '\n        )\n        response = bot.ask_ai(prompt, screenshot)\n        coords = re.findall(r'(\d+)', response)\n        if len(coords) >= 2:\n            bot.tap(int(coords[0]), int(coords[1]))        # Characters: Vigmarr, Ivor, Knut, Eira, etc.\n        prompt = (\n            'Is there a story dialog/cutscene on screen? '\n            'Signs: character portrait, name banner, dialog text at bottom, or arrow. '\n            'Reply: dialog or no'\n        )\n        response = bot.ask_ai(prompt, screenshot)\n        if 'dialog' in response.lower():\n            print('[CITY_RUSH] Story dialog detected - tapping to advance')\n            # Tap on the dialog text area (bottom center) to advance\n            bot.tap(540, 580)\n            time.sleep(1)
