import { dateTime, money } from "./format";
import type { ClaimDetail, Outcome } from "./types";

const outcomes: Record<Outcome, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

function PaymentState({ detail }: { readonly detail: ClaimDetail }) {
  if (detail.payment) {
    return (
      <p className="payment-state">
        <strong>Simulated payment recorded</strong>
        <span>
          {money(detail.payment.amount)} on {dateTime(detail.payment.paid_at)}
        </span>
      </p>
    );
  }
  if (detail.claim.status === "waiting_for_sign_off") {
    return (
      <p className="payment-state">Payment blocked pending handler sign-off.</p>
    );
  }
  if (
    detail.decision?.outcome === "approve" &&
    Number(detail.decision.payout) > 0
  ) {
    return <p className="payment-state">No simulated payment recorded yet.</p>;
  }
  return <p className="payment-state">No payment is due.</p>;
}

export function DecisionCard({ detail }: { readonly detail: ClaimDetail }) {
  const decision = detail.decision;
  return (
    <section
      className={`panel decision-panel decision-${decision?.outcome ?? "pending"}`}
    >
      <p className="eyebrow">UnderCover Agent</p>
      <h2>Decision</h2>
      {decision ? (
        <>
          <div className="decision-heading">
            <strong>{outcomes[decision.outcome]}</strong>
            <span className="money">{money(decision.payout)}</span>
          </div>
          <p>{decision.reason.join(" ")}</p>
          <p className="policy-citation">
            Policy sections {decision.policy_sections.join(", ")}
          </p>
          <details>
            <summary>Calculation</summary>
            <p className="calculation">{decision.calculation}</p>
          </details>
          {detail.sign_off && (
            <p>
              Signed off by{" "}
              <span className="identifier">{detail.sign_off.handler_id}</span>
              {" on "}
              {dateTime(detail.sign_off.signed_off_at)}.
            </p>
          )}
          <PaymentState detail={detail} />
        </>
      ) : (
        <p className="muted">Waiting for an agent decision.</p>
      )}
      {detail.run?.status === "failed" && (
        <div className="error-notice" role="alert">
          <strong>Agent run failed</strong>
          <p>{detail.run.error}</p>
        </div>
      )}
    </section>
  );
}
