import pandas as pd
import json
import numpy as np
from datetime import datetime

# Load datasets with explicit encoding and error handling
try:
    with open('unr_enriched_players.json', 'r', encoding='utf-8') as f:
        projections = json.load(f)
        
    game_stats = pd.read_csv('data/unrivaled/csv/unrivaled_game_stats.csv', 
                           parse_dates=['game_date'],
                           date_parser=lambda x: pd.to_datetime(x).tz_localize(None))
    
    player_stats = pd.read_csv('data/unrivaled/csv/unrivaled_player_stats.csv')
    team_stats = pd.read_csv('data/unrivaled/csv/unrivaled_team_stats.csv')

except FileNotFoundError as e:
    print(f"Critical file missing: {str(e)}")
    exit(1)

# Calculate league averages with null safety
league_avg_papg = team_stats['papg'].mean() if not team_stats.empty else 0
league_avg_ppg = player_stats['PTS'].mean() if not player_stats.empty else 0

# Calculate league points per shot
try:
    total_points = player_stats['PTS'].sum()
    total_fga = player_stats['FG'].str.split('-').str[1].fillna(0).astype(float).sum()
    league_avg_pps = total_points / total_fga if total_fga > 0 else 0
except KeyError:
    league_avg_pps = 0

def calculate_confidence(player_proj):
    try:
        # Extract data with null checks
        player_data = player_proj.get('Player Data', {})
        proj_data = player_proj.get('Projection Data', {})
        
        player_name = player_data.get('name', 'Unknown Player')
        team = player_data.get('team', 'Unknown Team')
        opponent = proj_data.get('description', 'Unknown Opponent')
        prop_line = proj_data.get('line_score', 0)
        position = player_data.get('position', 'N/A')
        
        # Safely parse game time
        game_time = pd.to_datetime(proj_data.get('start_time', '1900-01-01')).tz_localize(None)

        # Filter games with type safety
        player_games = game_stats[
            (game_stats['player_name'] == player_name) &
            (pd.to_datetime(game_stats['game_date']) < game_time)
        ].sort_values('game_date', ascending=False)

        if player_games.empty:
            return None

        # ----- Data Validation -----
        # Get player stats with fallbacks
        try:
            player_row = player_stats[player_stats['Player Name'] == player_name].iloc[0]
            season_ppg = player_row['PTS']
            mins_avg = player_row['MIN']
        except (IndexError, KeyError):
            season_ppg = 0
            mins_avg = 0

        # ----- Advanced Metrics -----
        # Trend analysis
        last_3_games = player_games.head(3)
        last_5_games = player_games.head(5)
        trend_3 = last_3_games['pts'].mean() - season_ppg if not last_3_games.empty else 0
        trend_5 = last_5_games['pts'].mean() - season_ppg if not last_5_games.empty else 0

        # Efficiency metrics
        fg_attempts = last_3_games['fg'].str.split('-').str[1].fillna(0).astype(float).mean()
        pts_per_shot = last_3_games['pts'].mean() / fg_attempts if fg_attempts > 0 else 0

        # ----- Contextual Factors -----
        # Defensive stats with fallbacks
        team_papg = team_stats.loc[team_stats['team'] == team, 'papg'].values[0] \
            if not team_stats[team_stats['team'] == team].empty else league_avg_papg
            
        opponent_papg = team_stats.loc[team_stats['team'] == opponent, 'papg'].values[0] \
            if not team_stats[team_stats['team'] == opponent].empty else league_avg_papg

        # Pace calculation
        team_pts = team_stats.loc[team_stats['team'] == team, 'pts'].values[0] \
            if not team_stats[team_stats['team'] == team].empty else 0
            
        opponent_pts = team_stats.loc[team_stats['team'] == opponent, 'pts'].values[0] \
            if not team_stats[team_stats['team'] == opponent].empty else 0
            
        pace_factor = (team_pts / 100) * (opponent_pts / 100) if team_pts and opponent_pts else 1.0

        # ----- Confidence Algorithm -----
        # Weighted components
        base_score = (
            0.4 * season_ppg +
            0.3 * (last_3_games['pts'].mean() if not last_3_games.empty else 0) +
            0.2 * (last_5_games['pts'].mean() if not last_5_games.empty else 0) +
            0.1 * trend_3
        )

        matchup_games = player_games[player_games['opponent'] == opponent]
        
        # Opponent adjustment
        matchup_adjusted = base_score * (opponent_papg / league_avg_papg)
        
        # Efficiency boost
        efficiency_boost = np.log(pts_per_shot + 1) * 10
        
        # Final calculation
        final_score = (matchup_adjusted * pace_factor) + efficiency_boost
        confidence = max(min((final_score / prop_line) * 100, 150), 50)  # Clamped 50-150

        return {
            'player': player_name,
            'team': team,
            'position': position,
            'opponent': opponent,
            'prop_line': prop_line,
            'confidence': round(confidence, 1),
            'recommendation': 'OVER' if confidence >= 103 else 'UNDER',
            'key_factors': {
                'recent_form': f"{trend_3:+.1f}",
                'efficiency': f"{pts_per_shot:.1f}",
                'matchup_history': f"{matchup_games['pts'].mean():.1f}" if not matchup_games.empty else "N/A",
                'pace_impact': f"{pace_factor:.2f}x",
                'defense_strength': f"{opponent_papg:.1f}"
            }
        }

    except Exception as e:
        print(f"⚠️ Error processing {player_name}: {str(e)}")
        return None

