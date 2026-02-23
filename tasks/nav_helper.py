def hard_reset_to_world_map(bot):
    """Use bot's built-in go_to_city (handles exit popup), then tap world map."""
    bot.go_to_city()
    bot.wait(2)
    bot.tap(47, 643, jitter=False)
    bot.wait(3)
    print("  [nav] Hard reset -> world map")
    return True

def hard_reset_to_city(bot):
    """Use bot's built-in go_to_city (handles exit popup)."""
    bot.go_to_city()
    bot.wait(2)
    print("  [nav] Hard reset -> city")
    return True
