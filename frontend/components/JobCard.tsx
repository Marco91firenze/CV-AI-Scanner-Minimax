import type { Job } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  job: Job;
  selected: boolean;
  onSelect: (id: string) => void;
};

export function JobCard({ job, selected, onSelect }: Props) {
  return (
    <button
      type="button"
      onClick={() => onSelect(job.id)}
      className={cn(
        "w-full rounded-lg border px-3 py-2 text-left text-sm transition",
        selected
          ? "border-brand-600 bg-brand-50 font-semibold text-brand-900"
          : "border-slate-200 bg-white text-slate-800 hover:border-brand-200"
      )}
    >
      <div className="line-clamp-2">{job.title}</div>
      {job.remote_only || job.location ? (
        <div className="mt-0.5 line-clamp-1 text-xs text-slate-500">
          {job.remote_only ? "Fully remote" : job.location}
          {job.remote_only && job.location ? ` · ${job.location}` : ""}
        </div>
      ) : null}
      <div className="mt-1 text-xs text-slate-500">
        {new Date(job.created_at).toLocaleDateString()}
      </div>
    </button>
  );
}
