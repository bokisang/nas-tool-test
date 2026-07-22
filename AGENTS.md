# AI development contract

Before changing this repository, read `docs/PROJECT_DEVELOPMENT_GUIDE.md` completely.

## Product invariants

- Source folders are always mounted and opened read-only. Never implement delete, move, rename, overwrite, chmod, or chown operations against indexed user files.
- Never accept an arbitrary host absolute path from an HTTP request. Resolve database entry IDs beneath a configured source root and verify the canonical path remains inside that root.
- The application must run as a non-root user. Do not add `privileged`, `network_mode: host`, Docker socket mounts, broad system-directory mounts, or writes to `/etc`, `/usr`, `/boot`, or the TOS root filesystem.
- Keep metadata, indexes, models, thumbnails, logs, and migrations under the configured application data volume. Do not persist important state only inside a container layer.
- Treat files as untrusted input. Parsers require timeouts, size limits, bounded temporary storage, and failure isolation. Never execute macros, scripts, archive contents, or embedded programs.
- Do not upload file names, file contents, embeddings, OCR text, thumbnails, or telemetry to an external service unless a future explicitly approved feature requires opt-in consent.

## Architecture constraints

- Backend: Python 3.11, FastAPI, SQLite, FTS5, and sqlite-vec.
- Frontend: TypeScript web application compiled to static assets served by the backend.
- Background work: durable SQLite job queue. Heavy AI work must not run in an API request process.
- First-release text embedding: `BAAI/bge-small-zh-v1.5`.
- First-release visual embedding: Chinese-CLIP RN50.
- OCR: PaddleOCR lightweight models. Video: FFmpeg/FFprobe and faster-whisper CPU INT8.
- Maintain separate text and visual vector spaces. Store model and extractor versions with every derived artifact.
- SQLite is the source of truth. Do not introduce Redis, PostgreSQL, Elasticsearch, or Qdrant without an accepted architecture change.

## Delivery rules

- Implement only one milestone or a clearly bounded vertical slice at a time.
- Add or update tests with every behavior change. Include failure and restart behavior for scanner/worker changes.
- Preserve database migration compatibility. Never edit an already released migration.
- Keep shell scripts and Linux configuration files in LF format.
- Pin production dependencies and container image versions. Do not use `latest` in a release artifact.
- Do not claim ARM64 support until the complete model and parser stack passes on real ARM64 hardware.
- Do not publish, push images, create releases, submit to the TNAS developer platform, or change the permanent application ID without explicit user approval.

## Required checks before marking work complete

Run the checks relevant to the changed area:

```text
backend format/lint/type checks
backend unit and integration tests
frontend lint/typecheck/tests/build
database migration test
Docker image build
container health check
TOS package metadata validation
Trivy image scan for release candidates
```

For a release candidate, also execute the full checklist in section 22 of
`docs/PROJECT_DEVELOPMENT_GUIDE.md` on a real TOS 7 TNAS device.

