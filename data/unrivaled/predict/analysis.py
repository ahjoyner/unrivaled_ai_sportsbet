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
    player_name = player_name.replace("_", " ")
    print(f"Fetching plays for player: {player_name}")

    try:
        # Query the play_by_play subcollection for the game
        plays_ref = db.collection("games").document(game_id).collection("play_by_play").stream()

        # Store all plays in a list
        all_plays = [doc for doc in plays_ref]

        # Print all plays for debugging

        for play in all_plays:
            play_data = play.to_dict()
            if play_data.get("player", "").lower().strip() == player_name.lower().strip():
                print(f"Exists: {play_data.get("player", "")}")
            

        # Filter plays for the specific player (case-insensitive and trimmed)
        plays = [
            play.to_dict() for play in all_plays 
            if play.to_dict().get("player", "").lower().strip() == player_name.lower().strip()
        ]

        # Print the filtered plays as a formatted JSON string
        return plays
    except Exception as e:
        print(f"Error fetching plays for player {player_name} in game {game_id}: {e}", file=sys.stderr)
        return []

def get_game_ids_for_player(player_name):
    """
    Fetch game IDs for a specific player from the `players/player_name/games/` subcollection.
    """
    try:
        games_ref = db.collection("players").document(player_name).collection("games").stream()
        game_ids = [doc.id for doc in games_ref]
        return game_ids
    except Exception as e:
        print(f"Error fetching game IDs for player {player_name}: {e}", file=sys.stderr)
        return []

def player_scoring_breakdown(plays):
    """
    Analyze scoring breakdown from play-by-play data.
    """
    scoring_data = {
        "2pt_made": 0,
        "2pt_missed": 0,
        "3pt_made": 0,
        "3pt_missed": 0,
        "free_throws_made": 0,
        "free_throws_missed": 0
    }
    for play in plays:
        description = play.get("play_description", "").lower()
        if "makes two point shot" in description:
            scoring_data["2pt_made"] += 1
        elif "misses two point shot" in description:
            scoring_data["2pt_missed"] += 1
        elif "makes three point shot" in description:
            scoring_data["3pt_made"] += 1
        elif "misses three point shot" in description:
            scoring_data["3pt_missed"] += 1
        elif "makes free throw" in description:
            scoring_data["free_throws_made"] += 1
        elif "misses free throw" in description:
            scoring_data["free_throws_missed"] += 1
    return scoring_data

def get_assists_rebounds(game_id, player_name):
    """
    Fetch assist and rebound stats for a player in a specific game.
    """
    try:
        game_stats_ref = db.collection("players").document(player_name).collection("games").document(game_id).get()
        if game_stats_ref.exists:
            game_stats = game_stats_ref.to_dict()
            return {
                "assists": game_stats.get("ast", 0),
                "offensive_rebounds": game_stats.get("offensive_rebounds", 0),
                "defensive_rebounds": game_stats.get("defensive_rebounds", 0)
            }
        return {"assists": 0, "offensive_rebounds": 0, "defensive_rebounds": 0}
    except Exception as e:
        print(f"Error fetching assists and rebounds for player {player_name} in game {game_id}: {e}", file=sys.stderr)
        return {"assists": 0, "offensive_rebounds": 0, "defensive_rebounds": 0}

def turnover_foul_analysis(plays):
    """
    Analyze turnovers and fouls from play-by-play data.
    """
    turnover_foul_data = {"turnovers": 0, "fouls": 0}
    for play in plays:
        description = play.get("play_description", "").lower()
        if "turnover" in description:
            turnover_foul_data["turnovers"] += 1
        elif "foul" in description:
            turnover_foul_data["fouls"] += 1
    return turnover_foul_data

def teammate_interaction_analysis(plays, player_name, player_teams):
    """
    Analyze teammate interactions (e.g., assists) from play-by-play data.
    """
    interaction_data = defaultdict(int)
    previous_play = None
    for play in plays:
        description = play.get("play_description", "").lower()
        player = play.get("player", "").lower()
        if "assist" in description and previous_play and previous_play.get("player"):
            teammate = previous_play.get("player").lower()
            if teammate in player_teams and player == player_name.lower() and player != teammate:
                if player_teams[teammate] == player_teams[player]:
                    interaction_data[teammate] += 1
        previous_play = play
    return dict(interaction_data)

