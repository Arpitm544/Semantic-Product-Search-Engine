# Live marketplace sources

The default search continues to use the Amazon ESCI catalog in MongoDB.
The website source selector also supports Amazon live, Flipkart live, and all
sources together. Live marketplace results are fetched on demand and are not
written into the benchmark catalog. The original MongoDB search ranking remains
unchanged. Live and combined searches use the cross-encoder to rerank returned
candidates and have not been evaluated on the ESCI benchmark.

## Configure

An ignored private `backend/.env` template is prepared locally. Fill its values
on your computer. Never place these credentials in frontend environment variables.

Amazon Creators API requires:

- `AMAZON_CREDENTIAL_ID`
- `AMAZON_CREDENTIAL_SECRET`
- `AMAZON_CREDENTIAL_VERSION` (use the actual version issued by Amazon)
- `AMAZON_PARTNER_TAG`
- `AMAZON_MARKETPLACE` (defaults to `www.amazon.in`)

Flipkart requires `FLIPKART_AFFILIATE_ID` and `FLIPKART_AFFILIATE_TOKEN`.
The API loads `.env` at startup; shell exports take precedence. Restart the
backend after changing credentials. The SDK handles Amazon token renewal.

## Official Amazon SDK

The SDK is already installed in this workspace. To prepare another checkout,
run from `backend/`:

```sh
.venv/bin/python scripts/install_amazon_sdk.py
```

This downloads the official Amazon SDK into Git-ignored `vendor/` and installs
its dependencies. The script does not read credentials.

## Start and use

Restart your existing backend terminal using `sh scripts/start_amazon_backend.sh`.
The search page source selector defaults to MongoDB. Choose Amazon live, Flipkart
live, or All sources before submitting a query.

API examples:

- `/api/search?q=headphones&source=mongo`
- `/api/search?q=headphones&source=amazon`
- `/api/search?q=headphones&source=flipkart`
- `/api/search?q=headphones&source=all`

Source statuses report partial failures without discarding other results. Prices
use each provider's currency; product links open the marketplace listing. No
credentials or raw SDK error bodies are returned to the browser. No live requests
were verified in this implementation because credentials have not been configured.

Amazon and Flipkart return limited candidate lists, not their entire catalogs.
Backend HTTP request timeouts are applied; provider outages and rate limits can
still prevent results. The live sources require the search engine to finish
initialization. The Colab accuracy figures do not apply to live source searches.

## References

- [Amazon SDK documentation](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/get-started/using-sdk)
- [Flipkart product API reference](https://affiliate.flipkart.com/api-docs/af_prod_ref.html)
