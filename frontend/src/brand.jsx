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

import BaseKineoLogo from "./KineoLogo.jsx"

/** Offizielles Logo — weiss auf dunklem Hintergrund, petrol auf hellem */
export function KineoLogo({ variant = "white", height = 36 }) {
  return (
    <BaseKineoLogo
      variant={variant === "white" ? "white" : "petrol"}
      width={Math.round(height * (479 / 333))}
      style={{ height, width: "auto", maxWidth: "100%", objectFit: "contain", display: "block" }}
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
        <strong>Wann gilt eine Änderung?</strong>
        <p style={{ margin: "6px 0 8px" }}>
          <strong>Standard:</strong> «Gültig ab» (Monat) — gilt ab dem <strong>1. dieses Monats</strong> für FTE,
          Standortverteilung und Soll-Tage. Frühere Monate behalten die ältere Version.
          <br />
          <strong>Monats-Override:</strong> «Nur dieser Monat» — überschreibt den Plan <em>nur für einen einzelnen Monat</em>
          (z. B. Vertretung), ohne die Standard-Version zu ändern.
        </p>
        <strong>Was bedeuten die Prozent-Werte?</strong>
        <p style={{ margin: "6px 0 0" }}>
          Die Woche hat <strong>10 Halbtage</strong> (Mo–Fr, je Vormittag + Nachmittag) = 100&nbsp;%.
          <strong> 10&nbsp;% = ein Halbtag</strong> (Vormittag <em>oder</em> Nachmittag).
          <strong> 10&nbsp;% + 10&nbsp;%</strong> am gleichen Standort = <strong>ein ganzer Tag (20&nbsp;%)</strong>.
          Beispiel Barbara: 10&nbsp;% + 10&nbsp;% Mo–Do in Wipkingen = 4 Tage × 20&nbsp;% = <strong>80&nbsp;% Pensum</strong>.
        </p>
      </div>
    </div>
  )
}

export { Bell, LogOut, Calendar, Users, Info }
