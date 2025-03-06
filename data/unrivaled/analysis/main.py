import asyncio
import aiohttp
import json
import sys
from database.firebase import db
from datetime import datetime, timedelta  # Import datetime for timestamp functionality
from analysis.game_flow import analyze_game_flow
from analysis.past_performance import analyze_past_performance
from analysis.final_evaluation import calculate_final_confidence_level
from helpers.injury_reports import fetch_injury_reports
from database.player_data import get_game_ids_for_player

semaphore = asyncio.Semaphore(4)

async def analyze_player(player):
    async with semaphore:
        player_name = player["player_data"]["name"].replace(" ", "_")
        player_team = player["player_data"]["team"]
        opposing_team = player["projection_data"]["description"]
        player_prop = player["projection_data"]["line_score"]
        stat_type = player["projection_data"]["stat_type"]  # Get the stat type from projection data
        
        # Fetch player data from Firebase
        player_ref = db.collection("players").document(player_name)

        # Check if there's already an analysis for this player and stat type
        analysis_results_ref = player_ref.collection("analysis_results").document(f"{stat_type.lower()}_latest")
        latest_analysis = analysis_results_ref.get().to_dict()

        if latest_analysis:
            # Get the timestamp of the latest analysis
            analysis_timestamp = latest_analysis.get("timestamp", None)
            if analysis_timestamp:
                # Convert the timestamp to a datetime object
                analysis_date = datetime.fromisoformat(analysis_timestamp)
                # Get the current date
                current_date = datetime.now()

                time_difference = current_date - analysis_date
                # Check if the analysis is from the last 3 hours
                if time_difference < timedelta(hours=3):
                    print(f"Skipping {player_name} ({stat_type}) - Analysis already exists within the last 3 hours.", file=sys.stderr)
                    return None  # Skip this player
                
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
                    game_flow_analysis = await analyze_game_flow(session, player_name, game_id, stat_type)
                    game_flow_analyses.append(game_flow_analysis)

                # Analyze past performance
                past_performance_analysis = await analyze_past_performance(session, player_name, opposing_team)
                injury_reports = fetch_injury_reports()  # Doesn't need async

                # Log inputs for debugging
                print(f"Inputs for {player_name} ({stat_type}):")
                print(f"Game Flow Analyses: {game_flow_analyses}")
                print(f"Past Performance Analysis: {past_performance_analysis}")
                print(f"Injury Reports: {injury_reports}")

                # Call final DeepSeek API request
                print(f"Starting final analysis for player: {player_name} ({stat_type})")
                final_analysis = await calculate_final_confidence_level(
                    session, player_name, player_team, past_performance_analysis, player_prop, opposing_team, injury_reports, stat_type
                )
                print(f"Final analysis completed for player: {player_name} ({stat_type})")

                if final_analysis:
                    print(f"Final Analysis for {player_name} ({stat_type}):\n{final_analysis}")
                    return final_analysis
                else:
                    print(f"Failed to generate final analysis for {player_name} ({stat_type}).")
                    return None
            except Exception as e:
                print(f"Error analyzing player {player_name} ({stat_type}): {e}", file=sys.stderr)
                return None

async def main():
    """
    Main function to analyze all players asynchronously.
    """
    prop_lines_ref = db.collection("prop_lines").stream()
    enriched_data = [{"player_data": doc.to_dict().get("player_data", {}), "projection_data": doc.to_dict().get("projection_data", {})} for doc in prop_lines_ref]
    
    # Create a list of tasks for analyzing each player and stat type asynchronously
    tasks = [analyze_player(player) for player in enriched_data]

    # Run all tasks concurrently using asyncio.gather
    results = await asyncio.gather(*tasks)

    # Map results to player names and stat types
    output = {}
    for player, result in zip(enriched_data, results):
        player_name = player["player_data"]["name"]
        stat_type = player["projection_data"]["stat_type"]
        if player_name not in output:
            output[player_name] = {}
        output[player_name][stat_type] = {"analysis": result} if result else {"analysis": "No analysis available."}

    # Print the final output
    print(json.dumps(output, indent=4))
    return output

async def test_single_request():
    async with aiohttp.ClientSession() as session:
        result = await analyze_game_flow(session, "Rickea_Jackson", "6vgjcmphd6wm")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())