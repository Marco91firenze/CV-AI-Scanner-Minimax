import type { CVRow } from "@/lib/api";
import { cn } from "@/lib/utils";

export function CVTable({ cvs }: { cvs: CVRow[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-4 py-3">File</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Reasoning</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {cvs.map((cv) => (
            <tr key={cv.id} className="hover:bg-slate-50/80">
              <td className="px-4 py-3 font-medium text-slate-900">{cv.filename}</td>
              <td className="px-4 py-3">
                {cv.score != null ? (
                  <span className="rounded-full bg-brand-600 px-2 py-0.5 text-xs font-bold text-white">
                    {cv.score}
                  </span>
                ) : (
                  <span className="text-slate-400">—</span>
                )}
              </td>
              <td className={cn("px-4 py-3 capitalize")}>{cv.status}</td>
              <td className="max-w-md px-4 py-3 text-slate-600">
                {cv.reasoning || cv.error_message || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
