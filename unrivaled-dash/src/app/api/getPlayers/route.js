import fs from 'fs';
import path from 'path';
import mysql from 'mysql2/promise';

export async function GET() {
    const filePath = path.join('/Users/ajoyner/Desktop/unrivaled_ai_sportsbet/data/unrivaled/unr_enriched_players.json');

    try {
        const data = fs.readFileSync(filePath, 'utf8');
        const jsonData = JSON.parse(data);

        const connection = await mysql.createConnection({
            host: 'localhost',
            user: 'root',
            password: 'Joynera4919',
            database: 'unrivaled',
        });

        const [rows] = await connection.execute('SELECT name, headshot_url FROM player_stats');
        const headshots = Object.fromEntries(rows.map(row => [row.name.toLowerCase(), row.headshot_url]));

        // Fetch last 5 games data for each player
        const [gamesData] = await connection.execute('SELECT * FROM game_stats ORDER BY game_id DESC LIMIT 5');
        const last5Games = gamesData.reduce((acc, game) => {
            if (!acc[game.player_name]) acc[game.player_name] = [];
            acc[game.player_name].push(game);
            return acc;
        }, {});

        await connection.end();

        const enrichedData = jsonData.map(player => {
            const playerName = player["Player Data"].name.toLowerCase();
            const last5GamesData = last5Games[playerName] || [];
            const confidence = calculateConfidence(last5GamesData, player["Projection Data"].line_score);

            return {
                ...player,
                headshot_url: headshots[playerName] || null,
                last_5_games: last5GamesData.map(game => ({
                    points: game.points,
                    over: game.points >= player["Projection Data"].line_score,
                })),
                confidence,
            };
        });

        return new Response(JSON.stringify(enrichedData), {
            status: 200,
            headers: {
                'Content-Type': 'application/json',
            },
        });
    } catch (error) {
        console.error('Error reading unr_enriched_players.json or fetching headshots:', error);
        return new Response(JSON.stringify({ error: 'Failed to read data' }), {
            status: 500,
            headers: {
                'Content-Type': 'application/json',
            },
        });
    }
}

function calculateConfidence(gamesData, propLine) {
    if (gamesData.length === 0) return 0;

    const overCount = gamesData.filter(game => game.points >= propLine).length;
    const underCount = gamesData.length - overCount;

    if (overCount >= 4) return 150; // Strong over confidence
    if (overCount >= 3) return 112.5; // Moderate over confidence
    if (underCount >= 4) return 0; // Strong under confidence
    if (underCount >= 3) return 37.5; // Moderate under confidence

    return 75; // Neutral
}