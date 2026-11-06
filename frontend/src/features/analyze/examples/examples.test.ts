import { readFileSync } from "node:fs";
import path from "node:path";
import { EXAMPLES } from "./index";

const fixtures = path.resolve(import.meta.dirname, "../../../../../backend/tests/fixtures");

test.each(EXAMPLES.map((e) => [e.id, e] as const))("%s is byte-identical to the backend fixture", (_, example) => {
  const backend = readFileSync(path.join(fixtures, example.file));
  const bundled = readFileSync(path.join(import.meta.dirname, example.file));
  expect(bundled.equals(backend)).toBe(true);
  expect(example.text).toBe(backend.toString("utf8"));
});
