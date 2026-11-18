import type {
  ActivityList,
  ClaimDetail,
  ClaimQueue,
  Decision,
  Outcome,
} from "./types";

export function detailFor(claimId = "CLM-1001"): ClaimDetail {
  return {
    claim: {
      claim_id: claimId,
      policy_id: "POL-TEST",
      customer_id: "CUS-TEST",
      claim_type: "trip_delay",
      submitted_on: "2026-06-24",
      incident_date: "2026-06-18",
      incident_location: "Rome, Italy",
      summary: "Crew delay with hotel and meals",
      story: "My flight was delayed overnight. Receipts are attached.",
      items: [
        {
          description: "Airport hotel",
          category: "accommodation",
          amount: 245,
        },
        { description: "Meals", category: "meals", amount: 95 },
        { description: "Taxis", category: "transport", amount: 80 },
      ],
      amount_claimed: 420,
      documents: [
        {
          name: "Carrier report",
          type: "carrier_report",
          content: "Crew delay of 19 hours.",
        },
        {
          name: "Hotel receipt",
          type: "receipt",
          content: "Hotel total: $245.00.",
        },
      ],
      status: "waiting",
    },
    policy: {
      policy_id: "POL-TEST",
      customer_id: "CUS-TEST",
      plan: "premium",
      add_ons: [],
      purchased_on: "2026-04-22",
      sold_through: "Test travel desk",
      trip: {
        destination: "Rome",
        departs_on: "2026-06-10",
        returns_on: "2026-06-18",
        trip_cost: 3100,
      },
      travelers: ["Morgan Example"],
      status: "active",
    },
    customer: {
      customer_id: "CUS-TEST",
      name: "Morgan Example",
      email: "morgan@example.test",
      phone: "555-0100",
      date_of_birth: "1990-01-01",
      address: {
        street: "1 Test Street",
        city: "Test City",
        state: "NY",
        zip: "10000",
      },
      customer_since: "2023-01-01",
      previous_claims: [
        {
          claim_id: "CLM-0412",
          filed_on: "2024-08-19",
          incident_date: "2024-08-09",
          claim_type: "baggage_delay",
          summary: "Delayed bag on an earlier trip",
          outcome: "approved",
          amount_paid: 140,
        },
      ],
    },
    plan: {
      plan: "premium",
      name: "UnderCover Premium",
      trip_cancellation_max: 5000,
      trip_delay_waiting_hours: 6,
      trip_delay_max: 800,
      baggage_delay_waiting_hours: 12,
      baggage_delay_max: 300,
      baggage_max: 1500,
      per_item_limit: 300,
      passport_max: 250,
      emergency_medical_max: 100000,
      deductible: 50,
      deductible_applies_to: ["baggage", "emergency_medical"],
      add_ons: [],
    },
    decision: null,
    sign_off: null,
    payment: null,
    run: null,
  };
}

export function queueFor(...details: ClaimDetail[]): ClaimQueue {
  return {
    total: details.length,
    claims: details.map(({ claim, customer }) => ({
      claim_id: claim.claim_id,
      customer_name: customer.name,
      claim_type: claim.claim_type,
      summary: claim.summary,
      amount_claimed: claim.amount_claimed,
      status: claim.status,
    })),
  };
}

export function decisionFor(outcome: Outcome = "approve"): Decision {
  return {
    thread_id: "test-thread",
    outcome,
    payout: outcome === "approve" ? "420.00" : "0.00",
    reason: [
      "The evidence was reviewed against the policy.",
      "The cited section explains the outcome.",
    ],
    policy_sections: [3, 10],
    calculation: "245.00 + 95.00 + 80.00 = 420.00.",
    recorded_at: "2026-11-18T12:00:00+00:00",
  };
}

export const activity: ActivityList = {
  events: [
    {
      sequence: 1,
      thread_id: "test-thread",
      kind: "started",
      message: "Agent run started.",
      created_at: "2026-11-18T12:00:00+00:00",
    },
    {
      sequence: 2,
      thread_id: "test-thread",
      kind: "tool_result",
      message: "Read policy wording.",
      created_at: "2026-11-18T12:00:01+00:00",
    },
  ],
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
