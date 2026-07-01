export const CURRENT_YEAR = new Date().getFullYear()

const now = new Date()
export const DEFAULT_MONTH = now.getMonth() === 0 ? 12 : now.getMonth()
export const DEFAULT_YEAR = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear()

/** API base: empty in production Docker (nginx proxies /api), localhost in dev */
export const API = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "")

export function periodForMonth(month, year = CURRENT_YEAR) {
  return `${month <= 6 ? "HJ1" : "HJ2"} ${year}`
}
