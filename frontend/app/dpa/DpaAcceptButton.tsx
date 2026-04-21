"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { acceptDpa } from "@/lib/api";

export function DpaAcceptButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onAccept() {
    setError(null);
    setLoading(true);
    try {
      await acceptDpa();
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record acceptance");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-10 flex flex-col items-start gap-3">
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <button
        type="button"
        disabled={loading}
        onClick={onAccept}
        className="rounded-xl bg-brand-600 px-6 py-3 font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {loading ? "Saving…" : "I Accept"}
      </button>
      <p className="text-xs text-slate-500">
        By accepting, you agree to the Data Processing Agreement on behalf of your company.
      </p>
    </div>
  );
}
