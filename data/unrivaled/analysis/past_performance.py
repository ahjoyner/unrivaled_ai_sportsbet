import aiohttp
import sys
from database.player_data import get_past_performance_against_opponent
from database.firebase import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL

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