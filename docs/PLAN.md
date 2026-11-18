# Pilot build plan

**Status: implementation in progress.** Checked criteria have been verified; remaining criteria are not yet reported as complete.

This plan follows [SPEC.md](SPEC.md), [TECH_STACK.md](TECH_STACK.md), [CODE_STANDARDS.md](CODE_STANDARDS.md), [PROCESS.md](PROCESS.md) and [BRAND.md](BRAND.md). The starting point is the health-only backend, agent and dashboard described in [STATUS.md](STATUS.md). Build the six phases in order only after implementation is requested.

## Scope and implementation choices

- Use FastAPI, SQLite and Python 3.12 through uv; React, Vite, strict TypeScript and Node 26. Reuse the existing dependencies and test runners. No new framework or rules engine is needed.
- The backend owns claim state, instructions, activity and payment checks. The agent uses LangChain's `create_agent`, accessing business information and instructions only through backend HTTP operations.
- Start one selected claim from the dashboard. A synchronous background worker runs the agent without blocking API requests; the dashboard polls once per second. This avoids adding a dispatcher, message broker or streaming infrastructure to the pilot.
- Persist business records and run activity in SQLite, but do not add resumable agent execution. A restart can interrupt a run; it must not silently restart the model or a payment.
- Keep decision outcome, queue status, agent-run status and simulated payment separate. An over-limit approval is still `approve`, not `refer`.
- Exclude the claims manual, evaluation sets, security example, sign-in, real payments, customer messages and later-day features. Do not read evaluation files or use Ed's branches to implement this plan.

## Verification and phase completion

API examples below are contracts to implement and exercise with FastAPI `TestClient` or Playwright's request client. Values such as `<thread_id>` and `<timestamp>` are generated values whose format and association must be asserted, not literal response text. All API inputs are required; read/start operations without a body need no invented optional parameters. Each operation has the listed unique `operation_id` and a one-line docstring.

| Command, from the repository root | Required result |
| --- | --- |
| `npm run check:python` | Exit 0; Ruff format/lint pass, Pyright reports 0 errors, pytest reports no failures and total Python coverage is at least 80%. |
| `npm run check:ts` | Exit 0; Prettier, ESLint and TypeScript pass, Vitest reports no failures and statement coverage is at least 80%, as configured. |
| `npm run e2e` | Exit 0; all Playwright tests pass against an isolated, stub-model backend; no OpenRouter requests. |
| `npm run check` | All three gates above pass without disabling rules, reducing thresholds or adding coverage exclusions. |

At each phase's completion, verify its checkboxes, record actual commands/results and browser observations in [STATUS.md](STATUS.md), tick only verified criteria, then commit that phase with the normal pre-commit hook. Fix failures and recheck any changes made by the hook. Never use `--no-verify` or push. A missing browser tool or failed prerequisite is a blocker to report, not a passed check. Planning itself changes only this document.

### Deterministic test fixtures

Create these small synthetic claims in test fixtures, not in the business seed files. Use valid policy dates, filing dates, evidence and exclusions except where the scenario explicitly changes one. Include the seeded handler identifiers in the fixture database.

| Fixture claim | Policy facts | Expected scripted decision |
| --- | --- | --- |
| `CLM-T420` | Premium; covered crew delay of 19 hours 15 minutes; hotel $245, meals $95, taxis $80; receipts and carrier report present. | `approve`, $420.00; sections 3 and 10. $245 + $95 + $80, below the $800 maximum, no deductible. |
| `CLM-TBAG` | Premium; covered baggage item worth $500; carrier compensation $50; required report present. | `approve`, $200.00; sections 1, 5 and 10. Cap the item at $300, subtract $50 compensation, then the $50 deductible. |
| `CLM-T1000` | First; eligible emergency medical bill of $1,000; required records present, no exclusion. | `approve`, $1,000.00; sections 7 and 10; no sign-off required. |
| `CLM-T100001` | Same medical scenario with an eligible bill of $1,000.01. | `approve`, $1,000.01; sections 7 and 10; payment blocked until sign-off. |
| `CLM-TDECLINE` | Baggage delay on the journey home. | `decline`, $0.00; section 4. |
| `CLM-TREFER` | Emergency medical claim with missing medical records. | `refer`, $0.00; sections 7 and 11; explain what is missing, without messaging the customer. |

Reuse the `StubModel` pattern in [agent/tests/test_agent.py](../agent/tests/test_agent.py) and script real tool calls, not just a final chat message. These fixtures verify information delivery, decision storage, money handling and workflow behavior. A scripted model cannot prove a live model's judgment or accuracy against handlers; that evaluation remains unperformed unless separately authorized.

