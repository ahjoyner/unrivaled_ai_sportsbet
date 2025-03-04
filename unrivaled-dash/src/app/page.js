/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import annotationPlugin from "chartjs-plugin-annotation";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { db } from "./firebase.js";
import { 
  collection, 
  getDocs, 
  doc, 
  getDoc,
  query, 
  orderBy, 
  limit 
} from "firebase/firestore";
import { useMediaQuery } from "react-responsive";

// Utility function to normalize names
const normalizeName = (name) => {
  return name.toLowerCase().replace(/ /g, "_"); // Replace spaces with underscores
};

const cleanReasonText = (text) => {
  return text.replace(/^\*\*.*:\*\*\s*/, "").replace(/^\*\*.*\*\*:\s*/, "");
};

const StatItem = ({ label, value, icon, unit, isShootingStat }) => (
  <div className="stat-item mobile-smaller-text flex justify-between items-center gap-2">
    <span className="text-gray-300">
      {icon && <span className="mr-2">{icon}</span>}
      {label}
    </span>
    <span className="text-white font-semibold">
      {isShootingStat ? `${value.made}-${value.attempted}` : value} {unit && <span className="text-sm text-gray-400">{unit}</span>}
    </span>
  </div>
);

export default function Home() {
  const [players, setPlayers] = useState([]);
  const [filteredPlayers, setFilteredPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [confidenceData, setConfidenceData] = useState({});
  const [last5GamesModal, setLast5GamesModal] = useState(null);
  const [gameStatsModal, setGameStatsModal] = useState(null);
  const [reasonIndex, setReasonIndex] = useState(1);

  const isMobile = useMediaQuery({ query: "(max-width: 768px)" });

  ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    annotationPlugin
  );

  // Fetch players and their prop lines from Firestore
  useEffect(() => {
    const fetchPlayers = async () => {
      try {
        // Fetch prop_lines collection
        const propLinesCollection = collection(db, "prop_lines");
        const propLinesSnapshot = await getDocs(propLinesCollection);

        // Fetch players collection
        const playersCollection = collection(db, "players");
        const playersSnapshot = await getDocs(playersCollection);

        // Create a map of players by normalized name for quick lookup
        const playersMap = new Map();
        playersSnapshot.docs.forEach((playerDoc) => {
          const playerData = playerDoc.data();
          const normalizedName = normalizeName(playerDoc.id); // Normalize the player name
          playersMap.set(normalizedName, {
            headshot_url: playerData.headshot_url || null,
          });
        });

        // Map through prop_lines and merge with player data
        const playerProjections = await Promise.all(
          propLinesSnapshot.docs.map(async (propLineDoc) => {
            const propLineData = propLineDoc.data();
            const playerData = propLineData.player_data;
            const projectionData = propLineData.projection_data;

            // Normalize the player name for comparison
            const normalizedName = normalizeName(playerData.display_name);
            const playerInfo = playersMap.get(normalizedName) || {};

            // Fetch analysis results for the player from players/{player_name}/analysis_results/latest
            const playerNameFirestore = playerData.display_name.replace(/ /g, "_");
            const analysisDocRef = doc(db, `players/${playerNameFirestore}/analysis_results`, "latest"); // Use "latest" as the document ID
            const analysisSnapshot = await getDoc(analysisDocRef);
            const analysisData = analysisSnapshot.exists() ? analysisSnapshot.data() : {};

            return {
              id: propLineDoc.id, // This is the game_id from prop_lines
              displayName: playerData.display_name || "Unknown Player",
              normalizedName: normalizedName, // Store normalized name for filtering
              team: playerData.team || "Unknown Team",
              position: playerData.position || "N/A",
              headshot_url: playerInfo.headshot_url || null, // Get headshot_url from players collection
              prop_line: projectionData.line_score || 0,
              stat_type: projectionData.stat_type || "Points",
              confidence_level: analysisData.confidence_level || 0, // Default to 0 if not found
              reason: { // Map reason_1, reason_2, reason_3, reason_4, and final_conclusion
                "1": analysisData.reason_1 || "", // Map reason_1
                "2": analysisData.reason_2 || "", // Map reason_2
                "3": analysisData.reason_3 || "", // Map reason_3
                "4": analysisData.reason_4 || "", // Map reason_4
                "final_conclusion": analysisData.final_conclusion || "", // Map final_conclusion
              },
            };
          })
        );

        setPlayers(playerProjections);
        setFilteredPlayers(playerProjections);
      } catch (error) {
        console.error("Error fetching players:", error);
        setError(error.message);
      } finally {
        setLoading(false);
      }
    };
    fetchPlayers();
  }, []);

  // Poll Firestore for each player's analysis result
  useEffect(() => {
    if (players.length === 0) return;

    const interval = setInterval(async () => {
      let updatedResults = {};
      for (const player of players) {
        try {
          const playerNameFirestore = player.displayName.replace(/ /g, "_");
          const analysisDoc = doc(db, `players/${playerNameFirestore}/analysis_results`, "latest"); // Use "latest" as the document ID
          const analysisSnapshot = await getDoc(analysisDoc);
          if (analysisSnapshot.exists()) {
            updatedResults[player.id] = analysisSnapshot.data();
          }
        } catch (err) {
          console.error(`Error fetching analysis for ${player.displayName}:`, err);
        }
      }
      console.log("Polled Firestore analysis results:", updatedResults);
      setConfidenceData((prev) => ({ ...prev, ...updatedResults }));
    }, 5000);

    return () => clearInterval(interval);
  }, [players]);

  // Fetch last 5 games from Firestore
  const openLast5GamesModal = async (player) => {
    try {
      // Replace spaces with underscores in the player name
      const playerNameFirestore = player.displayName.replace(/ /g, "_");
  
      // Fetch the most recent 5 games for the player from players/{player_name}/games
      const gamesCollection = collection(db, `players/${playerNameFirestore}/games`);
      console.log(`Querying collection: players/${playerNameFirestore}/games`);
  
      // Query to get the most recent 5 games sorted by game_date in descending order
      const gamesQuery = query(
        gamesCollection,
        orderBy("game_date", "desc"), // Sort by game_date in descending order
        limit(5) // Limit to 5 most recent games
      );
  
      const gamesSnapshot = await getDocs(gamesQuery);
      console.log("Games Snapshot:", gamesSnapshot); // Debugging: Log the snapshot
  
      if (gamesSnapshot.empty) {
        console.log("No games found for player:", playerNameFirestore);
        return;
      }
  
      const gamesData = gamesSnapshot.docs.map((doc) => {
        const gameData = doc.data();
        console.log("Game Data:", gameData); // Debugging: Log each game's data
        return {
          game_id: doc.id,
          ...gameData, // This includes the stats field
        };
      });
  
      console.log("Fetched last 5 games for", playerNameFirestore, gamesData);
      setLast5GamesModal({ ...player, last_5_games: gamesData });
    } catch (error) {
      console.error("Error fetching last 5 games:", error);
    }
  };

  // Fetch game stats from Firestore
  const fetchGameStats = async (gameId, playerName) => {
    try {
      // Replace spaces with underscores in the player name
      const playerNameFirestore = playerName.replace(/ /g, "_");
  
      // Fetch the player's team from players/{player_name}/team
      const playerRef = doc(db, `players/${playerNameFirestore}`);
      const playerDoc = await getDoc(playerRef);
  
      if (!playerDoc.exists()) {
        console.error("Player document not found:", playerNameFirestore);
        return;
      }
  
      const playerTeam = playerDoc.data().team; // Get the player's team
      console.log("Player Team:", playerTeam); // Debugging: Log the player's team
  
      // Fetch game stats from players/{player_name}/games/{game_id}
      const gameStatsRef = doc(db, `players/${playerNameFirestore}/games/${gameId}`);
      const gameStatsDoc = await getDoc(gameStatsRef);
  
      if (gameStatsDoc.exists()) {
        const gameStats = gameStatsDoc.data();
        console.log("Game Stats:", gameStats); // Debugging: Log game stats
  
        // Fetch game metadata (date, opponent, etc.) from the root games collection
        const gameMetadataRef = doc(db, "games", gameId);
        const gameMetadataDoc = await getDoc(gameMetadataRef);
  
        if (gameMetadataDoc.exists()) {
          const gameMetadata = gameMetadataDoc.data();
          console.log("Game Metadata:", gameMetadata); // Debugging: Log game metadata
  
          // Determine the opponent by checking which team is NOT the player's team
          let opponent;
          if (gameMetadata.home_team === playerTeam) {
            opponent = gameMetadata.away_team;
          } else if (gameMetadata.away_team === playerTeam) {
            opponent = gameMetadata.home_team;
          } else {
            // Fallback: If the player's team doesn't match either team in the metadata, log an error
            console.error(
              "Player's team does not match home_team or away_team in game metadata."
            );
            opponent = "Unknown Opponent"; // Fallback value
          }
  
          // Merge player stats with game metadata
          setGameStatsModal({
            ...gameStats, // Player-specific stats
            ...gameMetadata, // Game metadata (date, opponent, etc.)
            player_name: playerName,
            game_id: gameId,
            opponent: opponent, // Add the opponent dynamically
          });
        } else {
          console.error("Game metadata not found for game_id:", gameId);
        }
      } else {
        console.error("Game stats not found for player:", playerName, "game_id:", gameId);
      }
    } catch (error) {
      console.error("Error fetching game stats:", error);
    }
  };

  // Filter players based on search query
  useEffect(() => {
    const normalizedQuery = normalizeName(searchQuery); // Normalize the search query
    const filtered = players.filter((player) =>
      player.normalizedName.includes(normalizedQuery) // Compare normalized names
    );
    setFilteredPlayers(filtered);
  }, [searchQuery, players]);

  // Reset reasonIndex whenever the selected player changes
  useEffect(() => {
    setReasonIndex(1);
  }, [selectedPlayer]);

  // Functions for cycling through reason sections
  const handleNextReason = () => {
    setReasonIndex((prev) => (prev < 5 ? prev + 1 : 1));
  };

  const handlePrevReason = () => {
    setReasonIndex((prev) => (prev > 1 ? prev - 1 : 5));
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-gray-900">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500"></div>
        <span className="ml-4 text-orange-500 text-lg">Loading...</span>
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
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-800">
      {/* Header */}
      <header className="fixed top-0 left-0 w-full bg-gradient-to-r from-blue-600 to-purple-600 py-4 shadow-lg z-50">
        <div className="container mx-auto px-4 flex justify-between items-center">
          <h1 className="text-xl sm:text-3xl font-bold text-white flex items-center">
            <img src="/logo.jpg" alt="MODUEL Logo" className="h-8 sm:h-10 mr-2 rounded-full" />
            MODUEL Prop Confidence
          </h1>
          <input
            type="text"
            placeholder="Search players..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-white/20 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-white w-32 sm:w-64 placeholder:text-white/70"
          />
        </div>
      </header>

      {/* Main Content */}
      <motion.div
        className="container mx-auto p-4 sm:p-8 pt-24 sm:pt-32 relative z-10" // Increased top padding for mobile
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        <div className={`grid ${isMobile ? "grid-cols-2" : "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4"} gap-4 sm:gap-6`}>
          {filteredPlayers.map((player, index) => {
            const confidence = player.confidence_level || 0;
            const confidenceColor = confidence >= 51 ? "bg-gradient-to-r from-green-400 to-blue-500" : "bg-gradient-to-r from-red-400 to-pink-500";
            return (
              <motion.div
                key={index}
                className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg p-4 sm:p-6 text-center shadow-xl relative hover:shadow-2xl transition-shadow"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                whileHover={{ scale: 1.05 }}
              >
                <button
                  className="absolute top-2 right-2 bg-gray-700 text-white px-2 py-1 rounded-lg hover:bg-gray-600 transition-colors"
                  onClick={() => openLast5GamesModal(player)}
                >
                  L5
                </button>
                <div className="w-24 h-24 sm:w-32 sm:h-32 bg-gray-700 rounded-full mx-auto mb-4 overflow-hidden">
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
                <p className={`text-white ${isMobile ? "text-base" : "text-lg sm:text-xl"} font-semibold mt-2`}>{player.displayName}</p>
                <p className={`text-white ${isMobile ? "text-lg" : "text-xl sm:text-2xl"} font-bold mt-4`}>
                  {player.prop_line} <span className="text-sm text-gray-400">points</span>
                </p>
                <div className="mt-6">
                  <div className="w-full bg-gray-700 rounded-full h-2.5">
                    <div
                      className={`h-2.5 rounded-full confidence-bar ${confidenceColor} ${confidence >= 70 ? "pulse" : ""}`}
                      style={{
                        width: `${(confidence / 100) * 100}%`,
                        transition: "width 0.5s ease-in-out",
                      }}
                    ></div>
                  </div>
                  <div className="flex justify-between text-gray-400 text-sm mt-2">
                    <span>0</span>
                    <span>100</span>
                  </div>
                </div>
                <button
                  className="mt-4 bg-orange-500 text-white px-4 py-2 rounded-lg hover:bg-orange-600 transition-colors w-full"
                  onClick={() =>
                    setSelectedPlayer({
                      ...player,
                      reason: player.reason, // Pass the reason map directly
                    })
                  }
                >
                  <b>View Analysis</b>
                </button>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* Selected Player Modal */}
      {selectedPlayer && (
        <motion.div
          className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="modal p-4 w-11/12 sm:max-w-2xl relative bg-gray-800 rounded-lg overflow-y-auto max-h-[90vh]" // Increased width and added scroll
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0.9 }}
          >
            <button
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-300"
              onClick={() => setSelectedPlayer(null)}
            >
              &times;
            </button>
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-4">
              {selectedPlayer.displayName} ({selectedPlayer.position} - {selectedPlayer.team})
            </h2>
            <div className="bg-gray-700 p-3 rounded-lg mb-4"> {/* Reduced padding */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2"> {/* Reduced gap */}
                <div className="flex flex-col items-center">
                  <span className="text-orange-400 text-sm font-semibold">Confidence</span> {/* Reduced font size */}
                  <span className="text-white text-xl font-bold"> {/* Reduced font size */}
                    {selectedPlayer.confidence_level || 0}
                  </span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-orange-400 text-sm font-semibold">Line</span> {/* Reduced font size */}
                  <span className="text-white text-xl font-bold"> {/* Reduced font size */}
                    {selectedPlayer.prop_line} <span className="text-xs text-gray-400">points</span> {/* Reduced font size */}
                  </span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-orange-400 text-sm font-semibold">Stat</span> {/* Reduced font size */}
                  <span className="text-white text-xl font-bold"> {/* Reduced font size */}
                    {selectedPlayer.stat_type}
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-4"> {/* Reduced margin */}
              <h3 className="text-lg font-semibold text-orange-400 mb-2"> {/* Reduced margin */}
                🧠 Reason Breakdown
              </h3>
              <div className="bg-gray-700 p-3 rounded-lg"> {/* Reduced padding */}
                <div className="flex items-center justify-between mb-2"> {/* Reduced margin */}
                  <span className="text-gray-300 text-sm"> {/* Reduced font size */}
                    {reasonIndex === 1 && "📊 Performance Against Opposing Team"}
                    {reasonIndex === 2 && "📈 Scoring Trends"}
                    {reasonIndex === 3 && "🛠️ Opposing Team's Defensive Weaknesses"}
                    {reasonIndex === 4 && "🔍 Recent Performance"}
                  </span>
                  <span className="text-gray-400 text-xs"> {/* Reduced font size */}
                    Section {reasonIndex} of 4
                  </span>
                </div>
                <p className="text-white text-sm"> {/* Reduced font size */}
                  {cleanReasonText(selectedPlayer.reason[String(reasonIndex)] || "No text available.")}
                </p>
              </div>
              <div className="flex justify-between mt-2"> {/* Reduced margin */}
                {reasonIndex > 1 && (
                  <button
                    className="px-3 py-1 bg-gray-700 text-white rounded-lg hover:bg-gray-600 flex items-center text-sm" 
                    onClick={handlePrevReason}
                  >
                    <span className="mr-1">&larr;</span> Previous
                  </button>
                )}
                {reasonIndex < 4 && (
                  <button
                    className="px-3 py-1 bg-gray-700 text-white rounded-lg hover:bg-gray-600 flex items-center text-sm"
                    onClick={handleNextReason}
                  >
                    Next <span className="ml-1">&rarr;</span>
                  </button>
                )}
              </div>
              {/* Display Final Conclusion */}
              <div className="mt-4"> {/* Reduced margin */}
                <h3 className="text-lg font-semibold text-orange-400 mb-2"> {/* Reduced margin */}
                  🏆 Final Conclusion
                </h3>
                <div className="bg-gray-700 p-3 rounded-lg"> {/* Reduced padding */}
                  <p className="text-white text-sm"> {/* Reduced font size */}
                    {cleanReasonText(selectedPlayer.reason["final_conclusion"] || "No final conclusion available.")}
                  </p>
                </div>
              </div>
            </div>
            <button
              className="mt-4 bg-orange-500 text-white px-4 py-2 rounded-lg hover:bg-orange-600 transition-colors w-full text-sm"
              onClick={() => setSelectedPlayer(null)}
            >
              Close
            </button>
          </motion.div>
        </motion.div>
      )}

      {/* Last 5 Games Modal */}
      {last5GamesModal && (
        <motion.div
          className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="modal p-6 w-11/12 sm:max-w-lg relative"
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0.9 }}
          >
            <button
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-300"
              onClick={() => setLast5GamesModal(null)}
            >
              &times;
            </button>
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-4">
              {last5GamesModal.displayName}&apos;s Last 5 Games
            </h2>
            {(() => {
              const games = last5GamesModal.last_5_games || [];

              // Reverse the games array to display oldest to newest (left to right)
              const reversedGames = [...games].reverse();

              // Debugging: Log the fetched games
              console.log("Fetched Games (Reversed):", reversedGames);

              // Extract labels (dates) and data (points)
              const labels = reversedGames.map((game) => {
                if (game.game_date) {
                  const gameDate = game.game_date.toDate ? game.game_date.toDate() : new Date(game.game_date);
                  // Use UTC to avoid timezone issues
                  return gameDate.toLocaleDateString("en-US", { timeZone: "UTC" });
                } else {
                  return "No Date"; // Fallback for missing or invalid dates
                }
              });

              const data = reversedGames.map((game) => Number(game.pts || 0)); // Fallback to 0 if pts is missing

              // Debugging: Log the labels and data
              console.log("Labels (Reversed):", labels);
              console.log("Data (Reversed):", data);

              const chartData = {
                labels: labels,
                datasets: [
                  {
                    label: "Points",
                    data: data,
                    backgroundColor: data.map((pts) =>
                      pts >= last5GamesModal.prop_line ? "rgba(75, 192, 192, 0.6)" : "rgba(255, 99, 132, 0.6)"
                    ),
                    borderColor: data.map((pts) =>
                      pts >= last5GamesModal.prop_line ? "rgba(75, 192, 192, 1)" : "rgba(255, 99, 132, 1)"
                    ),
                    borderWidth: 1,
                  },
                ],
              };

              const chartOptions = {
                responsive: true,
                plugins: {
                  legend: {
                    display: false,
                  },
                  title: {
                    display: true,
                    text: "Points in Last 5 Games",
                    color: "#fff",
                  },
                  annotation: {
                    annotations: {
                      propLine: {
                        type: "line",
                        yMin: last5GamesModal.prop_line,
                        yMax: last5GamesModal.prop_line,
                        borderColor: "rgba(255, 255, 255, 0.5)",
                        borderWidth: 2,
                        borderDash: [10, 5],
                      },
                    },
                  },
                },
                scales: {
                  x: {
                    ticks: {
                      color: "#fff",
                    },
                    grid: {
                      color: "rgba(255, 255, 255, 0.1)",
                    },
                  },
                  y: {
                    ticks: {
                      color: "#fff",
                    },
                    grid: {
                      color: "rgba(255, 255, 255, 0.1)",
                    },
                  },
                },
                onClick: (event, elements) => {
                  if (elements.length > 0) {
                    const clickedIndex = elements[0].index;
                    const clickedGame = reversedGames[clickedIndex]; // Use reversedGames for correct index
                    fetchGameStats(clickedGame.game_id, last5GamesModal.displayName);
                  }
                },
              };

              return (
                <div className="chart-container">
                  <Bar data={chartData} options={chartOptions} />
                </div>
              );
            })()}
            <button
              className="mt-4 bg-gray-700 text-white px-4 py-2 rounded-lg hover:bg-gray-600"
              onClick={() => setLast5GamesModal(null)}
            >
              Close
            </button>
          </motion.div>
        </motion.div>
      )}

      {/* Game Stats Modal */}
      {gameStatsModal && (
        <motion.div
          className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="modal p-6 w-11/12 sm:max-w-2xl relative max-h-[90vh] overflow-y-auto"
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0.9 }}
          >
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-4 mobile-smaller-heading">
              🏀 Game Stats for {gameStatsModal.player_name} vs. {gameStatsModal.opponent}
            </h2>
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-gray-700 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-orange-400 mb-3 mobile-smaller-heading">Basic Stats</h3>
                <div className="space-y-2">
                  <StatItem label="Points" value={gameStatsModal.pts} icon="🔥" />
                  <StatItem label="Rebounds" value={gameStatsModal.reb} icon="🏀" />
                  <StatItem label="Assists" value={gameStatsModal.ast} icon="🎯" />
                  <StatItem label="Steals" value={gameStatsModal.stl} icon="⛹️‍♀️" />
                  <StatItem label="Blocks" value={gameStatsModal.blk} icon="🚫" />
                  <StatItem label="Turnovers" value={gameStatsModal.turnovers} icon="🔄" />
                  <StatItem label="Personal Fouls" value={gameStatsModal.pf} icon="⚠️" />
                </div>
              </div>
              <div className="bg-gray-700 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-orange-400 mb-3 mobile-smaller-heading">Shooting Stats</h3>
                <div className="space-y-2">
                  <StatItem 
                    label="Field Goals" 
                    value={{ made: gameStatsModal.fg_m, attempted: gameStatsModal.fg_a }}
                    isShootingStat
                  />
                  <StatItem
                    label="Field Goal %"
                    value={(
                      (gameStatsModal.fg_m / gameStatsModal.fg_a * 100).toFixed(1))
                    }
                    unit="%"
                  />
                  <StatItem 
                    label="3-Pointers" 
                    value={{ made: gameStatsModal.three_pt_m, attempted: gameStatsModal.three_pt_a }}
                    isShootingStat
                  />
                  <StatItem
                    label="3-Point %"
                    value={(
                      (gameStatsModal.three_pt_m / gameStatsModal.three_pt_a * 100).toFixed(1))
                    }
                    unit="%"
                  />
                  <StatItem 
                    label="Free Throws" 
                    value={{ made: gameStatsModal.ft_m, attempted: gameStatsModal.ft_a }}
                    isShootingStat
                  />
                  <StatItem
                    label="Free Throw %"
                    value={(
                      (gameStatsModal.ft_m / gameStatsModal.ft_a * 100).toFixed(1))
                    }
                    unit="%"
                  />
                </div>
              </div>
              <div className="bg-gray-700 p-4 rounded-lg col-span-full">
                <h3 className="text-lg font-semibold text-orange-400 mb-3 mobile-smaller-heading">Advanced Stats</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <StatItem label="Minutes Played" value={gameStatsModal.min} unit="min" />
                  <StatItem label="Offensive Rebounds" value={gameStatsModal.offensive_rebounds} />
                  <StatItem label="Defensive Rebounds" value={gameStatsModal.defensive_rebounds} />
                  <StatItem label="Game Date" value={new Date(gameStatsModal.game_date).toLocaleDateString()} />
                </div>
              </div>
            </div>
            <button
              className="mt-6 bg-orange-500 text-white px-4 py-2 rounded-lg hover:bg-orange-600 transition-colors"
              onClick={() => setGameStatsModal(null)}
            >
              Close
            </button>
          </motion.div>
        </motion.div>
      )}

      {/* Footer */}
      <footer className="bg-gray-800 text-white py-6 mt-8">
        <div className="container mx-auto px-4 text-center">
          <p className="text-gray-400">&copy; 2023 MODUEL. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}