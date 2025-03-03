import json
import sys

def fetch_injury_reports():
    try:
        with open("/Users/ajoyner/unrivaled_ai_sportsbet/data/unrivaled/injury_reports.json", "r") as f:
            return json.load(f).get("injury_reports", [])
    except Exception as e:
        print(f"Error fetching injury reports: {e}", file=sys.stderr)
        return []
