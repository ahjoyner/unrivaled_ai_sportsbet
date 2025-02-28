import requests
import re
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from bs4 import BeautifulSoup

# Initialize Firebase
cred = credentials.Certificate("secrets/firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client(database_id="unrivaled-db")

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
        logo_element = team_page_soup.select_one("header > div > a > img")
        logo_url = "https://www.unrivaled.basketball" + logo_element["src"] if logo_element else ""

        teams.append([team_name, logo_url] + stats)

    # Create DataFrame with updated stats structure
    columns = ["team", "logo_url", "gp", "pts", "offensive_rebounds", "defensive_rebounds",
               "reb", "ast", "stl", "blk", "turnovers", "pf"]
    team_stats_df = pd.DataFrame(teams, columns=columns)

    # Convert numeric columns
    numeric_cols = columns[2:]
    team_stats_df[numeric_cols] = team_stats_df[numeric_cols].apply(pd.to_numeric, errors='coerce')

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
            int(cols[1].text.strip()),  # Wins
            int(cols[2].text.strip()),  # Losses
            float(cols[3].text.strip().replace("%", "")),  # Win Percentage
            float(cols[4].text.strip()),  # Games Behind
            int(cols[5].text.strip()),  # Points
            int(cols[6].text.strip()),  # Points Allowed (PA)
            cols[8].text.strip()  # Streak
        ])

    return pd.DataFrame(teams, columns=["team", "wins", "losses", "win_pct", "games_behind", "pts", "pa", "streak"])

# --------------------------
# Database Functions
# --------------------------
def insert_team_stats_into_firestore(team_stats_df):
    for _, row in team_stats_df.iterrows():
        team_name = row["team"]
        team_data = row.to_dict()
        del team_data["team"]

        db.collection("teams").document(team_name).set(team_data)

    print(f"✅ Inserted/Updated {len(team_stats_df)} team records into Firestore.")

# --------------------------
# Main Execution
# --------------------------
def scrape_and_store_team_stats():
    print("🔄 Starting team stats scrape...")
    team_stats_df = scrape_team_stats()

    print("💾 Saving to CSV...")
    team_stats_df.to_csv("data/unrivaled/csv/unrivaled_team_stats.csv", index=False)

    print("🚀 Updating Firestore database...")
    insert_team_stats_into_firestore(team_stats_df)

    print("✅ Process completed successfully!")

if __name__ == "__main__":
    scrape_and_store_team_stats()
