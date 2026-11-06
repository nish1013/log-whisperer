import { getJson } from "@/api/client";
import type { components } from "@/api/schema";

export type AnalysisResponse = components["schemas"]["AnalysisResponse"];
export type Diagnosis = components["schemas"]["DiagnosisOut"];
export type Confidence = Diagnosis["confidence"];

export function analyzeLog(input: string): Promise<AnalysisResponse> {
  return getJson<AnalysisResponse>("/api/analyze", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ input }),
  });
}
