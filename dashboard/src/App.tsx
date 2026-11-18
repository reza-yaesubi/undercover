import { useState } from "react";
import { claimPath } from "./api";
import { ClaimQueue } from "./ClaimQueue";
import { ClaimWorkspace } from "./ClaimWorkspace";
import { ErrorNotice } from "./ErrorNotice";
import { money } from "./format";
import type {
  ActivityList,
  ClaimDetail,
  ClaimQueue as QueueData,
  Instructions,
} from "./types";
import { useResource } from "./useResource";
import "./styles.css";

export function App() {
  const [view, setView] = useState<"claims" | "instructions">("claims");
  const [selected, setSelected] = useState<string | null>(null);
  const queue = useResource<QueueData>("/api/claims", view === "claims");
  const detail = useResource<ClaimDetail>(
    selected === null ? null : claimPath(selected),
    view === "claims",
  );
  const activity = useResource<ActivityList>(
    selected === null ? null : `${claimPath(selected)}/activity`,
    view === "claims",
  );
  const instructions = useResource<Instructions>(
    view === "instructions" ? "/api/agent/instructions" : null,
  );

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            UC
          </span>
          <div>
            <h1>UnderCover</h1>
            <p>Travel insurance / Claims workspace</p>
          </div>
        </div>
        <nav aria-label="Workspace">
          <button
            aria-pressed={view === "claims"}
            onClick={() => {
              setView("claims");
            }}
          >
            Claims queue
          </button>
          <button
            aria-pressed={view === "instructions"}
            onClick={() => {
              setView("instructions");
            }}
          >
            Agent instructions
          </button>
        </nav>
      </header>
      <main>
        <div className="page-heading">
          <div>
            <p className="eyebrow">The claims pilot</p>
            <h2>
              {view === "claims"
                ? "Every claim, in clear view."
                : "How the agent works."}
            </h2>
          </div>
          <p className="pilot-note">Pilot only. No real payments.</p>
        </div>
        {view === "instructions" ? (
          <section className="panel instructions-panel">
            <h2>Agent instructions</h2>
            <p className="muted">
              Read only. Served by the backend, just as the agent receives them.
            </p>
            {instructions.loading && (
              <p role="status">Loading instructions...</p>
            )}
            {instructions.error && (
              <ErrorNotice
                message={instructions.error}
                onRetry={instructions.reload}
                label="Retry instructions"
              />
            )}
            {instructions.data && (
              <>
                <p>
                  Handler sign-off is required above{" "}
                  {money(instructions.data.payout_approval_limit)}.
                </p>
                <pre className="instructions-text">
                  {instructions.data.content}
                </pre>
              </>
            )}
          </section>
        ) : (
          <div className="workspace">
            <aside className="panel queue-panel" aria-label="Claims queue">
              <div className="row-line">
                <h2>Claims queue</h2>
                {queue.data && (
                  <span className="count">{queue.data.total} claims</span>
                )}
              </div>
              <p className="muted">
                Select a claim to review its evidence and progress.
              </p>
              {queue.loading && <p role="status">Loading claims...</p>}
              {queue.error && (
                <ErrorNotice
                  message={queue.error}
                  onRetry={queue.reload}
                  label="Retry queue"
                />
              )}
              {queue.data && (
                <ClaimQueue
                  claims={queue.data.claims}
                  selected={selected}
                  onSelect={setSelected}
                />
              )}
            </aside>
            <ClaimWorkspace
              selected={selected}
              detail={detail}
              activity={activity}
              onRefresh={() => {
                queue.reload();
                detail.reload();
                activity.reload();
              }}
            />
          </div>
        )}
      </main>
      <footer>UnderCover Travel Insurance / All amounts in US dollars</footer>
    </div>
  );
}
