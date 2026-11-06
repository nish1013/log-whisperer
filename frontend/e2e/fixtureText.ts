import { readFileSync } from "node:fs";
import path from "node:path";

const FIXTURES = path.resolve(import.meta.dirname, "../../backend/tests/fixtures");
const PLACEHOLDER = /\{\{secret:(\d+)\}\}/g;

type Expected = { F11: { secret_parts: string[][] } };

function expected(): Expected {
  return JSON.parse(readFileSync(path.join(FIXTURES, "expected.json"), "utf8")) as Expected;
}

export function secrets(): string[] {
  return expected().F11.secret_parts.map((parts) => parts.join(""));
}

export function fixtureText(name: string): string {
  const values = secrets();
  const text = readFileSync(path.join(FIXTURES, `${name}.txt`), "utf8");
  return text.replace(PLACEHOLDER, (_, index: string) => values[Number(index)] ?? "");
}
