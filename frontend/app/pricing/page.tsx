"use client";

import { useEffect, useState } from "react";
import { fetchPublicPricing, getToken, purchaseCredits } from "@/lib/api";

export default function PricingPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchPublicPricing>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    fetchPublicPricing()
      .then(setData)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load pricing")
      );
  }, []);

  async function buy(plan: "starter" | "professional") {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    setError(null);
    setLoading(plan);
    try {
      const { checkout_url } = await purchaseCredits(plan);
      window.location.href = checkout_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-16">
      <h1 className="text-3xl font-bold text-slate-900">Pricing</h1>
      <p className="mt-2 text-slate-600">
        {data?.description}. No subscription — buy credits when you need them.
      </p>
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      <div className="mt-10 grid gap-6 md:grid-cols-2">
        {data?.plans.map((p) => (
          <div
            key={p.id}
            className="flex flex-col rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
          >
            <h2 className="text-xl font-semibold text-slate-900">{p.name}</h2>
            <p className="mt-2 text-3xl font-bold text-brand-700">
              €{p.price_eur}
              <span className="text-base font-medium text-slate-600"> / {p.credits} credits</span>
            </p>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-slate-600">
              <li>One-time purchase via Stripe</li>
              <li>Credits used after your free {data?.free_cvs ?? 10} CVs</li>
              <li>Ranking is advisory — all CVs remain visible</li>
            </ul>
            <button
              type="button"
              disabled={!!loading}
              onClick={() => buy(p.id as "starter" | "professional")}
              className="mt-6 rounded-xl bg-brand-600 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
            >
              {loading === p.id ? "Redirecting…" : `Buy ${p.name}`}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
