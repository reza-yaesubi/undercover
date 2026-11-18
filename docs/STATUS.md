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
- Phase 4: responsive queue, complete claim evidence, decision/payment display,
  operational activity and read-only instructions. Safe text rendering, explicit
  read failures/retry and stale-selection protection are covered by component tests.
- Phase 5: run/retry, non-overlapping one-second polling, eligible handler
  selection, separate sign-off/payment requests, payment-only recovery and
  disabled conflicting controls. Polling remains active after the decision
  until the workspace closes, including final activity and payment updates.

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
- Phase 4: TypeScript format/lint/type checks passed; 13 component tests,
  100% statement/line/function coverage (branch coverage above 90%).
- B1/B2: integrated Playwright browser verified 25 waiting claims, CLM-1001's
  $420.00, Premium plan, full story, three items, four document texts, CLM-0412
  history, exact API instructions and retained selection. No live agent was run.
- B3: integrated-browser screenshot inspected; its viewport emulation reset
  unexpectedly, so local Playwright Chromium verified exact 1440x900 and 390x844
  light/dark layouts. No horizontal overflow with all documents expanded;
  Instrument Sans/JetBrains Mono and white/black panels verified; keyboard queue
  focus works. No unexpected console/network errors (StrictMode aborts expected).
  Four screenshots: `.playwright-mcp/pilot/phase4-{desktop,mobile}-{light,dark}.png`.
  Development helper servers were stopped after these read-only checks.
- Phase 5: `npm run check:ts` passed 20 tests; 99.21% statements, 93.05%
  branches, 100% functions/lines. `npm run e2e` passed 7 tests against the
  isolated stub app; both servers have `reuseExistingServer:false`.
- B4-B6 passed in the integrated Playwright browser: visible initial progress,
  13 ordered events for the $420 approval, $1,000 payment without sign-off,
  $1,000.01 blocked with 409 until HND-01 signed, persisted payment after reload,
  and distinct zero-payout decline/referral with no payment controls.
- B7 passed with a fresh stub instance: baggage first-attempt failure then
  explicit $200 retry; intercepted 503 payment retained sign-off and recovered
  through payment-only retry; intercepted queue read displayed its connection
  error. Expected injected 409/503 responses, request cancellation and deliberate
  server-restart connection failures were observed, not hidden. All helper
  servers stopped. No real model/payment calls.
