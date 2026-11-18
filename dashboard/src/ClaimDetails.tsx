import { humanize, money } from "./format";
import { StatusBadge } from "./StatusBadge";
import type { ClaimDetail } from "./types";

function PolicyContext({ detail }: { readonly detail: ClaimDetail }) {
  const { policy, plan } = detail;
  const limits: [string, number][] = [
    ["Cancellation and interruption", plan.trip_cancellation_max],
    ["Trip delay", plan.trip_delay_max],
    ["Baggage delay", plan.baggage_delay_max],
    ["Baggage", plan.baggage_max],
    ["Per item", plan.per_item_limit],
    ["Passport and documents", plan.passport_max],
    ["Emergency medical", plan.emergency_medical_max],
    ["Deductible", plan.deductible],
  ];
  return (
    <details className="context-section">
      <summary>Policy and plan</summary>
      <dl className="facts">
        <div>
          <dt>Policy</dt>
          <dd className="identifier">{policy.policy_id}</dd>
        </div>
        <div>
          <dt>Plan</dt>
          <dd>{plan.name}</dd>
        </div>
        <div>
          <dt>Policy status</dt>
          <dd>{policy.status}</dd>
        </div>
        <div>
          <dt>Purchased</dt>
          <dd>{policy.purchased_on}</dd>
        </div>
        <div>
          <dt>Sold through</dt>
          <dd>{policy.sold_through}</dd>
        </div>
        <div>
          <dt>Destination</dt>
          <dd>{policy.trip.destination}</dd>
        </div>
        <div>
          <dt>Trip dates</dt>
          <dd>
            {policy.trip.departs_on} to {policy.trip.returns_on}
          </dd>
        </div>
        <div>
          <dt>Trip cost</dt>
          <dd className="money">{money(policy.trip.trip_cost)}</dd>
        </div>
        <div>
          <dt>Travelers</dt>
          <dd>{policy.travelers.join(", ")}</dd>
        </div>
      </dl>
      <h3>Benefit limits</h3>
      <dl className="facts">
        {limits.map(([label, amount]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className="money">{money(amount)}</dd>
          </div>
        ))}
      </dl>
      <p>
        Trip delay waiting period: {plan.trip_delay_waiting_hours} hours.{" "}
        Baggage delay waiting period: {plan.baggage_delay_waiting_hours} hours.
      </p>
      <p>
        Deductible applies to:{" "}
        {plan.deductible_applies_to.map(humanize).join(", ")}.
      </p>
      <h3>Add-ons</h3>
      {plan.add_ons.length ? (
        plan.add_ons.map((addon) => (
          <div key={addon.add_on}>
            <strong>{addon.name}</strong>
            <p>{addon.effect}</p>
            {addon.electronics_per_item_limit !== null && (
              <p>
                Electronics per-item limit:{" "}
                {money(addon.electronics_per_item_limit)}
              </p>
            )}
          </div>
        ))
      ) : (
        <p>No add-ons on this policy.</p>
      )}
    </details>
  );
}

function CustomerContext({ detail }: { readonly detail: ClaimDetail }) {
  const customer = detail.customer;
  return (
    <details className="context-section">
      <summary>Customer and claim history</summary>
      <dl className="facts">
        <div>
          <dt>Customer</dt>
          <dd>{customer.name}</dd>
        </div>
        <div>
          <dt>Customer ID</dt>
          <dd className="identifier">{customer.customer_id}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{customer.email}</dd>
        </div>
        <div>
          <dt>Phone</dt>
          <dd>{customer.phone}</dd>
        </div>
        <div>
          <dt>Date of birth</dt>
          <dd>{customer.date_of_birth}</dd>
        </div>
        <div>
          <dt>Customer since</dt>
          <dd>{customer.customer_since}</dd>
        </div>
        <div>
          <dt>Address</dt>
          <dd>
            {customer.address.street}, {customer.address.city},{" "}
            {customer.address.state} {customer.address.zip}
          </dd>
        </div>
      </dl>
      <h3>Previous claims</h3>
      {customer.previous_claims.length ? (
        <ul className="history-list">
          {customer.previous_claims.map((claim) => (
            <li key={claim.claim_id}>
              <span className="identifier">{claim.claim_id}</span>
              <p>{claim.summary}</p>
              <p>
                {humanize(claim.claim_type)} / {claim.outcome} /{" "}
                {money(claim.amount_paid)}
              </p>
              <p className="muted">
                Incident {claim.incident_date}; filed {claim.filed_on}.
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p>No previous claims.</p>
      )}
    </details>
  );
}

export function ClaimDetails({ detail }: { readonly detail: ClaimDetail }) {
  const { claim } = detail;
  return (
    <section className="panel claim-detail" aria-label="Claim details">
      <div className="row-line">
        <p className="eyebrow identifier">{claim.claim_id}</p>
        <StatusBadge status={claim.status} />
      </div>
      <h2>{claim.summary}</h2>
      <p className="muted">
        {detail.customer.name} / {detail.plan.name}
      </p>
      <dl className="facts">
        <div>
          <dt>Amount claimed</dt>
          <dd className="money">{money(claim.amount_claimed)}</dd>
        </div>
        <div>
          <dt>Claim type</dt>
          <dd className="claim-type">{humanize(claim.claim_type)}</dd>
        </div>
        <div>
          <dt>Incident</dt>
          <dd>{claim.incident_date}</dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>{claim.incident_location}</dd>
        </div>
        <div>
          <dt>Submitted</dt>
          <dd>{claim.submitted_on}</dd>
        </div>
      </dl>
      <h3>Customer's account</h3>
      <p className="prose">{claim.story}</p>
      <h3>Claimed items</h3>
      <ul className="item-list">
        {claim.items.map((item) => (
          <li key={`${item.description}-${item.category}`}>
            <span>
              {item.description}
              <small>{humanize(item.category)}</small>
            </span>
            <span className="money">{money(item.amount)}</span>
          </li>
        ))}
      </ul>
      <h3>Supporting documents</h3>
      {claim.documents.map((document) => (
        <details className="document" key={document.name}>
          <summary>{document.name}</summary>
          <p className="muted">{humanize(document.type)}</p>
          <p className="prose">{document.content}</p>
        </details>
      ))}
      <PolicyContext detail={detail} />
      <CustomerContext detail={detail} />
    </section>
  );
}
