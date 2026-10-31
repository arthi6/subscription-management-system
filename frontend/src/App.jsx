import { useEffect, useState, useCallback } from "react";
import { api, tok, money, day } from "./api.js";
import Logo from "./Logo.jsx";
import Home from "./Home.jsx";

const Badge = ({ s }) => <span className={"badge " + s}>{s}</span>;
const Err = ({ e }) => (e ? <div className="err" role="alert">{e}</div> : null);
const Ok = ({ m }) => (m ? <div className="ok">{m}</div> : null);
const hit = (o, q) => !q || JSON.stringify(o).toLowerCase().includes(q.toLowerCase());

function useLoad(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(() => { setError(""); api(path).then(setData).catch((e) => setError(e.message)); }, [path]);
  useEffect(load, [load]);
  return { data, error, reload: load };
}
const Modal = ({ title, onClose, children }) => (
  <div className="overlay" onClick={onClose}>
    <div className="card modal" role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
      <div className="head"><h3>{title}</h3><button className="btn" onClick={onClose}>Close</button></div>{children}
    </div>
  </div>
);

/* ---------------- Login / sign up / password reset ---------------- */
function Login({ onDone, initialMode = "login", onBack }) {
  const resetToken = location.pathname === "/reset-password" ? new URLSearchParams(location.search).get("token") || "" : "";
  const [mode, setMode] = useState(resetToken ? "reset" : initialMode);
  const [role, setRole] = useState("admin");
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ email: "", password: "", full_name: "", token: resetToken });
  const [error, setError] = useState(""); const [info, setInfo] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault(); setError(""); setInfo("");
    try {
      if (mode === "signup") { await api("/auth/signup", { method: "POST", body: { email: f.email, full_name: f.full_name, password: f.password } }); setInfo("Account created. Please sign in."); setMode("login"); setRole("customer"); }
      else if (mode === "forgot") { const r = await api("/auth/forgot-password", { method: "POST", body: { email: f.email } }); setInfo(r.message); }
      else if (mode === "reset") { await api("/auth/reset-password", { method: "POST", body: { token: f.token, new_password: f.password } }); history.replaceState({}, "", "/"); setInfo("Password updated. Please sign in."); setMode("login"); }
      else {
        const d = await api("/auth/login", { method: "POST", body: { email: f.email, password: f.password } });
        tok.set(d.access_token);
        const me = await api("/auth/me");
        if (me.role !== role) { tok.set(null); throw new Error(`This is a ${me.role} account. Choose the ${me.role} tab.`); }
        onDone(me);
      }
    } catch (x) { setError(x.message); }
  }
  const titles = { login: "Sign in to your account", signup: "Create your account", forgot: "Reset your password", reset: "Choose a new password" };
  return (
    <div className="split">
      <div className="art" aria-hidden="true">
        <svg viewBox="0 0 400 400"><defs><linearGradient id="a1" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor="#f3e3c3" /><stop offset=".5" stopColor="#c9a06a" /><stop offset="1" stopColor="#8a6a4a" /></linearGradient></defs>
          {[0, 1, 2, 3, 4].map((i) => <path key={i} d={`M200 200c-${60 + i * 22} -${90 + i * 10} -${150 + i * 12} -${30 + i * 8} -${110 + i * 10} 40s${90 + i * 8} 60 ${110 + i * 10} 0 ${60 + i * 12} -150 ${110 + i * 10} -80 -50 70 -${110 + i * 10} 40z`} fill="none" stroke="url(#a1)" strokeWidth={14 - i * 2} opacity={0.35 + i * 0.13} strokeLinecap="round" />)}
          <circle cx="260" cy="120" r="14" fill="#fff4d6" /><circle cx="130" cy="290" r="9" fill="#e7c89a" /></svg>
      </div>
      <div className="pane">
        <form className="card login" onSubmit={submit}>
          <div className="center"><Logo size={34} /><b className="wordmark">Brightloop</b></div>
          <h1>{titles[mode]}</h1>
          {mode === "login" && <p className="muted center">Welcome back! Please enter your details.</p>}
          {mode === "login" && <div className="tabs" role="tablist">{["admin", "staff", "customer"].map((r) => <button type="button" role="tab" aria-selected={role === r} key={r} className={role === r ? "on" : ""} onClick={() => setRole(r)}>{r}</button>)}</div>}
          {mode === "signup" && <label>Full name<input value={f.full_name} onChange={set("full_name")} required minLength={2} /></label>}
          {mode === "reset" && <label>Reset token<input value={f.token} onChange={set("token")} required /></label>}
          {mode !== "reset" && <label>Email address<input type="email" placeholder="you@example.com" value={f.email} onChange={set("email")} required /></label>}
          {mode !== "forgot" && <label>{mode === "reset" ? "New password" : "Password"}
            <span className="pw"><input type={show ? "text" : "password"} value={f.password} onChange={set("password")} required /><button type="button" className="eye" onClick={() => setShow(!show)} aria-label="Show or hide password">{show ? "Hide" : "Show"}</button></span></label>}
          {mode === "login" && <a className="link right" onClick={() => setMode("forgot")}>Forgot password?</a>}
          <Err e={error} /><Ok m={info} />
          <button className="btn dark">{{ login: "Sign In", signup: "Sign Up", forgot: "Send reset link", reset: "Update password" }[mode]}</button>
          <p className="center muted">{mode === "login" ? <>Don't have an account? <a className="link" onClick={() => setMode("signup")}>Sign Up</a></> : <a className="link" onClick={() => setMode("login")}>Back to sign in</a>}</p>
          {onBack && <p className="center muted"><a className="link" onClick={onBack}>← Back to home</a></p>}
        </form>
      </div>
    </div>
  );
}