## Phase 1: Seeded records and read API

**Build and why:** Add a small SQLite connection/seed layer, typed response models and read operations in [backend/](../backend/). Keep the health route working. One backend source prevents the dashboard and agent from independently reading different data.

Seed only the explicitly named claims, policies, customers, plans and handlers files described in [data/README.md](../data/README.md). Normalize the source claim status `open` to `waiting`. Import only the pilot company settings: `currency`, `payout_approval_limit` and `policy_wording_version`. In particular, do not pass `repeat_claim_review` or `meal_allowance_without_receipts` from [company.json](../data/company.json) to the agent: those are manual-only rules. Serve the full [policy wording](../data/policy_wording.md), not the short alternative or claims manual.

Use a local ignored SQLite database, short transactions and separate connections for concurrent requests. Initialization inserts missing seed records without overwriting decisions or progress. Tests inject a temporary database; no reset endpoint or destructive automatic reseeding is needed.

| Operation | `operation_id` | Response contract |
| --- | --- | --- |
| `GET /api/health` | `health` | `200 {"status":"ok"}`. |
| `GET /api/claims` | `list_claims` | `200 {"claims":[...],"total":25}` on a fresh business database. Each summary includes `claim_id`, `customer_name`, `claim_type`, `summary`, `amount_claimed` and canonical queue `status`. |
| `GET /api/claims/{claim_id}` | `get_claim` | `200` object with `claim`, `policy`, `customer`, `plan`, `decision`, `sign_off`, `payment` and `run`. `claim` retains story, items and documents and uses canonical `status`; `customer` includes `previous_claims`; `plan` includes applicable add-on definitions. Workflow records are `null` before they exist. |
| `GET /api/policy-wording` | `get_policy_wording` | `200 {"version":"2026.1","content":"<full policy wording>"}`. |
| `GET /api/agent/instructions` | `get_agent_instructions` | `200 {"content":"<pilot instructions>","currency":"USD","payout_approval_limit":"1000.00"}`. Instructions describe policy-only decisions, evidence, calculations, citations and the separate payment guard. |
| `GET /api/handlers` | `list_handlers` | `200 {"handlers":[...]}` with `handler_id`, `name` and `can_approve_over_limit` per handler. |

### Success criteria

- [x] Fresh initialization returns exactly the 25 IDs from the allowed queue file, three handlers and all three plans; every queue claim is `waiting`. A second initialization leaves the count and an existing test workflow record unchanged.
- [x] `GET /api/claims/CLM-1001` returns `claim.policy_id == "POL-2001"`, `claim.amount_claimed == 420`, all four submitted documents, `policy.plan == "premium"` and customer history containing `CLM-0412`. The source JSON files remain unchanged.
- [x] Every read operation matches its table contract. `GET /api/claims/CLM-MISSING` returns `404 {"detail":"Claim not found"}`; the health response remains unchanged.
- [x] Instructions and wording have no write operations: `PUT /api/agent/instructions` returns 405. No endpoint accepts arbitrary file paths, and there is no general static mount of the data directory.
- [x] Seed tests assert the allowed paths without opening evaluations. Agent-facing responses contain neither manual-only company settings nor evaluation content; the security example is not a queue record.
- [x] `npm run check:python` passes with the results defined above; record results, update status and commit phase 1.

## Phase 2: Decisions, sign-off and payment enforcement

**Build and why:** Add the mutation schemas, state transitions and simulated-payment service before exposing them as agent tools. The same transactional guard must apply to every payment caller, regardless of what the prompt says.

Store workflow monetary amounts as integer cents, validating decimal inputs without binary-float rounding. New `payout` and payment `amount` fields use two-decimal USD strings; original read-only seed context retains its existing numeric shapes. Reject negative, non-finite or sub-cent amounts rather than silently rounding them.

### State rules

| Event | Queue status afterward | Decision/payment consequence |
| --- | --- | --- |
| Claim is seeded, or a failed run had no recorded decision | `waiting` | No decision or payment; failure remains visible in run/activity records. |
| A waiting claim starts a run | `in_progress` | Allocate a new thread ID; reject another start while it is running. |
| Record a decline or referral | `decided` | Payout is zero; no payment is permitted. A referral is a completed agent decision, not a sign-off request. |
| Record an approval at or below the company limit | `decided` | A positive payout is eligible for a separate simulated payment; a zero payout has no payment due. |
| Record an approval above the company limit | `waiting_for_sign_off` | Preserve the approval and payout; no payment record may be created yet. |
| Eligible handler signs off an over-limit approval | `decided` | Record handler and time; a separate payment call is now permitted. |
| Record a simulated payment | Unchanged | Record exactly the approved amount once. `decided` alone does not mean paid. |

