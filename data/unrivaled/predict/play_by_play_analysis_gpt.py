import firebase_admin
from firebase_admin import credentials, firestore
import json
import aiohttp
import asyncio
import re
import sys
import openai
from math import comb
from collections import defaultdict

# --- Celery Configuration ---
from celery import Celery

celery_app = Celery('play_by_play_analysis_gpt',
                    broker='redis://localhost:6379/0',
                    backend='redis://localhost:6379/0')

cred = credentials.Certificate("secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client(database_id="unrivaled-db")

# MySQL Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "unrivaled",  # Replace with your database name
    "user": "root",          # Replace with your MySQL username
    "password": "Joynera4919"       # Replace with your MySQL password
}

# Load API key from secrets file
with open("secrets/API_KEYS.json", "r") as file:
    api_keys = json.load(file)

# GPT-4 API Settings (replacing GPT)
GPT_API_KEY = api_keys["GPT_API_KEY"]
GPT_MODEL = "gpt-4o-mini"
GPT_API_URL = "https://api.openai.com/v1/chat/completions"

DEEPSEEK_API_KEY = api_keys["DEEPSEEK_API_KEY"]
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

def get_player_teams():
    player_teams = {}
    player_docs = db.collection("players").stream()

    for doc in player_docs:
        player_data = doc.to_dict()
        player_teams[doc.id.lower()] = player_data["team"]  # Use player_name as ID

    return player_teams

def fetch_injury_reports():
    """
    Fetch injury reports from the database or JSON file.
    """
    try:
        # Example: Load from a JSON file
        with open("/Users/ajoyner/unrivaled_ai_sportsbet/data/unrivaled/injury_reports.json", "r") as f:
            injury_data = json.load(f)
        return injury_data.get("injury_reports", [])
    except Exception as e:
        print(f"Error fetching injury reports: {e}", file=sys.stderr)
        return []


def fetch_plays_from_db(game_id, player_name):
    plays_ref = db.collection("games").document(game_id).collection("play_by_play").stream()
    plays = [doc.to_dict() for doc in plays_ref if doc.to_dict().get("player", "").lower() == player_name.lower()]
    return plays

def get_game_ids_for_player(player_name):
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT DISTINCT game_id FROM play_by_play
                WHERE LOWER(player) = LOWER(%s)
            """
            cursor.execute(query, (player_name,))
            game_ids = [row["game_id"] for row in cursor.fetchall()]
            return game_ids
    except Error as e:
        print(f"Error fetching game IDs from MySQL: {e}", file=sys.stderr)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def player_scoring_breakdown(plays):
    scoring_data = {
        "2pt_made": 0,
        "2pt_missed": 0,
        "3pt_made": 0,
        "3pt_missed": 0,
        "free_throws_made": 0,
        "free_throws_missed": 0
    }
    for play in plays:
        description = play["play_description"]
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
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT ast, offensive_rebounds, defensive_rebounds 
                FROM game_stats
                WHERE game_id = %s AND LOWER(player_name) = LOWER(%s)
            """
            cursor.execute(query, (game_id, player_name))
            result = cursor.fetchone()
            if result:
                return {
                    "assists": result["ast"],
                    "offensive_rebounds": result["offensive_rebounds"],
                    "defensive_rebounds": result["defensive_rebounds"]
                }
            else:
                return {"assists": 0, "offensive_rebounds": 0, "defensive_rebounds": 0}
    except mysql.connector.Error as e:
        print(f"Error fetching assists and rebounds: {e}", file=sys.stderr)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return {"assists": 0, "offensive_rebounds": 0, "defensive_rebounds": 0}

def turnover_foul_analysis(plays):
    turnover_foul_data = {"turnovers": 0, "fouls": 0}
    for play in plays:
        description = play["play_description"]
        if "turnover" in description:
            turnover_foul_data["turnovers"] += 1
        elif "foul" in description:
            turnover_foul_data["fouls"] += 1
    return turnover_foul_data

def teammate_interaction_analysis(plays, player_name, player_teams):
    interaction_data = defaultdict(int)
    previous_play = None
    for play in plays:
        description = play["play_description"]
        player = play.get("player")
        if player is None:
            continue
        if "assist" in description and previous_play and previous_play.get("player"):
            teammate = previous_play.get("player")
            if teammate is None:
                continue
            if (teammate.lower() in player_teams and 
                player.lower() in player_teams and 
                player.lower() == player_name.lower() and 
                player_name.lower() != teammate.lower()):
                if player_teams[teammate.lower()] == player_teams[player.lower()]:
                    interaction_data[teammate.lower()] += 1
        previous_play = play if player else None  
    return dict(interaction_data)