/* ---------------- Dashboard ---------------- */
function Chart({ pts }) {
  const W = 600, H = 220, P = 30, max = Math.max(1, ...pts.map((p) => p.v));
  const xy = pts.map((p, i) => [P + (i * (W - 2 * P)) / Math.max(1, pts.length - 1), H - P - (p.v / max) * (H - 2 * P)]);
  const line = xy.map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Collected revenue by month">
      <defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#c9a06a" stopOpacity=".5" /><stop offset="1" stopColor="#c9a06a" stopOpacity="0" /></linearGradient></defs>
      <path d={`${line} L${xy[xy.length - 1][0]} ${H - P} L${xy[0][0]} ${H - P}Z`} fill="url(#fill)" />
      <path d={line} fill="none" stroke="#a9824f" strokeWidth="3" strokeLinejoin="round" />
      {xy.map((p, i) => <g key={i}><circle cx={p[0]} cy={p[1]} r="4" fill="#a9824f" /><text x={p[0]} y={H - 8} textAnchor="middle" fontSize="12" fill="#6f6453">{pts[i].m}</text></g>)}
    </svg>
  );
}
function Dashboard({ names, q, openInvoice }) {
  const [d, setD] = useState({}); const [error, setError] = useState("");
  useEffect(() => {
    const now = new Date(), iso = (x) => x.toISOString().slice(0, 10), months = [];
    for (let i = 5; i >= 0; i--) { const s = new Date(now.getFullYear(), now.getMonth() - i, 1), e = new Date(now.getFullYear(), now.getMonth() - i + 1, 0); months.push({ m: s.toLocaleString("en", { month: "short" }), s: iso(new Date(s.getTime() - s.getTimezoneOffset() * 6e4)), e: iso(new Date(e.getTime() - e.getTimezoneOffset() * 6e4)) }); }
    const statuses = ["active", "quotation", "confirmed", "draft", "closed"];
    Promise.all([
      api("/reports/summary"),
      Promise.all(months.map((x) => api(`/reports/summary?start=${x.s}&end=${x.e}`).then((r) => ({ m: x.m, v: Number(r.collected_in_period) })))),
      api("/invoices?overdue=true&page_size=5"), api("/invoices?page_size=5"),
      Promise.all(statuses.map((s) => api(`/subscriptions?status=${s}&page_size=1`).then((r) => [s, r.total]))),
    ]).then(([sum, series, over, recent, subs]) => setD({ sum, series, over: over.items, recent: recent.items, subs })).catch((e) => setError(e.message));
  }, []);
  const { sum, series = [], over = [], recent = [], subs = [] } = d;
  const total = subs.reduce((a, [, n]) => a + n, 0) || 1, colors = ["#a9824f", "#d9b98a", "#e8d6b8", "#7d6a52", "#c4b49b"];
  let acc = 0;
  const kpis = sum ? [["Monthly Recurring Revenue", money(sum.monthly_recurring_revenue)], ["Active Subscriptions", sum.active_subscriptions], ["Collected this month", money(sum.collected_in_period)], ["Outstanding", money(sum.outstanding_balance)]] : [];
  return (
    <>
      <Err e={error} />
      <div className="kpis">{kpis.map(([k, v]) => <div className="card kpi" key={k}><span>{k}</span><b>{v}</b></div>)}</div>
      <div className="two">
        <div className="card"><h3>Revenue Trends <small className="muted">collected, last 6 months</small></h3>{series.length > 0 && <Chart pts={series} />}</div>
        <div className="card"><h3>Recent Activity</h3>
          {recent.filter((i) => hit(i, q)).map((i) => <div className="act" key={i.id} onClick={() => openInvoice(i.id)}><span className="av">{(names[i.customer_id] || "?")[0]}</span><span>{names[i.customer_id] || "Customer #" + i.customer_id} · {i.number || "Draft"} <Badge s={i.status} /></span><small className="muted">{day(i.invoice_date)}</small></div>)}
          {!recent.length && <p className="muted">No invoices yet. Run billing from Subscriptions.</p>}</div>
      </div>
      <div className="two">
        <div className="card"><h3>Overdue Invoices {sum && <small className="muted">{sum.overdue.count} overdue · {money(sum.overdue.amount)}</small>}</h3>
          <div className="scroll"><table><thead><tr><th>Client</th><th>Invoice</th><th>Due date</th><th>Balance</th><th>Status</th></tr></thead><tbody>
            {over.filter((i) => hit(i, q)).map((i) => <tr key={i.id} className="click" onClick={() => openInvoice(i.id)}><td>{names[i.customer_id] || "#" + i.customer_id}</td><td>{i.number}</td><td>{day(i.due_date)}</td><td>{money(i.balance)}</td><td><span className="badge overdue">Overdue</span></td></tr>)}
            {!over.length && <tr><td colSpan="5" className="muted">Nothing overdue.</td></tr>}</tbody></table></div></div>
        <div className="card"><h3>Subscription Status</h3>
          <svg viewBox="0 0 42 42" className="donut" role="img" aria-label="Subscriptions by status"><circle cx="21" cy="21" r="15.9" fill="none" stroke="#efe4d0" strokeWidth="6" />
            {subs.map(([s, n], i) => { const p = (n / total) * 100, el = <circle key={s} cx="21" cy="21" r="15.9" fill="none" stroke={colors[i]} strokeWidth="6" strokeDasharray={`${p} ${100 - p}`} strokeDashoffset={25 - acc} />; acc += p; return el; })}</svg>
          <div className="legend">{subs.map(([s, n], i) => <span key={s}><i style={{ background: colors[i] }} />{s} ({n})</span>)}</div></div>
      </div>
    </>
  );
}

