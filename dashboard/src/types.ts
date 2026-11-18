export type QueueStatus =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";
export type Outcome = "approve" | "decline" | "refer";

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  status: QueueStatus;
}

export interface ClaimQueue {
  claims: ClaimSummary[];
  total: number;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: { description: string; category: string; amount: number }[];
  amount_claimed: number;
  documents: { name: string; type: string; content: string }[];
  status: QueueStatus;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  address: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  customer_since: string;
  previous_claims: {
    claim_id: string;
    filed_on: string;
    incident_date: string;
    claim_type: string;
    summary: string;
    outcome: string;
    amount_paid: number;
  }[];
}

export interface Plan {
  plan: string;
  name: string;
  trip_cancellation_max: number;
  trip_delay_waiting_hours: number;
  trip_delay_max: number;
  baggage_delay_waiting_hours: number;
  baggage_delay_max: number;
  baggage_max: number;
  per_item_limit: number;
  passport_max: number;
  emergency_medical_max: number;
  deductible: number;
  deductible_applies_to: string[];
  add_ons: {
    add_on: string;
    name: string;
    effect: string;
    electronics_per_item_limit: number | null;
  }[];
}

export interface Decision {
  thread_id: string;
  outcome: Outcome;
  payout: string;
  reason: string[];
  policy_sections: number[];
  calculation: string;
  recorded_at: string;
}

export interface ClaimDetail {
  claim: Claim;
  policy: Policy;
  customer: Customer;
  plan: Plan;
  decision: Decision | null;
  sign_off: { handler_id: string; signed_off_at: string } | null;
  payment: { amount: string; simulated: true; paid_at: string } | null;
  run: {
    thread_id: string;
    status: "running" | "completed" | "failed";
    started_at: string;
    finished_at: string | null;
    error: string | null;
  } | null;
}

export interface Activity {
  sequence: number;
  thread_id: string;
  kind: string;
  message: string;
  created_at: string;
}

export interface ActivityList {
  events: Activity[];
}

export interface Instructions {
  content: string;
  currency: "USD";
  payout_approval_limit: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  can_approve_over_limit: boolean;
}