Keep run status (`running`, `completed` or `failed`) separate, because a decision can be saved before the worker finishes its final tool calls. The detail response's `run` object contains `thread_id`, `status`, `started_at`, `finished_at` and `error`; the latter two are nullable output fields until applicable. Once stored, a decision cannot be replaced in this pilot. Sign-off and payment refer to that stored decision.

| Operation | `operation_id` | Required body and response |
| --- | --- | --- |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | Body shown below. `201 {"claim_id":"<id>","status":"decided","decision":<stored decision>}` for an under-limit approval; over-limit uses `waiting_for_sign_off`. |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off_claim` | `{"handler_id":"HND-01"}` -> `200 {"claim_id":"<id>","status":"decided","sign_off":{"handler_id":"HND-01","signed_off_at":"<timestamp>"}}`. It does not itself pay. |
| `POST /api/claims/{claim_id}/pay` | `pay_claim` | `{"amount":"1000.01"}` -> `201 {"claim_id":"<id>","payment":{"amount":"1000.01","simulated":true,"paid_at":"<timestamp>"}}` only when eligible. |

Example decision request for `CLM-T420`:

```json
{
  "thread_id": "<active thread_id>",
  "outcome": "approve",
  "payout": "420.00",
  "reason": [
    "The documented crew delay meets the Premium waiting period under section 3.",
    "Eligible hotel, meal and taxi costs total $420.00, below the $800.00 limit, with no deductible."
  ],
  "policy_sections": [3, 10],
  "calculation": "245.00 + 95.00 + 80.00 = 420.00; no deductible."
}
```

All six fields are required. `reason` contains two or three nonempty, single-sentence entries and is displayed as one paragraph. Section numbers must exist in the wording. Decline/refer require `"payout":"0.00"` and an explanation of why nothing is payable. Validate shape and arithmetic representation, not the semantic truth of a model's judgment.

Unknown records return 404, malformed bodies return FastAPI's 422 validation response, and invalid state changes return 409 with an explicit `detail` message. Sign-off requires a known handler with `can_approve_over_limit`; a known ineligible handler receives 403. Handler selection is an unauthenticated attribution in this no-sign-in pilot, not proof of identity. Do not expose sign-off as an agent tool.

### Success criteria

- [ ] Tests begin a run using the backend state service, submit the example decision and assert the stored fields, `201`, and `decided`. A missing field, invalid outcome, invalid section or reason array outside two to three entries returns 422 without creating a decision.
- [ ] Decision writes require the current running thread and no existing decision. A mismatched thread or second decision returns 409 and preserves the original record.
- [ ] With `CLM-T1000` approved, `POST /pay {"amount":"1000.00"}` returns 201 without sign-off. With `CLM-T100001` approved, the corresponding call returns `409 {"detail":"Handler sign-off required"}` and leaves the payment table unchanged.
- [ ] For `CLM-T100001`, sign off with `HND-01`, then call `/pay` with `"1000.01"`: assert 200 then 201, the recorded handler/time, `simulated:true` and exactly 100001 stored cents.
- [ ] A direct attempt to pay only `"1000.00"` of the `"1000.01"` approval returns 409 for an amount mismatch. Splitting payments cannot evade sign-off; the guard checks the stored payout and company limit, not only the supplied amount.
- [ ] Paying a waiting, declined, referred or zero-payout claim returns 409; a repeated successful payment returns `409 {"detail":"Claim already paid"}`. Concurrent payment attempts create at most one payment record. Negative, non-finite and sub-cent requests return 422.
- [ ] Unknown/ineligible handlers cannot sign off, and sign-off is rejected for states other than `waiting_for_sign_off`. No payment code calls an external provider.
- [ ] `npm run check:python` passes; record results, update status and commit phase 2.

## Phase 3: Agent execution and live activity

**Build and why:** Replace the hello-world workflow in [agent/main.py](../agent/main.py), preserving its entry point and injectable stub-model pattern. Add a small backend run coordinator and activity storage. Typed tools over the phase 1/2 API keep model decisions separate from enforced business state.

`run(claim_id, thread_id)` fetches instructions from the backend, creates the LangChain agent, and gives it tools to read the selected claim bundle and wording, record its decision, and request payment. Bind the claim/thread identifiers to the run rather than letting the model choose another claim. Do not provide generic HTTP, filesystem, SQL or sign-off tools. Fetch failures must fail visibly, not fall back to a local prompt or empty context.

Use `https://openrouter.ai/api/v1`, the key in `OPENROUTER_API_KEY`, and `openai/gpt-6-luna` with low reasoning effort by default. Preserve the `MODEL_NAME` override, including `openrouter/free`; do not force the default model's reasoning setting onto an override.