/* ---------------- Invoices ---------------- */
function InvoiceModal({ id, staff, onClose, onChange }) {
  const { data: inv, error, reload } = useLoad(staff ? `/invoices/${id}` : `/portal/invoices/${id}`);
  const [msg, setMsg] = useState("");
  const [pay, setPay] = useState({ method: "bank_transfer", amount: "", paid_on: new Date().toISOString().slice(0, 10), note: "" });
  const post = (p, body) => api(`/invoices/${id}/${p}`, { method: "POST", body });
  const act = (fn) => async () => { setMsg(""); try { await fn(); reload(); onChange(); } catch (e) { setMsg(e.message); } };
  const print = async () => { try { const r = await api(`/invoices/${id}/print`, { raw: true }); window.open(URL.createObjectURL(new Blob([await r.text()], { type: "text/html" })), "_blank"); } catch (e) { setMsg(e.message); } };
  return (
    <Modal title={inv ? inv.number || `Draft #${inv.id}` : "Invoice"} onClose={onClose}>
      <Err e={error || msg} />
      {inv && <>
        <p className="muted">{inv.customer.full_name} · {inv.customer.email} · <Badge s={inv.status} /><br />Period {day(inv.period_start)} – {day(inv.period_end)} · Due {day(inv.due_date)}</p>
        <div className="scroll"><table><thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Tax</th><th>Total</th></tr></thead><tbody>
          {inv.lines.map((l) => <tr key={l.id}><td>{l.description}</td><td>{l.quantity}</td><td>{money(l.unit_price)}</td><td>{money(l.tax_amount)}</td><td>{money(l.line_total)}</td></tr>)}</tbody></table></div>
        <div className="totals"><span>Subtotal</span><b>{money(inv.subtotal)}</b><span>Discount</span><b>{money(inv.discount_total)}</b><span>Tax</span><b>{money(inv.tax_total)}</b><span>Total</span><b>{money(inv.total)}</b><span>Paid</span><b>{money(inv.amount_paid)}</b><span>Balance</span><b className="due">{money(inv.balance)}</b></div>
        {staff && <>
          <div className="row">
            {inv.status === "draft" && <button className="btn dark" onClick={act(() => post("confirm"))}>Confirm</button>}
            {["confirmed", "paid"].includes(inv.status) && <button className="btn" onClick={act(() => post("send"))}>Email</button>}
            {["draft", "confirmed"].includes(inv.status) && <button className="btn danger" onClick={act(() => post("cancel"))}>Cancel</button>}
            <button className="btn" onClick={print}>Print</button></div>
          {inv.status === "confirmed" && <form className="row" onSubmit={(e) => { e.preventDefault(); act(() => post("payments", { ...pay, amount: Number(pay.amount) }))(); }}>
            <select aria-label="Method" value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })}>{["bank_transfer", "upi", "card", "cash", "cheque"].map((m) => <option key={m}>{m}</option>)}</select>
            <input aria-label="Amount" type="number" step="0.01" placeholder="Amount" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} required />
            <input aria-label="Paid on" type="date" value={pay.paid_on} onChange={(e) => setPay({ ...pay, paid_on: e.target.value })} />
            <input aria-label="Note" placeholder="Note" value={pay.note} onChange={(e) => setPay({ ...pay, note: e.target.value })} />
            <button className="btn dark">Record payment</button></form>}
        </>}
        {inv.payments.length > 0 && <><h4>Payments</h4>{inv.payments.map((p) => <div className="muted" key={p.id}>{day(p.paid_on)} · {p.method} · {money(p.amount)} {p.note && "· " + p.note}</div>)}</>}
      </>}
    </Modal>
  );
}
function Invoices({ staff, names, q, open, setOpen }) {
  const [status, setStatus] = useState("");
  const { data, error, reload } = useLoad(`${staff ? "/invoices" : "/portal/invoices"}?page_size=100${status ? "&status=" + status : ""}`);
  return (
    <>
      <div className="head"><h2>Invoices</h2>{staff && <select aria-label="Status filter" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{["draft", "confirmed", "paid", "cancelled"].map((s) => <option key={s}>{s}</option>)}</select>}</div>
      <Err e={error} />
      <div className="card scroll"><table><thead><tr><th>Number</th>{staff && <th>Customer</th>}<th>Period</th><th>Due</th><th>Status</th><th>Total</th><th>Balance</th></tr></thead><tbody>
        {(data?.items || []).filter((i) => hit(i, q)).map((i) => <tr key={i.id} className="click" onClick={() => setOpen(i.id)}><td>{i.number || `Draft #${i.id}`}</td>{staff && <td>{names[i.customer_id] || "#" + i.customer_id}</td>}<td>{day(i.period_start)} – {day(i.period_end)}</td><td>{day(i.due_date)}</td><td><Badge s={i.status} /></td><td>{money(i.total)}</td><td>{money(i.balance)}</td></tr>)}
        {data && !data.items.length && <tr><td colSpan="7" className="muted">No invoices yet.</td></tr>}</tbody></table></div>
      {open && <InvoiceModal id={open} staff={staff} onClose={() => setOpen(null)} onChange={reload} />}
    </>
  );
}

