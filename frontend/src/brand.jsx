import {
  LayoutDashboard, Upload, TrendingUp, Download, ClipboardList,
  Calculator, User, Settings, Bell, LogOut, Calendar, Users, Info,
} from "lucide-react"

/** Kineo CD — übernommen von kineo-physiotherapie.ch */
export const CD = {
  darkBlue: "#0a2734",
  primary: "#004869",
  accent: "#fa4616",
  bg: "#f9f7ed",
  neutral: "#e0ded1",
  text: "#0a2734",
  fontDisplay: "'Roboto Condensed', sans-serif",
  fontBody: "'Roboto', sans-serif",
  radius: "10px",
}

export const NAV_ICONS = {
  dashboard: LayoutDashboard,
  upload: Upload,
  overview: TrendingUp,
  exports: Download,
  bilats: ClipboardList,
  lohnrechner: Calculator,
  profil: User,
  admin: Settings,
}

/** Offizielles Logo von kineo-physiotherapie.ch */
export function KineoLogo({ variant = "white", height = 36 }) {
  const src = variant === "white" ? "/kineo-logo.png" : "/kineo-logo-dark.png"
  return (
    <img
      src={src}
      alt="Kineo Physiotherapie"
      height={height}
      style={{ display: "block", maxWidth: "100%", objectFit: "contain" }}
    />
  )
}

export function NavIcon({ name, size = 18, color = "currentColor" }) {
  const Icon = NAV_ICONS[name]
  if (!Icon) return null
  return <Icon size={size} color={color} strokeWidth={1.75} />
}

export function ScheduleHelp() {
  return (
    <div style={{
      background: "#f9f7ed", border: `1px solid ${CD.neutral}`, borderRadius: CD.radius,
      padding: "12px 16px", marginBottom: 20, fontSize: 13, color: CD.text, lineHeight: 1.55,
      display: "flex", gap: 10, alignItems: "flex-start",
    }}>
      <Info size={18} color={CD.primary} style={{ flexShrink: 0, marginTop: 2 }} />
      <div>
        <strong>Was bedeuten die Prozent-Werte?</strong>
        <p style={{ margin: "6px 0 0" }}>
          Die Woche hat <strong>10 Halbtage</strong> (Mo–Fr, je Vormittag + Nachmittag).
          <strong> 20&nbsp;% = ein Halbtag gearbeitet</strong> (max. pro Vormittag/Nachmittag).
          Vormittag + Nachmittag am <strong>gleichen Standort</strong> = ein ganzer Arbeitstag (40&nbsp;%).
          Beispiel Barbara: 20&nbsp;% + 20&nbsp;% Mo–Do in Wipkingen = <strong>4 ganze Tage = 80&nbsp;% Pensum</strong>.
        </p>
      </div>
    </div>
  )
}

export { Bell, LogOut, Calendar, Users, Info }
