"""
app.py — CISS Manager Streamlit UI

Run with:
    streamlit run app/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd

from search import search_ciss, AVAILABLE_YEARS
from model_labels import MODEL_LABELS

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CISS Manager",
    page_icon="🚗",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

:root {
    --primary:     #2C5AA0;
    --secondary:   #4A6FA5;
    --bg:          #F5F7FA;
    --card:        #FFFFFF;
    --text:        #2E2E2E;
    --text-meta:   #6B7280;
    --accent:      #2CB1BC;
    --error:       #D64545;
    --border:      #E2E6EF;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    color: var(--text);
}

.stApp {
    background-color: var(--bg);
}

/* ---- Header ---- */
.ciss-header {
    background: var(--primary);
    border-radius: 10px;
    padding: 1.25rem 1.75rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: baseline;
    gap: 1rem;
}
.ciss-title {
    font-family: 'DM Mono', monospace;
    font-size: 1.5rem;
    font-weight: 500;
    color: #ffffff;
    margin: 0;
    letter-spacing: -0.01em;
}
.ciss-subtitle {
    font-size: 0.8rem;
    color: rgba(255,255,255,0.65);
    margin: 0;
}

/* ---- Form card ---- */
.form-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 1px 4px rgba(44,90,160,0.06);
}
.section-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    font-weight: 500;
    color: var(--text-meta);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0.85rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.4rem;
}

/* ---- Widget labels ---- */
div[data-testid="stSelectbox"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stToggle"] label {
    font-size: 0.75rem !important;
    color: var(--text-meta) !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* ---- Select / input boxes ---- */
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stNumberInput"] input {
    background-color: #F9FAFB !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 6px !important;
    font-size: 0.875rem !important;
}
div[data-testid="stSelectbox"] > div > div:focus-within,
div[data-testid="stNumberInput"] input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(44,90,160,0.12) !important;
}

/* ---- Primary button ---- */
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: var(--primary) !important;
    border: none !important;
    color: #ffffff !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    letter-spacing: 0.03em !important;
    border-radius: 6px !important;
    padding: 0.55rem 1.5rem !important;
    width: 100% !important;
    transition: background 0.15s ease !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: #234d8a !important;
}

/* ---- Secondary button (export) ---- */
div[data-testid="stDownloadButton"] > button {
    background-color: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-meta) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}

/* ---- Toggle ---- */
div[data-testid="stToggle"] > label > div[data-testid="stToggleSwitch"] > div {
    background-color: var(--accent) !important;
}

/* ---- Results card ---- */
.results-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem 1.75rem;
    box-shadow: 0 1px 4px rgba(44,90,160,0.06);
}
.results-meta {
    font-size: 0.8rem;
    color: var(--text-meta);
    margin-bottom: 0.75rem;
}
.results-count {
    font-weight: 600;
    color: var(--primary);
    font-size: 1rem;
}
.results-label {
    color: var(--text-meta);
}

/* ---- Dataframe ---- */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* ---- Info / error boxes ---- */
div[data-testid="stInfo"] {
    background-color: #EFF6FF !important;
    border-left: 3px solid var(--primary) !important;
    color: var(--text) !important;
    border-radius: 6px !important;
}
div[data-testid="stAlert"] {
    border-radius: 6px !important;
}

/* ---- Divider ---- */
hr {
    border-color: var(--border) !important;
    margin: 1rem 0 !important;
}

/* ---- Spinner ---- */
div[data-testid="stSpinner"] {
    color: var(--primary) !important;
}

/* ---- Remove default top padding / white gaps ---- */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 1rem !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
    border-bottom: none !important;
}
div[data-testid="stDecoration"] {
    display: none !important;
}
div[data-testid="stToolbar"] {
    display: none !important;
}
#MainMenu {
    display: none !important;
}
footer {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Build make / model lookup structures
# ---------------------------------------------------------------------------

MAKE_LABELS = {
    1:  "American Motors",
    2:  "Jeep",
    3:  "AM General",
    4:  "Willys",
    5:  "Kaiser",
    6:  "Chrysler",
    7:  "Dodge",
    8:  "Plymouth",
    9:  "Ram",
    10: "Eagle",
    11: "Imperial",
    12: "Ford",
    13: "Lincoln",
    14: "Mercury",
    15: "Edsel",
    16: "Oldsmobile",
    17: "Pontiac",
    18: "Buick",
    19: "Cadillac",
    20: "Chevrolet",
    21: "Saturn",
    22: "Hummer",
    23: "GMC",
    24: "Tesla",
    25: "Grumman",
    26: "Coda",
    27: "Rivian",
    28: "Lucid",
    29: "Fisker",
    30: "Polestar",
    31: "Alfa Romeo",
    32: "Audi",
    33: "Austin/Austin-Healey",
    34: "BMW",
    35: "Mini",
    36: "Fiat",
    37: "Honda",
    38: "Isuzu",
    39: "Jaguar",
    40: "Land Rover",
    41: "Lotus",
    42: "Maserati",
    43: "Mazda",
    44: "Mercedes-Benz",
    45: "MG",
    46: "Mitsubishi",
    47: "Nissan/Datsun",
    48: "Porsche",
    49: "Toyota",
    50: "Triumph",
    51: "Volkswagen",
    52: "Volvo",
    53: "Saab",
    54: "Acura",
    55: "Hyundai",
    56: "Suzuki",
    57: "Yugo",
    58: "Infiniti",
    59: "Lexus",
    60: "Daihatsu",
    61: "Geo",
    62: "Sterling",
    63: "Eagle Premier",
    64: "Daewoo",
    65: "Kia",
    66: "Subaru",
    67: "Scion",
    68: "Smart",
    69: "Genesis",
    70: "Freightliner",
    71: "Other domestic",
    72: "Other foreign",
    73: "Unknown make",
    80: "Blue Bird",
    81: "IC Bus",
    82: "Thomas Built",
    83: "Other bus",
    84: "Unknown bus make",
    85: "Unknown",
}

DAMAGE_PLANE_OPTIONS = {
    "Any":           None,
    "Front":         "F",
    "Back":          "B",
    "Left":          "L",
    "Right":         "R",
    "Top":           "T",
    "Undercarriage": "U",
}

AVAILABLE_MAKE_CODES = sorted(MODEL_LABELS.keys())
MAKE_OPTIONS = {MAKE_LABELS.get(k, f"Make {k}"): k for k in AVAILABLE_MAKE_CODES}
SORTED_MAKE_OPTIONS = dict(sorted(MAKE_OPTIONS.items()))


def get_model_options(make_code: int) -> dict:
    models = MODEL_LABELS.get(make_code, {})
    def sort_key(item):
        label = item[1]
        if label.lower().startswith("other") or label.lower().startswith("unknown"):
            return "zzz" + label
        return label
    sorted_models = sorted(models.items(), key=sort_key)
    options = {"All Models": None}
    options.update({label: code for code, label in sorted_models})
    return options


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="ciss-header">
    <p class="ciss-title">CISS Manager</p>
    <p class="ciss-subtitle">NHTSA Crash Investigation Sampling System — Case Search Tool</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Search form
# ---------------------------------------------------------------------------

st.markdown('<p class="section-label">Vehicle & Damage Criteria</p>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([2, 2, 1.5])

with col1:
    make_keys = list(SORTED_MAKE_OPTIONS.keys())
    selected_make_label = st.selectbox(
        "Make",
        options=make_keys,
        index=None,
        placeholder="Type or select a make...",
    )
    make_code = SORTED_MAKE_OPTIONS.get(selected_make_label)

with col2:
    model_options = get_model_options(make_code) if make_code is not None else {"All Models": None}
    selected_model_label = st.selectbox(
        "Model",
        options=list(model_options.keys()),
        index=None,
        placeholder="Type or select a model...",
        disabled=(make_code is None),
    )
    model_code = model_options.get(selected_model_label)

with col3:
    selected_plane_label = st.selectbox(
        "Damage Plane",
        options=list(DAMAGE_PLANE_OPTIONS.keys()),
        index=1,
    )
    damage_plane = DAMAGE_PLANE_OPTIONS[selected_plane_label]

st.markdown('<p class="section-label" style="margin-top:1rem;">Filters</p>', unsafe_allow_html=True)

col4, col5, col6, col7 = st.columns(4)

with col4:
    modelyr_min = st.number_input(
        "Model Year Min", min_value=1960, max_value=2026,
        value=None, placeholder="Any", step=1,
    )
with col5:
    modelyr_max = st.number_input(
        "Model Year Max", min_value=1960, max_value=2026,
        value=None, placeholder="Any", step=1,
    )
with col6:
    dv_min = st.number_input(
        "Delta-V Min (mph)", min_value=0.0, max_value=200.0,
        value=None, placeholder="Any", step=1.0,
    )
with col7:
    dv_max = st.number_input(
        "Delta-V Max (mph)", min_value=0.0, max_value=200.0,
        value=None, placeholder="Any", step=1.0,
    )

col8, col9 = st.columns([3, 1])

with col8:
    vehicle_contact_only = st.toggle(
        "Vehicle contacts only — exclude fixed objects, pedestrians, etc.",
        value=False,
        disabled=(damage_plane is None),
        help="Only available when a specific damage plane is selected.",
    )

with col9:
    st.write("")
    search_clicked = st.button("Search", type="primary")

# ---------------------------------------------------------------------------
# Search execution
# ---------------------------------------------------------------------------

if search_clicked:
    if modelyr_min and modelyr_max and modelyr_min > modelyr_max:
        st.error("Model Year Min cannot be greater than Model Year Max.")
    elif dv_min and dv_max and dv_min > dv_max:
        st.error("Delta-V Min cannot be greater than Delta-V Max.")
    else:
        if make_code is None:
            st.error("Please select a make before searching.")
        else:
            with st.spinner(f"Searching CISS {AVAILABLE_YEARS[0]}–{AVAILABLE_YEARS[-1]}..."):
                try:
                    df = search_ciss(
                        make_code=make_code,
                        model_code=model_code,
                        modelyr_min=int(modelyr_min) if modelyr_min else None,
                        modelyr_max=int(modelyr_max) if modelyr_max else None,
                        damage_plane=damage_plane,
                        dv_min=float(dv_min) if dv_min else None,
                        dv_max=float(dv_max) if dv_max else None,
                        vehicle_contact_only=vehicle_contact_only,
                        years=AVAILABLE_YEARS,
                    )
                    st.session_state["results"] = df
                    model_display = selected_model_label if selected_model_label else "All Models"
                    st.session_state["search_label"] = (
                        f"{selected_make_label} {model_display}"
                        f" · {selected_plane_label} plane"
                        f"{' · Vehicle contacts only' if vehicle_contact_only else ''}"
                    )
                except Exception as e:
                    st.error(f"Search failed: {e}")
                    st.session_state["results"] = None

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

if "results" in st.session_state and st.session_state["results"] is not None:
    df = st.session_state["results"]
    label = st.session_state.get("search_label", "")

    st.markdown("---")

    if df.empty:
        st.info("No cases found matching the selected criteria.")
    else:
        st.markdown(
            f'<div class="results-meta">'
            f'<span class="results-count">{len(df)}</span>'
            f' <span class="results-label">cases found &nbsp;·&nbsp; {label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        display_df = df[[
            "CASEID", "VEHNO", "MODELYR",
            "CDC_DV_MPH", "EDR_DV_MPH", "EDR_NOTE",
            "CRASHVIEWER_URL",
        ]].copy()

        display_df = display_df.rename(columns={
            "CASEID":          "Case ID",
            "VEHNO":           "Veh #",
            "MODELYR":         "Model Year",
            "CDC_DV_MPH":      "CDC ΔV (mph)",
            "EDR_DV_MPH":      "EDR ΔV (mph)",
            "EDR_NOTE":        "EDR Note",
            "CRASHVIEWER_URL": "CrashViewer",
        })

        # Sort: EDR DV ascending first, then CDC-only rows ascending at bottom
        has_edr = display_df["EDR ΔV (mph)"].notna()
        edr_rows = display_df[has_edr].sort_values("EDR ΔV (mph)", ascending=True)
        cdc_only_rows = display_df[~has_edr].sort_values("CDC ΔV (mph)", ascending=True, na_position="last")
        display_df = pd.concat([edr_rows, cdc_only_rows], ignore_index=True)

        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Case ID":      st.column_config.NumberColumn(format="%d"),
                "Veh #":        st.column_config.NumberColumn(format="%d"),
                "Model Year":   st.column_config.NumberColumn(format="%d"),
                "CDC ΔV (mph)": st.column_config.NumberColumn(format="%.1f"),
                "EDR ΔV (mph)": st.column_config.NumberColumn(format="%.1f"),
                "CrashViewer":  st.column_config.LinkColumn(display_text="Open ↗"),
            },
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # EDR note legend
        st.markdown("""
