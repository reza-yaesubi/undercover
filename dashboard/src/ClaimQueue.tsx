import { humanize, money } from "./format";
import { StatusBadge } from "./StatusBadge";
import type { ClaimSummary } from "./types";

export function ClaimQueue({
  claims,
  selected,
  onSelect,
}: {
  readonly claims: ClaimSummary[];
  readonly selected: string | null;
  readonly onSelect: (claimId: string) => void;
}) {
  if (claims.length === 0) {
    return <p className="empty-state">There are no claims in the queue.</p>;
  }
  return (
    <ul className="claim-list">
      {claims.map((claim) => (
        <li key={claim.claim_id}>
          <button
            className="claim-row"
            aria-label={`Open claim ${claim.claim_id}`}
            aria-pressed={selected === claim.claim_id}
            onClick={() => {
              onSelect(claim.claim_id);
            }}
          >
            <span className="row-line">
              <span className="identifier">{claim.claim_id}</span>
              <span className="money">{money(claim.amount_claimed)}</span>
            </span>
            <strong>{claim.customer_name}</strong>
            <span className="claim-summary">{claim.summary}</span>
            <span className="row-line">
              <span className="claim-type">{humanize(claim.claim_type)}</span>
              <StatusBadge status={claim.status} />
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
