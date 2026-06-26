import os
import resend

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "kineo@kineo.swiss")
CEO_EMAILS = os.environ.get("CEO_EMAILS", "ali.peters@kineo.swiss,sereina.urech@kineo.swiss").split(",")

def send_email(to: list, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        print(f"[EMAIL SKIPPED - no API key] To: {to} | Subject: {subject}")
        return False
    try:
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": f"Kineo AG <{FROM_EMAIL}>",
            "to": to,
            "subject": subject,
            "html": html,
        })
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

def email_zeg_alarm(alerts: list[dict]) -> bool:
    if not alerts:
        return False
    rows = "".join(f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;font-weight:600">{a['name']}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#888">{a['months']} Monate</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;color:#c0392b;font-weight:700">{a['avg_zeg']:.1f}%</td>
        </tr>""" for a in alerts)

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#006B6B;padding:24px;border-radius:8px 8px 0 0">
        <h2 style="color:white;margin:0">⚠️ ZEG-B Trend-Alarm — Kineo AG</h2>
      </div>
      <div style="background:white;padding:24px;border:1px solid #eee">
        <p style="color:#555">Folgende Mitarbeiter/innen haben <strong>2 oder mehr Monate in Folge</strong> einen ZEG-B unter 85%:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <thead>
            <tr style="background:#f5f5f5">
              <th style="padding:10px 14px;text-align:left;font-size:12px;color:#888;text-transform:uppercase">Mitarbeiter/in</th>
              <th style="padding:10px 14px;text-align:left;font-size:12px;color:#888;text-transform:uppercase">Monate unter 85%</th>
              <th style="padding:10px 14px;text-align:left;font-size:12px;color:#888;text-transform:uppercase">Ø ZEG-B</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="color:#555">Bitte Bilateral vorbereiten und Massnahmen besprechen.</p>
        <a href="https://kineo-umsatz-1.onrender.com" style="display:inline-block;background:#006B6B;color:white;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:700;margin-top:8px">
          App öffnen →
        </a>
      </div>
      <div style="padding:16px;color:#aaa;font-size:11px;text-align:center">
        Kineo AG Umsatzanalyse · Automatische Benachrichtigung
      </div>
    </div>"""

    return send_email(CEO_EMAILS, f"⚠️ ZEG-B Alarm: {len(alerts)} MA unter Ziel", html)

def email_csv_reminder(month_name: str, year: int) -> bool:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#856404;padding:24px;border-radius:8px 8px 0 0">
        <h2 style="color:white;margin:0">📋 CSV-Upload Erinnerung</h2>
      </div>
      <div style="background:white;padding:24px;border:1px solid #eee">
        <p style="color:#555">Die monatliche Umsatz-CSV für <strong>{month_name} {year}</strong> wurde noch nicht hochgeladen.</p>
        <p style="color:#555">Bitte Martino erinnern, den Export aus der Software zu machen und hochzuladen.</p>
        <a href="https://kineo-umsatz-1.onrender.com" style="display:inline-block;background:#006B6B;color:white;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:700;margin-top:8px">
          Zur App → Daten eingeben
        </a>
      </div>
      <div style="padding:16px;color:#aaa;font-size:11px;text-align:center">
        Kineo AG Umsatzanalyse · Automatische Benachrichtigung
      </div>
    </div>"""
    return send_email(CEO_EMAILS, f"📋 Erinnerung: CSV {month_name} {year} fehlt", html)

def email_new_ma(ma_names: list[str]) -> bool:
    names_html = "".join(f"<li style='padding:6px 0;color:#1a3a8a;font-weight:600'>{n}</li>" for n in ma_names)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#1a3a8a;padding:24px;border-radius:8px 8px 0 0">
        <h2 style="color:white;margin:0">👤 Neue Mitarbeiter in CSV</h2>
      </div>
      <div style="background:white;padding:24px;border:1px solid #eee">
        <p style="color:#555">Folgende <strong>unbekannte Namen</strong> wurden in der CSV gefunden:</p>
        <ul style="margin:12px 0;padding-left:20px">{names_html}</ul>
        <p style="color:#555">Bitte im Admin-Bereich erfassen und Arbeitstag-Muster hinterlegen.</p>
        <a href="https://kineo-umsatz-1.onrender.com" style="display:inline-block;background:#006B6B;color:white;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:700;margin-top:8px">
          Admin → Mitarbeiter erfassen
        </a>
      </div>
    </div>"""
    return send_email(CEO_EMAILS, f"👤 Neue MA in CSV: {', '.join(ma_names)}", html)
