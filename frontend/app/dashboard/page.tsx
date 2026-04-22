"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createJob,
  deleteAccount,
  deleteJob,
  fetchBalance,
  fetchCvs,
  fetchJobs,
  fetchMe,
  getToken,
  setToken,
  uploadCv,
  type CVRow,
  type Job,
  type JobLanguage,
  type TrialInfo,
} from "@/lib/api";
import { CreditBadge } from "@/components/CreditBadge";
import { CVTable } from "@/components/CVTable";
import { JobCard } from "@/components/JobCard";
import { LanguageRowsEditor } from "@/components/LanguageRowsEditor";
import { Modal } from "@/components/Modal";

export default function DashboardPage() {
  const router = useRouter();
  const [trial, setTrial] = useState<TrialInfo | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [cvs, setCvs] = useState<CVRow[]>([]);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newReq, setNewReq] = useState("");
  const [newLocation, setNewLocation] = useState("");
  const [newRemoteOnly, setNewRemoteOnly] = useState(false);
  const [newYearsExp, setNewYearsExp] = useState("");
  const [newSkills, setNewSkills] = useState("");
  const [mandatoryLangs, setMandatoryLangs] = useState<JobLanguage[]>([]);
  const [bonusLangs, setBonusLangs] = useState<JobLanguage[]>([]);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [delJobOpen, setDelJobOpen] = useState(false);
  const [delJobBusy, setDelJobBusy] = useState(false);
  const [delAccountOpen, setDelAccountOpen] = useState(false);

  const refreshTrial = useCallback(async () => {
    const b = await fetchBalance();
    setTrial(b);
  }, []);

  const loadJobs = useCallback(async () => {
    const j = await fetchJobs();
    setJobs(j);
    setSelectedJob((prev) => prev ?? (j[0]?.id ?? null));
  }, []);

  const loadCvs = useCallback(async () => {
    if (!selectedJob) {
      setCvs([]);
      return;
    }
    const r = await fetchCvs(selectedJob);
    setNote(r.note);
    setCvs(r.cvs);
  }, [selectedJob]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    (async () => {
      try {
        const me = await fetchMe();
        if (!me.dpa_accepted) {
          router.replace("/dpa");
          return;
        }
        setTrial({
          credits: me.credits,
          free_cvs_remaining: me.free_cvs_remaining,
          free_cvs_used: me.free_cvs_used,
          free_cvs_total: me.free_cvs_total,
          is_trial_active: me.is_trial_active,
          cvs_processed: me.cvs_processed,
          dpa_accepted: me.dpa_accepted,
        });
        await loadJobs();
      } catch {
        setToken(null);
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    })();
  }, [router, loadJobs]);

  useEffect(() => {
    if (!selectedJob || loading) return;
    let cancelled = false;
    const tick = async () => {
      try {
        await loadCvs();
        await refreshTrial();
      } catch {
        /* ignore poll errors */
      }
    };
    tick();
    const id = setInterval(() => {
      if (!cancelled) tick();
    }, 4000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [selectedJob, loading, loadCvs, refreshTrial]);

  const selected = useMemo(() => jobs.find((j) => j.id === selectedJob), [jobs, selectedJob]);

  async function onCreateJob(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const j = await createJob({
        title: newTitle,
        requirements: newReq,
        location: newLocation,
        remote_only: newRemoteOnly,
        years_experience: newYearsExp,
        skills: newSkills,
        mandatory_languages: mandatoryLangs,
        bonus_languages: bonusLangs,
      });
      setNewTitle("");
      setNewReq("");
      setNewLocation("");
      setNewRemoteOnly(false);
      setNewYearsExp("");
      setNewSkills("");
      setMandatoryLangs([]);
      setBonusLangs([]);
      setJobs((prev) => [j, ...prev]);
      setSelectedJob(j.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create job");
    }
  }

  async function onUpload(files: File[]) {
    if (files.length === 0) return;
    const jobId = selectedJob;
    if (!jobId) {
      setError("Select a job in the list before uploading CVs.");
      return;
    }
    if (!jobs.some((j) => j.id === jobId)) {
      setError("The selected job is no longer available. Refresh or pick another job.");
      return;
    }
    setError(null);
    setUploadPct(0);
    const n = files.length;
    try {
      for (let i = 0; i < n; i++) {
        const file = files[i]!;
        await uploadCv(jobId, file, (p) => {
          const base = (i / n) * 100;
          const slice = (100 / n) * (p / 100);
          setUploadPct(Math.round(base + slice));
        });
      }
      await loadCvs();
      await refreshTrial();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setError(
        msg === "Failed to fetch"
          ? "Upload could not reach the backend (network, wrong NEXT_PUBLIC_API_URL, or API CORS). Large files use direct storage upload; if the bar moves then stops, fix S3/R2 CORS for PUT from your site."
          : msg
      );
    } finally {
      setUploadPct(null);
    }
  }

  async function confirmDeleteJob() {
    if (!selectedJob || delJobBusy) return;
    setDelJobBusy(true);
    setError(null);
    try {
      await deleteJob(selectedJob);
      setDelJobOpen(false);
      setSelectedJob(null);
      await loadJobs();
      await refreshTrial();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDelJobBusy(false);
    }
  }

  async function confirmDeleteAccount() {
    setError(null);
    try {
      await deleteAccount();
      setToken(null);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Account deletion failed");
    }
  }

  if (loading || !trial) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-24 text-center text-slate-600">Loading workspace…</div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-600">
            All CVs are shown. Scores sort the list only — no candidate is hidden by automation.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setDelAccountOpen(true)}
          className="text-sm font-semibold text-red-700 hover:underline"
        >
          Delete account
        </button>
      </div>

      <div className="mt-6">
        <CreditBadge trial={trial} />
      </div>

      {note ? (
        <p className="mt-4 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
          {note}
        </p>
      ) : null}

      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      <div className="mt-8 grid gap-8 lg:grid-cols-[280px,1fr]">
        <aside className="space-y-6">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Jobs</h2>
            <div className="mt-3 flex max-h-[360px] flex-col gap-2 overflow-y-auto pr-1">
              {jobs.map((j) => (
                <JobCard key={j.id} job={j} selected={j.id === selectedJob} onSelect={setSelectedJob} />
              ))}
              {jobs.length === 0 ? (
                <p className="text-sm text-slate-500">Create your first job to upload CVs.</p>
              ) : null}
            </div>
          </div>
          <form onSubmit={onCreateJob} className="max-h-[min(70vh,520px)] space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900">New job</h3>
            <input
              placeholder="Job title"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <textarea
              placeholder="Role brief (main description)"
              value={newReq}
              onChange={(e) => setNewReq(e.target.value)}
              required
              rows={4}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <div>
              <label className="block text-xs font-medium text-slate-600">Location</label>
              <input
                placeholder="e.g. Berlin, hybrid, EU"
                value={newLocation}
                onChange={(e) => setNewLocation(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={newRemoteOnly}
                  onChange={(e) => setNewRemoteOnly(e.target.checked)}
                  className="rounded border-slate-300"
                />
                Fully remote
              </label>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600">Years of experience</label>
              <textarea
                placeholder="e.g. 3–5 years in B2B sales"
                value={newYearsExp}
                onChange={(e) => setNewYearsExp(e.target.value)}
                rows={2}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <LanguageRowsEditor label="Mandatory languages" rows={mandatoryLangs} onChange={setMandatoryLangs} />
            <LanguageRowsEditor label="Languages that are a plus" rows={bonusLangs} onChange={setBonusLangs} />
            <div>
              <label className="block text-xs font-medium text-slate-600">Skills</label>
              <textarea
                placeholder="Key skills, tools, certifications…"
                value={newSkills}
                onChange={(e) => setNewSkills(e.target.value)}
                rows={3}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-lg bg-brand-600 py-2 text-sm font-semibold text-white hover:bg-brand-700"
            >
              Add job
            </button>
          </form>
        </aside>

        <section className="space-y-4">
          {selected ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">{selected.title}</h2>
                  <p className="text-xs text-slate-500">
                    {cvs.length} CV{cvs.length === 1 ? "" : "s"} for this role
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="inline-flex cursor-pointer items-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
                    Upload CVs
                    <input
                      type="file"
                      accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      multiple
                      className="hidden"
                      onChange={(e) => {
                        const list = e.target.files;
                        const fs = list ? Array.from(list) : [];
                        e.target.value = "";
                        if (fs.length) void onUpload(fs);
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => setDelJobOpen(true)}
                    className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-100"
                  >
                    Delete job
                  </button>
                </div>
              </div>
              {uploadPct != null ? (
                <div className="text-sm text-slate-600">Uploading CVs… {uploadPct}%</div>
              ) : null}
              <CVTable cvs={cvs} />
            </>
          ) : (
            <p className="text-sm text-slate-600">Select or create a job to manage CVs.</p>
          )}
        </section>
      </div>

      <Modal
        open={delJobOpen}
        title="Delete this job?"
        onClose={() => (delJobBusy ? undefined : setDelJobOpen(false))}
        footer={
          <>
            <button
              type="button"
              disabled={delJobBusy}
              className="rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
              onClick={() => setDelJobOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={delJobBusy}
              className="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
              onClick={() => void confirmDeleteJob()}
            >
              {delJobBusy ? "Deleting…" : "Delete permanently"}
            </button>
          </>
        }
      >
        This will permanently delete all {cvs.length} CV{cvs.length === 1 ? "" : "s"} for this job,
        including any stored files and metadata. This cannot be undone.
      </Modal>

      <Modal
        open={delAccountOpen}
        title="Delete your company account?"
        onClose={() => setDelAccountOpen(false)}
        footer={
          <>
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
              onClick={() => setDelAccountOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700"
              onClick={confirmDeleteAccount}
            >
              Delete account
            </button>
          </>
        }
      >
        Complete account deletion removes jobs, CV records, and encrypted files associated with your tenant.
      </Modal>
    </div>
  );
}
