"""
search.py — CISS Manager core search module

Loads SAS tables for one or more years, filters by:
  - Vehicle make / model (via legacy MAKE and MODEL numeric codes)
  - Model year range (MODELYR)
  - Damage plane (GAD1/GAD2 in event table)
  - Delta-V range (applied to whichever DV columns are available)
  - Vehicle contact only (optional toggle)

All delta-V values in CISS are stored in km/h and converted to mph on output.
CDC and EDR delta-V are reported in separate columns with an EDR_NOTE column.
Cases where neither CDC nor EDR is available are excluded entirely.

Returns a DataFrame of matching cases with a CrashViewer URL column.
"""

import os
import math
import pandas as pd
import pyreadstat

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_ROOT = r"C:\Users\andyd\Documents\ciss-tool\data"

AVAILABLE_YEARS = list(range(2017, 2025))  # 2017-2024

CRASHVIEWER_URL = "https://crashviewer.nhtsa.dot.gov/CISS/details/{}"

KMH_TO_MPH = 0.621371

# EDR sentinel values — treat as missing for that component
EDR_SENTINEL = {888, 997}

# CDCEVENT codes considered "related to this crash event"
CDCEVENT_RELATED = set(range(1, 31)) | {95}

# Years using OBJCONT (1-30 = vehicle contact) vs OBJCLASS (1 = vehicle)
OBJCONT_YEARS = set(range(2017, 2024))   # 2017-2023
OBJCLASS_YEARS = {2024}                   # 2024+


# ---------------------------------------------------------------------------
# Byte-string decoding helpers
# ---------------------------------------------------------------------------

