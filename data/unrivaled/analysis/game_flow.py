import aiohttp
import sys
import asyncio
import json
from database.player_data import fetch_plays_for_player, analyze_streaks
from database.firebase import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL, db
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),  # Retry 3 times
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Exponential backoff
    retry=retry_if_exception_type(Exception),  # Retry on any exception
)
async def analyze_game_flow(session, player_name, game_id, stat_type):
    print(f"Analyzing game flow for {player_name} in {game_id} for stat type: {stat_type}")
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # Check if analysis already exists for this game and stat type
    player_ref = db.collection("players").document(player_name)
    game_ref = player_ref.collection("games").document(game_id)
    existing_analysis = game_ref.get()

    # Field name for storing analysis by stat type
    analysis_field = f"{stat_type.lower()}_analysis"
    #print(analysis_field)

    if existing_analysis.exists and analysis_field in existing_analysis.to_dict():
        print(f"Analysis already exists for {player_name} in Game {game_id} for stat type {stat_type}. Skipping.")
        return existing_analysis.to_dict().get(analysis_field)

    #print(f"{analysis_field} does not exist yet")
    # Fetch play-by-play data
    plays = fetch_plays_for_player(game_id, player_name)
    if not plays:
        print(f"No play-by-play data found for {player_name} in Game {game_id}.", file=sys.stderr)
        return None

    # Analyze streaks and performance based on the stat type
    try:
        if stat_type == "Points":
            #print("Looking at Points...")
            streaks = analyze_streaks(plays, player_name, stat_type)
            #print(streaks)
            summary = {
                "total_points": sum(1 for play in plays if "makes" in play["play_description"]),
                "total_misses": sum(1 for play in plays if "misses" in play["play_description"]),
            }
        elif stat_type == "Rebounds":
            # Analyze rebounds (offensive and defensive)
            offensive_rebounds = sum(1 for play in plays if "offensive rebound" in play["play_description"].lower())
            defensive_rebounds = sum(1 for play in plays if "defensive rebound" in play["play_description"].lower())
            summary = {
                "total_rebounds": offensive_rebounds + defensive_rebounds,
                "offensive_rebounds": offensive_rebounds,
                "defensive_rebounds": defensive_rebounds,
            }
            streaks = {
                "rebound_streaks": analyze_streaks(plays, player_name, stat_type)
            }
            #print(streaks)
        elif stat_type == "Assists":
            # Analyze assists
            total_assists = sum(1 for play in plays if "assist" in play["play_description"].lower())
            summary = {
                "total_assists": total_assists,
            }
            streaks = {
                "assist_streaks": analyze_streaks(plays, player_name, stat_type)
            }
            #print(streaks)
        elif stat_type == "Pts+Rebs+Asts":
            # Analyze combined stats (Points + Rebounds + Assists)
            total_points = sum(1 for play in plays if "makes" in play["play_description"])
            offensive_rebounds = sum(1 for play in plays if "offensive rebound" in play["play_description"].lower())
            defensive_rebounds = sum(1 for play in plays if "defensive rebound" in play["play_description"].lower())
            total_assists = sum(1 for play in plays if "assist" in play["play_description"].lower())
            summary = {
                "total_points": total_points,
                "total_rebounds": offensive_rebounds + defensive_rebounds,
                "total_assists": total_assists,
            }
            streaks = {
                "point_streaks": analyze_streaks(plays, player_name, stat_type),
                "rebound_streaks": analyze_streaks(plays, player_name, stat_type),
                "assist_streaks": analyze_streaks(plays, player_name, stat_type),
            }
            #print(streaks)
        else:
            print(f"Unsupported stat type: {stat_type}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"⚠️ Error analyzing streaks or summary for {player_name} in Game {game_id}: {e}", file=sys.stderr)
        return None

    # Simplify the play-by-play data for analysis
    simplified_plays = []
    for play in plays:
        try:
            simplified_play = {
                "quarter": play["quarter"],
                "time": play["time"],
                "description": play["play_description"],
                "score": f"{play['home_score']}-{play['away_score']}"
            }
            simplified_plays.append(simplified_play)
        except KeyError as e:
            print(f"⚠️ Missing key in play data: {e}", file=sys.stderr)
            continue

    # Prepare the analysis prompt based on the stat type
    try:
        if stat_type == "Points":
            analysis_prompt = (
                f"Analyze the game flow for {player_name} in Game {game_id} based on the following data:\n\n"
                f"Summary of Performance:\n"
                f"- Total Points: {summary['total_points']}\n"
                f"- Total Misses: {summary['total_misses']}\n\n"
                f"Streaks Analysis:\n"
                f"- Hot Streaks (back-to-back makes): {streaks['hot_streaks']}\n"
                f"- Cold Streaks (back-to-back misses): {streaks['cold_streaks']}\n\n"
                f"Key Plays:\n"
                + "\n".join([f"{play['quarter']} {play['time']}: {play['description']} (Score: {play['score']})" for play in simplified_plays])
                + "\n\n"
                "Provide an analysis of the player's form in this game, including:\n"
                "1. How the player performed in different quarters.\n"
                "2. The player's consistency throughout the game.\n"
                "3. The player's impact on the flow of the game."
            )
        elif stat_type == "Rebounds":
            analysis_prompt = (
                f"Analyze the game flow for {player_name} in Game {game_id} based on the following data:\n\n"
                f"Summary of Performance:\n"
                f"- Total Rebounds: {summary['total_rebounds']}\n"
                f"- Offensive Rebounds: {summary['offensive_rebounds']}\n"
                f"- Defensive Rebounds: {summary['defensive_rebounds']}\n\n"
                f"Streaks Analysis:\n"
                f"- Rebound Streaks: {streaks['rebound_streaks']}\n\n"
                f"Key Plays:\n"
                + "\n".join([f"{play['quarter']} {play['time']}: {play['description']} (Score: {play['score']})" for play in simplified_plays])
                + "\n\n"
                "Provide an analysis of the player's rebounding in this game, including:\n"
                "1. How the player performed in different quarters.\n"
                "2. The player's dominance on the boards (offensive vs. defensive).\n"
                "3. The player's impact on the flow of the game through rebounds."
            )
        elif stat_type == "Assists":
            analysis_prompt = (
                f"Analyze the game flow for {player_name} in Game {game_id} based on the following data:\n\n"
                f"Summary of Performance:\n"
                f"- Total Assists: {summary['total_assists']}\n\n"
                f"Streaks Analysis:\n"
                f"- Assist Streaks: {streaks['assist_streaks']}\n\n"
                f"Key Plays:\n"
                + "\n".join([f"{play['quarter']} {play['time']}: {play['description']} (Score: {play['score']})" for play in simplified_plays])
                + "\n\n"
                "Provide an analysis of the player's playmaking in this game, including:\n"
                "1. How the player performed in different quarters.\n"
                "2. The player's consistency in creating opportunities for teammates.\n"
                "3. The player's impact on the flow of the game through assists."
            )
        elif stat_type == "Pts+Rebs+Asts":
            analysis_prompt = (
                f"Analyze the game flow for {player_name} in Game {game_id} based on the following data:\n\n"
                f"Summary of Performance:\n"
                f"- Total Points: {summary['total_points']}\n"
                f"- Total Rebounds: {summary['total_rebounds']}\n"
                f"- Total Assists: {summary['total_assists']}\n\n"
                f"Streaks Analysis:\n"
                f"- Point Streaks: {streaks['point_streaks']}\n"
                f"- Rebound Streaks: {streaks['rebound_streaks']}\n"
                f"- Assist Streaks: {streaks['assist_streaks']}\n\n"
                f"Key Plays:\n"
                + "\n".join([f"{play['quarter']} {play['time']}: {play['description']} (Score: {play['score']})" for play in simplified_plays])
                + "\n\n"
                "Provide an analysis of the player's overall impact in this game, including:\n"
                "1. How the player performed in different quarters.\n"
                "2. The player's consistency in scoring, rebounding, and assisting.\n"
                "3. The player's impact on the flow of the game through combined stats."
            )
        else:
            return None
    except Exception as e:
        print(f"⚠️ Error generating analysis prompt for {player_name} in Game {game_id}: {e}", file=sys.stderr)
        return None

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": analysis_prompt
            }
        ]
    }

    try:
        async with session.post(DEEPSEEK_API_URL, headers=headers, json=data) as response:
            if response.status == 200:
                # Read the response content in chunks
                content = b""
                async for chunk in response.content.iter_chunked(1024):  # Read in 1KB chunks
                    content += chunk

                # Decode the raw content
                raw_content = content.decode("utf-8")
                # print(f"Raw Response Content: {raw_content}")  # Log the raw content

                try:
                    # Attempt to parse the JSON response
                    result = json.loads(raw_content)  # Use json.loads as a fallback
                    print(f"Parsed JSON Response: {result}")  # Log the parsed JSON
                    if result and "choices" in result and len(result["choices"]) > 0:
                        analysis = result["choices"][0]["message"]["content"]

                        # Store the analysis in Firestore under the game_id document, using the stat-specific field
                        game_ref.set({analysis_field: analysis}, merge=True)

                        return analysis
                except json.JSONDecodeError as json_error:
                    print(f"⚠️ Failed to parse JSON response: {json_error}", file=sys.stderr)
                    # If JSON parsing fails, return the raw content as a fallback
                    return raw_content
            else:
                error_text = await response.text()
                print(f"❌ DeepSeek API Error {response.status}: {error_text}", file=sys.stderr)
                raise RuntimeError(f"DeepSeek API Error {response.status}: {error_text}")

    except Exception as e:
        print(f"⚠️ Exception in analyze_game_flow({game_id}): {e}", file=sys.stderr)
        raise  # Re-raise the exception to trigger retry

    return None