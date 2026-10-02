"""
vehicle_index.py — Make/Model index built from NHTSA VIN-decode files

Each CISS year folder contains a VIN-decode CSV with one row per vehicle:
  - 2017-2019: VINDERIVED.CSV
  - 2020+    : VPICDECODE.csv
Both have CASEID, VEHNO, Make and Model columns, so CASEID + VEHNO joins
directly to the GV table.

The raw text is not perfectly consistent across years (e.g. 'PRIUS' vs
'Prius', '4-Runner' vs '4Runner', 'HARLEY DAVIDSON' vs 'HARLEY-DAVIDSON').
Names are grouped on a normalized key (uppercase, letters and digits only)
and each group is shown under a single display name.
"""

import glob
import os
import re
from functools import lru_cache

import pandas as pd

# Kept independent of search.py (which imports this module)
DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
AVAILABLE_YEARS = list(range(2017, 2025))  # 2017-2024


def get_year_path(year: int) -> str:
    return os.path.join(DATA_ROOT, f"CISS_{year}_SAS_files")

# Manual model merges, for different names that refer to the same vehicle and
# should be searched together. Keyed by (make key, model key) as produced by
# _norm_key; values are (target model key, display name). Add entries here.
MODEL_ALIASES = {
    ("DODGE", "CARAVAN"):             ("GRANDCARAVAN", "Caravan/Grand Caravan"),
    ("DODGE", "CARAVANGRANDCARAVAN"): ("GRANDCARAVAN", "Caravan/Grand Caravan"),
    ("DODGE", "GRANDCARAVAN"):        ("GRANDCARAVAN", "Caravan/Grand Caravan"),
}

# File names NHTSA has used for the VIN-decode table, in order of preference
VIN_DECODE_FILES = ["VPICDECODE.csv", "VINDERIVED.CSV"]


