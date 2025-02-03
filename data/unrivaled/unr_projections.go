package main

import (
	"encoding/json"
	"fmt"
	"os"
)

type ProjectionData struct {
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

func main() {
	// Read unr_bets.json
	file, err := os.ReadFile("data/unrivaled/unr_bets.json")
	if err != nil {
		fmt.Println("Error reading unr_bets.json:", err)
		return
	}

	// Parse JSON
	var projections ProjectionData
	err = json.Unmarshal(file, &projections)
	if err != nil {
		fmt.Println("Error unmarshalling JSON:", err)
		return
	}

	// Extract unique player IDs
	playerIDMap := make(map[string]bool)
	for _, proj := range projections.Data {
		playerID := proj.Relationships.NewPlayer.Data.ID
		playerIDMap[playerID] = true
	}

	// Convert map to a slice
	playerIDs := make([]string, 0, len(playerIDMap))
	for id := range playerIDMap {
		playerIDs = append(playerIDs, id)
	}

	// Write player IDs to player_ids.json
	playerIDsJSON, err := json.MarshalIndent(playerIDs, "", "  ")
	if err != nil {
		fmt.Println("Error marshalling player IDs:", err)
		return
	}

	err = os.WriteFile("data/unrivaled/player_ids.json", playerIDsJSON, 0644)
	if err != nil {
		fmt.Println("Error writing player_ids.json:", err)
		return
	}

	fmt.Println("Successfully wrote player IDs to player_ids.json")
}
