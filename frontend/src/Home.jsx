import { useState } from "react";
import Logo from "./Logo.jsx";

const FEATURES = [
  ["Products & plans", "Define what you sell, then attach plans with a price, billing period and end-of-term behaviour. Discounts and taxes are supported."],
  ["Subscription lifecycle", "Move every subscription through draft, quotation, confirmed, active and closed, one step at a time."],
  ["Automatic billing", "Billing runs create invoices for each period, catch up on missed periods and never bill the same period twice."],
  ["Invoices you can print", "Confirm invoices, email them to customers and print clean copies straight from the console."],
  ["Payments recorded", "Log bank transfers, UPI, cards, cash and cheques against an invoice and watch the balance update."],
  ["Live revenue dashboard", "See monthly recurring revenue, collections, outstanding balances and overdue invoices at a glance."],
];

const STEPS = [
  ["Set up your catalog", "Create products and the plans customers can buy."],
  ["Start subscriptions", "Pick a customer, a plan, a quantity and the start and expiry dates."],
  ["Billing runs on schedule", "Invoices are generated for each period, either on demand or automatically."],
  ["Get paid and track", "Record payments as they arrive and follow revenue on the dashboard."],
];

const ROLES = [
  ["Admin", "Full control. Manages the catalog, creates staff accounts and sees everything."],
  ["Staff", "Manages customers, subscriptions and invoices, and records payments."],
  ["Customer", "Signs up, then views their own subscriptions and invoices in the portal."],
];

const FAQS = [
  ["Can customers sign up on their own?", "Yes. Sign up creates a customer account that can see its own subscriptions and invoices. Staff accounts are created by an admin."],
  ["Does billing run automatically?", "It can. Automatic runs are switched on in the server settings. Staff can also run billing manually from the Subscriptions page at any time."],
  ["What if I forget my password?", "Use Forgot password on the sign-in screen. A reset link is emailed and expires after a short time."],
  ["Can invoices be printed?", "Yes. Every invoice has a print view that opens in a new tab, ready to save or send."],
];

export default function Home({ onAuth }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="home">
      <header className="hnav">
        <a href="#top" className="hbrand" onClick={closeMenu}><Logo size={26} /><b>Brightloop</b></a>
        <nav className={"hlinks" + (menuOpen ? " open" : "")} aria-label="Page sections">
          <a href="#features" onClick={closeMenu}>Features</a>
          <a href="#how" onClick={closeMenu}>How it works</a>
          <a href="#roles" onClick={closeMenu}>Who it's for</a>
          <a href="#faq" onClick={closeMenu}>FAQ</a>
        </nav>
        <div className="hcta">
          <button className="btn" onClick={() => onAuth("login")}>Sign in</button>
          <button className="btn dark" onClick={() => onAuth("signup")}>Sign up</button>
        </div>
        <button className="hburger" aria-label="Open menu" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>☰</button>
      </header>

      <section className="hero" id="top">
        <div>
          <span className="pill">Subscription billing, on autopilot</span>
          <h1>Every billing cycle, <em>perfectly on time.</em></h1>
          <p className="lead">Brightloop brings your products, plans, subscriptions, invoices and payments into one console, so recurring revenue comes in without the spreadsheets.</p>
          <div className="hactions">
            <button className="btn dark big" onClick={() => onAuth("signup")}>Get started</button>
            <a className="btn big" href="#features">See features</a>
          </div>
        </div>
        <div className="card hero-card" aria-hidden="true">
          <div className="hk">
            <div><span>Monthly recurring revenue</span><b>$12,480.00</b></div>
            <div><span>Active subscriptions</span><b>146</b></div>
            <div><span>Collected this month</span><b>$10,920.00</b></div>
            <div><span>Overdue</span><b>$1,560.00</b></div>
          </div>
          {[["Northwind Traders", "Pro plan · monthly", "active"], ["Kite & Co", "Team plan · yearly", "confirmed"], ["Lumen Studio", "Starter · monthly", "draft"]].map(([name, plan, status]) => (
            <div className="hrow" key={name}><span>{name}<br /><small className="muted">{plan}</small></span><span className={"badge " + status}>{status}</span></div>
          ))}
          <small className="muted">Preview with sample data</small>
        </div>
      </section>

      <section className="sec" id="features">
        <div className="sec-head">
          <span className="eyebrow">Features</span>
          <h2>Everything a subscription business needs</h2>
          <p className="muted">From the first product to the last payment, each step is built in.</p>
        </div>
        <div className="fgrid">
          {FEATURES.map(([title, text], i) => (
            <div className="card fcard" key={title}><span className="ficon">{String(i + 1).padStart(2, "0")}</span><h3>{title}</h3><p className="muted">{text}</p></div>
          ))}
        </div>
      </section>

      <section className="sec" id="how">
        <div className="sec-head">
          <span className="eyebrow">How it works</span>
          <h2>From catalog to cash in four steps</h2>
        </div>
        <div className="steps">
          {STEPS.map(([title, text], i) => (
            <div className="card step" key={title}><span className="ficon">{i + 1}</span><h3>{title}</h3><p className="muted">{text}</p></div>
          ))}
        </div>
      </section>

      <section className="sec" id="roles">
        <div className="sec-head">
          <span className="eyebrow">Who it's for</span>
          <h2>The right view for every role</h2>
        </div>
        <div className="fgrid">
          {ROLES.map(([role, text]) => (
            <div className="card fcard" key={role}><h3>{role}</h3><p className="muted">{text}</p></div>
          ))}
        </div>
      </section>

      <section className="sec" id="faq">
        <div className="sec-head">
          <span className="eyebrow">FAQ</span>
          <h2>Questions, answered</h2>
        </div>
        <div className="faq">
          {FAQS.map(([q, a]) => (
            <details className="card" key={q}><summary>{q}</summary><p className="muted">{a}</p></details>
          ))}
        </div>
      </section>

      <section className="sec">
        <div className="band">
          <h2>Ready to run billing on autopilot?</h2>
          <p>Create an account in a minute and set up your first plan today.</p>
          <div className="hactions">
            <button className="btn big" onClick={() => onAuth("signup")}>Sign up</button>
            <button className="btn big ghost" onClick={() => onAuth("login")}>Sign in</button>
          </div>
        </div>
      </section>

      <footer className="hfoot">
        <span className="hbrand"><Logo size={22} /><b>Brightloop</b></span>
        <span>© 2026 Brightloop Billing. All rights reserved.</span>
      </footer>
    </div>
  );
}
