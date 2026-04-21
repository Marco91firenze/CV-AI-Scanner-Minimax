import { cn } from "@/lib/utils";
import type { TrialInfo } from "@/lib/api";

type Props = { trial: TrialInfo; className?: string };

export function CreditBadge({ trial, className }: Props) {
  const creditLine = `${trial.credits} credits`;
  const trialLine = trial.is_trial_active
    ? `${trial.free_cvs_remaining} free CVs remaining (trial active)`
    : "0 free CVs remaining. Purchase credits to continue.";

  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3 text-sm md:flex-row md:items-center md:justify-between",
        className
      )}
    >
      <div className="font-semibold text-brand-900">{creditLine}</div>
      <div
        className={cn(
          "font-medium",
          trial.is_trial_active ? "text-emerald-800" : "text-amber-800"
        )}
      >
        {trialLine}
      </div>
    </div>
  );
}
