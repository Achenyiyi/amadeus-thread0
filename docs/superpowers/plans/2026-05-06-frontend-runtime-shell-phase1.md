# Frontend Runtime Shell Phase 1 Plan

## Goal

Verify the existing frontend shell still builds and consumes backend contract fixtures without introducing a second backend truth.

## Tasks

- Keep frontend runtime code under `frontend/`.
- Preserve mock fixtures as copied backend envelopes.
- Add an audit runner that executes backend contract tests and `npm --prefix frontend run build`.
- Make the audit runner resolve `npm.cmd` / `npm.exe` on Windows.

## Validation

- `python -m pytest tests/test_frontend_contract_sync.py tests/test_backend_api.py tests/test_backend_session.py -q`
- `npm --prefix frontend run build`
- `python evals/run_frontend_runtime_shell_audit.py --run-tag phase1-dev`