def get_player_averages(player_name):
    player_doc = db.collection("players").document(player_name).get()
    return player_doc.to_dict() if player_doc.exists else None


def get_game_stats(game_id, player_name):
    game_stats_ref = db.collection("players").document(player_name).collection("games").document(game_id).get()
    return game_stats_ref.to_dict() if game_stats_ref.exists else None


def get_opposing_team_stats(game_id, player_team):
    game_doc = db.collection("games").document(game_id).get()
    if game_doc.exists:
        game_data = game_doc.to_dict()
        opposing_team = game_data["away_team"] if game_data["home_team"] == player_team else game_data["home_team"]
        opposing_team_stats = db.collection("teams").document(opposing_team).get()
        return opposing_team_stats.to_dict() if opposing_team_stats.exists else None
    return None


async def analyze_game_flow(session, player_name, game_id, max_retries=3):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    plays = fetch_plays_from_db(game_id, player_name.lower())
    if not plays:
        print(f"No play-by-play data found for {player_name} in Game {game_id}.", file=sys.stderr)
        return None
    data = {
        "model": "deepseek-chat",
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
                print(f"Response status for game flow analysis of {player_name} in Game {game_id}: {response.status} (Attempt {retries + 1})", file=sys.stderr)
                if response.status == 200:
                    result = await response.json()
                    if result and "choices" in result and len(result["choices"]) > 0:
                        analysis = result["choices"][0]["message"]["content"]
                        return analysis
                    else:
                        print(f"Invalid response from DeepSeek API for game flow analysis of {player_name} in Game {game_id}: {result}", file=sys.stderr)
                else:
                    response_text = await response.text()
                    print(f"Failed to get analysis from DeepSeek API for game flow analysis of {player_name} in Game {game_id}. Status: {response.status}, Response: {response_text}", file=sys.stderr)
        except Exception as e:
            print(f"Error during DeepSeek API request for game flow analysis of {player_name} in Game {game_id}: {e}", file=sys.stderr)
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)
    print(f"Max retries ({max_retries}) exceeded for game flow analysis of {player_name} in Game {game_id}. Returning None.", file=sys.stderr)
    return None

async def get_DEEPSEEK_analysis(session, player_name, game_id, scoring_breakdown, assist_data, rebound_data, turnover_foul_data, interaction_data, player_averages, game_stats, opposing_team_stats, max_retries=3):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the following basketball stats for {player_name} in game {game_id} against {opposing_team_stats['opposing_team']}:\n\n"
                    f"Scoring Breakdown: {scoring_breakdown}\n"
                    f"Assist Data: {assist_data}\n"
                    f"Rebound Data: {rebound_data}\n"
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
                print(f"Game {game_id}: {'OK' if response.status == 200 else 'BAD'} (Attempt {retries + 1})", file=sys.stderr)
                if response.status == 200:
                    result = await response.json()
                    if result and "choices" in result and len(result["choices"]) > 0:
                        analysis = result["choices"][0]["message"]["content"]
                        return analysis
                    else:
                        print(f"Invalid response from DeepSeek API for Game {game_id}: {result}", file=sys.stderr)
                else:
                    response_text = await response.text()
                    print(f"Failed to get analysis from DeepSeek API for Game {game_id}. Status: {response.status}, Response: {response_text}", file=sys.stderr)
        except Exception as e:
            print(f"Error during DeepSeek API request for Game {game_id}: {e}", file=sys.stderr)
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)
    print(f"Max retries ({max_retries}) exceeded for Game {game_id}. Returning None.", file=sys.stderr)
    return None

