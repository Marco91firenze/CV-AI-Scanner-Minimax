/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

if (process.env.VERCEL === "1" && !process.env.NEXT_PUBLIC_API_URL?.trim()) {
  throw new Error(
    "NEXT_PUBLIC_API_URL must be set for Vercel builds (Railway backend URL, no trailing slash)."
  );
}

module.exports = nextConfig;
