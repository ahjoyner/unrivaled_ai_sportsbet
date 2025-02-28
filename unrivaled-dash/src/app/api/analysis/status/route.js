import mysql from 'mysql2/promise';

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const playerName = searchParams.get("playerName");
  if (!playerName) {
    return new Response(JSON.stringify({ error: "Missing playerName" }), { status: 400 });
  }
  try {
    // Connect to the database
    const connection = await mysql.createConnection({
      host: "localhost",
      user: "root",
      password: "Joynera4919",
      database: "unrivaled",
    });
    // Fetch the analysis results for the player.
    // Since there's no created_at column, we simply use LIMIT 1.
    const [rows] = await connection.execute(
      "SELECT * FROM analysis_results WHERE player_name = ? LIMIT 1",
      [playerName]
    );
    await connection.end();
    if (rows.length === 0) {
      return new Response(JSON.stringify({ error: "No analysis found for player" }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    const result = rows[0];
    return new Response(JSON.stringify({ result }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error(`Error fetching analysis results: ${error}`);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
