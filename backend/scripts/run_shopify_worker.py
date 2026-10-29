"""Durable job worker plus hourly reconciliation. Supervise separately from API."""
import logging
import time
from sync_shopify import context, get_candidate_ranker, synchronize
from src.data.shopify_repository import now


def run():
    settings, repository = context()
    repository.setup()
    while True:
        # Durable enqueue also closes missed delivery/restart gaps.
        repository.enqueue(f'reconcile:{now().strftime("%Y-%m-%dT%H")}')
        job = repository.claim()
        if not job:
            time.sleep(2)
            continue
        cutoff = now()
        started = time.monotonic()
        try:
            synchronize(settings, repository, get_candidate_ranker())
        except Exception:
            logging.exception('Shopify reconciliation failed')
            repository.finish(job, error=True)
        else:
            repository.finish(job)
            logging.info('Shopify sync completed in %.1fs', time.monotonic() - started)
            # A successful full scan covers already-queued deliveries. New events
            # arriving while scanning must remain pending for the next scan.
            from datetime import timedelta
            repository.jobs.update_many({'shop_domain': settings.shop, 'status': 'pending',
                                         'created_at': {'$lte': cutoff}},
                                        {'$set': {'status': 'done', 'expires_at': now() + timedelta(days=7)}})


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()
