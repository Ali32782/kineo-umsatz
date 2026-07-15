"""HJ2 2026 — Qualitative Ziele aus den Word-Vorlagen (2. Halbjahr).

Quellen (Downloads):
- Ziele Physiotherapie / Teamleiter / Standortlead / Lead CC / Lead BD / Fitness / CC / Billing
- Zielvereinbarung Head of Operations & Revenue 2026[3].docx
  → volle Ziele für Sereina.U + Anne.T
  → Teilbereiche Fitness (Ilaria), HYROX (Nina), Performance Lab/Laufanalysen (Marc + Nina)
"""
from __future__ import annotations

PERIOD = "HJ2 2026"
YEAR = 2026


def _goal(name: str, detail: str, *, sort_order: int = 0) -> dict:
    return {
        "name": name,
        "result": "",
        "status": "offen",
        "detail": detail.strip(),
        "sort_order": sort_order,
    }


# ── Bausteine Physiotherapie ───────────────────────────────────────────────

def _physio_oe(*, berichte_100: int) -> dict:
    # Proportionale Staffel wie in den Docs (15 bzw. 10 bei 100 %)
    if berichte_100 >= 15:
        staffel = "100 %: 15 · 90 %: 13 · 80 %: 12 · 60 %: 9 · 40 %: 6 Berichte"
    else:
        staffel = "100 %: 10 · 90 %: 9 · 80 %: 8 · 60 %: 6 · 40 %: 4 Berichte"
    return _goal(
        "Operational Excellence — Patientenberichte",
        (
            f"Bis 31.12.2026: qualitativ hochwertige Patientenberichte gemäss Pensum "
            f"({staffel}; weitere Pensen proportional). "
            "Anrechnung erst nach Qualitätsprüfung durch Martino. "
            "Messung: anerkannte Berichte quartalsweise; Ziel = Pensum-Soll erreicht."
        ),
        sort_order=0,
    )


def _physio_profit() -> dict:
    return _goal(
        "Profitabilität — Umsatzbudget",
        (
            "Bis 31.12.2026 mind. 100 % des individuellen Umsatzbudgets "
            "(bei 100 % Pensum CHF 220'000.– / Jahr; proportional zum Pensum). "
            "Monatliche Auswertung; Reflexion im Bilateral mit der Teamleitung."
        ),
        sort_order=1,
    )


def _physio_satisfaction() -> dict:
    return _goal(
        "Satisfaction — Patientenbindung",
        (
            "Bis 31.12.2026: langfristige Patientenbindung aktiv fördern "
            "(Verordnung ausschöpfen, vorausschauende Terminplanung, Abbrüche vermeiden). "
            "Messkennzahlen folgen mit dem neuen System im 2. HJ 2026; "
            "bis dahin Sensibilisierung und bewusste Umsetzung im Alltag."
        ),
        sort_order=2,
    )


def physio_goals(*, berichte_100: int = 15) -> list[dict]:
    goals = [_physio_oe(berichte_100=berichte_100), _physio_profit(), _physio_satisfaction()]
    for i, g in enumerate(goals):
        g["sort_order"] = i
    return goals


def _sop_standort() -> dict:
    return _goal(
        "SOPs Standort — Handbuch Physiotherapie",
        (
            "Bis 31.08.2026: Excel-Übersicht aller Standort-Aufgaben. "
            "Mit Head of Operations and Revenue priorisieren; "
            "5 zentrale Prozesse als SOPs ausarbeiten. "
            "Bis 31.12.2026: Handbuch mit den 5 SOPs fertig "
            "(z. B. Ämtli, Hygiene, Notfallkonzept, Schlüsselbox)."
        ),
    )


def _bd_fokuswochen() -> dict:
    return _goal(
        "Business Development — Fokuswochen",
        (
            "Während zweier Business-Development-Fokuswochen konkrete Ziele/Projekte "
            "festlegen und innerhalb der definierten Frist umsetzen."
        ),
    )


