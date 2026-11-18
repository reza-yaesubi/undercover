import { useRef, useState } from "react";
import { claimPath, errorMessage, request } from "./api";
import { ErrorNotice } from "./ErrorNotice";
import type { ClaimDetail, Handler } from "./types";
import { useResource } from "./useResource";

type Action = "run" | "sign-off" | "pay";

function SignOffControls({
  disabled,
  onSubmit,
}: {
  readonly disabled: boolean;
  readonly onSubmit: (handler: string) => void;
}) {
  const [handler, setHandler] = useState("");
  const handlers = useResource<{ handlers: Handler[] }>("/api/handlers");
  const eligible =
    handlers.data?.handlers.filter((item) => item.can_approve_over_limit) ?? [];
  return (
    <>
      <p>
        Choose an eligible handler to authorize this approval. This pilot does
        not verify identity.
      </p>
      {handlers.loading && <p role="status">Loading handlers...</p>}
      {handlers.error && (
        <ErrorNotice
          message={handlers.error}
          onRetry={handlers.reload}
          label="Retry handlers"
        />
      )}
      <label htmlFor="handler">Handler</label>
      <select
        id="handler"
        value={handler}
        disabled={disabled}
        onChange={(event) => {
          setHandler(event.target.value);
        }}
      >
        <option value="">Select a handler</option>
        {eligible.map((item) => (
          <option key={item.handler_id} value={item.handler_id}>
            {item.name} ({item.handler_id})
          </option>
        ))}
      </select>
      <button
        className="button"
        disabled={
          disabled ||
          !eligible.some((item) => item.handler_id === handler) ||
          Boolean(handlers.error)
        }
        onClick={() => {
          onSubmit(handler);
        }}
      >
        Sign off and record payment
      </button>
    </>
  );
}

function canPay(detail: ClaimDetail): boolean {
  return (
    detail.decision?.outcome === "approve" &&
    Number(detail.decision.payout) > 0 &&
    !detail.payment &&
    detail.claim.status !== "waiting_for_sign_off"
  );
}

export function ClaimActions({
  detail,
  refreshing,
  onRefresh,
}: {
  readonly detail: ClaimDetail;
  readonly refreshing: boolean;
  readonly onRefresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const locked = useRef(false);
  const needsSignOff = detail.claim.status === "waiting_for_sign_off";
  const running = detail.run?.status === "running";
  const disabled = busy || refreshing || running;

  async function act(action: Action, handler = "") {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError(null);
    const path = claimPath(detail.claim.claim_id);
    try {
      if (action === "run") {
        await request<unknown>(`${path}/run`, { method: "POST" });
      } else {
        if (action === "sign-off") {
          await request<unknown>(`${path}/sign-off`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ handler_id: handler }),
          });
        }
        await request<unknown>(`${path}/pay`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount: detail.decision?.payout }),
        });
      }
    } catch (failure: unknown) {
      setError(errorMessage(failure));
    } finally {
      onRefresh();
      locked.current = false;
      setBusy(false);
    }
  }

  return (
    <section className="panel action-panel" aria-label="Claim actions">
      {running && (
        <p role="status">Agent is working. Activity updates automatically.</p>
      )}
      {busy && <p role="status">Submitting request...</p>}
      {error && (
        <div className="error-notice" role="alert">
          {error}
        </div>
      )}
      {detail.claim.status === "waiting" && !detail.decision && (
        <button
          className="button"
          disabled={disabled}
          onClick={() => {
            void act("run");
          }}
        >
          {detail.run?.status === "failed" ? "Retry agent" : "Run agent"}
        </button>
      )}
      {needsSignOff && (
        <SignOffControls
          disabled={disabled}
          onSubmit={(handler) => {
            void act("sign-off", handler);
          }}
        />
      )}
      {canPay(detail) && (
        <button
          className="button"
          disabled={disabled}
          onClick={() => {
            void act("pay");
          }}
        >
          Retry payment
        </button>
      )}
    </section>
  );
}
