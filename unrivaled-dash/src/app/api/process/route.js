import { exec } from 'child_process';
import path from 'path';

export default async function handler(req, res) {
    const scripts = [
        'unr_projections.go',
        'unr_player_fetcher.py',
        'unr_player_scrape.py',
        'unr_team_scrape.py',
        'unr_game_stats_scrape.py'
    ];

    for (const script of scripts) {
        const scriptPath = path.join(process.cwd(), '../../data/unrivaled', script);
        exec(`python3 ${scriptPath}`, (error, stdout, stderr) => {
            if (error) {
                console.error(`Error running ${script}: ${error.message}`);
                return res.status(500).json({ error: `Failed to run ${script}` });
            }
            if (stderr) {
                console.error(`stderr: ${stderr}`);
                return res.status(500).json({ error: stderr });
            }
            console.log(`stdout: ${stdout}`);
            console.log(`Successfully ran ${script}!`)
        });
    }

    res.status(200).json({ message: 'Processing completed successfully' });
}