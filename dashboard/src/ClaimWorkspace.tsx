import { ActivityLog } from "./ActivityLog";
import { ClaimDetails } from "./ClaimDetails";
import { DecisionCard } from "./DecisionCard";
import { ErrorNotice } from "./ErrorNotice";
import type { ActivityList, ClaimDetail } from "./types";
import type { Resource } from "./useResource";

export function ClaimWorkspace({
  selected,
  detail,
  activity,
}: {
  readonly selected: string | null;
  readonly detail: Resource<ClaimDetail>;
  readonly activity: Resource<ActivityList>;
}) {
  return (
    <div className="claim-workspace">
      {selected === null && (
        <section className="panel empty-state">
          <h2>Select a claim</h2>
          <p>The evidence, decision and agent activity will appear here.</p>
        </section>
      )}
      {detail.loading && <p role="status">Loading claim details...</p>}
      {detail.error && (
        <ErrorNotice
          message={detail.error}
          onRetry={detail.reload}
          label="Retry claim"
        />
      )}
      {detail.data && (
        <>
          <DecisionCard detail={detail.data} />
          <ClaimDetails detail={detail.data} />
          <section className="panel">
            {activity.loading && <p role="status">Loading activity...</p>}
            {activity.error && (
              <ErrorNotice
                message={activity.error}
                onRetry={activity.reload}
                label="Retry activity"
              />
            )}
            <ActivityLog events={activity.data?.events ?? []} />
          </section>
        </>
      )}
    </div>
  );
}