The prompt requires claim, policy, plan/add-ons, customer history and policy wording before deciding; it follows the wording's calculation order and cites the applicable sections. It does not infer manual rules from repeat history. Positive under-limit approvals request simulated payment; over-limit approvals stop for handler sign-off.

| Operation | `operation_id` | Required body and response |
| --- | --- | --- |
| `POST /api/claims/{claim_id}/run` | `start_claim_run` | No body. `202 {"claim_id":"<id>","thread_id":"<new UUID>","status":"in_progress"}` after atomically recording the running state and scheduling work. |
| `GET /api/claims/{claim_id}/activity` | `get_claim_activity` | `200 {"events":[...]}` in sequence order, including previous attempts. Each event has `sequence`, `thread_id`, `kind`, `message` and `created_at`. |
| `POST /api/claims/{claim_id}/activity` | `record_claim_activity` | `{"thread_id":"<current thread>","kind":"tool_result","message":"Read claim, policy and customer history."}` -> 201 with the stored event; backend assigns sequence/time. |

Run the synchronous agent through FastAPI's background-task worker thread so its HTTP tools can call the same backend without blocking the event loop. Record start, tool calls/results, decision, payment outcome and completion or error as concise operational events, not hidden chain-of-thought, credentials or full prompts.

At the worker boundary, log failures and persist a failed run with a readable error. If no decision was stored, restore `waiting` so the handler can explicitly retry. If a decision already exists, retain it and any payment; show the failure and leave unpaid eligible claims available for a handler payment retry. A chat reply without a stored decision, or a positive under-limit approval left unpaid when the agent finishes, is a failed run rather than successful completion. Over-limit approvals awaiting sign-off are a normal completed run. On startup, mark interrupted running attempts failed using the same state rules; do not automatically replay them.

### Success criteria

- [ ] With a controlled stub worker, `/run` returns 202 while work is still pending, and `GET /api/health` stays responsive. A second start returns `409 {"detail":"Claim is already running"}` with only one worker scheduled; unknown claim returns 404.
- [ ] Starting an already decided or sign-off-pending claim returns 409 rather than replacing its decision. Only a waiting claim without a decision can be retried.
- [ ] Stub-model tests call the real API tools, confirm receipt of instructions and full claim context, and persist the fixture decisions and their exact payouts/citations. The initial API instructions, not the old hello-world constant, reach `create_agent`.
- [ ] `CLM-T420` and `CLM-T1000` finish with recorded simulated payments; `CLM-T100001` remains approved and unpaid pending sign-off; decline/refer finish without payment.
- [ ] A scripted agent that nevertheless invokes `/pay` for `CLM-T100001` receives the backend rejection and creates no payment. Its tool list contains no sign-off or unrestricted request operation.
- [ ] Activity is readable before completion, ordered and tied to the correct thread. Retrying after a failed attempt creates a new thread and retains the earlier error events.
- [ ] Simulated tool/model failures and a final message without a decision produce a failed run, a visible error and no invented decision. An agent that saves an under-limit approval but omits payment also fails visibly, retaining the decision for payment retry. A failure after decision storage does not erase that decision or create a duplicate payment.
- [ ] Restart tests preserve completed decisions/sign-offs/payments and mark unfinished runs interrupted without invoking the model or payment operation.
- [ ] Configuration tests assert the default model, low reasoning effort, OpenRouter URL and `MODEL_NAME` override without sending a request; API errors do not trigger a local-data or prompt fallback.
- [ ] Add a test-only backend app factory that uses a temporary SQLite database, the six synthetic fixtures and the injected `StubModel`. Script `CLM-TBAG` to fail before a decision on its first attempt and succeed for $200.00 on retry; the other scenarios follow the table. Even if a real API key is present, the factory never constructs the live model. Use it for later browser checks, with no production stub switch or reset endpoint.
- [ ] `npm run check:python` passes; record results, update status and commit phase 3.

