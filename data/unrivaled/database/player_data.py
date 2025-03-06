from database.firebase import db
from concurrent.futures import ThreadPoolExecutor
import sys

def get_game_ids_for_player(player_name):
    """
    Fetch game IDs for a specific player from the `players/player_name/games/` subcollection.
    Match player names case-insensitively, but use the original name from the `players/` collection for queries.
    """
    try:
        # Fetch all player names from the `players/` collection
        players_ref = db.collection("players").stream()
        player_names = {doc.id.lower(): doc.id for doc in players_ref}  # Map lowercase names to original names

        # Check if the lowercase version of the input player_name exists in the map
        lowercase_player_name = player_name.lower()
        if lowercase_player_name not in player_names:
            print(f"No player found with name: {player_name}", file=sys.stderr)
            return []

        # Use the original name from the `players/` collection
        exact_player_name = player_names[lowercase_player_name]

        # Fetch game IDs for the player
        games_ref = db.collection("players").document(exact_player_name).collection("games").stream()
        game_ids = [doc.id for doc in games_ref]

        print(f"Found {len(game_ids)} games for player: {exact_player_name}")
        return game_ids
    except Exception as e:
        print(f"Error fetching game IDs for player {player_name}: {e}", file=sys.stderr)
        return []

def fetch_plays_for_player(game_id, player_name):
    """
    Fetch play-by-play data for a specific player in a game.
    Use the exact name format from the `players/` collection for matching.
    """
    try:
        # Fetch all player names from the `players/` collection
        players_ref = db.collection("players").stream()
        player_names = {doc.id.lower(): doc.id for doc in players_ref}  # Map lowercase names to original names

        # Check if the lowercase version of the input player_name exists in the map
        lowercase_player_name = player_name.lower()
        if lowercase_player_name not in player_names:
            print(f"No player found with name: {player_name}", file=sys.stderr)
            return []

        # Use the original name from the `players/` collection
        exact_player_name = player_names[lowercase_player_name]

        # Query the play_by_play subcollection for the game
        plays_ref = db.collection("games").document(game_id).collection("play_by_play").stream()

        # Filter plays for the specific player (case-insensitive and trimmed)
        plays = [
            play.to_dict() for play in plays_ref 
            if play.to_dict().get("player") and play.to_dict().get("player").lower().strip() == exact_player_name.lower().strip()
        ]

        print(f"Found {len(plays)} plays for {exact_player_name} in game {game_id}")
        return plays
    except Exception as e:
        print(f"Error fetching plays for player {player_name} in game {game_id}: {e}", file=sys.stderr)
        return []

def analyze_streaks(plays, player_name, stat_type):
    print(f"Looking at possible {stat_type} streaks for {player_name}")
    """
    Analyze streaks in parallel for large datasets.
    """
    streaks = {
        "hot_streaks": 0,
        "cold_streaks": 0,
        "assist_streaks": 0,
        "rebound_streaks": 0,
    }

    def process_play(play, previous_play):
        description = play.get("play_description", "").lower()
        result = {"hot": 0, "cold": 0, "assist": 0, "rebound": 0}

        if stat_type == "Points":
            if "makes" in description:
                if previous_play and "makes" in previous_play.get("play_description", "").lower():
                    result["hot"] = 1
            elif "misses" in description:
                if previous_play and "misses" in previous_play.get("play_description", "").lower():
                    result["cold"] = 1
        elif stat_type == "Assists":
            if "assist" in description:
                if previous_play and "turnover" not in previous_play.get("play_description", "").lower():
                    result["assist"] = 1
        elif stat_type == "Rebounds":
            if "offensive rebound" in description or "defensive rebound" in description:
                if previous_play and ("offensive rebound" in previous_play.get("play_description", "").lower() or
                                   "defensive rebound" in previous_play.get("play_description", "").lower()):
                    result["rebound"] = 1
        elif stat_type == "Pts+Rebs+Asts":
            if "makes" in description or "misses" in description:
                if previous_play and ("makes" in previous_play.get("play_description", "").lower() or
                                   "misses" in previous_play.get("play_description", "").lower()):
                    result["hot"] = 1
            elif "assist" in description:
                if previous_play and "turnover" not in previous_play.get("play_description", "").lower():
                    result["assist"] = 1
            elif "offensive rebound" in description or "defensive rebound" in description:
                if previous_play and ("offensive rebound" in previous_play.get("play_description", "").lower() or
                                   "defensive rebound" in previous_play.get("play_description", "").lower()):
                    result["rebound"] = 1

        return result

    with ThreadPoolExecutor() as executor:
        futures = []
        previous_play = None
        for play in plays:
            futures.append(executor.submit(process_play, play, previous_play))
            previous_play = play

        for future in futures:
            result = future.result()
            streaks["hot_streaks"] += result["hot"]
            streaks["cold_streaks"] += result["cold"]
            streaks["assist_streaks"] += result["assist"]
            streaks["rebound_streaks"] += result["rebound"]

    print(f"Streaks found for {player_name} in stat type: {stat_type}")
    return streaks

