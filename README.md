# AI NAS Search

Private, local-first search for files stored on a TNAS device. This repository
currently contains the M0 engineering foundation only: a health-checked API,
static web shell, durable SQLite initialization, and container packaging. File
scanning, indexing, previews, and AI extraction are deliberately not included
yet.

## Development

Copy `.env.example` to `.env`, then set `AI_NAS_SOURCE_PATH` to one explicitly
authorized source folder and `AI_NAS_DATA_PATH` to an application-owned data
folder. The source mount is read-only; the application never writes to it.

```text
docker compose up --build
```

Open `http://localhost:18680`. Health is available at `/healthz`, and the API
version endpoint is `/api/v1/status`.

## Data and privacy

All application state is stored under `AI_NAS_DATA_PATH`. This M0 build does
not send telemetry or source-file data to external services. Run the container
with a non-root host UID/GID that can write the application data directory.