## Phase 4: Queue, claim workspace and instructions

**Build and why:** Replace [dashboard/src/App.tsx](../dashboard/src/App.tsx) with a simple queue, selected-claim workspace and read-only instructions view. Use small components and one typed API helper rather than adding routing/state libraries for three views of the same local workflow.

Show identifiers, customer, claim type, claimed amount and a plain-English status in the queue. The detail view includes the complete story, item amounts, document text, policy/trip/travelers/add-ons, customer history, decision paragraph, sections, calculation, payment/sign-off information and activity. Keep money formatting in one USD formatter; do not equate the label "Decided" with payment success.

Apply Instrument Sans to body/headings, Instrument Serif only if an accent is used, and JetBrains Mono to numbers/identifiers. Use the brand's light/dark surfaces through the system color preference, rounded panels without outlines, accessible darkened/lightened text variants and the specified accent palette. No theme-management feature is needed.

### Success criteria

- [ ] Component tests render every queue state as "Waiting", "In progress", "Waiting for sign-off" or "Decided"; selecting a row fetches and displays the corresponding full detail without mixing in a previous selection's response.
- [ ] Tests cover all fixture outcomes, a two-sentence reason rendered as a paragraph, policy sections, the calculation and formatted amounts such as `$1,000.01`. Referrals are clearly distinguished from sign-off-pending approvals.
- [ ] The instructions view displays the backend response as non-editable text. Neither instructions nor raw document text can execute markup or scripts.
- [ ] Loading, an empty test queue, missing claims and failed requests have explicit UI states. A failed request is not displayed as an empty queue or a successful action; provide a visible retry.
- [ ] Complete browser checks B1-B3 below with Playwright MCP, including screenshots and console/network-error inspection.
- [ ] `npm run check:ts` passes. Update the obsolete greeting-based end-to-end assertion to the real claims UI while retaining an API health assertion; record results, update status and commit phase 4.

## Phase 5: Start, progress, sign-off and payment interactions

**Build and why:** Wire controls to the existing guarded backend operations. Polling keeps handlers informed without a new event-transport layer, while separate requests preserve the distinction between approving a decision and recording a payment.

"Run agent" calls `/run` for a waiting claim. Poll the queue, selected detail and activity once per second while the workspace is open, including when a saved decision has changed the queue status but the run is still active. Avoid overlapping requests, discard stale selection responses and clean up polling on unmount.

For an over-limit approval, require an eligible handler selection. "Sign off and record payment" calls `/sign-off`, then `/pay` with the stored payout only after sign-off succeeds. Show "Simulated payment recorded" only after payment succeeds. If the second call fails, preserve the sign-off, show its error and offer "Retry payment", not another sign-off. The same payment action can recover an unpaid under-limit approval after a failed agent run. Disable conflicting actions while the run or request is active.

### Success criteria

- [ ] Interaction tests assert a single run request, its in-progress state, subsequent polling updates and the final persisted decision without a page reload. Polling continues through the final payment/activity update and stops when the component unmounts.
- [ ] For `CLM-T100001`, payment remains absent and no action sends `/pay` before sign-off succeeds. The handler ID and stored `"1000.01"` amount are sent in separate requests in that order.
- [ ] A rejected sign-off displays the backend error and causes no payment request. A failed payment after successful sign-off leaves the signed decision visible and retries only `/pay`; an already recorded payment is displayed from refreshed backend state.
- [ ] An agent failure before a decision displays the failed attempt and enables explicit retry; it does not invent a fifth queue status or show the claim as successfully decided.
- [ ] Complete browser checks B4-B7 below using the test-only stub backend, not a live model.
- [ ] `npm run check:ts` and `npm run e2e` pass. Playwright runs use the test-only app factory and `reuseExistingServer:false` for both servers; occupied ports fail clearly instead of reusing a possibly live-model backend. Record results, update status and commit phase 5.

### Browser acceptance walkthroughs

These are Playwright MCP checks during implementation, in addition to automated test files. Record observations and screenshot locations in the phase results; do not claim them completed based on source inspection alone.

For B1-B3, run `npm run dev`, confirm the health URL responds, and open `http://localhost:5173/`. Do not start the live agent. For B4-B7, stop only the development processes started for these checks, then start the planned test app with `uv run -m uvicorn backend.tests.e2e_app:create_app --factory --port 8000` and the dashboard with `npx vite dashboard --port 5173 --strictPort`. The test app has a fresh temporary database and scripted scenarios. If ports are already occupied by other processes, report that instead of killing or reusing them. Stop check-only servers afterward.

