import aiohttp
import sys
from database.firebase import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_API_URL, db
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(5),  # Retry up to 3 times
    wait=wait_exponential(multiplier=1, min=4, max=10),  # Exponential backoff
    retry=retry_if_exception_type(Exception),  # Retry on any exception
)

async def calculate_final_confidence_level(session, player_name, player_team, past_performance_analysis, player_prop, opposing_team, injury_reports):
    # Add a delay to avoid rate limiting
    await asyncio.sleep(1)  # 1-second delay between requests

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # Fetch past game analyses from Firebase
    player_ref = db.collection("players").document(player_name)
    games_ref = player_ref.collection("games")
    past_game_analyses = []

    # Fetch all teams' "pa" values
    teams_ref = db.collection("teams").stream()
    teams_pa = {team.id: team.to_dict().get("pa", 0) for team in teams_ref}  # Store in a dictionary

    # Sort teams by "pa" in descending order (higher is worse)
    sorted_teams = sorted(teams_pa.items(), key=lambda x: x[1], reverse=True)

    # Create a ranking dictionary
    team_rankings = {team: rank + 1 for rank, (team, _) in enumerate(sorted_teams)}

    # Function to get ranking for a specific opposing team
    def get_team_ranking(opposing_team):
        return team_rankings.get(opposing_team, "Team not found")

    rank = get_team_ranking(opposing_team)
    pa = teams_pa[opposing_team]

    try:
        # Use a regular for loop since stream() is synchronous
        for game in games_ref.stream():
            if "analysis" in game.to_dict():
                past_game_analyses.append(game.to_dict()["analysis"])
    except Exception as e:
        print(f"Error fetching past game analyses for {player_name}: {e}", file=sys.stderr)
        return None

    # Combine past game analyses into a single string
    past_game_analyses_str = "\n\n".join(past_game_analyses)

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
                    f"Past Game Analyses:\n{past_game_analyses_str}\n\n"
                    f"Past Performance Analysis against {opposing_team}:\n{past_performance_analysis}\n\n"
                    f"Player Prop: {player_prop} points\n\n"
                    f"Opposing Team: {opposing_team}\n\n"
                    f"Opposing Team Points Allowed: {pa} points, ranked {rank} out of 6 teams (6 being most pts allowed)\n\n"
                    f"Injury Reports:\n{injury_context}\n\n"
                    "Provide a definitive confidence level (0-100) and 4 detailed reasons for taking the over or under on the player's prop line, as well as a final summary. "
                    "The confidence level should reflect a strong belief in the outcome, with 0-25 indicating an extreme under, 26-50 indicating a moderate under, 51-75 indicating a moderate over, and 76-100 indicating an extreme over. "
                    "Please format your response as follows:\n"
                    "Confidence Level: <confidence_level>\n"
                    "Reason 1 (Performance Against Opposing Team): <reason_1>\n"
                    "Reason 2 (Scoring Trends - Clutch Performance in Critical Moments, Hot/Cold Streaks): <reason_2>\n"
                    "Reason 3 (Opposing Team's Defensive Weaknesses): <reason_3>\n"
                    "Reason 4 (Recent Performance - Last 5 Games): <reason_4>\n"
                    "Final Conclusion: <final_conclusion>\n\n"
                    "For the reasons, please provide detailed insights like:\n"
                    "- How the opposing team's defense ranks in points allowed and how it impacts the player's performance.\n"
                    "- The player's consistency in scoring above the prop line in past encounters with the opposing team.\n"
                    "- The player's role in their team and how it affects their scoring opportunities.\n"
                    "- The player's recent performance trends over the last 5 games.\n\n"
                    "Example format for reasons:\n"
                    "Reason 1 (Performance Against Opposing Team): {opposing_team} allowed {points_allowed} points this season. On top of this, {player_name} has scored above the prop line consistently in each of their past encounters with {opposing_team}, averaging {average_points_against_opponent} points per game. This suggests a favorable matchup for {player_name}.\n"
                    "Reason 2 (Scoring Trends - Clutch Performance in Critical Moments, Hot/Cold Streaks): {player_name} has shown a tendency to elevate their game in critical moments, particularly in the second half. In their last three games, they have had strong fourth-quarter performances, including an 8-point burst in one game and multiple three-pointers in another. This indicates they have the potential to exceed the prop line, especially if the game is close.\n"
                    "Reason 3 (Opposing Team's Defensive Weaknesses): {opposing_team} is missing key players like {injured_player} due to injuries, which could weaken their perimeter defense and rebounding. {player_name}'s strength in three-point shooting ({three_point_percentage}% against {opposing_team}) could be even more effective against a depleted defense. Additionally, {opposing_team}'s defensive rebounding may suffer without {injured_player}, potentially giving {player_name} more opportunities for second-chance points or open looks.\n"
                    "Reason 4 (Recent Performance - Last 5 Games): Over their last five games, {player_name} has averaged approximately {average_points_last_5} points per game, slightly below the prop line. However, they have shown the ability to exceed {player_prop} points in key games, such as their {best_game_points}-point performance against {opposing_team} and an 8-point burst in the fourth quarter of another game. Their recent trend of strong second-half performances suggests they could hit the over if they maintain their rhythm and take advantage of {opposing_team}'s defensive vulnerabilities.\n"
                    "Final Conclusion: While {player_name}'s recent scoring average ({average_points_last_5} points) is slightly below the prop line, their ability to perform in clutch moments, their strong three-point shooting, and {opposing_team}'s defensive weaknesses due to injuries make the over a reasonable bet. Their inconsistency in the first half is a concern, but their tendency to elevate their game in critical moments and their recent performances against {opposing_team} provide enough confidence to lean toward the over. Confidence level: {confidence_level}."
                )
            }
        ]
    }

    try:
        timeout = aiohttp.ClientTimeout(total=120)  # 120-second timeout
        async with session.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=timeout) as response:
            if response.status == 200:
                result = await response.json()
                if result and "choices" in result and len(result["choices"]) > 0:
                    response_content = result["choices"][0]["message"]["content"]

                    # Parse the response
                    confidence_level = None
                    reasons = []
                    final_conclusion = None

                    # Split the response into lines
                    lines = response_content.split("\n")
                    # print(lines)

                    # Iterate through the lines to extract data
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        # print(line)
                        # print(line)
                        if line.startswith("Confidence Level:"):
                            # Extract confidence level
                            confidence_level = int(line.split(":")[1].strip().split(" ")[0])  # Extract the number (e.g., "70" from "70 (Over)")
                            i += 1
                        elif line.startswith("Reason"):
                            # Capture the entire reason text, including multiline content
                            reason_text = []
                            print(line)
                            # Split at "):" and take the part after it
                            reason_part = line.split("):", 1)  # Split at the first occurrence of "):"
                            if len(reason_part) > 1:  # Ensure there is text after "):"
                                reason_text.append(reason_part[1].strip())  # Append the text after "):"
                            i += 1

                            print(reason_text)
                            reasons.append(" ".join(reason_text).strip())
                            
                        elif line.startswith("Final Conclusion:"):
                            # Capture the entire Final Conclusion section, including multiline text
                            conclusion = []
                            print(line)
                            # Split at "):" and take the part after it
                            final = line.split(":", 1)  # Split at the first occurrence of "):"
                            if len(final) > 1:  # Ensure there is text after "):"
                                conclusion.append(final[1].strip())  # Append the text after "):"
                            i += 1

                            print(conclusion)
                            final_conclusion = "\n".join(conclusion).strip()
                            
                            break  # Stop parsing after Final Conclusion
                        else:
                            i += 1  # Move to the next line

                    print(confidence_level)
                    print(reasons)
                    print(final_conclusion)
                    if confidence_level is not None and len(reasons) == 4 and final_conclusion is not None:
                        # Save the results to Firebase under the "latest" document
                        analysis_results_ref = player_ref.collection("analysis_results").document("latest")
                        analysis_results_ref.set({
                            "confidence_level": confidence_level,
                            "reason_1": reasons[0],
                            "reason_2": reasons[1],
                            "reason_3": reasons[2],
                            "reason_4": reasons[3],
                            "final_conclusion": final_conclusion
                        })

                        return {
                            "confidence_level": confidence_level,
                            "reasons": reasons,
                            "final_conclusion": final_conclusion
                        }
                    else:
                        print("Failed to parse DeepSeek response correctly.", file=sys.stderr)
            else:
                error_text = await response.text()
                print(f"DeepSeek API Error {response.status}: {error_text}", file=sys.stderr)
                raise RuntimeError(f"DeepSeek API Error {response.status}: {error_text}")
    except Exception as e:
        print(f"Error during DeepSeek API request for final analysis of {player_name}: {e}", file=sys.stderr)
        raise  # Re-raise the exception to trigger retry

    return None