async def calculate_final_confidence_level(session, player_name, player_team, game_analyses, player_prop, opposing_team, game_flow_analyses=None, injury_reports=None, max_retries=3):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # Prepare the injury report context
    injury_context = ""
    if injury_reports:
        for report in injury_reports:
            if report["team"].lower() == player_team.lower() or report["team"].lower() == opposing_team.lower():
                injury_context += f"{report['player']} ({report['team']}) is {report['status']} with {report['injury']}.\n"
                print(injury_context)

    points_probability = estimate_points_probability(player_name, player_prop)

    # Define weights for each factor
    weights = {
        "recent_performance": 0.25,  # Reduced slightly
        "opposing_team_defense": 0.30,  # Increased (defense is critical)
        "role_and_teammate_interactions": 0.15,  # Reduced
        "injuries_and_absences": 0.20,  # Increased (injuries can drastically impact performance)
        "consistency_and_clutch_performance": 0.10  # Kept low
    }

    # Ask the model to provide a score (0-100) for each factor
    data = {
        "model": "deepseek-chat",
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
                    f"Probability of Scoring at Least {player_prop} Points: {points_probability:.2f}\n\n"
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
                print(f"Response status for final analysis of {player_name}: {response.status} (Attempt {retries + 1})", file=sys.stderr)
                if response.status == 200:
                    result = await response.json()
                    if result and "choices" in result and len(result["choices"]) > 0:
                        conclusion = result["choices"][0]["message"]["content"]
                        
                        # Extract scores for each factor
                        scores = {}
                        for line in conclusion.split("\n"):
                            if "Recent Performance Trends:" in line:
                                scores["recent_performance"] = int(line.split(":")[1].strip())
                            elif "Opposing Team Defense:" in line:
                                scores["opposing_team_defense"] = int(line.split(":")[1].strip())
                            elif "Role and Teammate Interactions:" in line:
                                scores["role_and_teammate_interactions"] = int(line.split(":")[1].strip())
                            elif "Injuries and Absences:" in line:
                                scores["injuries_and_absences"] = int(line.split(":")[1].strip())
                            elif "Consistency and Clutch Performance:" in line:
                                scores["consistency_and_clutch_performance"] = int(line.split(":")[1].strip())
                        
                        # Calculate weighted confidence level
                        weighted_confidence = (
                            scores["recent_performance"] * weights["recent_performance"] +
                            scores["opposing_team_defense"] * weights["opposing_team_defense"] +
                            scores["role_and_teammate_interactions"] * weights["role_and_teammate_interactions"] +
                            scores["injuries_and_absences"] * weights["injuries_and_absences"] +
                            scores["consistency_and_clutch_performance"] * weights["consistency_and_clutch_performance"]
                        )
                        
                        # Scale the weighted confidence to the 0-100 range
                        confidence_level = int((weighted_confidence / 100) * 100)
                        
                        # Ensure confidence level is within bounds
                        confidence_level = max(0, min(100, confidence_level))
                        
                        # Extract and parse the reason into a dictionary.
                        reason_text = ""
                        if "Reason:" in conclusion:
                            reason_text = conclusion.split("Reason:")[-1].strip()
                        else:
                            reason_text = "No reason provided."
                        # Use regex to split reason_text at occurrences of a number followed by a period and a space.
                        parts = re.split(r'(?=\d+\.\s)', reason_text)
                        reason_dict = {}
                        for part in parts:
                            match = re.match(r'(\d+)\.\s*(.*)', part)
                            if match:
                                key = match.group(1)
                                text = match.group(2).strip()
                                reason_dict[key] = text
                        # If no valid parts were found, fall back to the raw reason_text.
                        if not reason_dict:
                            reason_dict = reason_text
                        return confidence_level, reason_dict
                    else:
                        print(f"Invalid response from DeepSeek API for final analysis of {player_name}: {result}", file=sys.stderr)
                else:
                    response_text = await response.text()
                    print(f"Failed to get analysis from DeepSeek API for final analysis of {player_name}. Status: {response.status}, Response: {response_text}", file=sys.stderr)
        except Exception as e:
            print(f"Error during DeepSeek API request for final analysis of {player_name}: {e}", file=sys.stderr)
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)
    print(f"Max retries ({max_retries}) exceeded for final analysis of {player_name}. Returning default values.", file=sys.stderr)
    return 50, {"5": "API request failed after multiple retries."}

async def analyze_player_with_semaphore(semaphore, player, player_teams):
    async with semaphore:
        return await analyze_player(player, player_teams)

