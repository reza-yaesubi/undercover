import type { QueueStatus } from "./types";

const labels: Record<QueueStatus, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  waiting_for_sign_off: "Waiting for sign-off",
  decided: "Decided",
};

export function StatusBadge({ status }: { readonly status: QueueStatus }) {
  return (
    <span className={`status-badge status-${status}`}>{labels[status]}</span>
  );
}
