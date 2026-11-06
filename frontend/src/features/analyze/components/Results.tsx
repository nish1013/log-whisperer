import { ChevronDown, ShieldCheck, Scissors } from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { AnalysisResponse, Confidence } from "../api/analyze";
import { CodeBlock } from "./CodeBlock";

const TONE: Record<Confidence, "green" | "amber" | "grey"> = {
  high: "green",
  medium: "amber",
  low: "grey",
};

export function Results({ result }: { result: AnalysisResponse }) {
  const { diagnosis } = result;
  const culprit = diagnosis.culprit;
  return (
    <div className="flex min-w-0 flex-col gap-3" data-testid="results">
      <Notices redactions={result.redaction_count} truncated={result.truncated} />
      <Card aria-label="Summary">
        <CardHeader>
          <CardTitle>Summary</CardTitle>
          <Badge tone={TONE[diagnosis.confidence]}>{diagnosis.confidence} confidence</Badge>
        </CardHeader>
        <CardContent>
          <p className="font-medium text-slate-900">{diagnosis.summary}</p>
          <p className="mt-1">{diagnosis.likely_cause}</p>
        </CardContent>
      </Card>
      <Card aria-label="Culprit">
        <CardHeader>
          <CardTitle>Culprit</CardTitle>
        </CardHeader>
        <CardContent>
          {culprit ? (
            <code className="block overflow-x-auto font-mono text-xs whitespace-pre text-slate-900">
              {culprit.file}:{culprit.line} in {culprit.func}
            </code>
          ) : (
            <p>No specific line identified</p>
          )}
        </CardContent>
      </Card>
      <Card aria-label="Fix">
        <CardHeader>
          <CardTitle>Fix</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="list-decimal space-y-1 pl-5">
            {diagnosis.fix.steps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
          {diagnosis.fix.code_snippet && (
            <CodeBlock code={diagnosis.fix.code_snippet} language={diagnosis.fix.language} />
          )}
        </CardContent>
      </Card>
      <Card aria-label="Explanation">
        <CardHeader>
          <CardTitle>Explanation</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-line">{diagnosis.explanation}</p>
        </CardContent>
      </Card>
      <ListSection title="Other possible causes" items={diagnosis.alternative_causes} />
      <ListSection title="What to check next" items={diagnosis.follow_up_checks} />
    </div>
  );
}

function Notices({ redactions, truncated }: { redactions: number; truncated: boolean }) {
  if (redactions === 0 && !truncated) return null;
  return (
    <div className="flex flex-col gap-1" role="status">
      {redactions > 0 && (
        <Notice icon={<ShieldCheck className="size-4" aria-hidden />}>
          Masked {redactions} {redactions === 1 ? "secret" : "secrets"} before analysis
        </Notice>
      )}
      {truncated && (
        <Notice icon={<Scissors className="size-4" aria-hidden />}>
          Log was truncated to the relevant parts
        </Notice>
      )}
    </div>
  );
}

function Notice({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 rounded-md bg-sky-50 px-3 py-1.5 text-xs text-sky-900">
      {icon}
      {children}
    </p>
  );
}

function ListSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <Card>
      <Collapsible>
        <CollapsibleTrigger className="group flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-slate-900">
          {title}
          <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" aria-hidden />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <ul className="list-disc space-y-1 px-4 pb-3 pl-9 text-sm text-slate-700">
            {items.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
