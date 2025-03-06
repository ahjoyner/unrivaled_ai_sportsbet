import aiohttp
import sys
import json
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

    # Fetch player data from Firebase
    player_ref = db.collection("players").document(player_name)
    player_stats = player_ref.get().to_dict()

    # Fetch PER and uPER from player stats
    player_per = player_stats.get("per", None)
    player_uper = player_stats.get("uper", None)

    # Fetch team data for points scored and points allowed
    team_ref = db.collection("teams").document(player_team)
    team_stats = team_ref.get().to_dict()
    points_scored = team_stats.get("pts_y", None)  # Points scored by the team
    points_allowed = team_stats.get("pts_a", None)  # Points allowed by the team

    # Fetch team records and win streaks
    losses = team_stats.get("losses", "")
    wins = team_stats.get("wins", "")
    team_record = f"{wins}-{losses}"
    streak = team_stats.get("streak", 0)

    # Fetch matchup history (player performance against opposing team)
    matchup_history = []
    games_ref = player_ref.collection("games").stream()
    for game in games_ref:
        game_stats = game.to_dict()
        if game_stats.get("opposing_team", "").lower() == opposing_team.lower():
            matchup_history.append({
                "points": game_stats.get("pts", 0),
                "rebounds": game_stats.get("reb", 0),
                "assists": game_stats.get("ast", 0),
                "date": game_stats.get("game_date", "Unknown")
            })

    # Fetch recent player performance (last 5 games)
    recent_games = []
    games_ref = player_ref.collection("games").stream()
    for game in games_ref:
        game_stats = game.to_dict()
        recent_games.append({
            "points": game_stats.get("pts", 0),
            "rebounds": game_stats.get("reb", 0),
            "assists": game_stats.get("ast", 0),
            "date": game_stats.get("game_date", "Unknown")
        })
    recent_games = sorted(recent_games, key=lambda x: x["date"], reverse=True)[:5]  # Last 5 games

    # Fetch injury reports (already passed as an argument)
    injury_context = ""
    if injury_reports:
        for report in injury_reports:
            if report["team"].lower() == player_team.lower() or report["team"].lower() == opposing_team.lower():
                injury_context += f"{report['player']} ({report['team']}) is {report['status']} with {report['injury']}.\n"

    # Prepare the analysis prompt with all stats
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Analyze the following data for {player_name}:\n\n"
                    f"Player Efficiency Rating (PER): {player_per} (League Average: 15)\n"
                    f"Unadjusted PER (UPER): {player_uper} (League Average: 0.851)\n"
                    f"Team Points Scored (Offensive Proxy): {points_scored}\n"
                    f"Team Points Allowed (Defensive Proxy): {points_allowed}\n"
                    f"Team Record: {team_record}\n"
                    f"Team Win/Lose Streak: {streak} games\n\n"
                    f"Past Performance Analysis: {past_performance_analysis}\n\n"
                    f"Matchup History Against {opposing_team}:\n"
                    f"{json.dumps(matchup_history, indent=2)}\n\n"
                    f"Recent Performance (Last 5 Games):\n"
                    f"{json.dumps(recent_games, indent=2)}\n\n"
                    f"Injury Reports:\n{injury_context}\n\n"
                    f"Player Prop: {player_prop} points\n\n"
                    f"Opposing Team: {opposing_team}\n\n"
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

                    # Iterate through the lines to extract data
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if line.startswith("Confidence Level:"):
                            confidence_level = int(line.split(":")[1].strip().split(" ")[0])
                            i += 1
                        elif line.startswith("Reason"):
                            reason_text = []
                            reason_part = line.split("):", 1)
                            if len(reason_part) > 1:
                                reason_text.append(reason_part[1].strip())
                            i += 1
                            reasons.append(" ".join(reason_text).strip())
                        elif line.startswith("Final Conclusion:"):
                            conclusion = []
                            final = line.split(":", 1)
                            if len(final) > 1:
                                conclusion.append(final[1].strip())
                            i += 1
                            final_conclusion = "\n".join(conclusion).strip()
                            break
                        else:
                            i += 1

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