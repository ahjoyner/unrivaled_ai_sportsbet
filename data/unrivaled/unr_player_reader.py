import json
from classes import player_stats as p, team_stats as t, game_by_game_stats as g


class UNRPlayerData:
    def __init__(self, player_id, player_data, projection_data):
        self.player_id = player_id
        self.name = player_data.get("name", "Unknown")
        self.position = player_data.get("position", "Unknown")
        self.team = player_data.get("team", "Unknown")
        self.image_url = player_data.get("image_url", "Unknown")
        self.league = player_data.get("league", "Unknown")
        self.stat_type = projection_data.get("stat_type", "Unknown")
        self.stat_display_name = projection_data.get("stat_display_name", "Unknown")
        self.line_score = projection_data.get("line_score", "Unknown")
        self.start_time = projection_data.get("start_time", "Unknown")
        self.status = projection_data.get("status", "Unknown")
        self.game_id = projection_data.get("game_id", "Unknown")
        self.opponent = None

    def find_opponent(self, all_players):
        """
        Find the opponent team by checking all players with the same game_id.
        """
        for player in all_players:
            if player.game_id == self.game_id and player.team != self.team:
                self.opponent = player.team
                break  # Stop searching once the opponent is found

    def __str__(self):
        opponent_text = f"vs {self.opponent}" if self.opponent else ""
        return f"\n{self.name} ({self.position}) - {self.team} | {self.stat_display_name} Prop: {self.line_score} {self.stat_type} {opponent_text}"


def parse_player_stats(file_path):
    players = []
    with open(file_path, "r") as f:
        for line in f.read().splitlines()[1:]:  # Skip the header
            fields = line.split(",")
            player = p.PlayerStats(*fields)
            players.append(player)
    return players


def parse_team_stats(file_path):
    teams = []
    with open(file_path, "r") as f:
        for line in f.read().splitlines()[1:]:  # Skip the header
            fields = line.split(",")
            team = t.TeamStats(*fields)
            teams.append(team)
    return teams


def parse_game_stats(file_path):
    games = []
    with open(file_path, "r") as f:
        for line in f.read().splitlines()[1:]:  # Skip the header
            fields = line.split(",")
            game = g.GameStats(*fields)
            games.append(game)
    return games


def get_player_data(player_name, player_stats, game_stats):
    """
    Retrieve and display stats for a specific player.
    """
    # Find player in player stats
    player_info = next((player for player in player_stats if player.name == player_name), None)

    # Find all games played by the player
    player_games = [game for game in game_stats if game.player_name == player_name]

    if not player_info:
        print(f"\nNo stats found for player: {player_name}")
        return

    # Display player stats
    print(f"\nPlayer Stats for {player_name}:")
    print(f"Team: {player_info.team}")
    print(f"GP: {player_info.gp}, MIN: {player_info.min_per_game}, PTS: {player_info.pts}")
    print(f"REB: {player_info.reb}, AST: {player_info.ast}, STL: {player_info.stl}, BLK: {player_info.blk}")

    # Display game-by-game stats
    if player_games:
        print("\nGame-by-Game Stats:")
        for game in player_games:
            if game.min_played.strip().upper() == "DNP":
                print(f"Opponent: {game.opponent}, Status: Did Not Play (DNP)")
            else:
                print(f"Opponent: {game.opponent}, MIN: {game.min_played}, FG%: {game.fg_percentage}, PTS: {game.pts}")
    else:
        print(f"No game stats available for {player_name}.")


def main():
    # Load enriched player data
    with open("unr_enriched_players.json", "r") as f:
        enriched_data = json.load(f)

    # Create UNRPlayerData objects
    players = [
        UNRPlayerData(player["Player ID"], player["Player Data"], player["Projection Data"])
        for player in enriched_data
    ]

    # Parse additional CSV stats
    player_stats = parse_player_stats("data/unrivaled/csv/unrivaled_player_stats.csv")
    team_stats = parse_team_stats("data/unrivaled/csv/unrivaled_team_stats.csv")
    game_stats = parse_game_stats("data/unrivaled/csv/unrivaled_game_stats.csv")

    for player in players:
        player.find_opponent(players)
        
    # Print player details and stats
    for player in players:
        print(player)
        get_player_data(player.name, player_stats, game_stats)


if __name__ == "__main__":
    main()
