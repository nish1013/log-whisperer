import f01 from "./F01_py3.12.txt?raw";
import f04 from "./F04_py3.12.txt?raw";
import f10 from "./F10_jsonlines.txt?raw";

export type Example = { id: string; label: string; file: string; text: string };

export const EXAMPLES: readonly Example[] = [
  { id: "F01", label: "KeyError in a service", file: "F01_py3.12.txt", text: f01 },
  { id: "F04", label: "Upstream connection refused", file: "F04_py3.12.txt", text: f04 },
  { id: "F10", label: "JSON log, no traceback", file: "F10_jsonlines.txt", text: f10 },
];
