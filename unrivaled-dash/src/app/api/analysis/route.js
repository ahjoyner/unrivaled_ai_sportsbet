// app/api/analysis/route.js
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function GET() {
  try {
    // Trigger the background analysis task.
    const { stdout, stderr } = await execAsync(
      `python3 -c "import sys; sys.path.append('/Users/ajoyner/Desktop/unrivaled_ai_sportsbet/data/unrivaled/predict'); from play_by_play_analysis_gpt import run_analysis_task; run_analysis_task.delay()"`
    );
    if (stderr) {
      console.error(`Error: ${stderr}`);
      return new Response(JSON.stringify({ error: stderr }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    // We don't actually need to use a taskId on the front end.
    console.log("Analysis triggered in background.");
    return new Response(JSON.stringify({ message: "Analysis triggered" }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error(`Error triggering Celery task: ${error}`);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
