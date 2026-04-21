"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { getToken } from "@/lib/api";
import { useEffect, useState } from "react";

const links = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
];

export function Navbar() {
  const path = usePathname();
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(!!getToken());
  }, [path]);

  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link href="/" className="text-lg font-semibold text-brand-700">
          AI CV Scanner
        </Link>
        <nav className="hidden gap-6 text-sm font-medium text-slate-600 md:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn("hover:text-brand-600", path === l.href && "text-brand-700")}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-3 text-sm">
          {loggedIn ? (
            <>
              <Link href="/dashboard" className="font-medium text-brand-700 hover:underline">
                Dashboard
              </Link>
            </>
          ) : (
            <>
              <Link href="/login" className="text-slate-600 hover:text-brand-700">
                Log in
              </Link>
              <Link
                href="/register"
                className="rounded-lg bg-brand-600 px-3 py-2 font-medium text-white hover:bg-brand-700"
              >
                Start free
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
