import { AnalyzePage } from "@/features/analyze/components/AnalyzePage";

export function App() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-6 font-sans text-slate-900 sm:px-6">
      <header className="mb-5">
        <h1 className="text-2xl font-semibold">log-whisperer</h1>
        <p className="text-slate-600">Paste a Python traceback or log. Get the cause and a fix.</p>
      </header>
      <AnalyzePage />
    </main>
  );
}
