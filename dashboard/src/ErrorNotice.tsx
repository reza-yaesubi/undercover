export function ErrorNotice({
  message,
  onRetry,
  label,
}: {
  readonly message: string;
  readonly onRetry: () => void;
  readonly label: string;
}) {
  return (
    <div className="error-notice" role="alert">
      <p>{message}</p>
      <button className="button secondary" onClick={onRetry}>
        {label}
      </button>
    </div>
  );
}