def generate_narrative_report(results_df):
    # Style configuration
    STYLES = {
        'strong_over': '\033[1;32m',  # Bright green
        'mod_over': '\033[0;32m',     # Green
        'strong_under': '\033[1;31m', # Bright red
        'mod_under': '\033[0;31m',    # Red
        'reset': '\033[0m'
    }

    def get_style(confidence, recommendation):
        if recommendation == 'OVER':
            return STYLES['strong_over'] if confidence >= 120 else STYLES['mod_over']
        return STYLES['strong_under'] if confidence <= 80 else STYLES['mod_under']

    report = []
    
    for _, row in results_df.iterrows():
        try:
            # ----- Style Setup -----
            color = get_style(row['confidence'], row['recommendation'])
            strength = "STRONG" if (row['confidence'] >= 120 or row['confidence'] <= 80) else "MODERATE"
            
            # ----- Historical Analysis -----
            player_games = game_stats[game_stats['player_name'] == row['player']]
            hit_rate = "N/A"
            
            if not player_games.empty and row['prop_line'] > 0:
                hits = sum(1 for g in player_games.itertuples() 
                          if (row['recommendation'] == 'OVER' and g.pts > row['prop_line']) or
                             (row['recommendation'] == 'UNDER' and g.pts < row['prop_line']))
                hit_rate = f"{hits}/{len(player_games)} ({hits/len(player_games):.0%})"

            # ----- Report Construction -----
            narrative = (
                f"{color}✦ {row['player']} ({row['position']} - {row['team']}){STYLES['reset']}\n"
                f"{color}┃ {strength} {row['recommendation']} CONFIDENCE: {row['confidence']}{STYLES['reset']}\n"
                f"┃ 📊 Line: {row['prop_line']} pts | 🎯 Hit Rate: {hit_rate}\n"
                f"┃ 🆚 Opponent: {row['opponent']} (Defense: {row['key_factors']['defense_strength']} PAPG)\n"
                f"┃ 📈 Recent Form: {row['key_factors']['recent_form']} | 🎯 PTS/SHOT: {row['key_factors']['efficiency']}\n"
                f"┃ 🏃 Pace Impact: {row['key_factors']['pace_impact']} | 🤼 History: {row['key_factors']['matchup_history']}\n"
                f"{color}┗{'━'*50}{STYLES['reset']}"
            )
            
            report.append(narrative)
            
        except Exception as e:
            print(f"⚠️ Error generating report for {row.get('player', 'Unknown')}: {str(e)}")

    return "\n\n".join(report)

# Main execution
if __name__ == "__main__":
    # Generate predictions
    analysis_results = []
    for player in projections:
        result = calculate_confidence(player)
        if result:
            analysis_results.append(result)

    if analysis_results:
        results_df = pd.DataFrame(analysis_results).sort_values('confidence', ascending=False)
        print("\nUNRIVALED PLAYER PROP ANALYSIS REPORT")
        print("══════════════════════════════════════\n")
        print(generate_narrative_report(results_df))
        print("\nLegend:")
        print("✦ Strong OVER: Bright Green | ✦ Moderate OVER: Green")
        print("✦ Strong UNDER: Bright Red | ✦ Moderate UNDER: Red")
    else:
        print("⚠️ No valid projections generated - check input data")