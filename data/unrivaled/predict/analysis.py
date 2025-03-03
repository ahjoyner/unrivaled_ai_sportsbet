import firebase_admin
from firebase_admin import credentials, firestore
import aiohttp
import asyncio
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
import os
from collections import defaultdict
import re
from concurrent.futures import ThreadPoolExecutor

# Load environment variables
load_dotenv("unrivaled-dash/.env.local")

# Initialize Firebase
cred = credentials.Certificate("secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client(database_id="unrivaled-db")

# DeepSeek API settings
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# --- Helper Functions ---

def get_player_teams():
    """
    Fetch player teams from the `players` collection.
    Returns a dictionary mapping player names (lowercase) to their teams.
    """
    player_teams = {}
    player_docs = db.collection("players").stream()
    for doc in player_docs:
        player_data = doc.to_dict()
        player_name = doc.id.lower()  # Use lowercase for consistency
        player_teams[player_name] = player_data.get("player_data", {}).get("team", "")
    return player_teams

def fetch_injury_reports():
    """
    Fetch injury reports from the database or a JSON file.
    """
    try:
        with open("/Users/ajoyner/unrivaled_ai_sportsbet/data/unrivaled/injury_reports.json", "r") as f:
            injury_data = json.load(f)
        return injury_data.get("injury_reports", [])
    except Exception as e:
        print(f"Error fetching injury reports: {e}", file=sys.stderr)
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

def analyze_streaks(plays):
    """
    Analyze streaks in parallel for large datasets.
    """
    streaks = {
        "hot_streaks": 0,
        "cold_streaks": 0,
        "assist_streaks": 0
    }

    def process_play(play, previous_play):
        description = play.get("play_description", "").lower()
        result = {"hot": 0, "cold": 0, "assist": 0}

        if "makes" in description:
            if previous_play and "makes" in previous_play.get("play_description", "").lower():
                result["hot"] = 1
        elif "misses" in description:
            if previous_play and "misses" in previous_play.get("play_description", "").lower():
                result["cold"] = 1
        elif "assist" in description:
            if previous_play and "turnover" not in previous_play.get("play_description", "").lower():
                result["assist"] = 1

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

# --- DeepSeek API Functions ---

async def analyze_game_flow(session, player_name, game_id):
    """
    Analyze game flow using DeepSeek API.
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    plays = fetch_plays_for_player(game_id, player_name)
    if not plays:
        print(f"No play-by-play data found for {player_name} in Game {game_id}.", file=sys.stderr)
        return None

    streaks = analyze_streaks(plays)

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the following play-by-play data for {player_name} in Game {game_id}:\n\n"
                    f"Play-by-Play Data: {plays}\n\n"
                    f"Streaks Analysis:\n"
                    f"Hot Streaks (back-to-back makes): {streaks['hot_streaks']}\n"
                    f"Cold Streaks (back-to-back misses): {streaks['cold_streaks']}\n"
                    f"Assist Streaks (assists without turnovers): {streaks['assist_streaks']}\n\n"
                    "Provide an analysis of the player's form in this game, including:\n"
                    "1. How the player performed in different quarters.\n"
                    "2. The player's consistency throughout the game.\n"
                    "3. The player's impact on the flow of the game."
                )
            }
        ]
    }

    try:
        async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                if result and "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
            else:
                print(f"Failed to get analysis from DeepSeek API for game flow analysis of {player_name} in Game {game_id}. Status: {response.status}", file=sys.stderr)
    except Exception as e:
        print(f"Error during DeepSeek API request for game flow analysis of {player_name} in Game {game_id}: {e}", file=sys.stderr)
    return None

async def analyze_past_performance(session, player_name, opposing_team):
    """
    Analyze past performance against a specific opposing team using DeepSeek API.
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    past_performance = get_past_performance_against_opponent(player_name, opposing_team)
    if not past_performance:
        print(f"No past performance data found for {player_name} against {opposing_team}.", file=sys.stderr)
        return None

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the following past performance data for {player_name} against {opposing_team}:\n\n"
                    f"Past Performance Data: {past_performance}\n\n"
                    "Provide an analysis of the player's performance against this team, including:\n"
                    "1. Scoring trends.\n"
                    "2. Assist and rebound trends.\n"
                    "3. Turnover and foul trends."
                )
            }
        ]
    }

    try:
        async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                if result and "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
            else:
                print(f"Failed to get analysis from DeepSeek API for past performance analysis of {player_name} against {opposing_team}. Status: {response.status}", file=sys.stderr)
    except Exception as e:
        print(f"Error during DeepSeek API request for past performance analysis of {player_name} against {opposing_team}: {e}", file=sys.stderr)
    return None

