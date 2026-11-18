# Status

The pilot is being implemented in the order in [PLAN.md](PLAN.md).

## Built

- Phase 1: SQLite-backed 25-claim queue, full claim context, policy wording,
  read-only agent instructions and handlers. The original health API is unchanged.
- Seeding uses an explicit allowlist, filters manual-only company settings, and
  does not overwrite workflow progress. Business source files are unchanged.
- The agent and dashboard are still the hello-world skeleton pending later phases.

## Run

Use Python 3.12 with uv and Node 26. The initial setup is `uv sync` and
`npm install`; `npm run dev` starts the API on port 8000 and dashboard on port 5173.
The backend creates the ignored `undercover.sqlite3` at the repository root.
Read operations do not require a model key.

## Verification

- Phase 1: `npm run check:python` passed: Ruff, Pyright (0 errors), 10 tests,
  99.65% Python coverage. Pylance syntax checks passed for the API and models.
- Tests use temporary databases; no evaluation files were opened and no external
  model or payment request was made. Browser checks are scheduled for phases 4-6.
