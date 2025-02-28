import requests
from bs4 import BeautifulSoup
import pandas as pd
import mysql.connector
from datetime import datetime
import json
import unr_play_by_play_scrape as pbp

# Base URL for Unrivaled schedule
BASE_URL = "https://www.unrivaled.basketball"
SCHEDULE_URL = f"{BASE_URL}/schedule"

def convert_to_sql_date(date_str):
    parsed_date = datetime.strptime(date_str, "%A, %B %d, %Y")
    return parsed_date.strftime("%Y-%m-%d")

def get_game_links_with_dates():
    response = requests.get(SCHEDULE_URL)
    soup = BeautifulSoup(response.content, "html.parser")

    game_data = []

    date_containers = soup.find_all("div", class_="flex row-12 p-12")

    for container in date_containers:
        date = container.find("span", class_="uppercase weight-500").text.strip()
        date_text = convert_to_sql_date(date)

        game_links = container.find_all("a", href=True)
        for a_tag in game_links:
            if "box-score" in a_tag["href"]:
                href = a_tag["href"]
                game_id = href.split("/")[2]
                game_link = f"{BASE_URL}{href}"
                game_data.append((game_link, game_id, date_text))

    return game_data

def format_player_name(player_href):
    name_part = player_href.split("/player/")[1].rsplit("-", 1)[0]
    formatted_name = name_part.replace("-", " ").title()
    return formatted_name

def scrape_game_stats(game_url, game_id, game_date):
    response = requests.get(game_url)
    soup = BeautifulSoup(response.content, "html.parser")

    teams_div = soup.find_all("div", class_="scrollbar-none")
    team_names = [div.find("h4").text.strip() for div in teams_div if div.find("h4")]

    if len(team_names) != 2:
        print(f"Error extracting team names from {game_url}")
        return None

    team_tables = [table for table in (div.find("table") for div in teams_div) if table is not None]
    home_team, away_team = team_names[0], team_names[1]
    home_team_pts, away_team_pts = 0, 0

    if len(team_tables) == 2:
        try:
            home_team_pts = int(team_tables[0].find("tr", class_="weight-500").find_all("td")[-1].text.strip())
            away_team_pts = int(team_tables[1].find("tr", class_="weight-500").find_all("td")[-1].text.strip())
        except Exception as e:
            print(f"Error scraping team points: {e}")

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

            stats = [col.text.strip() if col.text.strip() else "0" for col in cols[1:]]

            if stats[0] == "DNP":
                stats = ["0"] * 13

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
            shooting_stats = []
            for x in [row["fg"], row["three_pt"], row["ft"]]:
                if not x or x.strip() == "" or x == "0":
                    x = "0-0"
                if "-" in x:
                    made, attempted = map(int, x.split("-"))
                    shooting_stats.append(made)
                    shooting_stats.append(attempted)
                else:
                    shooting_stats.append(0)
            
            data = (
                row["game_date"],
                row["game_id"],
                row["player_name"],
                row["team"], row["opponent"],
                int(row["min"]) if row["min"].isdigit() else 0,
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

def insert_play_by_play_data(game_id, game_date, play_by_play_df):
    """Insert play-by-play data into the play_by_play table."""
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Joynera4919",
            database="unrivaled"
        )
        cursor = connection.cursor()

        # Insert each play into the play_by_play table
        for _, row in play_by_play_df.iterrows():
            sql_query = """
            INSERT INTO play_by_play (
                game_id, game_date, quarter, time, play_description, home_score, away_score, team, player
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            data = (
                game_id,
                game_date,
                row["quarter"],
                row["time"],
                row["play_description"],
                int(row["home_score"]),
                int(row["away_score"]),
                row["team"],
                row["player"]
            )
            cursor.execute(sql_query, data)

        connection.commit()
        print(f"Inserted {len(play_by_play_df)} play-by-play records for game_id: {game_id}")

    except mysql.connector.Error as e:
        print(f"Error inserting play-by-play data: {e}")

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def scrape_and_store_all_games():
    game_data = get_game_links_with_dates()
    all_game_stats = []

    for game_link, game_id, game_date in game_data:
        print(f"Scraping game stats from: {game_link} (Date: {game_date})")
        game_stats_df, game_metadata = scrape_game_stats(game_link, game_id, game_date)

        if game_stats_df is not None and game_metadata is not None:
            all_game_stats.append(game_stats_df)
            insert_game_metadata_into_database(game_metadata)

        print(f"Scraping play-by-play for game: {game_id}")
        play_by_play_df = pbp.scrape_play_by_play(game_id, game_date)
        if play_by_play_df is not None:
            insert_play_by_play_data(game_id, game_date, play_by_play_df)

    if all_game_stats:
        final_df = pd.concat(all_game_stats, ignore_index=True)
        insert_game_stats_into_database(final_df)
        final_df.to_csv("data/unrivaled/csv/unrivaled_game_stats.csv", index=False)
        print("Game stats saved to unrivaled_game_stats.csv and inserted into the database.")
    else:
        print("No game stats were scraped.")

if __name__ == "__main__":
    scrape_and_store_all_games()