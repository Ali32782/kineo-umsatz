import { useState, useEffect, createContext, useContext } from "react"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"
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
        <span>🔔</span>
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
          <div style={{ background: "#1C5B7A", color: "white", padding: "14px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontWeight: 700 }}>🔔 Hinweise ({count})</span>
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
                          style={{ background: "none", border: "none", color: "#1C5B7A", cursor: "pointer", fontWeight: 700, fontSize: 12, padding: "0 4px" }}>
                          → Admin öffnen
                        </button>
                      </div>
                    )}
                    {n.type === "missing_schedule" && (
                      <div style={{ fontSize: 12, color: "#555", marginTop: 4 }}>
                        Arbeitstag-Muster für {n.detail} fehlt noch.
                        <button onClick={() => { setPage("admin"); markRead(n.id); setOpen(false) }}
                          style={{ background: "none", border: "none", color: "#1C5B7A", cursor: "pointer", fontWeight: 700, fontSize: 12, padding: "0 4px" }}>
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
  const nav = [
    { id: "dashboard", label: "Dashboard", icon: "📊" },
    { id: "upload", label: "Daten eingeben", icon: "📥", roles: ["ceo","bd"] },
    { id: "overview", label: "Jahresübersicht", icon: "📈" },
    { id: "exports", label: "Exporte", icon: "⬇️", roles: ["ceo"] },
    { id: "bilats", label: "Bilaterals", icon: "📋" },
    { id: "lohnrechner", label: "Lohnrechner", icon: "🧮", roles: ["ceo"] },
    { id: "profil", label: "Profil", icon: "👤" },
    { id: "admin", label: "Admin", icon: "⚙️", roles: ["ceo"] },
  ].filter(n => !n.roles || n.roles.includes(auth.user?.role))

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#F2F5F7", fontFamily: "Inter, system-ui, sans-serif" }}>
      {/* Sidebar */}
      <div style={{ width: 220, background: "#0F3A50", color: "white", flexShrink: 0, display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "28px 20px 24px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
          <div style={{fontWeight:800,fontSize:18,letterSpacing:3,color:"white"}}>KINEO</div>
          <div style={{ fontSize: 10, opacity: 0.45, marginTop: 8, letterSpacing: 2, textTransform: "uppercase", fontFamily: "Inter, system-ui, sans-serif" }}>Kineo Analytics</div>
          {auth.user?.role === "ceo" && <NotificationBell setPage={setPage} />}
        </div>
        <nav style={{ flex: 1 }}>
          {nav.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)} style={{
              width: "100%", padding: "11px 20px", background: page === n.id ? "rgba(255,255,255,0.12)" : "transparent",
              border: "none", borderLeft: page === n.id ? "3px solid #7BBFD4" : "3px solid transparent",
              color: page === n.id ? "white" : "rgba(255,255,255,0.7)", textAlign: "left", cursor: "pointer", fontSize: 13,
              display: "flex", alignItems: "center", gap: 10, letterSpacing: 0.2,
            }}>
              <span>{n.icon}</span>{n.label}
            </button>
          ))}
        </nav>
        <div style={{ padding: "16px 20px", borderTop: "1px solid rgba(255,255,255,0.15)" }}>
          <div style={{ fontSize: 12, opacity: 0.8 }}>{auth.user?.full_name}</div>
          <div style={{ fontSize: 11, opacity: 0.5, marginBottom: 8 }}>{auth.user?.role?.toUpperCase()}</div>
          <button onClick={auth.logout} style={{
            background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)",
            color: "white", padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12
          }}>Abmelden</button>
        </div>
      </div>
      {/* Main */}
      <div style={{ flex: 1, overflow: "auto" }}>
        <div style={{ padding: "32px 36px" }}>{children}</div>
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
    <div style={{ minHeight: "100vh", background: "linear-gradient(135deg,#1C5B7A,#0F3A50)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "white", borderRadius: 10, padding: "48px 40px", width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🏥</div>
          <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "'Barlow Condensed', sans-serif", color: "#1C5B7A" }}>KINEO AG</div>
          <div style={{ fontSize: 13, color: "#888", marginTop: 4 }}>Kineo Analytics</div>
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
            width: "100%", padding: "12px", background: "#1C5B7A", color: "white",
            border: "none", borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: "pointer", marginTop: 8
          }}>{loading ? "Anmelden…" : "Anmelden"}</button>
        </form>
        <div style={{ textAlign: "center", marginTop: 20, fontSize: 11, color: "#AAA" }}>
          Standard: ali / sereina / martino — Passwort: kineo2026
        </div>
      </div>
    </div>
  )
}