/* ---------------- Subscriptions ---------------- */
function Subscriptions({ staff, names, q }) {
  const { data, error, reload } = useLoad(staff ? "/subscriptions?page_size=100" : "/portal/subscriptions?page_size=100");
  const [msg, setMsg] = useState(""); const [form, setForm] = useState(null);
  const customers = useLoad(staff ? "/admin/customers" : "/auth/me"), plans = useLoad(staff ? "/catalog/plans" : "/auth/me");
  const go = async (fn) => { setMsg(""); try { const r = await fn(); reload(); return r; } catch (e) { setMsg(e.message); } };
  const next = { draft: "quotation", quotation: "confirmed", confirmed: "active", active: "closed" };
  async function create(e) {
    e.preventDefault();
    const s = await go(() => api("/subscriptions", { method: "POST", body: { customer_id: +form.customer_id, plan_id: +form.plan_id, quantity: +form.quantity, start_date: form.start_date, expiry_date: form.expiry_date } }));
    if (s) setForm(null);
  }
  const f = (k) => ({ value: form[k], onChange: (e) => setForm({ ...form, [k]: e.target.value }), required: true });
  return (
    <>
      <div className="head"><h2>Subscriptions</h2>{staff && <div className="row nomargin">
        <button className="btn" onClick={() => go(async () => { const r = await api("/billing/runs", { method: "POST" }); setMsg(`Billing run complete: ${r.invoices_created} invoice(s) created.`); })}>Run billing</button>
        <button className="btn dark" onClick={() => setForm({ customer_id: "", plan_id: "", quantity: 1, start_date: new Date().toISOString().slice(0, 10), expiry_date: "" })}>New subscription</button></div>}</div>
      <Err e={error} /><Ok m={msg} />
      <div className="card scroll"><table><thead><tr><th>Number</th>{staff && <th>Customer</th>}<th>Qty</th><th>Start</th><th>Expiry</th><th>Next billing</th><th>Status</th>{staff && <th />}</tr></thead><tbody>
        {(data?.items || []).filter((s) => hit(s, q)).map((s) => <tr key={s.id}><td>{s.number}</td>{staff && <td>{names[s.customer_id] || "#" + s.customer_id}</td>}<td>{s.quantity}</td><td>{day(s.start_date)}</td><td>{day(s.expiry_date)}</td><td>{day(s.next_billing_date)}</td><td><Badge s={s.status} /></td>
          {staff && <td>{next[s.status] && <button className="btn sm" onClick={() => go(() => api(`/subscriptions/${s.id}/transition`, { method: "POST", body: { status: next[s.status] } }))}>→ {next[s.status]}</button>}</td>}</tr>)}
        {data && !data.items.length && <tr><td colSpan="8" className="muted">No subscriptions yet.</td></tr>}</tbody></table></div>
      {form && <Modal title="New subscription" onClose={() => setForm(null)}><form className="formgrid" onSubmit={create}>
        <label>Customer<select {...f("customer_id")}><option value="">Select…</option>{(customers.data || []).map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}</select></label>
        <label>Plan<select {...f("plan_id")}><option value="">Select…</option>{(plans.data || []).map((p) => <option key={p.id} value={p.id}>{p.name} ({p.billing_period})</option>)}</select></label>
        <label>Quantity<input type="number" min="1" {...f("quantity")} /></label><label>Start date<input type="date" {...f("start_date")} /></label><label>Expiry date<input type="date" {...f("expiry_date")} /></label>
        <button className="btn dark">Create</button></form></Modal>}
    </>
  );
}