def decode_bytes(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return value


def decode_column(series: pd.Series) -> pd.Series:
    return series.apply(decode_bytes)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def get_year_path(year: int) -> str:
    return os.path.join(DATA_ROOT, f"CISS_{year}_SAS_files")


def _read(year_path: str, table_name: str, usecols=None) -> pd.DataFrame:
    path = os.path.join(year_path, f"{table_name}.sas7bdat")
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df, _ = pyreadstat.read_sas7bdat(path, usecols=usecols)
        return df
    except Exception as e:
        print(f"  Warning: could not read {path}: {e}")
        return pd.DataFrame()


def load_tables(year: int) -> dict:
    yp = get_year_path(year)

    gv = _read(yp, "gv", usecols=[
        "CASEID", "VEHNO", "MAKE", "MODEL", "MODELYR", "VIN",
        "DAMPLANE", "DVTOTAL", "DVLONG", "DVLAT", "DVBASIS", "DVCONF",
    ])

    # Load event table with all potentially needed columns
    # OBJCONT used 2017-2023, OBJCLASS used 2024+
    event_cols = ["CASEID", "VEHNUM", "EVENTNO", "CLASS1", "GAD1",
                  "OBJCLASS", "OBJCONT", "CLASS2", "GAD2"]
    event = _read(yp, "event", usecols=event_cols)

    cdc = _read(yp, "cdc", usecols=[
        "CASEID", "VEHNO", "EVENTNO", "DVTOTAL", "DVBASIS", "CDCPLANE",
    ])
    edrcollect = _read(yp, "edrcollect", usecols=[
        "CASEID", "VEHNO", "EDROBTAINED", "EDRMETHOD",
    ])
    edrevent = _read(yp, "edrevent", usecols=[
        "CASEID", "VEHNO", "EDRSUMMNO", "EDREVENTNO",
        "MAXDVLONG", "MAXDVLAT", "CDCEVENT",
    ])
    crash = _read(yp, "crash", usecols=[
        "CASEID", "CRASHYEAR", "PSU", "CASENO", "CASENUMBER", "VEHICLES",
    ])

    if not event.empty and "VEHNUM" in event.columns:
        event = event.rename(columns={"VEHNUM": "VEHNO"})

    for df in [gv, event, cdc, edrcollect, edrevent, crash]:
        if df.empty:
            continue
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = decode_column(df[col])

    return {
        "gv": gv,
        "event": event,
        "cdc": cdc,
        "edrcollect": edrcollect,
        "edrevent": edrevent,
        "crash": crash,
    }


# ---------------------------------------------------------------------------
# Delta-V helpers
# ---------------------------------------------------------------------------

def _clean_component(val) -> float | None:
    """Return float value or None if sentinel/invalid."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return None if f in EDR_SENTINEL else f


def _resultant(long_val, lat_val) -> float | None:
    """
    Compute resultant from two EDR components, handling sentinels per-component.
    Both sentinel -> None. One sentinel -> use the other alone. Neither -> Pythagorean.
    Returns value in km/h (caller converts to mph).
    """
    lng = _clean_component(long_val)
    lat = _clean_component(lat_val)

    if lng is None and lat is None:
        return None
    if lng is None:
        return abs(lat)
    if lat is None:
        return abs(lng)
    return math.sqrt(lng ** 2 + lat ** 2)


def get_cdc_dv_mph(caseid, vehno, cdc: pd.DataFrame,
                   damage_plane: str | None = None):
    """
    Return (cdc_dv_mph, cdc_eventno) for the highest valid CDC delta-V.
    When damage_plane is provided, filters to CDC rows where CDCPLANE matches
    the searched plane so multi-event vehicles return the correct contact DV.
    Excludes 999 sentinel. Converts km/h -> mph.
    Returns (None, None) if unavailable.
    """
    if cdc.empty:
        return None, None
    rows = cdc[(cdc["CASEID"] == caseid) & (cdc["VEHNO"] == vehno)].copy()
    if rows.empty:
        return None, None

    # Filter to the matching damage plane when specified
    if damage_plane is not None and "CDCPLANE" in rows.columns:
        dp = damage_plane.upper()
        rows["CDCPLANE"] = decode_column(rows["CDCPLANE"].astype(str))
        plane_rows = rows[rows["CDCPLANE"] == dp]
        # Only apply the plane filter if it returns results — some vehicles may
        # have CDC data but CDCPLANE not coded, so fall back to all rows
        if not plane_rows.empty:
            rows = plane_rows

    rows["DVTOTAL"] = pd.to_numeric(rows["DVTOTAL"], errors="coerce")
    rows = rows[rows["DVTOTAL"].notna() & (rows["DVTOTAL"] != 999)]
    if rows.empty:
        return None, None
    idx = rows["DVTOTAL"].idxmax()
    best_row = rows.loc[idx]
    return float(best_row["DVTOTAL"]) * KMH_TO_MPH, best_row["EVENTNO"]


def get_edr_dv_mph(caseid, vehno, edrcollect: pd.DataFrame,
                   edrevent: pd.DataFrame, cdc_eventno,
                   damage_plane: str | None):
    """
    Return (edr_dv_mph, edr_note) for a vehicle.

    EDROBTAINED == 2  -> 5.0 mph, "EDR: No event recorded (<5 mph)"
    EDROBTAINED == 1:
      Single event:
        CDCEVENT in 1-30 or 95 -> resultant, "EDR: Confirmed event"
        CDCEVENT 97 or 99       -> resultant, "EDR: Single event, relatedness
                                   uncertain — verify on CrashViewer"
      Multiple events:
        damage_plane provided   -> match by cdc_eventno; if none match,
                                   (NaN, "EDR: No matching event")
        damage_plane is None    -> (NaN, "EDR: Multiple events — verify on CrashViewer")
    Not obtained / other        -> (None, None)

    Components of 888 or 997 are treated as missing per-component.
    All returned DV values are in mph.
    """
    if edrcollect.empty:
        return None, None

    row = edrcollect[
        (edrcollect["CASEID"] == caseid) & (edrcollect["VEHNO"] == vehno)
    ]
    if row.empty:
        return None, None

    obtained = row.iloc[0]["EDROBTAINED"]
    try:
        obtained = int(obtained)
    except (TypeError, ValueError):
        return None, None

    if obtained == 2:
        return 5.0, "EDR: No event recorded (<5 mph)"

    if obtained != 1:
        return None, None

    if edrevent.empty:
        return None, None

    events = edrevent[
        (edrevent["CASEID"] == caseid) & (edrevent["VEHNO"] == vehno)
    ].copy()
    if events.empty:
        return None, None

    events["CDCEVENT"] = pd.to_numeric(events["CDCEVENT"], errors="coerce")

    # ---- Single event ----
    if len(events) == 1:
        ev = events.iloc[0]
        r = _resultant(ev["MAXDVLONG"], ev["MAXDVLAT"])
        if r is None:
            return None, None
        dv_mph = r * KMH_TO_MPH
        try:
            cdcevent_int = int(ev["CDCEVENT"])
        except (TypeError, ValueError):
            cdcevent_int = None

        if cdcevent_int in CDCEVENT_RELATED:
            return round(dv_mph, 1), "EDR: Confirmed event"
        else:
            return round(dv_mph, 1), "EDR: Single event, relatedness uncertain — verify on CrashViewer"

    # ---- Multiple events ----
    if damage_plane is None:
        return None, "EDR: Multiple events — verify on CrashViewer"

    if cdc_eventno is not None:
        try:
            cdc_eventno_int = int(cdc_eventno)
        except (TypeError, ValueError):
            cdc_eventno_int = None

        if cdc_eventno_int is not None:
            matched = events[events["CDCEVENT"] == cdc_eventno_int]
            if not matched.empty:
                resultants = matched.apply(
                    lambda r: _resultant(r["MAXDVLONG"], r["MAXDVLAT"]), axis=1
                ).dropna()
                if not resultants.empty:
                    return round(float(resultants.max()) * KMH_TO_MPH, 1), "EDR: Matched to CDC event"

    return None, "EDR: No matching event"


# ---------------------------------------------------------------------------
# Vehicle contact filter helper
# ---------------------------------------------------------------------------

def _vehicle_contact_caseids(event: pd.DataFrame, year: int,
                              damage_plane: str) -> set:
    """
    Return a set of (CASEID, VEHNO) tuples where the damage-plane contact
    was with another vehicle.

    2017-2023: OBJCONT in 1-30 on the matching event row
    2024+    : OBJCLASS == 1 on the matching event row
    """
    if event.empty:
        return set()

    dp = damage_plane.upper()

    # Rows where this vehicle is the primary contact with the damage plane
    primary = event[event["GAD1"] == dp].copy()
    # Rows where this vehicle is the contacted vehicle for the damage plane
    contacted = event[event["GAD2"] == dp].copy()

    valid_pairs = set()

    if year in OBJCONT_YEARS:
        # OBJCONT 1-30 means the contacted object is a vehicle
        if "OBJCONT" in primary.columns:
            primary["OBJCONT"] = pd.to_numeric(primary["OBJCONT"], errors="coerce")
            veh_primary = primary[primary["OBJCONT"].between(1, 30)]
            for _, row in veh_primary.iterrows():
                valid_pairs.add((row["CASEID"], row["VEHNO"]))

        # For contacted vehicle rows: the primary vehicle (VEHNO) contacted
        # this vehicle, so OBJCONT on the primary side is 1-30 — already
        # captured above. But we also need to add the contacted vehicle itself.
        if "OBJCONT" in event.columns:
            event["OBJCONT"] = pd.to_numeric(event["OBJCONT"], errors="coerce")
            contacted_rows = event[
                (event["GAD2"] == dp) &
                event["OBJCONT"].between(1, 30)
            ]
            for _, row in contacted_rows.iterrows():
                # The contacted vehicle number is OBJCONT
                try:
                    contacted_vehno = int(row["OBJCONT"])
                    valid_pairs.add((row["CASEID"], contacted_vehno))
                except (TypeError, ValueError):
                    pass

    elif year in OBJCLASS_YEARS:
        # OBJCLASS == 1 means the contacted object is a vehicle
        if "OBJCLASS" in primary.columns:
            primary["OBJCLASS"] = pd.to_numeric(primary["OBJCLASS"], errors="coerce")
            veh_primary = primary[primary["OBJCLASS"] == 1]
            for _, row in veh_primary.iterrows():
                valid_pairs.add((row["CASEID"], row["VEHNO"]))

        if "OBJCLASS" in event.columns:
            event["OBJCLASS"] = pd.to_numeric(event["OBJCLASS"], errors="coerce")
            contacted_rows = event[
                (event["GAD2"] == dp) &
                (event["OBJCLASS"] == 1)
            ]
            for _, row in contacted_rows.iterrows():
                if "OBJCONT" in row and pd.notna(row["OBJCONT"]):
                    try:
                        contacted_vehno = int(row["OBJCONT"])
                        valid_pairs.add((row["CASEID"], contacted_vehno))
                    except (TypeError, ValueError):
                        pass

    return valid_pairs


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def search_ciss(
    make_code: int,
    model_code: int | None,
    modelyr_min: int | None,
    modelyr_max: int | None,
    damage_plane: str | None,
    dv_min: float | None,
    dv_max: float | None,
    vehicle_contact_only: bool = False,
    years: list[int] | None = None,
) -> pd.DataFrame:
    """
    Search CISS data and return matching vehicle records.

    Parameters
    ----------
    make_code            : int   - legacy MAKE numeric code (e.g. 49 = Toyota)
    model_code           : int | None - legacy MODEL code; None = all models
    modelyr_min          : int | None - minimum vehicle model year
    modelyr_max          : int | None - maximum vehicle model year
    damage_plane         : str | None - GAD code ('F','B','L','R','T','U'); None = any
    dv_min               : float | None - minimum delta-V (mph); None = no lower bound
    dv_max               : float | None - maximum delta-V (mph); None = no upper bound
    vehicle_contact_only : bool - if True, only include cases where the damage
                                  contact was with another vehicle (ignored if
                                  damage_plane is None)
    years                : list[int] | None - crash years to search; None = all

    Returns
    -------
    pd.DataFrame with columns:
        CASEID, VEHNO, MAKE, MODEL, MODELYR, VIN,
        DAMAGE_PLANE, CDC_DV_MPH, EDR_DV_MPH, EDR_NOTE, CRASHVIEWER_URL

    Cases where both CDC_DV_MPH and EDR_DV_MPH are NaN are excluded.
    dv_min/dv_max filter uses CDC_DV_MPH, falling back to EDR_DV_MPH.
    """
    if years is None:
        years = AVAILABLE_YEARS

    results = []

    for year in years:
        print(f"Searching {year}...")
        tables = load_tables(year)
        gv = tables["gv"]
        event = tables["event"]
        cdc = tables["cdc"]
        edrcollect = tables["edrcollect"]
        edrevent = tables["edrevent"]

        if gv.empty:
            continue

        # ------------------------------------------------------------------
        # Step 1: Filter GV by make, model, and model year
        # ------------------------------------------------------------------
        gv["MAKE"] = pd.to_numeric(gv["MAKE"], errors="coerce")
        mask = gv["MAKE"] == make_code

        if model_code is not None:
            gv["MODEL"] = pd.to_numeric(gv["MODEL"], errors="coerce")
            mask &= gv["MODEL"] == model_code

        if modelyr_min is not None:
            gv["MODELYR"] = pd.to_numeric(gv["MODELYR"], errors="coerce")
            mask &= gv["MODELYR"] >= modelyr_min

        if modelyr_max is not None:
            gv["MODELYR"] = pd.to_numeric(gv["MODELYR"], errors="coerce")
            mask &= gv["MODELYR"] <= modelyr_max

        vehicles = gv[mask].copy()
        if vehicles.empty:
            continue

        # ------------------------------------------------------------------
        # Step 2: Filter by damage plane via event table
        # ------------------------------------------------------------------
        if damage_plane is not None and not event.empty:
            dp = damage_plane.upper()
            event["GAD1"] = decode_column(event["GAD1"].astype(str))
            event["GAD2"] = decode_column(event["GAD2"].astype(str))
            event["OBJCONT"] = pd.to_numeric(event["OBJCONT"], errors="coerce") \
                if "OBJCONT" in event.columns else pd.Series(dtype=float)

            primary_match = event[event["GAD1"] == dp][["CASEID", "VEHNO"]].drop_duplicates()
            contacted_match = event[event["GAD2"] == dp][["CASEID", "OBJCONT"]].rename(
                columns={"OBJCONT": "VEHNO"}
            ).dropna(subset=["VEHNO"])
            contacted_match["VEHNO"] = contacted_match["VEHNO"].astype(int)
            contacted_match = contacted_match.drop_duplicates()

            damage_vehicles = pd.concat([primary_match, contacted_match]).drop_duplicates()
            vehicles = vehicles.merge(damage_vehicles, on=["CASEID", "VEHNO"], how="inner")
            if vehicles.empty:
                continue

            # --------------------------------------------------------------
            # Step 2b: Vehicle contact filter (only when damage_plane set)
            # --------------------------------------------------------------
            if vehicle_contact_only:
                valid_pairs = _vehicle_contact_caseids(event, year, dp)
                if valid_pairs:
                    keep = vehicles.apply(
                        lambda r: (r["CASEID"], r["VEHNO"]) in valid_pairs, axis=1
                    )
                    vehicles = vehicles[keep]
                    if vehicles.empty:
                        continue

        # ------------------------------------------------------------------
        # Step 3: Compute CDC and EDR delta-V in mph
        # ------------------------------------------------------------------
        cdc_dvs = []
        edr_dvs = []
        edr_notes = []

        for _, vrow in vehicles.iterrows():
            caseid = vrow["CASEID"]
            vehno = vrow["VEHNO"]

            cdc_dv, cdc_eventno = get_cdc_dv_mph(caseid, vehno, cdc, damage_plane)
            edr_dv, edr_note = get_edr_dv_mph(
                caseid, vehno, edrcollect, edrevent, cdc_eventno, damage_plane
            )

            cdc_dvs.append(round(cdc_dv, 1) if cdc_dv is not None else None)
            edr_dvs.append(edr_dv)
            edr_notes.append(edr_note)

        vehicles = vehicles.copy()
        vehicles["CDC_DV_MPH"] = cdc_dvs
        vehicles["EDR_DV_MPH"] = edr_dvs
        vehicles["EDR_NOTE"] = edr_notes

        # Exclude cases where both DV values are unavailable
        has_any_dv = vehicles["CDC_DV_MPH"].notna() | vehicles["EDR_DV_MPH"].notna()
        vehicles = vehicles[has_any_dv]
        if vehicles.empty:
            continue

        # Apply optional delta-V range filter (CDC preferred, EDR fallback)
        if dv_min is not None or dv_max is not None:
            _cdc = vehicles["CDC_DV_MPH"].astype(float)
            _edr = vehicles["EDR_DV_MPH"].astype(float)
            best_for_filter = _cdc.combine_first(_edr)
            dv_mask = best_for_filter.notna()
            if dv_min is not None:
                dv_mask &= best_for_filter >= dv_min
            if dv_max is not None:
                dv_mask &= best_for_filter <= dv_max
            vehicles = vehicles[dv_mask]
            if vehicles.empty:
                continue

        # ------------------------------------------------------------------
        # Step 4: Clean up types, attach damage plane and CrashViewer URL
        # ------------------------------------------------------------------
        for col in ["CASEID", "VEHNO", "MAKE", "MODEL", "MODELYR"]:
            if col in vehicles.columns:
                vehicles[col] = pd.to_numeric(vehicles[col], errors="coerce").astype("Int64")

        vehicles["DAMAGE_PLANE"] = damage_plane if damage_plane else "Any"
        vehicles["CRASHVIEWER_URL"] = vehicles["CASEID"].apply(
            lambda c: CRASHVIEWER_URL.format(int(c))
        )

        results.append(vehicles[[
            "CASEID", "VEHNO", "MAKE", "MODEL", "MODELYR", "VIN",
            "DAMAGE_PLANE", "CDC_DV_MPH", "EDR_DV_MPH", "EDR_NOTE", "CRASHVIEWER_URL",
        ]])

    if not results:
        return pd.DataFrame(columns=[
            "CASEID", "VEHNO", "MAKE", "MODEL", "MODELYR", "VIN",
            "DAMAGE_PLANE", "CDC_DV_MPH", "EDR_DV_MPH", "EDR_NOTE", "CRASHVIEWER_URL",
        ])

    results = [r for r in results if not r.empty]
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame(columns=[
        "CASEID", "VEHNO", "MAKE", "MODEL", "MODELYR", "VIN",
        "DAMAGE_PLANE", "CDC_DV_MPH", "EDR_DV_MPH", "EDR_NOTE", "CRASHVIEWER_URL",
    ])


# ---------------------------------------------------------------------------
# Quick CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test without vehicle contact filter
    print("=== Without vehicle contact filter ===")
    df = search_ciss(
        make_code=49,
        model_code=402,
        modelyr_min=None,
        modelyr_max=None,
        damage_plane="F",
        dv_min=None,
        dv_max=None,
        vehicle_contact_only=False,
        years=[2024],
    )
    print(f"Results: {len(df)}")

    # Test with vehicle contact filter
    print("\n=== With vehicle contact filter ===")
    df2 = search_ciss(
        make_code=49,
        model_code=402,
        modelyr_min=None,
        modelyr_max=None,
        damage_plane="F",
        dv_min=None,
        dv_max=None,
        vehicle_contact_only=True,
        years=[2024],
    )
    print(f"Results: {len(df2)}")
    if not df2.empty:
        print(df2[[
            "CASEID", "MODELYR", "CDC_DV_MPH", "EDR_DV_MPH", "EDR_NOTE", "CRASHVIEWER_URL"
        ]].to_string(index=False))
