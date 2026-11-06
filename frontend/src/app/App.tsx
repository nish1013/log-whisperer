import { useQuery } from "@tanstack/react-query";
import { getJson, type HealthResponse } from "@/api/client";

export function App() {
  const health = useQuery({
    queryKey: ["healthz"],
    queryFn: () => getJson<HealthResponse>("/healthz"),
  });
  const status = health.isPending ? "checking" : health.isError ? "unreachable" : health.data.status;
  return (
    <main className="mx-auto max-w-3xl p-6 font-sans">
      <h1 className="text-2xl font-semibold">log-whisperer</h1>
      <p className="text-slate-600">Paste a Python traceback or log. Get the cause and a fix.</p>
      <p className="mt-4" data-testid="backend-status">
        Backend: {status}
      </p>
    </main>
  );
}
