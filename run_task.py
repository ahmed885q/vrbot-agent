    "recruit_farmers": ("tasks.task_recruit_farmers", "TaskRecruitFarmers"),
    "village_champions": ("tasks.task_village_champions", "TaskVillageChampions"),
    # Phase 5: Heroes
    "hall_of_valor": ("tasks.task_hall_of_valor", "TaskHallOfValor"),
    "hero_xp": ("tasks.task_hero_xp", "TaskHeroXp"),
    "hero_training": ("tasks.task_hero_training", "TaskHeroTraining"),
    "account_items": ("tasks.task_account_items", "TaskAccountItems"),
    "divination": ("tasks.task_divination", "TaskDivination"),
    "smithy": ("tasks.task_smithy", "TaskSmithy"),
    # Phase 6: Combat
    "gather": ("tasks.task_gather", "TaskGather"),
    "niflung": ("tasks.task_niflung", "TaskNiflung"),
    "staging_post": ("tasks.task_staging_post", "TaskStagingPost"),
    "clear_forest": ("tasks.task_clear_forest", "TaskClearForest"),
    "cinderbone": ("tasks.task_cinderbone", "TaskCinderbone"),
    "reclaim_midgard": ("tasks.task_reclaim_midgard", "TaskReclaimMidgard"),
    # Phase 7: Events
    "leidolf": ("tasks.task_leidolf", "TaskLeidolf"),
    "festival_flames": ("tasks.task_festival_flames", "TaskFestivalFlames"),
    "promo_codes": ("tasks.task_promo_codes", "TaskPromoCodes"),
    # Phase 8: Strategy
    "chief_hall": ("tasks.task_chief_hall", "TaskChiefHall"),
    "upgrade_chief_hall": ("tasks.task_upgrade_chief_hall", "TaskUpgradeChiefHall"),
    "expansion": ("tasks.task_expansion", "TaskExpansion"),
    "tribe_tech": ("tasks.task_tribe_tech", "TaskTribeTech"),
    "chapter": ("tasks.task_chapter", "TaskChapter"),
    "city_rush": ("tasks.task_city_rush_v2", "TaskCityRush"),
}

def run(task_name):
    if task_name not in TASK_MAP:
        print(f"Unknown task: {task_name}")
        print(f"Available: {list(TASK_MAP.keys())}")
        return
    module_name, class_name = TASK_MAP[task_name]
    mod = __import__(module_name, fromlist=[class_name])
    cls = getattr(mod, class_name)
    bot = Bot()
    print("  [setup] Navigating to city...")
    bot.go_to_city()
    bot.wait(1)
    print(f"\n  Running: {cls.name}")
    print("=" * 50)
    task = cls(bot)
    success = task.run()
    print("=" * 50)
    print(f"  Result: {'OK' if success else 'FAIL'}")
    bot.go_to_city()

def main():
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        print("  Available tasks:")
        for name in TASK_MAP:
            print(f"    {name}")
        return
    run(sys.argv[1])

if __name__ == "__main__":
    main()

