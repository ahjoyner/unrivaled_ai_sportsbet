import mysql.connector
from mysql.connector import Error
import json
import aiohttp
import asyncio
import re
from collections import defaultdict

# MySQL Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "unrivaled",  # Replace with your database name
    "user": "root",          # Replace with your MySQL username
    "password": "Joynera4919"       # Replace with your MySQL password
}

# DeepSeek API Settings
DEEPSEEK_API_KEY = "sk-79d12b9eb2e649d58d95e2e3e24119e1"  # Replace with your DeepSeek API key
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek model name
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"  # DeepSeek API endpoint

# Function to fetch player team mapping from the database
def get_player_teams():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = "SELECT name, team FROM player_stats"
            cursor.execute(query)
            # Convert player names to lowercase for case-insensitive comparison
            player_teams = {row["name"].lower(): row["team"] for row in cursor.fetchall()}
            return player_teams
    except mysql.connector.Error as e:
        print(f"Error fetching player team data: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return {}

# Function to fetch plays from the MySQL database for a specific game
def fetch_plays_from_db(game_id, player_name):
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT * FROM play_by_play
                WHERE game_id = %s AND (LOWER(player) = LOWER(%s) OR play_description LIKE %s)
                ORDER BY time ASC
            """
            cursor.execute(query, (game_id, player_name, "%assist%"))
            plays = cursor.fetchall()
            return plays
    except Error as e:
        print(f"Error fetching data from MySQL: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Function to get all game_ids associated with a player
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
        print(f"Error fetching game IDs from MySQL: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Player Scoring Breakdown
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

# Function to fetch assists and rebounds directly from `game_stats`
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
        print(f"Error fetching assists and rebounds from game_stats: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    
    return {"assists": 0, "offensive_rebounds": 0, "defensive_rebounds": 0}

# Turnover and Foul Analysis
def turnover_foul_analysis(plays):
    turnover_foul_data = {
        "turnovers": 0,
        "fouls": 0
    }
    
    for play in plays:
        description = play["play_description"]
        if "turnover" in description:
            turnover_foul_data["turnovers"] += 1
        elif "foul" in description:
            turnover_foul_data["fouls"] += 1
    
    return turnover_foul_data

# Updated Teammate Interaction Analysis (now with team check)
def teammate_interaction_analysis(plays, player_name, player_teams):
    interaction_data = defaultdict(int)
    previous_play = None  # Track the previous play to check for assists

    for play in plays:
        description = play["play_description"]
        player = play.get("player")  # Use .get() to safely access the "player" field

        # Skip if player is None
        if player is None:
            continue

        # Check if the current play is an assist, previous play exists, and previous player is on the same team
        if "assist" in description and previous_play and previous_play.get("player"):
            teammate = previous_play.get("player")

            # Skip if teammate is None
            if teammate is None:
                continue

            # Validate both players exist in player_teams and are on the same team
            if teammate.lower() in player_teams and player.lower() in player_teams and player.lower() == player_name.lower() and player_name.lower() != teammate.lower():
                if player_teams[teammate.lower()] == player_teams[player.lower()]:  # Same team
                    interaction_data[teammate.lower()] += 1

        # Update previous play only if player is not None
        previous_play = play if player else None  

    return dict(interaction_data)

# Function to fetch player averages from player_stats
def get_player_averages(player_name):
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT pts, ast, reb, turnovers, pf
                FROM player_stats
                WHERE LOWER(name) = LOWER(%s)
            """
            cursor.execute(query, (player_name,))
            result = cursor.fetchone()
            return result if result else None
    except mysql.connector.Error as e:
        print(f"Error fetching player averages: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

# Function to fetch game stats for a specific game from game_stats
def get_game_stats(game_id, player_name):
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            query = """
                SELECT pts, ast, reb, fg_a, fg_m, three_pt_a, three_pt_m, ft_a, ft_m, turnovers, pf
                FROM game_stats
                WHERE game_id = %s AND LOWER(player_name) = LOWER(%s)
            """
            cursor.execute(query, (game_id, player_name))
            result = cursor.fetchone()
            return result if result else None
    except mysql.connector.Error as e:
        print(f"Error fetching game stats: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

def get_opposing_team_stats(game_id, player_team):
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # Fetch the opposing team's name for the given game
            query = """
                SELECT 
                    CASE 
                        WHEN home_team = %s THEN away_team
                        WHEN away_team = %s THEN home_team
                    END AS opposing_team
                FROM games
                WHERE game_id = %s
            """
            cursor.execute(query, (player_team, player_team, game_id))
            result = cursor.fetchone()
            
            if result and result["opposing_team"]:
                opposing_team = result["opposing_team"]
                
                # Fetch the opposing team's stats from team_stats
                query = """
                    SELECT pts, ast, reb, offensive_rebounds, defensive_rebounds, turnovers, pf
                    FROM team_stats
                    WHERE team = %s
                """
                cursor.execute(query, (opposing_team,))
                team_stats = cursor.fetchone()
                
                if team_stats:
                    # Add the opposing team's name to the stats dictionary
                    team_stats["opposing_team"] = opposing_team
                    return team_stats
            
    except mysql.connector.Error as e:
        print(f"Error fetching opposing team stats: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    return None

async def analyze_game_flow(session, player_name, game_id, max_retries=3):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Fetch play-by-play data for the game
    plays = fetch_plays_from_db(game_id, player_name.lower())  # Convert player name to lowercase
    if not plays:
        print(f"No play-by-play data found for {player_name} in Game {game_id}.")
        return None
    
    # Prepare the data to send
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Analyze the following play-by-play data for {player_name} in Game {game_id}:\n\n"
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
            }
        ]
    }
    
    retries = 0
    while retries < max_retries:
        try:
            # Send the request to DeepSeek API
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
                print(f'Response status for game flow analysis of {player_name} in Game {game_id}: {response.status} (Attempt {retries + 1})')  # Debugging
                if response.status == 200:
                    try:
                        result = await response.json()
                        if result and "choices" in result and len(result["choices"]) > 0:
                            analysis = result["choices"][0]["message"]["content"]
                            return analysis
                        else:
                            print(f"Invalid response from DeepSeek API for game flow analysis of {player_name} in Game {game_id}: {result}")
                    except Exception as e:
                        print(f"Error parsing JSON response for game flow analysis of {player_name} in Game {game_id}: {e}")
                else:
                    # Log the response text for debugging
                    response_text = await response.text()
                    print(f"Failed to get analysis from DeepSeek API for game flow analysis of {player_name} in Game {game_id}. Status: {response.status}, Response: {response_text}")
        except Exception as e:
            print(f"Error during DeepSeek API request for game flow analysis of {player_name} in Game {game_id}: {e}")
        
        # Retry after a short delay
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)  # Wait 2 seconds before retrying
    
    # If all retries fail, return None
    print(f"Max retries ({max_retries}) exceeded for game flow analysis of {player_name} in Game {game_id}. Returning None.")
    return None

