# CISS Manager

A Streamlit-based search tool for the [NHTSA Crash Investigation Sampling System (CISS)](https://www.nhtsa.gov/crash-data-systems/crash-investigation-sampling-system) database. Built for accident reconstruction and forensic engineering workflows.

**Live app:** [ciss-tool.streamlit.app](https://ciss-tool.streamlit.app)

**Files for Basis:** [NHTSA File location](https://www.nhtsa.gov/file-downloads?p=nhtsa/downloads/CISS/) 
**Reference Literature:** [CISS 2024 Analytical User's Handbook](https://crashstats.nhtsa.dot.gov/Api/Public/ViewPublication/813771)

---

## What It Does

CISS Manager lets you search across CISS case years (2017–2024) by vehicle make, model, model year range, damage plane, and delta-V range. As a note, this search tool is only for passenger vehicles within CISS. For each matching case it returns:

- Case ID with a direct link to the NHTSA CrashViewer
- Vehicle number within the case
- Model year
- CDC delta-V (mph)
- EDR delta-V (mph) with a note indicating confidence level
- Export to CSV

---

## Search Parameters

| Parameter | Description |
|---|---|
| **Make** | Vehicle manufacturer (e.g. Toyota, Ford) |
| **Model** | Specific model — filtered by selected make |
| **Damage Plane** | Front, Back, Left, Right, Top, Undercarriage, or Any |
| **Model Year Min/Max** | Optional range filter on the vehicle's model year |
| **Delta-V Min/Max** | Optional range filter in mph — uses CDC DV preferred, EDR as fallback. Note this is a positive resultant of longitudinal and lateral |
| **Vehicle contacts only** | When a damage plane is selected, filters to vehicle-to-vehicle contacts only (excludes fixed objects, pedestrians, etc.) |

---

## Delta-V Notes

All delta-V values are converted from km/h to mph. CDC delta-V is reported as the primary value where available; EDR delta-V is used as a fallback for the delta-V range filter.

Each result includes an **EDR Note** describing the confidence level of the EDR value:

| Note | Meaning |
|---|---|
| **EDR: Confirmed event** | Single EDR event with a related CDCEVENT code. High confidence. |
| **EDR: Matched to CDC event** | Multiple EDR events; matched to the CDC event for the searched damage plane. High confidence. |
| **EDR: Single event, relatedness uncertain — verify on CrashViewer** | Single EDR event but CDCEVENT code is unknown or non-related. Verify manually before relying on this value. |
| **EDR: No event recorded (<5 mph)** | EDR obtained but no event recorded — delta-V was below the ~5 mph recording threshold. Reported as 5.0 mph. |
| **EDR: No matching event** | Multiple EDR events present but none matched the CDC event for the searched damage plane. EDR DV not reported. |
| **EDR: Multiple events — verify on CrashViewer** | Multiple EDR events and no damage plane specified. Cannot determine which event corresponds to the contact of interest. |

---

## Data

The app uses the following SAS tables from each CISS year folder:

| Table | Contents |
|---|---|
| `gv` | Vehicle make, model, year, VIN, damage plane, CDC delta-V |
| `event` | Harmful events — used for damage plane matching and vehicle contact filtering |
| `cdc` | CDC-calculated delta-V by event and plane |
| `edrcollect` | EDR collection status per vehicle |
| `edrevent` | EDR event delta-V components (longitudinal and lateral) |
| `crash` | Top-level case info including crash year |

Data covers CISS years 2017–2024. 2016 uses a different format and is excluded, it only includes a minimal subset of data due to overlap with NASS-CDS. When future years of data becomes published, those contents will need to be inserted and minor edits likely necessary.

---

## Running Locally

### Prerequisites

- Python 3.10+
- CISS SAS data files organized as `data/CISS_{year}_SAS_files/`

### Setup

```bash
# Clone the repo
git clone https://github.com/adshelton/CISS-Manager.git
cd CISS-Manager

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app/app.py
```

The app will open automatically at `http://localhost:8501`.

### Data Folder Structure

```
CISS-Manager/
├── app/
│   ├── app.py
│   ├── search.py
│   └── model_labels.py
├── data/
│   ├── CISS_2017_SAS_files/
│   │   ├── gv.sas7bdat
│   │   ├── event.sas7bdat
│   │   ├── cdc.sas7bdat
│   │   ├── edrcollect.sas7bdat
│   │   ├── edrevent.sas7bdat
│   │   └── crash.sas7bdat
│   ├── CISS_2018_SAS_files/
│   │   └── ...
│   └── ... (through 2024)
└── requirements.txt
```

---

## Project Structure

```
app/
├── app.py            # Streamlit UI
├── search.py         # Core search logic
└── model_labels.py   # Make/model code → label lookup dictionary
```

---

## Technical Notes

- **Make/model coding:** Uses NHTSA legacy numeric codes consistent across all years (2017–2024). VPIC codes (available 2021+) are not used.
- **CDC delta-V plane scoping:** When a damage plane is specified, CDC delta-V is filtered to rows where `CDCPLANE` matches the searched plane, ensuring the correct contact is reported for vehicles with multiple CDC events.
- **Vehicle contact filtering:** Year-aware — uses `OBJCONT` (2017–2023) and `OBJCLASS` (2024+) per NHTSA coding changes.
- **EDR resultant:** Computed from `MAXDVLONG` and `MAXDVLAT`. Sentinel values (888, 997) are handled per-component — if one component is invalid the other is used as a scalar.

---

## Dependencies

```
pandas
streamlit>=1.35.0
pyreadstat
altair>=5.0.0
```

## Fun Facts on CISS Database Learned

```
There are occasional edge cases where the CISS Web Search function disagrees with the background data documents. One such instance is CASEID 12257, a 2011 Ford Escape's front contacts the rear of a 2018 Ford Escape. If you do a test run of rear damage to 2018 Ford Escapes in this search feature it will inform you that vehicle #2 of this CASEID experienced a rear contact with a CDC delta-V of 12 kph. However on the CISS website, you will see crush measurements taken for Vehicle #2 however the CDC delta-V is assigned to Vehicle #1 which disagrees with the background data.

EDR data is reportedly automatically uploaded from Bosch CDR files into the system during the inspection process. There are rare errors, so please verify. 

CASEID was chosen as it is more easily repopulated into the CISS search function per their website and utilized in their URLs vs other case identifiers.

The US is partitioned into 1,784 PSUs at last count.

For damage profiles, Rear of Cab and Back (rear of tractor) are only applicable to TDC applicable vehicles and medium/heavy trucks.
```
