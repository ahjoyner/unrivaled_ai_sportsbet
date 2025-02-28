/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useState } from "react";
import { db } from "@/firebase";
import { collection, getDocs } from "firebase/firestore";

export default function Home() {
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch players from Firestore
  useEffect(() => {
    const fetchPlayers = async () => {
      try {
        // Fetch prop_lines collection
        const propLinesCollection = collection(db, "prop_lines");
        const propLinesSnapshot = await getDocs(propLinesCollection);

        // Fetch players collection
        const playersCollection = collection(db, "players");
        const playersSnapshot = await getDocs(playersCollection);

        // Create a map of players by name for quick lookup
        const playersMap = new Map();
        playersSnapshot.docs.forEach((doc) => {
          const playerData = doc.data();
          playersMap.set(playerData.name, {
            headshot_url: playerData.headshot_url || null,
          });
        });

        // Map through prop_lines and merge with player data
        const playerProjections = propLinesSnapshot.docs.map((doc) => {
          const propLineData = doc.data();
          const playerData = propLineData.Player_Data;
          const projectionData = propLineData.Projection_Data;

          // Find the matching player in the players collection
          const playerInfo = playersMap.get(playerData.display_name) || {};

          return {
            id: doc.id, // This is the player_id
            displayName: playerData.display_name || "Unknown Player",
            team: playerData.team || "Unknown Team",
            position: playerData.position || "N/A",
            headshot_url: playerInfo.headshot_url || null, // Get headshot_url from players collection
            prop_line: projectionData.line_score || 0,
            stat_type: projectionData.stat_type || "Points",
          };
        });

        setPlayers(playerProjections);
      } catch (error) {
        console.error("Error fetching players:", error);
        setError(error.message);
      } finally {
        setLoading(false);
      }
    };
    fetchPlayers();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-gray-900">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex justify-center items-center h-screen bg-gray-900 text-red-500">
        Error: {error}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 p-8">
      <header className="fixed top-0 left-0 w-full bg-gray-800 py-4 shadow-lg z-50">
        <div className="container mx-auto px-4 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-white flex items-center">
            <img src="/logo.jpg" alt="MODUEL Logo" className="h-10 mr-2" />
            MODUEL Prop Confidence
          </h1>
        </div>
      </header>
      <div className="container mx-auto p-8 pt-24 relative z-10">
        <h2 className="text-2xl font-bold text-white mb-6">Players</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {players.map((player, index) => (
            <div key={index} className="bg-gray-800 rounded-lg p-6 text-center shadow-lg">
              <div className="w-32 h-32 bg-gray-700 rounded-full mx-auto mb-4 overflow-hidden">
                {player.headshot_url ? (
                  <img
                    src={player.headshot_url}
                    alt={player.displayName}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full bg-gray-700"></div>
                )}
              </div>
              <p className="text-gray-400 text-sm">
                {player.team} - {player.position}
              </p>
              <p className="text-white text-xl font-semibold mt-2">{player.displayName}</p>
              <p className="text-gray-400 text-sm mt-2">
                Prop Line: <span className="text-gray-300">{player.prop_line}</span>
              </p>
              <p className="text-gray-400 text-sm mt-2">
                Stat: <span className="text-gray-300">{player.stat_type}</span>
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}