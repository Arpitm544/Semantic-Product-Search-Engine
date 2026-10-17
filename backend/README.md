# Application workspace

Run Python commands from this directory. The repository overview and all shared
guides are in [the root README](../README.md) and [docs](../docs/).

For a step-by-step explanation of the files and request flow, read
[the backend reading guide](READING_GUIDE.md).

## Start the backend

```sh
sh scripts/start_backend.sh
```

## Start the frontend

```sh
cd ../frontend
npm run dev:frontend
```

See [Catalog backend setup](../docs/backend.md) for database configuration,
model paths, import commands, and index lifecycle. See [.env.example](.env.example)
for configuration names. The API loads `backend/.env`; shell exports take precedence.

The backend uses FastAPI with function-based routes. Uvicorn starts when you run
`api/main.py`; the startup script sets the local CPU thread limits.
Interactive API documentation is available at http://127.0.0.1:8000/docs.
