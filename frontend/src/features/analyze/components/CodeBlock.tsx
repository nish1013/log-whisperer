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
    <div className="relative mt-3 rounded-md border border-slate-200 bg-slate-50">
      <Button
        variant="outline"
        size="sm"
        className="absolute top-1.5 right-1.5 h-7"
        onClick={copy}
        aria-label="Copy code"
      >
        {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
        {copied ? "Copied" : "Copy"}
      </Button>
      {html ? (
        <div
          data-testid="code-highlighted"
          className="overflow-x-auto p-3 pr-20 font-mono text-xs [&_pre]:!bg-transparent"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre data-testid="code-plain" className="overflow-x-auto p-3 pr-20 font-mono text-xs">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
}