async def calculate_final_confidence_level(session, player_name, player_team, game_flow_analysis, past_performance_analysis, player_prop, opposing_team, injury_reports):
    """
    Calculate the final confidence level using DeepSeek API.
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    injury_context = ""
    if injury_reports:
        for report in injury_reports:
            if report["team"].lower() == player_team.lower() or report["team"].lower() == opposing_team.lower():
                injury_context += f"{report['player']} ({report['team']}) is {report['status']} with {report['injury']}.\n"

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the following data for {player_name}:\n\n"
                    f"Game Flow Analysis: {game_flow_analysis}\n\n"
                    f"Past Performance Analysis: {past_performance_analysis}\n\n"
                    f"Player Prop: {player_prop} points\n\n"
                    f"Opposing Team: {opposing_team}\n\n"
                    f"Injury Reports:\n{injury_context}\n\n"
                    "Provide a confidence level (0-100) and 4 reasons for taking the over or under on the player's prop line, as well as a final summary."
                )
            }
        ]
    }

    try:
        async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                if result and "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
            else:
                print(f"Failed to get analysis from DeepSeek API for final analysis of {player_name}. Status: {response.status}", file=sys.stderr)
    except Exception as e:
        print(f"Error during DeepSeek API request for final analysis of {player_name}: {e}", file=sys.stderr)
    return None

# --- Main Analysis Flow ---

async def analyze_player(player):
    """
    Analyze a player's performance across all their games.
    """
    async with semaphore:  # Use semaphore to limit concurrency
        player_name = player["player_data"]["name"].replace(" ", "_")
        # Fetch all player names from the `players/` collection
        players_ref = db.collection("players").stream()
        player_names = {doc.id.lower(): doc.id for doc in players_ref}  # Map lowercase names to original names

        # Check if the lowercase version of the input player_name exists in the map
        lowercase_player_name = player_name.lower()
        if lowercase_player_name not in player_names:
            print(f"No player found with name: {player_name}", file=sys.stderr)
            return []

        # Use the original name from the `players/` collection
        player_name = player_names[lowercase_player_name]
        # print(player_name)
        player_team = player["player_data"]["team"]
        opposing_team = player["projection_data"]["description"]
        player_prop = player["projection_data"]["line_score"]

        if not player_team:
            print(f"No team found for player: {player_name}", file=sys.stderr)
            return None

        game_ids = get_game_ids_for_player(player_name)
        if not game_ids:
            print(f"No games found for player: {player_name}", file=sys.stderr)
            return None

        async with aiohttp.ClientSession() as session:
            # Analyze game flow for each game
            game_flow_analyses = []
            for game_id in game_ids:
                game_flow_analysis = await analyze_game_flow(session, player_name, game_id)
                if game_flow_analysis:
                    game_flow_analyses.append(game_flow_analysis)

            # Analyze past performance against the opposing team
            past_performance_analysis = await analyze_past_performance(session, player_name, opposing_team)

            # Fetch injury reports
            injury_reports = fetch_injury_reports()

            # Calculate final confidence level
            final_analysis = await calculate_final_confidence_level(
                session, player_name, player_team, game_flow_analyses, past_performance_analysis, player_prop, opposing_team, injury_reports
            )

            if final_analysis:
                print(f"Final Analysis for {player_name}:\n{final_analysis}", file=sys.stderr)
                save_analysis_results(player_name, final_analysis)  # Save the analysis results
                return final_analysis
            else:
                print(f"Failed to generate final analysis for {player_name}.", file=sys.stderr)
                return None

def save_analysis_results(player_name, analysis_text):
    """
    Save the analysis results to Firestore under players/{player_name}/analysis_results.
    Parse the analysis text to extract confidence level, reasons, and final conclusion.
    """
    try:
        # Parse the analysis text to extract confidence level, reasons, and final conclusion
        confidence_level = None
        reasons = {
            "reason_1": None,  # Performance Against Opposing Team
            "reason_2": None,  # Scoring Trends
            "reason_3": None,  # Role & Teammate Interactions
            "reason_4": None,  # Recent Game Flow Analysis
        }
        final_conclusion = None

        # Extract confidence level
        confidence_match = re.search(r"Confidence Level: (\d+)%", analysis_text)
        if confidence_match:
            confidence_level = int(confidence_match.group(1))

        # Extract reasons
        reason_matches = re.findall(r"### Reasons for Taking the (Over|Under):\n\n(.*?)\n\n---", analysis_text, re.DOTALL)
        if reason_matches:
            reasons_text = reason_matches[0][1]  # Take the first set of reasons (Over or Under)
            reason_lines = reasons_text.split("\n\n")
            for i, line in enumerate(reason_lines):
                if i < 4:  # Only extract the first 4 reasons
                    reasons[f"reason_{i + 1}"] = line.strip()

        # Extract final conclusion
        conclusion_match = re.search(r"### Final Summary:(.*)", analysis_text, re.DOTALL)
        if conclusion_match:
            final_conclusion = conclusion_match.group(1).strip()

        # Prepare the analysis data
        analysis_data = {
            "confidence_level": confidence_level,
            **reasons,
            "final_conclusion": final_conclusion,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }

        # Save the analysis data to Firestore
        db.collection("players").document(player_name).collection("analysis_results").document("latest").set(analysis_data)
        print(f"✅ Analysis results saved for {player_name}")
    except Exception as e:
        print(f"❌ Error saving analysis results for {player_name}: {e}", file=sys.stderr)

# --- Main Function ---

async def main():
    """
    Main function to analyze all players.
    """
    prop_lines_ref = db.collection("prop_lines").stream()
    enriched_data = []
    for doc in prop_lines_ref:
        player_data = doc.to_dict()
        enriched_data.append({
            "player_data": player_data.get("player_data", {}),
            "projection_data": player_data.get("projection_data", {})
        })

    # Set semaphore limit to the number of player props
    global semaphore
    semaphore = asyncio.Semaphore(len(enriched_data))

    tasks = [analyze_player(player) for player in enriched_data]
    results = await asyncio.gather(*tasks)

    output = {}
    for player, result in zip(enriched_data, results):
        player_name = player["player_data"]["name"]
        if result:
            output[player_name] = {"analysis": result}
        else:
            output[player_name] = {"analysis": "No analysis available."}

    print(json.dumps(output))
    return output

# --- Run the Analysis ---

if __name__ == "__main__":
    asyncio.run(main())