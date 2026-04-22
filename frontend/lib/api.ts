const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

export type TrialInfo = {
  credits: number;
  free_cvs_remaining: number;
  free_cvs_used: number;
  free_cvs_total: number;
  is_trial_active: boolean;
  cvs_processed: number;
  dpa_accepted: boolean;
};

export type MeResponse = TrialInfo & {
  id: string;
  email: string;
  company_name: string;
};

export type JobLanguage = { code: string; level: string; name: string };

export type Job = {
  id: string;
  company_id: string;
  title: string;
  requirements: string;
  created_at: string;
  location?: string;
  remote_only?: boolean;
  years_experience?: string;
  mandatory_languages?: JobLanguage[];
  bonus_languages?: JobLanguage[];
  skills?: string;
};

export type CreateJobBody = {
  title: string;
  requirements: string;
  location?: string;
  remote_only?: boolean;
  years_experience?: string;
  mandatory_languages?: JobLanguage[];
  bonus_languages?: JobLanguage[];
  skills?: string;
};

export type CVRow = {
  id: string;
  filename: string;
  status: string;
  score: number | null;
  reasoning: string | null;
  error_message: string | null;
  created_at: string;
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ai_cv_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("ai_cv_token", token);
  else localStorage.removeItem("ai_cv_token");
}

const missingApiMsg =
  "Backend URL is not configured. Set NEXT_PUBLIC_API_URL on Vercel (Production) and redeploy.";

async function request<T>(
  path: string,
  init: RequestInit = {},
  auth = true
): Promise<T> {
  if (!API) {
    throw new Error(missingApiMsg);
  }
  const headers: HeadersInit = {
    ...(init.headers || {}),
  };
  if (auth) {
    const t = getToken();
    if (t) (headers as Record<string, string>)["Authorization"] = `Bearer ${t}`;
  }
  const res = await fetch(`${API}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function register(body: {
  email: string;
  password: string;
  company_name: string;
}) {
  return request<{ access_token: string } & TrialInfo>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }, false);
}

export async function loginJson(email: string, password: string) {
  return request<{ access_token: string } & TrialInfo>("/auth/login/json", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  }, false);
}

export async function fetchMe(): Promise<MeResponse> {
  return request<MeResponse>("/auth/me");
}

export async function acceptDpa() {
  return request<{ ok: boolean } & TrialInfo>("/dpa/accept", { method: "POST" });
}

export async function fetchBalance(): Promise<TrialInfo> {
  return request<TrialInfo>("/credits/balance");
}

export async function fetchJobs(): Promise<Job[]> {
  return request<Job[]>("/jobs");
}

export async function createJob(body: CreateJobBody) {
  return request<Job>("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: body.title,
      requirements: body.requirements,
      location: body.location ?? "",
      remote_only: body.remote_only ?? false,
      years_experience: body.years_experience ?? "",
      mandatory_languages: body.mandatory_languages ?? [],
      bonus_languages: body.bonus_languages ?? [],
      skills: body.skills ?? "",
    }),
  });
}

export async function deleteJob(jobId: string) {
  const t = getToken();
  if (!t) {
    throw new Error("Not signed in");
  }
  const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as {
    ok: boolean;
    credits_refunded: number;
    trial_slots_restored: number;
  };
}

export async function fetchCvs(jobId: string) {
  return request<{ note: string; cvs: CVRow[] }>(`/jobs/${jobId}/cvs`);
}

export async function uploadCv(
  jobId: string,
  file: File,
  onProgress?: (p: number) => void
): Promise<{ id: string; status: string; filename: string }> {
  const t = getToken();
  if (!t) {
    throw new Error("Not signed in");
  }
  const fd = new FormData();
  fd.append("file", file);
  onProgress?.(0);
  const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/cvs`, {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
    body: fd,
  });
  onProgress?.(100);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as { id: string; status: string; filename: string };
}

export async function purchaseCredits(plan: "starter" | "professional") {
  return request<{ checkout_url: string; session_id: string }>("/credits/purchase", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan }),
  });
}

export async function deleteAccount() {
  return request<{ ok: boolean }>("/account", { method: "DELETE" });
}

export async function fetchPublicPricing() {
  return request<{
    free_cvs: number;
    description: string;
    plans: { id: string; name: string; price_eur: number; credits: number }[];
  }>("/pricing", {}, false);
}