def get_opposing_team_stats(game_id, player_team):
    """
    Fetch stats for the opposing team in a specific game.
    """
    try:
        game_doc = db.collection("games").document(game_id).get()
        if game_doc.exists:
            game_data = game_doc.to_dict()
            opposing_team = game_data["away_team"] if game_data["home_team"] == player_team else game_data["home_team"]
            opposing_team_stats = db.collection("teams").document(opposing_team).get()
            if opposing_team_stats.exists:
                return {"opposing_team": opposing_team, **opposing_team_stats.to_dict()}  # Include team name and stats
            else:
                return {"opposing_team": opposing_team}  # Return at least the team name if stats are missing
        return {"opposing_team": "Unknown"}  # Default if game data is missing
    except Exception as e:
        print(f"Error fetching opposing team stats for game {game_id}: {e}", file=sys.stderr)
        return {"opposing_team": "Unknown"}  # Default if an error occurs

# --- DeepSeek API Functions ---

async def analyze_game_flow(session, player_name, game_id, max_retries=3):
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

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the following play-by-play data for {player_name} in Game {game_id}:\n\n"
                    f"Play-by-Play Data: {plays}\n\n"
                    "Provide an analysis of the player's form in this game, including:\n"
                    "1. How the player performed in different quarters (e.g., strong start, slow finish).\n"
                    "2. The player's consistency throughout the game.\n"
                    "3. The player's impact on the flow of the game (e.g., clutch plays, momentum shifts).\n\n"
                    "Format your response as:\n"
                    "Game Flow Analysis:\n"
                    "1. <quarter performance>\n"
                    "2. <consistency>\n"
                    "3. <impact on game flow>"
                )
            }
        ]
    }

    retries = 0
    while retries < max_retries:
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
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)
    print(f"Max retries ({max_retries}) exceeded for game flow analysis of {player_name} in Game {game_id}.", file=sys.stderr)
    return None

