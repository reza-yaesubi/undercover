import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { decisionFor, detailFor, jsonResponse, queueFor } from "./test-data";
import { useResource } from "./useResource";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function workflow() {
  const detail = detailFor();
  const calls: { path: string; body: unknown }[] = [];
  const errors = new Map<string, string>();
  const events = {
    events: [] as {
      sequence: number;
      thread_id: string;
      kind: string;
      message: string;
      created_at: string;
    }[],
  };
  function respond(path: string, options: RequestInit) {
    if (options.method === "POST") {
      calls.push({
        path,
        body:
          typeof options.body === "string"
            ? (JSON.parse(options.body) as unknown)
            : null,
      });
      const error = errors.get(path);
      if (error) return jsonResponse({ detail: error }, 503);
      if (path.endsWith("/sign-off")) {
        detail.sign_off = {
          handler_id: "HND-01",
          signed_off_at: "2026-11-18T12:00:00Z",
        };
        detail.claim.status = "decided";
      } else if (path.endsWith("/pay")) {
        detail.payment = {
          amount: detail.decision?.payout ?? "0.00",
          simulated: true,
          paid_at: "2026-11-18T12:00:01Z",
        };
      } else if (path.endsWith("/run")) {
        detail.claim.status = "in_progress";
        detail.run = {
          thread_id: "test-run",
          status: "running",
          started_at: "2026-11-18T12:00:00Z",
          finished_at: null,
          error: null,
        };
      }
      return jsonResponse({});
    }
    if (path === "/api/claims") return jsonResponse(queueFor(detail));
    if (path.endsWith("/activity")) return jsonResponse(events);
    if (path === "/api/handlers")
      return jsonResponse({
        handlers: [
          {
            handler_id: "HND-01",
            name: "Eligible handler",
            can_approve_over_limit: true,
          },
          {
            handler_id: "HND-02",
            name: "Ineligible handler",
            can_approve_over_limit: false,
          },
        ],
      });
    return jsonResponse(detail);
  }
  const fetch = vi.fn((path: string, options: RequestInit) =>
    Promise.resolve(respond(path, options)),
  );
  vi.stubGlobal("fetch", fetch);
  return { detail, calls, errors, events, fetch };
}

async function openClaim() {
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Open claim CLM-1001" }),
  );
}

function overLimit(state: ReturnType<typeof workflow>) {
  state.detail.decision = { ...decisionFor(), payout: "1000.01" };
  state.detail.claim.status = "waiting_for_sign_off";
}

async function signOff() {
  await screen.findByRole("option", { name: "Eligible handler (HND-01)" });
  expect(screen.queryByRole("option", { name: /Ineligible/ })).toBeNull();
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Sign off and record payment" }),
  );
}

it("starts once and polls through the saved decision to final payment and activity", async () => {
  const state = workflow();
  await openClaim();
  const button = await screen.findByRole("button", { name: "Run agent" });
  fireEvent.click(button);
  fireEvent.click(button);
  expect(
    await screen.findByText(
      "Agent is working. Activity updates automatically.",
    ),
  ).toBeDefined();
  expect(state.calls).toEqual([
    { path: "/api/claims/CLM-1001/run", body: null },
  ]);
  state.detail.claim.status = "decided";
  state.detail.decision = decisionFor();
  expect(
    await screen.findByText("Approved", {}, { timeout: 2500 }),
  ).toBeDefined();
  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "Retry payment" })
      .disabled,
  ).toBe(true);
  state.detail.payment = {
    amount: "420.00",
    simulated: true,
    paid_at: "2026-11-18T12:00:10Z",
  };
  if (!state.detail.run) throw new Error("Missing run");
  state.detail.run.status = "completed";
  state.events.events.push({
    sequence: 1,
    thread_id: "test-run",
    kind: "completed",
    message: "Finished the run.",
    created_at: "2026-11-18T12:00:10Z",
  });
  expect(
    await screen.findByText(
      "Simulated payment recorded",
      {},
      { timeout: 2500 },
    ),
  ).toBeDefined();
  expect(await screen.findByText("Finished the run.")).toBeDefined();
});