def get_game_stats(game_id, player_name):
    """
    Fetch the player's statistics for a specific game.
    Use the exact name format from the `players/` collection for matching.
    """
    try:
        # Fetch all player names from the `players/` collection
        players_ref = db.collection("players").stream()
        player_names = {doc.id.lower(): doc.id for doc in players_ref}  # Map lowercase names to original names

        # Check if the lowercase version of the input player_name exists in the map
        lowercase_player_name = player_name.lower()
        if lowercase_player_name not in player_names:
            print(f"No player found with name: {player_name}", file=sys.stderr)
            return {}

        # Use the original name from the `players/` collection
        exact_player_name = player_names[lowercase_player_name]

        # Fetch the player's game stats
        game_stats_ref = db.collection("players").document(exact_player_name).collection("games").document(game_id).get()
        if game_stats_ref.exists:
            game_stats = game_stats_ref.to_dict()
            return game_stats
        return {}
    except Exception as e:
        print(f"Error fetching game stats for player {player_name} in game {game_id}: {e}", file=sys.stderr)
        return {}
    
def get_opposing_team_stats(game_id, player_team):
    """
    Fetch stats for the opposing team in a specific game.
    Use the exact team name from the `teams/` collection for matching.
    """
    try:
        game_doc = db.collection("games").document(game_id).get()
        if game_doc.exists:
            game_data = game_doc.to_dict()
            opposing_team = game_data["away_team"] if game_data["home_team"] == player_team else game_data["home_team"]
            # print(player_team, opposing_team)

            # Fetch the opposing team's stats
            opposing_team_stats = db.collection("teams").document(opposing_team).get()
            if opposing_team_stats.exists:
                return {"opposing_team": opposing_team, **opposing_team_stats.to_dict()}  # Include team name and stats
            else:
                return {"opposing_team": opposing_team}  # Return at least the team name if stats are missing
        return {"opposing_team": "Unknown"}  # Default if game data is missing
    except Exception as e:
        print(f"Error fetching opposing team stats for game {game_id}: {e}", file=sys.stderr)
        return {"opposing_team": "Unknown"}  # Default if an error occurs

def get_past_performance_against_opponent(player_name, opposing_team):
    """
    Fetch and analyze the player's past performance against a specific opposing team.
    Use the exact name format from the `players/` collection for matching.
    """
    try:
        # Fetch all player names from the `players/` collection
        players_ref = db.collection("players").stream()
        player_names = {doc.id.lower(): doc.id for doc in players_ref}  # Map lowercase names to original names

        # Check if the lowercase version of the input player_name exists in the map
        lowercase_player_name = player_name.lower()
        if lowercase_player_name not in player_names:
            print(f"No player found with name: {player_name}", file=sys.stderr)
            return []

        # Use the original name from the `players/` collection
        exact_player_name = player_names[lowercase_player_name]

        # Fetch game IDs for the player
        games_ref = db.collection("players").document(exact_player_name).collection("games").stream()
        doc_ref = db.collection("players").document(exact_player_name)
        doc = doc_ref.get()

        team = doc.to_dict().get("team")

        # print(team)
        past_performance = []

        for game in games_ref:
            # game_data = game.to_dict()
            game_id = game.id
            game_stats = get_game_stats(game_id, exact_player_name)
            opposing_team_stats = get_opposing_team_stats(game_id, team)

            if opposing_team_stats.get("opposing_team", "").lower() == opposing_team.lower():
                past_performance.append({
                    "game_id": game_id,
                    "stats": game_stats,
                    "opposing_team_stats": opposing_team_stats
                })

        print(f"Found {len(past_performance)} past performances for {exact_player_name} against {opposing_team}")
        return past_performance
    except Exception as e:
        print(f"Error fetching past performance for {player_name} against {opposing_team}: {e}", file=sys.stderr)
        return []