import aiohttp
import sys
from database.player_data import fetch_plays_for_player, analyze_streaks
from database.firebase import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL

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

    streaks = analyze_streaks(plays, player_name)

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
                print(result)
                if result and "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
            else:
                raise RuntimeError(f"❌ DeepSeek API Error {response.status}: {await response.text()}")

    except Exception as e:
        print(f"⚠️ Exception in analyze_game_flow({game_id}): {e}", file=sys.stderr)
    return None