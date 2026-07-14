import { useState, useEffect, createContext, useContext, useMemo, useRef } from "react"
import { createPortal } from "react-dom"
import { API, CURRENT_YEAR, DEFAULT_YEAR, DEFAULT_MONTH, periodForMonth } from "./config.js"
import { CD, KineoLogo, NavIcon, ScheduleHelp, Bell, LogOut, Calendar, Users, formatRoleLabel, hasFullAccess, FULL_ACCESS_ROLES } from "./brand.jsx"

const AuthCtx = createContext(null)

// ── Auth Hook ──────────────────────────────────────────────────────────────
function useAuth() { return useContext(AuthCtx) }

// ── API Helper ─────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const token = localStorage.getItem("token")
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...opts,
  })
  if (res.status === 401) { localStorage.clear(); window.location.reload() }
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || "Fehler") }
  return res.json()
}

function useAvailableYears() {
  const [years, setYears] = useState([CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR + 1])
  useEffect(() => {
    api("/api/years").then(d => setYears(d.years)).catch(() => {})
  }, [])
  return years
}

function formatImportDt(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleString("de-CH", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    })
  } catch { return null }
}

function ImportStatusPanel({ year, highlightMonth, onMonthClick, reloadKey = 0, compact = false }) {
  const { user } = useAuth()
  const [status, setStatus] = useState(null)

  useEffect(() => {
    api(`/api/import-status/${year}`).then(setStatus).catch(() => setStatus(null))
  }, [year, reloadKey])

  if (!status) return null

  const importedCount = status.months.filter(m => m.umsatz.imported).length

  return (
    <div style={{
      background: "white", borderRadius: 8, padding: compact ? "14px 18px" : "18px 22px",
      marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontFamily: "'Roboto Condensed', sans-serif", fontWeight: 700, fontSize: compact ? 14 : 16, color: "#004869" }}>
            Gespeicherte Daten {year}
          </div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
            {importedCount} von 12 Monaten mit CSV-Umsatz importiert
          </div>
        </div>
        {status.storage && user?.role !== "teamlead" && (
          <div style={{ fontSize: 11, color: "#666", textAlign: "right", lineHeight: 1.5 }}>
            {status.storage.backend === "postgresql" ? (
              <div style={{ color: "#1a7a1a", fontWeight: 600 }}>✓ PostgreSQL — Daten persistent</div>
            ) : (
              <>
                <div>Datenbank: {status.storage.database_size_kb} KB (SQLite)</div>
                {status.storage.on_render && !status.storage.persistent && (
                  <div style={{ color: "#c0392b", fontWeight: 600 }}>⚠ Daten gehen bei Deploy verloren</div>
                )}
              </>
            )}
          </div>
        )}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: compact ? "repeat(6, 1fr)" : "repeat(6, 1fr)", gap: 8 }}>
        {status.months.map(m => {
          const hasUmsatz = m.umsatz.imported
          const hasInputs = m.inputs.saved
          const active = highlightMonth === m.month
          const short = m.month_name.slice(0, 3)
          return (
            <button
              key={m.month}
              type="button"
              onClick={() => onMonthClick?.(m.month)}
              style={{
                textAlign: "left", cursor: onMonthClick ? "pointer" : "default",
                background: hasUmsatz ? "#E8F8E8" : "#F8F8F8",
                border: active ? "2px solid #004869" : `1px solid ${hasUmsatz ? "#B8E0B8" : "#E0E0E0"}`,
                borderRadius: 8, padding: "8px 10px", minHeight: compact ? 58 : 72,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 12, color: "#333", marginBottom: 4 }}>{short}</div>
              {hasUmsatz ? (
                <>
                  <div style={{ fontSize: 10, color: "#1a7a1a", lineHeight: 1.35 }}>
                    {m.umsatz.ma_count} MA · CHF {Math.round(m.umsatz.total).toLocaleString("de-CH")}
                  </div>
                  <div style={{ fontSize: 9, color: "#888", marginTop: 2 }}>
                    {formatImportDt(m.umsatz.uploaded_at)}
                    {m.umsatz.uploaded_by ? ` · ${m.umsatz.uploaded_by}` : ""}
                  </div>
                </>
              ) : (
                <div style={{ fontSize: 10, color: "#aaa" }}>kein CSV</div>
              )}
              {hasInputs && (
                <div style={{ fontSize: 9, color: "#666", marginTop: 3 }}>✓ Tätigkeiten</div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function YearSelect({ value, onChange, years, style }) {
  const opts = useMemo(() => {
    const list = years?.length ? [...years] : []
    if (value != null && !list.includes(value)) list.push(value)
    return list.sort((a, b) => b - a)
  }, [years, value])
  const safeValue = opts.includes(value) ? value : opts[0]
  return (
    <select value={safeValue} onChange={e => onChange(+e.target.value)}
      style={style || { padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14 }}>
      {opts.map(y => <option key={y} value={y}>{y}</option>)}
    </select>
  )
}

function useYtd(year, reloadKey = 0) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setData(null)
    api(`/api/ytd/${year}`)
      .then(d => {
        if (!active) return
        if (d?.year !== year) {
          setError("Ungültige Antwort vom Server")
          return
        }
        setData(d)
      })
      .catch(e => { if (active) setError(e.message || "Daten konnten nicht geladen werden") })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [year, reloadKey])

  return { data, loading, error }
}

// ── Colors & ZEG ──────────────────────────────────────────────────────────
const ZEG_COLORS = {
  green: { bg: "#E8F8E8", text: "#1a7a1a", border: "#4CAF50" },
  amber: { bg: "#FFF8E0", text: "#856404", border: "#FFC107" },
  red:   { bg: "#FFE8E8", text: "#c0392b", border: "#F44336" },
  gray:  { bg: "#F5F5F5", text: "#888888", border: "#CCCCCC" },
}

function ZEGBadge({ value, color, size = "sm" }) {
  const c = ZEG_COLORS[color || "gray"]
  const pct = value ? `${(value * 100).toFixed(1)}%` : "—"
  const pad = size === "lg" ? "8px 16px" : "4px 10px"
  const fs = size === "lg" ? "15px" : "12px"
  return (
    <span style={{
      background: c.bg, color: c.text, border: `1.5px solid ${c.border}`,
      borderRadius: 4, padding: pad, fontSize: fs, fontWeight: 700,
      display: "inline-block", minWidth: size === "lg" ? 80 : 60, textAlign: "center"
    }}>{pct}</span>
  )
}

// ── Notification Bell ──────────────────────────────────────────────────────
function NotificationBell({ setPage }) {
  const [notifs, setNotifs] = useState([])
  const [open, setOpen] = useState(false)

  const load = () => api("/api/notifications").then(setNotifs).catch(()=>{})

  useEffect(() => {
    load()
    const t = setInterval(load, 60000) // refresh every minute
    return () => clearInterval(t)
  }, [])

  const markRead = async (id) => {
    await api(`/api/notifications/${id}/read`, {method:"PATCH"})
    load()
  }

  const markAllRead = async () => {
    await api("/api/notifications/read-all", {method:"PATCH"})
    setNotifs([]); setOpen(false)
  }

  const count = notifs.length

  const typeIcon = (type) => type === "new_ma" ? "👤" : "⚠️"
  const typeColor = (type) => type === "new_ma" ? "#E8F0FF" : "#FFF3CD"
  const typeTextColor = (type) => type === "new_ma" ? "#1a3a8a" : "#856404"

  return (
    <div style={{ position: "relative", marginTop: 16 }}>
      <button onClick={() => setOpen(!open)} style={{
        background: count > 0 ? "rgba(255,200,0,0.2)" : "rgba(255,255,255,0.1)",
        border: count > 0 ? "1.5px solid rgba(255,200,0,0.5)" : "1.5px solid rgba(255,255,255,0.2)",
        borderRadius: 4, padding: "6px 14px", cursor: "pointer", color: "white",
        display: "flex", alignItems: "center", gap: 8, fontSize: 13, width: "100%"
      }}>
        <Bell size={16} strokeWidth={1.75} />
        <span>{count > 0 ? `${count} Hinweis${count>1?"e":""}` : "Keine Hinweise"}</span>
        {count > 0 && <span style={{
          background: "#FF4444", color: "white", borderRadius: "50%",
          width: 18, height: 18, fontSize: 10, fontWeight: 800,
          display: "flex", alignItems: "center", justifyContent: "center", marginLeft: "auto"
        }}>{count}</span>}
      </button>

      {open && count > 0 && (
        <div style={{
          position: "fixed", left: 220, top: 80, width: 360, zIndex: 1000,
          background: "white", borderRadius: 8, boxShadow: "0 8px 30px rgba(0,0,0,0.2)",
          border: "1px solid #E0E0E0", overflow: "hidden"
        }}>
          <div style={{ background: "#004869", color: "white", padding: "14px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }}>
              <Bell size={16} /> Hinweise ({count})
            </span>
            <button onClick={markAllRead} style={{ background: "rgba(255,255,255,0.2)", border: "none", color: "white", padding: "4px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12 }}>
              Alle als gelesen markieren
            </button>
          </div>
          <div style={{ maxHeight: 400, overflowY: "auto" }}>
            {notifs.map(n => (
              <div key={n.id} style={{ padding: "14px 18px", borderBottom: "1px solid #F0F0F0", background: typeColor(n.type) }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: typeTextColor(n.type) }}>
                      {typeIcon(n.type)} {n.message}
                    </div>
                    {n.type === "new_ma" && (
                      <div style={{ fontSize: 12, color: "#555", marginTop: 4 }}>
                        MA im Arbeitstag-Muster erfassen und aktivieren.
                        <button onClick={() => { setPage("admin"); markRead(n.id); setOpen(false) }}
                          style={{ background: "none", border: "none", color: "#004869", cursor: "pointer", fontWeight: 700, fontSize: 12, padding: "0 4px" }}>
                          → Admin öffnen
                        </button>
                      </div>
                    )}
                    {n.type === "missing_schedule" && (
                      <div style={{ fontSize: 12, color: "#555", marginTop: 4 }}>
                        Arbeitstag-Muster für {n.detail} fehlt noch.
                        <button onClick={() => { setPage("admin"); markRead(n.id); setOpen(false) }}
                          style={{ background: "none", border: "none", color: "#004869", cursor: "pointer", fontWeight: 700, fontSize: 12, padding: "0 4px" }}>
                          → Admin öffnen
                        </button>
                      </div>
                    )}
                    <div style={{ fontSize: 10, color: "#999", marginTop: 6 }}>
                      {new Date(n.created_at).toLocaleString("de-CH")}
                    </div>
                  </div>
                  <button onClick={() => markRead(n.id)} style={{ background: "none", border: "none", cursor: "pointer", color: "#999", fontSize: 16, padding: "0 4px" }}>✕</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Layout ─────────────────────────────────────────────────────────────────
function Layout({ children, page, setPage }) {
  const auth = useAuth()
  const [navOpen, setNavOpen] = useState(false)
  const [isNarrow, setIsNarrow] = useState(typeof window !== "undefined" && window.innerWidth < 820)
  useEffect(() => {
    const onResize = () => setIsNarrow(window.innerWidth < 820)
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])
  useEffect(() => { setNavOpen(false) }, [page])

  const nav = [
    { id: "dashboard", label: "Dashboard" },
    { id: "upload", label: "Daten eingeben", roles: FULL_ACCESS_ROLES },
    { id: "overview", label: "Jahresübersicht" },
    { id: "exports", label: "Exporte", roles: FULL_ACCESS_ROLES },
    { id: "bilats", label: "Bilaterals" },
    { id: "qualziele", label: "Quali-Themen" },
    { id: "ablage", label: "Ablage" },
    { id: "lohnrechner", label: "Lohnrechner", roles: FULL_ACCESS_ROLES },
    { id: "profil", label: "Profil" },
    { id: "admin", label: "Admin", roles: FULL_ACCESS_ROLES },
  ].filter(n => !n.roles || n.roles.includes(auth.user?.role))

  const sidebar = (
    <div style={{
      width: isNarrow ? "min(280px, 86vw)" : 220,
      background: CD.darkBlue, color: "white", flexShrink: 0,
      display: "flex", flexDirection: "column",
      position: isNarrow ? "fixed" : "relative",
      top: 0, left: 0, bottom: 0, zIndex: 40,
      transform: isNarrow && !navOpen ? "translateX(-105%)" : "none",
      transition: "transform 0.2s ease",
      boxShadow: isNarrow && navOpen ? "8px 0 24px rgba(0,0,0,0.25)" : "none",
    }}>
      <div style={{ padding: "24px 20px 20px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
        <KineoLogo variant="white" height={34} />
        <div style={{ fontSize: 10, opacity: 0.45, marginTop: 10, letterSpacing: 2, textTransform: "uppercase", fontFamily: CD.fontDisplay }}>Analytics</div>
        {hasFullAccess(auth.user?.role) && <NotificationBell setPage={setPage} />}
      </div>
      <nav style={{ flex: 1, overflowY: "auto" }}>
        {nav.map(n => (
          <button key={n.id} onClick={() => setPage(n.id)} style={{
            width: "100%", padding: "11px 20px", background: page === n.id ? "rgba(255,255,255,0.12)" : "transparent",
            border: "none", borderLeft: page === n.id ? "3px solid #fa4616" : "3px solid transparent",
            color: page === n.id ? "white" : "rgba(255,255,255,0.7)", textAlign: "left", cursor: "pointer", fontSize: 13,
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <NavIcon name={n.id} size={17} color={page === n.id ? "#fa4616" : "rgba(255,255,255,0.65)"} />
            {n.label}
          </button>
        ))}
      </nav>
      <div style={{ padding: "16px 20px", borderTop: "1px solid rgba(255,255,255,0.15)" }}>
        <div style={{ fontSize: 12, opacity: 0.8 }}>{auth.user?.full_name}</div>
        <div style={{ fontSize: 11, opacity: 0.5, marginBottom: 8 }}>{formatRoleLabel(auth.user?.role)}</div>
        <button onClick={auth.logout} style={{
          background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)",
          color: "white", padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12,
          display: "flex", alignItems: "center", gap: 6,
        }}><LogOut size={14} /> Abmelden</button>
      </div>
    </div>
  )

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: CD.bg, fontFamily: CD.fontBody }}>
      {isNarrow && navOpen && (
        <div onClick={() => setNavOpen(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 30 }} />
      )}
      {sidebar}
      <div style={{ flex: 1, overflow: "auto", minWidth: 0 }}>
        {isNarrow && (
          <div style={{
            display: "flex", alignItems: "center", gap: 12, padding: "12px 16px",
            background: CD.darkBlue, color: "white", position: "sticky", top: 0, zIndex: 20,
          }}>
            <button type="button" onClick={() => setNavOpen(o => !o)}
              style={{ background: "rgba(255,255,255,0.12)", border: "none", color: "white", padding: "8px 12px", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 13 }}>
              Menü
            </button>
            <KineoLogo variant="white" height={26} />
          </div>
        )}
        <div style={{ padding: isNarrow ? "18px 16px" : "32px 36px" }}>{children}</div>
      </div>
    </div>
  )
}

// ── Login Page ─────────────────────────────────────────────────────────────
function LoginPage({ onLogin }) {
  const [form, setForm] = useState({ username: "", password: "" })
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault(); setError(""); setLoading(true)
    try {
      const res = await fetch(`${API}/api/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      })
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail) }
      const data = await res.json()
      localStorage.setItem("token", data.access_token)
      onLogin(data.user)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(135deg,#004869,#0a2734)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "white", borderRadius: 10, padding: "48px 40px", width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
            <KineoLogo variant="dark" height={48} />
          </div>
          <div style={{ fontSize: 13, color: "#888", marginTop: 4, fontFamily: CD.fontDisplay, letterSpacing: "0.08em", textTransform: "uppercase" }}>Analytics</div>
        </div>
        <form onSubmit={submit}>
          {["username","password"].map(f => (
            <div key={f} style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>
                {f === "username" ? "Benutzername" : "Passwort"}
              </label>
              <input
                type={f === "password" ? "password" : "text"}
                value={form[f]} onChange={e => setForm({...form, [f]: e.target.value})}
                style={{ width: "100%", padding: "10px 14px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14, boxSizing: "border-box", outline: "none" }}
                required
              />
            </div>
          ))}
          {error && <div style={{ background: "#FFE8E8", color: "#c0392b", padding: "10px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16 }}>{error}</div>}
          <button type="submit" disabled={loading} style={{
            width: "100%", padding: "12px", background: "#004869", color: "white",
            border: "none", borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: "pointer", marginTop: 8
          }}>{loading ? "Anmelden…" : "Anmelden"}</button>
        </form>
        <div style={{ textAlign: "center", marginTop: 16 }}>
          <a href="?forgot=1" style={{ fontSize: 13, color: "#004869", textDecoration: "none", fontWeight: 600 }}>
            Passwort vergessen?
          </a>
        </div>
      </div>
    </div>
  )
}

function ForgotPasswordPage({ onBack }) {
  const [identifier, setIdentifier] = useState("")
  const [msg, setMsg] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setMsg(null)
    try {
      const res = await fetch(`${API}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Anfrage fehlgeschlagen")
      setMsg({ type: "ok", text: data.message })
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(135deg,#004869,#0a2734)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "white", borderRadius: 10, padding: "48px 40px", width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <h2 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px", color: "#004869" }}>Passwort vergessen</h2>
        <p style={{ fontSize: 13, color: "#888", marginBottom: 24 }}>Benutzername oder E-Mail eingeben — wir senden einen Link (1h gültig).</p>
        <form onSubmit={submit}>
          <input
            type="text"
            value={identifier}
            onChange={e => setIdentifier(e.target.value)}
            placeholder="z. B. ali oder name@kineo.swiss"
            required
            style={{ width: "100%", padding: "10px 14px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14, boxSizing: "border-box", marginBottom: 16 }}
          />
          {msg && <div style={{ background: msg.type === "ok" ? "#E8F8E8" : "#FFE8E8", color: msg.type === "ok" ? "#1a7a1a" : "#c0392b", padding: "10px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16 }}>{msg.text}</div>}
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px", background: "#004869", color: "white", border: "none", borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>
            {loading ? "Senden…" : "Link senden"}
          </button>
        </form>
        <button type="button" onClick={onBack} style={{ width: "100%", marginTop: 12, padding: "10px", background: "transparent", border: "none", color: "#888", cursor: "pointer", fontSize: 13 }}>
          ← Zurück zum Login
        </button>
      </div>
    </div>
  )
}

function ResetPasswordPage({ token, onDone }) {
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [msg, setMsg] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (password !== confirm) { setMsg({ type: "err", text: "Passwörter stimmen nicht überein" }); return }
    if (password.length < 8) { setMsg({ type: "err", text: "Mindestens 8 Zeichen" }); return }
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || "Zurücksetzen fehlgeschlagen")
      setMsg({ type: "ok", text: data.message })
      setTimeout(onDone, 2000)
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(135deg,#004869,#0a2734)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "white", borderRadius: 10, padding: "48px 40px", width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <h2 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 24px", color: "#004869" }}>Neues Passwort</h2>
        <form onSubmit={submit}>
          {[["password", "Neues Passwort"], ["confirm", "Passwort bestätigen"]].map(([k, label]) => (
            <div key={k} style={{ marginBottom: 14 }}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>{label}</label>
              <input type="password" value={k === "password" ? password : confirm}
                onChange={e => (k === "password" ? setPassword : setConfirm)(e.target.value)}
                required minLength={8}
                style={{ width: "100%", padding: "10px 14px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14, boxSizing: "border-box" }} />
            </div>
          ))}
          {msg && <div style={{ background: msg.type === "ok" ? "#E8F8E8" : "#FFE8E8", color: msg.type === "ok" ? "#1a7a1a" : "#c0392b", padding: "10px 14px", borderRadius: 8, fontSize: 13, marginBottom: 16 }}>{msg.text}</div>}
          <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px", background: "#004869", color: "white", border: "none", borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: "pointer" }}>
            {loading ? "Speichern…" : "Passwort speichern"}
          </button>
        </form>
      </div>
    </div>
  )
}

// ── Dashboard Page ─────────────────────────────────────────────────────────
function DashboardPage() {
  const now = new Date()
  const years = useAvailableYears()
  const [year, setYear] = useState(DEFAULT_YEAR)
  const [month, setMonth] = useState(now.getMonth() === 0 ? 12 : now.getMonth()) // previous month
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api(`/api/dashboard/${year}/${month}`).then(setData).catch(console.error).finally(() => setLoading(false))
  }, [year, month])

  const months = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]

  if (loading) return <div style={{ textAlign: "center", padding: 60, color: "#888" }}>Lade Daten…</div>
  if (!data) return null

  const teams = Object.entries(data.team_summary || {})
    .sort(([,a],[,b]) => (b.zeg_b_avg||0) - (a.zeg_b_avg||0))

  const noUmsatz = !(data.total_umsatz > 0)

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: 0, fontSize: 24, color: "#1a1a1a", fontWeight: 800 }}>Dashboard</h1>
          <div style={{ fontSize: 13, color: "#888", marginTop: 4 }}>ZEG-B Übersicht pro Standort und Mitarbeiter</div>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <select value={month} onChange={e => setMonth(+e.target.value)}
            style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14 }}>
            {months.map((m,i) => <option key={i+1} value={i+1}>{m}</option>)}
          </select>
          <YearSelect value={year} onChange={setYear} years={years} />
        </div>
      </div>

      <ImportStatusPanel
        year={year}
        highlightMonth={month}
        onMonthClick={setMonth}
        compact
      />

      {noUmsatz && (
        <div style={{ background: "#FFF3CD", border: "1px solid #FFE69C", borderRadius: 8, padding: "14px 18px", marginBottom: 20, fontSize: 13, color: "#856404" }}>
          <strong>Kein Umsatz für {data.month_name} {year}.</strong> Bitte unter «Daten eingeben» die CSV für diesen Monat hochladen.
          Abwesenheiten-Excel allein reicht nicht — Umsatz kommt aus dem CSV-Export der Kineo-Software.
        </div>
      )}

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginBottom: 28 }}>
        {[
          { label: "Gesamtumsatz", value: `CHF ${(data.total_umsatz||0).toLocaleString("de-CH")}`, icon: "💰" },
          { label: "FTE Total", value: data.total_fte ? data.total_fte.toFixed(1) : (data.ma_data?.reduce((s,m)=>s+(m.bg_pct||0),0)||0).toFixed(1), icon: "👥" },
          { label: "Monat", value: `${data.month_name} ${year}`, icon: "📅" },
        ].map(card => (
          <div key={card.label} style={{ background: "white", borderRadius: 8, padding: "20px 24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ fontSize: 28 }}>{card.icon}</div>
            <div>
              <div style={{ fontSize: 11, color: "#888", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{card.label}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: "#1a1a1a", marginTop: 2 }}>{card.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Team overview */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(300px,1fr))", gap: 20, marginBottom: 28 }}>
        {teams.map(([team, stats]) => {
          const teamMAs = (data.ma_data||[]).filter(m => m.team === team)
          const isOffice = stats.is_office || team === "Office"
          const c = ZEG_COLORS[stats.color || "gray"]
          return (
            <div key={team} style={{ background: "white", borderRadius: 8, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", opacity: isOffice ? 0.92 : 1 }}>
              <div style={{ background: isOffice ? "#F5F5F5" : c.bg, borderBottom: `3px solid ${isOffice ? "#999" : c.border}`, padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 16, fontFamily: "'Roboto Condensed', sans-serif", letterSpacing: "0.05em", color: "#1a1a1a" }}>{team}</div>
                  <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
                    {isOffice ? `FTE ${(stats.fte||0).toFixed(1)} · kein Umsatz` : `CHF ${(stats.umsatz||0).toLocaleString("de-CH")}`}
                  </div>
                </div>
                {!isOffice && <ZEGBadge value={stats.zeg_b_avg} color={stats.color} size="lg" />}
              </div>
              <div style={{ padding: "12px 20px" }}>
                {/* FTE Total */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "2px solid #EEE", marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#004869", textTransform: "uppercase", letterSpacing: 0.5 }}>FTE Total</span>
                  <span style={{ fontSize: 14, fontWeight: 800, color: "#004869" }}>
                    {teamMAs.reduce((s, ma) => s + (ma.bg_pct||0), 0).toFixed(1)}
                  </span>
                </div>
                {/* MA rows: FTE% + Name + ZEG */}
                {teamMAs.map(ma => (
                  <div key={`${ma.name}-${ma.team}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid #F5F5F5" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#888", minWidth: 30 }}>{(ma.bg_pct*100).toFixed(0)}%</span>
                      <span style={{ fontSize: 12, color: "#333" }}>{ma.display_name}</span>
                    </div>
                    {ma.is_office
                      ? <span style={{ fontSize: 10, color: "#999" }}>Office</span>
                      : <ZEGBadge value={ma.zeg_b} color={ma.color} />}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Upload / Input Page ────────────────────────────────────────────────────
function UploadPage() {
  const years = useAvailableYears()
  const [year, setYear] = useState(DEFAULT_YEAR)
  const [month, setMonth] = useState(DEFAULT_MONTH)
  const [step, setStep] = useState(1)
  const [csvFile, setCsvFile] = useState(null)
  const [csvPreview, setCsvPreview] = useState(null)
  const [abFile, setAbFile] = useState(null)
  const [abPreview, setAbPreview] = useState(null)
  const [mitgliederFile, setMitgliederFile] = useState(null)
  const [mitgliederCount, setMitgliederCount] = useState("")
  const [importedMAs, setImportedMAs] = useState(() => new Set())
  const [maList, setMaList] = useState([])
  const [inputs, setInputs] = useState({})
  const inputsFetchRef = useRef(0)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const [statusKey, setStatusKey] = useState(0)
  const months = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]

  useEffect(() => {
    api(`/api/ma?year=${year}&month=${month}`).then(setMaList).catch(e => setMsg({ type: "err", text: e.message }))
  }, [year, month])
  useEffect(() => {
    const fetchId = ++inputsFetchRef.current
    setImportedMAs(new Set())
    api(`/api/inputs/${year}/${month}`).then(data => {
      if (fetchId === inputsFetchRef.current) setInputs(data)
    }).catch(e => setMsg({ type: "err", text: e.message }))
  }, [year, month])

  const uploadCSV = async () => {
    if (!csvFile) return
    setSaving(true); setMsg(null)
    const fd = new FormData()
    fd.append("file", csvFile)
    fd.append("year", year)
    fd.append("month", month)
    const token = localStorage.getItem("token")
    const res = await fetch(`${API}/api/upload-csv`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd
    })
    const data = await res.json()
    if (res.ok) {
      setCsvPreview(data.data)
      const warn = data.warnings?.length ? ` ${data.warnings.join(" ")}` : ""
      setMsg({ type: data.warnings?.length ? "warn" : "ok", text: data.message + warn })
      setStatusKey(k => k + 1)
      setStep(2)
    }
    else { setMsg({ type: "err", text: data.detail }) }
    setSaving(false)
  }

  const uploadAbwesenheiten = async () => {
    if (!abFile) return
    setSaving(true); setMsg(null)
    const fd = new FormData()
    fd.append("file", abFile)
    fd.append("year", year)
    fd.append("month", month)
    fd.append("all_months", "true")
    const token = localStorage.getItem("token")
    const res = await fetch(`${API}/api/upload-abwesenheiten`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd
    })
    const data = await res.json()
    if (res.ok) {
      setAbPreview(data)
      const imported = new Set(Object.keys(data.inputs || data.data || {}))
      setImportedMAs(imported)
      setInputs(prev => {
        const next = { ...prev }
        for (const [maName, vals] of Object.entries(data.inputs || data.data || {})) {
          next[maName] = { ...(next[maName] || {}), ...vals }
        }
        return next
      })
      setStep(2)
      const warn = data.unmatched?.length
        ? ` Nicht zugeordnet: ${data.unmatched.join(", ")}`
        : ""
      setMsg({
        type: data.unmatched?.length ? "warn" : "ok",
        text: (data.message || "Importiert") + warn + " — Felder unten sind vorausgefüllt.",
      })
      setStatusKey(k => k + 1)
    } else {
      setMsg({ type: "err", text: data.detail || "Import fehlgeschlagen" })
    }
    setSaving(false)
  }

  const uploadMitgliederCsv = async () => {
    if (!mitgliederFile) return
    setSaving(true); setMsg(null)
    const fd = new FormData()
    fd.append("file", mitgliederFile)
    fd.append("year", String(year))
    fd.append("ma_name", "Ilaria.F")
    const token = localStorage.getItem("token")
    const res = await fetch(`${API}/api/mitglieder/upload-csv`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd,
    })
    const data = await res.json().catch(() => ({}))
    if (res.ok) setMsg({ type: "ok", text: data.message || "Mitglieder importiert" })
    else setMsg({ type: "err", text: data.detail || "Import fehlgeschlagen" })
    setSaving(false)
  }

  const saveMitgliederManual = async () => {
    const n = parseFloat(String(mitgliederCount).replace(",", "."))
    if (!Number.isFinite(n)) {
      setMsg({ type: "err", text: "Bitte gültige Mitgliederzahl eingeben" })
      return
    }
    setSaving(true); setMsg(null)
    try {
      const res = await api("/api/mitglieder", {
        method: "POST",
        body: JSON.stringify([{ ma_name: "Ilaria.F", year, month, count: n }]),
      })
      setMsg({ type: "ok", text: res.message || "Mitgliederzahl gespeichert" })
      setMitgliederCount("")
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const saveInputs = async () => {
    setSaving(true); setMsg(null)
    const payload = maList.map(ma => ({
      ma_name: ma.name, year, month,
      ferien_t: +((inputs[ma.name]?.ferien_t) || 0),
      kurs_h: +((inputs[ma.name]?.kurs_h) || 0),
      workshop_h: +((inputs[ma.name]?.workshop_h) || 0),
      marketing_h: +((inputs[ma.name]?.marketing_h) || 0),
      laufanalyse_h: +((inputs[ma.name]?.laufanalyse_h) || 0),
      krank_t: +((inputs[ma.name]?.krank_t) || 0),
      notes: inputs[ma.name]?.notes || null,
    }))
    try {
      await api("/api/inputs", { method: "POST", body: JSON.stringify(payload) })
      setMsg({ type: "ok", text: "Alle Inputs gespeichert ✓" })
      setStatusKey(k => k + 1)
    } catch (e) { setMsg({ type: "err", text: e.message }) }
    setSaving(false)
  }

  const inputField = (maName, field, label, stepVal = "0.5", highlight = false) => {
    const raw = inputs[maName]?.[field]
    const val = raw === undefined || raw === null || raw === "" ? "" : raw
    return (
      <input
        type="number" min="0" step={stepVal} value={val}
        onChange={e => setInputs(prev => ({
          ...prev,
          [maName]: { ...(prev[maName] || {}), [field]: e.target.value }
        }))}
        style={{
          width: "100%", padding: "5px 8px",
          border: highlight ? "1.5px solid #1a7a1a" : "1px solid #DDD",
          borderRadius: 6, fontSize: 12, textAlign: "center",
          background: highlight ? "#E8F8E8" : "white",
        }}
        placeholder="0"
      />
    )
  }

  return (
    <div>
      <h1 style={{ margin: "0 0 8px", fontSize: 26, fontWeight: 700, fontFamily: "'Roboto Condensed', sans-serif", letterSpacing: "0.03em" }}>Daten eingeben</h1>
      <div style={{ color: "#888", marginBottom: 28, fontSize: 13 }}>CSV-Umsatz + Abwesenheiten-Excel + Tätigkeiten erfassen</div>

      <ImportStatusPanel
        year={year}
        highlightMonth={month}
        onMonthClick={m => { setMonth(m); setStep(1) }}
        reloadKey={statusKey}
      />

      {/* Month/Year selector */}
      <div style={{ background: "white", borderRadius: 8, padding: "20px 24px", marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", display: "flex", gap: 16, alignItems: "center" }}>
        <label style={{ fontWeight: 600, fontSize: 13 }}>Jahr:</label>
        <YearSelect value={year} onChange={setYear} years={years} style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8 }} />
        <label style={{ fontWeight: 600, fontSize: 13 }}>Monat:</label>
        <select value={month} onChange={e => setMonth(+e.target.value)} style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8 }}>
          {months.map((m,i) => <option key={i+1} value={i+1}>{m} {year}</option>)}
        </select>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button onClick={() => setStep(1)} style={{ padding: "8px 16px", background: step===1?"#004869":"#F0F0F0", color: step===1?"white":"#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>1. CSV Upload</button>
          <button onClick={() => setStep(2)} style={{ padding: "8px 16px", background: step===2?"#004869":"#F0F0F0", color: step===2?"white":"#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>2. Tätigkeiten</button>
        </div>
      </div>

      {msg && (
        <div style={{ background: msg.type==="ok"?"#E8F8E8":msg.type==="warn"?"#FFF3CD":"#FFE8E8", color: msg.type==="ok"?"#1a7a1a":msg.type==="warn"?"#856404":"#c0392b", padding: "12px 16px", borderRadius: 8, marginBottom: 16, fontSize: 13 }}>
          {msg.text}
        </div>
      )}

      {/* Step 1: CSV Upload */}
      {step === 1 && (
        <div style={{ background: "white", borderRadius: 8, padding: "32px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px", color: "#004869" }}>CSV aus Software hochladen</h3>
          <p style={{ margin: "0 0 20px", fontSize: 12, color: "#666", lineHeight: 1.5 }}>
            Pivot-CSV mit Spalten «Jan 2026», «Feb 2026» usw.: alle Monate mit Daten werden automatisch importiert.
            Monat oben dient nur zur Vorschau.
          </p>
          <div style={{ border: "2px dashed #DDD", borderRadius: 8, padding: "40px", textAlign: "center", marginBottom: 20, background: "#FAFAFA" }}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); setCsvFile(e.dataTransfer.files[0]) }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>📄</div>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>CSV-Datei hierher ziehen</div>
            <div style={{ color: "#888", fontSize: 13, marginBottom: 16 }}>Oder:</div>
            <input type="file" accept=".csv" onChange={e => setCsvFile(e.target.files[0])} style={{ display: "none" }} id="csv-input" />
            <label htmlFor="csv-input" style={{ background: "#004869", color: "white", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontSize: 14, fontWeight: 600 }}>Datei auswählen</label>
          </div>
          {csvFile && (
            <div style={{ background: "#E8F8E8", padding: "12px 16px", borderRadius: 8, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{csvFile.name}</div>
                <div style={{ fontSize: 12, color: "#888" }}>{(csvFile.size/1024).toFixed(1)} KB</div>
              </div>
              <button onClick={uploadCSV} disabled={saving} style={{ background: "#004869", color: "white", border: "none", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontWeight: 700 }}>
                {saving ? "Lade hoch…" : "Hochladen & Importieren"}
              </button>
            </div>
          )}
          {csvPreview && (
            <div>
              <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", color: "#004869", margin: "0 0 12px" }}>Importierte Umsätze:</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 8 }}>
                {Object.entries(csvPreview).map(([name, amt]) => (
                  <div key={name} style={{ background: "#F5F5F5", borderRadius: 8, padding: "8px 12px", display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
                    <span style={{ fontSize: 13, color: "#004869" }}>CHF {(+amt).toLocaleString("de-CH")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ marginTop: 28, paddingTop: 24, borderTop: "1px solid #EEE" }}>
            <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px", color: "#004869" }}>Mitgliederzahlen (Ilaria / CC)</h3>
            <p style={{ margin: "0 0 14px", fontSize: 12, color: "#666" }}>
              CSV mit Spalten <em>month,count</em> (optional ma_name) — oder manuell für den Monat oben.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", marginBottom: 12 }}>
              <input type="file" accept=".csv,.txt" onChange={e => setMitgliederFile(e.target.files?.[0] || null)} />
              <button type="button" onClick={uploadMitgliederCsv} disabled={saving || !mitgliederFile}
                style={{ background: "#004869", color: "white", border: "none", padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 13 }}>
                CSV importieren
              </button>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
              <span style={{ fontSize: 13, color: "#555" }}>{months[month - 1]} {year}:</span>
              <input value={mitgliederCount} onChange={e => setMitgliederCount(e.target.value)} placeholder="Anzahl"
                style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, width: 100, fontSize: 13 }} />
              <button type="button" onClick={saveMitgliederManual} disabled={saving}
                style={{ background: "white", color: "#004869", border: "1px solid #004869", padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 13 }}>
                Speichern
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Tätigkeiten */}
      {step === 2 && (
        <div style={{ background: "white", borderRadius: 8, padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ background: "#F8F9FA", border: "1px solid #E8E8E8", borderRadius: 8, padding: "16px 20px", marginBottom: 20 }}>
            <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px", color: "#004869", fontSize: 15 }}>Abwesenheiten-Excel importieren</h4>
            <p style={{ margin: "0 0 12px", fontSize: 12, color: "#666", lineHeight: 1.5 }}>
              HR-Export mit Spalten <em>Mitarbeitende, Abwesenheitsart, Von, Bis, Halber Tag</em>.
              Die ganze Jahresliste auf einmal hochladen — Ferien & Krank werden automatisch pro Monat verteilt.
              Nur <em>Urlaub</em> (inkl. unbezahlt) → Ferien (T); <em>Krankheit</em> → Krank (T).
              Gleitzeit, Umzug, Hochzeit usw. werden ignoriert.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
              <input type="file" accept=".xlsx,.xlsm" onChange={e => { setAbFile(e.target.files[0]); setAbPreview(null) }} style={{ fontSize: 12 }} />
              {abFile && (
                <button onClick={uploadAbwesenheiten} disabled={saving} style={{ background: "#004869", color: "white", border: "none", padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 13 }}>
                  {saving ? "Importiere…" : "Ferien & Krank importieren"}
                </button>
              )}
            </div>
            {abPreview?.details?.filter(d => d.month === month).length > 0 && (
              <div style={{ marginTop: 14, maxHeight: 160, overflowY: "auto", fontSize: 11, color: "#555" }}>
                {abPreview.details.filter(d => d.month === month).slice(0, 12).map((d, i) => (
                  <div key={i} style={{ padding: "3px 0", borderBottom: "1px solid #EEE" }}>
                    <strong>{d.excel_name}</strong> → {d.ma_name}: {d.art},{" "}
                    {d.days} T{d.halber_tag && d.weekdays ? ` (${d.weekdays} AT × ½)` : ""} ({d.von} – {d.bis})
                  </div>
                ))}
                {abPreview.details.filter(d => d.month === month).length > 12 && (
                  <div style={{ paddingTop: 6, color: "#888" }}>… und {abPreview.details.filter(d => d.month === month).length - 12} weitere Einträge</div>
                )}
                {abPreview.months_imported?.some(m => m !== month) && (
                  <div style={{ paddingTop: 8, color: "#888", fontSize: 10 }}>
                    Weitere Monate wurden mitimportiert — nur {months[month - 1]} {year} in der Vorschau.
                  </div>
                )}
              </div>
            )}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: 0, color: "#004869" }}>Tätigkeiten — {months[month-1]} {year}</h3>
            <button onClick={saveInputs} disabled={saving} style={{ background: "#004869", color: "white", border: "none", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 14 }}>
              {saving ? "Speichern…" : "Alle speichern"}
            </button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#004869", color: "white" }}>
                  {["Mitarbeiter","Team","Ferien (T)","Kurse (h)","Workshop (h)","Marketing (h)","Laufanalyse (h)","Krank (T)"].map(h => (
                    <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 700, whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {maList.map((ma, i) => {
                  const imported = importedMAs.has(ma.name)
                  return (
                  <tr key={ma.name} style={{ background: i%2===0?"white":"#F8F9FA", opacity: ma.austritt ? 0.85 : 1 }}>
                    <td style={{ padding: "8px 12px", fontWeight: 600, whiteSpace: "nowrap" }}>
                      {ma.display_name}
                      {ma.austritt && <span style={{ marginLeft: 6, fontSize: 10, color: "#999" }}>(ausgetreten)</span>}
                    </td>
                    <td style={{ padding: "8px 12px", color: "#888", fontSize: 11 }}>{ma.team}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"ferien_t","", "0.5", imported)}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"kurs_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"workshop_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"marketing_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"laufanalyse_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"krank_t","", "0.5", imported)}</td>
                  </tr>
                )})}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── YTD Overview Page ──────────────────────────────────────────────────────
const OUTLIER_PP = 0.15 // ±15 Prozentpunkte vs. eigener Ø ZEG-B

function formatPct(value) {
  return value != null ? `${(value * 100).toFixed(1)}%` : "—"
}

function formatChf(value) {
  if (value == null || value === 0) return "—"
  return `CHF ${Number(value).toLocaleString("de-CH")}`
}

function formatTage(value) {
  if (value == null) return "—"
  return Number(value).toLocaleString("de-CH", { maximumFractionDigits: 1 })
}

function isZegOutlier(zeg, avgZeg) {
  if (zeg == null || avgZeg == null) return false
  return Math.abs(zeg - avgZeg) >= OUTLIER_PP
}

function MonthCellTooltip({ monthLabel, cell, avgZeg, anchorRect }) {
  const zeg = cell?.zeg_b
  const delta = (zeg != null && avgZeg != null) ? zeg - avgZeg : null
  const rows = [
    ["Umsatz", formatChf(cell?.umsatz)],
    ["ZEG-B", formatPct(zeg)],
    ["Prod-Tage (B)", formatTage(cell?.prod_b)],
    ["Soll-Tage", formatTage(cell?.soll_tage)],
  ]
  if (cell?.ferien_t) rows.push(["Ferien", `${formatTage(cell.ferien_t)} T`])
  if (cell?.krank_t) rows.push(["Krank", `${formatTage(cell.krank_t)} T`])
  if (delta != null) {
    const sign = delta >= 0 ? "+" : ""
    rows.push(["vs. eigener Ø", `${sign}${(delta * 100).toFixed(1)} pp`])
  }

  const tipW = 180
  const tipH = 28 + rows.length * 18
  const gap = 8
  let left = (anchorRect?.left || 0) + (anchorRect?.width || 0) / 2 - tipW / 2
  left = Math.max(8, Math.min(left, window.innerWidth - tipW - 8))
  const preferAbove = (anchorRect?.top || 0) > tipH + gap + 8
  const top = preferAbove
    ? (anchorRect?.top || 0) - tipH - gap
    : (anchorRect?.bottom || 0) + gap

  return (
    <div style={{
      position: "fixed", top, left, width: tipW,
      background: "#1a2a32", color: "white", borderRadius: 8, padding: "10px 12px",
      fontSize: 11, lineHeight: 1.45, zIndex: 9999,
      boxShadow: "0 6px 18px rgba(0,0,0,0.22)", pointerEvents: "none", textAlign: "left",
      boxSizing: "border-box",
    }}>
      <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 12 }}>{monthLabel}</div>
      {rows.map(([label, value]) => (
        <div key={label} style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
          <span style={{ opacity: 0.72 }}>{label}</span>
          <span style={{ fontWeight: 600 }}>{value}</span>
        </div>
      ))}
    </div>
  )
}

function OverviewMonthCell({ cell, monthLabel, viewMode, avgZeg }) {
  const [hover, setHover] = useState(false)
  const [anchorRect, setAnchorRect] = useState(null)
  const ref = useRef(null)

  if (!cell) return <span style={{ color: "#DDD", fontSize: 11 }}>—</span>

  const outlier = viewMode === "zeg" && isZegOutlier(cell.zeg_b, avgZeg)
  const content = viewMode === "zeg"
    ? <ZEGBadge value={cell.zeg_b} color={cell.color} />
    : (
      <span style={{
        display: "inline-block", minWidth: 56, padding: "4px 6px", fontSize: 11, fontWeight: 600,
        color: "#004869", background: "#F0F4F6", borderRadius: 4, textAlign: "center",
      }}>
        {(cell.umsatz || 0) ? cell.umsatz.toLocaleString("de-CH") : "—"}
      </span>
    )

  const showTip = () => {
    if (ref.current) setAnchorRect(ref.current.getBoundingClientRect())
    setHover(true)
  }

  return (
    <span
      ref={ref}
      onMouseEnter={showTip}
      onMouseLeave={() => setHover(false)}
      style={{
        position: "relative", display: "inline-flex", alignItems: "center", justifyContent: "center",
        cursor: "default",
        outline: outlier ? "2px solid #004869" : undefined,
        outlineOffset: outlier ? 2 : undefined,
        borderRadius: 6,
      }}
    >
      {content}
      {outlier && (
        <span style={{
          position: "absolute", top: -3, right: -3, width: 7, height: 7, borderRadius: "50%",
          background: "#004869", border: "1.5px solid white",
        }} />
      )}
      {hover && anchorRect && createPortal(
        <MonthCellTooltip monthLabel={monthLabel} cell={cell} avgZeg={avgZeg} anchorRect={anchorRect} />,
        document.body
      )}
    </span>
  )
}

function UmsatzCell({ value }) {
  if (!value) return <span style={{ color: "#DDD", fontSize: 11 }}>—</span>
  return (
    <span style={{
      display: "inline-block", minWidth: 56, padding: "4px 6px", fontSize: 11, fontWeight: 600,
      color: "#004869", background: "#F0F4F6", borderRadius: 4, textAlign: "center",
    }}>
      {value.toLocaleString("de-CH")}
    </span>
  )
}

function maStandorteList(ma) {
  return ma.standorte?.length ? ma.standorte : (ma.team ? [ma.team] : [])
}

function maAvgMonthlyUmsatz(ma) {
  const vals = (ma.monthly || []).filter(Boolean).map(c => c.umsatz || 0).filter(u => u > 0)
  return vals.length ? Math.round(vals.reduce((s, v) => s + v, 0) / vals.length) : null
}

function OverviewPage() {
  const years = useAvailableYears()
  const [year, setYear] = useState(DEFAULT_YEAR)
  const [reloadKey, setReloadKey] = useState(0)
  const { data, loading, error } = useYtd(year, reloadKey)
  const [filterTeam, setFilterTeam] = useState("Alle")
  const [filterRole, setFilterRole] = useState("Alle")
  const [filterFk, setFilterFk] = useState("Alle")
  const [hideExMa, setHideExMa] = useState(true)
  const [viewMode, setViewMode] = useState("zeg")
  const [sortKey, setSortKey] = useState("name")
  const [sortDir, setSortDir] = useState("asc")
  const months = ["Jan","Feb","Mrz","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

  if (loading) return <div style={{ textAlign: "center", padding: 60, color: "#888" }}>Lade Jahresübersicht {year}…</div>
  if (error) return (
    <div style={{ textAlign: "center", padding: 60 }}>
      <div style={{ color: "#c0392b", marginBottom: 12 }}>{error}</div>
      <button onClick={() => setReloadKey(k => k + 1)} style={{ padding: "8px 16px", borderRadius: 6, border: "1px solid #DDD", cursor: "pointer" }}>Erneut laden</button>
    </div>
  )
  if (!data || data.year !== year) return <div style={{ textAlign: "center", padding: 60, color: "#888" }}>Lade Jahresübersicht {year}…</div>

  const throughMonth = data.reporting_through_month ?? 12
  const visibleMonthCount = throughMonth > 0 ? throughMonth : 12
  const visibleMonths = months.slice(0, visibleMonthCount)

  const allMA = data.ma_data || []
  const standortSet = new Set()
  allMA.forEach(m => maStandorteList(m).forEach(s => { if (s) standortSet.add(s) }))
  const teams = ["Alle", ...Array.from(standortSet).sort()]
  const roles = ["Alle", ...Array.from(new Set(allMA.map(m => m.role).filter(Boolean))).sort()]
  const fkOptions = [{ username: "Alle", label: "Alle" }, ...(data.fk_filter_options || []).map(f => ({
    username: f.username,
    label: f.full_name || f.username,
  }))]

  let rows = allMA.filter(m =>
    (filterTeam === "Alle" || maStandorteList(m).includes(filterTeam)) &&
    (filterRole === "Alle" || m.role === filterRole) &&
    (filterFk === "Alle" || m.fk_username === filterFk) &&
    (!hideExMa || m.is_active !== false)
  )

  const dir = sortDir === "asc" ? 1 : -1
  rows = [...rows].sort((a, b) => {
    if (sortKey === "name") return dir * (a.display_name||"").localeCompare(b.display_name||"")
    if (sortKey === "team") return dir * maStandorteList(a).join(" · ").localeCompare(maStandorteList(b).join(" · "))
    if (sortKey === "avg") {
      if (viewMode === "umsatz") return dir * ((maAvgMonthlyUmsatz(a) || 0) - (maAvgMonthlyUmsatz(b) || 0))
      return dir * ((a.avg_zeg_b || 0) - (b.avg_zeg_b || 0))
    }
    if (sortKey.startsWith("m")) {
      const mi = parseInt(sortKey.slice(1), 10)
      if (viewMode === "umsatz") {
        const av = (a.monthly || [])[mi]?.umsatz ?? -1
        const bv = (b.monthly || [])[mi]?.umsatz ?? -1
        return dir * (av - bv)
      }
      const av = (a.monthly||[])[mi]?.zeg_b ?? -1
      const bv = (b.monthly||[])[mi]?.zeg_b ?? -1
      return dir * (av - bv)
    }
    return 0
  })

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc")
    else { setSortKey(key); setSortDir("asc") }
  }

  const SortArrow = ({ k }) => sortKey === k ? <span style={{ marginLeft: 4 }}>{sortDir === "asc" ? "▲" : "▼"}</span> : null

  const filtered = filterTeam !== "Alle" || filterRole !== "Alle" || filterFk !== "Alle" || hideExMa
  const displayMonthlyTotals = filtered
    ? Array.from({ length: 12 }, (_, mi) =>
        rows.reduce((s, ma) => {
          const cell = (ma.monthly || [])[mi]
          if (!cell) return s
          return s + (cell.umsatz || 0)
        }, 0)
      )
    : (data.monthly_totals || [])
  const displayYearTotal = filtered
    ? rows.reduce((s, ma) => s + (ma.total_umsatz || 0), 0)
    : (data.year_total_umsatz ?? (data.monthly_totals || []).reduce((a, b) => a + b, 0))

  const selectStyle = { padding: "6px 10px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12, background: "white", color: "#333" }

  const viewToggleBtn = (mode, label) => ({
    padding: "6px 12px", border: "1px solid #DDD", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
    background: viewMode === mode ? "#004869" : "white",
    color: viewMode === mode ? "white" : "#555",
  })

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: "0 0 8px", fontSize: 26, fontWeight: 700, fontFamily: "'Roboto Condensed', sans-serif", letterSpacing: "0.03em" }}>Jahresübersicht {year}</h1>
          <div style={{ color: "#888", fontSize: 13 }}>
            {viewMode === "zeg" ? "ZEG-B pro Monat und Mitarbeiter" : "Umsatz pro Monat und Mitarbeiter (CHF)"}
            {data.reporting_through_label && throughMonth < 12 && (
              <span> · Stand {data.reporting_through_label}</span>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button" style={viewToggleBtn("zeg", "ZEG-B %")} onClick={() => setViewMode("zeg")}>ZEG-B %</button>
          <button type="button" style={viewToggleBtn("umsatz", "Umsatz CHF")} onClick={() => setViewMode("umsatz")}>Umsatz CHF</button>
          <YearSelect value={year} onChange={setYear} years={years} />
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 18, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Standort:
          <select value={filterTeam} onChange={e => setFilterTeam(e.target.value)} style={selectStyle}>
            {teams.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Führungsperson:
          <select value={filterFk} onChange={e => setFilterFk(e.target.value)} style={selectStyle}>
            {fkOptions.map(f => <option key={f.username} value={f.username}>{f.label}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Rolle:
          <select value={filterRole} onChange={e => setFilterRole(e.target.value)} style={selectStyle}>
            {roles.map(r => <option key={r} value={r}>{r === "Alle" ? "Alle" : formatRoleLabel(r)}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input type="checkbox" checked={hideExMa} onChange={e => setHideExMa(e.target.checked)} />
          Ex-MA ausblenden
        </label>
        {(filterTeam !== "Alle" || filterRole !== "Alle" || filterFk !== "Alle" || hideExMa) && (
          <button onClick={() => { setFilterTeam("Alle"); setFilterRole("Alle"); setFilterFk("Alle"); setHideExMa(true) }}
            style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #DDD", background: "white", fontSize: 12, color: "#888", cursor: "pointer" }}>
            Filter zurücksetzen
          </button>
        )}
        <div style={{ marginLeft: "auto", fontSize: 12, color: "#888" }}>{rows.length} Mitarbeiter</div>
        <div style={{ fontSize: 13, fontWeight: 700, color: "#004869" }}>
          Jahresumsatz: CHF {displayYearTotal.toLocaleString("de-CH")}
          {filtered && <span style={{ fontWeight: 400, color: "#888" }}> (gefiltert)</span>}
        </div>
      </div>

      <div style={{ background: "white", borderRadius: 8, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#004869", color: "white" }}>
                <th onClick={() => toggleSort("name")} style={{ padding: "12px 16px", textAlign: "left", position: "sticky", left: 0, background: "#004869", zIndex: 2, minWidth: 140, cursor: "pointer", userSelect: "none" }}>
                  Mitarbeiter<SortArrow k="name" />
                </th>
                <th onClick={() => toggleSort("team")} style={{ padding: "12px 8px", textAlign: "center", minWidth: 90, cursor: "pointer", userSelect: "none" }}>
                  Standorte<SortArrow k="team" />
                </th>
                {visibleMonths.map((m, mi) => (
                  <th key={m} onClick={() => toggleSort("m"+mi)} style={{ padding: "12px 8px", textAlign: "center", minWidth: 68, cursor: "pointer", userSelect: "none" }}>
                    {m}<SortArrow k={"m"+mi} />
                  </th>
                ))}
                <th onClick={() => toggleSort("avg")} style={{ padding: "12px 12px", textAlign: "center", minWidth: 80, borderLeft: "2px solid rgba(255,255,255,0.3)", cursor: "pointer", userSelect: "none" }}>
                  {viewMode === "zeg" ? "Ø ZEG-B" : "Ø CHF"}<SortArrow k="avg" />
                </th>
                <th style={{ padding: "12px 12px", textAlign: "right", minWidth: 100, borderLeft: "2px solid rgba(255,255,255,0.3)" }}>
                  Jahr CHF
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((ma, i) => (
                <tr key={ma.name} style={{ background: i%2===0?"white":"#F8F9FA", opacity: ma.is_active === false ? 0.65 : 1 }}>
                  <td style={{ padding: "8px 16px", fontWeight: 600, position: "sticky", left: 0, background: i%2===0?"white":"#F8F9FA", zIndex: 1, borderRight: "1px solid #EEE" }}>
                    {ma.display_name}
                    {ma.is_active === false && <span style={{ marginLeft: 6, fontSize: 10, color: "#999" }}>(ausgetreten)</span>}
                  </td>
                  <td style={{ padding: "8px 8px", textAlign: "center", color: "#888", fontSize: 10, lineHeight: 1.35 }}>
                    {maStandorteList(ma).join(" · ") || "—"}
                  </td>
                  {visibleMonths.map((monthLabel, mi) => {
                    const m = (ma.monthly || [])[mi]
                    return (
                    <td key={mi} style={{ padding: "6px 4px", textAlign: "center" }}>
                      <OverviewMonthCell
                        cell={m}
                        monthLabel={monthLabel}
                        viewMode={viewMode}
                        avgZeg={ma.avg_zeg_b}
                      />
                    </td>
                    )
                  })}
                  <td style={{ padding: "6px 8px", textAlign: "center", borderLeft: "2px solid #EEE" }}>
                    {viewMode === "zeg"
                      ? <ZEGBadge value={ma.avg_zeg_b} color={ma.color} size="sm" />
                      : <UmsatzCell value={maAvgMonthlyUmsatz(ma)} />}
                  </td>
                  <td style={{ padding: "8px 12px", textAlign: "right", fontWeight: 700, borderLeft: "2px solid #EEE", fontSize: 11 }}>
                    {(ma.total_umsatz||0).toLocaleString("de-CH")}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={visibleMonthCount + 4} style={{ padding: 24, textAlign: "center", color: "#888" }}>Keine Mitarbeiter für diese Filterauswahl</td></tr>
              )}
              {rows.length > 0 && (
                <tr style={{ background: "#F0F4F6", fontWeight: 700 }}>
                  <td style={{ padding: "10px 16px", position: "sticky", left: 0, background: "#F0F4F6", borderRight: "1px solid #EEE" }} colSpan={2}>
                    Monatssumme (≙ Dashboard)
                  </td>
                  {(displayMonthlyTotals||[]).slice(0, visibleMonthCount).map((t, mi) => (
                    <td key={mi} style={{ padding: "8px 4px", textAlign: "center", fontSize: 10 }}>
                      {t ? t.toLocaleString("de-CH") : "—"}
                    </td>
                  ))}
                  <td style={{ borderLeft: "2px solid #DDD" }} />
                  <td style={{ padding: "8px 12px", textAlign: "right", borderLeft: "2px solid #DDD" }}>
                    {displayYearTotal.toLocaleString("de-CH")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {viewMode === "zeg" && (
      <div style={{ marginTop: 16, display: "flex", gap: 16, fontSize: 12, color: "#888", flexWrap: "wrap", alignItems: "center" }}>
        {[["green","≥ 100%"],["amber","85–99%"],["red","< 85%"]].map(([c,l]) => (
          <div key={c} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 12, height: 12, borderRadius: "50%", background: ZEG_COLORS[c].border }}/>
            {l}
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{
            width: 22, height: 14, borderRadius: 4, border: "2px solid #004869", position: "relative", display: "inline-block",
          }}>
            <span style={{
              position: "absolute", top: -3, right: -3, width: 6, height: 6, borderRadius: "50%",
              background: "#004869", border: "1px solid white",
            }} />
          </span>
          Ausreisser (±15 pp vs. eigener Ø) · Hover zeigt Umsatz & Prod-Tage
        </div>
      </div>
      )}
      {viewMode === "umsatz" && (
        <div style={{ marginTop: 16, fontSize: 12, color: "#888" }}>
          Hover auf Monatszellen zeigt ZEG-B, Soll- und Prod-Tage.
        </div>
      )}
    </div>
  )
}

// ── Exports Page ───────────────────────────────────────────────────────────
function ExportsPage() {
  const auth = useAuth()
  const years = useAvailableYears()
  const [year, setYear] = useState(DEFAULT_YEAR)
  const [loading, setLoading] = useState({})
  const [maList, setMaList] = useState([])
  const [bilat_month, setBilatMonth] = useState(DEFAULT_MONTH)
  const token = localStorage.getItem("token")
  const months = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]

  useEffect(() => { api("/api/ma").then(setMaList).catch(console.error) }, [])

  const download = async (url, filename, key) => {
    setLoading(l => ({...l,[key]:true}))
    try {
      const res = await fetch(`${API}${url}`, { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) throw new Error(await res.text())
      const blob = await res.blob()
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = filename; a.click()
    } catch(e) { alert("Fehler: " + e.message) }
    setLoading(l => ({...l,[key]:false}))
  }

  const isFullAccess = hasFullAccess(auth.user?.role)

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ margin: "0 0 8px", fontSize: 26, fontWeight: 700, fontFamily: "'Roboto Condensed', sans-serif", letterSpacing: "0.03em" }}>Exporte</h1>
          <div style={{ color: "#888", fontSize: 13 }}>CEO, COO & Business Development</div>
        </div>
        <YearSelect value={year} onChange={setYear} years={years} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(380px,1fr))", gap: 20 }}>

        {/* Excel Export */}
        {isFullAccess && (
          <div style={{ background: "white", borderRadius: 8, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <div style={{ fontSize: 36, marginBottom: 16 }}>📊</div>
            <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px" }}>Umsatzanalyse Excel</h3>
            <p style={{ color: "#888", fontSize: 13, marginBottom: 20, lineHeight: 1.5 }}>
              Komplette Jahresübersicht mit allen Monaten, Arbeitstag-Muster, ZEG-A/B/C und MA-Details.
            </p>
            <button onClick={() => download(`/api/export/excel/${year}`,`Kineo_Umsatzanalyse_${year}.xlsx`,"excel")}
              disabled={loading.excel} style={{ background:"#004869",color:"white",border:"none",padding:"12px 24px",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,width:"100%" }}>
              {loading.excel ? "Wird erstellt…" : "Excel herunterladen"}
            </button>
          </div>
        )}

        {/* Bilaterals - alle als ZIP */}
        <div style={{ background: "white", borderRadius: 8, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontSize: 36, marginBottom: 16 }}>📁</div>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px" }}>Alle Bilaterals als ZIP</h3>
          <p style={{ color: "#888", fontSize: 13, marginBottom: 16, lineHeight: 1.5 }}>
            {isFullAccess ? "Alle MA" : "Ihr Team"} — Word-Dokumente mit ZEG-B Daten.
          </p>
          <select value={bilat_month} onChange={e => setBilatMonth(+e.target.value)}
            style={{ width:"100%",padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,marginBottom:12 }}>
            {months.map((m,i) => <option key={i+1} value={i+1}>Stand: {m} {year}</option>)}
          </select>
          <button onClick={() => download(`/api/export/bilats/${year}/${encodeURIComponent(periodForMonth(bilat_month, year))}/${bilat_month}`,`Kineo_Bilats_${months[bilat_month-1]}_${year}.zip`,"bilat_all")}
            disabled={loading.bilat_all} style={{ background:"#004869",color:"white",border:"none",padding:"12px 24px",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,width:"100%" }}>
            {loading.bilat_all ? "Wird erstellt…" : "ZIP herunterladen"}
          </button>
        </div>

        {/* Bilaterals - einzeln */}
        <div style={{ background: "white", borderRadius: 8, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontSize: 36, marginBottom: 16 }}>📝</div>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px" }}>Bilateral einzeln</h3>
          <p style={{ color: "#888", fontSize: 13, marginBottom: 16, lineHeight: 1.5 }}>
            Einzelnes Bilateral für eine/n Mitarbeiter/in herunterladen.
          </p>
          <select value={bilat_month} onChange={e => setBilatMonth(+e.target.value)}
            style={{ width:"100%",padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,marginBottom:8 }}>
            {months.map((m,i) => <option key={i+1} value={i+1}>Stand: {m} {year}</option>)}
          </select>
          <div style={{ maxHeight: 280, overflowY:"auto", border:"1.5px solid #EEE", borderRadius:8, marginBottom:12 }}>
            {maList.map(ma => (
              <div key={ma.name} style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
                padding:"10px 14px", borderBottom:"1px solid #F5F5F5" }}>
                <div>
                  <div style={{ fontSize:13, fontWeight:600 }}>{ma.display_name}</div>
                  <div style={{ fontSize:11, color:"#888" }}>{ma.team} · {(ma.bg_pct*100).toFixed(0)}%</div>
                </div>
                <button
                  onClick={() => download(`/api/export/bilat-single/${year}/${bilat_month}/${ma.name}`,
                    `Bilat_${ma.name.replace(".","_").replace(" ","_")}_HJ1_${year}.docx`,
                    `bilat_${ma.name}`)}
                  disabled={loading[`bilat_${ma.name}`]}
                  style={{ background:"#E4EEF3",color:"#004869",border:"none",padding:"6px 14px",
                    borderRadius:6,cursor:"pointer",fontWeight:600,fontSize:12,whiteSpace:"nowrap" }}>
                  {loading[`bilat_${ma.name}`] ? "…" : "⬇ Word"}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}


// ── Admin Page ─────────────────────────────────────────────────────────────
const STANDORTE = ["Seefeld","Wipkingen","Thalwil","Escher Wyss","Stauffacher","Zollikon","CC","Office"]
const ROLLEN = ["therapeut","teamlead","sl","bd","management"]
const DAYS_DE = ["Mo","Di","Mi","Do","Fr"]

function AdminPage() {
  const years = useAvailableYears()
  const [feiertagYear, setFeiertagYear] = useState(DEFAULT_YEAR)
  const [tab, setTab] = useState("ma")
  const [mas, setMas] = useState([])
  const [feiertage, setFeiertage] = useState([])
  const [editMA, setEditMA] = useState(null)
  const [scheduleMA, setScheduleMA] = useState(null)
  const [scheduleMAMeta, setScheduleMAMeta] = useState(null)
  const [scheduleLoading, setScheduleLoading] = useState(false)
  const [schedule, setSchedule] = useState([])
  const [scheduleValidFrom, setScheduleValidFrom] = useState("")
  const [scheduleVersions, setScheduleVersions] = useState([])
  const [scheduleScope, setScheduleScope] = useState("from")
  const [scheduleEditYM, setScheduleEditYM] = useState("")
  const [msg, setMsg] = useState(null)
  const [newMA, setNewMA] = useState({name:"",display_name:"",team:"Seefeld",role:"therapeut",bg_pct:1.0,eintritt:"",austritt:"",fk_username:""})
  const [showNewMA, setShowNewMA] = useState(false)
  const [newFeiertag, setNewFeiertag] = useState({date_str:"",name:"",faktor:1.0})
  const [teamleads, setTeamleads] = useState([])

  const loadMAs = () => api("/api/admin/ma").then(setMas).catch(console.error)
  const loadTeamleads = () => api("/api/admin/teamleads").then(setTeamleads).catch(console.error)
  const loadFeiertage = () => api(`/api/admin/feiertage/${feiertagYear}`).then(setFeiertage).catch(console.error)

  useEffect(() => { loadMAs(); loadTeamleads() }, [])
  useEffect(() => { if (tab === "feiertage") loadFeiertage() }, [feiertagYear, tab])

  const scheduleDefaultFrom = (ma) => {
    if (ma && !ma.is_active) {
      return ma.eintritt?.slice(0, 7) || "2026-01"
    }
    return `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`
  }

  const loadSchedule = async (name, editYM = "") => {
    const ma = mas.find(m => m.name === name)
    setScheduleMA(name)
    setScheduleMAMeta(ma || null)
    setScheduleLoading(true)
    try {
      const enc = encodeURIComponent(name)
      const url = editYM
        ? `/api/admin/schedule/${enc}?year=${editYM.split("-")[0]}&month=${+editYM.split("-")[1]}`
        : `/api/admin/schedule/${enc}`
      const res = await api(url)
      setSchedule(res.days || res)
      setScheduleValidFrom(res.valid_from || scheduleDefaultFrom(ma))
      setScheduleVersions(res.versions || [])
      setScheduleScope(editYM ? "month" : (res.scope || "from"))
      setScheduleEditYM(editYM)
    } catch (e) {
      setMsg({ type: "err", text: e.message })
      setScheduleMA(null)
      setScheduleMAMeta(null)
    } finally {
      setScheduleLoading(false)
    }
  }

  const saveSchedule = async () => {
    const body = scheduleScope === "month" && scheduleEditYM
      ? {
          scope: "month",
          year: +scheduleEditYM.split("-")[0],
          month: +scheduleEditYM.split("-")[1],
          valid_from: scheduleEditYM,
          days: schedule,
        }
      : { scope: "from", valid_from: scheduleValidFrom, days: schedule }
    try {
      const res = await api(`/api/admin/schedule/${encodeURIComponent(scheduleMA)}`, {
        method: "POST",
        body: JSON.stringify(body),
      })
      setMsg({ type: "ok", text: res.message || "Arbeitstag-Muster gespeichert" })
      await loadSchedule(scheduleMA, scheduleScope === "month" ? scheduleEditYM : "")
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    }
  }

  const toggleMA = async (name) => {
    await api(`/api/admin/ma/${encodeURIComponent(name)}/toggle`, { method: "PATCH" })
    loadMAs()
  }

  const saveMA = async (isNew=false) => {
    const data = isNew ? newMA : editMA
    const method = isNew ? "POST" : "PUT"
    const url = isNew ? "/api/admin/ma" : `/api/admin/ma/${encodeURIComponent(editMA.name)}`
    try {
      await api(url, {method, body:JSON.stringify(data)})
      setMsg({type:"ok",text:"Gespeichert"}); loadMAs()
      isNew ? setShowNewMA(false) : setEditMA(null)
    } catch(e) { setMsg({type:"err",text:e.message}) }
  }

  const saveFeiertage = async () => {
    await api(`/api/admin/feiertage/${feiertagYear}`, {method:"POST", body:JSON.stringify(feiertage)})
    setMsg({type:"ok",text:"Feiertage gespeichert"}); loadFeiertage()
  }

  const addFeiertag = () => {
    if (!newFeiertag.date_str || !newFeiertag.name) return
    setFeiertage([...feiertage, newFeiertag].sort((a,b)=>a.date_str.localeCompare(b.date_str)))
    setNewFeiertag({date_str:"",name:"",faktor:1.0})
  }

  const inp = (style={}) => ({padding:"8px 10px",border:"1.5px solid #DDD",borderRadius:6,fontSize:13,...style})
  const btn = (bg="#004869",color="white") => ({background:bg,color,border:"none",padding:"8px 16px",borderRadius:6,cursor:"pointer",fontWeight:600,fontSize:13})

  const fkSelect = (value, onChange) => (
    <select style={inp({ width: "100%", boxSizing: "border-box" })} value={value || ""} onChange={e => onChange(e.target.value || null)}>
      <option value="">— Keine FK —</option>
      {teamleads.map(t => (
        <option key={t.username} value={t.username}>
          {t.full_name} ({t.team || formatRoleLabel(t.role)})
        </option>
      ))}
    </select>
  )

  const formatStandorte = (ma) => {
    const sites = ma.standorte?.length ? ma.standorte : (ma.team ? [ma.team] : [])
    return sites.length ? sites.join(" · ") : "—"
  }

  const tabs = [["ma","Mitarbeiter", Users],["schedule","Arbeitstag-Muster", Calendar],["feiertage","Feiertage", Calendar]]

  return (
    <div>
      <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 8px",fontSize:24,fontWeight:800}}>Admin</h1>
      <div style={{color:"#888",marginBottom:24,fontSize:13}}>CEO, COO & Business Development</div>

      {msg && <div style={{background:msg.type==="ok"?"#E8F8E8":"#FFE8E8",color:msg.type==="ok"?"#1a7a1a":"#c0392b",padding:"10px 14px",borderRadius:8,marginBottom:16,fontSize:13,display:"flex",justifyContent:"space-between"}}>
        {msg.text}<span style={{cursor:"pointer"}} onClick={()=>setMsg(null)}>✕</span>
      </div>}

      {/* Tabs */}
      <div style={{display:"flex",gap:4,marginBottom:24,background:"white",padding:4,borderRadius:10,boxShadow:"0 2px 8px rgba(0,0,0,0.06)",width:"fit-content"}}>
        {tabs.map(([id,label,TabIcon]) => (
          <button key={id} onClick={()=>setTab(id)} style={{
            padding:"8px 20px",border:"none",borderRadius:8,cursor:"pointer",fontWeight:600,fontSize:13,
            background:tab===id?CD.primary:"transparent",color:tab===id?"white":"#555",
            display: "flex", alignItems: "center", gap: 6,
          }}><TabIcon size={15} />{label}</button>
        ))}
      </div>

      {/* ── TAB: Mitarbeiter ── */}
      {tab==="ma" && (
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
            <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:0}}>Mitarbeiter/innen ({mas.filter(m=>m.is_active).length} aktiv)</h3>
            <button style={btn()} onClick={()=>setShowNewMA(!showNewMA)}>+ Neue/r MA</button>
          </div>

          {showNewMA && (
            <div style={{background:"#F0F8F0",border:"1.5px solid #004869",borderRadius:10,padding:20,marginBottom:20}}>
              <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 16px",color:"#004869"}}>Neue/r Mitarbeiter/in</h4>
              <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(180px,1fr))",gap:12}}>
                {[["name","Kürzel (z.B. Maria.M)"],["display_name","Anzeigename"],["eintritt","Eintritt (YYYY-MM-DD)"],["austritt","Austritt (YYYY-MM-DD)"]].map(([k,l]) => (
                  <div key={k}><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>{l}</div>
                  <input style={inp({width:"100%",boxSizing:"border-box"})} value={newMA[k]||""} onChange={e=>setNewMA({...newMA,[k]:e.target.value})} /></div>
                ))}
                <div><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>Führungsperson</div>
                {fkSelect(newMA.fk_username, v => setNewMA({ ...newMA, fk_username: v }))}</div>
                <div><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>Hauptstandort</div>
                <select style={inp({width:"100%",boxSizing:"border-box"})} value={newMA.team} onChange={e=>setNewMA({...newMA,team:e.target.value})}>
                  {STANDORTE.filter(s=>s!=="Office").map(s=><option key={s}>{s}</option>)}</select></div>
                <div><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>Rolle</div>
                <select style={inp({width:"100%",boxSizing:"border-box"})} value={newMA.role} onChange={e=>setNewMA({...newMA,role:e.target.value})}>
                  {ROLLEN.map(r => <option key={r} value={r}>{formatRoleLabel(r)}</option>)}</select></div>
                <div><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>BG%</div>
                <input type="number" min="0.1" max="1" step="0.1" style={inp({width:"100%",boxSizing:"border-box"})} value={newMA.bg_pct} onChange={e=>setNewMA({...newMA,bg_pct:+e.target.value})} /></div>
              </div>
              <div style={{display:"flex",gap:8,marginTop:16}}>
                <button style={btn()} onClick={()=>saveMA(true)}>Speichern</button>
                <button style={btn("#EEE","#333")} onClick={()=>setShowNewMA(false)}>Abbrechen</button>
              </div>
            </div>
          )}

          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
            <thead><tr style={{background:"#004869",color:"white"}}>
              {["Name","Anzeige","Führungsperson","Rolle","Standorte","BG%","Eintritt","Austritt","Status","Aktionen"].map(h=>(
                <th key={h} style={{padding:"10px 12px",textAlign:"left",fontWeight:700}}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {mas.map((ma,i) => editMA?.name===ma.name ? (
                <tr key={ma.name} style={{background:"#F0F8F0"}}>
                  <td style={{padding:"8px 12px",fontWeight:700}}>{ma.name}</td>
                  {[["display_name",180],["fk_username",null],["role",null,ROLLEN],["team",null,STANDORTE.filter(s=>s!=="Office")],["bg_pct",60],["eintritt",120],["austritt",120]].map(([k,w,opts])=>(
                    <td key={k} style={{padding:"4px 8px"}}>
                      {k === "fk_username" ? fkSelect(editMA.fk_username, v => setEditMA({ ...editMA, fk_username: v }))
                      : opts ? <select style={inp()} value={editMA[k]||""} onChange={e=>setEditMA({...editMA,[k]:e.target.value})}>
                        {opts.map(o => <option key={o} value={o}>{k === "role" ? formatRoleLabel(o) : o}</option>)}</select>
                      : <input style={inp({width:w||"100%"})} value={editMA[k]||""} onChange={e=>setEditMA({...editMA,[k]:e.target.value})} />}
                    </td>
                  ))}
                  <td style={{padding:"4px 8px"}}><span style={{color:ma.is_active?"green":"#999"}}>{ma.is_active?"Aktiv":"Inaktiv"}</span></td>
                  <td style={{padding:"4px 8px",display:"flex",gap:4}}>
                    <button style={btn()} onClick={()=>saveMA()}>✓</button>
                    <button style={btn("#EEE","#333")} onClick={()=>setEditMA(null)}>✕</button>
                  </td>
                </tr>
              ) : (
                <tr key={ma.name} style={{background:!ma.is_active?"#F9F9F9":i%2===0?"white":"#F8F9FA",opacity:ma.is_active?1:0.6}}>
                  <td style={{padding:"8px 12px",fontWeight:700,fontFamily:"monospace",fontSize:12}}>{ma.name}</td>
                  <td style={{padding:"8px 12px"}}>{ma.display_name}</td>
                  <td style={{padding:"8px 12px",color:"#555",fontSize:12}}>{ma.fk_display_name || ma.fk_username || "—"}</td>
                  <td style={{padding:"8px 12px",color:"#555"}}>{formatRoleLabel(ma.role)}</td>
                  <td style={{padding:"8px 12px",color:"#555",fontSize:12}} title={formatStandorte(ma)}>{formatStandorte(ma)}</td>
                  <td style={{padding:"8px 12px",textAlign:"center"}}>{(ma.bg_pct*100).toFixed(0)}%</td>
                  <td style={{padding:"8px 12px",fontSize:12,color:"#777"}}>{ma.eintritt||"—"}</td>
                  <td style={{padding:"8px 12px",fontSize:12,color:"#777"}}>{ma.austritt||"—"}</td>
                  <td style={{padding:"8px 12px"}}>
                    <span style={{background:ma.is_active?"#E8F8E8":"#F0F0F0",color:ma.is_active?"#1a7a1a":"#999",padding:"3px 10px",borderRadius:20,fontSize:11,fontWeight:700}}>
                      {ma.is_active?"Aktiv":"Inaktiv"}
                    </span>
                  </td>
                  <td style={{padding:"8px 12px"}}>
                    <div style={{display:"flex",gap:6}}>
                      <button style={btn("#E4EEF3","#004869")} onClick={()=>setEditMA({...ma})}>✏️</button>
                      <button style={btn("#E4EEF3","#004869")} onClick={()=>loadSchedule(ma.name)}>📅</button>
                      <button style={btn(ma.is_active?"#FFE8E8":"#E8F8E8",ma.is_active?"#c0392b":"#1a7a1a")} onClick={()=>toggleMA(ma.name)}>
                        {ma.is_active?"Deakt.":"Aktivieren"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── TAB: Arbeitstag-Muster (via MA selection) ── */}
      {tab==="schedule" && (
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 20px"}}>Arbeitstag-Muster pro Mitarbeiter/in</h3>
          {!scheduleMA ? (
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))",gap:12}}>
              {[...mas].sort((a,b)=>(b.is_active-a.is_active)||a.display_name.localeCompare(b.display_name)).map(ma=>(
                <button key={ma.name} onClick={()=>loadSchedule(ma.name)} style={{
                  background: ma.is_active ? "#F8F9FA" : "#FFF8F0",
                  border: ma.is_active ? "1.5px solid #E0E0E0" : "1.5px solid #F0D8B8",
                  borderRadius:8,padding:"14px 16px",
                  cursor:"pointer",textAlign:"left"
                }}>
                  <div style={{fontWeight:700,fontSize:13}}>
                    {ma.display_name}
                    {!ma.is_active && <span style={{fontWeight:500,color:"#B8860B",marginLeft:6}}>(ausgetreten)</span>}
                  </div>
                  <div style={{fontSize:11,color:"#888",marginTop:4}}>{ma.team} · {(ma.bg_pct*100).toFixed(0)}%</div>
                </button>
              ))}
            </div>
          ) : (
            <div>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
                <h4 style={{ fontFamily: CD.fontDisplay,margin:0,color:CD.primary,display:"flex",alignItems:"center",gap:8}}>
                  <Calendar size={18} /> {scheduleMAMeta?.display_name || scheduleMA}
                  {scheduleMAMeta && !scheduleMAMeta.is_active && (
                    <span style={{ fontSize: 12, fontWeight: 600, color: "#B8860B" }}>(ausgetreten)</span>
                  )}
                </h4>
                <button style={btn("#EEE","#333")} onClick={()=>{setScheduleMA(null);setScheduleMAMeta(null);setScheduleEditYM("")}}>← Zurück</button>
              </div>
              {scheduleMAMeta && !scheduleMAMeta.is_active && (
                <div style={{ marginBottom: 16, padding: "12px 16px", background: "#FFF8F0", border: "1px solid #F0D8B8", borderRadius: 8, fontSize: 12, lineHeight: 1.5, color: "#555" }}>
                  {scheduleMAMeta.austritt
                    ? <>Ausgetreten am <strong>{scheduleMAMeta.austritt}</strong>. </>
                    : null}
                  «Gültig ab» auf <strong>2026-01</strong> lassen (oder früher), damit historische Monate stimmen — oder pro Monat einen Override setzen.
                </div>
              )}
              <ScheduleHelp />
              <div style={{display:"flex",flexWrap:"wrap",gap:12,marginBottom:16}}>
                <label style={{display:"flex",alignItems:"center",gap:6,fontSize:13,cursor:"pointer"}}>
                  <input type="radio" name="schedScope" checked={scheduleScope==="from"} onChange={()=>{setScheduleScope("from");setScheduleEditYM("");loadSchedule(scheduleMA)}} />
                  Standard (gültig ab Monat)
                </label>
                <label style={{display:"flex",alignItems:"center",gap:6,fontSize:13,cursor:"pointer"}}>
                  <input type="radio" name="schedScope" checked={scheduleScope==="month"} onChange={()=>{
                    const ym = scheduleEditYM || `${new Date().getFullYear()}-${String(new Date().getMonth()+1).padStart(2,"0")}`
                    setScheduleScope("month"); setScheduleEditYM(ym); loadSchedule(scheduleMA, ym)
                  }} />
                  Nur dieser Monat (Override)
                </label>
              </div>
              <div style={{display:"flex",flexWrap:"wrap",gap:16,alignItems:"flex-end",marginBottom:16,padding:"12px 16px",background:"#F8F9FA",borderRadius:8,border:"1px solid #E8E8E8"}}>
                {scheduleScope === "from" ? (
                  <>
                    <div>
                      <div style={{fontSize:11,fontWeight:700,color:"#555",marginBottom:4}}>Gültig ab (Monat)</div>
                      <input type="month" value={scheduleValidFrom} onChange={e=>setScheduleValidFrom(e.target.value)}
                        style={inp()} />
                    </div>
                    <div style={{fontSize:12,color:"#666",maxWidth:420,lineHeight:1.5}}>
                      Gilt ab dem <strong>1. des gewählten Monats</strong> für FTE, Standorte und Soll-Tage.
                      Frühere Monate behalten die bisherige Version.
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <div style={{fontSize:11,fontWeight:700,color:"#555",marginBottom:4}}>Monat (nur dieser)</div>
                      <input type="month" value={scheduleEditYM} onChange={e=>{setScheduleEditYM(e.target.value); loadSchedule(scheduleMA, e.target.value)}}
                        style={inp()} />
                    </div>
                    <div style={{fontSize:12,color:"#666",maxWidth:420,lineHeight:1.5}}>
                      Überschreibt den Standardplan <strong>nur für diesen einen Monat</strong> (z. B. Vertretung, temporäre Standortänderung).
                    </div>
                  </>
                )}
                {scheduleVersions.length > 0 && (
                  <div style={{fontSize:11,color:"#888",width:"100%"}}>
                    Versionen: {scheduleVersions.map(v => v.label).join(" · ")}
                  </div>
                )}
              </div>
              {scheduleLoading ? (
                <div style={{ padding: 32, textAlign: "center", color: "#888" }}>Arbeitsplan wird geladen…</div>
              ) : (
              <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
                <thead><tr style={{background:CD.primary,color:"white"}}>
                  <th style={{padding:"10px 14px",textAlign:"left"}}>Tag</th>
                  <th style={{padding:"10px 14px",textAlign:"center"}}>Vormittag</th>
                  <th style={{padding:"10px 14px",textAlign:"left"}}>Standort VM</th>
                  <th style={{padding:"10px 14px",textAlign:"center"}}>Nachmittag</th>
                  <th style={{padding:"10px 14px",textAlign:"left"}}>Standort NM</th>
                </tr></thead>
                <tbody>
                  {DAYS_DE.map((day,di) => {
                    const entry = schedule.find(s=>s.weekday===di) || {weekday:di,vm_pct:0,vm_standort:"",nm_pct:0,nm_standort:""}
                    const update = (field,val) => {
                      const newSched = schedule.filter(s=>s.weekday!==di)
                      newSched.push({...entry,[field]:field.includes("pct")?+val:val})
                      setSchedule(newSched.sort((a,b)=>a.weekday-b.weekday))
                    }
                    return (
                      <tr key={di} style={{background:di%2===0?"white":"#F8F9FA"}}>
                        <td style={{padding:"10px 14px",fontWeight:700}}>{day}</td>
                        <td style={{padding:"6px 8px",textAlign:"center"}}>
                          <div style={{display:"flex",alignItems:"center",justifyContent:"center",gap:4}}>
                            <input type="number" min="0" max="10" step="5"
                              value={Math.round((entry.vm_pct||0)*100)}
                              onChange={e=>update("vm_pct", +e.target.value / 100)}
                              style={{...inp(),width:56,textAlign:"center"}} />
                            <span style={{fontSize:11,color:"#888"}}>%</span>
                          </div>
                        </td>
                        <td style={{padding:"6px 8px"}}>
                          <select value={entry.vm_standort||""} onChange={e=>update("vm_standort",e.target.value)}
                            style={inp({minWidth:130})}>
                            <option value="">— frei —</option>
                            {STANDORTE.map(s=><option key={s}>{s}</option>)}
                          </select>
                        </td>
                        <td style={{padding:"6px 8px",textAlign:"center"}}>
                          <div style={{display:"flex",alignItems:"center",justifyContent:"center",gap:4}}>
                            <input type="number" min="0" max="10" step="5"
                              value={Math.round((entry.nm_pct||0)*100)}
                              onChange={e=>update("nm_pct", +e.target.value / 100)}
                              style={{...inp(),width:56,textAlign:"center"}} />
                            <span style={{fontSize:11,color:"#888"}}>%</span>
                          </div>
                        </td>
                        <td style={{padding:"6px 8px"}}>
                          <select value={entry.nm_standort||""} onChange={e=>update("nm_standort",e.target.value)}
                            style={inp({minWidth:130})}>
                            <option value="">— frei —</option>
                            {STANDORTE.map(s=><option key={s}>{s}</option>)}
                          </select>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              )}
              <div style={{marginTop:16,display:"flex",gap:8}}>
                <button style={btn()} onClick={saveSchedule} disabled={scheduleLoading}>Speichern</button>
                <button style={btn("#EEE","#333")} onClick={()=>{setScheduleMA(null);setScheduleMAMeta(null);setScheduleEditYM("")}}>Abbrechen</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB: Feiertage ── */}
      {tab==="feiertage" && (
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20,flexWrap:"wrap",gap:12}}>
            <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:0}}>Feiertage Kanton Zürich</h3>
            <div style={{display:"flex",gap:12,alignItems:"center"}}>
              <YearSelect value={feiertagYear} onChange={setFeiertagYear} years={years} />
              <button style={btn()} onClick={saveFeiertage}>Alle speichern</button>
            </div>
          </div>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13,marginBottom:20}}>
            <thead><tr style={{background:"#004869",color:"white"}}>
              {["Datum","Name","Faktor (1.0 = ganz, 0.5 = halb)",""].map(h=>(
                <th key={h} style={{padding:"10px 14px",textAlign:"left",fontWeight:700}}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {feiertage.map((f,i)=>(
                <tr key={f.date_str} style={{background:i%2===0?"white":"#F8F9FA"}}>
                  <td style={{padding:"8px 14px",fontFamily:"monospace"}}>{f.date_str}</td>
                  <td style={{padding:"8px 14px"}}>{f.name}</td>
                  <td style={{padding:"8px 14px"}}>
                    <select value={f.faktor} onChange={e=>setFeiertage(feiertage.map((x,j)=>j===i?{...x,faktor:+e.target.value}:x))}
                      style={inp()}>
                      <option value={1.0}>1.0 — ganzer Tag</option>
                      <option value={0.5}>0.5 — halber Tag</option>
                    </select>
                  </td>
                  <td style={{padding:"8px 14px"}}>
                    <button style={btn("#FFE8E8","#c0392b")} onClick={()=>setFeiertage(feiertage.filter((_,j)=>j!==i))}>✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{background:"#F8F9FA",border:"1.5px solid #DDD",borderRadius:8,padding:16}}>
            <div style={{fontWeight:700,fontSize:13,marginBottom:12,color:"#555"}}>Neuer Feiertag</div>
            <div style={{display:"flex",gap:12,alignItems:"flex-end",flexWrap:"wrap"}}>
              <div><div style={{fontSize:11,fontWeight:600,marginBottom:4}}>Datum</div>
              <input type="date" style={inp()} value={newFeiertag.date_str} onChange={e=>setNewFeiertag({...newFeiertag,date_str:e.target.value})} /></div>
              <div><div style={{fontSize:11,fontWeight:600,marginBottom:4}}>Name</div>
              <input style={inp({width:200})} value={newFeiertag.name} onChange={e=>setNewFeiertag({...newFeiertag,name:e.target.value})} /></div>
              <div><div style={{fontSize:11,fontWeight:600,marginBottom:4}}>Faktor</div>
              <select style={inp()} value={newFeiertag.faktor} onChange={e=>setNewFeiertag({...newFeiertag,faktor:+e.target.value})}>
                <option value={1.0}>1.0 — ganz</option>
                <option value={0.5}>0.5 — halb</option>
              </select></div>
              <button style={btn()} onClick={addFeiertag}>Hinzufügen</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


// ── Profil / Passwort ändern ───────────────────────────────────────────────
function ProfilPage() {
  const auth = useAuth()
  const [form, setForm] = useState({current_password:"",new_password:"",confirm:""})
  const [email, setEmail] = useState("")
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    api("/api/profile").then(p => setEmail(p.email || "")).catch(() => {})
  }, [])

  const saveEmail = async () => {
    try {
      await api("/api/profile", { method: "PATCH", body: JSON.stringify({ email }) })
      setMsg({ type: "ok", text: "E-Mail gespeichert — für «Passwort vergessen»" })
    } catch (e) { setMsg({ type: "err", text: e.message }) }
  }

  const submit = async () => {
    if (form.new_password !== form.confirm) { setMsg({type:"err",text:"Passwörter stimmen nicht überein"}); return }
    if (form.new_password.length < 8) { setMsg({type:"err",text:"Mindestens 8 Zeichen"}); return }
    try {
      await api("/api/profile/change-password", {method:"POST", body:JSON.stringify({
        current_password: form.current_password, new_password: form.new_password
      })})
      setMsg({type:"ok",text:"Passwort erfolgreich geändert"})
      setForm({current_password:"",new_password:"",confirm:""})
    } catch(e) { setMsg({type:"err",text:e.message}) }
  }

  return (
    <div>
      <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 28px",fontSize:24,fontWeight:800}}>Profil</h1>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:20,maxWidth:800}}>
        <div style={{background:"white",borderRadius:12,padding:28,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 20px",color:"#004869"}}>👤 Mein Konto</h3>
          {[["Benutzername",auth.user?.username],["Name",auth.user?.full_name],["Rolle",formatRoleLabel(auth.user?.role)],["Team",auth.user?.team||"Alle"]].map(([l,v])=>(
            <div key={l} style={{display:"flex",justifyContent:"space-between",padding:"10px 0",borderBottom:"1px solid #F5F5F5"}}>
              <span style={{color:"#888",fontSize:13}}>{l}</span>
              <span style={{fontWeight:600,fontSize:13}}>{v||"—"}</span>
            </div>
          ))}
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>E-Mail (für Passwort-Reset)</div>
            <div style={{ display: "flex", gap: 8 }}>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="name@kineo.swiss"
                style={{ flex: 1, padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
              <button type="button" onClick={saveEmail} style={{ padding: "8px 14px", background: "#F0F0F0", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>Speichern</button>
            </div>
          </div>
        </div>
        <div style={{background:"white",borderRadius:12,padding:28,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 20px",color:"#004869"}}>🔒 Passwort ändern</h3>
          {msg && <div style={{background:msg.type==="ok"?"#E8F8E8":"#FFE8E8",color:msg.type==="ok"?"#1a7a1a":"#c0392b",padding:"10px 14px",borderRadius:8,marginBottom:16,fontSize:13}}>{msg.text}</div>}
          {[["current_password","Aktuelles Passwort"],["new_password","Neues Passwort (min. 8 Zeichen)"],["confirm","Neues Passwort bestätigen"]].map(([k,l])=>(
            <div key={k} style={{marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:6}}>{l}</div>
              <input type="password" value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})}
                style={{width:"100%",padding:"10px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:14,boxSizing:"border-box"}} />
            </div>
          ))}
          <button onClick={submit} style={{width:"100%",padding:"11px",background:"#004869",color:"white",border:"none",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,marginTop:4}}>
            Passwort ändern
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Bilaterals Page ────────────────────────────────────────────────────────
const KAT_LABELS = {
  a: "Profitabilität & Auslastung",
  b: "Qualität & Operational Excellence",
  c: "Satisfaction Intern – Team & Kultur",
  d: "Satisfaction Extern – Patienten & Zuweiser",
  e: "Entwicklung & Potenzial",
  f: "Zusammenarbeit & Kommunikation",
}
const KAT_KEYS_REQUIRED = ["a", "b", "c", "d"]
const KAT_KEYS_ALL = ["a", "b", "c", "d", "e", "f"]

const QUAL_STATUSES = ["offen", "läuft", "gut", "stabil", "erledigt", "kritisch"]

function QualGoalsPage() {
  const auth = useAuth()
  const years = useAvailableYears()
  const now = new Date()
  const defaultPeriod = `${now.getMonth() < 6 ? "HJ1" : "HJ2"} ${now.getFullYear()}`
  const [year, setYear] = useState(now.getFullYear())
  const [period, setPeriod] = useState(defaultPeriod)
  const [overview, setOverview] = useState([])
  const [selected, setSelected] = useState(null)
  const [goals, setGoals] = useState([])
  const [templateGoals, setTemplateGoals] = useState([])
  const [signature, setSignature] = useState(null)
  const [signForm, setSignForm] = useState({ fk_display_name: "", ma_confirm_name: "", notes: "" })
  const [fkOk, setFkOk] = useState(false)
  const [maOk, setMaOk] = useState(false)
  const [msg, setMsg] = useState(null)
  const [saving, setSaving] = useState(false)

  const loadOverview = () => {
    api(`/api/qual-goals/${year}/${encodeURIComponent(period)}`)
      .then(d => setOverview(d.ma_data || []))
      .catch(e => setMsg({ type: "err", text: e.message }))
  }

  useEffect(() => { loadOverview() }, [year, period])

  const openMA = async (ma) => {
    setMsg(null)
    const data = await api(`/api/qual-goals/${ma.name}/${year}/${encodeURIComponent(period)}`).catch(e => {
      setMsg({ type: "err", text: e.message }); return null
    })
    if (!data) return
    setSelected(ma)
    setGoals(data.goals?.length ? data.goals : [{ name: "", result: "", status: "offen", detail: "" }])
    setTemplateGoals(data.template_goals || [])
    setSignature(data.signature || null)
    setSignForm({
      fk_display_name: auth.user?.full_name || "",
      ma_confirm_name: ma.display_name || "",
      notes: "",
    })
    setFkOk(false)
    setMaOk(false)
  }

  const save = async (unlock = false) => {
    setSaving(true)
    try {
      const res = await api(`/api/qual-goals/${selected.name}/${year}/${encodeURIComponent(period)}`, {
        method: "PUT",
        body: JSON.stringify({
          goals: goals.filter(g => (g.name || "").trim()),
          unlock_signed: unlock,
        }),
      })
      setGoals(res.goals?.length ? res.goals : [])
      if (unlock) setSignature(null)
      setMsg({ type: "ok", text: res.message || "Gespeichert — Bilats nutzen diese Werte" })
      loadOverview()
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const unlockAndEdit = async () => {
    if (!confirm("Signatur ungültig machen und Qualis bearbeiten? Danach neu unterzeichnen.")) return
    await save(true)
  }

  const importTemplate = async () => {
    setSaving(true)
    try {
      const res = await api(`/api/qual-goals/${selected.name}/${year}/${encodeURIComponent(period)}/import-template`, {
        method: "POST",
      })
      setGoals(res.goals || [])
      setMsg({ type: "ok", text: res.message || "Aus Vorlage importiert" })
      loadOverview()
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const sign = async () => {
    if (!fkOk || !maOk) {
      setMsg({ type: "err", text: "Bitte beide Bestätigungen (FK + MA) anhaken." })
      return
    }
    setSaving(true)
    try {
      const res = await api(`/api/qual-goals/${selected.name}/${year}/${encodeURIComponent(period)}/sign`, {
        method: "POST",
        body: JSON.stringify(signForm),
      })
      setSignature(res.signature || null)
      setMsg({ type: "ok", text: res.message || "Unterzeichnet — PDF in der Ablage" })
      loadOverview()
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const downloadSignedPdf = async (docId) => {
    try {
      const token = localStorage.getItem("token")
      const res = await fetch(`${API}/api/documents/${docId}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error("Download fehlgeschlagen")
      const blob = await res.blob()
      const a = document.createElement("a")
      a.href = URL.createObjectURL(blob)
      a.download = `Quali_${selected?.display_name || selected?.name}_${period}_signed.pdf`
      a.click()
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    }
  }

  const updateGoal = (idx, field, value) => {
    setGoals(gs => gs.map((g, i) => i === idx ? { ...g, [field]: value } : g))
  }

  const selectStyle = { padding: "6px 10px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12, background: "white", color: "#333" }

  if (selected) {
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
          <button onClick={() => { setSelected(null); setMsg(null); loadOverview() }}
            style={{ background: "#EEE", border: "none", padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>
            ← Zurück
          </button>
          <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: 0, fontSize: 22, fontWeight: 800 }}>
            Quali-Themen — {selected.display_name}
          </h1>
          <span style={{ color: "#888", fontSize: 13 }}>{period}</span>
          {signature && (
            <span style={{ background: "#E8F8E8", color: "#1a7a1a", padding: "4px 10px", borderRadius: 20, fontSize: 11, fontWeight: 700 }}>
              ✓ Unterzeichnet
            </span>
          )}
        </div>
        <div style={{ background: "#F8FAFB", border: "1px solid #E4EEF3", borderRadius: 10, padding: "12px 16px", marginBottom: 16, fontSize: 13, color: "#555" }}>
          Hier pflegt das Management Qualitätsthemen (Ziel, Ergebnis %, Status, Detail).
          Speichern → Bilat-Gesprächsinfos. Unterzeichnen → PDF in der <strong>Ablage</strong>.
        </div>
        {msg && (
          <div style={{
            background: msg.type === "ok" ? "#E8F8E8" : "#FFE8E8",
            color: msg.type === "ok" ? "#1a7a1a" : "#c0392b",
            padding: "10px 14px", borderRadius: 8, marginBottom: 16, fontSize: 13,
          }}>{msg.text}</div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {goals.map((g, i) => (
            <div key={i} style={{ background: "white", borderRadius: 12, padding: 16, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", opacity: signature ? 0.85 : 1 }}>
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 10, marginBottom: 10 }}>
                <input value={g.name || ""} onChange={e => updateGoal(i, "name", e.target.value)}
                  placeholder="Qualitätsthema / Ziel" disabled={!!signature}
                  style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                <input value={g.result || ""} onChange={e => updateGoal(i, "result", e.target.value)}
                  placeholder="Ergebnis (z.B. 91.7%)" disabled={!!signature}
                  style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                <select value={g.status || "offen"} onChange={e => updateGoal(i, "status", e.target.value)} disabled={!!signature}
                  style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }}>
                  {QUAL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <input value={g.detail || ""} onChange={e => updateGoal(i, "detail", e.target.value)}
                  placeholder="Detail / Bemerkung" disabled={!!signature}
                  style={{ flex: 1, padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                {!signature && (
                  <button type="button" onClick={() => setGoals(gs => gs.filter((_, j) => j !== i))}
                    style={{ padding: "8px 12px", border: "1px solid #DDD", borderRadius: 8, background: "white", cursor: "pointer", color: "#c0392b", fontSize: 12 }}>
                    Entfernen
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 16, display: "flex", gap: 10, flexWrap: "wrap" }}>
          {!signature && (
            <button type="button" onClick={() => setGoals(gs => [...gs, { name: "", result: "", status: "offen", detail: "" }])}
              style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #DDD", background: "white", cursor: "pointer", fontWeight: 600 }}>
              + Ziel hinzufügen
            </button>
          )}
          {!signature && templateGoals.length > 0 && (
            <button type="button" onClick={importTemplate} disabled={saving}
              style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #004869", background: "white", color: "#004869", cursor: "pointer", fontWeight: 600 }}>
              Aus Word-Vorlage übernehmen
            </button>
          )}
          {signature ? (
            <button type="button" onClick={unlockAndEdit} disabled={saving}
              style={{ padding: "10px 24px", borderRadius: 8, border: "1px solid #c0392b", background: "white", color: "#c0392b", cursor: "pointer", fontWeight: 700, marginLeft: "auto" }}>
              Bearbeitung freigeben
            </button>
          ) : (
            <button type="button" onClick={() => save(false)} disabled={saving}
              style={{ padding: "10px 24px", borderRadius: 8, border: "none", background: "#004869", color: "white", cursor: "pointer", fontWeight: 700, marginLeft: "auto" }}>
              {saving ? "…" : "Speichern"}
            </button>
          )}
        </div>

        <div style={{ marginTop: 28, background: "white", borderRadius: 12, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px", color: "#004869", fontSize: 16 }}>Unterzeichnen</h3>
          <div style={{ fontSize: 12, color: "#888", marginBottom: 14 }}>
            Digitale Bestätigung mit Zeitstempel — erzeugt ein PDF in der Ablage (pro MA).
          </div>
          {signature ? (
            <div style={{ background: "#E8F8E8", borderRadius: 8, padding: 14, fontSize: 13 }}>
              <div style={{ fontWeight: 700, color: "#1a7a1a", marginBottom: 6 }}>Bereits unterzeichnet</div>
              <div>FK: {signature.fk_display_name} · {signature.fk_confirmed_at && new Date(signature.fk_confirmed_at).toLocaleString("de-CH")}</div>
              <div>MA: {signature.ma_display_name} · {signature.ma_confirmed_at && new Date(signature.ma_confirmed_at).toLocaleString("de-CH")}</div>
              {signature.document_id && (
                <button type="button" onClick={() => downloadSignedPdf(signature.document_id)}
                  style={{ marginTop: 10, padding: "8px 14px", borderRadius: 8, border: "1px solid #004869", background: "white", color: "#004869", cursor: "pointer", fontWeight: 600, fontSize: 12 }}>
                  PDF herunterladen
                </button>
              )}
              <div style={{ marginTop: 10, fontSize: 12, color: "#666" }}>
                Erneutes Unterzeichnen erstellt eine neue Version in der Ablage.
              </div>
            </div>
          ) : null}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: signature ? 14 : 0 }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>Name Führungskraft</div>
              <input value={signForm.fk_display_name} onChange={e => setSignForm({ ...signForm, fk_display_name: e.target.value })}
                style={{ width: "100%", padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13, boxSizing: "border-box" }} />
              <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, fontSize: 12, cursor: "pointer" }}>
                <input type="checkbox" checked={fkOk} onChange={e => setFkOk(e.target.checked)} />
                FK bestätigt die Quali-Ziele
              </label>
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>Name Mitarbeiter/in</div>
              <input value={signForm.ma_confirm_name} onChange={e => setSignForm({ ...signForm, ma_confirm_name: e.target.value })}
                style={{ width: "100%", padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13, boxSizing: "border-box" }} />
              <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, fontSize: 12, cursor: "pointer" }}>
                <input type="checkbox" checked={maOk} onChange={e => setMaOk(e.target.checked)} />
                MA bestätigt die Quali-Ziele
              </label>
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>Bemerkung (optional)</div>
            <input value={signForm.notes} onChange={e => setSignForm({ ...signForm, notes: e.target.value })}
              style={{ width: "100%", padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13, boxSizing: "border-box" }} />
          </div>
          <button type="button" onClick={sign} disabled={saving || !(goals.some(g => (g.name || "").trim()))}
            style={{ marginTop: 14, padding: "11px 22px", borderRadius: 8, border: "none", background: "#004869", color: "white", cursor: "pointer", fontWeight: 700, fontSize: 14 }}>
            {saving ? "…" : "Unterzeichnen & PDF ablegen"}
          </button>
        </div>
      </div>
    )
  }

  const teams = [...new Set(overview.map(m => m.team).filter(Boolean))]
  return (
    <div>
      <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px", fontSize: 24, fontWeight: 800 }}>Quali-Themen</h1>
      <div style={{ color: "#888", marginBottom: 18, fontSize: 13 }}>
        Qualitätsthemen für Bilaterals pflegen — Quelle für Gesprächsinfos, Unterzeichnung & Ablage
      </div>
      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Jahr: <YearSelect value={year} onChange={y => {
            setYear(y)
            const half = period.includes("HJ2") || period.startsWith("2.") ? "HJ2" : "HJ1"
            setPeriod(`${half} ${y}`)
          }} years={years} style={selectStyle} />
        </label>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Periode:
          <select value={period} onChange={e => setPeriod(e.target.value)} style={selectStyle}>
            {[`HJ1 ${year}`, `HJ2 ${year}`].map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
      </div>
      {msg && (
        <div style={{
          background: msg.type === "ok" ? "#E8F8E8" : "#FFE8E8",
          color: msg.type === "ok" ? "#1a7a1a" : "#c0392b",
          padding: "10px 14px", borderRadius: 8, marginBottom: 16, fontSize: 13,
        }}>{msg.text}</div>
      )}
      {teams.map(team => (
        <div key={team} style={{ marginBottom: 24 }}>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif", fontSize: 16, color: "#004869", marginBottom: 10 }}>{team}</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))", gap: 12 }}>
            {overview.filter(m => m.team === team).map(ma => (
              <button key={ma.name} onClick={() => openMA(ma)}
                style={{
                  textAlign: "left", background: "white", border: "1px solid #EEE", borderRadius: 10,
                  padding: "14px 16px", cursor: "pointer", boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
                }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{ma.display_name}</div>
                  {ma.signed && <span style={{ fontSize: 10, fontWeight: 700, color: "#1a7a1a" }}>✓ signiert</span>}
                </div>
                <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
                  {ma.goal_count ? `${ma.goal_count} Ziele gepflegt` : "Noch keine Ziele in der App"}
                  {ma.kpi_label ? ` · ${ma.kpi_label}` : ""}
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
      {overview.length === 0 && (
        <div style={{ color: "#888", fontSize: 13 }}>Keine Mitarbeiter sichtbar für diese Auswahl.</div>
      )}
    </div>
  )
}

function DocumentsPage() {
  const years = useAvailableYears()
  const now = new Date()
  const [docs, setDocs] = useState([])
  const [mas, setMas] = useState([])
  const [filterMa, setFilterMa] = useState("")
  const [uploadMa, setUploadMa] = useState("")
  const [title, setTitle] = useState("")
  const [uploadYear, setUploadYear] = useState(now.getFullYear())
  const [uploadPeriod, setUploadPeriod] = useState(`${now.getMonth() < 6 ? "HJ1" : "HJ2"} ${now.getFullYear()}`)
  const [msg, setMsg] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = () => {
    const q = filterMa ? `?ma_name=${encodeURIComponent(filterMa)}` : ""
    api(`/api/documents${q}`)
      .then(d => { setDocs(d.documents || []); setMas(d.mas || []) })
      .catch(e => setMsg({ type: "err", text: e.message }))
  }

  useEffect(() => { load() }, [filterMa])

  const download = async (doc) => {
    try {
      const token = localStorage.getItem("token")
      const res = await fetch(`${API}/api/documents/${doc.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error("Download fehlgeschlagen")
      const blob = await res.blob()
      const a = document.createElement("a")
      a.href = URL.createObjectURL(blob)
      a.download = doc.filename || "dokument"
      a.click()
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    }
  }

  const remove = async (doc) => {
    if (!confirm(`«${doc.title}» löschen?`)) return
    try {
      await api(`/api/documents/${doc.id}`, { method: "DELETE" })
      setMsg({ type: "ok", text: "Gelöscht" })
      load()
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    }
  }

  const upload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ""
    if (!file || !uploadMa) {
      setMsg({ type: "err", text: "Bitte MA wählen und Datei auswählen" })
      return
    }
    setLoading(true)
    try {
      const token = localStorage.getItem("token")
      const fd = new FormData()
      fd.append("file", file)
      if (title.trim()) fd.append("title", title.trim())
      fd.append("year", String(uploadYear))
      fd.append("period_label", uploadPeriod)
      const res = await fetch(`${API}/api/documents/${encodeURIComponent(uploadMa)}/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg || d).join(", ") : data.detail
        throw new Error(detail || "Upload fehlgeschlagen")
      }
      setMsg({ type: "ok", text: "Hochgeladen" })
      setTitle("")
      load()
    } catch (err) {
      setMsg({ type: "err", text: err.message })
    } finally {
      setLoading(false)
    }
  }

  const byMa = {}
  for (const d of docs) {
    if (!byMa[d.ma_name]) byMa[d.ma_name] = { display: d.display_name || d.ma_name, team: d.team, items: [] }
    byMa[d.ma_name].items.push(d)
  }

  const selectStyle = { padding: "6px 10px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12, background: "white" }

  return (
    <div>
      <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 8px", fontSize: 24, fontWeight: 800 }}>Ablage</h1>
      <div style={{ color: "#888", marginBottom: 18, fontSize: 13 }}>
        Unterzeichnete Quali-PDFs und Dateien pro Mitarbeiter/in
      </div>
      {msg && (
        <div style={{
          background: msg.type === "ok" ? "#E8F8E8" : "#FFE8E8",
          color: msg.type === "ok" ? "#1a7a1a" : "#c0392b",
          padding: "10px 14px", borderRadius: 8, marginBottom: 16, fontSize: 13,
        }}>{msg.text}</div>
      )}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 20, alignItems: "center" }}>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Filter MA:
          <select value={filterMa} onChange={e => setFilterMa(e.target.value)} style={selectStyle}>
            <option value="">Alle</option>
            {mas.map(m => <option key={m.name} value={m.name}>{m.display_name} ({m.team})</option>)}
          </select>
        </label>
      </div>
      <div style={{ background: "white", borderRadius: 12, padding: 16, marginBottom: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <div style={{ fontWeight: 700, color: "#004869", marginBottom: 10, fontSize: 14 }}>Datei hochladen</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <select value={uploadMa} onChange={e => setUploadMa(e.target.value)} style={selectStyle}>
            <option value="">MA wählen…</option>
            {mas.map(m => <option key={m.name} value={m.name}>{m.display_name}</option>)}
          </select>
          <YearSelect value={uploadYear} onChange={y => {
            setUploadYear(y)
            const half = uploadPeriod.includes("HJ2") || uploadPeriod.startsWith("2.") ? "HJ2" : "HJ1"
            setUploadPeriod(`${half} ${y}`)
          }} years={years} style={selectStyle} />
          <select value={uploadPeriod} onChange={e => setUploadPeriod(e.target.value)} style={selectStyle}>
            {[`HJ1 ${uploadYear}`, `HJ2 ${uploadYear}`].map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Titel (optional)"
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12, minWidth: 180 }} />
          <label style={{ padding: "8px 14px", background: "#004869", color: "white", borderRadius: 8, cursor: "pointer", fontSize: 12, fontWeight: 700 }}>
            {loading ? "…" : "Datei wählen"}
            <input type="file" accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt,.png,.jpg,.jpeg,.webp" onChange={upload} style={{ display: "none" }} disabled={loading} />
          </label>
        </div>
      </div>
      {Object.keys(byMa).length === 0 && (
        <div style={{ color: "#888", fontSize: 13 }}>Noch keine Dokumente — Qualis unterzeichnen oder Datei hochladen.</div>
      )}
      {Object.entries(byMa).map(([name, group]) => (
        <div key={name} style={{ background: "white", borderRadius: 12, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", marginBottom: 16 }}>
          <div style={{ background: "#004869", color: "white", padding: "12px 16px", display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontWeight: 800 }}>{group.display}</span>
            <span style={{ fontSize: 12, opacity: 0.85 }}>{group.team || ""} · {group.items.length}</span>
          </div>
          {group.items.map(doc => (
            <div key={doc.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "12px 16px", borderBottom: "1px solid #F5F5F5", flexWrap: "wrap" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{doc.title}</div>
                <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>
                  {doc.doc_type === "qual_signed" ? "Quali unterzeichnet" : "Upload"}
                  {doc.period_label ? ` · ${doc.period_label}` : ""}
                  {doc.created_at ? ` · ${new Date(doc.created_at).toLocaleString("de-CH")}` : ""}
                  {doc.size_bytes != null ? ` · ${Math.max(1, Math.round(doc.size_bytes / 1024))} KB` : ""}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" onClick={() => download(doc)}
                  style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #004869", background: "white", color: "#004869", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                  Download
                </button>
                <button type="button" onClick={() => remove(doc)}
                  style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #DDD", background: "white", color: "#c0392b", cursor: "pointer", fontSize: 12 }}>
                  Löschen
                </button>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

const RATING_WORDS = ["", "Entwicklungsbedarf", "Unter Erwartung", "Erwartung erfüllt", "Gut", "Ausgezeichnet"]

const FLOW_STEPS = [
  { id: "fk_prep", label: "FK vorbereiten" },
  { id: "ma_self", label: "MA Selbsteinschätzung" },
  { id: "reveal", label: "Abgleich" },
  { id: "done", label: "Abschluss" },
]

const BILAT_FIELD_KEYS = [
  "kat_a_self", "kat_a_fk", "kat_a_comment",
  "kat_b_self", "kat_b_fk", "kat_b_comment",
  "kat_c_self", "kat_c_fk", "kat_c_comment",
  "kat_d_self", "kat_d_fk", "kat_d_comment",
  "kat_e_self", "kat_e_fk", "kat_e_comment",
  "kat_f_self", "kat_f_fk", "kat_f_comment",
  "vereinbarungen", "vereinbarungen_items", "themen_ma", "gespraechseindruck", "naechstes_bilat",
]

function bilatPayload(data) {
  return Object.fromEntries(BILAT_FIELD_KEYS.map(k => [k, data[k] ?? null]))
}

function emptyVereinbarung() {
  return { what: "", who: "", until: "" }
}

const FLOW_PHASE_LABEL = {
  fk_prep: "Schritt 1 — Führungskraft bereitet Einschätzung vor",
  ma_self: "Schritt 2 — Selbsteinschätzung im Gespräch (FK-Sicht ausgeblendet)",
  reveal: "Schritt 3 — Abgleich: Agenda, Qualis, Vereinbarungen",
  done: "Bilateral abgeschlossen",
}

function BilatDataPage() {
  const auth = useAuth()
  const years = useAvailableYears()
  const now = new Date()
  const defaultPeriod = `${now.getMonth() < 6 ? "HJ1" : "HJ2"} ${now.getFullYear()}`
  const [overview, setOverview] = useState([])
  const [selected, setSelected] = useState(null)
  const [bilatData, setBilatData] = useState({ flow_phase: "fk_prep", vereinbarungen_items: [emptyVereinbarung()] })
  const [faktenblatt, setFaktenblatt] = useState(null)
  const [faktenOpen, setFaktenOpen] = useState(true)
  const [msg, setMsg] = useState(null)
  const [year, setYear] = useState(now.getFullYear())
  const [period, setPeriod] = useState(defaultPeriod)
  const [periods, setPeriods] = useState([defaultPeriod])
  const [newPeriod, setNewPeriod] = useState("")
  const [showNewPeriod, setShowNewPeriod] = useState(false)
  const [saving, setSaving] = useState(false)
  const [wordLoading, setWordLoading] = useState(false)
  const [signForm, setSignForm] = useState({ fk_display_name: "", ma_confirm_name: "", notes: "" })
  const [fkOk, setFkOk] = useState(false)
  const [maOk, setMaOk] = useState(false)
  const [qualGoals, setQualGoals] = useState([])
  const [qualSigned, setQualSigned] = useState(null)

  const phase = bilatData.flow_phase || "fk_prep"
  const deviations = bilatData.deviations || {}
  const agenda = bilatData.agenda || deviations.categories || []
  const hasGrave = deviations.has_grave
  const showFaktenblatt = phase !== "ma_self"
  const vereinItems = bilatData.vereinbarungen_items?.length
    ? bilatData.vereinbarungen_items
    : [emptyVereinbarung()]

  useEffect(() => {
    api("/api/bilat-periods").then(p => { setPeriods(p); if (!p.includes(period)) setPeriod(p[0] || defaultPeriod) }).catch(e => setMsg({ type: "err", text: e.message }))
  }, [])

  useEffect(() => {
    if (period) api(`/api/bilat-overview/${year}/${encodeURIComponent(period)}`).then(setOverview).catch(e => setMsg({ type: "err", text: e.message }))
  }, [year, period])

  const loadFaktenblatt = (maName) => {
    api(`/api/bilat/${maName}/${year}/${encodeURIComponent(period)}/faktenblatt`)
      .then(setFaktenblatt)
      .catch(e => { setFaktenblatt(null); setMsg({ type: "err", text: e.message || "Gesprächsinfos nicht geladen" }) })
  }

  const loadQual = (maName) => {
    api(`/api/qual-goals/${maName}/${year}/${encodeURIComponent(period)}`)
      .then(d => {
        setQualGoals(d.goals || [])
        setQualSigned(d.signature || null)
      })
      .catch(e => {
        setQualGoals([])
        setQualSigned(null)
        setMsg({ type: "err", text: e.message || "Qualis nicht geladen" })
      })
  }

  const openBilat = async (ma) => {
    const data = await api(`/api/bilat/${ma.name}/${year}/${encodeURIComponent(period)}`).catch(() => ({ flow_phase: "fk_prep" }))
    const merged = {
      flow_phase: "fk_prep",
      vereinbarungen_items: [emptyVereinbarung()],
      ...(data || {}),
    }
    if (!merged.vereinbarungen_items?.length) merged.vereinbarungen_items = [emptyVereinbarung()]
    setBilatData(merged)
    setSelected(ma)
    setMsg(null)
    setFaktenOpen(true)
    setFkOk(false)
    setMaOk(false)
    setSignForm({
      fk_display_name: auth.user?.full_name || "",
      ma_confirm_name: ma.display_name || "",
      notes: "",
    })
    loadFaktenblatt(ma.name)
    loadQual(ma.name)
  }

  const setVereinItem = (idx, field, value) => {
    setBilatData(prev => {
      const items = [...(prev.vereinbarungen_items?.length ? prev.vereinbarungen_items : [emptyVereinbarung()])]
      items[idx] = { ...items[idx], [field]: value }
      return { ...prev, vereinbarungen_items: items }
    })
  }

  const updateQualStatus = async (idx, status, unlock = false) => {
    if (qualSigned && !unlock) {
      setMsg({ type: "err", text: "Qualis unterzeichnet — zuerst Bearbeitung freigeben." })
      return
    }
    const next = qualGoals.map((g, i) => i === idx ? { ...g, status } : g)
    setQualGoals(next)
    try {
      const res = await api(`/api/qual-goals/${selected.name}/${year}/${encodeURIComponent(period)}`, {
        method: "PUT",
        body: JSON.stringify({
          goals: next.filter(g => (g.name || "").trim()),
          unlock_signed: unlock,
        }),
      })
      if (unlock) setQualSigned(null)
      loadFaktenblatt(selected.name)
      if (unlock) setMsg({ type: "ok", text: res.message || "Bearbeitung freigegeben" })
    } catch (e) {
      setMsg({ type: "err", text: e.message })
      loadQual(selected.name)
    }
  }

  const unlockQualEdit = async () => {
    if (!confirm("Signatur ungültig machen und Quali-Status bearbeiten? Danach neu unterzeichnen.")) return
    try {
      const res = await api(`/api/qual-goals/${selected.name}/${year}/${encodeURIComponent(period)}`, {
        method: "PUT",
        body: JSON.stringify({
          goals: qualGoals.filter(g => (g.name || "").trim()),
          unlock_signed: true,
        }),
      })
      setQualSigned(null)
      setMsg({ type: "ok", text: res.message || "Bearbeitung freigegeben" })
      loadFaktenblatt(selected.name)
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    }
  }

  const signQualis = async () => {
    if (!fkOk || !maOk) {
      setMsg({ type: "err", text: "Bitte beide Bestätigungen (FK + MA) anhaken." })
      return
    }
    setSaving(true)
    try {
      const resBilat = await api(`/api/bilat/${selected.name}/${year}/${encodeURIComponent(period)}`, {
        method: "POST",
        body: JSON.stringify({ data: bilatPayload(bilatData) }),
      })
      setBilatData(resBilat)
      const res = await api(`/api/qual-goals/${selected.name}/${year}/${encodeURIComponent(period)}/sign`, {
        method: "POST",
        body: JSON.stringify({
          ...signForm,
          vereinbarungen: resBilat.vereinbarungen || "",
        }),
      })
      setQualSigned(res.signature || null)
      setMsg({ type: "ok", text: res.message || "Qualis unterzeichnet" })
      loadFaktenblatt(selected.name)
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const downloadWord = async () => {
    if (!selected || !faktenblatt?.through_month) return
    setWordLoading(true)
    try {
      const token = localStorage.getItem("token")
      const month = faktenblatt.through_month
      const res = await fetch(`${API}/api/export/bilat-single/${year}/${month}/${encodeURIComponent(selected.name)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error("Download fehlgeschlagen")
      const blob = await res.blob()
      const a = document.createElement("a")
      a.href = URL.createObjectURL(blob)
      a.download = `Bilat_${selected.display_name || selected.name}_${period}.docx`
      a.click()
    } catch (e) {
      setMsg({ type: "err", text: e.message || "Word-Download fehlgeschlagen" })
    } finally {
      setWordLoading(false)
    }
  }

  const save = async (flowAction = null) => {
    setSaving(true)
    try {
      const res = await api(`/api/bilat/${selected.name}/${year}/${encodeURIComponent(period)}`, {
        method: "POST",
        body: JSON.stringify({ data: bilatPayload(bilatData), flow_action: flowAction }),
      })
      setBilatData(res)
      setMsg({ type: "ok", text: flowAction ? "Phase gespeichert" : "Gespeichert" })
      api(`/api/bilat-overview/${year}/${encodeURIComponent(period)}`).then(setOverview)
      api("/api/bilat-periods").then(setPeriods)
      loadFaktenblatt(selected.name)
    } catch (e) {
      setMsg({ type: "err", text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const addPeriod = () => {
    if (!newPeriod.trim()) return
    const p = newPeriod.trim()
    setPeriods(prev => [...new Set([...prev, p])])
    setPeriod(p)
    setNewPeriod("")
    setShowNewPeriod(false)
  }

  const RatingButtons = ({ field, label, large = false }) => (
    <div style={{ marginBottom: large ? 20 : 16 }}>
      <div style={{ fontSize: large ? 14 : 12, fontWeight: 600, color: "#555", marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {[1, 2, 3, 4, 5].map(v => (
          <button key={v} onClick={() => setBilatData({ ...bilatData, [field]: bilatData[field] === v ? null : v })}
            style={{
              width: large ? 48 : 38, height: large ? 48 : 38,
              border: `2px solid ${bilatData[field] === v ? "#004869" : "#DDD"}`,
              borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: large ? 16 : 14,
              background: bilatData[field] === v ? "#004869" : "white",
              color: bilatData[field] === v ? "white" : "#555",
            }}>
            {v}
          </button>
        ))}
        {bilatData[field] && (
          <span style={{ fontSize: 12, color: "#004869", alignSelf: "center", marginLeft: 4 }}>
            {RATING_WORDS[bilatData[field]]}
          </span>
        )}
      </div>
    </div>
  )

  const FlowStepper = () => (
    <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
      {FLOW_STEPS.map((s, i) => {
        const active = s.id === phase
        const done = FLOW_STEPS.findIndex(x => x.id === phase) > i || phase === "done"
        return (
          <div key={s.id} style={{
            flex: "1 1 140px", padding: "10px 12px", borderRadius: 8, fontSize: 12, fontWeight: 600,
            background: active ? "#004869" : done ? "#E8F0F4" : "#F5F5F5",
            color: active ? "white" : done ? "#004869" : "#999",
          }}>
            {i + 1}. {s.label}
          </div>
        )
      })}
    </div>
  )

  if (selected) return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <button onClick={() => { setSelected(null); setMsg(null) }}
          style={{ background: "#EEE", border: "none", padding: "8px 16px", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>
          ← Zurück
        </button>
        <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: 0, fontSize: 22, fontWeight: 800 }}>
          Bilateral — {selected.display_name}
        </h1>
        <span style={{ color: "#888", fontSize: 13 }}>{period}</span>
      </div>

      <FlowStepper />
      <div style={{ background: "#F8FAFB", border: "1px solid #E4EEF3", borderRadius: 10, padding: "12px 16px", marginBottom: 20, fontSize: 13, color: "#004869" }}>
        {FLOW_PHASE_LABEL[phase] || phase}
      </div>

      {msg && (
        <div style={{
          background: msg.type === "ok" ? "#E8F8E8" : "#FFE8E8",
          color: msg.type === "ok" ? "#1a7a1a" : "#c0392b",
          padding: "10px 14px", borderRadius: 8, marginBottom: 16, fontSize: 13,
        }}>{msg.text}</div>
      )}

      {showFaktenblatt && (
        <div style={{ background: "white", borderRadius: 12, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", marginBottom: 20, overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 18px", background: "#F0F4F6", flexWrap: "wrap" }}>
            <button type="button" onClick={() => setFaktenOpen(o => !o)}
              style={{ background: "none", border: "none", cursor: "pointer", fontWeight: 800, fontSize: 14, color: "#004869", padding: 0 }}>
              {faktenOpen ? "▼" : "▶"} Gesprächsinfos (FK-intern)
            </button>
            <span style={{ fontSize: 12, color: "#888" }}>
              {faktenblatt ? `${faktenblatt.perf_range} · Ø ZEG-B ${faktenblatt.avg_zeg_pct}` : "Lade…"}
            </span>
            <button type="button" onClick={downloadWord} disabled={wordLoading || !faktenblatt}
              style={{ marginLeft: "auto", padding: "7px 14px", borderRadius: 8, border: "1px solid #004869", background: "white", color: "#004869", fontWeight: 700, fontSize: 12, cursor: "pointer" }}>
              {wordLoading ? "…" : "⬇ Word herunterladen"}
            </button>
          </div>
          {faktenOpen && faktenblatt && (
            <div style={{ padding: 18 }}>
              {faktenblatt.kpi_label && (
                <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>
                  Kennzahl: <strong style={{ color: "#004869" }}>{faktenblatt.kpi_label}</strong>
                </div>
              )}
              {faktenblatt.kpi_type === "mitglieder" ? (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ background: "#F0F4F6", borderRadius: 8, padding: "12px 14px", marginBottom: 10, fontSize: 13, color: "#555" }}>
                    Für diese Person gelten <strong>Mitgliederzahlen</strong>, kein Umsatz/ZEG.
                  </div>
                  {(faktenblatt.mitglieder_months || []).length === 0 ? (
                    <div style={{ fontSize: 13, color: "#888" }}>Noch keine Mitgliederzahlen — unter Daten eingeben erfassen.</div>
                  ) : (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr style={{ background: "#004869", color: "white" }}>
                          <th style={{ padding: "8px 10px", textAlign: "left" }}>Monat</th>
                          <th style={{ padding: "8px 10px", textAlign: "right" }}>Mitglieder</th>
                          <th style={{ padding: "8px 10px", textAlign: "left" }}>Notiz</th>
                        </tr>
                      </thead>
                      <tbody>
                        {faktenblatt.mitglieder_months.map((m, i) => (
                          <tr key={i} style={{ borderBottom: "1px solid #EEE" }}>
                            <td style={{ padding: "8px 10px" }}>{m.label}</td>
                            <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 700 }}>{m.count}</td>
                            <td style={{ padding: "8px 10px", color: "#666" }}>{m.notes || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: 13, fontWeight: 700, color: "#004869", marginBottom: 12 }}>
                  {faktenblatt.performance_comment}
                </div>
              )}

              {faktenblatt.kpi_type !== "mitglieder" && faktenblatt.kpi_type !== "keine" && (
              <div style={{ overflowX: "auto", marginBottom: 18 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: "#004869", color: "white" }}>
                      {["Monat", "ZEG-B", "vs. Ziel", "Soll", "Ferien", "Krank", "Prod-B", "Umsatz"].map(h => (
                        <th key={h} style={{ padding: "8px 10px", textAlign: h === "Monat" || h === "Umsatz" ? "left" : "center", fontWeight: 600 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(faktenblatt.months || []).map((m, i) => {
                      const c = ZEG_COLORS[m.color || "gray"]
                      return (
                        <tr key={m.month} style={{ background: i % 2 ? "#F8F9FA" : "white" }}>
                          <td style={{ padding: "8px 10px", fontWeight: 600 }}>{m.label}</td>
                          <td style={{ padding: "8px 10px", textAlign: "center" }}>
                            <span style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}`, borderRadius: 4, padding: "2px 8px", fontWeight: 700 }}>
                              {m.zeg_pct}
                            </span>
                          </td>
                          <td style={{ padding: "8px 10px", textAlign: "center", color: "#666" }}>{m.vs_ziel}</td>
                          <td style={{ padding: "8px 10px", textAlign: "center" }}>{m.soll_tage}</td>
                          <td style={{ padding: "8px 10px", textAlign: "center" }}>{m.ferien_t ? `-${m.ferien_t}` : "—"}</td>
                          <td style={{ padding: "8px 10px", textAlign: "center" }}>{m.krank_t ? `-${m.krank_t}` : "—"}</td>
                          <td style={{ padding: "8px 10px", textAlign: "center" }}>{m.prod_b != null ? m.prod_b : "—"}</td>
                          <td style={{ padding: "8px 10px", fontWeight: 600 }}>CHF {(m.umsatz || 0).toLocaleString("de-CH")}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              )}

              {(faktenblatt.qual_goals || []).length > 0 && (
                <div style={{ marginBottom: 18 }}>
                  <div style={{ fontWeight: 800, fontSize: 13, color: "#004869", marginBottom: 8 }}>Qualitative Ziele</div>
                  <div style={{ display: "grid", gap: 8 }}>
                    {faktenblatt.qual_goals.map((g, i) => (
                      <div key={i} style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12, padding: "8px 10px", background: "#F8FAFB", borderRadius: 8 }}>
                        <span style={{ fontWeight: 700, minWidth: 180 }}>{g.name}</span>
                        <span style={{ color: "#004869" }}>{g.result || "—"}</span>
                        <span style={{ color: "#888" }}>{g.status || ""}</span>
                        {g.detail && <span style={{ color: "#666" }}>{g.detail}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(faktenblatt.leitfaden_points || []).length > 0 && (
                <div>
                  <div style={{ fontWeight: 800, fontSize: 13, color: "#004869", marginBottom: 8 }}>Gesprächspunkte</div>
                  <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#333", lineHeight: 1.6 }}>
                    {faktenblatt.leitfaden_points.map((p, i) => (
                      <li key={i}>{p.replace(/^\d+\.\s*/, "")}</li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}
          {faktenOpen && !faktenblatt && (
            <div style={{ padding: 18, fontSize: 13, color: "#888" }}>Gesprächsinfos werden geladen…</div>
          )}
        </div>
      )}

      {/* Phase: FK Vorbereitung */}
      {phase === "fk_prep" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 20 }}>
            {KAT_KEYS_REQUIRED.map(k => (
              <div key={k} style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
                <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 16px", color: "#004869" }}>
                  Kat. {k.toUpperCase()} — {KAT_LABELS[k]}
                </h4>
                <RatingButtons field={`kat_${k}_fk`} label="Einschätzung Führungskraft (1–5)" />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>Notiz FK (optional)</div>
                  <textarea value={bilatData[`kat_${k}_comment`] || ""}
                    onChange={e => setBilatData({ ...bilatData, [`kat_${k}_comment`]: e.target.value })}
                    style={{ width: "100%", padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13, resize: "vertical", minHeight: 60, boxSizing: "border-box" }} />
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 20, fontSize: 13, fontWeight: 700, color: "#004869" }}>Optional — Kat. E/F</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 20, marginTop: 10 }}>
            {["e", "f"].map(k => (
              <div key={k} style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", opacity: 0.95 }}>
                <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 16px", color: "#004869" }}>
                  Kat. {k.toUpperCase()} — {KAT_LABELS[k]}
                </h4>
                <RatingButtons field={`kat_${k}_fk`} label="Einschätzung Führungskraft (1–5)" />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>Notiz FK (optional)</div>
                  <textarea value={bilatData[`kat_${k}_comment`] || ""}
                    onChange={e => setBilatData({ ...bilatData, [`kat_${k}_comment`]: e.target.value })}
                    style={{ width: "100%", padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13, resize: "vertical", minHeight: 60, boxSizing: "border-box" }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phase: MA Selbsteinschätzung — keine FK-Zahlen sichtbar */}
      {phase === "ma_self" && (
        <div>
          <div style={{
            background: "linear-gradient(135deg, #004869 0%, #006B8F 100%)", color: "white",
            borderRadius: 16, padding: "28px 32px", marginBottom: 24, textAlign: "center",
          }}>
            <div style={{ fontSize: 22, fontWeight: 800, marginBottom: 8 }}>Selbsteinschätzung</div>
            <div style={{ fontSize: 14, opacity: 0.9 }}>
              Bitte Gerät an {selected.display_name} wenden. Die Einschätzung der Führungskraft ist ausgeblendet.
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 20 }}>
            {KAT_KEYS_ALL.map(k => (
              <div key={k} style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
                <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 16px", color: "#004869" }}>
                  Kat. {k.toUpperCase()} — {KAT_LABELS[k]}
                  {!KAT_KEYS_REQUIRED.includes(k) && <span style={{ fontWeight: 500, color: "#888", fontSize: 12 }}> (optional)</span>}
                </h4>
                <RatingButtons field={`kat_${k}_self`} label="Wie schätzen Sie sich ein? (1–5)" large />
              </div>
            ))}
            <div style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", gridColumn: "1 / -1" }}>
              <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 16px", color: "#004869" }}>Themen & Wünsche</h4>
              <textarea value={bilatData.themen_ma || ""} onChange={e => setBilatData({ ...bilatData, themen_ma: e.target.value })}
                placeholder="Was liegt Ihnen auf dem Herzen?"
                style={{ width: "100%", padding: 12, border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14, resize: "vertical", minHeight: 100, boxSizing: "border-box" }} />
            </div>
          </div>
        </div>
      )}

      {/* Phase: Abgleich */}
      {phase === "reveal" && (
        <div>
          <div style={{ fontWeight: 800, fontSize: 15, color: "#004869", marginBottom: 12 }}>Gesprächsagenda</div>
          {hasGrave && (
            <div style={{ background: "#FFF8E1", border: "1px solid #FFE082", borderRadius: 10, padding: 14, marginBottom: 14, fontSize: 13, color: "#6D4C00" }}>
              Deutliche Abweichungen vorhanden — behutsam ansprechen, keine Skalen-Zahlen vorlesen.
            </div>
          )}
          <div style={{ display: "grid", gap: 12, marginBottom: 24 }}>
            {agenda.map(cat => (
              <div key={cat.cat} style={{
                background: "white", borderRadius: 12, padding: 18, boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                borderLeft: `4px solid ${cat.grave ? "#F57F17" : cat.gap === 0 ? "#2E7D32" : "#004869"}`,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
                  <div style={{ fontWeight: 800, color: "#004869", fontSize: 14 }}>
                    Kat. {cat.cat.toUpperCase()} — {cat.label}
                  </div>
                  <div style={{ fontSize: 12, color: cat.grave ? "#F57F17" : "#666", fontWeight: 600 }}>
                    {cat.gap === 0 ? "Übereinstimmung" : cat.grave ? "Deutliche Abweichung" : "Leichte Abweichung"}
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10, fontSize: 13 }}>
                  <div style={{ background: "#F8FAFB", borderRadius: 8, padding: "10px 12px" }}>
                    <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>Mitarbeiter/in</div>
                    <strong>{cat.self_label}</strong>
                  </div>
                  <div style={{ background: "#F0F4F6", borderRadius: 8, padding: "10px 12px" }}>
                    <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>Führungskraft</div>
                    <strong>{cat.fk_label}</strong>
                  </div>
                </div>
                {cat.comment && (
                  <div style={{ fontSize: 12, color: "#555", marginBottom: 8, fontStyle: "italic" }}>FK-Notiz: {cat.comment}</div>
                )}
                <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>{cat.hint}</div>
                <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13, color: "#333", lineHeight: 1.5 }}>
                  {(cat.talk_prompts || []).map((q, i) => <li key={i}>{q}</li>)}
                </ul>
              </div>
            ))}
          </div>

          {bilatData.themen_ma && (
            <div style={{ background: "white", borderRadius: 12, padding: 16, marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <div style={{ fontWeight: 800, color: "#004869", marginBottom: 8, fontSize: 14 }}>Themen vom MA</div>
              <div style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>{bilatData.themen_ma}</div>
            </div>
          )}

          <div style={{ background: "white", borderRadius: 12, padding: 18, marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <div style={{ fontWeight: 800, color: "#004869", marginBottom: 8, fontSize: 14 }}>Qualitative Ziele</div>
            {qualGoals.length === 0 ? (
              <div style={{ fontSize: 13, color: "#888" }}>
                Noch keine Qualis — unter Quali-Themen pflegen, dann hier Status setzen und unterzeichnen.
              </div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {qualGoals.map((g, i) => (
                  <div key={i} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", padding: "8px 10px", background: "#F8FAFB", borderRadius: 8, fontSize: 13 }}>
                    <span style={{ fontWeight: 700, flex: "1 1 160px" }}>{g.name}</span>
                    <span style={{ color: "#004869" }}>{g.result || "—"}</span>
                    <select value={g.status || "offen"} onChange={e => updateQualStatus(i, e.target.value)}
                      disabled={!!qualSigned}
                      style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12, opacity: qualSigned ? 0.7 : 1 }}>
                      {QUAL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                ))}
              </div>
            )}
            {qualSigned ? (
              <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                <div style={{ fontSize: 12, color: "#1a7a1a", fontWeight: 600 }}>
                  ✓ Qualis unterzeichnet ({qualSigned.fk_display_name} / {qualSigned.ma_display_name})
                </div>
                <button type="button" onClick={unlockQualEdit}
                  style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #c0392b", background: "white", color: "#c0392b", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                  Bearbeitung freigeben
                </button>
              </div>
            ) : qualGoals.length > 0 && (
              <div style={{ marginTop: 14, borderTop: "1px solid #EEE", paddingTop: 14 }}>
                <div style={{ fontSize: 12, color: "#888", marginBottom: 10 }}>Am Ende unterzeichnen (PDF → Ablage)</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
                  <input value={signForm.fk_display_name} onChange={e => setSignForm({ ...signForm, fk_display_name: e.target.value })}
                    placeholder="Name FK" style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                  <input value={signForm.ma_confirm_name} onChange={e => setSignForm({ ...signForm, ma_confirm_name: e.target.value })}
                    placeholder="Name MA" style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                </div>
                <label style={{ display: "flex", gap: 8, fontSize: 12, marginBottom: 6, cursor: "pointer" }}>
                  <input type="checkbox" checked={fkOk} onChange={e => setFkOk(e.target.checked)} /> FK bestätigt
                </label>
                <label style={{ display: "flex", gap: 8, fontSize: 12, marginBottom: 10, cursor: "pointer" }}>
                  <input type="checkbox" checked={maOk} onChange={e => setMaOk(e.target.checked)} /> MA bestätigt
                </label>
                <button type="button" onClick={signQualis} disabled={saving}
                  style={{ padding: "9px 16px", borderRadius: 8, border: "none", background: "#004869", color: "white", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
                  Qualis unterzeichnen & PDF ablegen
                </button>
              </div>
            )}
          </div>

          <div style={{ background: "white", borderRadius: 12, padding: 24, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 16px", color: "#004869" }}>Abschluss des Gesprächs</h4>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 8 }}>Gesprächseindruck</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {["Konstruktiv", "Offen", "Angespannt"].map(v => (
                  <button key={v} onClick={() => setBilatData({ ...bilatData, gespraechseindruck: bilatData.gespraechseindruck === v ? null : v })}
                    style={{
                      padding: "7px 14px", border: `2px solid ${bilatData.gespraechseindruck === v ? "#004869" : "#DDD"}`,
                      borderRadius: 8, cursor: "pointer", fontSize: 13,
                      background: bilatData.gespraechseindruck === v ? "#E4EEF3" : "white",
                      color: bilatData.gespraechseindruck === v ? "#004869" : "#555",
                    }}>{v}</button>
                ))}
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 6 }}>Nächstes Bilat-Datum</div>
              <input type="date" value={bilatData.naechstes_bilat || ""} onChange={e => setBilatData({ ...bilatData, naechstes_bilat: e.target.value })}
                style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 8 }}>Vereinbarungen (Was / Wer / Bis wann)</div>
            {vereinItems.map((it, i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginBottom: 8 }}>
                <input value={it.what || ""} onChange={e => setVereinItem(i, "what", e.target.value)}
                  placeholder={`Vereinbarung ${i + 1}`}
                  style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                <input value={it.who || ""} onChange={e => setVereinItem(i, "who", e.target.value)}
                  placeholder="Wer"
                  style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                <input type="date" value={it.until || ""} onChange={e => setVereinItem(i, "until", e.target.value)}
                  style={{ padding: "8px 10px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 13 }} />
                <button type="button"
                  onClick={() => setBilatData({
                    ...bilatData,
                    vereinbarungen_items: vereinItems.length <= 1
                      ? [emptyVereinbarung()]
                      : vereinItems.filter((_, j) => j !== i),
                  })}
                  style={{ padding: "8px 10px", border: "1px solid #DDD", borderRadius: 8, background: "white", cursor: "pointer", color: "#c0392b", fontSize: 12 }}>
                  ×
                </button>
              </div>
            ))}
            <button type="button"
              onClick={() => setBilatData({ ...bilatData, vereinbarungen_items: [...vereinItems, emptyVereinbarung()] })}
              style={{ marginTop: 4, padding: "6px 12px", borderRadius: 6, border: "1px solid #DDD", background: "white", cursor: "pointer", fontSize: 12 }}>
              + Punkt hinzufügen
            </button>
          </div>
        </div>
      )}

      {/* Phase: Abgeschlossen — volle Ansicht für FK */}
      {phase === "done" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
            {agenda.length > 0 ? agenda.map(cat => (
              <div key={cat.cat} style={{ background: "white", borderRadius: 12, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
                <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 12px", color: "#004869" }}>
                  Kat. {cat.cat.toUpperCase()} — {cat.label}
                </h4>
                <div style={{ fontSize: 13, marginBottom: 6 }}>MA: <strong>{cat.self_label}</strong></div>
                <div style={{ fontSize: 13, marginBottom: 8 }}>FK: <strong>{cat.fk_label}</strong></div>
                {cat.comment && <div style={{ fontSize: 12, color: "#666" }}>{cat.comment}</div>}
              </div>
            )) : KAT_KEYS_ALL.map(k => (
              <div key={k} style={{ background: "white", borderRadius: 12, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
                <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif", margin: "0 0 12px", color: "#004869" }}>
                  Kat. {k.toUpperCase()} — {KAT_LABELS[k]}
                </h4>
                <div style={{ fontSize: 13, marginBottom: 6 }}>
                  MA: <strong>{bilatData[`kat_${k}_self`] ? RATING_WORDS[bilatData[`kat_${k}_self`]] : "—"}</strong>
                </div>
                <div style={{ fontSize: 13 }}>
                  FK: <strong>{bilatData[`kat_${k}_fk`] ? RATING_WORDS[bilatData[`kat_${k}_fk`]] : "—"}</strong>
                </div>
              </div>
            ))}
          </div>
          {bilatData.vereinbarungen && (
            <div style={{ background: "white", borderRadius: 12, padding: 18, marginBottom: 16, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <div style={{ fontWeight: 800, color: "#004869", marginBottom: 8 }}>Vereinbarungen</div>
              <pre style={{ margin: 0, fontFamily: "inherit", fontSize: 13, whiteSpace: "pre-wrap" }}>{bilatData.vereinbarungen}</pre>
            </div>
          )}
          {qualGoals.length > 0 && (
            <div style={{ background: "white", borderRadius: 12, padding: 18, marginBottom: 16, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <div style={{ fontWeight: 800, color: "#004869", marginBottom: 8 }}>
                Qualis {qualSigned ? "· unterzeichnet" : ""}
              </div>
              {qualGoals.map((g, i) => (
                <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                  <strong>{g.name}</strong> — {g.status || "offen"} {g.result ? `(${g.result})` : ""}
                </div>
              ))}
            </div>
          )}
          {(bilatData.gespraechseindruck || bilatData.naechstes_bilat) && (
            <div style={{ fontSize: 13, color: "#555" }}>
              {bilatData.gespraechseindruck && <span>Eindruck: <strong>{bilatData.gespraechseindruck}</strong></span>}
              {bilatData.naechstes_bilat && <span style={{ marginLeft: 16 }}>Nächstes Bilat: <strong>{bilatData.naechstes_bilat}</strong></span>}
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 20, display: "flex", gap: 12, flexWrap: "wrap" }}>
        {phase === "fk_prep" && (
          <>
            <button onClick={() => save()} disabled={saving}
              style={{ padding: "12px 24px", background: "#EEE", color: "#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>
              Zwischenspeichern
            </button>
            <button onClick={() => save("submit_fk")} disabled={saving}
              style={{ padding: "12px 32px", background: "#004869", color: "white", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 15 }}>
              Für Gespräch freigeben →
            </button>
          </>
        )}
        {phase === "ma_self" && (
          <button onClick={() => save("submit_self")} disabled={saving}
            style={{ padding: "12px 32px", background: "#004869", color: "white", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 15 }}>
            Selbsteinschätzung abschliessen →
          </button>
        )}
        {phase === "reveal" && (
          <>
            <button onClick={() => save()} disabled={saving}
              style={{ padding: "12px 24px", background: "#EEE", color: "#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>
              Zwischenspeichern
            </button>
            <button onClick={() => save("complete_reveal")} disabled={saving}
              style={{ padding: "12px 32px", background: "#004869", color: "white", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 15 }}>
              Gespräch abschliessen
            </button>
          </>
        )}
        {phase === "done" && (
          <button onClick={() => save()} disabled={saving}
            style={{ padding: "12px 32px", background: "#004869", color: "white", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 15 }}>
            Speichern
          </button>
        )}
      </div>
    </div>
  )

  const selectStyle = { padding: "6px 10px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12, background: "white", color: "#333" }

  // Overview
  const teams = [...new Set(overview.map(m=>m.team))]
  return (
    <div>
      <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 8px",fontSize:24,fontWeight:800}}>Bilaterals</h1>
      <div style={{color:"#888",marginBottom:18,fontSize:13}}>Bewertungen erfassen und speichern</div>

      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Jahr:
          <YearSelect value={year} onChange={y => {
            setYear(y)
            const half = period.includes("HJ2") || period.startsWith("2.") ? "HJ2" : "HJ1"
            const next = `${half} ${y}`
            setPeriod(next)
            setPeriods(prev => prev.includes(next) ? prev : [...prev, next])
          }} years={years} style={selectStyle} />
        </label>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Periode:
          <select value={period} onChange={e => setPeriod(e.target.value)} style={selectStyle}>
            {periods.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <button onClick={() => setShowNewPeriod(!showNewPeriod)} style={{ ...selectStyle, cursor: "pointer", fontWeight: 600 }}>
          + Neue Periode
        </button>
        {showNewPeriod && (
          <>
            <input value={newPeriod} onChange={e => setNewPeriod(e.target.value)} placeholder="z.B. HJ1 2027"
              style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12 }} />
            <button onClick={addPeriod} style={{ padding: "6px 14px", background: "#004869", color: "white", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
              Hinzufügen
            </button>
          </>
        )}
      </div>

      <div style={{color:"#888",marginBottom:28,fontSize:13}}>{period} — Übersicht nach Standort</div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(320px,1fr))",gap:20}}>
        {teams.map(team=>{
          const teamMAs=overview.filter(m=>m.team===team)
          const done=teamMAs.filter(m=>m.has_data).length
          return (
            <div key={team} style={{background:"white",borderRadius:12,overflow:"hidden",boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
              <div style={{background:"#004869",padding:"14px 20px",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <span style={{fontWeight:800,color:"white",fontSize:14}}>{team}</span>
                <span style={{color:"rgba(255,255,255,0.8)",fontSize:12}}>{done}/{teamMAs.length} erfasst</span>
              </div>
              {teamMAs.map(ma=>(
                <div key={ma.name} onClick={()=>openBilat(ma)} style={{
                  display:"flex",justifyContent:"space-between",alignItems:"center",
                  padding:"12px 20px",borderBottom:"1px solid #F5F5F5",cursor:"pointer"
                }} onMouseEnter={e=>e.currentTarget.style.background="#F8F9FA"}
                   onMouseLeave={e=>e.currentTarget.style.background="white"}>
                  <div>
                    <div style={{fontSize:13,fontWeight:600}}>{ma.display_name}</div>
                    <div style={{fontSize:11,color:"#888",marginTop:2}}>
                      {ma.kpi_label ? `${ma.kpi_label} · ` : ""}
                      {ma.flow_phase === "fk_prep" && "FK vorbereiten"}
                      {ma.flow_phase === "ma_self" && "Selbsteinschätzung offen"}
                      {ma.flow_phase === "reveal" && "Abgleich"}
                      {ma.flow_phase === "done" && "Abgeschlossen"}
                      {!ma.flow_phase && "Neu"}
                    </div>
                  </div>
                  <span style={{
                    background:ma.has_data?"#E8F8E8":"#F5F5F5",
                    color:ma.has_data?"#1a7a1a":"#999",
                    padding:"4px 12px",borderRadius:20,fontSize:11,fontWeight:700
                  }}>{ma.has_data?"✓ Erfasst":"Offen"}</span>
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Umsatzlohn Rechner ─────────────────────────────────────────────────────
function LohnrechnerPage() {
  const years = useAvailableYears()
  const [dataYear, setDataYear] = useState(DEFAULT_YEAR)
  const [params, setParams] = useState({
    umsatz: 0, bg_pct: 100, ziel_chf: 1040, lohnquote: 40,
    fixlohn: 5000, zeg_schwelle: 85, bonus_ab: 100
  })
  const [maList, setMaList] = useState([])
  const [selectedMA, setSelectedMA] = useState(null)
  const [ytdData, setYtdData] = useState(null)
  const [ytdLoading, setYtdLoading] = useState(true)

  useEffect(() => { api("/api/ma").then(setMaList).catch(console.error) }, [])

  useEffect(() => {
    let active = true
    setYtdLoading(true)
    setYtdData(null)
    api(`/api/ytd/${dataYear}`)
      .then(d => { if (active && d?.year === dataYear) setYtdData(d) })
      .catch(console.error)
      .finally(() => { if (active) setYtdLoading(false) })
    return () => { active = false }
  }, [dataYear])

  const p = params
  const brutto_ziel = p.fixlohn / (p.lohnquote/100)
  const umsatz_fuer_fixlohn = p.fixlohn / (p.lohnquote/100)
  const prod_tage_monat = (p.bg_pct/100) * 20 * 0.85  // ~85% nach Abzügen
  const soll_umsatz = prod_tage_monat * p.ziel_chf
  const zeg_b = p.umsatz > 0 ? p.umsatz / prod_tage_monat / p.ziel_chf : 0
  const lohn_variabel = p.umsatz * (p.lohnquote/100)
  const lohn_diff = lohn_variabel - p.fixlohn
  const ist_plus = lohn_diff > 0

  const set = (k,v) => setParams({...params,[k]:+v})

  const inp = (k,min=0,max=999999,step=100) => (
    <input type="number" min={min} max={max} step={step} value={params[k]}
      onChange={e=>set(k,e.target.value)}
      style={{padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:14,width:110}} />
  )

  const Card = ({title,value,sub,color="#1a1a1a",bg="white"}) => (
    <div style={{background:bg,borderRadius:10,padding:"18px 20px",boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
      <div style={{fontSize:11,fontWeight:700,color:"#888",textTransform:"uppercase",letterSpacing:0.5,marginBottom:4}}>{title}</div>
      <div style={{fontSize:22,fontWeight:800,color}}>{value}</div>
      {sub && <div style={{fontSize:12,color:"#888",marginTop:4}}>{sub}</div>}
    </div>
  )

  const chf = v => `CHF ${Math.round(v).toLocaleString("de-CH")}`

  // MA-specific calculation
  const maCalc = selectedMA && ytdData ? (() => {
    const ma = ytdData.ma_data?.find(m=>m.name===selectedMA)
    if (!ma) return null
    const months = ma.monthly?.filter(m=>m) || []
    const avgZeg = ma.avg_zeg_b || 0
    const totalUmsatz = ma.total_umsatz || 0
    const avgMonthlyUmsatz = months.length ? totalUmsatz/months.length : 0
    const lohnVar = avgMonthlyUmsatz * (p.lohnquote/100)
    const maObj = maList.find(m=>m.name===selectedMA)
    const bgPct = maObj?.bg_pct || 1
    const fixlohn_adj = p.fixlohn * bgPct
    return { avgZeg, totalUmsatz, avgMonthlyUmsatz, lohnVar, fixlohn_adj, bgPct, months: months.length }
  })() : null

  return (
    <div>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:28,flexWrap:"wrap",gap:12}}>
        <div>
          <h1 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 8px",fontSize:24,fontWeight:800}}>🧮 Umsatzlohn-Rechner</h1>
          <div style={{color:"#888",fontSize:13}}>Simulation Umsatzlohnmodell — {params.lohnquote}% Bruttolohnquote</div>
        </div>
        <label style={{fontSize:12,color:"#888",display:"flex",alignItems:"center",gap:6}}>
          Ist-Daten:
          <YearSelect value={dataYear} onChange={setDataYear} years={years} />
        </label>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"320px 1fr",gap:24}}>
        {/* Parameter */}
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)",height:"fit-content"}}>
          <h3 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 20px",color:"#004869"}}>Parameter</h3>
          {[
            ["umsatz","Monatsumsatz (CHF)",0,100000,500],
            ["bg_pct","Beschäftigungsgrad (%)",10,100,10],
            ["ziel_chf","Ziel CHF / produktiver Tag",800,1500,20],
            ["lohnquote","Bruttolohnquote (%)",30,60,5],
            ["fixlohn","Fixlohn (CHF/Monat, 100%)",3000,10000,100],
          ].map(([k,l,mn,mx,st])=>(
            <div key={k} style={{marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:6}}>{l}</div>
              <div style={{display:"flex",alignItems:"center",gap:10}}>
                <input type="range" min={mn} max={mx} step={st} value={params[k]}
                  onChange={e=>set(k,e.target.value)} style={{flex:1,accentColor:"#004869"}} />
                <span style={{fontSize:14,fontWeight:700,color:"#004869",minWidth:60,textAlign:"right"}}>
                  {k==="umsatz"||k==="fixlohn"||k==="ziel_chf"?`CHF ${Number(params[k]).toLocaleString("de-CH")}`:params[k]+"%"}
                </span>
              </div>
            </div>
          ))}

          <div style={{borderTop:"1px solid #EEE",paddingTop:16,marginTop:8}}>
            <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:8}}>MA aus Daten simulieren:</div>
            <select value={selectedMA||""} onChange={e=>setSelectedMA(e.target.value||null)}
              style={{width:"100%",padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13}}>
              <option value="">— Manuell —</option>
              {maList.map(m=><option key={m.name} value={m.name}>{m.display_name}</option>)}
            </select>
          </div>
        </div>

        {/* Results */}
        <div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:16,marginBottom:20}}>
            <Card title="ZEG-B (simuliert)" value={`${(zeg_b*100).toFixed(1)}%`}
              color={zeg_b>=1?"#1a7a1a":zeg_b>=0.85?"#856404":"#c0392b"}
              bg={zeg_b>=1?"#E8F8E8":zeg_b>=0.85?"#FFF8E0":"#FFE8E8"} />
            <Card title="Soll-Umsatz" value={chf(soll_umsatz)} sub={`${(p.bg_pct/100*20*0.85).toFixed(1)} Prod-Tage × CHF ${p.ziel_chf}`} />
            <Card title="Lohn variabel" value={chf(lohn_variabel)} sub={`${p.lohnquote}% von CHF ${Number(p.umsatz).toLocaleString("de-CH")}`} />
          </div>

          {/* Vergleich Fix vs Variabel */}
          <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)",marginBottom:20}}>
            <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 20px",color:"#004869"}}>Fix vs. Variabel — Vergleich</h4>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:16}}>
              {[
                ["Fixlohn (aktuell)",chf(p.fixlohn),"#555"],
                ["Variabel-Lohn",chf(lohn_variabel),lohn_variabel>=p.fixlohn?"#1a7a1a":"#c0392b"],
                ["Differenz",(ist_plus?"+":"")+chf(lohn_diff),ist_plus?"#1a7a1a":"#c0392b"],
              ].map(([l,v,c])=>(
                <div key={l} style={{textAlign:"center",padding:"16px",background:"#F8F9FA",borderRadius:10}}>
                  <div style={{fontSize:11,color:"#888",fontWeight:600,marginBottom:8,textTransform:"uppercase"}}>{l}</div>
                  <div style={{fontSize:20,fontWeight:800,color:c}}>{v}</div>
                </div>
              ))}
            </div>
            <div style={{marginTop:16,padding:"12px 16px",background:"#F0F8F0",borderRadius:8,fontSize:13}}>
              <strong>Break-Even Umsatz:</strong> MA muss <strong>{chf(p.fixlohn/(p.lohnquote/100))}</strong> Umsatz erzielen damit Variabel = Fixlohn
              {" "}→ entspricht ZEG-B von <strong>{(p.fixlohn/(p.lohnquote/100)/prod_tage_monat/p.ziel_chf*100).toFixed(1)}%</strong>
            </div>
          </div>

          {/* MA-spezifische Simulation */}
          {maCalc && (
            <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
              <h4 style={{ fontFamily: "'Roboto Condensed', sans-serif",margin:"0 0 16px",color:"#004869"}}>📊 {selectedMA} — Simulation mit Ist-Daten {dataYear}</h4>
              <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12}}>
                {[
                  ["Ø Monats-Umsatz",chf(maCalc.avgMonthlyUmsatz)],
                  ["Ø ZEG-B",`${(maCalc.avgZeg*100).toFixed(1)}%`],
                  ["Fixlohn (adj.)",chf(maCalc.fixlohn_adj)],
                  ["Variabel-Lohn",chf(maCalc.lohnVar)],
                ].map(([l,v])=>(
                  <div key={l} style={{textAlign:"center",padding:"14px",background:"#F8F9FA",borderRadius:8}}>
                    <div style={{fontSize:11,color:"#888",fontWeight:600,marginBottom:6}}>{l}</div>
                    <div style={{fontSize:16,fontWeight:800,color:"#004869"}}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{marginTop:14,padding:"12px 16px",background:maCalc.lohnVar>=maCalc.fixlohn_adj?"#E8F8E8":"#FFE8E8",borderRadius:8,fontSize:13,color:maCalc.lohnVar>=maCalc.fixlohn_adj?"#1a7a1a":"#c0392b"}}>
                <strong>{maCalc.lohnVar>=maCalc.fixlohn_adj?"✓":"⚠"} {selectedMA}:</strong>{" "}
                Mit Variabellohn würde {maCalc.lohnVar>=maCalc.fixlohn_adj?"mehr":"weniger"} verdient als mit Fixlohn
                {" "}(Differenz: {maCalc.lohnVar>=maCalc.fixlohn_adj?"+":""}{chf(maCalc.lohnVar-maCalc.fixlohn_adj)}/Monat)
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Root App ───────────────────────────────────────────────────────────────
export default function App() {
  const params = new URLSearchParams(window.location.search)
  const resetToken = params.get("reset")
  const showForgot = params.get("forgot") === "1"

  const [user, setUser] = useState(() => {
    const token = localStorage.getItem("token")
    if (!token) return null
    try {
      const payload = JSON.parse(atob(token.split(".")[1]))
      if (payload.exp * 1000 < Date.now()) { localStorage.clear(); return null }
      return JSON.parse(localStorage.getItem("user") || "null")
    } catch { return null }
  })
  const [page, setPage] = useState("dashboard")

  const RESTRICTED_PAGES = useMemo(() => new Set(["upload", "exports", "lohnrechner", "admin"]), [])

  useEffect(() => {
    if (user && RESTRICTED_PAGES.has(page) && !hasFullAccess(user.role)) {
      setPage("dashboard")
    }
  }, [user, page, RESTRICTED_PAGES])

  const handleLogin = (userData) => {
    setUser(userData)
    localStorage.setItem("user", JSON.stringify(userData))
  }
  const logout = () => { localStorage.clear(); setUser(null) }

  const clearAuthQuery = () => { window.history.replaceState({}, "", window.location.pathname) }

  if (!user && resetToken) {
    return <ResetPasswordPage token={resetToken} onDone={() => { clearAuthQuery(); window.location.reload() }} />
  }
  if (!user && showForgot) {
    return <ForgotPasswordPage onBack={() => { clearAuthQuery() }} />
  }
  if (!user) return <LoginPage onLogin={handleLogin} />

  const pages = { dashboard: DashboardPage, upload: UploadPage, overview: OverviewPage, exports: ExportsPage, admin: AdminPage, bilats: BilatDataPage, qualziele: QualGoalsPage, ablage: DocumentsPage, lohnrechner: LohnrechnerPage, profil: ProfilPage }
  const PageComponent = pages[page] || DashboardPage

  return (
    <AuthCtx.Provider value={{ user, logout }}>
      <Layout page={page} setPage={setPage}>
        <PageComponent />
      </Layout>
    </AuthCtx.Provider>
  )
}
