# Status

The pilot is being implemented in the order in [PLAN.md](PLAN.md).

## Built

- Phase 1: SQLite-backed 25-claim queue, full claim context, policy wording,
  read-only agent instructions and handlers. The original health API is unchanged.
- Seeding uses an explicit allowlist, filters manual-only company settings, and
  does not overwrite workflow progress. Business source files are unchanged.
- Phase 2: immutable decisions tied to active runs, handler sign-off and a separate
  simulated payment operation. Money is stored in integer cents. SQLite write
  transactions prevent duplicate payments, and partial amounts cannot bypass the
  approval limit.
- The agent and dashboard are still the hello-world skeleton pending later phases.

## Run

Use Python 3.12 with uv and Node 26. The initial setup is `uv sync` and
`npm install`; `npm run dev` starts the API on port 8000 and dashboard on port 5173.
The backend creates the ignored `undercover.sqlite3` at the repository root.
Read operations do not require a model key.

## Verification

- Phase 1: `npm run check:python` passed: Ruff, Pyright (0 errors), 10 tests,
  99.65% Python coverage. Pylance syntax checks passed for the API and models.
- Phase 2: `npm run check:python` passed: 34 tests, 99.78% Python coverage,
  Ruff and Pyright clean. Guard tests use isolated copies of the seed claim with
  the plan's exact monetary scenarios; named synthetic agent fixtures follow in
  phase 3. Verified $1,000.00 vs $1,000.01, sign-off before payment, 100001 stored
  cents, invalid states/inputs and simultaneous duplicate-payment attempts.
- Tests use temporary databases; no evaluation files were opened and no external
  model or payment request was made. Browser checks are scheduled for phases 4-6.
