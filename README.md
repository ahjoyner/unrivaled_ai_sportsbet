# unrivaled_ai_sportsbet
An API for scraping data for Unrivaled 3v3 Women's Basketball League &amp; making predictions on player props from PrizePicks.

1. Run *scrape.go* to pull all prop and player data from PrizePicks. It will be saved to **data/unrivaled/unr_bets.json**
2. Run *unr_projections.go* to read **unr_bets.json** and parse all player_ids to **data/unrivaled/player_ids.json**
3. Run *unr_player_fetcher* to pull each individual player data from their PrizePicks links & ID.
