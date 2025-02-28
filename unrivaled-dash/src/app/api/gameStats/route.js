// src/app/api/gameStats/route.js
import mysql from "mysql2/promise";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const gameId = searchParams.get("gameId");
  const playerName = searchParams.get("playerName").replace(/-/g, " ");

  // Create a database connection
  const connection = await mysql.createConnection({
    host: "localhost",
    user: "root",
    password: "Joynera4919",
    database: "unrivaled",
  });

  try {
    // Query the game_stats table
    const query = `
      SELECT 
        game_id, 
        player_name, 
        team, 
        opponent, 
        min, 
        reb, 
        offensive_rebounds, 
        defensive_rebounds, 
        ast, 
        stl, 
        blk, 
        turnovers, 
        pf, 
        pts, 
        game_date, 
        fg_m, 
        fg_a, 
        three_pt_m, 
        three_pt_a, 
        ft_m, 
        ft_a
      FROM game_stats
      WHERE game_id = ? AND player_name = ?
    `;
    const [results] = await connection.execute(query, [gameId, playerName]);

    if (results.length === 0) {
      return new Response(JSON.stringify({ error: "Game stats not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Return the first matching game stats
    return new Response(JSON.stringify(results[0]), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Error fetching game stats:", error);
    return new Response(JSON.stringify({ error: "Internal server error" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  } finally {
    // Close the database connection
    await connection.end();
  }
}