it("requires an eligible handler and signs off before paying the stored amount", async () => {
  const state = workflow();
  overLimit(state);
  await openClaim();
  expect(
    (
      await screen.findByRole<HTMLButtonElement>("button", {
        name: "Sign off and record payment",
      })
    ).disabled,
  ).toBe(true);
  expect(state.calls).toEqual([]);
  await signOff();
  expect(await screen.findByText("Simulated payment recorded")).toBeDefined();
  expect(state.calls).toEqual([
    { path: "/api/claims/CLM-1001/sign-off", body: { handler_id: "HND-01" } },
    { path: "/api/claims/CLM-1001/pay", body: { amount: "1000.01" } },
  ]);
});

it("does not pay after rejected sign-off", async () => {
  const state = workflow();
  overLimit(state);
  state.errors.set("/api/claims/CLM-1001/sign-off", "Handler is not eligible");
  await openClaim();
  await signOff();
  expect(await screen.findByText("Handler is not eligible")).toBeDefined();
  expect(state.calls).toHaveLength(1);
  expect(screen.queryByText("Simulated payment recorded")).toBeNull();
});

it("preserves sign-off after failed payment and retries only payment", async () => {
  const state = workflow();
  overLimit(state);
  state.errors.set("/api/claims/CLM-1001/pay", "Payment unavailable");
  await openClaim();
  await signOff();
  expect(await screen.findByText("Payment unavailable")).toBeDefined();
  expect(await screen.findByText("HND-01")).toBeDefined();
  expect(screen.queryByText("Simulated payment recorded")).toBeNull();
  state.errors.clear();
  fireEvent.click(await screen.findByRole("button", { name: "Retry payment" }));
  expect(await screen.findByText("Simulated payment recorded")).toBeDefined();
  expect(state.calls.map(({ path }) => path)).toEqual([
    "/api/claims/CLM-1001/sign-off",
    "/api/claims/CLM-1001/pay",
    "/api/claims/CLM-1001/pay",
  ]);
});

it("retries a failed agent without inventing a decision and recovers an unpaid approval", async () => {
  const state = workflow();
  state.detail.run = {
    thread_id: "failed",
    status: "failed",
    started_at: "2026-11-18T12:00:00Z",
    finished_at: "2026-11-18T12:00:01Z",
    error: "Tool unavailable",
  };
  await openClaim();
  expect(await screen.findByText("Tool unavailable")).toBeDefined();
  expect(screen.getByText("Waiting for an agent decision.")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Retry agent" }));
  expect(
    await screen.findByText(
      "Agent is working. Activity updates automatically.",
    ),
  ).toBeDefined();
  state.detail.claim.status = "decided";
  state.detail.decision = decisionFor();
  state.detail.run.status = "failed";
  state.detail.run.error = "Payment tool failed";
  const pay = await screen.findByRole(
    "button",
    { name: "Retry payment" },
    { timeout: 2500 },
  );
  fireEvent.click(pay);
  expect(await screen.findByText("Simulated payment recorded")).toBeDefined();
});

it("never overlaps polling reads and aborts and stops polling on unmount", async () => {
  vi.useFakeTimers();
  let release: ((response: Response) => void) | undefined;
  const signals: (AbortSignal | null | undefined)[] = [];
  const fetch = vi.fn((path: string, options: RequestInit) => {
    expect(path).toBe("/slow");
    signals.push(options.signal);
    return new Promise<Response>((resolve) => {
      release = resolve;
    });
  });
  vi.stubGlobal("fetch", fetch);
  const hook = renderHook(() => useResource<{ value: number }>("/slow", true));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(fetch).toHaveBeenCalledTimes(1);
  await act(async () => {
    if (!release) throw new Error("Missing resolver");
    release(jsonResponse({ value: 1 }));
    await Promise.resolve();
  });
  expect(hook.result.current.data).toEqual({ value: 1 });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(fetch).toHaveBeenCalledTimes(2);
  const signal = signals[1];
  hook.unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("refreshes backend payment state even when a duplicate action returns an error", async () => {
  const state = workflow();
  state.detail.claim.status = "decided";
  state.detail.decision = decisionFor();
  await openClaim();
  const pay = await screen.findByRole("button", { name: "Retry payment" });
  state.detail.payment = {
    amount: "420.00",
    simulated: true,
    paid_at: "2026-11-18T12:00:01Z",
  };
  state.errors.set("/api/claims/CLM-1001/pay", "Claim already paid");
  fireEvent.click(pay);
  await waitFor(() => {
    expect(screen.getByText("Simulated payment recorded")).toBeDefined();
  });
  expect(screen.queryByRole("button", { name: "Retry payment" })).toBeNull();
});
