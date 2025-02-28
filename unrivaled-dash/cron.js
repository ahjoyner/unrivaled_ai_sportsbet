const cron = require('node-cron');
const { exec } = require('child_process');
const path = require('path');

// Schedule the cron job to run every day at midnight (0 0 * * *)
cron.schedule('0 0 * * *', () => {
    console.log('Running scraping and processing scripts...');

    // Run scrape.go
    const scrapeScriptPath = path.join(__dirname, '../data/unrivaled/scrape.go');
    exec(`go run ${scrapeScriptPath}`, (error, stdout, stderr) => {
        if (error) {
            console.error(`Error running scrape.go: ${error.message}`);
            return;
        }
        if (stderr) {
            console.error(`stderr: ${stderr}`);
            return;
        }
        console.log(`stdout: ${stdout}`);
    });

    // Run other processing scripts
    const scripts = [
        'unr_projections.go',
        'unr_player_fetcher.py',
        'unr_player_scrape.py',
        'unr_team_scrape.py',
        'unr_game_stats_scrape.py'
    ];

    scripts.forEach((script) => {
        const scriptPath = path.join(__dirname, '../data/unrivaled', script);
        exec(`python ${scriptPath}`, (error, stdout, stderr) => {
            if (error) {
                console.error(`Error running ${script}: ${error.message}`);
                return;
            }
            if (stderr) {
                console.error(`stderr: ${stderr}`);
                return;
            }
            console.log(`stdout: ${stdout}`);
        });
    });
});

console.log('Cron job scheduled. Waiting for the next run...');