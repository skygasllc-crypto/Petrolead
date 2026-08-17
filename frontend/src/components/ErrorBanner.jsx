export default function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="flex items-start justify-between gap-4 rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger">
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 font-medium underline decoration-status-danger/50 underline-offset-2 hover:decoration-status-danger"
        >
          Retry
        </button>
      )}
    </div>
  );
}
