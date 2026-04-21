import Link from "next/link";

export default function HomePage() {
  return (
    <div>
      <section className="border-b border-slate-200 bg-gradient-to-b from-brand-50 to-white">
        <div className="mx-auto max-w-6xl px-4 py-16 md:py-24">
          <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">
            B2B SaaS · EU-first · GDPR-aware
          </p>
          <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight text-slate-900 md:text-5xl">
            Rank CVs with AI — without automating people out.
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-slate-600">
            Upload CVs, compare them to your role brief, and get transparent scores for{" "}
            <strong>prioritization only</strong>. Every candidate stays visible to your team.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link
              href="/register"
              className="rounded-xl bg-brand-600 px-6 py-3 font-semibold text-white shadow hover:bg-brand-700"
            >
              Start with 10 free CVs
            </Link>
            <Link
              href="/pricing"
              className="rounded-xl border border-slate-300 bg-white px-6 py-3 font-semibold text-slate-800 hover:border-brand-300"
            >
              View pricing
            </Link>
          </div>
          <div className="mt-10 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900 md:inline-block">
            <strong>First 10 CVs are free forever</strong> per account — no credit card required.
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-2xl font-bold text-slate-900">Built for hiring teams</h2>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {[
            {
              title: "Tenant isolation",
              body: "MongoDB stores tenant data with strict company_id scoping on every query.",
            },
            {
              title: "Ephemeral CV storage",
              body: "Raw files are encrypted and stored in your bucket, then deleted after ranking. Metadata powers your dashboard.",
            },
            {
              title: "No automated exclusion",
              body: "Scores sort the list — they never hide applicants. Humans stay in control (GDPR Article 22 alignment).",
            },
          ].map((f) => (
            <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="font-semibold text-slate-900">{f.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="text-2xl font-bold text-slate-900">GDPR-minded by design</h2>
          <ul className="mt-6 list-disc space-y-2 pl-6 text-slate-600">
            <li>DPA acceptance is required before any CV upload.</li>
            <li>One-click deletion removes a job&apos;s CVs and blobs; account deletion erases tenant data.</li>
            <li>OpenAI API for ranking; Stripe handles payments only — no CV content to Stripe.</li>
          </ul>
          <Link href="/dpa" className="mt-6 inline-block font-semibold text-brand-700 hover:underline">
            Read the Data Processing Agreement →
          </Link>
        </div>
      </section>

      <section className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 px-4 py-16 md:flex-row md:items-center">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Simple credit pricing</h2>
            <p className="mt-2 text-slate-600">
              €50 for 100 credits · €300 for 1000 credits. Trial covers your first 10 CVs.
            </p>
          </div>
          <Link
            href="/pricing"
            className="rounded-xl bg-brand-600 px-6 py-3 font-semibold text-white hover:bg-brand-700"
          >
            See plans
          </Link>
        </div>
      </section>
    </div>
  );
}
