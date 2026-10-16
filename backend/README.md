# Application workspace

Run Python commands from this directory. The repository overview and all shared
guides are in [the root README](../README.md) and [docs](../docs/).

## Start the backend

```sh
sh scripts/start_amazon_backend.sh
```

## Start the frontend

```sh
cd ../frontend
npm run dev:frontend
```

See [Amazon backend setup](../docs/amazon-backend.md) for database configuration,
model paths, import commands, and index lifecycle. See [.env.example](.env.example)
for configuration names. The API loads `backend/.env`; shell exports take precedence.
