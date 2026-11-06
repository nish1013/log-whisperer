import { useMutation } from "@tanstack/react-query";
import { analyzeLog } from "../api/analyze";

export function useAnalyze() {
  return useMutation({ mutationFn: analyzeLog });
}
