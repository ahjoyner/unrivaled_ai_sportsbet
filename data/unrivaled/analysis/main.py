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

semaphore = asyncio.Semaphore(1)

async def analyze_player(player):
    async with semaphore:
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
            try:
                # Process game flow analyses sequentially
                game_flow_analyses = []
                for game_id in game_ids:
                    game_flow_analysis = await analyze_game_flow(session, player_name, game_id)
                    game_flow_analyses.append(game_flow_analysis)

                # Analyze past performance
                past_performance_analysis = await analyze_past_performance(session, player_name, opposing_team)
                injury_reports = fetch_injury_reports()  # Doesn't need async

                # Log inputs for debugging
                print(f"Inputs for {player_name}:")
                print(f"Game Flow Analyses: {game_flow_analyses}")
                print(f"Past Performance Analysis: {past_performance_analysis}")
                print(f"Injury Reports: {injury_reports}")

                # Call final DeepSeek API request
                print("Starting final analysis for player:", player_name)
                final_analysis = await calculate_final_confidence_level(
                    session, player_name, player_team, past_performance_analysis, player_prop, opposing_team, injury_reports
                )
                print("Final analysis completed for player:", player_name)

                if final_analysis:
                    print(f"Final Analysis for {player_name}:\n{final_analysis}")
                    return final_analysis
                else:
                    print(f"Failed to generate final analysis for {player_name}.")
                    return None
            except Exception as e:
                print(f"Error analyzing player {player_name}: {e}", file=sys.stderr)
                return None

async def main():
    """
    Main function to analyze all players asynchronously.
    """
    prop_lines_ref = db.collection("prop_lines").stream()
    enriched_data = [{"player_data": doc.to_dict().get("player_data", {}), "projection_data": doc.to_dict().get("projection_data", {})} for doc in prop_lines_ref]
    
    # Create a list of tasks for analyzing each player asynchronously
    tasks = [analyze_player(player) for player in enriched_data]

    # Run all tasks concurrently using asyncio.gather
    results = await asyncio.gather(*tasks)

    # Map results to player names
    output = {}
    for player, result in zip(enriched_data, results):
        output[player["player_data"]["name"]] = {"analysis": result} if result else {"analysis": "No analysis available."}

    # Print the final output
    print(json.dumps(output, indent=4))
    return output

async def test_single_request():
    async with aiohttp.ClientSession() as session:
        result = await analyze_game_flow(session, "Rickea_Jackson", "6vgjcmphd6wm")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())