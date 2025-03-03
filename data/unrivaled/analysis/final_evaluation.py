import aiohttp
import sys
from database.firebase import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL

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
                    print(result["choices"][0]["message"]["content"])
                    return result["choices"][0]["message"]["content"]
            else:
                print(f"Failed to get analysis from DeepSeek API for final analysis of {player_name}. Status: {response.status}", file=sys.stderr)
    except Exception as e:
        print(f"Error during DeepSeek API request for final analysis of {player_name}: {e}", file=sys.stderr)
    return None
