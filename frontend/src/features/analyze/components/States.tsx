import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ResultsSkeleton() {
  return (
    <div className="flex flex-col gap-3" data-testid="results-skeleton" aria-busy="true">
      {[20, 12, 28, 16].map((height, index) => (
        <div
          key={index}
          className="animate-pulse rounded-lg border border-slate-200 bg-slate-100"
          style={{ height: `${height * 4}px` }}
        />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      <span className="flex items-center gap-2">
        <AlertCircle className="size-4 shrink-0" aria-hidden />
        {message}
      </span>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function EmptyResults() {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500">
      The culprit, the fix and the explanation appear here.
    </div>
  );
}
