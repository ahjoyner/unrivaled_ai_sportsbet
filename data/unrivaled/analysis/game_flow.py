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
async def analyze_game_flow(session, player_name, game_id):
    print(f"Analyzing game flow for {player_name} in {game_id}")
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # Check if analysis already exists for this game
    player_ref = db.collection("players").document(player_name)
    game_ref = player_ref.collection("games").document(game_id)
    existing_analysis = game_ref.get()

    if existing_analysis.exists and "analysis" in existing_analysis.to_dict():
        print(f"Analysis already exists for {player_name} in Game {game_id}. Skipping.")
        return existing_analysis.to_dict().get("analysis")

    plays = fetch_plays_for_player(game_id, player_name)
    if not plays:
        print(f"No play-by-play data found for {player_name} in Game {game_id}.", file=sys.stderr)
        return None

    streaks = analyze_streaks(plays, player_name)

    # Simplify the play-by-play data for analysis
    simplified_plays = []
    for play in plays:
        simplified_play = {
            "quarter": play["quarter"],
            "time": play["time"],
            "description": play["play_description"],
            "score": f"{play['home_score']}-{play['away_score']}"
        }
        simplified_plays.append(simplified_play)

    # Summarize the player's performance
    summary = {
        "total_points": sum(1 for play in plays if "makes" in play["play_description"]),
        "total_misses": sum(1 for play in plays if "misses" in play["play_description"]),
        "total_rebounds": sum(1 for play in plays if "rebound" in play["play_description"]),
        "total_turnovers": sum(1 for play in plays if "turnover" in play["play_description"]),
        "total_assists": sum(1 for play in plays if "assist" in play["play_description"]),
    }

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the game flow for {player_name} in Game {game_id} based on the following data:\n\n"
                    f"Summary of Performance:\n"
                    f"- Total Points: {summary['total_points']}\n"
                    f"- Total Misses: {summary['total_misses']}\n"
                    f"- Total Rebounds: {summary['total_rebounds']}\n"
                    f"- Total Turnovers: {summary['total_turnovers']}\n"
                    f"- Total Assists: {summary['total_assists']}\n\n"
                    f"Streaks Analysis:\n"
                    f"- Hot Streaks (back-to-back makes): {streaks['hot_streaks']}\n"
                    f"- Cold Streaks (back-to-back misses): {streaks['cold_streaks']}\n"
                    f"- Assist Streaks (assists without turnovers): {streaks['assist_streaks']}\n\n"
                    f"Key Plays:\n"
                    + "\n".join([f"{play['quarter']} {play['time']}: {play['description']} (Score: {play['score']})" for play in simplified_plays])
                    + "\n\n"
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
                # Read the response content in chunks
                content = b""
                async for chunk in response.content.iter_chunked(1024):  # Read in 1KB chunks
                    content += chunk

                # Decode the raw content
                raw_content = content.decode("utf-8")
                print(f"Raw Response Content: {raw_content}")  # Log the raw content

                try:
                    # Attempt to parse the JSON response
                    result = json.loads(raw_content)  # Use json.loads as a fallback
                    print(f"Parsed JSON Response: {result}")  # Log the parsed JSON
                    if result and "choices" in result and len(result["choices"]) > 0:
                        analysis = result["choices"][0]["message"]["content"]

                        # Store the analysis in Firestore under the game_id document
                        game_ref.set({"analysis": analysis}, merge=True)

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