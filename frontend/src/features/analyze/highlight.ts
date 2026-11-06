import type { HighlighterCore } from "shiki/core";

const THEME = "github-light";
let highlighter: Promise<HighlighterCore> | null = null;

async function loadHighlighter(): Promise<HighlighterCore> {
  const [{ createHighlighterCore }, { createJavaScriptRegexEngine }, { bundledThemes }] =
    await Promise.all([import("shiki/core"), import("shiki/engine/javascript"), import("shiki/themes")]);
  return createHighlighterCore({
    themes: [bundledThemes[THEME]()],
    langs: [],
    engine: createJavaScriptRegexEngine(),
  });
}

/** Highlighted HTML for a known grammar, or null so the caller shows plain text. */
export async function highlight(code: string, language: string | null): Promise<string | null> {
  if (!language) return null;
  const { bundledLanguages } = await import("shiki/langs");
  const id = language.toLowerCase();
  const grammar = (bundledLanguages as Record<string, (typeof bundledLanguages)[keyof typeof bundledLanguages]>)[id];
  if (!grammar) return null;
  highlighter ??= loadHighlighter();
  const core = await highlighter;
  if (!core.getLoadedLanguages().includes(id)) await core.loadLanguage(grammar());
  return core.codeToHtml(code, { lang: id, theme: THEME });
}