# Add this function to handle database operations for analysis results
def save_analysis_results(player_name, confidence_level, reason):
    try:
        reason_1 = reason.get("1", "")
        reason_2 = reason.get("2", "")
        reason_3 = reason.get("3", "")
        reason_4 = reason.get("4", "")
        final_conclusion = reason.get("5", "")
        # Create a new connection for each call
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor()
            # Delete existing rows for the player
            delete_query = "DELETE FROM analysis_results WHERE player_name = %s"
            cursor.execute(delete_query, (player_name,))
            # Insert new analysis results
            insert_query = """
                INSERT INTO analysis_results (player_name, confidence_level, reason_1, reason_2, reason_3, reason_4, final_conclusion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (player_name, confidence_level, reason_1, reason_2, reason_3, reason_4, final_conclusion))
            connection.commit()
            print(f"Saved analysis results for {player_name} to database.", file=sys.stderr)
    except mysql.connector.Error as e:
        print(f"Error saving analysis results to database for {player_name}: {e}", file=sys.stderr)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Modify the analyze_player function to save results to the database
async def analyze_player(player, player_teams):
    player_name = player["Player Data"]["name"]
    player_team = player_teams.get(player_name.lower())
    if not player_team:
        print(f"No team found for player: {player_name}", file=sys.stderr)
        return None
    print(f"Checking plays for {player_name}...", file=sys.stderr)
    game_ids = get_game_ids_for_player(player_name.lower())
    if not game_ids:
        print(f"No games found for player: {player_name}", file=sys.stderr)
        return None
    game_analyses = []
    game_flow_analyses = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        game_flow_tasks = []
        for game_id in game_ids:
            print(f"\nAnalyzing Game {game_id} for {player_name}...", file=sys.stderr)
            plays = fetch_plays_from_db(game_id, player_name.lower())
            if not plays:
                print(f"No plays found for player {player_name} in Game {game_id}", file=sys.stderr)
                continue
            scoring_breakdown = player_scoring_breakdown(plays)
            game_stats = get_assists_rebounds(game_id, player_name.lower())
            assist_data = {"total_assists": game_stats["assists"]}
            rebound_data = {
                "offensive_rebounds": game_stats["offensive_rebounds"],
                "defensive_rebounds": game_stats["defensive_rebounds"]
            }
            turnover_foul_data = turnover_foul_analysis(plays)
            interaction_data = teammate_interaction_analysis(plays, player_name.lower(), player_teams)
            player_averages = get_player_averages(player_name.lower())
            game_stats = get_game_stats(game_id, player_name.lower())
            opposing_team_stats = get_opposing_team_stats(game_id, player_team)
            task = get_DEEPSEEK_analysis(session, player_name, game_id, scoring_breakdown, assist_data, rebound_data, turnover_foul_data, interaction_data, player_averages, game_stats, opposing_team_stats)
            tasks.append(task)
            game_flow_task = analyze_game_flow(session, player_name, game_id)
            game_flow_tasks.append(game_flow_task)
        game_analyses = await asyncio.gather(*tasks)
        game_flow_analyses = await asyncio.gather(*game_flow_tasks)
    game_analyses = [analysis for analysis in game_analyses if analysis is not None]
    game_flow_analyses = [analysis for analysis in game_flow_analyses if analysis is not None]
    player_prop = player["Projection Data"]["line_score"]
    opposing_team = player["Projection Data"]["description"]

    # Fetch injury reports
    injury_reports = fetch_injury_reports()

    async with aiohttp.ClientSession() as session:
        confidence_level, reason = await calculate_final_confidence_level(session, player_name, player_team, game_analyses, player_prop, opposing_team, game_flow_analyses, injury_reports)
    print(f"\nConfidence Level for {player_name} on {player_prop} points: {confidence_level}", file=sys.stderr)
    print(f"Reason: {reason}", file=sys.stderr)

    return confidence_level, reason

def binomial_probability(n, k, p):
    """
    Calculate the binomial probability P(X = k) using the formula:
    P(X = k) = C(n, k) * p^k * (1-p)^(n-k)
    """
    if n < 0 or k < 0 or k > n or p < 0 or p > 1:
        return 0  # Return 0 for invalid inputs
    try:
        return comb(n, k) * (p ** k) * ((1 - p) ** (n - k))
    except Exception as e:
        print(f"Error calculating binomial probability: {e}", file=sys.stderr)
        return 0
    
def estimate_points_probability(player_name, player_prop) -> float:
    """
    Estimate the probability of a player scoring at least the projected points (player_prop)
    using binomial probability for 2-pointers, 3-pointers, and free throws.
    """
    shooting_probs = calculate_shooting_probabilities(player_name)
    if not shooting_probs:
        return 0.5  # Default probability if no data is available

    # Get average shot attempts per game
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT 
                    AVG(fg_a) AS avg_fg_attempted,
                    AVG(three_pt_a) AS avg_3pt_attempted,
                    AVG(ft_a) AS avg_ft_attempted
                FROM game_stats
                WHERE LOWER(player_name) = LOWER(%s)
            """
            cursor.execute(query, (player_name,))
            result = cursor.fetchone()
            if result:
                avg_fg_attempted = result["avg_fg_attempted"] or 0
                avg_3pt_attempted = result["avg_3pt_attempted"] or 0
                avg_ft_attempted = result["avg_ft_attempted"] or 0
            else:
                return 0.5  # Default probability if no data is available
    except mysql.connector.Error as e:
        print(f"Error fetching average shot attempts for {player_name}: {e}", file=sys.stderr)
        return 0.5
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

    # Ensure average attempts are valid
    avg_fg_attempted = max(0, int(avg_fg_attempted))
    avg_3pt_attempted = max(0, int(avg_3pt_attempted))
    avg_ft_attempted = max(0, int(avg_ft_attempted))

    # Calculate probabilities for different scoring scenarios
    total_points = 0
    for k_2pt in range(avg_fg_attempted + 1):
        for k_3pt in range(avg_3pt_attempted + 1):
            for k_ft in range(avg_ft_attempted + 1):
                points = (2 * k_2pt) + (3 * k_3pt) + (1 * k_ft)
                if points >= player_prop:
                    print(avg_fg_attempted, k_2pt, shooting_probs)
                    prob_2pt = binomial_probability(avg_fg_attempted, k_2pt, shooting_probs["p_2pt"])
                    prob_3pt = binomial_probability(avg_3pt_attempted, k_3pt, shooting_probs["p_3pt"])
                    prob_ft = binomial_probability(avg_ft_attempted, k_ft, shooting_probs["p_ft"])
                    total_points += prob_2pt * prob_3pt * prob_ft
    return total_points

