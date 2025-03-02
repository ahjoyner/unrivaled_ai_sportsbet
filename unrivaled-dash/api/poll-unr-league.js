import fetch from 'node-fetch';

export default async (req, res) => {
  try {
    // Check if the UNR league is available
    const response = await fetch('https://api.prizepicks.com/projections?league_id=288&per_page=250&single_stat=true', {
      headers: {
        'Host': 'api.prizepicks.com',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Mobile Safari/537.36',
        'Referer': 'https://app.prizepicks.com/',
      },
    });

    const data = await response.json();

    // If the UNR league is available, trigger the scraping pipeline
    if (data && data.length > 0) {
      console.log('UNR League is available. Triggering scraping pipeline...');

      // Trigger the scraping pipeline (e.g., call scrape.go)
      await triggerScrapingPipeline();

      res.status(200).json({ message: 'UNR League detected. Scraping pipeline triggered.' });
    } else {
      console.log('UNR League not available.');
      res.status(200).json({ message: 'UNR League not available.' });
    }
  } catch (error) {
    console.error('Error polling UNR league:', error);
    res.status(500).json({ error: 'Failed to poll UNR league.' });
  }
};

async function triggerScrapingPipeline() {
    const { exec } = require('child_process');
  
    // Run scrape.go
    exec('go run data/unrivaled/scrape.go', (error, stdout, stderr) => {
      if (error) {
        console.error('Error running scrape.go:', error);
        return;
      }
      console.log('scrape.go output:', stdout);
  
      // Run unr_projections.go
      exec('go run data/unrivaled/unr_projections.go', (error, stdout, stderr) => {
        if (error) {
          console.error('Error running unr_projections.go:', error);
          return;
        }
        console.log('unr_projections.go output:', stdout);
  
        // Run unr_player_fetcher
        exec('python3 data/unrivaled/unr_player_fetcher.py', (error, stdout, stderr) => {
          if (error) {
            console.error('Error running unr_player_fetcher.py:', error);
            return;
          }
          console.log('unr_player_fetcher.py output:', stdout);
  
          // Run Python scripts
          exec('python3 data/unrivaled/unr_player_scrape.py', (error, stdout, stderr) => {
            if (error) {
              console.error('Error running unr_player_scrape.py:', error);
              return;
            }
            console.log('unr_player_scrape.py output:', stdout);
  
            exec('python3 data/unrivaled/unr_game_stats_scrape.py', (error, stdout, stderr) => {
              if (error) {
                console.error('Error running unr_game_stats_scrape.py:', error);
                return;
              }
              console.log('unr_game_stats_scrape.py output:', stdout);
  
              exec('python3 data/unrivaled/unr_team_scrape.py', (error, stdout, stderr) => {
                if (error) {
                  console.error('Error running unr_team_scrape.py:', error);
                  return;
                }
                console.log('unr_team_scrape.py output:', stdout);
  
                // Run analysis.py
                exec('python3 data/unrivaled/predict/analysis.py', (error, stdout, stderr) => {
                  if (error) {
                    console.error('Error running analysis.py:', error);
                    return;
                  }
                  console.log('analysis.py output:', stdout);
                });
              });
            });
          });
        });
      });
    });
  }