/* ---------------- Products & Plans, Customers ---------------- */
function Products({ q, admin }) {
  const prods = useLoad("/catalog/products"), plans = useLoad("/catalog/plans"), taxes = useLoad("/catalog/taxes");
  const [form, setForm] = useState(null); const [error, setError] = useState("");
  const reload = () => { prods.reload(); plans.reload(); };
  async function save(e) {
    e.preventDefault(); setError("");
    try {
      if (form.kind === "product") await api("/catalog/products", { method: "POST", body: { name: form.name, product_type: form.product_type, sales_price: +form.price, cost_price: +(form.cost || 0), notes: form.notes || null, tax_id: form.tax_id ? +form.tax_id : null } });
      else await api("/catalog/plans", { method: "POST", body: { name: form.name, product_id: +form.product_id, price: +form.price, billing_period: form.billing_period, min_quantity: 1, available_from: form.from, end_behavior: form.end_behavior } });
      setForm(null); reload();
    } catch (x) { setError(x.message); }
  }
  const f = (k) => ({ value: form[k] || "", onChange: (e) => setForm({ ...form, [k]: e.target.value }) });
  const today = new Date().toISOString().slice(0, 10);
  return (
    <>
      <div className="head"><h2>Products &amp; Plans</h2>{admin && <div className="row nomargin">
        <button className="btn" onClick={() => setForm({ kind: "product", product_type: "service" })}>New product</button>
        <button className="btn dark" onClick={() => setForm({ kind: "plan", billing_period: "monthly", end_behavior: "auto_close", from: today })}>New plan</button></div>}</div>
      <Err e={prods.error || plans.error} />
      <div className="card scroll"><h3>Products</h3><table><thead><tr><th>Name</th><th>Type</th><th>Sales price</th><th>Cost</th><th>Notes</th></tr></thead><tbody>
        {(prods.data || []).filter((p) => hit(p, q)).map((p) => <tr key={p.id}><td>{p.name}</td><td>{p.product_type}</td><td>{money(p.sales_price)}</td><td>{money(p.cost_price)}</td><td>{p.notes || "—"}</td></tr>)}</tbody></table></div>
      <div className="card scroll gap"><h3>Plans</h3><table><thead><tr><th>Name</th><th>Billing</th><th>Price</th><th>Available from</th><th>At end</th></tr></thead><tbody>
        {(plans.data || []).filter((p) => hit(p, q)).map((p) => <tr key={p.id}><td>{p.name}</td><td>{p.billing_period}</td><td>{money(p.price)}</td><td>{day(p.available_from)}</td><td>{p.end_behavior}</td></tr>)}</tbody></table></div>
      {form && <Modal title={form.kind === "product" ? "New product" : "New plan"} onClose={() => setForm(null)}><form className="formgrid" onSubmit={save}>
        <label>Name<input required minLength={2} {...f("name")} /></label>
        {form.kind === "product" ? <>
          <label>Type<input required {...f("product_type")} /></label><label>Sales price<input type="number" step="0.01" min="0" required {...f("price")} /></label>
          <label>Cost price<input type="number" step="0.01" min="0" {...f("cost")} /></label>
          <label>Tax<select {...f("tax_id")}><option value="">None</option>{(taxes.data || []).map((t) => <option key={t.id} value={t.id}>{t.name} ({t.rate}%)</option>)}</select></label>
          <label>Notes<input {...f("notes")} /></label></> : <>
          <label>Product<select required {...f("product_id")}><option value="">Select…</option>{(prods.data || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <label>Price<input type="number" step="0.01" min="0" required {...f("price")} /></label>
          <label>Billing period<select {...f("billing_period")}>{["daily", "weekly", "monthly", "yearly"].map((b) => <option key={b}>{b}</option>)}</select></label>
          <label>At expiry<select {...f("end_behavior")}>{["auto_close", "manual_close", "pause", "renew"].map((b) => <option key={b}>{b}</option>)}</select></label>
          <label>Available from<input type="date" required {...f("from")} /></label></>}
        <Err e={error} /><button className="btn dark">Save</button></form></Modal>}
    </>
  );
}
function Customers({ q }) {
  const { data, error } = useLoad("/admin/customers");
  return (<><div className="head"><h2>Customers</h2></div><Err e={error} />
    <div className="card scroll"><table><thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Status</th></tr></thead><tbody>
      {(data || []).filter((c) => hit(c, q)).map((c) => <tr key={c.id}><td>{c.id}</td><td>{c.full_name}</td><td>{c.email}</td><td><Badge s={c.is_active ? "active" : "closed"} /></td></tr>)}
      {data && !data.length && <tr><td colSpan="4" className="muted">No customers yet.</td></tr>}</tbody></table></div></>);
}

/* ---------------- Shell ---------------- */
export default function App() {
  const [user, setUser] = useState(null); const [ready, setReady] = useState(!tok.get());
  const [auth, setAuth] = useState(() => (location.pathname === "/reset-password" ? "login" : null));
  const [page, setPage] = useState("dashboard"); const [navOpen, setNavOpen] = useState(false);
  const [q, setQ] = useState(""); const [names, setNames] = useState({}); const [openInv, setOpenInv] = useState(null);
  const start = (u) => {
    setUser(u); setPage(u.role === "customer" ? "invoices" : "dashboard");
    if (u.role !== "customer") api("/admin/customers").then((c) => setNames(Object.fromEntries(c.map((x) => [x.id, x.full_name])))).catch(() => {});
  };
  useEffect(() => { if (tok.get()) api("/auth/me").then(start).catch(() => tok.set(null)).finally(() => setReady(true)); }, []);
  if (!ready) return <div className="center muted pad">Loading…</div>;
  if (!user) return auth
    ? <Login onDone={start} initialMode={auth} onBack={() => setAuth(null)} />
    : <Home onAuth={setAuth} />;
  const staff = user.role !== "customer";
  const nav = staff ? [["dashboard", "Dashboard"], ["customers", "Customers"], ["products", "Products & Plans"], ["subscriptions", "Subscriptions"], ["invoices", "Invoices"]] : [["invoices", "Invoices"], ["subscriptions", "Subscriptions"]];
  const go = (p) => { setPage(p); setQ(""); setNavOpen(false); };
  return (
    <div className="app">
      <aside className={navOpen ? "open" : ""}>
        <div className="brand"><Logo /> Brightloop</div>
        <nav>{nav.map(([k, l]) => <a key={k} className={page === k ? "on" : ""} onClick={() => go(k)}>{l}</a>)}</nav>
        <div className="spacer" />
        <a onClick={() => { tok.set(null); setUser(null); setAuth(null); }}>Log out</a>
      </aside>
      {navOpen && <div className="scrim" onClick={() => setNavOpen(false)} />}
      <div className="content">
        <header className="top">
          <button className="burger" onClick={() => setNavOpen(true)} aria-label="Open menu">☰</button>
          <input className="search" type="search" placeholder="Search this page…" aria-label="Search" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="me"><span className="av">{user.full_name[0]}</span><span className="hide-s">{user.full_name}<small>{user.role}</small></span></div>
        </header>
        <main>
          {page === "dashboard" && <Dashboard names={names} q={q} openInvoice={(id) => { setOpenInv(id); setPage("invoices"); }} />}
          {page === "customers" && <Customers q={q} />}
          {page === "products" && <Products q={q} admin={user.role === "admin"} />}
          {page === "subscriptions" && <Subscriptions staff={staff} names={names} q={q} />}
          {page === "invoices" && <Invoices staff={staff} names={names} q={q} open={openInv} setOpen={setOpenInv} />}
        </main>
      </div>
    </div>
  );
}