// ── Dashboard Page ─────────────────────────────────────────────────────────
function DashboardPage() {
  const now = new Date()
  const [year, setYear] = useState(2026)
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
    .filter(([t]) => t !== "Management")
    .sort(([,a],[,b]) => (b.zeg_b_avg||0) - (a.zeg_b_avg||0))

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontFamily: "'Barlow Condensed', sans-serif", margin: 0, fontSize: 24, color: "#1a1a1a", fontWeight: 800 }}>Dashboard</h1>
          <div style={{ fontSize: 13, color: "#888", marginTop: 4 }}>ZEG-B Übersicht pro Standort und Mitarbeiter</div>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <select value={month} onChange={e => setMonth(+e.target.value)}
            style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14 }}>
            {months.map((m,i) => <option key={i+1} value={i+1}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(+e.target.value)}
            style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8, fontSize: 14 }}>
            <option value={2026}>2026</option>
          </select>
        </div>
      </div>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginBottom: 28 }}>
        {[
          { label: "Gesamtumsatz", value: `CHF ${(data.total_umsatz||0).toLocaleString("de-CH")}`, icon: "💰" },
          { label: "Aktive MA", value: data.ma_data?.length || 0, icon: "👥" },
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
          const c = ZEG_COLORS[stats.color || "gray"]
          return (
            <div key={team} style={{ background: "white", borderRadius: 8, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <div style={{ background: c.bg, borderBottom: `3px solid ${c.border}`, padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 16, fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.05em", color: "#1a1a1a" }}>{team}</div>
                  <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
                    CHF {(stats.umsatz||0).toLocaleString("de-CH")}
                  </div>
                </div>
                <ZEGBadge value={stats.zeg_b_avg} color={stats.color} size="lg" />
              </div>
              <div style={{ padding: "12px 20px" }}>
                {/* FTE Total */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "2px solid #EEE", marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#1C5B7A", textTransform: "uppercase", letterSpacing: 0.5 }}>FTE Total</span>
                  <span style={{ fontSize: 14, fontWeight: 800, color: "#1C5B7A" }}>
                    {teamMAs.reduce((s, ma) => s + (ma.bg_pct||0), 0).toFixed(1)}
                  </span>
                </div>
                {/* MA rows: FTE% + Name + ZEG */}
                {teamMAs.map(ma => (
                  <div key={ma.name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: "1px solid #F5F5F5" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "#888", minWidth: 30 }}>{(ma.bg_pct*100).toFixed(0)}%</span>
                      <span style={{ fontSize: 12, color: "#333" }}>{ma.display_name}</span>
                    </div>
                    <ZEGBadge value={ma.zeg_b} color={ma.color} />
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
  const [year, setYear] = useState(2026)
  const [month, setMonth] = useState(5)
  const [step, setStep] = useState(1)
  const [csvFile, setCsvFile] = useState(null)
  const [csvPreview, setCsvPreview] = useState(null)
  const [maList, setMaList] = useState([])
  const [inputs, setInputs] = useState({})
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const months = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]

  useEffect(() => { api("/api/ma").then(setMaList).catch(console.error) }, [])
  useEffect(() => {
    api(`/api/inputs/${year}/${month}`).then(data => {
      setInputs(data)
    }).catch(console.error)
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
    if (res.ok) { setCsvPreview(data.data); setMsg({ type: "ok", text: data.message }); setStep(2) }
    else { setMsg({ type: "err", text: data.detail }) }
    setSaving(false)
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
    } catch (e) { setMsg({ type: "err", text: e.message }) }
    setSaving(false)
  }

  const inputField = (maName, field, label, step = "0.5") => {
    const val = inputs[maName]?.[field] || ""
    return (
      <input
        type="number" min="0" step={step} value={val}
        onChange={e => setInputs(prev => ({
          ...prev,
          [maName]: { ...(prev[maName] || {}), [field]: e.target.value }
        }))}
        style={{ width: "100%", padding: "5px 8px", border: "1px solid #DDD", borderRadius: 6, fontSize: 12, textAlign: "center" }}
        placeholder="0"
      />
    )
  }

  return (
    <div>
      <h1 style={{ margin: "0 0 8px", fontSize: 26, fontWeight: 700, fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.03em" }}>Daten eingeben</h1>
      <div style={{ color: "#888", marginBottom: 28, fontSize: 13 }}>CSV hochladen + Tätigkeiten erfassen</div>

      {/* Month/Year selector */}
      <div style={{ background: "white", borderRadius: 8, padding: "20px 24px", marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", display: "flex", gap: 16, alignItems: "center" }}>
        <label style={{ fontWeight: 600, fontSize: 13 }}>Monat:</label>
        <select value={month} onChange={e => setMonth(+e.target.value)} style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8 }}>
          {months.map((m,i) => <option key={i+1} value={i+1}>{m} {year}</option>)}
        </select>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button onClick={() => setStep(1)} style={{ padding: "8px 16px", background: step===1?"#1C5B7A":"#F0F0F0", color: step===1?"white":"#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>1. CSV Upload</button>
          <button onClick={() => setStep(2)} style={{ padding: "8px 16px", background: step===2?"#1C5B7A":"#F0F0F0", color: step===2?"white":"#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>2. Tätigkeiten</button>
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
          <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif", margin: "0 0 20px", color: "#1C5B7A" }}>CSV aus Software hochladen</h3>
          <div style={{ border: "2px dashed #DDD", borderRadius: 8, padding: "40px", textAlign: "center", marginBottom: 20, background: "#FAFAFA" }}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); setCsvFile(e.dataTransfer.files[0]) }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>📄</div>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>CSV-Datei hierher ziehen</div>
            <div style={{ color: "#888", fontSize: 13, marginBottom: 16 }}>Oder:</div>
            <input type="file" accept=".csv" onChange={e => setCsvFile(e.target.files[0])} style={{ display: "none" }} id="csv-input" />
            <label htmlFor="csv-input" style={{ background: "#1C5B7A", color: "white", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontSize: 14, fontWeight: 600 }}>Datei auswählen</label>
          </div>
          {csvFile && (
            <div style={{ background: "#E8F8E8", padding: "12px 16px", borderRadius: 8, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{csvFile.name}</div>
                <div style={{ fontSize: 12, color: "#888" }}>{(csvFile.size/1024).toFixed(1)} KB</div>
              </div>
              <button onClick={uploadCSV} disabled={saving} style={{ background: "#1C5B7A", color: "white", border: "none", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontWeight: 700 }}>
                {saving ? "Lade hoch…" : "Hochladen & Importieren"}
              </button>
            </div>
          )}
          {csvPreview && (
            <div>
              <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif", color: "#1C5B7A", margin: "0 0 12px" }}>Importierte Umsätze:</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 8 }}>
                {Object.entries(csvPreview).map(([name, amt]) => (
                  <div key={name} style={{ background: "#F5F5F5", borderRadius: 8, padding: "8px 12px", display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
                    <span style={{ fontSize: 13, color: "#1C5B7A" }}>CHF {(+amt).toLocaleString("de-CH")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Tätigkeiten */}
      {step === 2 && (
        <div style={{ background: "white", borderRadius: 8, padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif", margin: 0, color: "#1C5B7A" }}>Tätigkeiten — {months[month-1]} {year}</h3>
            <button onClick={saveInputs} disabled={saving} style={{ background: "#1C5B7A", color: "white", border: "none", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 14 }}>
              {saving ? "Speichern…" : "Alle speichern"}
            </button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#1C5B7A", color: "white" }}>
                  {["Mitarbeiter","Team","Ferien (T)","Kurse (h)","Workshop (h)","Marketing (h)","Laufanalyse (h)","Krank (T)"].map(h => (
                    <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 700, whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {maList.map((ma, i) => (
                  <tr key={ma.name} style={{ background: i%2===0?"white":"#F8F9FA" }}>
                    <td style={{ padding: "8px 12px", fontWeight: 600, whiteSpace: "nowrap" }}>{ma.display_name}</td>
                    <td style={{ padding: "8px 12px", color: "#888", fontSize: 11 }}>{ma.team}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"ferien_t","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"kurs_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"workshop_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"marketing_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"laufanalyse_h","")}</td>
                    <td style={{ padding: "4px 8px" }}>{inputField(ma.name,"krank_t","")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── YTD Overview Page ──────────────────────────────────────────────────────
function OverviewPage() {
  const [data, setData] = useState(null)
  const [filterTeam, setFilterTeam] = useState("Alle")
  const [filterRole, setFilterRole] = useState("Alle")
  const [sortKey, setSortKey] = useState("name")
  const [sortDir, setSortDir] = useState("asc")
  const months = ["Jan","Feb","Mrz","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

  useEffect(() => { api("/api/ytd/2026").then(setData).catch(console.error) }, [])

  if (!data) return <div style={{ textAlign: "center", padding: 60, color: "#888" }}>Lade…</div>

  const allMA = data.ma_data || []
  const teams = ["Alle", ...Array.from(new Set(allMA.map(m => m.team))).sort()]
  const roles = ["Alle", ...Array.from(new Set(allMA.map(m => m.role).filter(Boolean))).sort()]

  let rows = allMA.filter(m =>
    (filterTeam === "Alle" || m.team === filterTeam) &&
    (filterRole === "Alle" || m.role === filterRole)
  )

  const dir = sortDir === "asc" ? 1 : -1
  rows = [...rows].sort((a, b) => {
    if (sortKey === "name") return dir * (a.display_name||"").localeCompare(b.display_name||"")
    if (sortKey === "team") return dir * (a.team||"").localeCompare(b.team||"")
    if (sortKey === "avg") return dir * ((a.avg_zeg_b||0) - (b.avg_zeg_b||0))
    if (sortKey.startsWith("m")) {
      const mi = parseInt(sortKey.slice(1), 10)
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

  const selectStyle = { padding: "6px 10px", borderRadius: 6, border: "1px solid #DDD", fontSize: 12, background: "white", color: "#333" }

  return (
    <div>
      <h1 style={{ margin: "0 0 8px", fontSize: 26, fontWeight: 700, fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.03em" }}>Jahresübersicht 2026</h1>
      <div style={{ color: "#888", marginBottom: 18, fontSize: 13 }}>ZEG-B pro Monat und Mitarbeiter</div>

      <div style={{ display: "flex", gap: 12, marginBottom: 18, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Standort:
          <select value={filterTeam} onChange={e => setFilterTeam(e.target.value)} style={selectStyle}>
            {teams.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 12, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
          Rolle:
          <select value={filterRole} onChange={e => setFilterRole(e.target.value)} style={selectStyle}>
            {roles.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        {(filterTeam !== "Alle" || filterRole !== "Alle") && (
          <button onClick={() => { setFilterTeam("Alle"); setFilterRole("Alle") }}
            style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #DDD", background: "white", fontSize: 12, color: "#888", cursor: "pointer" }}>
            Filter zurücksetzen
          </button>
        )}
        <div style={{ marginLeft: "auto", fontSize: 12, color: "#888" }}>{rows.length} Mitarbeiter</div>
      </div>

      <div style={{ background: "white", borderRadius: 8, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#1C5B7A", color: "white" }}>
                <th onClick={() => toggleSort("name")} style={{ padding: "12px 16px", textAlign: "left", position: "sticky", left: 0, background: "#1C5B7A", zIndex: 2, minWidth: 140, cursor: "pointer", userSelect: "none" }}>
                  Mitarbeiter<SortArrow k="name" />
                </th>
                <th onClick={() => toggleSort("team")} style={{ padding: "12px 8px", textAlign: "center", minWidth: 60, cursor: "pointer", userSelect: "none" }}>
                  Team<SortArrow k="team" />
                </th>
                {months.map((m, mi) => (
                  <th key={m} onClick={() => toggleSort("m"+mi)} style={{ padding: "12px 8px", textAlign: "center", minWidth: 68, cursor: "pointer", userSelect: "none" }}>
                    {m}<SortArrow k={"m"+mi} />
                  </th>
                ))}
                <th onClick={() => toggleSort("avg")} style={{ padding: "12px 12px", textAlign: "center", minWidth: 80, borderLeft: "2px solid rgba(255,255,255,0.3)", cursor: "pointer", userSelect: "none" }}>
                  Ø ZEG-B<SortArrow k="avg" />
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((ma, i) => (
                <tr key={ma.name} style={{ background: i%2===0?"white":"#F8F9FA" }}>
                  <td style={{ padding: "8px 16px", fontWeight: 600, position: "sticky", left: 0, background: i%2===0?"white":"#F8F9FA", zIndex: 1, borderRight: "1px solid #EEE" }}>{ma.display_name}</td>
                  <td style={{ padding: "8px 8px", textAlign: "center", color: "#888", fontSize: 11 }}>{ma.team}</td>
                  {(ma.monthly||[]).concat(Array(12).fill(null)).slice(0,12).map((m, mi) => (
                    <td key={mi} style={{ padding: "6px 4px", textAlign: "center" }}>
                      {m ? <ZEGBadge value={m.zeg_b} color={m.color} /> : <span style={{ color: "#DDD", fontSize: 11 }}>—</span>}
                    </td>
                  ))}
                  <td style={{ padding: "6px 8px", textAlign: "center", borderLeft: "2px solid #EEE" }}>
                    <ZEGBadge value={ma.avg_zeg_b} color={ma.color} size="sm" />
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={14} style={{ padding: 24, textAlign: "center", color: "#888" }}>Keine Mitarbeiter für diese Filterauswahl</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 16, display: "flex", gap: 16, fontSize: 12, color: "#888" }}>
        {[["green","≥ 100%"],["amber","85–99%"],["red","< 85%"]].map(([c,l]) => (
          <div key={c} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 12, height: 12, borderRadius: "50%", background: ZEG_COLORS[c].border }}/>
            {l}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Exports Page ───────────────────────────────────────────────────────────
function ExportsPage() {
  const auth = useAuth()
  const [loading, setLoading] = useState({})
  const [maList, setMaList] = useState([])
  const [bilat_month, setBilatMonth] = useState(5)
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

  const isCEO = auth.user?.role === "ceo"

  return (
    <div>
      <h1 style={{ margin: "0 0 8px", fontSize: 26, fontWeight: 700, fontFamily: "'Barlow Condensed', sans-serif", letterSpacing: "0.03em" }}>Exporte</h1>
      <div style={{ color: "#888", marginBottom: 28, fontSize: 13 }}>Nur für CEO / COO</div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(380px,1fr))", gap: 20 }}>

        {/* Excel Export */}
        {isCEO && (
          <div style={{ background: "white", borderRadius: 8, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <div style={{ fontSize: 36, marginBottom: 16 }}>📊</div>
            <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif", margin: "0 0 8px" }}>Umsatzanalyse Excel</h3>
            <p style={{ color: "#888", fontSize: 13, marginBottom: 20, lineHeight: 1.5 }}>
              Komplette Jahresübersicht mit allen Monaten, Arbeitstag-Muster, ZEG-A/B/C und MA-Details.
            </p>
            <button onClick={() => download("/api/export/excel/2026","Kineo_Umsatzanalyse_2026.xlsx","excel")}
              disabled={loading.excel} style={{ background:"#1C5B7A",color:"white",border:"none",padding:"12px 24px",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,width:"100%" }}>
              {loading.excel ? "Wird erstellt…" : "Excel herunterladen"}
            </button>
          </div>
        )}

        {/* Bilaterals - alle als ZIP */}
        <div style={{ background: "white", borderRadius: 8, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontSize: 36, marginBottom: 16 }}>📁</div>
          <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif", margin: "0 0 8px" }}>Alle Bilaterals als ZIP</h3>
          <p style={{ color: "#888", fontSize: 13, marginBottom: 16, lineHeight: 1.5 }}>
            {isCEO ? "Alle MA" : "Ihr Team"} — Word-Dokumente mit ZEG-B Daten.
          </p>
          <select value={bilat_month} onChange={e => setBilatMonth(+e.target.value)}
            style={{ width:"100%",padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,marginBottom:12 }}>
            {months.map((m,i) => <option key={i+1} value={i+1}>Stand: {m} 2026</option>)}
          </select>
          <button onClick={() => download(`/api/export/bilats/2026/${bilat_month}`,`Kineo_Bilats_${months[bilat_month-1]}_2026.zip`,"bilat_all")}
            disabled={loading.bilat_all} style={{ background:"#1C5B7A",color:"white",border:"none",padding:"12px 24px",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,width:"100%" }}>
            {loading.bilat_all ? "Wird erstellt…" : "ZIP herunterladen"}
          </button>
        </div>

        {/* Bilaterals - einzeln */}
        <div style={{ background: "white", borderRadius: 8, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontSize: 36, marginBottom: 16 }}>📝</div>
          <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif", margin: "0 0 8px" }}>Bilateral einzeln</h3>
          <p style={{ color: "#888", fontSize: 13, marginBottom: 16, lineHeight: 1.5 }}>
            Einzelnes Bilateral für eine/n Mitarbeiter/in herunterladen.
          </p>
          <select value={bilat_month} onChange={e => setBilatMonth(+e.target.value)}
            style={{ width:"100%",padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,marginBottom:8 }}>
            {months.map((m,i) => <option key={i+1} value={i+1}>Stand: {m} 2026</option>)}
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
                  onClick={() => download(`/api/export/bilat-single/2026/${bilat_month}/${ma.name}`,
                    `Bilat_${ma.name.replace(".","_")}_${months[bilat_month-1]}_2026.docx`,
                    `bilat_${ma.name}`)}
                  disabled={loading[`bilat_${ma.name}`]}
                  style={{ background:"#E4EEF3",color:"#1C5B7A",border:"none",padding:"6px 14px",
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
const STANDORTE = ["Seefeld","Wipkingen","Thalwil","Escher Wyss","Stauffacher","Zollikon","Office"]
const ROLLEN = ["therapeut","teamlead","sl","bd","management"]
const DAYS_DE = ["Mo","Di","Mi","Do","Fr"]

function AdminPage() {
  const [tab, setTab] = useState("ma")
  const [mas, setMas] = useState([])
  const [feiertage, setFeiertage] = useState([])
  const [editMA, setEditMA] = useState(null)
  const [scheduleMA, setScheduleMA] = useState(null)
  const [schedule, setSchedule] = useState([])
  const [msg, setMsg] = useState(null)
  const [newMA, setNewMA] = useState({name:"",display_name:"",team:"Seefeld",role:"therapeut",bg_pct:1.0,eintritt:"",austritt:""})
  const [showNewMA, setShowNewMA] = useState(false)
  const [newFeiertag, setNewFeiertag] = useState({date_str:"",name:"",faktor:1.0})

  const loadMAs = () => api("/api/admin/ma").then(setMas).catch(console.error)
  const loadFeiertage = () => api("/api/admin/feiertage/2026").then(setFeiertage).catch(console.error)

  useEffect(() => { loadMAs(); loadFeiertage() }, [])

  const loadSchedule = async (name) => {
    const s = await api(`/api/admin/schedule/${name}`)
    setSchedule(s); setScheduleMA(name)
  }

  const saveSchedule = async () => {
    await api(`/api/admin/schedule/${scheduleMA}`, {method:"POST", body:JSON.stringify(schedule)})
    setMsg({type:"ok",text:"Arbeitstag-Muster gespeichert"}); setScheduleMA(null)
  }

  const toggleMA = async (name) => {
    await api(`/api/admin/ma/${name}/toggle`, {method:"PATCH"})
    loadMAs()
  }

  const saveMA = async (isNew=false) => {
    const data = isNew ? newMA : editMA
    const method = isNew ? "POST" : "PUT"
    const url = isNew ? "/api/admin/ma" : `/api/admin/ma/${editMA.name}`
    try {
      await api(url, {method, body:JSON.stringify(data)})
      setMsg({type:"ok",text:"Gespeichert"}); loadMAs()
      isNew ? setShowNewMA(false) : setEditMA(null)
    } catch(e) { setMsg({type:"err",text:e.message}) }
  }

  const saveFeiertage = async () => {
    await api("/api/admin/feiertage/2026", {method:"POST", body:JSON.stringify(feiertage)})
    setMsg({type:"ok",text:"Feiertage gespeichert"}); loadFeiertage()
  }

  const addFeiertag = () => {
    if (!newFeiertag.date_str || !newFeiertag.name) return
    setFeiertage([...feiertage, newFeiertag].sort((a,b)=>a.date_str.localeCompare(b.date_str)))
    setNewFeiertag({date_str:"",name:"",faktor:1.0})
  }

  const inp = (style={}) => ({padding:"8px 10px",border:"1.5px solid #DDD",borderRadius:6,fontSize:13,...style})
  const btn = (bg="#1C5B7A",color="white") => ({background:bg,color,border:"none",padding:"8px 16px",borderRadius:6,cursor:"pointer",fontWeight:600,fontSize:13})

  const tabs = [["ma","👥 Mitarbeiter"],["schedule","📅 Arbeitstag-Muster"],["feiertage","🗓 Feiertage"]]

  return (
    <div>
      <h1 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 8px",fontSize:24,fontWeight:800}}>Admin</h1>
      <div style={{color:"#888",marginBottom:24,fontSize:13}}>Nur CEO / COO</div>

      {msg && <div style={{background:msg.type==="ok"?"#E8F8E8":"#FFE8E8",color:msg.type==="ok"?"#1a7a1a":"#c0392b",padding:"10px 14px",borderRadius:8,marginBottom:16,fontSize:13,display:"flex",justifyContent:"space-between"}}>
        {msg.text}<span style={{cursor:"pointer"}} onClick={()=>setMsg(null)}>✕</span>
      </div>}

      {/* Tabs */}
      <div style={{display:"flex",gap:4,marginBottom:24,background:"white",padding:4,borderRadius:10,boxShadow:"0 2px 8px rgba(0,0,0,0.06)",width:"fit-content"}}>
        {tabs.map(([id,label]) => (
          <button key={id} onClick={()=>setTab(id)} style={{
            padding:"8px 20px",border:"none",borderRadius:8,cursor:"pointer",fontWeight:600,fontSize:13,
            background:tab===id?"#1C5B7A":"transparent",color:tab===id?"white":"#555"
          }}>{label}</button>
        ))}
      </div>

      {/* ── TAB: Mitarbeiter ── */}
      {tab==="ma" && (
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
            <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:0}}>Mitarbeiter/innen ({mas.filter(m=>m.is_active).length} aktiv)</h3>
            <button style={btn()} onClick={()=>setShowNewMA(!showNewMA)}>+ Neue/r MA</button>
          </div>

          {showNewMA && (
            <div style={{background:"#F0F8F0",border:"1.5px solid #1C5B7A",borderRadius:10,padding:20,marginBottom:20}}>
              <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 16px",color:"#1C5B7A"}}>Neue/r Mitarbeiter/in</h4>
              <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(180px,1fr))",gap:12}}>
                {[["name","Kürzel (z.B. Maria.M)"],["display_name","Anzeigename"],["eintritt","Eintritt (YYYY-MM-DD)"],["austritt","Austritt (YYYY-MM-DD)"]].map(([k,l]) => (
                  <div key={k}><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>{l}</div>
                  <input style={inp({width:"100%",boxSizing:"border-box"})} value={newMA[k]||""} onChange={e=>setNewMA({...newMA,[k]:e.target.value})} /></div>
                ))}
                <div><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>Team/Standort</div>
                <select style={inp({width:"100%",boxSizing:"border-box"})} value={newMA.team} onChange={e=>setNewMA({...newMA,team:e.target.value})}>
                  {STANDORTE.filter(s=>s!=="Office").map(s=><option key={s}>{s}</option>)}</select></div>
                <div><div style={{fontSize:11,fontWeight:600,color:"#555",marginBottom:4}}>Rolle</div>
                <select style={inp({width:"100%",boxSizing:"border-box"})} value={newMA.role} onChange={e=>setNewMA({...newMA,role:e.target.value})}>
                  {ROLLEN.map(r=><option key={r}>{r}</option>)}</select></div>
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
            <thead><tr style={{background:"#1C5B7A",color:"white"}}>
              {["Name","Anzeige","Team","Rolle","BG%","Eintritt","Austritt","Status","Aktionen"].map(h=>(
                <th key={h} style={{padding:"10px 12px",textAlign:"left",fontWeight:700}}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {mas.map((ma,i) => editMA?.name===ma.name ? (
                <tr key={ma.name} style={{background:"#F0F8F0"}}>
                  <td style={{padding:"8px 12px",fontWeight:700}}>{ma.name}</td>
                  {[["display_name",180],["team",null,STANDORTE.filter(s=>s!=="Office")],["role",null,ROLLEN],["bg_pct",60],["eintritt",120],["austritt",120]].map(([k,w,opts])=>(
                    <td key={k} style={{padding:"4px 8px"}}>
                      {opts ? <select style={inp()} value={editMA[k]||""} onChange={e=>setEditMA({...editMA,[k]:e.target.value})}>
                        {opts.map(o=><option key={o}>{o}</option>)}</select>
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
                  <td style={{padding:"8px 12px",color:"#555"}}>{ma.team}</td>
                  <td style={{padding:"8px 12px",color:"#555"}}>{ma.role}</td>
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
                      <button style={btn("#E4EEF3","#1C5B7A")} onClick={()=>setEditMA({...ma})}>✏️</button>
                      <button style={btn("#E4EEF3","#1C5B7A")} onClick={()=>loadSchedule(ma.name)}>📅</button>
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
          <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 20px"}}>Arbeitstag-Muster pro Mitarbeiter/in</h3>
          {!scheduleMA ? (
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))",gap:12}}>
              {mas.filter(m=>m.is_active).map(ma=>(
                <button key={ma.name} onClick={()=>loadSchedule(ma.name)} style={{
                  background:"#F8F9FA",border:"1.5px solid #E0E0E0",borderRadius:8,padding:"14px 16px",
                  cursor:"pointer",textAlign:"left"
                }}>
                  <div style={{fontWeight:700,fontSize:13}}>{ma.display_name}</div>
                  <div style={{fontSize:11,color:"#888",marginTop:4}}>{ma.team} · {(ma.bg_pct*100).toFixed(0)}%</div>
                </button>
              ))}
            </div>
          ) : (
            <div>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
                <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:0,color:"#1C5B7A"}}>📅 {scheduleMA}</h4>
                <button style={btn("#EEE","#333")} onClick={()=>setScheduleMA(null)}>← Zurück</button>
              </div>
              <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
                <thead><tr style={{background:"#1C5B7A",color:"white"}}>
                  <th style={{padding:"10px 14px",textAlign:"left"}}>Tag</th>
                  <th style={{padding:"10px 14px",textAlign:"center"}}>VM %</th>
                  <th style={{padding:"10px 14px",textAlign:"left"}}>VM Standort</th>
                  <th style={{padding:"10px 14px",textAlign:"center"}}>NM %</th>
                  <th style={{padding:"10px 14px",textAlign:"left"}}>NM Standort</th>
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
                          <input type="number" min="0" max="0.2" step="0.05" value={entry.vm_pct||0}
                            onChange={e=>update("vm_pct",e.target.value)}
                            style={{...inp(),width:70,textAlign:"center"}} />
                        </td>
                        <td style={{padding:"6px 8px"}}>
                          <select value={entry.vm_standort||""} onChange={e=>update("vm_standort",e.target.value)}
                            style={inp({minWidth:130})}>
                            <option value="">— frei —</option>
                            {STANDORTE.map(s=><option key={s}>{s}</option>)}
                          </select>
                        </td>
                        <td style={{padding:"6px 8px",textAlign:"center"}}>
                          <input type="number" min="0" max="0.2" step="0.05" value={entry.nm_pct||0}
                            onChange={e=>update("nm_pct",e.target.value)}
                            style={{...inp(),width:70,textAlign:"center"}} />
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
              <div style={{marginTop:16,display:"flex",gap:8}}>
                <button style={btn()} onClick={saveSchedule}>Speichern</button>
                <button style={btn("#EEE","#333")} onClick={()=>setScheduleMA(null)}>Abbrechen</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB: Feiertage ── */}
      {tab==="feiertage" && (
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
            <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:0}}>Feiertage Kanton Zürich 2026</h3>
            <button style={btn()} onClick={saveFeiertage}>Alle speichern</button>
          </div>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13,marginBottom:20}}>
            <thead><tr style={{background:"#1C5B7A",color:"white"}}>
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
  const [msg, setMsg] = useState(null)

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
      <h1 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 28px",fontSize:24,fontWeight:800}}>Profil</h1>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:20,maxWidth:800}}>
        <div style={{background:"white",borderRadius:12,padding:28,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 20px",color:"#1C5B7A"}}>👤 Mein Konto</h3>
          {[["Benutzername",auth.user?.username],["Name",auth.user?.full_name],["Rolle",auth.user?.role?.toUpperCase()],["Team",auth.user?.team||"Alle"]].map(([l,v])=>(
            <div key={l} style={{display:"flex",justifyContent:"space-between",padding:"10px 0",borderBottom:"1px solid #F5F5F5"}}>
              <span style={{color:"#888",fontSize:13}}>{l}</span>
              <span style={{fontWeight:600,fontSize:13}}>{v||"—"}</span>
            </div>
          ))}
        </div>
        <div style={{background:"white",borderRadius:12,padding:28,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 20px",color:"#1C5B7A"}}>🔒 Passwort ändern</h3>
          {msg && <div style={{background:msg.type==="ok"?"#E8F8E8":"#FFE8E8",color:msg.type==="ok"?"#1a7a1a":"#c0392b",padding:"10px 14px",borderRadius:8,marginBottom:16,fontSize:13}}>{msg.text}</div>}
          {[["current_password","Aktuelles Passwort"],["new_password","Neues Passwort (min. 8 Zeichen)"],["confirm","Neues Passwort bestätigen"]].map(([k,l])=>(
            <div key={k} style={{marginBottom:14}}>
              <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:6}}>{l}</div>
              <input type="password" value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})}
                style={{width:"100%",padding:"10px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:14,boxSizing:"border-box"}} />
            </div>
          ))}
          <button onClick={submit} style={{width:"100%",padding:"11px",background:"#1C5B7A",color:"white",border:"none",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,marginTop:4}}>
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
  d: "Satisfaction Extern – Patienten & Zuweiser"
}

function BilatDataPage() {
  const now = new Date()
  const defaultPeriod = `${now.getMonth() < 6 ? "HJ1" : "HJ2"} ${now.getFullYear()}`
  const [overview, setOverview] = useState([])
  const [selected, setSelected] = useState(null)
  const [bilatData, setBilatData] = useState({})
  const [msg, setMsg] = useState(null)
  const [year, setYear] = useState(now.getFullYear())
  const [period, setPeriod] = useState(defaultPeriod)
  const [periods, setPeriods] = useState([defaultPeriod])
  const [newPeriod, setNewPeriod] = useState("")
  const [showNewPeriod, setShowNewPeriod] = useState(false)

  useEffect(() => {
    api("/api/bilat-periods").then(p => { setPeriods(p); if (!p.includes(period)) setPeriod(p[0] || defaultPeriod) }).catch(console.error)
  }, [])

  useEffect(() => {
    if (period) api(`/api/bilat-overview/${year}/${encodeURIComponent(period)}`).then(setOverview).catch(console.error)
  }, [year, period])

  const openBilat = async (ma) => {
    const data = await api(`/api/bilat/${ma.name}/${year}/${encodeURIComponent(period)}`).catch(()=>({}))
    setBilatData(data || {})
    setSelected(ma)
  }

  const save = async () => {
    try {
      await api(`/api/bilat/${selected.name}/${year}/${encodeURIComponent(period)}`, {method:"POST", body:JSON.stringify(bilatData)})
      setMsg({type:"ok",text:"Bilateral gespeichert"})
      api(`/api/bilat-overview/${year}/${encodeURIComponent(period)}`).then(setOverview)
      api("/api/bilat-periods").then(setPeriods)
    } catch(e) { setMsg({type:"err",text:e.message}) }
  }

  const addPeriod = () => {
    if (!newPeriod.trim()) return
    const p = newPeriod.trim()
    setPeriods(prev => [...new Set([...prev, p])])
    setPeriod(p)
    setNewPeriod("")
    setShowNewPeriod(false)
  }

  const RatingButtons = ({field, label}) => (
    <div style={{marginBottom:16}}>
      <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:8}}>{label}</div>
      <div style={{display:"flex",gap:6}}>
        {[1,2,3,4,5].map(v=>(
          <button key={v} onClick={()=>setBilatData({...bilatData,[field]:bilatData[field]===v?null:v})}
            style={{width:38,height:38,border:`2px solid ${bilatData[field]===v?"#1C5B7A":"#DDD"}`,
              borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,
              background:bilatData[field]===v?"#1C5B7A":"white",
              color:bilatData[field]===v?"white":"#555"}}>
            {v}
          </button>
        ))}
        {bilatData[field] && <span style={{fontSize:11,color:"#1C5B7A",alignSelf:"center",marginLeft:4}}>
          {["","Entwicklungsbedarf","Unter Erwartung","Erwartung erfüllt","Gut","Ausgezeichnet"][bilatData[field]]}
        </span>}
      </div>
    </div>
  )

  if (selected) return (
    <div>
      <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:24}}>
        <button onClick={()=>{setSelected(null);setMsg(null)}} style={{background:"#EEE",border:"none",padding:"8px 16px",borderRadius:8,cursor:"pointer",fontWeight:600}}>← Zurück</button>
        <h1 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:0,fontSize:22,fontWeight:800}}>Bilateral — {selected.display_name}</h1>
        <span style={{color:"#888",fontSize:13}}>HJ{half} {year}</span>
      </div>
      {msg && <div style={{background:msg.type==="ok"?"#E8F8E8":"#FFE8E8",color:msg.type==="ok"?"#1a7a1a":"#c0392b",padding:"10px 14px",borderRadius:8,marginBottom:16,fontSize:13}}>{msg.text}</div>}

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:20}}>
        {/* Kategorien A-D */}
        {["a","b","c","d"].map(k=>(
          <div key={k} style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
            <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 16px",color:"#1C5B7A"}}>Kat. {k.toUpperCase()} — {KAT_LABELS[k]}</h4>
            <RatingButtons field={`kat_${k}_self`} label="Selbsteinschätzung MA (1–5)" />
            <RatingButtons field={`kat_${k}_fk`} label="Einschätzung Führungskraft (1–5)" />
            <div>
              <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:6}}>Kommentar</div>
              <textarea value={bilatData[`kat_${k}_comment`]||""} onChange={e=>setBilatData({...bilatData,[`kat_${k}_comment`]:e.target.value})}
                style={{width:"100%",padding:"8px 10px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,resize:"vertical",minHeight:60,boxSizing:"border-box"}} />
            </div>
          </div>
        ))}

        {/* Themen MA */}
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 16px",color:"#1C5B7A"}}>💬 Themen des Mitarbeiters</h4>
          <textarea value={bilatData.themen_ma||""} onChange={e=>setBilatData({...bilatData,themen_ma:e.target.value})}
            style={{width:"100%",padding:"10px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,resize:"vertical",minHeight:100,boxSizing:"border-box"}} />
        </div>

        {/* Abschluss */}
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
          <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 16px",color:"#1C5B7A"}}>✅ Abschluss</h4>
          <div style={{marginBottom:16}}>
            <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:8}}>Gesprächseindruck</div>
            <div style={{display:"flex",gap:8}}>
              {["Konstruktiv","Offen","Angespannt"].map(v=>(
                <button key={v} onClick={()=>setBilatData({...bilatData,gespraechseindruck:bilatData.gespraechseindruck===v?null:v})}
                  style={{padding:"7px 14px",border:`2px solid ${bilatData.gespraechseindruck===v?"#1C5B7A":"#DDD"}`,
                    borderRadius:8,cursor:"pointer",fontSize:13,fontWeight:bilatData.gespraechseindruck===v?700:400,
                    background:bilatData.gespraechseindruck===v?"#E4EEF3":"white",color:bilatData.gespraechseindruck===v?"#1C5B7A":"#555"}}>
                  {v}
                </button>
              ))}
            </div>
          </div>
          <div style={{marginBottom:16}}>
            <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:6}}>Nächstes Bilat-Datum</div>
            <input type="date" value={bilatData.naechstes_bilat||""} onChange={e=>setBilatData({...bilatData,naechstes_bilat:e.target.value})}
              style={{padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13}} />
          </div>
          <div>
            <div style={{fontSize:12,fontWeight:600,color:"#555",marginBottom:6}}>Vereinbarungen & nächste Schritte</div>
            <textarea value={bilatData.vereinbarungen||""} onChange={e=>setBilatData({...bilatData,vereinbarungen:e.target.value})}
              placeholder="Eine Vereinbarung pro Zeile..." style={{width:"100%",padding:"10px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,resize:"vertical",minHeight:80,boxSizing:"border-box"}} />
          </div>
        </div>
      </div>

      <div style={{marginTop:20,display:"flex",gap:12}}>
        <button onClick={save} style={{padding:"12px 32px",background:"#1C5B7A",color:"white",border:"none",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:15}}>
          Speichern
        </button>
        <button onClick={()=>setSelected(null)} style={{padding:"12px 24px",background:"#EEE",color:"#333",border:"none",borderRadius:8,cursor:"pointer",fontWeight:600,fontSize:14}}>
          Abbrechen
        </button>
      </div>
    </div>
  )

  // Overview
  const teams = [...new Set(overview.map(m=>m.team))]
  return (
    <div>
      <h1 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 8px",fontSize:24,fontWeight:800}}>Bilaterals</h1>
      <div style={{color:"#888",marginBottom:28,fontSize:13}}>HJ{half} {year} — Bewertungen erfassen und speichern</div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(320px,1fr))",gap:20}}>
        {teams.map(team=>{
          const teamMAs=overview.filter(m=>m.team===team)
          const done=teamMAs.filter(m=>m.has_data).length
          return (
            <div key={team} style={{background:"white",borderRadius:12,overflow:"hidden",boxShadow:"0 2px 8px rgba(0,0,0,0.06)"}}>
              <div style={{background:"#1C5B7A",padding:"14px 20px",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
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
                    {ma.has_data && <div style={{fontSize:11,color:"#888",marginTop:2}}>
                      A:{ma.kat_a_fk||"—"} B:{ma.kat_b_fk||"—"} C:{ma.kat_c_fk||"—"} D:{ma.kat_d_fk||"—"}
                    </div>}
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
  const [params, setParams] = useState({
    umsatz: 0, bg_pct: 100, ziel_chf: 1040, lohnquote: 40,
    fixlohn: 5000, zeg_schwelle: 85, bonus_ab: 100
  })
  const [maList, setMaList] = useState([])
  const [selectedMA, setSelectedMA] = useState(null)
  const [ytdData, setYtdData] = useState(null)

  useEffect(() => {
    api("/api/ma").then(setMaList).catch(console.error)
    api("/api/ytd/2026").then(setYtdData).catch(console.error)
  }, [])

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
      <h1 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 8px",fontSize:24,fontWeight:800}}>🧮 Umsatzlohn-Rechner</h1>
      <div style={{color:"#888",marginBottom:28,fontSize:13}}>Simulation Umsatzlohnmodell — {params.lohnquote}% Bruttolohnquote</div>

      <div style={{display:"grid",gridTemplateColumns:"320px 1fr",gap:24}}>
        {/* Parameter */}
        <div style={{background:"white",borderRadius:12,padding:24,boxShadow:"0 2px 8px rgba(0,0,0,0.06)",height:"fit-content"}}>
          <h3 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 20px",color:"#1C5B7A"}}>Parameter</h3>
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
                  onChange={e=>set(k,e.target.value)} style={{flex:1,accentColor:"#1C5B7A"}} />
                <span style={{fontSize:14,fontWeight:700,color:"#1C5B7A",minWidth:60,textAlign:"right"}}>
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
            <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 20px",color:"#1C5B7A"}}>Fix vs. Variabel — Vergleich</h4>
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
              <h4 style={{ fontFamily: "'Barlow Condensed', sans-serif",margin:"0 0 16px",color:"#1C5B7A"}}>📊 {selectedMA} — Simulation mit Ist-Daten 2026</h4>
              <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12}}>
                {[
                  ["Ø Monats-Umsatz",chf(maCalc.avgMonthlyUmsatz)],
                  ["Ø ZEG-B",`${(maCalc.avgZeg*100).toFixed(1)}%`],
                  ["Fixlohn (adj.)",chf(maCalc.fixlohn_adj)],
                  ["Variabel-Lohn",chf(maCalc.lohnVar)],
                ].map(([l,v])=>(
                  <div key={l} style={{textAlign:"center",padding:"14px",background:"#F8F9FA",borderRadius:8}}>
                    <div style={{fontSize:11,color:"#888",fontWeight:600,marginBottom:6}}>{l}</div>
                    <div style={{fontSize:16,fontWeight:800,color:"#1C5B7A"}}>{v}</div>
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

  const handleLogin = (userData) => {
    setUser(userData)
    localStorage.setItem("user", JSON.stringify(userData))
  }
  const logout = () => { localStorage.clear(); setUser(null) }

  if (!user) return <LoginPage onLogin={handleLogin} />

  const pages = { dashboard: DashboardPage, upload: UploadPage, overview: OverviewPage, exports: ExportsPage, admin: AdminPage, bilats: BilatDataPage, lohnrechner: LohnrechnerPage, profil: ProfilPage }
  const PageComponent = pages[page] || DashboardPage

  return (
    <AuthCtx.Provider value={{ user, logout }}>
      <Layout page={page} setPage={setPage}>
        <PageComponent />
      </Layout>
    </AuthCtx.Provider>
  )
}
