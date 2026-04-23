import { NextRequest, NextResponse } from "next/server";

/** Large PDFs + slow networks */
export const maxDuration = 120;
/** Multipart + forwarding FormData to Railway is unreliable on Edge */
export const runtime = "nodejs";

function backendBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL;
  if (!raw?.trim()) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  return raw.replace(/\/$/, "");
}

export async function POST(req: NextRequest, context: { params: { jobId: string } }) {
  const { jobId } = context.params;
  if (!jobId) {
    return NextResponse.json({ detail: "Missing job id" }, { status: 400 });
  }

  const auth = req.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json({ detail: "Invalid multipart body" }, { status: 400 });
  }

  const file = formData.get("file");
  // Node/Edge may expose uploads as Blob; `instanceof File` can fail even for valid parts.
  if (!(file instanceof Blob) || file.size === 0) {
    return NextResponse.json({ detail: "Missing or empty file" }, { status: 400 });
  }

  const fname = file instanceof File ? file.name : "cv.pdf";
  const out = new FormData();
  out.append("file", file, fname);

  let upstream: Response;
  try {
    upstream = await fetch(`${backendBase()}/jobs/${encodeURIComponent(jobId)}/cvs`, {
      method: "POST",
      headers: { Authorization: auth },
      body: out,
    });
  } catch (e) {
    console.error("[cv-upload-proxy] upstream fetch failed", e);
    return NextResponse.json(
      {
        detail:
          "Upload proxy could not reach the backend. Verify NEXT_PUBLIC_API_URL on Vercel and that Railway is up.",
      },
      { status: 502 }
    );
  }

  const text = await upstream.text();
  if (!upstream.ok) {
    console.error(
      "[cv-upload-proxy] upstream",
      upstream.status,
      text.slice(0, 500)
    );
  }
  const ct = upstream.headers.get("content-type") || "application/json";
  return new NextResponse(text, { status: upstream.status, headers: { "content-type": ct } });
}
