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
- Phase 3: API-only LangChain agent, background execution, ordered live activity,
  explicit run failures/retries and restart interruption handling. The test-only
  app supplies six synthetic cases and scripted models, including a retry scenario.
- The dashboard is still the hello-world skeleton pending phases 4-5.

## Run

Use Python 3.12 with uv and Node 26. The initial setup is `uv sync` and
`npm install`; `npm run dev` starts the API on port 8000 and dashboard on port 5173.
The backend creates the ignored `undercover.sqlite3` at the repository root.
Read operations do not require a model key.
Live agent runs use `OPENROUTER_API_KEY` from `.env`. The default is
`openai/gpt-6-luna` with low reasoning effort; `MODEL_NAME` selects an alternative.
The agent does not resume automatically after a backend restart.

## Verification

- Phase 1: `npm run check:python` passed: Ruff, Pyright (0 errors), 10 tests,
  99.65% Python coverage. Pylance syntax checks passed for the API and models.
- Phase 2: `npm run check:python` passed: 34 tests, 99.78% Python coverage,
  Ruff and Pyright clean. Guard tests use isolated copies of the seed claim with
  the plan's exact monetary scenarios; named synthetic agent fixtures follow in
  phase 3. Verified $1,000.00 vs $1,000.01, sign-off before payment, 100001 stored
  cents, invalid states/inputs and simultaneous duplicate-payment attempts.
- Phase 3: `npm run check:python` passed: 50 tests, 99.33% Python coverage,
  Ruff and Pyright clean. Agent and runner Pylance syntax checks passed.
- Real HTTP check against the isolated stub app: `/run` returned 202 in 0.038s
  while the run was still active and health remained responsive; it completed
  with a $420.00 simulated payment and 13 ordered events. The helper was stopped.
- Tests use temporary databases; no evaluation files were opened and no external
  model or payment request was made. Browser checks are scheduled for phases 4-6.
