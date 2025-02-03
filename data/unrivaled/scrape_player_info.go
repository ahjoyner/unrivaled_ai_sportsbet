package main

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
)

type BetData struct {
	Data []struct {
		Relationships struct {
			NewPlayer struct {
				Data struct {
					ID string `json:"id"`
				} `json:"data"`
			} `json:"new_player"`
		} `json:"relationships"`
	} `json:"data"`
}

type PlayerData struct {
	ID         string `json:"id"`
	Name       string `json:"name"`
	Position   string `json:"position"`
	Team       string `json:"team"`
	TeamName   string `json:"team_name"`
	Market     string `json:"market"`
	ImageURL   string `json:"image_url"`
	League     string `json:"league"`
	UpdatedAt  string `json:"updated_at"`
	CreatedAt  string `json:"created_at"`
	PlayerType string `json:"type"`
}

func main() {
	// Load bets.json
	betsFile := "unr_bets.json"
	betsData, err := os.ReadFile(betsFile)
	if err != nil {
		log.Fatalf("Error reading bets.json: %v", err)
	}

	// Parse JSON to extract player IDs
	var bets BetData
	err = json.Unmarshal(betsData, &bets)
	if err != nil {
		log.Fatalf("Error parsing bets.json: %v", err)
	}

	// HTTP client with TLS configuration
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: false},
	}
	client := &http.Client{Transport: tr}

	// Collect all player data
	allPlayers := []PlayerData{}

	// Fetch player data for each player ID
	for _, bet := range bets.Data {
		playerID := bet.Relationships.NewPlayer.Data.ID
		url := fmt.Sprintf("https://api.prizepicks.com/players/%s", playerID)

		// Create HTTP GET request
		req, err := http.NewRequest("GET", url, nil)
		if err != nil {
			log.Printf("Error creating request for player %s: %v", playerID, err)
			continue
		}

		// Add headers
		req.Header.Set("Host", "api.prizepicks.com")
		req.Header.Set("Sec-Ch-Ua", `"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"`)
		req.Header.Set("Accept", "application/json")
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Sec-Ch-Ua-Mobile", "?0")
		req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")
		req.Header.Set("Sec-Ch-Ua-Platform", `"Windows"`)
		req.Header.Set("Origin", "https://app.prizepicks.com")
		req.Header.Set("Sec-Fetch-Site", "same-site")
		req.Header.Set("Sec-Fetch-Mode", "cors")
		req.Header.Set("Sec-Fetch-Dest", "empty")
		req.Header.Set("Referer", "https://app.prizepicks.com/")
		req.Header.Set("Accept-Language", "en-US,en;q=0.9")

		// Send the request
		resp, err := client.Do(req)
		if err != nil {
			log.Printf("Error fetching data for player %s: %v", playerID, err)
			continue
		}
		defer resp.Body.Close()

		// Check response status
		if resp.StatusCode != http.StatusOK {
			log.Printf("Non-OK HTTP status for player %s: %s", playerID, resp.Status)
			continue
		}

		// Read response body
		bodyText, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			log.Printf("Error reading response for player %s: %v", playerID, err)
			continue
		}

		// Parse player JSON data
		var player struct {
			Data struct {
				ID         string `json:"id"`
				Type       string `json:"type"`
				Attributes struct {
					Name      string `json:"name"`
					Position  string `json:"position"`
					Team      string `json:"team"`
					TeamName  string `json:"team_name"`
					Market    string `json:"market"`
					ImageURL  string `json:"image_url"`
					League    string `json:"league"`
					UpdatedAt string `json:"updated_at"`
					CreatedAt string `json:"created_at"`
				} `json:"attributes"`
			} `json:"data"`
		}
		err = json.Unmarshal(bodyText, &player)
		if err != nil {
			log.Printf("Error parsing player data for player %s: %v", playerID, err)
			continue
		}

		// Append player data to allPlayers
		allPlayers = append(allPlayers, PlayerData{
			ID:         player.Data.ID,
			Name:       player.Data.Attributes.Name,
			Position:   player.Data.Attributes.Position,
			Team:       player.Data.Attributes.Team,
			TeamName:   player.Data.Attributes.TeamName,
			Market:     player.Data.Attributes.Market,
			ImageURL:   player.Data.Attributes.ImageURL,
			League:     player.Data.Attributes.League,
			UpdatedAt:  player.Data.Attributes.UpdatedAt,
			CreatedAt:  player.Data.Attributes.CreatedAt,
			PlayerType: player.Data.Type,
		})
	}

	// Save all player data to a single JSON file
	outputFile := "unr_all_players.json"
	allPlayersJSON, err := json.MarshalIndent(allPlayers, "", "  ")
	if err != nil {
		log.Fatalf("Error marshalling all players data: %v", err)
	}
	err = os.WriteFile(outputFile, allPlayersJSON, 0o644)
	if err != nil {
		log.Fatalf("Error saving all players data to file: %v", err)
	}

	fmt.Printf("All player data saved to %s\n", outputFile)
}
