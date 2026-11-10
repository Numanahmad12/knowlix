"""Generate the two synthetic source PDFs for the EvalLens golden set.

The PDFs are fully synthetic documents written for this harness — every
number is invented by the author and internally consistent, so the golden
set's expected answers are unambiguous. Regenerate with:

    python -m evallens.generate_docs

The generated files are committed under evallens/documents/ so eval runs
are reproducible without regeneration. (reportlab is already a
test dependency of the backend — see requirements.txt.)
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

DOCS_DIR = Path(__file__).resolve().parent / "documents"

# ── Document B: Meridian Wind Farm ────────────────────────────────────────────

MERIDIAN_TITLE = "Meridian Wind Farm — Environmental Impact Assessment (Excerpt)"

MERIDIAN_PAGES = [
    """Project overview. The Meridian Wind Farm is located near Jaisalmer in
Rajasthan. The project consists of 48 wind turbines with a total installed
capacity of 144 megawatts, at 3 megawatts per turbine. The developer is
Meridian Renewables Pvt Ltd. Construction began in January 2024 and
commissioning is expected in December 2026. The total project cost is
1,150 crore rupees.""",
    """Turbine specifications. Each turbine is rated at 3 megawatts, with a hub
height of 120 metres and a rotor diameter of 150 metres. The cut-in wind
speed is 3 metres per second, the rated wind speed is 12 metres per
second, and the cut-out wind speed is 25 metres per second. The wind farm
is expected to generate 380 gigawatt-hours per year at a capacity factor
of 30 percent.""",
    """Bird and bat survey. A two-year survey carried out in 2022 and 2023
recorded 64 bird species in the project area. Collision risk modelling
predicts 2.1 bird fatalities per turbine per year. Mitigation measures
include curtailment during peak migration months, March to April and
September to October, and radar-activated shutdown. Bat activity is
highest in July and August.""",
    """Noise and shadow flicker. The predicted noise level at the nearest
residence, 1.2 kilometres away, is 38 decibels (A-weighted), below the
45 decibel daytime limit and the 40 decibel night-time limit. Shadow
flicker is predicted to reach a maximum of 18 hours per year at the
nearest house, below the 30-hour guideline.""",
    """Water and land use. The project covers 62 hectares in total, with a
permanent footprint of 18 hectares. Water use during construction is
45,000 litres per day from a licensed borewell. As compensation, 12,000
native trees will be planted.""",
    """Community and jobs. Construction will create 320 jobs and operations
will create 45 permanent jobs. A community benefit fund of 2.4 crore
rupees per year will be established. 85 percent of the construction
workforce will be hired locally. Grid connection is via a 220 kilovolt
substation 8 kilometres away.""",
]

# ── Document C: Kaveri River Basin Water Quality Study ────────────────────────

KAVERI_TITLE = "Kaveri River Basin Water Quality Study 2025"

KAVERI_PAGES = [
    """Study scope. This study monitored 18 stations along the Kaveri River,
from Talakaveri in Karnataka to Poompuhar in Tamil Nadu, with samples
collected monthly from January to December 2025. The study was conducted
by the Central Water Commission together with the State Pollution Control
Boards. The parameters measured were pH, dissolved oxygen, biochemical
oxygen demand, total coliform, turbidity, and nitrate.""",
    """pH results. The pH ranged from 6.8 to 8.4 across all stations, within
the acceptable range of 6.5 to 8.5. The lowest pH of 6.8 was recorded at
Station 14, Erode, in August. The highest pH of 8.4 was recorded at
Station 3, Mysuru, in March.""",
    """Dissolved oxygen. Dissolved oxygen ranged from 4.1 to 8.9 milligrams
per litre. 14 of the 18 stations met the standard of at least 5 milligrams
per litre for bathing water. The worst dissolved oxygen level, 4.1
milligrams per litre, was recorded at Station 14, Erode, in September.
The best level, 8.9 milligrams per litre, was recorded at Station 1,
Talakaveri, in January.""",
    """Biochemical oxygen demand and coliform. Biochemical oxygen demand
ranged from 1.2 to 9.8 milligrams per litre. The limit of 3 milligrams per
litre was exceeded at 6 stations, all downstream of urban centres. Total
coliform peaked at 24,000 MPN per 100 millilitres at Station 15,
Tiruchirappalli, in October, against a limit of 500 MPN per 100
millilitres.""",
    """Nitrate and turbidity. Nitrate ranged from 2.1 to 18.6 milligrams per
litre, below the drinking-water limit of 45 milligrams per litre at all
stations. Turbidity peaked at 68 NTU during the July monsoon at Station 9,
Srirangapatna. The dry-season average turbidity was 12 NTU.""",
    """Recommendations. The study makes four recommendations. First, upgrade
sewage treatment at Erode and Tiruchirappalli. Second, create riparian
buffer zones of 30 metres along urban stretches. Third, install real-time
monitoring at 6 priority stations by June 2026. Fourth, launch a community
reporting app. The estimated cost of the recommendations is 86 crore rupees
over three years.""",
]


def _write_pdf(path: Path, title: str, pages: list[str]) -> None:
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    body_style.fontSize = 12
    body_style.leading = 17
    story = [Paragraph(title, title_style), Spacer(1, 12)]
    for i, page_text in enumerate(pages):
        if i > 0:
            story.append(PageBreak())
            story.append(Paragraph(f"{title} — Page {i + 1}", styles["Heading3"]))
            story.append(Spacer(1, 8))
        story.append(Paragraph(" ".join(page_text.split()), body_style))
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    doc.build(story)
    print(f"wrote {path} ({len(pages)} pages)")


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    _write_pdf(DOCS_DIR / "meridian_wind_farm.pdf", MERIDIAN_TITLE, MERIDIAN_PAGES)
    _write_pdf(DOCS_DIR / "kaveri_water_quality.pdf", KAVERI_TITLE, KAVERI_PAGES)


if __name__ == "__main__":
    main()