<div style="background:#F0F4FA; border:1px solid #E2E6EF; border-radius:8px; padding:1rem 1.25rem; margin-bottom:1rem;">
<p style="font-family:'DM Mono',monospace; font-size:0.65rem; font-weight:500; color:#6B7280; letter-spacing:0.12em; text-transform:uppercase; margin:0 0 0.65rem 0; border-bottom:1px solid #E2E6EF; padding-bottom:0.4rem;">EDR Note Legend</p>
<p style="font-size:0.8rem; color:#2E2E2E; margin:0.3rem 0;"><strong>EDR: Confirmed event</strong> — Single EDR event with a related CDCEVENT code (1–30 or 95). High confidence this delta-V corresponds to the crash of interest.</p>
<p style="font-size:0.8rem; color:#2E2E2E; margin:0.3rem 0;"><strong>EDR: Matched to CDC event</strong> — Multiple EDR events present; this value matched to the CDC event number for the searched damage plane. High confidence.</p>
<p style="font-size:0.8rem; color:#2E2E2E; margin:0.3rem 0;"><strong>EDR: Single event, relatedness uncertain — verify on CrashViewer</strong> — Single EDR event but CDCEVENT code indicates unknown or non-related event. Verify manually before relying on this value.</p>
<p style="font-size:0.8rem; color:#2E2E2E; margin:0.3rem 0;"><strong>EDR: No event recorded (&lt;5 mph)</strong> — EDR was obtained but recorded no event, indicating delta-V was below the ~5 mph recording threshold. Value reported as 5.0 mph.</p>
<p style="font-size:0.8rem; color:#2E2E2E; margin:0.3rem 0;"><strong>EDR: No matching event</strong> — Multiple EDR events present but none matched the CDC event for the searched damage plane. EDR delta-V not reported for this case.</p>
<p style="font-size:0.8rem; color:#2E2E2E; margin:0.3rem 0;"><strong>EDR: Multiple events — verify on CrashViewer</strong> — Multiple EDR events present and no damage plane was specified. Cannot determine which event corresponds to the contact of interest; verify manually.</p>
</div>
""", unsafe_allow_html=True)

        csv = display_df.to_csv(index=False)
        st.download_button(
            label="⬇  Export CSV",
            data=csv,
            file_name=f"ciss_{selected_make_label}_{selected_model_label}.csv".replace(" ", "_"),
            mime="text/csv",
        )