def _bilat_struktur() -> dict:
    return _goal(
        "Implementierung neuer Bilat-Struktur",
        (
            "Drei Bilats via Microsoft Teams am PC mit Read-AI-Protokoll "
            "(z. B. Aug./Okt./Dez.). Ali eingeladen (Feedback im Nachgang, nicht aktiv im Gespräch). "
            "Erkenntnisse dokumentieren; mind. eine konkrete Verbesserung aus dem Feedback umsetzen/definieren."
        ),
    )


def teamlead_goals() -> list[dict]:
    """Hanna & Clara — Teamleads Physio."""
    goals = [
        _goal(
            "Profitabilität — Team-Umsatzziel",
            "Umsatzzahlen à CHF 220'000.– pro Therapeut auf 100 % Pensum (Teamverantwortung).",
            sort_order=0,
        ),
        {**_bilat_struktur(), "sort_order": 1},
        {**_sop_standort(), "sort_order": 2},
        _goal(
            "Laufender Auftrag — Pläne & KPIs",
            "Monatliche Kontrolle der Pläne und Zeiterfassung; KPIs (Berichte, Umsatz) in den Bilats besprechen. (ohne Zielwertung)",
            sort_order=3,
        ),
    ]
    for g in physio_goals(berichte_100=10):
        goals.append({**g, "sort_order": len(goals)})
    return goals


def standortlead_goals() -> list[dict]:
    """Andrina, Helen, Raphael (+ Carmen als SL)."""
    goals = [
        {**_sop_standort(), "sort_order": 0},
        {**_bd_fokuswochen(), "sort_order": 1},
    ]
    for g in physio_goals(berichte_100=10):
        goals.append({**g, "sort_order": len(goals)})
    return goals


def lead_cc_goals() -> list[dict]:
    """Pamela — Teamlead Corporate Functions / CC."""
    return [
        {**_bilat_struktur(), "sort_order": 0},
        _goal(
            "SOPs & SLA — Customer Care",
            (
                "Bis 31.08.2026: Excel-Übersicht aller CC-Aufgaben; "
                "mit Head of Operations and Revenue priorisieren; "
                "5 Prozesse als SOPs. Bis 31.12.2026: Handbuch + SLA für Customer Care."
            ),
            sort_order=1,
        ),
        _goal(
            "Onboarding-Konzept — administrative Abläufe",
            (
                "Gemeinsam mit Sereina: alle admin. Onboarding-Schritte erfassen, "
                "standardisiertes Konzept inkl. Checkliste erstellen, validieren und "
                "für künftige Neueintritte bereitstellen."
            ),
            sort_order=2,
        ),
    ]


def lead_bd_goals() -> list[dict]:
    """Martino — Lead Business Development."""
    return [
        _goal(
            "SOPs — Fitness, HYROX, Shop, Billing/Insurance",
            (
                "Bis 31.08.2026: für Fitness, HYROX, Shop und Billing/Insurance "
                "je eine Excel-Übersicht mit Bereichsverantwortlichen; "
                "mit Head of Operations and Revenue priorisieren; zentrale SOPs. "
                "Bis 31.12.2026: Handbuch für alle vier Bereiche."
            ),
            sort_order=0,
        ),
        _goal(
            "SLA & Übergabe — Billing/Insurance an Susanne",
            (
                "Offboarding/Übergabe Billing & Insurance an Susanne planen; "
                "Prozesse dokumentieren; SLA erstellen; Übergabe + Wissenstransfer bis Austritt."
            ),
            sort_order=1,
        ),
        _goal(
            "Offboarding — Standort Escher-Wyss",
            (
                "Offboarding Escher-Wyss planen; Aufgaben/Prozesse/Kontakte dokumentieren; "
                "Übergabe an Standortleitung und Nina; Wissenstransfer bis Abgabedatum."
            ),
            sort_order=2,
        ),
    ]


# ── HOOR-Zielvereinbarung (Sereina / Anne) + Teilbereiche CC ───────────────