async def get_deepseek_analysis(session, player_name, game_id, scoring_breakdown, assist_rebound_data, turnover_foul_data, interaction_data, player_averages, game_stats, opposing_team_stats, max_retries=3):
    """
    Get detailed analysis of a player's performance in a game using DeepSeek API.
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # Ensure opposing_team_stats has at least the team name
    opposing_team = opposing_team_stats.get("opposing_team", "Unknown")

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the following basketball stats for {player_name} in game {game_id} against {opposing_team}:\n\n"
                    f"Scoring Breakdown: {scoring_breakdown}\n"
                    f"Assist/Rebound Data: {assist_rebound_data}\n"
                    f"Turnover and Foul Data: {turnover_foul_data}\n"
                    f"Teammate Interaction Data: {interaction_data}\n\n"
                    f"Player Averages (Season): {player_averages}\n"
                    f"Game Stats: {game_stats}\n"
                    f"Opposing Team Stats: {opposing_team_stats}\n\n"
                    "Provide a detailed analysis of the player's performance in this game."
                )
            }
        ]
    }

    retries = 0
    while retries < max_retries:
        try:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result and "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"]
                else:
                    print(f"Failed to get analysis from DeepSeek API for Game {game_id}. Status: {response.status}", file=sys.stderr)
        except Exception as e:
            print(f"Error during DeepSeek API request for Game {game_id}: {e}", file=sys.stderr)
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)
    print(f"Max retries ({max_retries}) exceeded for Game {game_id}.", file=sys.stderr)
    return None

def get_player_averages(player_name):
    """
    Fetch the player's average statistics for the season.
    """
    try:
        player_ref = db.collection("players").document(player_name).get()
        if player_ref.exists:
            player_data = player_ref.to_dict()
            # Assuming averages are stored in a field called "season_averages"
            return player_data.get("season_averages", {})
        return {}
    except Exception as e:
        print(f"Error fetching player averages for {player_name}: {e}", file=sys.stderr)
        return {}
    
def get_game_stats(game_id, player_name):
    """
    Fetch the player's statistics for a specific game.
    """
    try:
        game_stats_ref = db.collection("players").document(player_name).collection("games").document(game_id).get()
        if game_stats_ref.exists:
            game_stats = game_stats_ref.to_dict()
            return game_stats
        return {}
    except Exception as e:
        print(f"Error fetching game stats for player {player_name} in game {game_id}: {e}", file=sys.stderr)
        return {}
    
def save_analysis_results(player_name, confidence_level, reason):
    """
    Save the analysis results directly to the player's `analysis_results` collection in Firestore.
    This will overwrite any existing analysis results for the player.
    """
    try:
        analysis_data = {
            "confidence_level": confidence_level,
            "reason": reason,
            "timestamp": firestore.SERVER_TIMESTAMP  # Timestamp for when analysis was performed
        }
        # Save directly to the player's analysis_results collection
        db.collection("players").document(player_name).collection("analysis_results").document("latest").set(analysis_data)
        print(f"✅ Analysis results saved for {player_name}")
    except Exception as e:
        print(f"❌ Error saving analysis results for {player_name}: {e}", file=sys.stderr)

# --- Main Analysis Flow ---

async def analyze_player(player, player_teams):
    """
    Analyze a player's performance across all their games.
    """
    player_name = player["player_data"]["name"].replace(" ", "_")  # Ensure lowercase for matching
    player_team = player["player_data"]["team"]  # Get team from player_data
    if not player_team:
        print(f"No team found for player: {player_name}", file=sys.stderr)
        return None

    game_ids = get_game_ids_for_player(player_name)
    if not game_ids:
        print(f"No games found for player: {player_name}", file=sys.stderr)
        return None

    game_analyses = []
    game_flow_analyses = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        game_flow_tasks = []
        for game_id in game_ids:
            plays = fetch_plays_for_player(game_id, player_name)
            if not plays:
                print(f"No plays found for player {player_name} in Game {game_id}", file=sys.stderr)
                continue

            scoring_breakdown = player_scoring_breakdown(plays)
            assist_rebound_data = get_assists_rebounds(game_id, player_name)
            turnover_foul_data = turnover_foul_analysis(plays)
            interaction_data = teammate_interaction_analysis(plays, player_name, player_teams)
            player_averages = get_player_averages(player_name)
            game_stats = get_game_stats(game_id, player_name)
            opposing_team_stats = get_opposing_team_stats(game_id, player_team)

            task = get_deepseek_analysis(
                session, player_name, game_id, scoring_breakdown, assist_rebound_data,
                turnover_foul_data, interaction_data, player_averages, game_stats, opposing_team_stats
            )
            tasks.append(task)
            game_flow_task = analyze_game_flow(session, player_name, game_id)
            game_flow_tasks.append(game_flow_task)

        game_analyses = await asyncio.gather(*tasks)
        game_flow_analyses = await asyncio.gather(*game_flow_tasks)

    game_analyses = [analysis for analysis in game_analyses if analysis is not None]
    game_flow_analyses = [analysis for analysis in game_flow_analyses if analysis is not None]

    player_prop = player["projection_data"]["line_score"]
    opposing_team = player["projection_data"]["description"]
    injury_reports = fetch_injury_reports()

    async with aiohttp.ClientSession() as session:
        confidence_level, reason = await calculate_final_confidence_level(session, player_name, player_team, game_analyses, player_prop, opposing_team, game_flow_analyses, injury_reports)
    print(f"\nConfidence Level for {player_name} on {player_prop} points: {confidence_level}", file=sys.stderr)
    print(f"Reason: {reason}", file=sys.stderr)

    # Save the analysis results to Firestore
    save_analysis_results(player_name, confidence_level, reason)

    return confidence_level, reason

# --- Final Confidence Level Calculation ---

async def calculate_final_confidence_level(session, player_name, player_team, game_analyses, player_prop, opposing_team, game_flow_analyses=None, injury_reports=None, max_retries=3):
    """
    Calculate the final confidence level for a player's performance.
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
                    f"Analyze the following game analyses for {player_name}:\n\n"
                    f"Game Analyses: {game_analyses}\n\n"
                    f"Player Prop: {player_prop} points\n\n"
                    f"Opposing Team: {opposing_team}\n\n"
                    f"Game Flow Analyses: {game_flow_analyses}\n\n"
                    f"Injury Reports:\n{injury_context}\n\n"
                    "Provide a score (0-100) for each of the following factors:\n"
                    "1. Recent Performance Trends (e.g., scoring, assists, rebounds).\n"
                    "2. Opposing Team's Defensive Strength and Matchup.\n"
                    "3. Role and Teammate Interactions.\n"
                    "4. Injuries and Absences.\n"
                    "5. Consistency and Clutch Performance.\n\n"
                    "Based on these scores, calculate a weighted confidence level from 0-100 for whether the player will go over or under the points prop. "
                    "A confidence level of 0 means strong confidence in the under, 100 means strong confidence in the over. "
                    "If you personally think the player will go over, confidence should be between 75 and 100. Otherwise, between 0 and 74.\n\n"
                    "Format your response as:\n"
                    "Scores:\n"
                    "1. Recent Performance Trends: <score>\n"
                    "2. Opposing Team Defense: <score>\n"
                    "3. Role and Teammate Interactions: <score>\n"
                    "4. Injuries and Absences: <score>\n"
                    "5. Consistency and Clutch Performance: <score>\n\n"
                    "Confidence Level: <number>\n"
                    "Reason:\n"
                    "1. <performance against opposing team:>\n"
                    "2. <scoring trends:>\n"
                    "3. <role and teammate interactions:>\n"
                    "4. <game flow analysis:>\n"
                    "5. <final reason for confidence level:>"
                )
            }
        ]
    }

    retries = 0
    while retries < max_retries:
        try:
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result and "choices" in result and len(result["choices"]) > 0:
                        conclusion = result["choices"][0]["message"]["content"]
                        # Extract scores and confidence level from the conclusion
                        # (Implementation omitted for brevity)
                        return 75, {"reason": "Sample reason"}  # Placeholder
                else:
                    print(f"Failed to get analysis from DeepSeek API for final analysis of {player_name}. Status: {response.status}", file=sys.stderr)
        except Exception as e:
            print(f"Error during DeepSeek API request for final analysis of {player_name}: {e}", file=sys.stderr)
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)
    print(f"Max retries ({max_retries}) exceeded for final analysis of {player_name}.", file=sys.stderr)
    return 50, {"reason": "API request failed after multiple retries."}

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
            "player_data": {
                "name": player_data.get("player_data", {}).get("display_name", ""),
                "team": player_data.get("player_data", {}).get("team", ""),
                "position": player_data.get("player_data", {}).get("position", ""),
                "league": player_data.get("player_data", {}).get("league", ""),
                "image_url": player_data.get("player_data", {}).get("image_url", ""),
                "created_at": player_data.get("player_data", {}).get("created_at", ""),
                "updated_at": player_data.get("player_data", {}).get("updated_at", ""),
                "sportsradar_id": player_data.get("player_data", {}).get("sportsradar_id", ""),
                "oddsjam_id": player_data.get("player_data", {}).get("oddsjam_id", ""),
                "fantasy_data_id": player_data.get("player_data", {}).get("fantasy_data_id", ""),
                "market": player_data.get("player_data", {}).get("market", ""),
                "league_id": player_data.get("player_data", {}).get("league_id", ""),
                "swish_id": player_data.get("player_data", {}).get("swish_id", ""),
                "team_name": player_data.get("player_data", {}).get("team_name", ""),
                "display_name": player_data.get("player_data", {}).get("display_name", "")
            },
            "projection_data": {
                "line_score": player_data.get("projection_data", {}).get("line_score", 0),
                "description": player_data.get("projection_data", {}).get("description", ""),
                "in_game": player_data.get("projection_data", {}).get("in_game", False),
                "is_live": player_data.get("projection_data", {}).get("is_live", False),
                "flash_sale_line_score": player_data.get("projection_data", {}).get("flash_sale_line_score", None),
                "is_promo": player_data.get("projection_data", {}).get("is_promo", False),
                "projection_type": player_data.get("projection_data", {}).get("projection_type", ""),
                "start_time": player_data.get("projection_data", {}).get("start_time", ""),
                "updated_at": player_data.get("projection_data", {}).get("updated_at", ""),
                "status": player_data.get("projection_data", {}).get("status", ""),
                "rank": player_data.get("projection_data", {}).get("rank", 0),
                "adjusted_odds": player_data.get("projection_data", {}).get("adjusted_odds", False),
                "refundable": player_data.get("projection_data", {}).get("refundable", True),
                "board_time": player_data.get("projection_data", {}).get("board_time", ""),
                "end_time": player_data.get("projection_data", {}).get("end_time", ""),
                "stat_type": player_data.get("projection_data", {}).get("stat_type", ""),
                "custom_image": player_data.get("projection_data", {}).get("custom_image", None),
                "game_id": player_data.get("projection_data", {}).get("game_id", ""),
                "odds_type": player_data.get("projection_data", {}).get("odds_type", ""),
                "hr_20": player_data.get("projection_data", {}).get("hr_20", True),
                "stat_display_name": player_data.get("projection_data", {}).get("stat_display_name", ""),
                "today": player_data.get("projection_data", {}).get("today", True),
                "tv_channel": player_data.get("projection_data", {}).get("tv_channel", None)
            }
        })

    player_teams = get_player_teams()
    semaphore = asyncio.Semaphore(4)  # Limit concurrency
    tasks = [analyze_player(player, player_teams) for player in enriched_data]
    results = await asyncio.gather(*tasks)

    output = {}
    for player, result in zip(enriched_data, results):
        player_name = player["player_data"]["name"]
        if result:
            confidence_level, reason = result
            output[player_name] = {"confidence": confidence_level, "reason": reason}
        else:
            output[player_name] = {"confidence": 75, "reason": "No analysis available."}

    print(json.dumps(output))
    return output

# --- Run the Analysis ---

if __name__ == "__main__":
    asyncio.run(main())