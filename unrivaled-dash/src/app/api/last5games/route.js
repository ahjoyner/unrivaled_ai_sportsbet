// app/api/last5games/route.js
import mysql from 'mysql2/promise';

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const playerName = searchParams.get("playerName");
  
  if (!playerName) {
    return new Response(JSON.stringify({ error: "Missing playerName" }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  
  try {
    const connection = await mysql.createConnection({
      host: "localhost",
      user: "root",
      password: "Joynera4919",
      database: "unrivaled",
    });
    
    // Retrieve the last 5 games sorted by game_date descending (most recent first)
    const [rows] = await connection.execute(
      `SELECT gs.game_id, gs.pts, g.game_date
       FROM game_stats gs
       JOIN games g ON gs.game_id = g.game_id
       WHERE LOWER(gs.player_name) = LOWER(?)
       ORDER BY g.game_date DESC
       LIMIT 5`,
      [playerName]
    );

    await connection.end();
    
    // Flip the order: Instead of most recent -> 5th last, return 5th last -> most recent
    const flippedRows = rows.reverse();  

    return new Response(JSON.stringify({ result: flippedRows }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error("Error fetching last 5 games:", error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
