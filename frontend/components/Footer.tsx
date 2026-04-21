import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 text-sm text-slate-600 md:flex-row md:items-center md:justify-between">
        <p className="font-medium text-slate-800">AI CV Scanner — B2B CV ranking for growing teams.</p>
        <div className="flex flex-wrap gap-4">
          <Link href="/privacy" className="hover:text-brand-700">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-brand-700">
            Terms
          </Link>
          <Link href="/dpa" className="hover:text-brand-700">
            DPA
          </Link>
          <Link href="/pricing" className="hover:text-brand-700">
            Pricing
          </Link>
        </div>
      </div>
    </footer>
  );
}
