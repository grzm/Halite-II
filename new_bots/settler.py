import common


my_tag, map_size, initial_map = common.initialize("Settler")

while True:
    game_map = common.get_map()
    command_queue = []

    for ship in game_map.ships[my_tag].values():
        if ship.docked != "undocked":
            continue

        planets = game_map.planets.values()
        for planet in planets:
            if planet.owned:
                continue

            angle, distance = common.orient_towards(ship, planet)
            if common.can_dock(ship, planet):
                command_queue.append(common.dock(ship, planet))
            else:
                command_queue.append(common.move_to(ship, angle, 1))

            break

    common.send_command_queue(command_queue)