- [ ] **B1 - Seeded queue and full detail:** At `/`, see 25 claims and all initially labeled "Waiting" on a fresh pilot database. Click `CLM-1001`; verify `$420.00` claimed, Premium policy, the story, three expense items, four document texts and the `CLM-0412` history entry.
- [ ] **B2 - Instructions:** Open "Agent instructions"; compare its text to `GET /api/agent/instructions`. Verify no editable field or save control, then return to the selected claim without losing the selection.
- [ ] **B3 - Brand and usable layout:** Inspect at 1440x900 and 390x844 in light and dark system preferences. Verify branded fonts/surfaces, readable status text and keyboard-focusable queue/controls; long stories/documents and money labels do not clip or force page-wide horizontal scrolling. Capture both layouts and check for unexpected console errors.
- [ ] **B4 - Visible progress and ordinary payment:** In the stub app, run `CLM-T420`. The stub pauses between tool steps long enough to observe "In progress" and an initial activity entry before completion. Within the next polling update, verify "Approved", `$420.00`, the reason/sections, ordered activity and "Simulated payment recorded" without reloading. Use awaited assertions, not fixed browser sleeps.
- [ ] **B5 - Threshold and sign-off:** Run `CLM-T1000` and confirm a simulated payment without sign-off. Run `CLM-T100001`; confirm "Waiting for sign-off" and no payment. A direct Playwright request to `POST /api/claims/CLM-T100001/pay` with `{"amount":"1000.01"}` returns 409. Select `HND-01`, click "Sign off and record payment", then verify "Decided", `$1,000.01`, recorded handler and one simulated payment. Reload and verify persistence.
- [ ] **B6 - Decline and referral:** Run `CLM-TDECLINE` and `CLM-TREFER`. Each ends "Decided" with its distinct outcome, reason and relevant section, zero payout and no payment/sign-off controls. The referral explains the missing records without sending a message.
- [ ] **B7 - Failures and recovery:** Use a fresh test-app instance, not the paid claims from B5. Run `CLM-TBAG`; verify the scripted first-attempt error, then explicitly retry and see its $200.00 decision/payment. Run `CLM-T100001`; intercept the first `/pay` request with a 503 response without forwarding it to the backend. Sign off and verify the payment error, retained sign-off and no payment-success message; remove the interception and retry payment successfully without signing off again. Intercept one read request and verify a visible connection error rather than an empty/success state.

## Phase 6: Regression proof and pilot handover

**Build and why:** Finish automated coverage of the integrated paths and document the actual pilot, not future capabilities. Reuse the synthetic fixtures and test-only app from phase 3 so this proof neither spends model credits nor leaks evaluation data.

Give stateful end-to-end scenarios separate fixture claims or fresh test-server lifetimes; do not let parallel tests race over one payment. The standard `npm run e2e` must start its own stub backend, use temporary storage and never fall back to a running development server. Windows-compatible setup belongs in Playwright configuration, `uv run` commands or `.mjs` helpers, not shell-only environment assignments.

### Success criteria

- [ ] Automated Playwright coverage reproduces the core B1-B7 behaviors where applicable: read-only navigation, live progress, ordinary payout, threshold/sign-off, decline/referral and explicit failures. Seed-count assertions use the business seed fixture; six-claim workflow fixtures are not mistaken for the 25-claim production queue.
- [ ] Backend tests verify persisted decisions, activity, sign-offs and payments after reopening the same database; new test runs use clean temporary storage, not automatic deletion of the user's pilot database.
- [ ] Contract tests inspect OpenAPI for unique operation IDs and required inputs on every new operation. Agent tests confirm no file access to business data and no tool that can sign off; no automated test makes an external model/payment request.
- [ ] Repeat the completed browser walkthroughs against the final build, record actual observations and resolve unexpected console/network errors. If the required MCP browser capability is unavailable, report that remaining verification explicitly.
- [ ] [STATUS.md](STATUS.md) documents setup/run/check commands, local database location, required environment variable names without secret values, model override, the four queue states, sign-off and simulated payments, failure/retry behavior, and non-resumable in-process execution. Clearly state that model accuracy versus handler decisions has not been measured.
- [ ] Run `npm run check` with all configured thresholds intact, record the actual results, tick verified criteria, update status and commit phase 6 with hooks enabled.
- [ ] After the last phase, run `npm run check` again as required by the process and report its result plus any remaining limitations. Do not push, provision resources, open evaluation files or add later-day features.
