import type { AnalysisResponse } from "./api/analyze";

export function analysis(overrides: Partial<AnalysisResponse> = {}): AnalysisResponse {
  return {
    diagnosis: {
      summary: "KeyError: 'email' in get_profile",
      likely_cause: "KeyError: 'email'",
      confidence: "high",
      explanation: "get_profile raised KeyError at line 2.",
      culprit: { file: "/srv/app/services/user.py", line: 2, func: "get_profile" },
      fix: {
        steps: ["Open the file.", "Use user.get('email')."],
        code_snippet: "return user.get('email')",
        language: "python",
      },
      alternative_causes: ["The caller dropped the key."],
      follow_up_checks: ["Check the request payload."],
    },
    kind: "python_traceback",
    truncated: false,
    redaction_count: 0,
    ...overrides,
  };
}