def _norm_key(value: str) -> str:
    """Grouping key: uppercase, letters and digits only."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _find_vin_decode_file(year: int) -> str | None:
    """Return the VIN-decode CSV path for a year, matching names case-insensitively."""
    year_path = get_year_path(year)
    files = {os.path.basename(p).lower(): p for p in glob.glob(os.path.join(year_path, "*"))}
    for name in VIN_DECODE_FILES:
        if name.lower() in files:
            return files[name.lower()]
    return None


def _pick_display_name(spellings: pd.Series) -> str:
    """
    Choose one display name for a group of equivalent spellings.
    Prefers mixed-case spellings over ALL CAPS (e.g. 'Prius' over 'PRIUS'),
    then the most frequent spelling.
    """
    counts = spellings.value_counts()
    mixed = [s for s in counts.index if s != s.upper()]
    return mixed[0] if mixed else counts.index[0]


def load_vehicle_index(years: list[int] | None = None) -> pd.DataFrame:
    """
    One row per vehicle across all years.

    Returns
    -------
    pd.DataFrame with columns:
        YEAR, CASEID, VEHNO, MAKE_KEY, MODEL_KEY, MAKE_NAME, MODEL_NAME
    MAKE_KEY / MODEL_KEY are the normalized keys used for matching;
    MAKE_NAME / MODEL_NAME are the cleaned display names.
    Vehicles with a blank Make or Model keep an empty key/name.
    """
    if years is None:
        years = AVAILABLE_YEARS

    frames = []
    for year in years:
        path = _find_vin_decode_file(year)
        if path is None:
            print(f"  Warning: no VIN-decode CSV found for {year}")
            continue
        df = pd.read_csv(
            path,
            usecols=["CASEID", "VEHNO", "Make", "Model"],
            dtype={"Make": str, "Model": str},
            encoding="latin1",
            keep_default_na=False,
        )
        df["YEAR"] = year
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=[
            "YEAR", "CASEID", "VEHNO", "MAKE_KEY", "MODEL_KEY", "MAKE_NAME", "MODEL_NAME",
        ])

    idx = pd.concat(frames, ignore_index=True)
    idx["CASEID"] = pd.to_numeric(idx["CASEID"], errors="coerce").astype("Int64")
    idx["VEHNO"] = pd.to_numeric(idx["VEHNO"], errors="coerce").astype("Int64")
    idx["Make"] = idx["Make"].str.strip()
    idx["Model"] = idx["Model"].str.strip()

    idx["MAKE_KEY"] = idx["Make"].map(_norm_key)
    idx["MODEL_KEY"] = idx["Model"].map(_norm_key)

    # Apply manual merges from MODEL_ALIASES
    alias_display = {}
    for (mk, mo), (target, display) in MODEL_ALIASES.items():
        hit = (idx["MAKE_KEY"] == mk) & (idx["MODEL_KEY"] == mo)
        idx.loc[hit, "MODEL_KEY"] = target
        alias_display[(mk, target)] = display

    # One display name per make, and per (make, model)
    make_names = (
        idx[idx["MAKE_KEY"] != ""]
        .groupby("MAKE_KEY")["Make"].agg(_pick_display_name)
    )
    model_names = (
        idx[(idx["MAKE_KEY"] != "") & (idx["MODEL_KEY"] != "")]
        .groupby(["MAKE_KEY", "MODEL_KEY"])["Model"].agg(_pick_display_name)
    )
    idx["MAKE_NAME"] = idx["MAKE_KEY"].map(make_names).fillna("")
    for key, display in alias_display.items():
        if key in model_names.index:
            model_names.loc[key] = display
    idx["MODEL_NAME"] = [
        model_names.get((mk, mo), "") for mk, mo in zip(idx["MAKE_KEY"], idx["MODEL_KEY"])
    ]

    return idx[["YEAR", "CASEID", "VEHNO", "MAKE_KEY", "MODEL_KEY", "MAKE_NAME", "MODEL_NAME"]]


@lru_cache(maxsize=1)
def get_vehicle_index() -> pd.DataFrame:
    """Full index for all available years, loaded once per process."""
    return load_vehicle_index()


def build_make_model_options(index: pd.DataFrame) -> pd.DataFrame:
    """
    Every unique make/model combination in the index, with a vehicle count.
    Blank makes and models are left out of the dropdown list (vehicles with
    a blank model are still found when searching 'All Models').

    Returns
    -------
    pd.DataFrame with columns: MAKE_KEY, MAKE_NAME, MODEL_KEY, MODEL_NAME, VEHICLES
    sorted by make name, then model name.
    """
    combos = (
        index[(index["MAKE_KEY"] != "") & (index["MODEL_KEY"] != "")]
        .groupby(["MAKE_KEY", "MAKE_NAME", "MODEL_KEY", "MODEL_NAME"], as_index=False)
        .size()
        .rename(columns={"size": "VEHICLES"})
    )
    combos["_m"] = combos["MAKE_NAME"].str.upper()
    combos["_o"] = combos["MODEL_NAME"].str.upper()
    return combos.sort_values(["_m", "_o"]).drop(columns=["_m", "_o"]).reset_index(drop=True)


def get_make_options(options: pd.DataFrame) -> dict:
    """{make display name: make key}, alphabetical."""
    makes = options.drop_duplicates("MAKE_KEY")
    return dict(zip(makes["MAKE_NAME"], makes["MAKE_KEY"]))


def get_model_options(options: pd.DataFrame, make_key: str) -> dict:
    """{model display name: model key} for one make, with 'All Models' first."""
    models = options[options["MAKE_KEY"] == make_key]
    out = {"All Models": None}
    out.update(dict(zip(models["MODEL_NAME"], models["MODEL_KEY"])))
    return out


if __name__ == "__main__":
    index = load_vehicle_index()
    options = build_make_model_options(index)
    print(f"Vehicles indexed: {len(index)}")
    print(f"Makes: {options['MAKE_KEY'].nunique()}   Make/model combinations: {len(options)}")
    toyota = get_model_options(options, "TOYOTA")
    print(f"Toyota models ({len(toyota) - 1}): {list(toyota)[:12]} ...")
