"""Manual bounded collection import: python scripts/sync_shopify.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
from api.shopify_service import context
from api.ranking_service import get_candidate_ranker
from src.integrations.shopify.sync import synchronize

if __name__ == '__main__':
    settings, repository = context()
    repository.setup()
    count = synchronize(settings, repository, get_candidate_ranker())
    print(f'Shopify sync complete: {count} searchable products.')
