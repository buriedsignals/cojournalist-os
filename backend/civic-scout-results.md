# Civic Scout Pipeline Audit Results
Generated: 2026-04-21T11:51:19+00:00

**Scenarios:** 10

## Summary Matrix

| Scenario | URL | Candidates | PDF Size | Pages | Promises | Firecrawl | LlamaParse | Gemini In | Time (ms) | Status |
|----------|-----|------------|----------|-------|----------|-----------|------------|-----------|-----------|--------|
| Basel: Grosser Rat (DE) | https://grosserrat.bs.ch/ratsbetrieb/ratsprotokoll... | 1 | 0KB | 0 | 3 | 1 | 0pg | 3,619 | 6791 | OK |
| Basel: Grosser Rat + criteria (DE) | https://grosserrat.bs.ch/ratsbetrieb/ratsprotokoll... | 1 | 0KB | 0 | 0 | 1 | 0pg | 3,619 | 5219 | OK |
| Zurich: Gemeinderat (DE) | https://www.gemeinderat-zuerich.ch/protokolle... | 1 | 0KB | 0 | 0 | 1 | 0pg | 891 | 12956 | OK |
| Lausanne: Conseil communal (FR) | https://www.lausanne.ch/officiel/autorites/conseil... | 1 | 0KB | 0 | 0 | 1 | 0pg | 1,480 | 20980 | OK |
| Bern: Stadtrat (DE) | https://www.bern.ch/politik-und-verwaltung/stadtra... | 1 | 0KB | 0 | 0 | 1 | 0pg | 585 | 87306 | OK |
| Bozeman: City Commission (EN) | https://www.bozeman.net/departments/city-commissio... | 5 | 0KB | 0 | 0 | 1 | 0pg | 855 | 21802 | OK |
| Bozeman: City Commission + criteria (EN) | https://www.bozeman.net/departments/city-commissio... | 5 | 0KB | 0 | 0 | 1 | 0pg | 827 | 8712 | OK |
| Madison WI: Common Council (EN) | https://www.cityofmadison.com/council... | 5 | 0KB | 0 | 0 | 1 | 0pg | 2,464 | 26008 | OK |
| Zermatt: Gemeinde (DE) | https://gemeinde.zermatt.ch... | 5 | 0KB | 0 | 0 | 1 | 0pg | 2,408 | 23551 | OK |
| Zermatt: Gemeinde + criteria (DE) | https://gemeinde.zermatt.ch... | 5 | 0KB | 0 | 0 | 1 | 0pg | 2,408 | 17920 | OK |

## Step Timing Breakdown

| Scenario | Discover | Download PDF | Parse PDF | Extract | Total |
|----------|----------|--------------|-----------|---------|-------|
| Basel: Grosser Rat (DE) | 4742ms | --ms | --ms | 1436ms | 6791ms |
| Basel: Grosser Rat + criteria (DE) | 3067ms | --ms | --ms | 1435ms | 5219ms |
| Zurich: Gemeinderat (DE) | 8910ms | --ms | --ms | 773ms | 12956ms |
| Lausanne: Conseil communal (FR) | 13361ms | --ms | --ms | 3423ms | 20980ms |
| Bern: Stadtrat (DE) | 30062ms | --ms | --ms | 922ms | 87306ms |
| Bozeman: City Commission (EN) | 7754ms | --ms | --ms | 10645ms | 21802ms |
| Bozeman: City Commission + criteria (EN) | 4399ms | --ms | --ms | 822ms | 8712ms |
| Madison WI: Common Council (EN) | 6757ms | --ms | --ms | 18638ms | 26008ms |
| Zermatt: Gemeinde (DE) | 6860ms | --ms | --ms | 16077ms | 23551ms |
| Zermatt: Gemeinde + criteria (DE) | 7783ms | --ms | --ms | 9737ms | 17920ms |

## Cost Estimates

| Scenario | Firecrawl Credits | LlamaParse Pages | Gemini Tokens In | Gemini Tokens Out |
|----------|-------------------|-----------------|-----------------|------------------|
| Basel: Grosser Rat (DE) | 1 | 0 | 3,619 | 120 |
| Basel: Grosser Rat + criteria (DE) | 1 | 0 | 3,619 | 0 |
| Zurich: Gemeinderat (DE) | 1 | 0 | 891 | 0 |
| Lausanne: Conseil communal (FR) | 1 | 0 | 1,480 | 0 |
| Bern: Stadtrat (DE) | 1 | 0 | 585 | 0 |
| Bozeman: City Commission (EN) | 1 | 0 | 855 | 0 |
| Bozeman: City Commission + criteria (EN) | 1 | 0 | 827 | 0 |
| Madison WI: Common Council (EN) | 1 | 0 | 2,464 | 0 |
| Zermatt: Gemeinde (DE) | 1 | 0 | 2,408 | 0 |
| Zermatt: Gemeinde + criteria (DE) | 1 | 0 | 2,408 | 0 |
| **TOTAL** | **10** | **0** | **19,156** | **120** |

## Quality Checks

