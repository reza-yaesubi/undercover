# Status

The six-phase pilot in [PLAN.md](PLAN.md) is implemented.

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
- Phase 6: full workflow/browser regression tests, API contract checks and exact
  decision/activity/sign-off/payment persistence checks on a reopened database.

## Run

Use Python 3.12 with uv and Node 26. The initial setup is `uv sync` and
`npm install`; `npm run dev` starts the API on port 8000 and dashboard on port 5173.
The backend creates the ignored `undercover.sqlite3` at the repository root.
Read operations do not require a model key.
Live agent runs use `OPENROUTER_API_KEY` from `.env`. The default is
`openai/gpt-6-luna` with low reasoning effort; `MODEL_NAME` selects an alternative.
The agent does not resume automatically after a backend restart.

### Handler workflow

Select a claim to inspect the full evidence and choose **Run agent**. The four
queue states are **Waiting**, **In progress**, **Waiting for sign-off** and
**Decided**. Outcome (Approved, Declined or Referred) and payment are separate:
Decided does not mean paid. The workspace polls once per second after each
completed read; slow reads never overlap. Instructions are read only.

Positive approvals up to $1,000.00 can receive a simulated payment immediately.
Above $1,000.00, select an eligible handler and choose **Sign off and record
payment**. The backend enforces this limit for every caller. If payment fails
after sign-off, the signed approval remains; **Retry payment** sends only the
payment request. No real money is transferred.

Failures before a saved decision restore Waiting and allow **Retry agent**.
Failures after a decision preserve it and expose payment-only recovery when
eligible. Runs execute in-process, not durably: a restart marks interrupted runs
failed and never automatically replays them. Handler selection is attribution,
not authentication; this local pilot has no sign-in.

### Checks

From the root, run `npm run check` for all gates, or `npm run check:python`,
`npm run check:ts` and `npm run e2e` separately. E2E starts its own six-claim
stub backend and Vite servers; stop development servers first. Occupied ports
8000/5173 are rejected rather than reused. Test storage is isolated; E2E uses
an automatically cleaned directory under `.pytest_cache/`, never the pilot DB.
The 25-business-claim seed is separately tested by backend tests and the read-only
browser walkthrough. Tests need no OpenRouter key.

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
- Tests use isolated databases; no evaluation files were opened and no external
  model or payment request was made.
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

## Final handover verification

- `npm run check` passed: Ruff format/lint, Pyright (0 errors), 52 Python tests
  with **99.33%** coverage; Prettier/ESLint/tsc, 20 component/interaction tests
  with **99.21%** statements, **93.05%** branches and **100%** functions/lines;
  **13 Playwright tests**. All configured thresholds and exclusions are unchanged.
- The required post-phase `npm run check` also passed with the same counts
  and coverage; the final documentation records that completed run.
- B1/B2 and B4-B7 were repeated on the final dashboard using the integrated
  Playwright browser, including a fresh server for failure recovery. B3 exact
  viewports were repeated with local Chromium because integrated-browser
  emulation resets unpredictably. Screenshots:
  `.playwright-mcp/pilot/final-{desktop,mobile}-{light,dark}.png`.
  Automated responsive screenshots are also saved under `e2e/test-results/`.
  These local evidence files are ignored, not committed.
- Normal navigation/layout tests observed no unexpected console/network errors.
  Recovery tests deliberately produce 403/409/503 responses; cancellation and
  connection errors during deliberate server shutdowns are expected.
- Verified occupied-port refusal by running E2E while our development server
  was active: it stopped before tests with an explicit port-8000 error.
- Production records were inspected read-only. No live agent, evaluation data,
  real payments, AWS operations or pushes were used. All helper servers stopped.

Model accuracy versus handler decisions has **not** been measured. Scripted
models verify tool delivery, money/state enforcement and UI behavior, not real
model judgment. Windows-compatible commands are retained; this verification ran
on Linux, not Windows. Google Fonts requires internet (system fallbacks remain).
