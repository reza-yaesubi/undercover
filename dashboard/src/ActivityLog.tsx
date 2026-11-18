import { dateTime, humanize } from "./format";
import type { Activity } from "./types";

export function ActivityLog({ events }: { readonly events: Activity[] }) {
  return (
    <>
      <h2>Agent activity</h2>
      <p className="muted">Operational steps, not private model reasoning.</p>
      {events.length ? (
        <ol className="activity-list">
          {events.map((event) => (
            <li key={event.sequence}>
              <span className={`activity-kind activity-${event.kind}`}>
                {humanize(event.kind)}
              </span>
              <p>{event.message}</p>
              <time dateTime={event.created_at}>
                {dateTime(event.created_at)}
              </time>
              <span className="activity-thread">
                Thread <span className="identifier">{event.thread_id}</span>
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p>No agent activity yet.</p>
      )}
    </>
  );
}