def _hoor_area(bereich: str, ziel: str, messgroesse: str, *, sort_order: int = 0) -> dict:
    return _goal(
        bereich,
        f"Ziel: {ziel}. Messung: {messgroesse}.",
        sort_order=sort_order,
    )


def hoor_goals() -> list[dict]:
    """Vollständige Zielvereinbarung Head of Operations & Revenue 2026."""
    rows = [
        (
            "Physiotherapie — Umsatz & Standards",
            "Ø CHF 220’000 Jahresumsatz pro Physio-FTE; einheitliche Leistungs-, Termin- und Angebotslogik",
            "Umsatz pro Physio-FTE; Einhaltung standardisierter Prozesse",
        ),
        (
            "Fitness — Mitglieder & Umsatz",
            "CHF 200 aktive Mitglieder; CHF 240’000 Jahresumsatz",
            "Anzahl Mitglieder; Umsatzstatistik",
        ),
        (
            "HYROX — Jahresumsatz",
            "CHF 180’000 Jahresumsatz",
            "Umsatzstatistik",
        ),
        (
            "Performance Lab inkl. Laufanalysen",
            "CHF 160’000 Jahresumsatz; klare Produkt- & Prozesslogik; hohe Auslastung der Analyse-Slots",
            "Umsatz; Auslastungsquote (%)",
        ),
        (
            "Team Lab",
            "Wirtschaftlich tragfähige Angebote für Teams & Vereine; skalierbare Formate & saubere Integration in den Betrieb",
            "Anzahl Angebote / Umsatz; Feedback Betriebsintegration",
        ),
        (
            "Shop / Retail",
            "CHF 360’000 Jahresumsatz; klare Produkt-, Lager- und Kassenprozesse; Integration in den Praxisalltag",
            "Umsatz; Lager- & Kassen-Check; Integrationstest",
        ),
        (
            "Customer Care",
            "Reibungslose Termin-, Kommunikations- und Abrechnungsprozesse; Minimierung umsatzrelevanter Verluste; hohe Servicequalität",
            "Anzahl Fehler/Verluste; Kundenzufriedenheit (Bewertung)",
        ),
        (
            "Billing & Insurance",
            "Korrekte, fristgerechte Rechnungsstellung; effizientes Mahnwesen; professionelle Kommunikation mit Krankenkassen",
            "Anzahl korrekt erstellter Rechnungen; Zahlungsverzögerungen; Feedback Krankenkassen",
        ),
        (
            "Liquidität & Zahlungseingänge",
            "Sicherung von Liquidität & Zahlungseingängen",
            "Cashflow-Überwachung; Mahnquote",
        ),
    ]
    return [
        _hoor_area(name, ziel, mess, sort_order=i)
        for i, (name, ziel, mess) in enumerate(rows)
    ]


def fitness_goals() -> list[dict]:
    """Ilaria — CC Fitness (SOP + HOOR-Teilbereich)."""
    return [
        _goal(
            "SOPs — Fitness (mit Martino)",
            (
                "Bis 31.08.2026: Excel-Übersicht aller Fitness-Aufgaben gemeinsam mit Martino; "
                "mit Head of Operations and Revenue priorisieren; zentrale SOPs. "
                "Bis 31.12.2026: Handbuch-Beitrag Fitness."
            ),
            sort_order=0,
        ),
        _goal(
            "Fitness — Mitglieder & Umsatz",
            (
                "Ziel: 200 aktive Mitglieder und CHF 240’000 Jahresumsatz. "
                "Messung: Mitgliederzahlen; Umsatzstatistik."
            ),
            sort_order=1,
        ),
    ]


def nina_goals() -> list[dict]:
    """Nina — HYROX + Performance Lab."""
    return [
        _goal(
            "HYROX — Jahresumsatz",
            "Ziel: CHF 180’000 Jahresumsatz. Messung: Umsatzstatistik.",
            sort_order=0,
        ),
        _goal(
            "Performance Lab inkl. Laufanalysen",
            (
                "Ziel: CHF 160’000 Jahresumsatz; klare Produkt- & Prozesslogik; "
                "hohe Auslastung der Analyse-Slots. Messung: Umsatz; Auslastungsquote (%)."
            ),
            sort_order=1,
        ),
    ]


