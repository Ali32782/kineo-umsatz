export const CURRENT_YEAR = new Date().getFullYear()

const now = new Date()
export const DEFAULT_MONTH = now.getMonth() === 0 ? 12 : now.getMonth()
export const DEFAULT_YEAR = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear()

/** API base: empty in production Docker (nginx proxies /api), localhost in dev */
export const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "")

/**
 * Bilat-/Quali-Periode nach Kalender:
 * Feb–Jul → HJ1 year · Aug–Dez → HJ2 year · Jan → HJ2 year-1.
 */
export function periodForCalendar(year, month) {
  const m = Number(month)
  const y = Number(year)
  if (m === 1) return `HJ2 ${y - 1}`
  if (m <= 7) return `HJ1 ${y}`
  return `HJ2 ${y}`
}

/** @deprecated prefer periodForCalendar — kept for call sites with month/year */
export function periodForMonth(month, year = CURRENT_YEAR) {
  return periodForCalendar(year, month)
}

/** Default Bilat/Quali period + year for "today". */
export function defaultBilatPeriod(date = new Date()) {
  const m = date.getMonth() + 1
  const y = date.getFullYear()
  const period = periodForCalendar(y, m)
  const year = Number(period.split(" ").pop())
  return { year, period }
}
