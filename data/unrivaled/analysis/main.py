import asyncio
import aiohttp
import json
import sys
from database.firebase import db
from analysis.game_flow import analyze_game_flow
from analysis.past_performance import analyze_past_performance
from analysis.final_evaluation import calculate_final_confidence_level
from helpers.injury_reports import fetch_injury_reports
from database.player_data import get_game_ids_for_player

async def analyze_player(player):
    player_name = player["player_data"]["name"].replace(" ", "_")
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
        # Run API calls concurrently
        game_flow_tasks = [await analyze_game_flow(session, player_name, game_id) for game_id in game_ids]
        game_flow_analyses = await asyncio.gather(*game_flow_tasks, return_exceptions=True)
        past_performance_analysis = await analyze_past_performance(session, player_name, opposing_team)
        injury_reports = fetch_injury_reports()  # Doesn't need async

        # Log inputs for debugging
        print(f"Inputs for {player_name}:")
        print(f"Game Flow Analyses: {game_flow_analyses}")
        print(f"Past Performance Analysis: {past_performance_analysis}")
        print(f"Injury Reports: {injury_reports}")

        # Call final DeepSeek API request
        final_analysis = await calculate_final_confidence_level(
            session, player_name, player_team, game_flow_analyses, past_performance_analysis, player_prop, opposing_team, injury_reports
        )

        if final_analysis:
            print(f"Final Analysis for {player_name}:\n{final_analysis}")
            return final_analysis
        else:
            print(f"Failed to generate final analysis for {player_name}.")
            return None

async def main():
    """
    Main function to analyze all players.
    """
    prop_lines_ref = db.collection("prop_lines").stream()
    enriched_data = [{"player_data": doc.to_dict().get("player_data", {}), "projection_data": doc.to_dict().get("projection_data", {})} for doc in prop_lines_ref]

    tasks = [analyze_player(player) for player in enriched_data]
    results = await asyncio.gather(*tasks)

    output = {player["player_data"]["name"]: {"analysis": result} if result else {"analysis": "No analysis available."} for player, result in zip(enriched_data, results)}

    print(json.dumps(output))
    return output

if __name__ == "__main__":
    asyncio.run(main())