# Function to send data to DeepSeek and get analysis
async def get_deepseek_analysis(session, player_name, game_id, scoring_breakdown, assist_data, rebound_data, turnover_foul_data, interaction_data, player_averages, game_stats, opposing_team_stats, max_retries=3):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prepare the data to send
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Analyze the following basketball stats for {player_name} in game {game_id} against {opposing_team_stats['opposing_team']}:\n\n"
                           f"Scoring Breakdown: {scoring_breakdown}\n"
                           f"Assist Data: {assist_data}\n"
                           f"Rebound Data: {rebound_data}\n"
                           f"Turnover and Foul Data: {turnover_foul_data}\n"
                           f"Teammate Interaction Data: {interaction_data}\n\n"
                           f"Player Averages (Season): {player_averages}\n"
                           f"Game Stats: {game_stats}\n"
                           f"Opposing Team Stats: {opposing_team_stats}\n\n"
                           "Provide a detailed analysis of the player's performance in this game."
            }
        ]
    }
    
    retries = 0
    while retries < max_retries:
        try:
            # Send the request to DeepSeek API
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
                print(f'Game {game_id}: {"OK" if response.status == 200 else "BAD"} (Attempt {retries + 1})')  # Debugging
                if response.status == 200:
                    try:
                        result = await response.json()
                        if result and "choices" in result and len(result["choices"]) > 0:
                            analysis = result["choices"][0]["message"]["content"]
                            return analysis
                        else:
                            print(f"Invalid response from DeepSeek API for Game {game_id}: {result}")
                    except Exception as e:
                        print(f"Error parsing JSON response for Game {game_id}: {e}")
                else:
                    # Log the response text for debugging
                    response_text = await response.text()
                    print(f"Failed to get analysis from DeepSeek API for Game {game_id}. Status: {response.status}, Response: {response_text}")
        except Exception as e:
            print(f"Error during DeepSeek API request for Game {game_id}: {e}")
        
        # Retry after a short delay
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)  # Wait 2 seconds before retrying
    
    # If all retries fail, return None
    print(f"Max retries ({max_retries}) exceeded for Game {game_id}. Returning None.")
    return None

