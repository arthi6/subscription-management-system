const BASE = "/api/v1";
export const CUR = "$"; // the data model has no currency field; change this symbol if needed
export const tok = {
  get: () => localStorage.getItem("token"),
  set: (v) => (v ? localStorage.setItem("token", v) : localStorage.removeItem("token")),
};
export async function api(path, { method = "GET", body, raw } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (tok.get()) headers.Authorization = "Bearer " + tok.get();
  const r = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (raw && r.ok) return r;
  const d = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && tok.get()) { tok.set(null); location.href = "/"; }
    const msg = Array.isArray(d.detail) ? d.detail.map((x) => x.msg).join("; ") : d.detail;
    throw new Error(msg || `Request failed (${r.status})`);
  }
  return d;
}
export const money = (n) => CUR + Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const day = (d) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—");
