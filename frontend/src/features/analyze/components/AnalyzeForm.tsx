import { Loader2 } from "lucide-react";
import type { KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { EXAMPLES } from "../examples";
import { formatKb, MAX_INPUT_BYTES, utf8Bytes } from "../limits";

const PLACEHOLDER = `Traceback (most recent call last):
  File "app/main.py", line 3, in <module>
KeyError: 'email'`;

type Props = {
  value: string;
  pending: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function AnalyzeForm({ value, pending, onChange, onSubmit }: Props) {
  const bytes = utf8Bytes(value);
  const over = bytes > MAX_INPUT_BYTES;
  const disabled = pending || over || !value.trim();

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      if (!disabled) onSubmit();
    }
  }

  function pickExample(id: string) {
    const example = EXAMPLES.find((e) => e.id === id);
    if (example) onChange(example.text);
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor="log-input" className="text-sm font-medium text-slate-800">
          Traceback or log
        </label>
        <Select value="" onValueChange={pickExample}>
          <SelectTrigger aria-label="Load an example" className="w-52">
            <SelectValue placeholder="Load an example" />
          </SelectTrigger>
          <SelectContent>
            {EXAMPLES.map((example) => (
              <SelectItem key={example.id} value={example.id}>
                {example.id}: {example.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Textarea
        id="log-input"
        rows={14}
        wrap="off"
        spellCheck={false}
        placeholder={PLACEHOLDER}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        className="min-h-[18rem] resize-y overflow-auto font-mono text-xs whitespace-pre"
      />
      <div className="flex items-center justify-between gap-2">
        <span
          data-testid="byte-counter"
          data-over={over}
          className={cn("text-xs tabular-nums", over ? "font-semibold text-red-600" : "text-slate-500")}
        >
          {formatKb(bytes)} / 200 KB
        </span>
        <Button onClick={onSubmit} disabled={disabled}>
          {pending && <Loader2 className="size-4 animate-spin" aria-hidden data-testid="spinner" />}
          Analyze
        </Button>
      </div>
      <p className="text-xs text-slate-500">Ctrl or Cmd + Enter to analyze.</p>
    </div>
  );
}
