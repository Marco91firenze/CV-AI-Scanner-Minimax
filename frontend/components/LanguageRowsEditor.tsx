"use client";

import type { JobLanguage } from "@/lib/api";
import { CEFR_LEVELS, LANGUAGES } from "@/lib/languages";

type Props = {
  label: string;
  rows: JobLanguage[];
  onChange: (rows: JobLanguage[]) => void;
};

export function LanguageRowsEditor({ label, rows, onChange }: Props) {
  function update(i: number, patch: Partial<JobLanguage>) {
    onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function add() {
    const first = LANGUAGES[0]!;
    onChange([...rows, { code: first.code, level: "B2", name: first.name }]);
  }
  function remove(i: number) {
    onChange(rows.filter((_, j) => j !== i));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-slate-700">{label}</span>
        <button
          type="button"
          onClick={add}
          className="shrink-0 text-xs font-semibold text-brand-700 hover:underline"
        >
          + Add language
        </button>
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-500">None — use &quot;Add language&quot; if this role has requirements.</p>
      ) : null}
      {rows.map((row, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/80 px-2 py-2">
          <select
            value={row.code}
            onChange={(e) => {
              const code = e.target.value;
              const name = LANGUAGES.find((l) => l.code === code)?.name ?? code;
              update(i, { code, name });
            }}
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
            aria-label={`${label} language ${i + 1}`}
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name} ({l.code})
              </option>
            ))}
          </select>
          <select
            value={row.level}
            onChange={(e) => update(i, { level: e.target.value })}
            className="w-24 shrink-0 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm"
            aria-label={`${label} level ${i + 1}`}
          >
            {CEFR_LEVELS.map((lv) => (
              <option key={lv} value={lv}>
                {lv}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => remove(i)}
            className="shrink-0 text-xs font-medium text-red-600 hover:underline"
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  );
}
