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
      borderRadius: 20, padding: pad, fontSize: fs, fontWeight: 700,
      display: "inline-block", minWidth: size === "lg" ? 80 : 60, textAlign: "center"
    }}>{pct}</span>
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
  ].filter(n => !n.roles || n.roles.includes(auth.user?.role))

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#F8F9FA", fontFamily: "Arial, sans-serif" }}>
      {/* Sidebar */}
      <div style={{ width: 220, background: "#006B6B", color: "white", flexShrink: 0, display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "28px 20px 20px" }}>
          <div style={{ fontWeight: 800, fontSize: 18, letterSpacing: 1 }}>KINEO AG</div>
          <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>Umsatzanalyse 2026</div>
        </div>
        <nav style={{ flex: 1 }}>
          {nav.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)} style={{
              width: "100%", padding: "12px 20px", background: page === n.id ? "rgba(255,255,255,0.15)" : "transparent",
              border: "none", borderLeft: page === n.id ? "3px solid white" : "3px solid transparent",
              color: "white", textAlign: "left", cursor: "pointer", fontSize: 14,
              display: "flex", alignItems: "center", gap: 10,
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
    <div style={{ minHeight: "100vh", background: "linear-gradient(135deg,#006B6B,#004444)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "white", borderRadius: 16, padding: "48px 40px", width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🏥</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: "#006B6B" }}>KINEO AG</div>
          <div style={{ fontSize: 13, color: "#888", marginTop: 4 }}>Umsatzanalyse 2026</div>
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
            width: "100%", padding: "12px", background: "#006B6B", color: "white",
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
          <h1 style={{ margin: 0, fontSize: 24, color: "#1a1a1a", fontWeight: 800 }}>Dashboard</h1>
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
          <div key={card.label} style={{ background: "white", borderRadius: 12, padding: "20px 24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)", display: "flex", alignItems: "center", gap: 16 }}>
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
            <div key={team} style={{ background: "white", borderRadius: 12, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
              <div style={{ background: c.bg, borderBottom: `3px solid ${c.border}`, padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 800, fontSize: 15, color: "#1a1a1a" }}>{team}</div>
                  <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>
                    CHF {(stats.umsatz||0).toLocaleString("de-CH")}
                  </div>
                </div>
                <ZEGBadge value={stats.zeg_b_avg} color={stats.color} size="lg" />
              </div>
              <div style={{ padding: "12px 20px" }}>
                {/* FTE Total */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "2px solid #EEE", marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#006B6B", textTransform: "uppercase", letterSpacing: 0.5 }}>FTE Total</span>
                  <span style={{ fontSize: 14, fontWeight: 800, color: "#006B6B" }}>
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
      <h1 style={{ margin: "0 0 8px", fontSize: 24, fontWeight: 800 }}>Daten eingeben</h1>
      <div style={{ color: "#888", marginBottom: 28, fontSize: 13 }}>CSV hochladen + Tätigkeiten erfassen</div>

      {/* Month/Year selector */}
      <div style={{ background: "white", borderRadius: 12, padding: "20px 24px", marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.06)", display: "flex", gap: 16, alignItems: "center" }}>
        <label style={{ fontWeight: 600, fontSize: 13 }}>Monat:</label>
        <select value={month} onChange={e => setMonth(+e.target.value)} style={{ padding: "8px 12px", border: "1.5px solid #DDD", borderRadius: 8 }}>
          {months.map((m,i) => <option key={i+1} value={i+1}>{m} {year}</option>)}
        </select>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button onClick={() => setStep(1)} style={{ padding: "8px 16px", background: step===1?"#006B6B":"#F0F0F0", color: step===1?"white":"#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>1. CSV Upload</button>
          <button onClick={() => setStep(2)} style={{ padding: "8px 16px", background: step===2?"#006B6B":"#F0F0F0", color: step===2?"white":"#333", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>2. Tätigkeiten</button>
        </div>
      </div>

      {msg && (
        <div style={{ background: msg.type==="ok"?"#E8F8E8":"#FFE8E8", color: msg.type==="ok"?"#1a7a1a":"#c0392b", padding: "12px 16px", borderRadius: 8, marginBottom: 16, fontSize: 13 }}>
          {msg.text}
        </div>
      )}

      {/* Step 1: CSV Upload */}
      {step === 1 && (
        <div style={{ background: "white", borderRadius: 12, padding: "32px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <h3 style={{ margin: "0 0 20px", color: "#006B6B" }}>CSV aus Software hochladen</h3>
          <div style={{ border: "2px dashed #DDD", borderRadius: 12, padding: "40px", textAlign: "center", marginBottom: 20, background: "#FAFAFA" }}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); setCsvFile(e.dataTransfer.files[0]) }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>📄</div>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>CSV-Datei hierher ziehen</div>
            <div style={{ color: "#888", fontSize: 13, marginBottom: 16 }}>Oder:</div>
            <input type="file" accept=".csv" onChange={e => setCsvFile(e.target.files[0])} style={{ display: "none" }} id="csv-input" />
            <label htmlFor="csv-input" style={{ background: "#006B6B", color: "white", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontSize: 14, fontWeight: 600 }}>Datei auswählen</label>
          </div>
          {csvFile && (
            <div style={{ background: "#E8F8E8", padding: "12px 16px", borderRadius: 8, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{csvFile.name}</div>
                <div style={{ fontSize: 12, color: "#888" }}>{(csvFile.size/1024).toFixed(1)} KB</div>
              </div>
              <button onClick={uploadCSV} disabled={saving} style={{ background: "#006B6B", color: "white", border: "none", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontWeight: 700 }}>
                {saving ? "Lade hoch…" : "Hochladen & Importieren"}
              </button>
            </div>
          )}
          {csvPreview && (
            <div>
              <h4 style={{ color: "#006B6B", margin: "0 0 12px" }}>Importierte Umsätze:</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 8 }}>
                {Object.entries(csvPreview).map(([name, amt]) => (
                  <div key={name} style={{ background: "#F5F5F5", borderRadius: 8, padding: "8px 12px", display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{name}</span>
                    <span style={{ fontSize: 13, color: "#006B6B" }}>CHF {(+amt).toLocaleString("de-CH")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Tätigkeiten */}
      {step === 2 && (
        <div style={{ background: "white", borderRadius: 12, padding: "24px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h3 style={{ margin: 0, color: "#006B6B" }}>Tätigkeiten — {months[month-1]} {year}</h3>
            <button onClick={saveInputs} disabled={saving} style={{ background: "#006B6B", color: "white", border: "none", padding: "10px 24px", borderRadius: 8, cursor: "pointer", fontWeight: 700, fontSize: 14 }}>
              {saving ? "Speichern…" : "Alle speichern"}
            </button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#006B6B", color: "white" }}>
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
  const months = ["Jan","Feb","Mrz","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

  useEffect(() => { api("/api/ytd/2026").then(setData).catch(console.error) }, [])

  if (!data) return <div style={{ textAlign: "center", padding: 60, color: "#888" }}>Lade…</div>

  return (
    <div>
      <h1 style={{ margin: "0 0 8px", fontSize: 24, fontWeight: 800 }}>Jahresübersicht 2026</h1>
      <div style={{ color: "#888", marginBottom: 28, fontSize: 13 }}>ZEG-B pro Monat und Mitarbeiter</div>
      <div style={{ background: "white", borderRadius: 12, overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ background: "#006B6B", color: "white" }}>
                <th style={{ padding: "12px 16px", textAlign: "left", position: "sticky", left: 0, background: "#006B6B", zIndex: 2, minWidth: 140 }}>Mitarbeiter</th>
                <th style={{ padding: "12px 8px", textAlign: "center", minWidth: 60 }}>Team</th>
                {months.map(m => <th key={m} style={{ padding: "12px 8px", textAlign: "center", minWidth: 68 }}>{m}</th>)}
                <th style={{ padding: "12px 12px", textAlign: "center", minWidth: 80, borderLeft: "2px solid rgba(255,255,255,0.3)" }}>Ø ZEG-B</th>
              </tr>
            </thead>
            <tbody>
              {(data.ma_data||[]).sort((a,b)=>a.team.localeCompare(b.team)||(a.display_name||"").localeCompare(b.display_name||"")).map((ma, i) => (
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
      <h1 style={{ margin: "0 0 8px", fontSize: 24, fontWeight: 800 }}>Exporte</h1>
      <div style={{ color: "#888", marginBottom: 28, fontSize: 13 }}>Nur für CEO / COO</div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(380px,1fr))", gap: 20 }}>

        {/* Excel Export */}
        {isCEO && (
          <div style={{ background: "white", borderRadius: 12, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
            <div style={{ fontSize: 36, marginBottom: 16 }}>📊</div>
            <h3 style={{ margin: "0 0 8px" }}>Umsatzanalyse Excel</h3>
            <p style={{ color: "#888", fontSize: 13, marginBottom: 20, lineHeight: 1.5 }}>
              Komplette Jahresübersicht mit allen Monaten, Arbeitstag-Muster, ZEG-A/B/C und MA-Details.
            </p>
            <button onClick={() => download("/api/export/excel/2026","Kineo_Umsatzanalyse_2026.xlsx","excel")}
              disabled={loading.excel} style={{ background:"#006B6B",color:"white",border:"none",padding:"12px 24px",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,width:"100%" }}>
              {loading.excel ? "Wird erstellt…" : "Excel herunterladen"}
            </button>
          </div>
        )}

        {/* Bilaterals - alle als ZIP */}
        <div style={{ background: "white", borderRadius: 12, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontSize: 36, marginBottom: 16 }}>📁</div>
          <h3 style={{ margin: "0 0 8px" }}>Alle Bilaterals als ZIP</h3>
          <p style={{ color: "#888", fontSize: 13, marginBottom: 16, lineHeight: 1.5 }}>
            {isCEO ? "Alle MA" : "Ihr Team"} — Word-Dokumente mit ZEG-B Daten.
          </p>
          <select value={bilat_month} onChange={e => setBilatMonth(+e.target.value)}
            style={{ width:"100%",padding:"8px 12px",border:"1.5px solid #DDD",borderRadius:8,fontSize:13,marginBottom:12 }}>
            {months.map((m,i) => <option key={i+1} value={i+1}>Stand: {m} 2026</option>)}
          </select>
          <button onClick={() => download(`/api/export/bilats/2026/${bilat_month}`,`Kineo_Bilats_${months[bilat_month-1]}_2026.zip`,"bilat_all")}
            disabled={loading.bilat_all} style={{ background:"#006B6B",color:"white",border:"none",padding:"12px 24px",borderRadius:8,cursor:"pointer",fontWeight:700,fontSize:14,width:"100%" }}>
            {loading.bilat_all ? "Wird erstellt…" : "ZIP herunterladen"}
          </button>
        </div>

        {/* Bilaterals - einzeln */}
        <div style={{ background: "white", borderRadius: 12, padding: "28px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
          <div style={{ fontSize: 36, marginBottom: 16 }}>📝</div>
          <h3 style={{ margin: "0 0 8px" }}>Bilateral einzeln</h3>
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
                  style={{ background:"#E0F0F0",color:"#006B6B",border:"none",padding:"6px 14px",
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

  const pages = { dashboard: DashboardPage, upload: UploadPage, overview: OverviewPage, exports: ExportsPage }
  const PageComponent = pages[page] || DashboardPage

  return (
    <AuthCtx.Provider value={{ user, logout }}>
      <Layout page={page} setPage={setPage}>
        <PageComponent />
      </Layout>
    </AuthCtx.Provider>
  )
}
