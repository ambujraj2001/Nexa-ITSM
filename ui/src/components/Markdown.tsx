/**
 * Minimal, safe Markdown renderer for knowledge articles: headings, paragraphs,
 * lists, fenced code, inline code and bold. Builds React elements only — no
 * HTML strings are ever injected.
 */
import type { ReactNode } from "react";

function inline(text: string, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = pattern.exec(text))) {
    if (match.index > last) out.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("`")) out.push(<code key={`${keyPrefix}-${i++}`} className="rounded bg-surface-container-low px-1 font-label-code text-[12px] text-on-surface">{token.slice(1, -1)}</code>);
    else out.push(<strong key={`${keyPrefix}-${i++}`} className="font-semibold text-on-surface">{token.slice(2, -2)}</strong>);
    last = match.index + token.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++;
      blocks.push(
        <pre key={key++} className="overflow-x-auto rounded bg-inverse-surface p-space-md font-label-code text-[12px] leading-relaxed text-tertiary-fixed">
          <code>{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const cls = level === 1 ? "font-headline-md text-headline-md font-semibold" : level === 2 ? "font-headline-sm text-headline-sm font-semibold pt-space-sm" : "font-body-md text-body-md font-semibold";
      blocks.push(<p key={key++} className={`${cls} text-on-surface`} role="heading" aria-level={level + 1}>{inline(heading[2], `h${key}`)}</p>);
      i++;
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""));
      const List = ordered ? "ol" : "ul";
      blocks.push(
        <List key={key++} className={`${ordered ? "list-decimal" : "list-disc"} flex flex-col gap-1 pl-6 font-body-md text-body-md text-on-surface`}>
          {items.map((item, n) => <li key={n}>{inline(item, `li${key}-${n}`)}</li>)}
        </List>,
      );
      continue;
    }
    if (!line.trim()) {
      i++;
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|```|\s*([-*]|\d+\.)\s)/.test(lines[i])) para.push(lines[i++]);
    blocks.push(<p key={key++} className="font-body-md text-body-md leading-relaxed text-on-surface">{inline(para.join(" "), `p${key}`)}</p>);
  }
  return <div className="flex flex-col gap-space-sm">{blocks}</div>;
}
