import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { highlight } from "../highlight";

type Props = { code: string; language: string | null };

export function CodeBlock({ code, language }: Props) {
  const [highlighted, setHighlighted] = useState<{ code: string; html: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    highlight(code, language)
      .then((html) => {
        if (active && html) setHighlighted({ code, html });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [code, language]);

  async function copy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
  }

  const html = highlighted?.code === code ? highlighted.html : null;
  return (
    <div className="mt-3 rounded-md border border-slate-200 bg-slate-50">
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-1">
        <span className="font-mono text-xs text-slate-500">{language ?? "text"}</span>
        <Button variant="ghost" size="sm" onClick={copy} aria-label="Copy code">
          {copied ? (
            <Check className="size-3.5" aria-hidden />
          ) : (
            <Copy className="size-3.5" aria-hidden />
          )}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      {html ? (
        <div
          data-testid="code-highlighted"
          className="overflow-x-auto p-3 font-mono text-xs [&_pre]:!bg-transparent"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre data-testid="code-plain" className="overflow-x-auto p-3 font-mono text-xs">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
}
