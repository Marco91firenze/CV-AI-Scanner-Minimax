import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 120;

function backendBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL;
  if (!raw?.trim()) {
    throw new Error("NEXT_PUBLIC_API_URL is not set");
  }
  return raw.replace(/\/$/, "");
}

export async function DELETE(
  req: NextRequest,
  context: { params: { jobId: string } }
) {
  const { jobId } = context.params;
  if (!jobId) {
    return NextResponse.json({ detail: "Missing job id" }, { status: 400 });
  }

  const auth = req.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${backendBase()}/jobs/${encodeURIComponent(jobId)}`, {
      method: "DELETE",
      headers: { Authorization: auth },
    });
  } catch (e) {
    console.error("[job-delete-proxy] upstream fetch failed", e);
    return NextResponse.json(
      {
        detail:
          "Could not reach the backend. Verify NEXT_PUBLIC_API_URL on Vercel and that Railway is up.",
      },
      { status: 502 }
    );
  }

  const text = await upstream.text();
  const ct = upstream.headers.get("content-type") || "application/json";
  return new NextResponse(text, { status: upstream.status, headers: { "content-type": ct } });
}