def marc_goals() -> list[dict]:
    """Marc — Performance Lab / Runnerslab (Laufanalysen)."""
    return [
        _goal(
            "Performance Lab inkl. Laufanalysen / Runnerslab",
            (
                "Ziel: CHF 160’000 Jahresumsatz; klare Produkt- & Prozesslogik; "
                "hohe Auslastung der Analyse-Slots (inkl. Runnerslab). "
                "Messung: Umsatzstatistik; Auslastungsquote (%)."
            ),
            sort_order=0,
        ),
        _goal(
            "HYROX — Unterstützung Umsatzziel",
            (
                "Mitverantwortung am HYROX-Jahresumsatzziel von CHF 180’000 "
                "(Abstimmung mit Nina). Messung: Umsatzstatistik."
            ),
            sort_order=1,
        ),
    ]


def cc_larissa_goals() -> list[dict]:
    """Larissa — Customer Care."""
    return [
        _goal(
            "SOPs — Customer Care (mit Pamela)",
            (
                "Bis 31.08.2026: Excel-Übersicht aller CC-Aufgaben mit Pamela; "
                "mit Head of Operations and Revenue priorisieren; 5 SOPs. "
                "Bis 31.12.2026: Handbuch mit den fünf SOPs."
            ),
            sort_order=0,
        ),
    ]


def billing_goals() -> list[dict]:
    """Susanne — Billing/Insurance."""
    return [
        _goal(
            "SOPs — Billing/Insurance (mit Martino)",
            (
                "Bis 31.08.2026: Excel-Übersicht Billing/Insurance mit Martino; "
                "mit Head of Operations and Revenue priorisieren; zentrale SOPs. "
                "Bis 31.12.2026: Handbuch-Beitrag Billing/Insurance."
            ),
            sort_order=0,
        ),
    ]


# Therapeut:innen Physio (Standard-Staffel 15 Berichte) — ohne Leads/SL/CC
PHYSIO_THERAPEUTEN = [
    "Barbara.V",
    "Emma.L",
    "Eva.D",
    "Joëlle.R",
    "Lucrecia.G",
    "Meike.V",
    "Noah.S",
    "Pablo.G",
    "Pablo.M",
    "Sonia.M",
    "Valerio.S",
]

TEAMLEADS = ["Hanna.R", "Clara.B"]
STANDORTLEADS = ["Andrina.K", "Helen.S", "Raphael.H", "Carmen.W"]  # Carmen = SL Stauffacher
HOOR_OWNERS = ["Sereina.U", "Anne.T"]  # Head of Ops & Revenue + Head of Marketing & Design


def goals_for_ma(ma_name: str) -> list[dict]:
    if ma_name in TEAMLEADS:
        return teamlead_goals()
    if ma_name in STANDORTLEADS:
        return standortlead_goals()
    if ma_name == "Pamela.P":
        return lead_cc_goals()
    if ma_name == "Martino.C":
        return lead_bd_goals()
    if ma_name == "Ilaria.F":
        return fitness_goals()
    if ma_name == "Nina.S":
        return nina_goals()
    if ma_name == "Marc.W":
        return marc_goals()
    if ma_name in HOOR_OWNERS:
        return hoor_goals()
    if ma_name == "Larissa.S":
        return cc_larissa_goals()
    if ma_name == "Susanne.K":
        return billing_goals()
    if ma_name in PHYSIO_THERAPEUTEN:
        return physio_goals(berichte_100=15)
    return []


def all_ma_goals() -> dict[str, list[dict]]:
    names = (
        list(PHYSIO_THERAPEUTEN)
        + TEAMLEADS
        + STANDORTLEADS
        + HOOR_OWNERS
        + ["Pamela.P", "Martino.C", "Ilaria.F", "Nina.S", "Marc.W", "Larissa.S", "Susanne.K"]
    )
    return {ma: goals_for_ma(ma) for ma in names if goals_for_ma(ma)}
