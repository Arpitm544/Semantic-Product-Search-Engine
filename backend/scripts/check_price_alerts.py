"""Run one batch for cron/host schedulers; no public admin endpoint required."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
from api.price_alerts import run_due_checks

if __name__ == '__main__':
    print(f'Price checks completed: {run_due_checks()}')