| Scenario | Discovery | URL Coverage | Promises |
|----------|-----------|--------------|----------|
| Basel: Grosser Rat (DE) | PASS (1 candidates, 1 high-confidence) | PASS (1/1 on-domain) | PASS (3 promises, 3 with due_date) |
| Basel: Grosser Rat + criteria (DE) | PASS (1 candidates, 1 high-confidence) | PASS (1/1 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Zurich: Gemeinderat (DE) | PASS (1 candidates, 1 high-confidence) | PASS (1/1 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Lausanne: Conseil communal (FR) | PASS (1 candidates, 1 high-confidence) | PASS (1/1 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Bern: Stadtrat (DE) | PASS (1 candidates, 1 high-confidence) | PASS (1/1 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Bozeman: City Commission (EN) | PASS (5 candidates, 4 high-confidence) | PASS (5/5 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Bozeman: City Commission + criteria (EN) | PASS (5 candidates, 4 high-confidence) | PASS (5/5 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Madison WI: Common Council (EN) | PASS (5 candidates, 3 high-confidence) | PASS (5/5 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Zermatt: Gemeinde (DE) | PASS (5 candidates, 5 high-confidence) | PASS (5/5 on-domain) | WARN (no promises extracted (may be expected for some documents)) |
| Zermatt: Gemeinde + criteria (DE) | PASS (5 candidates, 4 high-confidence) | PASS (5/5 on-domain) | WARN (no promises extracted (may be expected for some documents)) |

## Detailed Results

### Basel: Grosser Rat (DE)

- **URL:** https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1
- **Language:** de
- **Criteria:** --
- **Candidates found:** 1
- **PDF processed:** https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 12477 chars
- **Promises extracted:** 3
- **Total time:** 6791ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=3,619  out=120

**Step timing:**
- `discover`: 4742ms
- `download_and_parse`: 612ms
- `extract_promises`: 1436ms

**Candidates (top 5):**
- [0.95] https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle
  This page likely lists and links to multiple council meeting protocol documents over time.

**Promises (3):**
1. The council will make audiovisual minutes available for sessions in April 2026.
   Due: 2026-04-30 (confidence: medium)
2. The council will make audiovisual minutes available for sessions in March 2026.
   Due: 2026-03-31 (confidence: medium)
3. The council will make audiovisual minutes available for sessions in February 2026.
   Due: 2026-02-28 (confidence: medium)

### Basel: Grosser Rat + criteria (DE)

- **URL:** https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1
- **Language:** de
- **Criteria:** Wohnungspolitik
- **Candidates found:** 1
- **PDF processed:** https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 12477 chars
- **Promises extracted:** 0
- **Total time:** 5219ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=3,619  out=0

**Step timing:**
- `discover`: 3067ms
- `download_and_parse`: 716ms
- `extract_promises`: 1435ms

**Candidates (top 5):**
- [0.90] https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle
  This page likely serves as an index for council meeting protocols, listing individual protocol docum

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Zurich: Gemeinderat (DE)

- **URL:** https://www.gemeinderat-zuerich.ch/protokolle
- **Language:** de
- **Criteria:** --
- **Candidates found:** 1
- **PDF processed:** https://www.gemeinderat-zuerich.ch/protokolle
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 1564 chars
- **Promises extracted:** 0
- **Total time:** 12956ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=891  out=0

**Step timing:**
- `discover`: 8910ms
- `download_and_parse`: 3272ms
- `extract_promises`: 773ms

**Candidates (top 5):**
- [0.90] https://www.gemeinderat-zuerich.ch/protokolle
  This page likely serves as an index or listing for official protocols of council meetings.

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Lausanne: Conseil communal (FR)

- **URL:** https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html
- **Language:** fr
- **Criteria:** --
- **Candidates found:** 1
- **PDF processed:** https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 3922 chars
- **Promises extracted:** 0
- **Total time:** 20980ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=1,480  out=0

**Step timing:**
- `discover`: 13361ms
- `download_and_parse`: 4195ms
- `extract_promises`: 3423ms

**Candidates (top 5):**
- [0.90] https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html
  This page likely serves as an index for council meeting minutes and proceedings, linking to past off

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Bern: Stadtrat (DE)

- **URL:** https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen
- **Language:** de
- **Criteria:** Klimaschutz
- **Candidates found:** 1
- **PDF processed:** https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 341 chars
- **Promises extracted:** 0
- **Total time:** 87306ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=585  out=0

**Step timing:**
- `discover`: 30062ms
- `download_and_parse`: 56321ms
- `extract_promises`: 922ms

**Candidates (top 5):**
- [0.90] https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen
  This page likely lists or links to council meetings, potentially including minutes or related docume

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Bozeman: City Commission (EN)

- **URL:** https://www.bozeman.net/departments/city-commission
- **Language:** en
- **Criteria:** --
- **Candidates found:** 5
- **PDF processed:** https://www.bozeman.net/departments/city-commission/city-documents
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 1420 chars
- **Promises extracted:** 0
- **Total time:** 21802ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=855  out=0

**Step timing:**
- `discover`: 7754ms
- `download_and_parse`: 3402ms
- `extract_promises`: 10645ms

**Candidates (top 5):**
- [0.90] https://www.bozeman.net/departments/city-commission/city-documents
  This page likely serves as a central index for official city documents, including meeting protocols 
- [0.85] https://www.bozeman.net/departments/city-commission/meeting-agendas
  This page is expected to list meeting agendas, which often precede or are linked to meeting minutes 
- [0.75] https://www.bozeman.net/departments/city-commission/meeting-videos
  This page could offer a listing of meeting videos, potentially with links to associated official doc
- [0.70] https://www.bozeman.net/departments/city-commission/commission-and-boards-calendar
  This page acts as a calendar for commission and board meetings, which may link to published proceedi
- [0.60] https://www.bozeman.net/departments/city-commission
  The main city commission page might provide links to various sub-sections, including those that hous

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Bozeman: City Commission + criteria (EN)

- **URL:** https://www.bozeman.net/departments/city-commission
- **Language:** en
- **Criteria:** housing policy
- **Candidates found:** 5
- **PDF processed:** https://www.bozeman.net/departments/city-commission/meeting-agendas
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 1311 chars
- **Promises extracted:** 0
- **Total time:** 8712ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=827  out=0

**Step timing:**
- `discover`: 4399ms
- `download_and_parse`: 3489ms
- `extract_promises`: 822ms

**Candidates (top 5):**
- [0.90] https://www.bozeman.net/departments/city-commission/meeting-agendas
  This page is highly likely to list and link to past and future meeting agendas, which are precursors
- [0.85] https://www.bozeman.net/departments/city-commission/commission-and-boards-calendar
  This page likely lists upcoming and past meetings, potentially linking to associated documents like 
- [0.80] https://www.bozeman.net/departments/city-commission/city-documents
  This page likely serves as a central repository for various official city documents, potentially inc
- [0.70] https://www.bozeman.net/departments/city-commission/meeting-videos
  This page may provide access to recordings of meetings, which often accompany or substitute for writ
- [0.60] https://www.bozeman.net/departments/city-commission
  The main department page may provide an overview and links to various subsections, including those t

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Madison WI: Common Council (EN)

- **URL:** https://www.cityofmadison.com/council
- **Language:** en
- **Criteria:** --
- **Candidates found:** 5
- **PDF processed:** https://www.cityofmadison.com/council/meetings-agendas
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 7859 chars
- **Promises extracted:** 0
- **Total time:** 26008ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=2,464  out=0

**Step timing:**
- `discover`: 6757ms
- `download_and_parse`: 612ms
- `extract_promises`: 18638ms

**Candidates (top 5):**
- [0.95] https://www.cityofmadison.com/council/meetings-agendas
  This page is explicitly labeled for meetings and agendas, strongly suggesting it will host listings 
- [0.90] https://www.cityofmadison.com/council
  This page serves as a central hub for the City Council, likely containing links to important documen
- [0.70] https://www.cityofmadison.com/council/district20/blog/2023-12-06/district-20-forward-planning-2024
  While a blog post, the title 'District 20 Forward Planning 2024' suggests it may link to or summariz
- [0.65] https://www.cityofmadison.com/council/district10/blog/2023-11-26/winter-notices-snow-sidewalks-parking
  This blog post about winter notices may link to or summarize official directives or decisions relate
- [0.65] https://www.cityofmadison.com/council/district19/blog/2026-02-13/latest-housing-snapshot-report-published
  This post announcing the publication of a housing snapshot report likely links to an official docume

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Zermatt: Gemeinde (DE)

- **URL:** https://gemeinde.zermatt.ch
- **Language:** de
- **Criteria:** --
- **Candidates found:** 5
- **PDF processed:** https://gemeinde.zermatt.ch/urversammlung/protokoll
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 7635 chars
- **Promises extracted:** 0
- **Total time:** 23551ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=2,408  out=0

**Step timing:**
- `discover`: 6860ms
- `download_and_parse`: 613ms
- `extract_promises`: 16077ms

**Candidates (top 5):**
- [0.95] https://gemeinde.zermatt.ch/urversammlung/protokoll
  This page likely serves as an index or listing for protocol documents from the 'Urversammlung' (muni
- [0.85] https://gemeinde.zermatt.ch/news
  This page is a general news section that may contain recurring updates on council decisions and even
- [0.80] https://gemeinde.zermatt.ch/abstimmungen-und-wahlen
  This page is likely to list or link to official documents related to past and future votes and elect
- [0.75] https://gemeinde.zermatt.ch/news/archiv/2024
  This page is an archive of news from 2024, which could contain recurring updates or published decisi
- [0.70] https://gemeinde.zermatt.ch/news/archiv/2023/05
  This page is a specific monthly archive of news from 2023, potentially listing recurring updates or 

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

### Zermatt: Gemeinde + criteria (DE)

- **URL:** https://gemeinde.zermatt.ch
- **Language:** de
- **Criteria:** Infrastruktur
- **Candidates found:** 5
- **PDF processed:** https://gemeinde.zermatt.ch/urversammlung/protokoll
- **PDF size:** 0KB
- **Parsed pages:** ~0
- **Text length:** 7635 chars
- **Promises extracted:** 0
- **Total time:** 17920ms
- **Firecrawl credits:** 1
- **Gemini tokens:** in=2,408  out=0

**Step timing:**
- `discover`: 7783ms
- `download_and_parse`: 398ms
- `extract_promises`: 9737ms

**Candidates (top 5):**
- [0.90] https://gemeinde.zermatt.ch/urversammlung/protokoll
  This page likely lists and links to past meeting protocols of the 'Urversammlung' over time.
- [0.80] https://gemeinde.zermatt.ch/news
  This is a general news page that may contain recurring updates on council decisions and official ann
- [0.75] https://gemeinde.zermatt.ch/abstimmungen-und-wahlen
  This page is likely an index for past referendums, votes, and elections, which often involve officia
- [0.70] https://gemeinde.zermatt.ch/news/archiv/2024
  This page appears to be an archive for news from 2024, potentially containing records of council mee
- [0.65] https://gemeinde.zermatt.ch/news/archiv/2023/05
  This page is an archive for a specific month in 2023, which could contain records of council meeting

**Quality issues:**
- promises (WARN): no promises extracted (may be expected for some documents)

---
## Identified Flaws

- **Basel: Grosser Rat (DE)**: Only 1 candidate(s) found
- **Basel: Grosser Rat + criteria (DE)**: Only 1 candidate(s) found
- **Basel: Grosser Rat + criteria (DE)**: 12477 chars parsed but 0 promises extracted
- **Zurich: Gemeinderat (DE)**: Only 1 candidate(s) found
- **Zurich: Gemeinderat (DE)**: 1564 chars parsed but 0 promises extracted
- **Lausanne: Conseil communal (FR)**: Only 1 candidate(s) found
- **Lausanne: Conseil communal (FR)**: 3922 chars parsed but 0 promises extracted
- **Bern: Stadtrat (DE)**: Only 1 candidate(s) found
- **Bern: Stadtrat (DE)**: 341 chars parsed but 0 promises extracted
- **Bozeman: City Commission (EN)**: 1420 chars parsed but 0 promises extracted
- **Bozeman: City Commission + criteria (EN)**: 1311 chars parsed but 0 promises extracted
- **Madison WI: Common Council (EN)**: 7859 chars parsed but 0 promises extracted
- **Zermatt: Gemeinde (DE)**: 7635 chars parsed but 0 promises extracted
- **Zermatt: Gemeinde + criteria (DE)**: 7635 chars parsed but 0 promises extracted

## Test Inputs

| Scenario | URL | Language | Criteria |
|----------|-----|----------|----------|
| Basel: Grosser Rat (DE) | https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1 | de | -- |
| Basel: Grosser Rat + criteria (DE) | https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1 | de | Wohnungspolitik |
| Zurich: Gemeinderat (DE) | https://www.gemeinderat-zuerich.ch/protokolle | de | -- |
| Lausanne: Conseil communal (FR) | https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html | fr | -- |
| Bern: Stadtrat (DE) | https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen | de | Klimaschutz |
| Bozeman: City Commission (EN) | https://www.bozeman.net/departments/city-commission | en | -- |
| Bozeman: City Commission + criteria (EN) | https://www.bozeman.net/departments/city-commission | en | housing policy |
| Madison WI: Common Council (EN) | https://www.cityofmadison.com/council | en | -- |
| Zermatt: Gemeinde (DE) | https://gemeinde.zermatt.ch | de | -- |
| Zermatt: Gemeinde + criteria (DE) | https://gemeinde.zermatt.ch | de | Infrastruktur |

## Raw Data (JSON)

```json
[
  {
    "scenario": "Basel: Grosser Rat (DE)",
    "url": "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1",
    "language": "de",
    "criteria": null,
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 4742,
        "candidate_count": 1,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 612,
        "text": "# Protokolle/Videos\n\nDie Protokolle der Plenumssitzungen sind seit 2004 als Vollprotokoll abrufbar. Ab 2010 sind auch Audios und ab 2023 Videos verf\u00fcgbar; die einzelnen Voten sind downloadbar (![Symbol Play/Abspielen](https://grosserrat.bs.ch/images/system/icons/play.svg)). Auch das Stimmverhalten der Ratsmitglieder\u00a0(![Symbol Abstimmungsurne](https://grosserrat.bs.ch/images/system/icons/abstimmung.svg)) ist integriert.\n\n[Nutzungsbestimmungen](https://grosserrat.bs.ch/images/dateien/Nutzungsbedingungen_Video-Bild-Ton_2024.pdf) (PDF) \\| [Ratsprotokolle 1690-2011](https://dls.staatsarchiv.bs.ch/records/hierarchy/199821?context=%2Fsearch%3Fpage%3D1%26page_size%3D25%26query%3DProtokolle%2520Grosser%2520Rat%26advanced_query%3Dfalse)\u00a0(Staatsarchiv)\n\n### Amtsjahr 2026/2027\n\n[![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/ausklapper_black.svg)](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos#protokolle_2026)\n\n| 15./22. April 2026 | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/) | Kein Vollprotokoll\u00a0April 2026 vorhanden | (der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-04-15.pdf) | [Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-04-15.pdf) |\n| Mittwoch22.04.2026 | Kein Wortprotokoll Sitzung 12 (20 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 11 (15 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 10 (09 Uhr)\u00a022.04.2026 vorhanden | Kein Wortprotokoll Sitzung 12 (20 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 11 (15 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 10 (09 Uhr)\u00a022.04.2026 vorhanden | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/)<br>Kein Vollprotokoll\u00a0April 2026 vorhanden<br>(der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-04-15.pdf)<br>[Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-04-15.pdf) |\n| Mittwoch15.04.2026 | Kein Wortprotokoll Sitzung 9 (15 Uhr)\u00a015.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 8 (09 Uhr)\u00a015.04.2026 vorhanden |\n| 11./18. M\u00e4rz 2026 | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/) | Kein Vollprotokoll\u00a0M\u00e4rz 2026 vorhanden | (der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-03-11.pdf) | [Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-03-11.pdf) |\n| Mittwoch18.03.2026 | Kein Wortprotokoll Sitzung 7 (15 Uhr)\u00a018.03.2026 vorhanden<br>Kein Wortprotokoll Sitzung 6 (09 Uhr)\u00a018.03.2026 vorhanden | Kein Wortprotokoll Sitzung 7 (15 Uhr)\u00a018.03.2026 vorhanden<br>Kein Wortprotokoll Sitzung 6 (09 Uhr)\u00a018.03.2026 vorhanden | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/)<br>Kein Vollprotokoll\u00a0M\u00e4rz 2026 vorhanden<br>(der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-03-11.pdf)<br>[Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-03-11.pdf) |\n| Mittwoch11.03.2026 | Kein Wortprotokoll Sitzung 5 (15 Uhr)\u00a011.03.2026 vorhanden<br>Kein Wortprotokoll Sitzung 4 (09 Uhr)\u00a011.03.2026 vorhanden |\n| 04./11. Februar 2026 | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/) | Kein Vollprotokoll\u00a0Februar 2026 vorhanden | (der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-02-04.pdf) | [Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-02-04.pdf) |\n| Mittwoch11.02.2026 | Kein Wortprotokoll Sitzung 3 (09 Uhr)\u00a011.02.2026 vorhanden | Kein Wortprotokoll Sitzung 3 (09 Uhr)\u00a011.02.2026 vorhanden | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/)<br>Kein Vollprotokoll\u00a0Februar 2026 vorhanden<br>(der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-02-04.pdf)<br>[Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-02-04.pdf) |\n| Mittwoch04.02.2026 | Kein Wortprotokoll Sitzung 2 (15 Uhr)\u00a004.02.2026 vorhanden<br>Kein Wortprotokoll Sitzung 1 (09 Uhr)\u00a004.02.2026 vorhanden |\n\n[Alle Ratsprotokolle und Abstimmungsresultate](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos?all=1)\n\n**Parlamentswissen**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Der Grosse Rat](https://grosserrat.bs.ch/parlamentswissen/der-grosse-rat)\n- [Aufgaben](https://grosserrat.bs.ch/parlamentswissen/aufgaben)\n- [Gewaltenteilung](https://grosserrat.bs.ch/parlamentswissen/gewaltenteilung)\n- [So entsteht ein Gesetz](https://grosserrat.bs.ch/parlamentswissen/so-entsteht-ein-gesetz)\n\n- [Parlamentarische Instrumente](https://grosserrat.bs.ch/parlamentswissen/parlamentarische-instrumente)\n- [Mitbestimmung der Bev\u00f6lkerung](https://grosserrat.bs.ch/parlamentswissen/mitbestimmung-der-bevoelkerung)\n- [Wahlen](https://grosserrat.bs.ch/parlamentswissen/wahlen)\n- [Ergebnisse Grossratswahlen](https://grosserrat.bs.ch/parlamentswissen/ergebnisse-grossratswahlen)\n- [Was kostet ein Parlament?](https://grosserrat.bs.ch/parlamentswissen/was-kostet-ein-parlament)\n\n- [Politw\u00f6rterbuch A - Z](https://grosserrat.bs.ch/parlamentswissen/politwoerterbuch-a-z)\n- [Brosch\u00fcre: Politik in BS kurz erkl\u00e4rt \ud83d\udcc4](https://grosserrat.bs.ch/images/dateien/broschuere/broschuere.pdf)\n- [Ratsgeschichte](https://grosserrat.bs.ch/parlamentswissen/ratsgeschichte)\n  - [Entwicklung der Parteien](https://grosserrat.bs.ch/parlamentswissen/ratsgeschichte/entwicklung-der-parteien)\n- [Parlamentarische Recherche](https://grosserrat.bs.ch/parlamentswissen/parlamentarische-recherche)\n\n**Gremien**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Pr\u00e4sidium und B\u00fcro](https://grosserrat.bs.ch/gremien/praesidium-und-buero)\n- [Oberaufsicht](https://grosserrat.bs.ch/gremien/oberaufsicht)\n  - [Gesch\u00e4ftspr\u00fcfung](https://grosserrat.bs.ch/gremien/oberaufsicht/geschaeftspruefung)\n  - [Finanzkommission](https://grosserrat.bs.ch/gremien/oberaufsicht/finanzkommission)\n- [Sachkommissionen](https://grosserrat.bs.ch/gremien/sachkommissionen)\n  - [Bau und Raumplanung](https://grosserrat.bs.ch/gremien/sachkommissionen/bau-raumplanung)\n  - [Bildung und Kultur](https://grosserrat.bs.ch/gremien/sachkommissionen/bildung-kultur)\n  - [Gesundheit und Soziales](https://grosserrat.bs.ch/gremien/sachkommissionen/gesundheit-soziales)\n  - [Justiz, Sicherheit und Sport](https://grosserrat.bs.ch/gremien/sachkommissionen/justiz-sicherheit-sport)\n  - [Regio](https://grosserrat.bs.ch/gremien/sachkommissionen/regio)\n  - [Umwelt, Verkehr und Energie](https://grosserrat.bs.ch/gremien/sachkommissionen/umwelt-verkehr-energie)\n  - [Wirtschaft und Abgaben](https://grosserrat.bs.ch/gremien/sachkommissionen/wirtschaft-abgaben)\n\n- [Parteien und Fraktionen](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen)\n  - [SP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/sp)\n  - [LDP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/ldp)\n  - [SVP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/svp)\n  - [GR\u00dcNE/jgb](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/gruene-jgb)\n  - [Die Mitte/EVP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/mitte-evp)\n  - [GLP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/glp)\n  - [FDP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/fdp)\n  - [BastA!](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/basta)\n  - [Fraktionslos](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/fraktionslos)\n- [Trinationale Gremien](https://grosserrat.bs.ch/gremien/trinationale-gremien)\n  - [Oberrheinrat](https://grosserrat.bs.ch/gremien/trinationale-gremien/oberrheinrat)\n  - [Districtsrat](https://grosserrat.bs.ch/gremien/trinationale-gremien/districtsrat)\n\n- [Interparlamentarische Gremien](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien)\n  - [IGPK Universit\u00e4t](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-universitaet)\n  - [IGPK Kinderspital](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-kinderspital)\n  - [IGPK Rheinh\u00e4fen](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-rheinhaefen)\n  - [IPK Fachhochschule](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/ipk-fachhochschule)\n  - [IGPK Polizeischule](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-polizeischule)\n  - [Interparl. Konferenz der Nordwestschweiz](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/interparl-konferenz-der-nordwestschweiz)\n  - [Interkantonale Legislativkonferenz](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/interkantonale-legislativkonferenz)\n- [Weitere Kommissionen](https://grosserrat.bs.ch/gremien/weitere-kommissionen)\n  - [Begnadigungskommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/begnadigungskommission)\n  - [Disziplinarkommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/disziplinarkommission)\n  - [Petitionskommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/petitionskommission)\n  - [Wahlvorbereitungskommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/wahlvorbereitungskommission)\n  - [Spezialkommissionen und PUK](https://grosserrat.bs.ch/gremien/weitere-kommissionen/spezialkommissionen-und-puk)\n  - [Ratsexterne Gremien](https://grosserrat.bs.ch/gremien/weitere-kommissionen/ratsexterne-gremien)\n- [Finanzkontrolle, Ombudsstelle und Datenschutz](https://grosserrat.bs.ch/gremien/finanzkontrolle-ombudsstelle-und-datenschutz)\n\n**Ratsbetrieb**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Tagesordnung](https://grosserrat.bs.ch/ratsbetrieb/tagesordnung)\n  - [Abstimmungsergebnisse](https://grosserrat.bs.ch/ratsbetrieb/tagesordnung/abstimmungsergebnisse)\n- [Sitzungskalender](https://grosserrat.bs.ch/ratsbetrieb/sitzungskalender)\n- [Neue Vorst\u00f6sse](https://grosserrat.bs.ch/ratsbetrieb/neue-vorstoesse)\n- [Neue Berichte und Schreiben](https://grosserrat.bs.ch/ratsbetrieb/neue-berichte-und-schreiben)\n- [Protokolle/Videos](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos)\n\n- [Rechtsgrundlagen](https://grosserrat.bs.ch/ratsbetrieb/rechtsgrundlagen)\n- [Sitzordnung](https://grosserrat.bs.ch/ratsbetrieb/sitzordnung)\n- [Interessenbindungen](https://grosserrat.bs.ch/ratsbetrieb/interessenbindungen)\n- [Personelle Wechsel](https://grosserrat.bs.ch/ratsbetrieb/personelle-wechsel)\n\n- [Parlamentsdienst](https://grosserrat.bs.ch/ratsbetrieb/parlamentsdienst)\n- [F\u00fcr Ratsmitglieder](https://grosserrat.bs.ch/ratsbetrieb/fuer-ratsmitglieder)\n  - [Intern (PIXAS)](https://grosserratbs.pixas.ch/)\n  - [Vademekum \ud83d\udcc4](https://grosserrat.bs.ch/images/dateien/Vademekum.pdf)\n  - [Termine und Traktandierungen \ud83d\udcc4](https://grosserrat.bs.ch/images/dateien/termine_und_traktandierungen.pdf)\n- [Parlamentarische Gruppen](https://grosserrat.bs.ch/ratsbetrieb/parlamentarische-gruppen)\n\n**Medien**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Medienmitteilungen](https://grosserrat.bs.ch/medien/medienmitteilungen)\n\n- [F\u00fcr Medienschaffende](https://grosserrat.bs.ch/medien/fuer-medienschaffende)\n\n- [Bilder-Datenbank](https://grosserrat.bs.ch/medien/bilder-datenbank)\n\n**Besuch**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [\u00d6ffentliche Trib\u00fcne](https://grosserrat.bs.ch/besuch/oeffentliche-tribuene)\n- [Rathausf\u00fchrungen](https://grosserrat.bs.ch/besuch/rathausfuehrungen)\n\n- [Schulangebote](https://grosserrat.bs.ch/besuch/schulangebote)\n- [Blick von der Trib\u00fcne](https://grosserrat.bs.ch/besuch/blick-von-der-tribuene)\n\n- [Folgen Sie uns](https://grosserrat.bs.ch/besuch/folgen-sie-uns)\n\n[Men\u00fc schlie\u00dfen](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos#mm-0)",
        "text_length": 12477,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 1436,
        "promise_count": 3,
        "gemini_tokens_in": 3619,
        "gemini_tokens_out": 120,
        "error": null
      }
    ],
    "candidate_count": 1,
    "pdf_url": "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle",
    "pdf_size_kb": 0,
    "text_length": 12477,
    "llamaparse_pages": 0,
    "promise_count": 3,
    "promises": [
      {
        "promise_text": "The council will make audiovisual minutes available for sessions in April 2026.",
        "due_date": "2026-04-30",
        "date_confidence": "medium",
        "criteria_match": true
      },
      {
        "promise_text": "The council will make audiovisual minutes available for sessions in March 2026.",
        "due_date": "2026-03-31",
        "date_confidence": "medium",
        "criteria_match": true
      },
      {
        "promise_text": "The council will make audiovisual minutes available for sessions in February 2026.",
        "due_date": "2026-02-28",
        "date_confidence": "medium",
        "criteria_match": true
      }
    ],
    "total_time_ms": 6791,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 3619,
    "gemini_tokens_out": 120,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "1 candidates, 1 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "1/1 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "PASS",
        "detail": "3 promises, 3 with due_date",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Basel: Grosser Rat + criteria (DE)",
    "url": "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle?all=1",
    "language": "de",
    "criteria": "Wohnungspolitik",
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 3067,
        "candidate_count": 1,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 716,
        "text": "# Protokolle/Videos\n\nDie Protokolle der Plenumssitzungen sind seit 2004 als Vollprotokoll abrufbar. Ab 2010 sind auch Audios und ab 2023 Videos verf\u00fcgbar; die einzelnen Voten sind downloadbar (![Symbol Play/Abspielen](https://grosserrat.bs.ch/images/system/icons/play.svg)). Auch das Stimmverhalten der Ratsmitglieder\u00a0(![Symbol Abstimmungsurne](https://grosserrat.bs.ch/images/system/icons/abstimmung.svg)) ist integriert.\n\n[Nutzungsbestimmungen](https://grosserrat.bs.ch/images/dateien/Nutzungsbedingungen_Video-Bild-Ton_2024.pdf) (PDF) \\| [Ratsprotokolle 1690-2011](https://dls.staatsarchiv.bs.ch/records/hierarchy/199821?context=%2Fsearch%3Fpage%3D1%26page_size%3D25%26query%3DProtokolle%2520Grosser%2520Rat%26advanced_query%3Dfalse)\u00a0(Staatsarchiv)\n\n### Amtsjahr 2026/2027\n\n[![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/ausklapper_black.svg)](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos#protokolle_2026)\n\n| 15./22. April 2026 | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/) | Kein Vollprotokoll\u00a0April 2026 vorhanden | (der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-04-15.pdf) | [Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-04-15.pdf) |\n| Mittwoch22.04.2026 | Kein Wortprotokoll Sitzung 12 (20 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 11 (15 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 10 (09 Uhr)\u00a022.04.2026 vorhanden | Kein Wortprotokoll Sitzung 12 (20 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 11 (15 Uhr)\u00a022.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 10 (09 Uhr)\u00a022.04.2026 vorhanden | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/)<br>Kein Vollprotokoll\u00a0April 2026 vorhanden<br>(der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-04-15.pdf)<br>[Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0April 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-04-15.pdf) |\n| Mittwoch15.04.2026 | Kein Wortprotokoll Sitzung 9 (15 Uhr)\u00a015.04.2026 vorhanden<br>Kein Wortprotokoll Sitzung 8 (09 Uhr)\u00a015.04.2026 vorhanden |\n| 11./18. M\u00e4rz 2026 | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/) | Kein Vollprotokoll\u00a0M\u00e4rz 2026 vorhanden | (der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-03-11.pdf) | [Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-03-11.pdf) |\n| Mittwoch18.03.2026 | Kein Wortprotokoll Sitzung 7 (15 Uhr)\u00a018.03.2026 vorhanden<br>Kein Wortprotokoll Sitzung 6 (09 Uhr)\u00a018.03.2026 vorhanden | Kein Wortprotokoll Sitzung 7 (15 Uhr)\u00a018.03.2026 vorhanden<br>Kein Wortprotokoll Sitzung 6 (09 Uhr)\u00a018.03.2026 vorhanden | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/)<br>Kein Vollprotokoll\u00a0M\u00e4rz 2026 vorhanden<br>(der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-03-11.pdf)<br>[Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0M\u00e4rz 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-03-11.pdf) |\n| Mittwoch11.03.2026 | Kein Wortprotokoll Sitzung 5 (15 Uhr)\u00a011.03.2026 vorhanden<br>Kein Wortprotokoll Sitzung 4 (09 Uhr)\u00a011.03.2026 vorhanden |\n| 04./11. Februar 2026 | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/) | Kein Vollprotokoll\u00a0Februar 2026 vorhanden | (der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-02-04.pdf) | [Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-02-04.pdf) |\n| Mittwoch11.02.2026 | Kein Wortprotokoll Sitzung 3 (09 Uhr)\u00a011.02.2026 vorhanden | Kein Wortprotokoll Sitzung 3 (09 Uhr)\u00a011.02.2026 vorhanden | [Audiovisuelles Protokoll](https://ratsprotokolle.grosserrat.bs.ch/)<br>Kein Vollprotokoll\u00a0Februar 2026 vorhanden<br>(der ganzen Session, inkl.<br>Abstimmungsergebnisse) | [Tagesordnung\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/tagesordnung_2026-02-04.pdf)<br>[Gesch\u00e4fts\u00adver\u00adzeich\u00adnis\u00a0Februar 2026](https://grosserrat.bs.ch/media/files/tagesordnungen/geschaeftsverzeichnis_2026-02-04.pdf) |\n| Mittwoch04.02.2026 | Kein Wortprotokoll Sitzung 2 (15 Uhr)\u00a004.02.2026 vorhanden<br>Kein Wortprotokoll Sitzung 1 (09 Uhr)\u00a004.02.2026 vorhanden |\n\n[Alle Ratsprotokolle und Abstimmungsresultate](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos?all=1)\n\n**Parlamentswissen**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Der Grosse Rat](https://grosserrat.bs.ch/parlamentswissen/der-grosse-rat)\n- [Aufgaben](https://grosserrat.bs.ch/parlamentswissen/aufgaben)\n- [Gewaltenteilung](https://grosserrat.bs.ch/parlamentswissen/gewaltenteilung)\n- [So entsteht ein Gesetz](https://grosserrat.bs.ch/parlamentswissen/so-entsteht-ein-gesetz)\n\n- [Parlamentarische Instrumente](https://grosserrat.bs.ch/parlamentswissen/parlamentarische-instrumente)\n- [Mitbestimmung der Bev\u00f6lkerung](https://grosserrat.bs.ch/parlamentswissen/mitbestimmung-der-bevoelkerung)\n- [Wahlen](https://grosserrat.bs.ch/parlamentswissen/wahlen)\n- [Ergebnisse Grossratswahlen](https://grosserrat.bs.ch/parlamentswissen/ergebnisse-grossratswahlen)\n- [Was kostet ein Parlament?](https://grosserrat.bs.ch/parlamentswissen/was-kostet-ein-parlament)\n\n- [Politw\u00f6rterbuch A - Z](https://grosserrat.bs.ch/parlamentswissen/politwoerterbuch-a-z)\n- [Brosch\u00fcre: Politik in BS kurz erkl\u00e4rt \ud83d\udcc4](https://grosserrat.bs.ch/images/dateien/broschuere/broschuere.pdf)\n- [Ratsgeschichte](https://grosserrat.bs.ch/parlamentswissen/ratsgeschichte)\n  - [Entwicklung der Parteien](https://grosserrat.bs.ch/parlamentswissen/ratsgeschichte/entwicklung-der-parteien)\n- [Parlamentarische Recherche](https://grosserrat.bs.ch/parlamentswissen/parlamentarische-recherche)\n\n**Gremien**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Pr\u00e4sidium und B\u00fcro](https://grosserrat.bs.ch/gremien/praesidium-und-buero)\n- [Oberaufsicht](https://grosserrat.bs.ch/gremien/oberaufsicht)\n  - [Gesch\u00e4ftspr\u00fcfung](https://grosserrat.bs.ch/gremien/oberaufsicht/geschaeftspruefung)\n  - [Finanzkommission](https://grosserrat.bs.ch/gremien/oberaufsicht/finanzkommission)\n- [Sachkommissionen](https://grosserrat.bs.ch/gremien/sachkommissionen)\n  - [Bau und Raumplanung](https://grosserrat.bs.ch/gremien/sachkommissionen/bau-raumplanung)\n  - [Bildung und Kultur](https://grosserrat.bs.ch/gremien/sachkommissionen/bildung-kultur)\n  - [Gesundheit und Soziales](https://grosserrat.bs.ch/gremien/sachkommissionen/gesundheit-soziales)\n  - [Justiz, Sicherheit und Sport](https://grosserrat.bs.ch/gremien/sachkommissionen/justiz-sicherheit-sport)\n  - [Regio](https://grosserrat.bs.ch/gremien/sachkommissionen/regio)\n  - [Umwelt, Verkehr und Energie](https://grosserrat.bs.ch/gremien/sachkommissionen/umwelt-verkehr-energie)\n  - [Wirtschaft und Abgaben](https://grosserrat.bs.ch/gremien/sachkommissionen/wirtschaft-abgaben)\n\n- [Parteien und Fraktionen](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen)\n  - [SP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/sp)\n  - [LDP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/ldp)\n  - [SVP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/svp)\n  - [GR\u00dcNE/jgb](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/gruene-jgb)\n  - [Die Mitte/EVP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/mitte-evp)\n  - [GLP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/glp)\n  - [FDP](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/fdp)\n  - [BastA!](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/basta)\n  - [Fraktionslos](https://grosserrat.bs.ch/gremien/parteien-und-fraktionen/fraktionslos)\n- [Trinationale Gremien](https://grosserrat.bs.ch/gremien/trinationale-gremien)\n  - [Oberrheinrat](https://grosserrat.bs.ch/gremien/trinationale-gremien/oberrheinrat)\n  - [Districtsrat](https://grosserrat.bs.ch/gremien/trinationale-gremien/districtsrat)\n\n- [Interparlamentarische Gremien](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien)\n  - [IGPK Universit\u00e4t](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-universitaet)\n  - [IGPK Kinderspital](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-kinderspital)\n  - [IGPK Rheinh\u00e4fen](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-rheinhaefen)\n  - [IPK Fachhochschule](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/ipk-fachhochschule)\n  - [IGPK Polizeischule](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/igpk-polizeischule)\n  - [Interparl. Konferenz der Nordwestschweiz](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/interparl-konferenz-der-nordwestschweiz)\n  - [Interkantonale Legislativkonferenz](https://grosserrat.bs.ch/gremien/interparlamentarische-gremien/interkantonale-legislativkonferenz)\n- [Weitere Kommissionen](https://grosserrat.bs.ch/gremien/weitere-kommissionen)\n  - [Begnadigungskommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/begnadigungskommission)\n  - [Disziplinarkommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/disziplinarkommission)\n  - [Petitionskommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/petitionskommission)\n  - [Wahlvorbereitungskommission](https://grosserrat.bs.ch/gremien/weitere-kommissionen/wahlvorbereitungskommission)\n  - [Spezialkommissionen und PUK](https://grosserrat.bs.ch/gremien/weitere-kommissionen/spezialkommissionen-und-puk)\n  - [Ratsexterne Gremien](https://grosserrat.bs.ch/gremien/weitere-kommissionen/ratsexterne-gremien)\n- [Finanzkontrolle, Ombudsstelle und Datenschutz](https://grosserrat.bs.ch/gremien/finanzkontrolle-ombudsstelle-und-datenschutz)\n\n**Ratsbetrieb**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Tagesordnung](https://grosserrat.bs.ch/ratsbetrieb/tagesordnung)\n  - [Abstimmungsergebnisse](https://grosserrat.bs.ch/ratsbetrieb/tagesordnung/abstimmungsergebnisse)\n- [Sitzungskalender](https://grosserrat.bs.ch/ratsbetrieb/sitzungskalender)\n- [Neue Vorst\u00f6sse](https://grosserrat.bs.ch/ratsbetrieb/neue-vorstoesse)\n- [Neue Berichte und Schreiben](https://grosserrat.bs.ch/ratsbetrieb/neue-berichte-und-schreiben)\n- [Protokolle/Videos](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos)\n\n- [Rechtsgrundlagen](https://grosserrat.bs.ch/ratsbetrieb/rechtsgrundlagen)\n- [Sitzordnung](https://grosserrat.bs.ch/ratsbetrieb/sitzordnung)\n- [Interessenbindungen](https://grosserrat.bs.ch/ratsbetrieb/interessenbindungen)\n- [Personelle Wechsel](https://grosserrat.bs.ch/ratsbetrieb/personelle-wechsel)\n\n- [Parlamentsdienst](https://grosserrat.bs.ch/ratsbetrieb/parlamentsdienst)\n- [F\u00fcr Ratsmitglieder](https://grosserrat.bs.ch/ratsbetrieb/fuer-ratsmitglieder)\n  - [Intern (PIXAS)](https://grosserratbs.pixas.ch/)\n  - [Vademekum \ud83d\udcc4](https://grosserrat.bs.ch/images/dateien/Vademekum.pdf)\n  - [Termine und Traktandierungen \ud83d\udcc4](https://grosserrat.bs.ch/images/dateien/termine_und_traktandierungen.pdf)\n- [Parlamentarische Gruppen](https://grosserrat.bs.ch/ratsbetrieb/parlamentarische-gruppen)\n\n**Medien**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [Medienmitteilungen](https://grosserrat.bs.ch/medien/medienmitteilungen)\n\n- [F\u00fcr Medienschaffende](https://grosserrat.bs.ch/medien/fuer-medienschaffende)\n\n- [Bilder-Datenbank](https://grosserrat.bs.ch/medien/bilder-datenbank)\n\n**Besuch**\n\n![](https://grosserrat.bs.ch/media/templates/site/grosserrat_2020/images/svg/close.svg)\n\n- [\u00d6ffentliche Trib\u00fcne](https://grosserrat.bs.ch/besuch/oeffentliche-tribuene)\n- [Rathausf\u00fchrungen](https://grosserrat.bs.ch/besuch/rathausfuehrungen)\n\n- [Schulangebote](https://grosserrat.bs.ch/besuch/schulangebote)\n- [Blick von der Trib\u00fcne](https://grosserrat.bs.ch/besuch/blick-von-der-tribuene)\n\n- [Folgen Sie uns](https://grosserrat.bs.ch/besuch/folgen-sie-uns)\n\n[Men\u00fc schlie\u00dfen](https://grosserrat.bs.ch/ratsbetrieb/protokolle-videos#mm-0)",
        "text_length": 12477,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 1435,
        "promise_count": 0,
        "gemini_tokens_in": 3619,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 1,
    "pdf_url": "https://grosserrat.bs.ch/ratsbetrieb/ratsprotokolle",
    "pdf_size_kb": 0,
    "text_length": 12477,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 5219,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 3619,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "1 candidates, 1 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "1/1 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Zurich: Gemeinderat (DE)",
    "url": "https://www.gemeinderat-zuerich.ch/protokolle",
    "language": "de",
    "criteria": null,
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 8910,
        "candidate_count": 1,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 3272,
        "text": "# Navigation\n\n## Skiplinks\n\n[Skip to content](https://www.gemeinderat-zuerich.ch/protokolle#anchorContent \"[ALT + 2]\")[Skip to meta navigation](https://www.gemeinderat-zuerich.ch/protokolle#anchorNavMeta \"[ALT + 6]\")\n\n# Dokument nicht auffindbar (Error 404)\n\nHinweis\n\nIhr gew\u00fcnschtes Dokument bzw. die gew\u00fcnschte Seite ist nicht auffindbar. Vielleicht hat sich die Platzierung des Dokuments ge\u00e4ndert oder es wurde durch eine neue Version ersetzt.\n\nWir empfehlen Ihnen folgende Schritte:\n\n1. F\u00fcr den Weg zur\u00fcck\n   - geben Sie die gesuchte Adresse (bzw. Webseite) direkt in Ihrem Browser ein,\n\n      z.B. [www.stadt-zuerich.ch](http://www.stadt-zuerich.ch/)\n   - oder bet\u00e4tigen Sie die Zur\u00fccktaste (Back Button) in Ihrem Browser.\n   - oder klicken Sie auf unsere automatisch generierte Zur\u00fcck-Verlinkung: zur\u00fcck\n2. Suchen Sie erneut nach dem gew\u00fcnschten Dokument und \u00e4ndern Sie allenfalls den Favoriten (das\n    Lesezeichen) in Ihrem Browser.\n\n\nFalls das Problem wiederholt auftritt und Sie Hilfe ben\u00f6tigen, senden Sie unserem Servicedesk eine Problembeschreibung mit folgenden\n[Informationen:](mailto:szh.egovservicedesk@zuerich.ch?subject=Problem%20Webzugriff%3A%20&body=-%20Kontaktdaten%20und%20Erreichbarkeit%3A%0A%0A%0A-%20Fehlerbeschreibung%3A%0A%0A%0A-%20Fehlerdetails:%0A1aac0a84-hts_www-2026.04.21_1147.50.667-001%0ATuesday,%2021-Apr-2026%2013:47:50%20CEST%0Ahttps://www.gemeinderat-zuerich.ch/protokolle \"Informationen\")\n\n_1aac0a84-hts\\_www-2026.04.21\\_1147.50.667-001_\n\n_Tuesday, 21-Apr-2026 13:47:50 CEST_\n\n_https://www.gemeinderat-zuerich.ch/protokolle_",
        "text_length": 1564,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 773,
        "promise_count": 0,
        "gemini_tokens_in": 891,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 1,
    "pdf_url": "https://www.gemeinderat-zuerich.ch/protokolle",
    "pdf_size_kb": 0,
    "text_length": 1564,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 12956,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 891,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "1 candidates, 1 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "1/1 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Lausanne: Conseil communal (FR)",
    "url": "https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html",
    "language": "fr",
    "criteria": null,
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 13361,
        "candidate_count": 1,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 4195,
        "text": "[liens d'\u00e9vitement](https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html# \"liens d'\u00e9vitement\")[Aller au contenu](https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html#) [Aller \u00e0 la recherche](https://www.lausanne.ch/recherche.html) [Partager](https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html#)\n\n# Erreur 404\n\n![\u00a9 Droits r\u00e9serv\u00e9s](https://www.lausanne.ch/.imaging/mte/lausanne/original/website/lausanne/errors/404/contentAutogenerated/autogeneratedContainer/col1/0/import/Tasse-erreur.2018-03-08-09-18-24.jpg)\n\n#### D\u00e9sol\u00e9, la page recherch\u00e9e est introuvable!\n\nSoit votre URL est incorrecte ou le fichier a \u00e9t\u00e9 d\u00e9plac\u00e9 ou renomm\u00e9. V\u00e9rifiez qu'il n'y a pas d'erreurs dans l'adresse puis ressayez.\n\nEn cas d'\u00e9chec, vous pouvez:\n\n- essayer de trouver l\u2019information recherch\u00e9e \u00e0 l\u2019aide du moteur de recherche\n- parcourir la rubrique concern\u00e9e en utilisant le menu de navigation\n- signaler le probl\u00e8me en contactant le [webmaster](mailto:webmaster@lausanne.ch?subject=Erreur%20404&body=Bonjour,%0A%0A%20J%27arrive%20sur%20une%20erreur%20404.%20La%20page%20qui%20provoque%20l%27erreur%20est:%20https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html%0A%0ALa%20page%20pr%C3%A9c%C3%A9dente:%20https://www.google.com/%0A%0AJ%27utilise%20Mozilla/5.0%20(X11;%20Linux%20x86_64)%20AppleWebKit/537.36%20(KHTML,%20like%20Gecko)%20Chrome/146.0.0.0%20Safari/537.36%0A%0AMerci)\n\n[\u00c0 PROPOS](https://www.lausanne.ch/portrait.html)\n\n[Portrait de Lausanne](https://www.lausanne.ch/portrait.html)\n\n[Actualit\u00e9s municipales](https://www.lausanne.ch/agenda-et-actualites/actualites-municipales.html)\n\n[Agenda des manifestations](https://www.lausanne.ch/agenda)\n\n[Le Journal + newsletter](https://www.lausanne.ch/agenda-et-actualites/journal.html)\n\n[Plan de ville](https://www.lausanne-tourisme.ch/fr/P19864/plan-de-ville)\n\n[Une suggestion? \u2013 Bo\u00eete \u00e0 id\u00e9es virtuelle](https://participer.lausanne.ch/processes/boite-a-idees)\n\n[Annuaire de l'administration](https://www.lausanne.ch/officiel/administration/annuaire.html)\n\n[PRATIQUE](https://www.lausanne.ch/vie-pratique.html)\n\n[Bienvenue \u00e0 Lausanne](https://www.lausanne.ch/officiel/administration/culture-et-developpement-urbain/secretariat-municipal/en-relation/nouveaux-arrivants.html)\n\n[Adresses, num\u00e9ros et infos utiles](https://www.lausanne.ch/prestations/info-cite/c-services-administratifs/adresses-utiles.html)\n\n[Guichet virtuel](https://www.lausanne.ch/prestations.html)\n\n[D\u00e9chets m\u00e9nagers](https://www.lausanne.ch/dechets)\n\n[Vacances scolaires](https://www.lausanne.ch/vacances)\n\n[Guichet cartographique](https://map.lausanne.ch/)\n\n[NOUS REJOINDRE](https://www.lausanne.ch/officiel/travailler-a-la-ville.html)\n\n[L'employeur Ville](https://www.lausanne.ch/officiel/travailler-a-la-ville/employeur-ville.html)\n\n[Offres d'emploi](https://www.lausanne.ch/officiel/travailler-a-la-ville/nous-rejoindre/offres-emploi.html)\n\n[Apprentissage](https://www.lausanne.ch/officiel/travailler-a-la-ville/apprentissage.html)\n\n[Stages et offres spontan\u00e9es](https://www.lausanne.ch/officiel/travailler-a-la-ville/nous-rejoindre/places-stage.html)\n\n[TOURISME](https://www.lausanne-tourisme.ch/)\n\n[Bienvenue](https://www.lausanne-tourisme.ch/fr/)\n\n[Welcome](https://www.lausanne-tourisme.ch/en/)\n\n[Willkommen](https://www.lausanne-tourisme.ch/de/)\n\n[Benvenuto](https://www.lausanne-tourisme.ch/it/)\n\n[Bienvenido](https://www.lausanne-tourisme.ch/es/)\n\n[LAUSANNE SUR LE WEB](https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html)\n\n[Art en ville \u2013 le guide de l'art dans l'espace public lausannois](https://www.art-en-ville.ch/)\n\n[Services industriels](https://www.lausanne.ch/sil)\n\n[SiL Multim\u00e9dia](https://sil-bliblablo.ch/)\n\n[Vins de la Ville](https://www.lausanne.ch/vins)\n\n[Lausanne Tourisme](https://www.lausanne-tourisme.ch/)\n\n[Lausanne \u00e0 table](https://www.lausanneatable.ch/)",
        "text_length": 3922,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 3423,
        "promise_count": 0,
        "gemini_tokens_in": 1480,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 1,
    "pdf_url": "https://www.lausanne.ch/officiel/autorites/conseil-communal/seances-et-pv.html",
    "pdf_size_kb": 0,
    "text_length": 3922,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 20980,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 1480,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "1 candidates, 1 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "1/1 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Bern: Stadtrat (DE)",
    "url": "https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen",
    "language": "de",
    "criteria": "Klimaschutz",
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 30062,
        "candidate_count": 1,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 56321,
        "text": "# Server Error\n\n\\[an error occurred while processing this directive\\]\n\nOur web servers are currently offline. The servers will all be up and running again shortly. Please check back soon.\n\nPlease contact the server administrator and inform them of the time the error occurred,\nand anything you might have done that may have caused the error.",
        "text_length": 341,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 922,
        "promise_count": 0,
        "gemini_tokens_in": 585,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 1,
    "pdf_url": "https://www.bern.ch/politik-und-verwaltung/stadtrat/sitzungen",
    "pdf_size_kb": 0,
    "text_length": 341,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 87306,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 585,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "1 candidates, 1 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "1/1 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Bozeman: City Commission (EN)",
    "url": "https://www.bozeman.net/departments/city-commission",
    "language": "en",
    "criteria": null,
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 7754,
        "candidate_count": 5,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 3402,
        "text": "- BOZEMAN\n\n5 Entries\n\n|  | Name | Page count | Is indexed | Date created | Date modified | Volume name | Template name |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n|  | [Citizen Advisory Board](https://weblink.bozeman.net/WebLink/Browse.aspx?id=256154&dbid=0&repo=BOZEMAN) |  | true | 10/18/2021 6:53:15 PM | 4/17/2026 5:00:39 PM | CITY COMMISSION |  |\n|  | [City Commission](https://weblink.bozeman.net/WebLink/Browse.aspx?id=26&dbid=0&repo=BOZEMAN) |  | true | 11/30/2004 11:34:24 AM | 4/17/2026 5:00:39 PM | CITY COMMISSION |  |\n|  | [Planning](https://weblink.bozeman.net/WebLink/Browse.aspx?id=175844&dbid=0&repo=BOZEMAN) |  | true | 3/12/2019 4:52:42 PM | 8/19/2024 1:07:14 PM | DEPARTMENTS |  |\n|  | [Public Documents](https://weblink.bozeman.net/WebLink/Browse.aspx?id=256150&dbid=0&repo=BOZEMAN) |  | true | 10/18/2021 6:52:22 PM | 3/26/2026 12:16:34 PM | CITY COMMISSION |  |\n|  | [Strategic Services](https://weblink.bozeman.net/WebLink/Browse.aspx?id=27&dbid=0&repo=BOZEMAN) |  | true | 11/30/2004 11:34:30 AM | 8/21/2025 9:16:23 PM |  |  |\n\n- Column Picker\n\n|     |     |\n| --- | --- |\n| Entry Properties |\n| Modified | 11/14/2025 6:22:53 PM |\n| Created | 10/13/2009 11:13:33 AM |\n| Path | [\\](https://weblink.bozeman.net/WebLink/Browse.aspx?id=1&dbid=0&repo=BOZEMAN&cr=1) |\n| Template |\n| No template assigned |\n\nThe URL can be used to link to this page\n\nYour browser does not support the video tag.",
        "text_length": 1420,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 10645,
        "promise_count": 0,
        "gemini_tokens_in": 855,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 5,
    "pdf_url": "https://www.bozeman.net/departments/city-commission/city-documents",
    "pdf_size_kb": 0,
    "text_length": 1420,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 21802,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 855,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "5 candidates, 4 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "5/5 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Bozeman: City Commission + criteria (EN)",
    "url": "https://www.bozeman.net/departments/city-commission",
    "language": "en",
    "criteria": "housing policy",
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 4399,
        "candidate_count": 5,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 3489,
        "text": "- BOZEMAN\n\n- City Commission\n\n- City Commission Agendas\n\n4 Entries\n\n|  | Name | Page count | Is indexed | Date created | Date modified | Volume name | Template name |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n|  | [1980-1989](https://weblink.bozeman.net/WebLink/Browse.aspx?id=51796&dbid=0&repo=BOZEMAN) |  | true | 4/5/2013 12:42:18 PM | 4/5/2013 12:43:18 PM | CITY COMMISSION |  |\n|  | [1990-1999](https://weblink.bozeman.net/WebLink/Browse.aspx?id=51797&dbid=0&repo=BOZEMAN) |  | true | 4/5/2013 12:42:33 PM | 1/8/2015 4:36:10 PM | CITY COMMISSION |  |\n|  | [2000-2009](https://weblink.bozeman.net/WebLink/Browse.aspx?id=47&dbid=0&repo=BOZEMAN) |  | true | 11/30/2004 12:56:03 PM | 1/8/2015 4:03:43 PM | CITY COMMISSION |  |\n|  | [2010-2019](https://weblink.bozeman.net/WebLink/Browse.aspx?id=51800&dbid=0&repo=BOZEMAN) |  | true | 4/5/2013 12:44:41 PM | 1/3/2019 3:24:16 PM | CITY COMMISSION |  |\n\n- Column Picker\n\n|     |     |\n| --- | --- |\n| Entry Properties |\n| Modified | 3/19/2026 1:19:41 PM |\n| Created | 4/5/2013 11:20:45 AM |\n| Path | [\\\\City Commission\\\\City Commission Agendas](https://weblink.bozeman.net/WebLink/Browse.aspx?id=51769&dbid=0&repo=BOZEMAN&cr=1) |\n| Template |\n| No template assigned |\n\nThe URL can be used to link to this page\n\nYour browser does not support the video tag.",
        "text_length": 1311,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 822,
        "promise_count": 0,
        "gemini_tokens_in": 827,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 5,
    "pdf_url": "https://www.bozeman.net/departments/city-commission/meeting-agendas",
    "pdf_size_kb": 0,
    "text_length": 1311,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 8712,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 827,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "5 candidates, 4 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "5/5 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Madison WI: Common Council (EN)",
    "url": "https://www.cityofmadison.com/council",
    "language": "en",
    "criteria": null,
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 6757,
        "candidate_count": 5,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 612,
        "text": "[Skip to main content](https://www.cityofmadison.com/council/meetings-agendas#main-content)\n\n![City-County Building](https://www.cityofmadison.com/sites/default/files/styles/banner_desktop/public/council/images/council-banner.jpg?h=e0d9a4bb&itok=NC6_2hNC)\n\n![City of Madison - Common Council logo](https://www.cityofmadison.com/sites/default/files/icons/city-logo-white-council.svg)\n\n[Common Council](https://www.cityofmadison.com/council \"Home - Common Council\")\n\n# Meetings & Agendas\n\nThe Common Council generally holds meetings twice a month on Tuesdays, starting at 6:30 pm.\n\n## Upcoming Meetings\n\n| [Tuesday, Apr. 21, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-04-21 \" Tuesday, Apr. 21, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  | - [Agenda(opens in a new window)](https://madison.legistar.com/View.ashx?M=A&ID=1316267&GUID=6DA62006-C06C-4FBF-921C-B6805291FE2D \"Agenda of the Tuesday, Apr. 21, 2026 6:30pm meeting of the Common Council\") PDF |\n| [Wednesday, Apr. 22, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-04-22 \" Wednesday, Apr. 22, 2026 at 8:00am meeting of Common Council\")<br> Notice of possible quorum | 8:00am |  | - [Agenda(opens in a new window)](https://www.cityofmadison.com/city-hall/committees/meeting-schedule/documents/agendas/042226%20Habitat%20for%20Humanity.pdf \"Agenda of the Wednesday, Apr. 22, 2026 8:00am meeting of the Common Council\") PDF |\n| [Tuesday, May. 5, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-05-05 \" Tuesday, May. 5, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, May. 19, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-05-19 \" Tuesday, May. 19, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Wednesday, May. 20, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-05-20 \" Wednesday, May. 20, 2026 at 6:30pm meeting of Common Council\")<br> Notice of possible quorum | 6:30pm |  | - [Agenda(opens in a new window)](https://www.cityofmadison.com/city-hall/committees/meeting-schedule/documents/agendas/052026%20MPD%20Q%26A.pdf \"Agenda of the Wednesday, May. 20, 2026 6:30pm meeting of the Common Council\") PDF |\n| [Tuesday, Jun. 9, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-06-09 \" Tuesday, Jun. 9, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Jun. 23, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-06-23 \" Tuesday, Jun. 23, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Jul. 7, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-07-07 \" Tuesday, Jul. 7, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Jul. 21, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-07-21 \" Tuesday, Jul. 21, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Aug. 4, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-08-04 \" Tuesday, Aug. 4, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Sep. 8, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-09-08 \" Tuesday, Sep. 8, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Sep. 22, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-09-22 \" Tuesday, Sep. 22, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Oct. 6, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-10-06 \" Tuesday, Oct. 6, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Oct. 20, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-10-20 \" Tuesday, Oct. 20, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Nov. 10, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-11-10 \" Tuesday, Nov. 10, 2026 at 5:30pm meeting of Common Council\") | 5:30pm |  |  |\n| [Wednesday, Nov. 11, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-11-11 \" Wednesday, Nov. 11, 2026 at 5:30pm meeting of Common Council\") | 5:30pm |  |  |\n| [Thursday, Nov. 12, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-11-12 \" Thursday, Nov. 12, 2026 at 5:30pm meeting of Common Council\") | 5:30pm |  |  |\n| [Tuesday, Nov. 24, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-11-24 \" Tuesday, Nov. 24, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  |  |\n| [Tuesday, Dec. 8, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-12-08 \" Tuesday, Dec. 8, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  | - [Agenda(opens in a new window)](https://madison.legistar.com/View.ashx?M=A&ID=1328954&GUID=6BB98A2E-666D-4518-A921-E50DE47AF3B5 \"Agenda of the Tuesday, Dec. 8, 2026 6:30pm meeting of the Common Council\") PDF |\n\n## Past Meetings\n\n| [Saturday, Apr. 18, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-04-18 \" Saturday, Apr. 18, 2026 at 10:00am meeting of Common Council\")<br> Notice of possible quorum | 10:00am |  | - [Agenda(opens in a new window)](https://www.cityofmadison.com/city-hall/committees/meeting-schedule/documents/agendas/041826%20Old%20Problems%20Young%20Solutions.pdf \"Agenda of the Saturday, Apr. 18, 2026 10:00am meeting of the Common Council\") PDF |\n| [Tuesday, Apr. 14, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-04-14 \" Tuesday, Apr. 14, 2026 at 7:00pm meeting of Common Council\")<br> Notice of possible quorum | 7:00pm |  | - [Agenda(opens in a new window)](https://www.cityofmadison.com/city-hall/committees/meeting-schedule/documents/agendas/041426%20Amtrak.pdf \"Agenda of the Tuesday, Apr. 14, 2026 7:00pm meeting of the Common Council\") PDF |\n| [Friday, Apr. 3, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-04-03 \" Friday, Apr. 3, 2026 at 1:00pm meeting of Common Council\")<br> Notice of possible quorum | 1:00pm |  | - [Agenda(opens in a new window)](https://www.cityofmadison.com/city-hall/committees/meeting-schedule/documents/agendas/040326%20Worker%20Justice%20Wisconsin.pdf \"Agenda of the Friday, Apr. 3, 2026 1:00pm meeting of the Common Council\") PDF |\n| [Wednesday, Mar. 25, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-03-25 \" Wednesday, Mar. 25, 2026 at 6:00pm meeting of Common Council\")<br> Notice of possible quorum | 6:00pm |  | - [Agenda(opens in a new window)](https://www.cityofmadison.com/city-hall/committees/meeting-schedule/documents/agendas/032526%20PCOB.pdf \"Agenda of the Wednesday, Mar. 25, 2026 6:00pm meeting of the Common Council\") PDF |\n| [Tuesday, Mar. 24, 2026](https://www.cityofmadison.com/city-hall/committees/common-council/2026-03-24 \" Tuesday, Mar. 24, 2026 at 6:30pm meeting of Common Council\") | 6:30pm |  | - [Agenda(opens in a new window)](https://madison.legistar.com/View.ashx?M=A&ID=1316258&GUID=C1E119D3-2D0B-4D75-88D2-474EE70217C2 \"Agenda of the Tuesday, Mar. 24, 2026 6:30pm meeting of the Common Council\") PDF<br>  <br>- [Minutes(external)](https://madison.legistar.com/DepartmentDetail.aspx?ID=17248&GUID=09B17CD6-CEFD-4DFC-9A6E-F47D545D907D&Search= \"Minutes of the Tuesday, Mar. 24, 2026 6:30pm meeting of the Common Council, \")<br>  <br>- [Watch](https://media.cityofmadison.com/mediasite/showcase/madison-city-channel/channel/common-council \"Watch the Tuesday, Mar. 24, 2026 6:30pm meeting of the Common Council\") |\n\n[View all past meetings \u00bb](https://www.cityofmadison.com/city-hall/committees/common-council?meeting=past)\n\nWas this page helpful to you?\n\\\\* required\n\nYes\n\n\nNo\n\n\nWhy or why not?\n\n\nLeave this field blank",
        "text_length": 7859,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 18638,
        "promise_count": 0,
        "gemini_tokens_in": 2464,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 5,
    "pdf_url": "https://www.cityofmadison.com/council/meetings-agendas",
    "pdf_size_kb": 0,
    "text_length": 7859,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 26008,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 2464,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "5 candidates, 3 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "5/5 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Zermatt: Gemeinde (DE)",
    "url": "https://gemeinde.zermatt.ch",
    "language": "de",
    "criteria": null,
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 6860,
        "candidate_count": 5,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 613,
        "text": "- [Zum Inhalt springen](https://gemeinde.zermatt.ch/urversammlung/protokoll#main-content)\n\n* * *\n\n![](https://gemeinde.zermatt.ch/images/bg/2004-09-05_07-07-40.jpg)\n\nPolitik\n\nEinwohnergemeinde Zermatt\n\n# Protokoll\n\n## Urversammlungs-Protokolle\n\n- [Protokoll vom 09.12.2025](https://gemeinde.zermatt.ch/pdf/protokoll/pur251209.pdf)(PDF: 545 KB / 28 Seiten)\n- [Protokoll vom 10.06.2025](https://gemeinde.zermatt.ch/pdf/protokoll/pur250610.pdf)(PDF: 501 KB / 17 Seiten)\n- [Protokoll vom 11.02.2025](https://gemeinde.zermatt.ch/pdf/protokoll/pur250211.pdf)(PDF: 328 KB / 13 Seiten)\n- [Protokoll vom 04.06.2024](https://gemeinde.zermatt.ch/pdf/protokoll/pur240604.pdf)(PDF: 755 KB / 29 Seiten)\n- [Protokoll vom 05.12.2023](https://gemeinde.zermatt.ch/pdf/protokoll/pur231205-2.pdf)(PDF: 285 KB / 12 Seiten)\n- [Protokoll vom 06.06.2023](https://gemeinde.zermatt.ch/pdf/protokoll/pur230606.pdf)(PDF: 775 KB / 13 Seiten)\n- [Protokoll vom 07.12.2022](https://gemeinde.zermatt.ch/pdf/protokoll/pur221207.pdf)(PDF: 460 KB / 13 Seiten)\n- [Protokoll vom 07.06.2022](https://gemeinde.zermatt.ch/pdf/protokoll/pur220607.pdf)(PDF: 762 KB / 22 Seiten)\n- [Protokoll vom 07.12.2021](https://gemeinde.zermatt.ch/pdf/protokoll/pur211207-2.pdf)(PDF: 199 KB / 18 Seiten)\n- [Protokoll vom 08.06.2021](https://gemeinde.zermatt.ch/pdf/protokoll/pur210608.pdf)(PDF: 1.1 MB / 38 Seiten)\n- [Protokoll vom 09.02.2021](https://gemeinde.zermatt.ch/pdf/protokoll/pur210209-2.pdf)(PDF: 172 KB / 10 Seiten)\n- [Protokoll vom 25.06.2020](https://gemeinde.zermatt.ch/pdf/protokoll/pur200625.pdf)(PDF: 234 KB / 15 Seiten)\n- [Protokoll vom 03.12.2019](https://gemeinde.zermatt.ch/pdf/protokoll/pur191203-2.pdf)(PDF: 288 KB / 11 Seiten)\n- [Protokoll vom 11.06.2019](https://gemeinde.zermatt.ch/pdf/protokoll/pur190611.pdf)(PDF: 176 KB / 13 Seiten)\n- [Protokoll vom 05.02.2019](https://gemeinde.zermatt.ch/pdf/protokoll/pur190205.pdf)(PDF: 2.3 MB / 18 Seiten)\n- [Protokoll vom 04.12.2018](https://gemeinde.zermatt.ch/pdf/protokoll/pur181204.pdf)(PDF: 174 KB / 13 Seiten)\n- [Protokoll vom 12.06.2018](https://gemeinde.zermatt.ch/pdf/protokoll/pur180612-2.pdf)(PDF: 317 KB / 13 Seiten)\n- [Protokoll vom 24.04.2018](https://gemeinde.zermatt.ch/pdf/protokoll/pur180424-3.pdf)(PDF: 161 KB / 16 Seiten)\n- [Protokoll vom 05.12.2017](https://gemeinde.zermatt.ch/pdf/protokoll/pur171205.pdf)(PDF: 274 KB / 13 Seiten)\n- [Protokoll vom 13.06.2017](https://gemeinde.zermatt.ch/pdf/protokoll/pur170613.pdf)(PDF: 476 KB / 21 Seiten)\n- [Protokoll vom 07.02.2017](https://gemeinde.zermatt.ch/pdf/protokoll/pur170207.pdf)(PDF: 746 KB / 13 Seiten)\n- [Protokoll vom 16.08.2016](https://gemeinde.zermatt.ch/pdf/protokoll/pur160816-2.pdf)(PDF: 215 KB / 43 Seiten)\n- [Protokoll vom 14.06.2016](https://gemeinde.zermatt.ch/pdf/protokoll/pur160614.pdf)(PDF: 447 KB / 20 Seiten)\n- [Protokoll vom 08.03.2016](https://gemeinde.zermatt.ch/pdf/protokoll/pur160308.pdf)(PDF: 133 KB / 10 Seiten)\n- [Protokoll vom 01.12.2015](https://gemeinde.zermatt.ch/pdf/protokoll/pur151201-2.pdf)(PDF: 345 KB / 35 Seiten)\n- [Protokoll vom 02.06.2015](https://gemeinde.zermatt.ch/pdf/protokoll/pur150602.pdf)(PDF: 678 KB / 14 Seiten)\n- [Protokoll vom 24.03.2015](https://gemeinde.zermatt.ch/pdf/protokoll/pur150324.pdf)(PDF: 97 KB / 7 Seiten)\n- [Protokoll vom 09.12.2014](https://gemeinde.zermatt.ch/pdf/protokoll/pur141209.pdf)(PDF: 358 KB / 35 Seiten)\n- [Protokoll vom 03.06.2014](https://gemeinde.zermatt.ch/pdf/protokoll/pur140603.pdf)(PDF: 613 KB / 15 Seiten)\n- [Protokoll vom 04.03.2014](https://gemeinde.zermatt.ch/pdf/protokoll/pur140304.pdf)(PDF: 72 KB / 7 Seiten)\n- [Protokoll vom 10.12.2013](https://gemeinde.zermatt.ch/pdf/protokoll/pur131210.pdf)(PDF: 334 KB / 15 Seiten)\n- [Protokoll vom 18.06.2013](https://gemeinde.zermatt.ch/pdf/protokoll/pur130618.pdf)(PDF: 683 KB / 15 Seiten)\n- [Protokoll vom 15.01.2013](https://gemeinde.zermatt.ch/pdf/protokoll/pur130115-2.pdf)(PDF: 315 KB / 12 Seiten)\n- [Protokoll vom 12.06.2012](https://gemeinde.zermatt.ch/pdf/protokoll/pur120612.pdf)(PDF: 255 KB / 36 Seiten)\n- [Protokoll vom 13.12.2011](https://gemeinde.zermatt.ch/pdf/protokoll/pur111213.pdf)(PDF: 119 KB / 13 Seiten)\n- [Protokoll vom 31.08.2011](https://gemeinde.zermatt.ch/pdf/protokoll/pur110831.pdf)(PDF: 254 KB / 61 Seiten)\n- [Protokoll vom 24.05.2011](https://gemeinde.zermatt.ch/pdf/protokoll/pur110524.pdf)(PDF: 676 KB / 13 Seiten)\n- [Protokoll vom 14.12.2010](https://gemeinde.zermatt.ch/pdf/protokoll/pur101214.pdf)(PDF: 288 KB / 34 Seiten)\n- [Protokoll vom 25.05.2010](https://gemeinde.zermatt.ch/pdf/protokoll/pur100525.pdf)(PDF: 87K / 8 Seiten)\n- [Protokoll vom 25.03.2010](https://gemeinde.zermatt.ch/pdf/protokoll/pur100325.pdf)(PDF: 112K / 19 Seiten)\n- [Protokoll vom 15.12.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur091215.pdf)(PDF: 95K / 14 Seiten)\n- [Protokoll vom 27.10.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur091027.pdf)(PDF: 105K / 9 Seiten)\n- [Protokoll vom 16.06.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur090616.pdf)(PDF: 73K / 17 Seiten)\n- [Protokoll vom 16.02.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur090216.pdf)(PDF: 58K / 11 Seiten)\n- [Protokoll vom 17.06.2008](https://gemeinde.zermatt.ch/pdf/protokoll/pur080617.pdf)(PDF: 210K / 13 Seiten)\n- [Protokoll vom 04.12.2007](https://gemeinde.zermatt.ch/pdf/protokoll/pur071204.pdf)(PDF: 66K / 13 Seiten)\n- [Protokoll vom 19.06.2007](https://gemeinde.zermatt.ch/pdf/protokoll/pur070619.pdf)(PDF: 272K / 12 Seiten)\n- [Protokoll vom 26.04.2007](https://gemeinde.zermatt.ch/pdf/protokoll/pur070426.pdf)(PDF: 98K / 7 Seiten)\n- [Protokoll vom 05.12.2006](https://gemeinde.zermatt.ch/pdf/protokoll/pur061205.pdf)(PDF: 372K / 10 Seiten)\n- [Protokoll vom 08.06.2006](https://gemeinde.zermatt.ch/pdf/protokoll/pur060608.pdf)(PDF: 93K / 7 Seiten)\n- [Protokoll vom 15.12.2005](https://gemeinde.zermatt.ch/pdf/protokoll/pur051215.pdf)(PDF: 116K / 16 Seiten)\n- [Protokoll vom 23.06.2005](https://gemeinde.zermatt.ch/pdf/protokoll/pur050623.pdf)(PDF: 64K / 13 Seiten)\n- [Protokoll vom 24.02.2005](https://gemeinde.zermatt.ch/pdf/protokoll/pur050224.pdf)(PDF: 126K / 8 Seiten)\n- [Protokoll vom 04.11.2004](https://gemeinde.zermatt.ch/pdf/protokoll/pur041104.pdf)(PDF: 36K / 9 Seiten)\n- [Protokoll vom 22.06.2004](https://gemeinde.zermatt.ch/pdf/protokoll/pur040622.pdf)(PDF: 29K / 4 Seiten)\n- [Protokoll vom 06.05.2004](https://gemeinde.zermatt.ch/pdf/protokoll/pur040506.pdf)(PDF: 114K / 14 Seiten)\n- [Protokoll vom 18.12.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur031218.pdf)(PDF: 79K / 7 Seiten)\n- [Protokoll vom 17.06.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur030617.pdf)(PDF: 31K / 7 Seiten)\n- [Protokoll vom 20.05.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur030520.pdf)(PDF: 64K / 9 Seiten)\n- [Protokoll vom 27.03.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur030327.pdf)(PDF: 20K / 5 Seiten)\n- [Protokoll vom 19.12.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur021219.pdf)(PDF: 139K / 10 Seiten)\n- [Protokoll vom 19.06.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur020619.pdf)(PDF: 134K / 7 Seiten)\n- [Protokoll vom 28.05.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur020528.pdf)(PDF: 83K / 11 Seiten)\n- [Protokoll vom 22.01.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur020122.pdf)(PDF: 39K / 10 Seiten)\n- [Protokoll vom 30.10.2001](https://gemeinde.zermatt.ch/pdf/protokoll/pur011030.pdf)(PDF: 61K / 12 Seiten)\n- [Protokoll vom 20.06.2001](https://gemeinde.zermatt.ch/pdf/protokoll/pur010620.pdf)(PDF: 351K / 13 Seiten)\n- [Protokoll vom 27.02.2001](https://gemeinde.zermatt.ch/pdf/protokoll/pur010227.pdf)(PDF: 82K / 15 Seiten)\n\n* * *\n\n## Seitennavigation",
        "text_length": 7635,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 16077,
        "promise_count": 0,
        "gemini_tokens_in": 2408,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 5,
    "pdf_url": "https://gemeinde.zermatt.ch/urversammlung/protokoll",
    "pdf_size_kb": 0,
    "text_length": 7635,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 23551,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 2408,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "5 candidates, 5 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "5/5 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  },
  {
    "scenario": "Zermatt: Gemeinde + criteria (DE)",
    "url": "https://gemeinde.zermatt.ch",
    "language": "de",
    "criteria": "Infrastruktur",
    "steps": [
      {
        "step": "discover",
        "elapsed_ms": 7783,
        "candidate_count": 5,
        "firecrawl_credits": 1,
        "error": null
      },
      {
        "step": "download_and_parse",
        "doc_type": "html",
        "elapsed_ms": 398,
        "text": "- [Zum Inhalt springen](https://gemeinde.zermatt.ch/urversammlung/protokoll#main-content)\n\n* * *\n\n![](https://gemeinde.zermatt.ch/images/bg/2004-09-05_07-07-40.jpg)\n\nPolitik\n\nEinwohnergemeinde Zermatt\n\n# Protokoll\n\n## Urversammlungs-Protokolle\n\n- [Protokoll vom 09.12.2025](https://gemeinde.zermatt.ch/pdf/protokoll/pur251209.pdf)(PDF: 545 KB / 28 Seiten)\n- [Protokoll vom 10.06.2025](https://gemeinde.zermatt.ch/pdf/protokoll/pur250610.pdf)(PDF: 501 KB / 17 Seiten)\n- [Protokoll vom 11.02.2025](https://gemeinde.zermatt.ch/pdf/protokoll/pur250211.pdf)(PDF: 328 KB / 13 Seiten)\n- [Protokoll vom 04.06.2024](https://gemeinde.zermatt.ch/pdf/protokoll/pur240604.pdf)(PDF: 755 KB / 29 Seiten)\n- [Protokoll vom 05.12.2023](https://gemeinde.zermatt.ch/pdf/protokoll/pur231205-2.pdf)(PDF: 285 KB / 12 Seiten)\n- [Protokoll vom 06.06.2023](https://gemeinde.zermatt.ch/pdf/protokoll/pur230606.pdf)(PDF: 775 KB / 13 Seiten)\n- [Protokoll vom 07.12.2022](https://gemeinde.zermatt.ch/pdf/protokoll/pur221207.pdf)(PDF: 460 KB / 13 Seiten)\n- [Protokoll vom 07.06.2022](https://gemeinde.zermatt.ch/pdf/protokoll/pur220607.pdf)(PDF: 762 KB / 22 Seiten)\n- [Protokoll vom 07.12.2021](https://gemeinde.zermatt.ch/pdf/protokoll/pur211207-2.pdf)(PDF: 199 KB / 18 Seiten)\n- [Protokoll vom 08.06.2021](https://gemeinde.zermatt.ch/pdf/protokoll/pur210608.pdf)(PDF: 1.1 MB / 38 Seiten)\n- [Protokoll vom 09.02.2021](https://gemeinde.zermatt.ch/pdf/protokoll/pur210209-2.pdf)(PDF: 172 KB / 10 Seiten)\n- [Protokoll vom 25.06.2020](https://gemeinde.zermatt.ch/pdf/protokoll/pur200625.pdf)(PDF: 234 KB / 15 Seiten)\n- [Protokoll vom 03.12.2019](https://gemeinde.zermatt.ch/pdf/protokoll/pur191203-2.pdf)(PDF: 288 KB / 11 Seiten)\n- [Protokoll vom 11.06.2019](https://gemeinde.zermatt.ch/pdf/protokoll/pur190611.pdf)(PDF: 176 KB / 13 Seiten)\n- [Protokoll vom 05.02.2019](https://gemeinde.zermatt.ch/pdf/protokoll/pur190205.pdf)(PDF: 2.3 MB / 18 Seiten)\n- [Protokoll vom 04.12.2018](https://gemeinde.zermatt.ch/pdf/protokoll/pur181204.pdf)(PDF: 174 KB / 13 Seiten)\n- [Protokoll vom 12.06.2018](https://gemeinde.zermatt.ch/pdf/protokoll/pur180612-2.pdf)(PDF: 317 KB / 13 Seiten)\n- [Protokoll vom 24.04.2018](https://gemeinde.zermatt.ch/pdf/protokoll/pur180424-3.pdf)(PDF: 161 KB / 16 Seiten)\n- [Protokoll vom 05.12.2017](https://gemeinde.zermatt.ch/pdf/protokoll/pur171205.pdf)(PDF: 274 KB / 13 Seiten)\n- [Protokoll vom 13.06.2017](https://gemeinde.zermatt.ch/pdf/protokoll/pur170613.pdf)(PDF: 476 KB / 21 Seiten)\n- [Protokoll vom 07.02.2017](https://gemeinde.zermatt.ch/pdf/protokoll/pur170207.pdf)(PDF: 746 KB / 13 Seiten)\n- [Protokoll vom 16.08.2016](https://gemeinde.zermatt.ch/pdf/protokoll/pur160816-2.pdf)(PDF: 215 KB / 43 Seiten)\n- [Protokoll vom 14.06.2016](https://gemeinde.zermatt.ch/pdf/protokoll/pur160614.pdf)(PDF: 447 KB / 20 Seiten)\n- [Protokoll vom 08.03.2016](https://gemeinde.zermatt.ch/pdf/protokoll/pur160308.pdf)(PDF: 133 KB / 10 Seiten)\n- [Protokoll vom 01.12.2015](https://gemeinde.zermatt.ch/pdf/protokoll/pur151201-2.pdf)(PDF: 345 KB / 35 Seiten)\n- [Protokoll vom 02.06.2015](https://gemeinde.zermatt.ch/pdf/protokoll/pur150602.pdf)(PDF: 678 KB / 14 Seiten)\n- [Protokoll vom 24.03.2015](https://gemeinde.zermatt.ch/pdf/protokoll/pur150324.pdf)(PDF: 97 KB / 7 Seiten)\n- [Protokoll vom 09.12.2014](https://gemeinde.zermatt.ch/pdf/protokoll/pur141209.pdf)(PDF: 358 KB / 35 Seiten)\n- [Protokoll vom 03.06.2014](https://gemeinde.zermatt.ch/pdf/protokoll/pur140603.pdf)(PDF: 613 KB / 15 Seiten)\n- [Protokoll vom 04.03.2014](https://gemeinde.zermatt.ch/pdf/protokoll/pur140304.pdf)(PDF: 72 KB / 7 Seiten)\n- [Protokoll vom 10.12.2013](https://gemeinde.zermatt.ch/pdf/protokoll/pur131210.pdf)(PDF: 334 KB / 15 Seiten)\n- [Protokoll vom 18.06.2013](https://gemeinde.zermatt.ch/pdf/protokoll/pur130618.pdf)(PDF: 683 KB / 15 Seiten)\n- [Protokoll vom 15.01.2013](https://gemeinde.zermatt.ch/pdf/protokoll/pur130115-2.pdf)(PDF: 315 KB / 12 Seiten)\n- [Protokoll vom 12.06.2012](https://gemeinde.zermatt.ch/pdf/protokoll/pur120612.pdf)(PDF: 255 KB / 36 Seiten)\n- [Protokoll vom 13.12.2011](https://gemeinde.zermatt.ch/pdf/protokoll/pur111213.pdf)(PDF: 119 KB / 13 Seiten)\n- [Protokoll vom 31.08.2011](https://gemeinde.zermatt.ch/pdf/protokoll/pur110831.pdf)(PDF: 254 KB / 61 Seiten)\n- [Protokoll vom 24.05.2011](https://gemeinde.zermatt.ch/pdf/protokoll/pur110524.pdf)(PDF: 676 KB / 13 Seiten)\n- [Protokoll vom 14.12.2010](https://gemeinde.zermatt.ch/pdf/protokoll/pur101214.pdf)(PDF: 288 KB / 34 Seiten)\n- [Protokoll vom 25.05.2010](https://gemeinde.zermatt.ch/pdf/protokoll/pur100525.pdf)(PDF: 87K / 8 Seiten)\n- [Protokoll vom 25.03.2010](https://gemeinde.zermatt.ch/pdf/protokoll/pur100325.pdf)(PDF: 112K / 19 Seiten)\n- [Protokoll vom 15.12.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur091215.pdf)(PDF: 95K / 14 Seiten)\n- [Protokoll vom 27.10.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur091027.pdf)(PDF: 105K / 9 Seiten)\n- [Protokoll vom 16.06.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur090616.pdf)(PDF: 73K / 17 Seiten)\n- [Protokoll vom 16.02.2009](https://gemeinde.zermatt.ch/pdf/protokoll/pur090216.pdf)(PDF: 58K / 11 Seiten)\n- [Protokoll vom 17.06.2008](https://gemeinde.zermatt.ch/pdf/protokoll/pur080617.pdf)(PDF: 210K / 13 Seiten)\n- [Protokoll vom 04.12.2007](https://gemeinde.zermatt.ch/pdf/protokoll/pur071204.pdf)(PDF: 66K / 13 Seiten)\n- [Protokoll vom 19.06.2007](https://gemeinde.zermatt.ch/pdf/protokoll/pur070619.pdf)(PDF: 272K / 12 Seiten)\n- [Protokoll vom 26.04.2007](https://gemeinde.zermatt.ch/pdf/protokoll/pur070426.pdf)(PDF: 98K / 7 Seiten)\n- [Protokoll vom 05.12.2006](https://gemeinde.zermatt.ch/pdf/protokoll/pur061205.pdf)(PDF: 372K / 10 Seiten)\n- [Protokoll vom 08.06.2006](https://gemeinde.zermatt.ch/pdf/protokoll/pur060608.pdf)(PDF: 93K / 7 Seiten)\n- [Protokoll vom 15.12.2005](https://gemeinde.zermatt.ch/pdf/protokoll/pur051215.pdf)(PDF: 116K / 16 Seiten)\n- [Protokoll vom 23.06.2005](https://gemeinde.zermatt.ch/pdf/protokoll/pur050623.pdf)(PDF: 64K / 13 Seiten)\n- [Protokoll vom 24.02.2005](https://gemeinde.zermatt.ch/pdf/protokoll/pur050224.pdf)(PDF: 126K / 8 Seiten)\n- [Protokoll vom 04.11.2004](https://gemeinde.zermatt.ch/pdf/protokoll/pur041104.pdf)(PDF: 36K / 9 Seiten)\n- [Protokoll vom 22.06.2004](https://gemeinde.zermatt.ch/pdf/protokoll/pur040622.pdf)(PDF: 29K / 4 Seiten)\n- [Protokoll vom 06.05.2004](https://gemeinde.zermatt.ch/pdf/protokoll/pur040506.pdf)(PDF: 114K / 14 Seiten)\n- [Protokoll vom 18.12.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur031218.pdf)(PDF: 79K / 7 Seiten)\n- [Protokoll vom 17.06.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur030617.pdf)(PDF: 31K / 7 Seiten)\n- [Protokoll vom 20.05.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur030520.pdf)(PDF: 64K / 9 Seiten)\n- [Protokoll vom 27.03.2003](https://gemeinde.zermatt.ch/pdf/protokoll/pur030327.pdf)(PDF: 20K / 5 Seiten)\n- [Protokoll vom 19.12.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur021219.pdf)(PDF: 139K / 10 Seiten)\n- [Protokoll vom 19.06.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur020619.pdf)(PDF: 134K / 7 Seiten)\n- [Protokoll vom 28.05.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur020528.pdf)(PDF: 83K / 11 Seiten)\n- [Protokoll vom 22.01.2002](https://gemeinde.zermatt.ch/pdf/protokoll/pur020122.pdf)(PDF: 39K / 10 Seiten)\n- [Protokoll vom 30.10.2001](https://gemeinde.zermatt.ch/pdf/protokoll/pur011030.pdf)(PDF: 61K / 12 Seiten)\n- [Protokoll vom 20.06.2001](https://gemeinde.zermatt.ch/pdf/protokoll/pur010620.pdf)(PDF: 351K / 13 Seiten)\n- [Protokoll vom 27.02.2001](https://gemeinde.zermatt.ch/pdf/protokoll/pur010227.pdf)(PDF: 82K / 15 Seiten)\n\n* * *\n\n## Seitennavigation",
        "text_length": 7635,
        "file_size_kb": 0,
        "llamaparse_pages": 0,
        "error": null
      },
      {
        "step": "extract_promises",
        "elapsed_ms": 9737,
        "promise_count": 0,
        "gemini_tokens_in": 2408,
        "gemini_tokens_out": 0,
        "error": null
      }
    ],
    "candidate_count": 5,
    "pdf_url": "https://gemeinde.zermatt.ch/urversammlung/protokoll",
    "pdf_size_kb": 0,
    "text_length": 7635,
    "llamaparse_pages": 0,
    "promise_count": 0,
    "promises": [],
    "total_time_ms": 17920,
    "firecrawl_credits": 1,
    "gemini_tokens_in": 2408,
    "gemini_tokens_out": 0,
    "error": null,
    "quality_checks": [
      {
        "check": "discovery",
        "status": "PASS",
        "detail": "5 candidates, 4 high-confidence",
        "issues": []
      },
      {
        "check": "url_coverage",
        "status": "PASS",
        "detail": "5/5 on-domain",
        "off_domain": []
      },
      {
        "check": "promises",
        "status": "WARN",
        "detail": "no promises extracted (may be expected for some documents)",
        "issues": []
      }
    ]
  }
]
```
