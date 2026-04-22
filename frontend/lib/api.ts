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

export type Job = {
  id: string;
  company_id: string;
  title: string;
  requirements: string;
  created_at: string;
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

async function request<T>(
  path: string,
  init: RequestInit = {},
  auth = true
): Promise<T> {
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

export async function createJob(title: string, requirements: string) {
  return request<Job>("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, requirements }),
  });
}

export async function deleteJob(jobId: string) {
  return request<{ ok: boolean; credits_refunded: number; trial_slots_restored: number }>(
    `/jobs/${jobId}`,
    { method: "DELETE" }
  );
}

export async function fetchCvs(jobId: string) {
  return request<{ note: string; cvs: CVRow[] }>(`/jobs/${jobId}/cvs`);
}

export async function uploadCv(jobId: string, file: File, onProgress?: (p: number) => void) {
  const t = getToken();
  const fd = new FormData();
  fd.append("file", file);
  return new Promise<{ id: string; status: string; filename: string }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}/jobs/${jobId}/cvs`);
    if (t) xhr.setRequestHeader("Authorization", `Bearer ${t}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        let detail = xhr.statusText;
        try {
          const j = JSON.parse(xhr.responseText);
          if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
        } catch {
          /* ignore */
        }
        reject(new Error(detail));
      }
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(fd);
  });
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
  if (!API) {
    throw new Error(
      "Backend URL is not configured (set NEXT_PUBLIC_API_URL on Vercel for Production, then redeploy)."
    );
  }
  return request<{
    free_cvs: number;
    description: string;
    plans: { id: string; name: string; price_eur: number; credits: number }[];
  }>("/pricing", {}, false);
}
