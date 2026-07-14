// Central place for the backend URL.
// During local dev this is http://localhost:8000.
// In Docker it is overridden at build time via NEXT_PUBLIC_API_URL.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
