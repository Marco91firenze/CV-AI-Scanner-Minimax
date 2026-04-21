import type { CVRow } from "@/lib/api";
import { cn } from "@/lib/utils";

const statusStyles: Record<string, string> = {
  ranked: "bg-emerald-100 text-emerald-800",
  ranking: "bg-amber-100 text-amber-800",
  uploaded: "bg-slate-100 text-slate-700",
  error: "bg-red-100 text-red-800",
};

export function CVCard({ cv }: { cv: CVRow }) {
  const st = statusStyles[cv.status] || "bg-slate-100 text-slate-700";
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="font-medium text-slate-900">{cv.filename}</h3>
        <div className="flex items-center gap-2">
          {cv.score != null ? (
            <span className="rounded-full bg-brand-600 px-2 py-0.5 text-xs font-bold text-white">
              {cv.score}/10
            </span>
          ) : null}
          <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", st)}>
            {cv.status}
          </span>
        </div>
      </div>
      {cv.reasoning ? (
        <p className="mt-2 text-sm text-slate-600">{cv.reasoning}</p>
      ) : cv.error_message ? (
        <p className="mt-2 text-sm text-red-700">{cv.error_message}</p>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Processing…</p>
      )}
    </article>
  );
}