# Function to calculate final confidence level for the player prop
async def calculate_final_confidence_level(session, player_name, game_analyses, player_prop, opposing_team, game_flow_analyses=None, max_retries=3):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prepare the data to send
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"Analyze the following game analyses for {player_name}:\n\n"
                           f"Game Analyses: {game_analyses}\n\n"
                           f"Player Prop: {player_prop} points\n\n"
                           f"Opposing Team: {opposing_team}\n\n"
                           f"Game Flow Analyses: {game_flow_analyses}\n\n"
                           "Provide a confidence level from 0-150 for whether the player will go over or under the points prop. "
                           "A confidence level of 0 means strong confidence in the under, 150 means strong confidence in the over.\n\n"
                           "Also, provide a detailed reason for why you came to your conclusion based on the following:\n"
                           "1. How the player is expected to perform against the opposing team based on their team averages.\n"
                           "2. Current scoring trends based on their past performance.\n"
                           "3. The role the player plays on her team and her interactions with teammates.\n"
                           "4. The player's form in recent games and how they're expected to perform tonight.\n\n"
                           "Format your response as:\n"
                           "Confidence Level: <number>\n"
                           "Reason:\n"
                           "1. <performance against opposing team>\n"
                           "2. <scoring trends>\n"
                           "3. <role and teammate interactions>\n"
                           "4. <game flow analysis>"
            }
        ]
    }
    
    retries = 0
    while retries < max_retries:
        try:
            # Send the request to DeepSeek API
            async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
                print(f'Response status for final analysis of {player_name}: {response.status} (Attempt {retries + 1})')  # Debugging
                if response.status == 200:
                    try:
                        result = await response.json()
                        if result and "choices" in result and len(result["choices"]) > 0:
                            conclusion = result["choices"][0]["message"]["content"]
                            
                            # Extract confidence level
                            confidence_level_match = re.search(r'Confidence Level:\s*(\d+)', conclusion)
                            if confidence_level_match:
                                confidence_level = int(confidence_level_match.group(1))
                            else:
                                print("Failed to extract confidence level from DeepSeek response.")
                                confidence_level = 75  # Default to neutral if extraction fails
                            
                            # Extract reason
                            reason = ""
                            if "Reason:" in conclusion:
                                reason = conclusion.split("Reason:")[-1].strip()
                            else:
                                reason = "No reason provided."
                            
                            return confidence_level, reason
                        else:
                            print(f"Invalid response from DeepSeek API for final analysis of {player_name}: {result}")
                    except Exception as e:
                        print(f"Error parsing JSON response for final analysis of {player_name}: {e}")
                else:
                    # Log the response text for debugging
                    response_text = await response.text()
                    print(f"Failed to get analysis from DeepSeek API for final analysis of {player_name}. Status: {response.status}, Response: {response_text}")
        except Exception as e:
            print(f"Error during DeepSeek API request for final analysis of {player_name}: {e}")
        
        # Retry after a short delay
        retries += 1
        if retries < max_retries:
            await asyncio.sleep(2)  # Wait 2 seconds before retrying
    
    # If all retries fail, return default values
    print(f"Max retries ({max_retries}) exceeded for final analysis of {player_name}. Returning default values.")
    return 75, "API request failed after multiple retries."

async def analyze_player_with_semaphore(semaphore, player, player_teams):
    async with semaphore:
        return await analyze_player(player, player_teams)

