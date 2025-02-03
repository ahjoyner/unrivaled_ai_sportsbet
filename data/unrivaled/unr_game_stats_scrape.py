import requests
from bs4 import BeautifulSoup
import pandas as pd
import mysql.connector
from datetime import datetime
import unr_play_by_play_scrape as pbp

# Base URL for Unrivaled schedule
BASE_URL = "https://www.unrivaled.basketball"
SCHEDULE_URL = f"{BASE_URL}/schedule"


def convert_to_sql_date(date_str):
    # Parse the date string into a Python datetime object
    parsed_date = datetime.strptime(date_str, "%A, %B %d, %Y")
    # Format the date as a SQL-compatible string (YYYY-MM-DD)
    return parsed_date.strftime("%Y-%m-%d")


# Function to scrape game URLs and associated dates
def get_game_links_with_dates():
    response = requests.get(SCHEDULE_URL)
    soup = BeautifulSoup(response.content, "html.parser")

    game_data = []  # To store tuples of (game_link, game_date)

    # Find all date containers (parent containers holding dates and game links)
    date_containers = soup.find_all("div", class_="flex row-12 p-12")

    for container in date_containers:
        # Extract the game date
        date = container.find("span", class_="uppercase weight-500").text.strip()
        date_text = convert_to_sql_date(date)

        # Find all game links within this date's container
        game_links = container.find_all("a", href=True)
        for a_tag in game_links:
            if "box-score" in a_tag["href"]:
                game_link = f"{BASE_URL}{a_tag['href']}"
                game_data.append((game_link, date_text))

    return game_data

# Function to format player name from href
def format_player_name(player_href):
    name_part = player_href.split("/player/")[1].rsplit("-", 1)[0]
    formatted_name = name_part.replace("-", " ").title()
    return formatted_name

# Function to scrape player stats for a specific game
def get_game_links_with_dates():
    response = requests.get(SCHEDULE_URL)
    soup = BeautifulSoup(response.content, "html.parser")

    game_data = []  # To store tuples of (game_link, game_id, game_date)

    # Find all date containers (parent containers holding dates and game links)
    date_containers = soup.find_all("div", class_="flex row-12 p-12")

    for container in date_containers:
        # Extract the game date
        date = container.find("span", class_="uppercase weight-500").text.strip()
        date_text = convert_to_sql_date(date)

        # Find all game links within this date's container
        game_links = container.find_all("a", href=True)
        for a_tag in game_links:
            if "box-score" in a_tag["href"]:
                href = a_tag["href"]
                game_id = href.split("/")[2]  # Extract game_id from URL
                game_link = f"{BASE_URL}{href}"
                game_data.append((game_link, game_id, date_text))

    return game_data

def scrape_game_stats(game_url, game_id, game_date):
    response = requests.get(game_url)
    soup = BeautifulSoup(response.content, "html.parser")

    # Extract team names from divs
    teams_div = soup.find_all("div", class_="scrollbar-none")
    team_names = [div.find("h4").text.strip() for div in teams_div if div.find("h4")]

    if len(team_names) != 2:
        print(f"Error extracting team names from {game_url}")
        return None

    # Get team and opponent points from the last <td> of each table
    team_tables = [table for table in (div.find("table") for div in teams_div) if table is not None]
    home_team, away_team = team_names[0], team_names[1]
    home_team_pts, away_team_pts = 0, 0

    if len(team_tables) == 2:
        try:
            # Extract team points
            home_team_pts = int(team_tables[0].find("tr", class_="weight-500").find_all("td")[-1].text.strip())
            away_team_pts = int(team_tables[1].find("tr", class_="weight-500").find_all("td")[-1].text.strip())
        except Exception as e:
            print(f"Error scraping team points: {e}")

    # Prepare game metadata to insert into games table
    game_metadata = (game_id, game_date, home_team, away_team, home_team_pts, away_team_pts)

    players_stats = []
    tables = soup.find_all("table")

    for team, table in zip(team_names, tables):
        opponent = away_team if team == home_team else home_team

        rows = table.find("tbody").find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if cols[0].text.strip().upper() == "TEAM":
                break

            player_link = cols[0].find("a")
            if player_link and "href" in player_link.attrs:
                player_href = player_link["href"]
                player_name = format_player_name(player_href)
            else:
                continue

            # Extract stats and check if player did not play ("DNP")
            stats = [col.text.strip() if col.text.strip() else "0" for col in cols[1:]]

            if stats[0] == "DNP":
                stats = ["0"] * 13  # Replace all stats with 0 if player did not play

            # Append player stats with correctly assigned team and opponent points
            players_stats.append([game_id, game_date, team, opponent, player_name] + stats)

    columns = [
        "game_id", "game_date", "team", "opponent", "player_name",
        "min", "fg", "three_pt", "ft", "reb", "offensive_rebounds", "defensive_rebounds", 
        "ast", "stl", "blk", "turnovers", "pf", "pts"
    ]

    return pd.DataFrame(players_stats, columns=columns), game_metadata

