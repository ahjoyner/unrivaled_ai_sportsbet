/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useState } from "react";
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
import { collection, getDocs, doc, getDoc } from "firebase/firestore";

const cleanReasonText = (text) => {
  return text.replace(/^\*\*.*:\*\*\s*/, "").replace(/^\*\*.*\*\*:\s*/, "");
};

const StatItem = ({ label, value, icon, unit, isShootingStat }) => (
  <div className="flex justify-between items-center">
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

        // Create a map of players by name (document ID) for quick lookup
        const playersMap = new Map();
        playersSnapshot.docs.forEach((doc) => {
          const playerData = doc.data();
          playersMap.set(doc.id, { // Use doc.id (name) as the key
            headshot_url: playerData.headshot_url || null,
          });
        });

        // Map through prop_lines and merge with player data
        const playerProjections = propLinesSnapshot.docs.map((doc) => {
          const propLineData = doc.data();
          const playerData = propLineData.player_data;
          const projectionData = propLineData.projection_data;

          // Find the matching player in the players collection using the name (document ID)
          const playerInfo = playersMap.get(playerData.display_name) || {};

          return {
            id: doc.id, // This is the player_id from prop_lines
            displayName: playerData.display_name || "Unknown Player",
            team: playerData.team || "Unknown Team",
            position: playerData.position || "N/A",
            headshot_url: playerInfo.headshot_url || null, // Get headshot_url from players collection
            prop_line: projectionData.line_score || 0,
            stat_type: projectionData.stat_type || "Points",
          };
        });

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
          const analysisDoc = doc(db, "analysis_results", player.id);
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
      const gamesCollection = collection(db, "games");
      const gamesSnapshot = await getDocs(gamesCollection);
      const gamesData = gamesSnapshot.docs
        .map((doc) => doc.data())
        .filter((game) => game.player_name === player.displayName)
        .slice(-5); // Get last 5 games

      console.log("Fetched last 5 games for", player.displayName, gamesData);
      setLast5GamesModal({ ...player, last_5_games: gamesData });
    } catch (error) {
      console.error("Error fetching last 5 games:", error);
    }
  };

  // Fetch game stats from Firestore
  const fetchGameStats = async (gameId, playerName) => {
    try {
      const gameDoc = doc(db, "games", gameId);
      const gameSnapshot = await getDoc(gameDoc);
      if (gameSnapshot.exists()) {
        setGameStatsModal(gameSnapshot.data());
      }
    } catch (error) {
      console.error("Error fetching game stats:", error);
    }
  };

  // Filter players based on search query
  useEffect(() => {
    const filtered = players.filter((player) =>
      player.displayName.toLowerCase().includes(searchQuery.toLowerCase())
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
    <div className="min-h-screen bg-gray-900">
      <header className="fixed top-0 left-0 w-full bg-gray-800 py-4 shadow-lg z-50">
        <div className="container mx-auto px-4 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-white flex items-center">
            <img src="/logo.jpg" alt="MODUEL Logo" className="h-10 mr-2" />
            MODUEL Prop Confidence
          </h1>
          <input
            type="text"
            placeholder="Search players..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-gray-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-orange-500 w-64"
          />
        </div>
      </header>
      <div className="container mx-auto p-8 pt-24 relative z-10">
        <h2 className="text-2xl font-bold text-white mb-6">Players</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {filteredPlayers.map((player, index) => {
            const analysis = confidenceData[player.id] || {};
            const confidence = analysis.confidence_level || 0;
            const confidenceColor = confidence >= 70 ? "bg-gradient-to-r from-green-400 to-blue-500" : "bg-gradient-to-r from-red-400 to-pink-500";
            return (
              <div key={index} className="bg-gray-800 rounded-lg p-6 text-center shadow-lg relative hover:shadow-xl transition-shadow">
                <button
                  className="absolute top-2 right-2 bg-gray-700 text-white px-2 py-1 rounded-lg hover:bg-gray-600 transition-colors"
                  onClick={() => openLast5GamesModal(player)}
                >
                  L5
                </button>
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
                <p className="text-white text-2xl font-bold mt-4">
                  {player.prop_line} <span className="text-sm text-gray-400">points</span>
                </p>
                <div className="mt-6">
                  <div className="w-full bg-gray-700 rounded-full h-2.5">
                    <div
                      className={`h-2.5 rounded-full ${confidenceColor}`}
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
                      reason: {
                        "1": analysis.reason_1 || "",
                        "2": analysis.reason_2 || "",
                        "3": analysis.reason_3 || "",
                        "4": analysis.reason_4 || "",
                        "5": analysis.final_conclusion || "",
                      },
                    })
                  }
                >
                  <b>View Analysis</b>
                </button>
              </div>
            );
          })}
        </div>
      </div>
      {selectedPlayer && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-lg w-full relative">
            <button
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-300"
              onClick={() => setSelectedPlayer(null)}
            >
              &times;
            </button>
            <h2 className="text-2xl font-bold text-white mb-4">
              {selectedPlayer.displayName} ({selectedPlayer.position} - {selectedPlayer.team})
            </h2>
            <div className="bg-gray-700 p-4 rounded-lg mb-6">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="flex flex-col items-center">
                  <span className="text-orange-400 text-lg font-semibold">Confidence</span>
                  <span className="text-white text-2xl font-bold">
                    {confidenceData[selectedPlayer.id]?.confidence_level || 0}
                  </span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-orange-400 text-lg font-semibold">Line</span>
                  <span className="text-white text-2xl font-bold">
                    {selectedPlayer.prop_line} <span className="text-sm text-gray-400">points</span>
                  </span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-orange-400 text-lg font-semibold">Stat</span>
                  <span className="text-white text-2xl font-bold">
                    {selectedPlayer.stat_type}
                  </span>
                </div>
              </div>
            </div>
            <div className="mt-6">
              <h3 className="text-lg font-semibold text-orange-400 mb-4">
                🧠 Reason Breakdown
              </h3>
              <div className="bg-gray-700 p-4 rounded-lg">
                <div className="flex items-center justify-between mb-4">
                  <span className="text-gray-300">
                    {reasonIndex === 1 && "📊 Performance Against Opposing Team"}
                    {reasonIndex === 2 && "📈 Scoring Trends"}
                    {reasonIndex === 3 && "🛠️ Role & Teammate Interactions"}
                    {reasonIndex === 4 && "🔍 Recent Game Flow Analysis"}
                    {reasonIndex === 5 && "🏆 Final Reason for Confidence Level"}
                  </span>
                  <span className="text-gray-400 text-sm">
                    Section {reasonIndex} of 5
                  </span>
                </div>
                <p className="text-white text-lg">
                  {cleanReasonText(selectedPlayer.reason[String(reasonIndex)] || "No text available.")}
                </p>
              </div>
              <div className="flex justify-between mt-4">
                {reasonIndex > 1 && (
                  <button
                    className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 flex items-center"
                    onClick={handlePrevReason}
                  >
                    <span className="mr-2">&larr;</span> Previous
                  </button>
                )}
                {reasonIndex < 5 && (
                  <button
                    className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 flex items-center"
                    onClick={handleNextReason}
                  >
                    Next <span className="ml-2">&rarr;</span>
                  </button>
                )}
              </div>
            </div>
            <button
              className="mt-6 bg-orange-500 text-white px-4 py-2 rounded-lg hover:bg-orange-600 transition-colors w-full"
              onClick={() => setSelectedPlayer(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
      {last5GamesModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-lg w-full relative">
            <button
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-300"
              onClick={() => setLast5GamesModal(null)}
            >
              &times;
            </button>
            <h2 className="text-2xl font-bold text-white mb-4">
              {last5GamesModal.displayName}&apos;s Last 5 Games
            </h2>
            {(() => {
              const games = last5GamesModal.last_5_games || [];
              const labels = games.map((game) =>
                new Date(game.game_date).toLocaleDateString()
              );
              const data = games.map((game) => Number(game.pts));

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
                    const clickedGame = last5GamesModal.last_5_games[clickedIndex];
                    fetchGameStats(clickedGame.game_id, last5GamesModal.displayName);
                  }
                },
              };

              return (
                <div className="w-full h-64">
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
          </div>
        </div>
      )}
      {gameStatsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-2xl w-full">
            <h2 className="text-2xl font-bold text-white mb-4">
              🏀 Game Stats for {gameStatsModal.player_name} vs. {gameStatsModal.opponent}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-gray-700 p-4 rounded-lg">
                <h3 className="text-lg font-semibold text-orange-400 mb-3">Basic Stats</h3>
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
                <h3 className="text-lg font-semibold text-orange-400 mb-3">Shooting Stats</h3>
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
                <h3 className="text-lg font-semibold text-orange-400 mb-3">Advanced Stats</h3>
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
          </div>
        </div>
      )}
      <footer className="bg-gray-800 text-white py-6 mt-8">
        <div className="container mx-auto px-4 text-center">
          <p className="text-gray-400">&copy; 2023 MODUEL. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}