# Function to analyze a single player's games asynchronously
async def analyze_player(player, player_teams):
    player_name = player["Player Data"]["name"]
    player_team = player_teams.get(player_name.lower())  # Convert player name to lowercase
    if not player_team:
        print(f"No team found for player: {player_name}")
        return None
    
    print(f"Checking plays for {player_name}...")
    
    # Step 1: Get all game_ids associated with the player
    game_ids = get_game_ids_for_player(player_name.lower())  # Convert player name to lowercase
    if not game_ids:
        print(f"No games found for player: {player_name}")
        return None
    
    # Step 2: Analyze each game individually and store DeepSeek analyses
    game_analyses = []
    game_flow_analyses = []  # Store game flow analyses
    async with aiohttp.ClientSession() as session:
        tasks = []
        game_flow_tasks = []
        for game_id in game_ids:
            print(f"\nAnalyzing Game {game_id} for {player_name}...")

            # Step 3: Fetch all plays for the player in this game
            plays = fetch_plays_from_db(game_id, player_name.lower())  # Convert player name to lowercase
            if not plays:
                print(f"No plays found for player {player_name} in Game {game_id}")
                continue
            
            # Step 4: Run all analyses for this game
            scoring_breakdown = player_scoring_breakdown(plays)
            game_stats = get_assists_rebounds(game_id, player_name.lower())  # Convert player name to lowercase
            assist_data = {"total_assists": game_stats["assists"]}
            rebound_data = {
                "offensive_rebounds": game_stats["offensive_rebounds"],
                "defensive_rebounds": game_stats["defensive_rebounds"]
            }
            turnover_foul_data = turnover_foul_analysis(plays)
            interaction_data = teammate_interaction_analysis(plays, player_name.lower(), player_teams)  # Convert player name to lowercase
            
            # Step 5: Fetch additional data for comparison
            player_averages = get_player_averages(player_name.lower())  # Convert player name to lowercase
            game_stats = get_game_stats(game_id, player_name.lower())  # Convert player name to lowercase
            opposing_team_stats = get_opposing_team_stats(game_id, player_team)
            
            # Step 6: Send data to DeepSeek for analysis and store the result
            task = get_deepseek_analysis(session, player_name, game_id, scoring_breakdown, assist_data, rebound_data, turnover_foul_data, interaction_data, player_averages, game_stats, opposing_team_stats)
            tasks.append(task)
            
            # Step 7: Analyze game flow for this game
            game_flow_task = analyze_game_flow(session, player_name, game_id)
            game_flow_tasks.append(game_flow_task)
        
        # Wait for all tasks to complete
        game_analyses = await asyncio.gather(*tasks)
        game_flow_analyses = await asyncio.gather(*game_flow_tasks)
    
    # Step 8: Filter out None responses
    game_analyses = [analysis for analysis in game_analyses if analysis is not None]
    game_flow_analyses = [analysis for analysis in game_flow_analyses if analysis is not None]
    
    # Step 9: Get the player prop for the day
    player_prop = player["Projection Data"]["line_score"]
    opposing_team = player["Projection Data"]["description"]
    
    # Step 10: Calculate final confidence level using all game analyses and game flow analyses
    async with aiohttp.ClientSession() as session:
        confidence_level, reason = await calculate_final_confidence_level(session, player_name, game_analyses, player_prop, opposing_team, game_flow_analyses)
    
    # Step 11: Print the confidence level and reason
    print(f"\nConfidence Level for {player_name} on {player_prop} points: {confidence_level}")
    print(f"Reason: {reason}")

    return confidence_level, reason


# Main Function to Run All Analyses
async def main():
    with open("/Users/ajoyner/unrivaled_ai_sportsbet/data/unrivaled/unr_enriched_players.json", "r") as f:
        enriched_data = json.load(f)

    # Fetch player teams from the database
    player_teams = get_player_teams()

    # Analyze all players sequentially
    # for player in enriched_data:
        # await analyze_player(player, player_teams)

    # Limit concurrency to 5 tasks at a time
    semaphore = asyncio.Semaphore(2)
    tasks = [analyze_player_with_semaphore(semaphore, player, player_teams) for player in enriched_data]
    results = await asyncio.gather(*tasks)

    # Prepare the final output as a dictionary
    output = {}
    for player, result in zip(enriched_data, results):
        player_name = player["Player Data"]["name"]
        if result:
            confidence_level, reason = result
            output[player_name] = {
                "confidence": confidence_level,
                "reason": reason
            }
        else:
            output[player_name] = {
                "confidence": 75,  # Default confidence level if analysis fails
                "reason": "No analysis available."
            }

    # Print the final output as JSON
    print(json.dumps(output))

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())