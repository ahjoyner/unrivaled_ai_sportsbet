def calculate_per(player_name, db, league_average_uper=None):
    """
    Calculate the Player Efficiency Rating (PER) for a given player using the updated formulas.

    Args:
        player_name (str): The name of the player.
        db: The Firebase database connection object.
        league_average_uper (float, optional): Precomputed league-wide average UPER.

    Returns:
        float: The calculated PER for the player, or None if the player has no minutes played.
    """
    # Fetch player data from Firebase
    player_ref = db.collection("players").document(player_name.replace(" ", "_"))
    player_stats = player_ref.get().to_dict()

    # If no stats are found, return None instead of raising an error
    if not player_stats:
        print(f"⚠ No stats found for player: {player_name}. Skipping PER calculation.")
        return None

    # Fetch individual game stats for the player
    games_ref = player_ref.collection("games")
    games = games_ref.stream()

    # Initialize total stats
    total_points = 0
    total_assists = 0
    total_offensive_rebounds = 0
    total_defensive_rebounds = 0
    total_steals = 0
    total_blocks = 0
    total_fg_attempted = 0
    total_fg_made = 0
    total_ft_attempted = 0
    total_ft_made = 0
    total_turnovers = 0
    total_fouls = 0
    total_minutes = 0

    # Aggregate stats from individual games
    for game in games:
        game_stats = game.to_dict()

        # Convert all stats to integers or floats
        total_points += int(game_stats.get("pts", 0))
        total_assists += int(game_stats.get("ast", 0))
        total_offensive_rebounds += int(game_stats.get("offensive_rebounds", 0))
        total_defensive_rebounds += int(game_stats.get("defensive_rebounds", 0))
        total_steals += int(game_stats.get("stl", 0))
        total_blocks += int(game_stats.get("blk", 0))
        total_fg_attempted += int(game_stats.get("fg_a", 0))
        total_fg_made += int(game_stats.get("fg_m", 0))
        total_ft_attempted += int(game_stats.get("ft_a", 0))
        total_ft_made += int(game_stats.get("ft_m", 0))
        total_turnovers += int(game_stats.get("turnovers", 0))
        total_fouls += int(game_stats.get("pf", 0))
        total_minutes += int(game_stats.get("min", 0))

    # Calculate averages
    num_games = player_stats.get("gp", 1)
    points = total_points / num_games
    assists = total_assists / num_games
    offensive_rebounds = total_offensive_rebounds / num_games
    defensive_rebounds = total_defensive_rebounds / num_games
    steals = total_steals / num_games
    blocks = total_blocks / num_games
    fg_attempted = total_fg_attempted / num_games
    fg_made = total_fg_made / num_games
    ft_attempted = total_ft_attempted / num_games
    ft_made = total_ft_made / num_games
    turnovers = total_turnovers / num_games
    fouls = total_fouls / num_games
    minutes_played = total_minutes / num_games

    # Check if minutes_played is 0
    if minutes_played <= 0:
        print(f"⚠ Player {player_name} has 0 minutes played. Skipping PER calculation.")
        return None

    # Compute UPER (Unadjusted PER)
    uPER = (
        points
        + 0.7 * assists
        + 0.85 * offensive_rebounds
        + 0.5 * defensive_rebounds
        + steals
        + blocks
        - 0.7 * (fg_attempted - fg_made)
        - 0.5 * (ft_attempted - ft_made)
        - turnovers
        - 0.3 * fouls
    ) / minutes_played

    # If league average UPER isn't provided, return UPER only
    if league_average_uper is None:
        return uPER

    # Normalize UPER to league average
    # PER = uPER * (15 / league_average_uper)

    return uPER

def compute_league_average_uper(db):
    """
    Compute the league-wide average UPER by iterating over all players.

    Args:
        db: The Firebase database connection object.

    Returns:
        float: The calculated league-wide average UPER.
    """
    league_total_uper = 0
    num_players = 0
    players_ref = db.collection("players").stream()

    for player in players_ref:
        player_name = player.id
        player_uper = calculate_per(player_name, db)  # Get unadjusted UPER

        if player_uper is not None:
            league_total_uper += player_uper
            num_players += 1

    return league_total_uper / num_players if num_players > 0 else 15.0

def get_league_average_per(league_average_uper):
    """
    Given the league-wide average UPER, calculate the league-wide PER.

    Args:
        league_average_uper (float): The computed league-wide UPER.

    Returns:
        float: The league-wide PER (should always be 15).
    """
    return 15  # By definition

