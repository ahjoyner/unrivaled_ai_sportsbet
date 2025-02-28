import { exec } from 'child_process';
import path from 'path';

export default async function handler(req, res) {
    const scrapeScriptPath = path.join(process.cwd(), '../../data/unrivaled/scrape.go');

    exec(`go run ${scrapeScriptPath}`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Error running scrape.go: ${error.message}`);
            return res.status(500).json({ error: 'Failed to run scrape.go' });
        }
        if (stderr) {
            console.error(`stderr: ${stderr}`);
            return res.status(500).json({ error: stderr });
        }
        console.log(`stdout: ${stdout}`);
        res.status(200).json({ message: 'Scraping completed successfully' });
    });
}