import requests
import re
import pandas as pd
import mysql.connector
from bs4 import BeautifulSoup

# --------------------------
# PAPG Calculation Function
# --------------------------
def calculate_papg(games):
    """
    Calculate Points Allowed Per Game (PAPG) for each team using only the `games` table.
    """
    if games.empty:
        return {}

    # Create a list to store PAPG for each team
    papg_dict = {}

    # Iterate through each game and calculate PAPG
    for _, row in games.iterrows():
        home_team = row["home_team"]
        away_team = row["away_team"]
        home_team_score = row["home_team_score"]
        away_team_score = row["away_team_score"]

        # Points allowed by home team = away_team_score
        if home_team not in papg_dict:
            papg_dict[home_team] = {"total_pts_allowed": 0, "games_played": 0}
        papg_dict[home_team]["total_pts_allowed"] += away_team_score
        papg_dict[home_team]["games_played"] += 1

        # Points allowed by away team = home_team_score
        if away_team not in papg_dict:
            papg_dict[away_team] = {"total_pts_allowed": 0, "games_played": 0}
        papg_dict[away_team]["total_pts_allowed"] += home_team_score
        papg_dict[away_team]["games_played"] += 1

    # Calculate average PAPG for each team
    for team, data in papg_dict.items():
        papg_dict[team] = round(data["total_pts_allowed"] / data["games_played"], 1)

    return papg_dict

# --------------------------
# Web Scraping Functions
# --------------------------
def scrape_team_stats():
    url = "https://www.unrivaled.basketball/stats/team"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    teams = []
    tbody = soup.find("tbody")
    rows = tbody.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        team_name = cols[1].find("a").text.strip()
        stats = [col.text.strip() for col in cols[2:]]
        
        # Scrape team logo URL
        team_page_url = f"https://www.unrivaled.basketball/{team_name.lower().replace(' ', '-')}"
        team_page_response = requests.get(team_page_url)
        team_page_soup = BeautifulSoup(team_page_response.content, "html.parser")
        
        # Extract logo URL
        logo_url = "https://www.unrivaled.basketball" + team_page_soup.select_one("header > div > a > img")["src"]
        
        teams.append([team_name, logo_url] + stats)

    # Create DataFrame with basic stats
    columns = ["team", "logo_url", "gp", "pts", "offensive_rebounds", "defensive_rebounds", 
               "reb", "ast", "stl", "blk", "turnovers", "pf"]
    team_stats_df = pd.DataFrame(teams, columns=columns)

    # Convert numeric columns
    numeric_cols = columns[2:]
    team_stats_df[numeric_cols] = team_stats_df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    try:
        # Load games table from SQL database using mysql.connector
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Joynera4919",
            database="unrivaled"
        )
        games = pd.read_sql_query("SELECT * FROM games", connection)
        connection.close()

        # Calculate PAPG
        papg_dict = calculate_papg(games)
        papg_df = pd.DataFrame(list(papg_dict.items()), columns=["team", "papg"])
        
        # Merge PAPG into team stats
        team_stats_df = pd.merge(team_stats_df, papg_df, on="team", how="left")
    except Exception as e:
        print(f"Warning: {str(e)}. PAPG will not be included.")
        team_stats_df["papg"] = None

    # Merge with standings
    standings_df = scrape_standings()
    final_df = pd.merge(team_stats_df, standings_df, on="team", how="left")
    
    return final_df

def scrape_standings():
    url = "https://www.unrivaled.basketball/standings"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    teams = []
    tbody = soup.find("tbody")
    rows = tbody.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        team_name = re.sub(r'^\d+\.\s*', '', cols[0].find("a").text.strip())
        
        teams.append([
            team_name,
            int(cols[1].text.strip()),
            int(cols[2].text.strip()),
            float(cols[3].text.strip().replace("%", "")),
            float(cols[4].text.strip()),
            cols[5].text.strip()
        ])

    return pd.DataFrame(teams, columns=["team", "wins", "losses", "win_pct", "games_behind", "streak"])

# --------------------------
# Database Functions
# --------------------------
def insert_team_stats_into_database(team_stats_df):
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Joynera4919",
            database="unrivaled"
        )
        cursor = connection.cursor()

        # Create table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_stats (
            team VARCHAR(50) PRIMARY KEY,
            logo_url VARCHAR(255),
            gp INT,
            pts FLOAT,
            offensive_rebounds FLOAT,
            defensive_rebounds FLOAT,
            reb FLOAT,
            ast FLOAT,
            stl FLOAT,
            blk FLOAT,
            turnovers FLOAT,
            pf FLOAT,
            wins INT,
            losses INT,
            win_pct FLOAT,
            games_behind FLOAT,
            streak VARCHAR(10),
            papg FLOAT
        )
        """)

        # Insert/update data
        for _, row in team_stats_df.iterrows():
            sql_query = """
            INSERT INTO team_stats (
                team, logo_url, gp, pts, offensive_rebounds, defensive_rebounds, reb, ast, stl, blk, 
                turnovers, pf, wins, losses, win_pct, games_behind, streak, papg
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                gp = VALUES(gp), pts = VALUES(pts), offensive_rebounds = VALUES(offensive_rebounds), 
                defensive_rebounds = VALUES(defensive_rebounds), reb = VALUES(reb),
                ast = VALUES(ast), stl = VALUES(stl), blk = VALUES(blk),
                turnovers = VALUES(turnovers), pf = VALUES(pf),
                wins = VALUES(wins), losses = VALUES(losses), win_pct = VALUES(win_pct),
                games_behind = VALUES(games_behind), streak = VALUES(streak),
                papg = VALUES(papg), logo_url = VALUES(logo_url)
            """
            data = (
                row["team"], 
                row["logo_url"],
                row.get("gp", 0), 
                row.get("pts", 0),
                row.get("offensive_rebounds", 0),
                row.get("defensive_rebounds", 0),
                row.get("reb", 0),
                row.get("ast", 0),
                row.get("stl", 0),
                row.get("blk", 0),
                row.get("turnovers", 0),
                row.get("pf", 0),
                row.get("wins", 0),
                row.get("losses", 0),
                row.get("win_pct", 0),
                row.get("games_behind", 0),
                row.get("streak", ""),
                row.get("papg", None)
            )
            cursor.execute(sql_query, data)

        connection.commit()
        print(f"Successfully processed {len(team_stats_df)} team records")

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# --------------------------
# Main Execution
# --------------------------
def scrape_and_store_team_stats():
    print("Starting team stats scrape...")
    team_stats_df = scrape_team_stats()
    
    print("Saving to CSV...")
    team_stats_df.to_csv("data/unrivaled/csv/unrivaled_team_stats.csv", index=False)
    
    print("Updating database...")
    insert_team_stats_into_database(team_stats_df)
    
    print("Process completed successfully!")

if __name__ == "__main__":
    scrape_and_store_team_stats()