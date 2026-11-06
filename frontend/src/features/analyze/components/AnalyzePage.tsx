import { useState } from "react";
import { useAnalyze } from "../hooks/useAnalyze";
import { AnalyzeForm } from "./AnalyzeForm";
import { Results } from "./Results";
import { EmptyResults, ErrorState, ResultsSkeleton } from "./States";

export function AnalyzePage() {
  const [input, setInput] = useState("");
  const analysis = useAnalyze();

  function submit() {
    analysis.mutate(input);
  }

  function retry() {
    if (analysis.variables !== undefined) analysis.mutate(analysis.variables);
  }

  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-2">
      <AnalyzeForm value={input} pending={analysis.isPending} onChange={setInput} onSubmit={submit} />
      <div className="min-w-0" aria-live="polite">
        {analysis.isPending && <ResultsSkeleton />}
        {analysis.isError && <ErrorState message={analysis.error.message} onRetry={retry} />}
        {analysis.isSuccess && <Results result={analysis.data} />}
        {analysis.isIdle && <EmptyResults />}
      </div>
    </div>
  );
}
