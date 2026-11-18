import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { ClaimDetails } from "./ClaimDetails";
import { DecisionCard } from "./DecisionCard";
import {
  activity,
  decisionFor,
  detailFor,
  jsonResponse,
  queueFor,
} from "./test-data";
import type { Outcome, QueueStatus } from "./types";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function serve(overrides: Record<string, unknown> = {}) {
  const detail = detailFor();
  const responses: Record<string, unknown> = {
    "/api/claims": queueFor(detail),
    "/api/claims/CLM-1001": detail,
    "/api/claims/CLM-1001/activity": activity,
    "/api/agent/instructions": {
      content: "Read all evidence before deciding. Follow the policy wording.",
      currency: "USD",
      payout_approval_limit: "1000.00",
    },
    ...overrides,
  };
  const fetch = vi.fn((path: string) =>
    Promise.resolve(
      Object.hasOwn(responses, path)
        ? jsonResponse(responses[path])
        : jsonResponse({ detail: "Not found" }, 404),
    ),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

it("loads the queue and displays full claim context and operational activity", async () => {
  serve();
  render(<App />);
  expect(screen.getByText("Loading claims...")).toBeDefined();
  fireEvent.click(
    await screen.findByRole("button", { name: "Open claim CLM-1001" }),
  );
  expect(
    await screen.findByText(
      "My flight was delayed overnight. Receipts are attached.",
    ),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Hotel total: $245.00.")).toBeDefined();
  expect(screen.getByText("CLM-0412")).toBeDefined();
  expect(screen.getByText("Test travel desk")).toBeDefined();
  expect(await screen.findByText("Read policy wording.")).toBeDefined();
  expect(screen.getByText("Waiting for an agent decision.")).toBeDefined();
});

it("shows read-only API instructions and preserves the selected claim", async () => {
  serve();
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Open claim CLM-1001" }),
  );
  await screen.findByText(
    "My flight was delayed overnight. Receipts are attached.",
  );
  fireEvent.click(screen.getByRole("button", { name: "Agent instructions" }));
  expect(
    await screen.findByText(
      "Read all evidence before deciding. Follow the policy wording.",
    ),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Claims queue" }));
  expect(
    screen
      .getByRole("button", { name: "Open claim CLM-1001" })
      .getAttribute("aria-pressed"),
  ).toBe("true");
  expect(
    screen.getByText("My flight was delayed overnight. Receipts are attached."),
  ).toBeDefined();
});

it("labels all four queue states", async () => {
  const statuses: QueueStatus[] = [
    "waiting",
    "in_progress",
    "waiting_for_sign_off",
    "decided",
  ];
  const details = statuses.map((status, index) => {
    const detail = detailFor(`CLM-${String(index)}`);
    detail.claim.status = status;
    return detail;
  });
  serve({ "/api/claims": queueFor(...details) });
  render(<App />);
  for (const label of [
    "Waiting",
    "In progress",
    "Waiting for sign-off",
    "Decided",
  ]) {
    expect(await screen.findByText(label)).toBeDefined();
  }
});

it.each<{ outcome: Outcome; label: string }>([
  { outcome: "approve", label: "Approved" },
  { outcome: "decline", label: "Declined" },
  { outcome: "refer", label: "Referred" },
])("renders the $label decision and its explanation", ({ outcome, label }) => {
  const detail = detailFor();
  detail.decision = decisionFor(outcome);
  render(<DecisionCard detail={detail} />);
  expect(screen.getByText(label)).toBeDefined();
  expect(
    screen.getByText(
      "The evidence was reviewed against the policy. The cited section explains the outcome.",
    ),
  ).toBeDefined();
  expect(screen.getByText("Policy sections 3, 10")).toBeDefined();
  expect(screen.getByText("245.00 + 95.00 + 80.00 = 420.00.")).toBeDefined();
});

it("distinguishes sign-off pending, failed runs, and recorded simulated payment", () => {
  const detail = detailFor();
  detail.claim.status = "waiting_for_sign_off";
  detail.decision = { ...decisionFor(), payout: "1000.01" };
  const { rerender } = render(<DecisionCard detail={detail} />);
  expect(
    screen.getByText("Payment blocked pending handler sign-off."),
  ).toBeDefined();
  expect(screen.getByText("$1,000.01")).toBeDefined();
  detail.claim.status = "decided";
  detail.sign_off = {
    handler_id: "HND-01",
    signed_off_at: "2026-11-18T12:00:00+00:00",
  };
  detail.payment = {
    amount: "1000.01",
    simulated: true,
    paid_at: "2026-11-18T12:00:01+00:00",
  };
  detail.run = {
    thread_id: "test-thread",
    status: "failed",
    error: "Failure after payment.",
    started_at: "2026-11-18T12:00:00+00:00",
    finished_at: "2026-11-18T12:00:01+00:00",
  };
  rerender(<DecisionCard detail={detail} />);
  expect(screen.getByText("Simulated payment recorded")).toBeDefined();
  expect(screen.getByText("HND-01")).toBeDefined();
  expect(screen.getByRole("alert").textContent).toContain(
    "Failure after payment.",
  );
});

it("renders add-ons and document contents as text without editable markup", () => {
  const detail = detailFor();
  detail.customer.previous_claims = [];
  detail.plan.add_ons = [
    {
      add_on: "electronics_plus",
      name: "Electronics Plus",
      effect: "A higher limit.",
      electronics_per_item_limit: 1200,
    },
    {
      add_on: "adventure_sports",
      name: "Adventure Sports",
      effect: "Specified sports are covered.",
      electronics_per_item_limit: null,
    },
  ];
  detail.claim.documents = [
    {
      name: "Uploaded text",
      type: "receipt",
      content: "<img src=x onerror=alert(1)>",
    },
  ];
  render(<ClaimDetails detail={detail} />);
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeDefined();
  expect(screen.queryByRole("img")).toBeNull();
  expect(
    screen.getByText("Electronics per-item limit: $1,200.00"),
  ).toBeDefined();
  expect(screen.getByText("No previous claims.")).toBeDefined();
});

it("shows an empty queue only after a successful empty response", async () => {
  serve({ "/api/claims": { claims: [], total: 0 } });
  render(<App />);
  expect(
    await screen.findByText("There are no claims in the queue."),
  ).toBeDefined();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("renders instructions as text rather than executable markup", async () => {
  serve({
    "/api/agent/instructions": {
      content: "<script>alert('instructions')</script>",
      currency: "USD",
      payout_approval_limit: "1000.00",
    },
  });
  const { container } = render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Agent instructions" }));
  expect(
    await screen.findByText("<script>alert('instructions')</script>"),
  ).toBeDefined();
  expect(container.querySelector("script")).toBeNull();
});

it("reports a network failure and lets the handler retry the queue", async () => {
  const fetch = serve();
  fetch.mockRejectedValueOnce(new Error("Connection unavailable"));
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Connection unavailable",
  );
  expect(screen.queryByText("There are no claims in the queue.")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry queue" }));
  expect(
    await screen.findByRole("button", { name: "Open claim CLM-1001" }),
  ).toBeDefined();
});

it("reports a missing claim instead of showing an empty detail", async () => {
  const fetch = serve();
  const original = fetch.getMockImplementation();
  fetch.mockImplementation((path) => {
    if (path === "/api/claims/CLM-1001") {
      return Promise.resolve(jsonResponse({ detail: "Claim not found" }, 404));
    }
    if (!original) throw new Error("Missing mock");
    return original(path);
  });
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Open claim CLM-1001" }),
  );
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Claim not found",
  );
  expect(screen.getByRole("button", { name: "Retry claim" })).toBeDefined();
});

it("discards a late response from a previously selected claim", async () => {
  const second = detailFor("CLM-1002");
  second.claim.story = "This is the second claim.";
  let release: ((response: Response) => void) | undefined;
  const delayed = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const fetch = serve({
    "/api/claims": queueFor(detailFor(), second),
    "/api/claims/CLM-1002": second,
    "/api/claims/CLM-1002/activity": { events: [] },
  });
  const original = fetch.getMockImplementation();
  fetch.mockImplementation((path) => {
    if (path === "/api/claims/CLM-1001") return delayed;
    if (!original) throw new Error("Missing mock");
    return original(path);
  });
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Open claim CLM-1001" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Open claim CLM-1002" }));
  expect(await screen.findByText("This is the second claim.")).toBeDefined();
  if (!release) throw new Error("Missing delayed response resolver");
  release(jsonResponse(detailFor()));
  await waitFor(() => {
    expect(
      screen.queryByText(
        "My flight was delayed overnight. Receipts are attached.",
      ),
    ).toBeNull();
  });
  expect(screen.getByText("No agent activity yet.")).toBeDefined();
});