def calculate_shooting_probabilities(player_name):
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT 
                    SUM(fg_m) AS total_fg_made,
                    SUM(fg_a) AS total_fg_attempted,
                    SUM(three_pt_m) AS total_3pt_made,
                    SUM(three_pt_a) AS total_3pt_attempted,
                    SUM(ft_m) AS total_ft_made,
                    SUM(ft_a) AS total_ft_attempted
                FROM game_stats
                WHERE LOWER(player_name) = LOWER(%s)
            """
            cursor.execute(query, (player_name,))
            result = cursor.fetchone()
            if result:
                # Handle NULL values by defaulting to 0
                total_fg_made = result["total_fg_made"] or 0
                total_fg_attempted = result["total_fg_attempted"] or 0
                total_3pt_made = result["total_3pt_made"] or 0
                total_3pt_attempted = result["total_3pt_attempted"] or 0
                total_ft_made = result["total_ft_made"] or 0
                total_ft_attempted = result["total_ft_attempted"] or 0

                # Calculate shooting probabilities
                p_2pt = total_fg_made / total_fg_attempted if total_fg_attempted > 0 else 0
                p_3pt = total_3pt_made / total_3pt_attempted if total_3pt_attempted > 0 else 0
                p_ft = total_ft_made / total_ft_attempted if total_ft_attempted > 0 else 0

                return {
                    "p_2pt": p_2pt,
                    "p_3pt": p_3pt,
                    "p_ft": p_ft
                }
            else:
                return None
    except mysql.connector.Error as e:
        print(f"Error fetching shooting probabilities for {player_name}: {e}", file=sys.stderr)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

async def main():
    with open("/Users/ajoyner/unrivaled_ai_sportsbet/data/unrivaled/unr_enriched_players.json", "r") as f:
        enriched_data = json.load(f)
    player_teams = get_player_teams()
    semaphore = asyncio.Semaphore(4)  # Increased concurrency
    tasks = [analyze_player_with_semaphore(semaphore, player, player_teams) for player in enriched_data]
    results = await asyncio.gather(*tasks)
    output = {}
    for player, result in zip(enriched_data, results):
        player_name = player["Player Data"]["name"]
        if result:
            confidence_level, reason = result
            # save_analysis_results(player_name, confidence_level, reason)
            output[player_name] = {"confidence": confidence_level, "reason": reason}
        else:
            output[player_name] = {"confidence": 75, "reason": "No analysis available."}
    # Print only the final JSON result to stdout.
    for player_name, analysis in output.items():
        save_analysis_results(player_name, analysis["confidence"], analysis["reason"])

    print(json.dumps(output))
    return output

@celery_app.task
def run_analysis_task():
    result = asyncio.run(main())
    return result

if __name__ == "__main__":
    asyncio.run(main())