def insert_game_metadata_into_database(game_metadata):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Joynera4919",
            database="unrivaled"
        )
        cursor = connection.cursor()

        # Insert game metadata
        sql_query = """
        INSERT INTO games (game_id, game_date, home_team, away_team, home_team_score, away_team_score)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            game_date = VALUES(game_date),
            home_team = VALUES(home_team),
            away_team = VALUES(away_team),
            home_team_score = VALUES(home_team_score),
            away_team_score = VALUES(away_team_score);
        """
        cursor.execute(sql_query, game_metadata)
        connection.commit()
        print(f"Inserted/Updated game metadata for game_id: {game_metadata[0]}")

    except mysql.connector.Error as e:
        print(f"Error: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Function to insert game stats into MySQL database
def insert_game_stats_into_database(game_stats_df):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Joynera4919",
            database="unrivaled"
        )
        cursor = connection.cursor()

        for _, row in game_stats_df.iterrows():
            # Convert shooting stats (FG, 3PT, FT) to percentages safely
            shooting_stats = []
            for x in [row["fg"], row["three_pt"], row["ft"]]:
                if not x or x.strip() == "" or x == "0":  # Handle empty or None values
                    x = "0-0"
                if "-" in x:
                    made, attempted = map(int, x.split("-"))
                    shooting_stats.append(made)
                    shooting_stats.append(attempted)
                else:
                    shooting_stats.append(0)
            
            print(row)

            # Ensure all numerical fields have valid values before conversion
            data = (
                row["game_date"],  # Store the game date
                row["game_id"],  # Game ID as a combination of Team and Opponent
                row["player_name"],
                row["team"], row["opponent"],
                int(row["min"]) if row["min"].isdigit() else 0,  # Convert "None" to 0
                *shooting_stats,
                int(row["reb"]) if row["reb"] else 0,
                int(row["offensive_rebounds"]) if row["offensive_rebounds"] else 0,
                int(row["defensive_rebounds"]) if row["defensive_rebounds"] else 0,
                int(row["ast"]) if row["ast"] else 0,
                int(row["stl"]) if row["stl"] else 0,
                int(row["blk"]) if row["blk"] else 0,
                int(row["turnovers"]) if row["turnovers"] else 0,
                int(row["pf"]) if row["pf"] else 0,
                int(row["pts"]) if row["pts"] else 0
            )
            print(data)

            sql_query = """
            INSERT INTO game_stats (
                game_date, game_id, player_name, team, opponent, min, fg_m, fg_a, three_pt_m, three_pt_a, 
                ft_m, ft_a, reb, offensive_rebounds, defensive_rebounds, ast, stl, blk, turnovers, pf, pts
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                min = VALUES(min), fg_m = VALUES(fg_m), fg_a = VALUES(fg_a), three_pt_m = VALUES(three_pt_m),
                three_pt_a = VALUES(three_pt_a), ft_m = VALUES(ft_m), ft_a = VALUES(ft_a), reb = VALUES(reb),
                offensive_rebounds = VALUES(offensive_rebounds), defensive_rebounds = VALUES(defensive_rebounds),
                ast = VALUES(ast), stl = VALUES(stl), blk = VALUES(blk),
                turnovers = VALUES(turnovers), pf = VALUES(pf), pts = VALUES(pts), game_date = VALUES(game_date);
            """
            
            cursor.execute(sql_query, data)

        connection.commit()
        print(f"Inserted/Updated {len(game_stats_df)} records into the game_stats table.")
    
    except mysql.connector.Error as e:
        print(f"Error: {e}")
    
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Main function to scrape all games and insert into database
def scrape_and_store_all_games():
    game_data = get_game_links_with_dates()  # Get game links, IDs, and dates
    all_game_stats = []

    for game_link, game_id, game_date in game_data:
        print(f"Scraping game stats from: {game_link} (Date: {game_date})")
        game_stats_df, game_metadata = scrape_game_stats(game_link, game_id, game_date)
        # game_metadata.to_csv(f"data/unrivaled/csv/game_{game_id}.csv")

        if game_stats_df is not None and game_metadata is not None:
            all_game_stats.append(game_stats_df)
            insert_game_metadata_into_database(game_metadata)  # Insert metadata into games table

        print(f"Scraping play-by-play for game: {game_id}")
        play_by_play_df = pbp.scrape_play_by_play(game_id, game_date)
        if play_by_play_df is not None:
            # pbp.insert_play_by_play_into_database(play_by_play_df)
            play_by_play_df.to_csv(f"data/unrivaled/csv/play_by_play/play_by_play_{game_id}.csv", index=False)  # Save to CSV
            print(f"Play-by-play data saved to play_by_play_{game_id}.csv")

    if all_game_stats:
        final_df = pd.concat(all_game_stats, ignore_index=True)
        insert_game_stats_into_database(final_df)  # Insert data into database
        final_df.to_csv("data/unrivaled/csv/unrivaled_game_stats.csv", index=False)
        print("Game stats saved to unrivaled_game_stats.csv and inserted into the database.")
    else:
        print("No game stats were scraped.")

if __name__ == "__main__":
    scrape_and_store_all_games()
