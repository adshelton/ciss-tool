import pandas as pd
import os
import numpy as np

# ============================================================
# CONFIGURATION
# ============================================================
DATA_DIR = r"C:\Users\andyd\Documents\ciss-tool\data"

# Damage plane codes from FORMAT24.sas
# We'll use these to build our dropdown later
DAMAGE_PLANE_LABELS = {
    'F': 'Front',
    'B': 'Back',
    'L': 'Left',
    'R': 'Right',
    'T': 'Top',
    'U': 'Undercarriage',
    'N': 'Noncollision',
    '9': 'Unknown',
    '0': 'Not a motor vehicle'
}

# MAKE codes from FORMAT24.sas - most common makes for dropdown
MAKE_LABELS = {
    6:  'Chrysler',
    7:  'Dodge',
    12: 'Ford',
    13: 'Lincoln',
    18: 'Buick',
    19: 'Cadillac',
    20: 'Chevrolet',
    22: 'Pontiac',
    23: 'GMC',
    24: 'Saturn',
    30: 'Volkswagen',
    32: 'Audi',
    34: 'BMW',
    35: 'Nissan',
    37: 'Honda',
    38: 'Isuzu',
    39: 'Jaguar',
    41: 'Mazda',
    42: 'Mercedes-Benz',
    45: 'Porsche',
    47: 'Saab',
    48: 'Subaru',
    49: 'Toyota',
    51: 'Volvo',
    52: 'Mitsubishi',
    53: 'Suzuki',
    54: 'Acura',
    55: 'Hyundai',
    58: 'Infiniti',
    59: 'Lexus',
    62: 'Land Rover',
    63: 'Kia',
    65: 'Smart',
    67: 'Scion',
    98: 'Other',
    99: 'Unknown'
}


# ============================================================
# DROPDOWN POPULATION FUNCTIONS
# ============================================================

def get_all_makes(all_tables):
    """
    Scans GV tables across all loaded years and returns a
    sorted dictionary of {make_code: make_label} for every
    unique make present in the data.

    'all_tables' is a dictionary of {year: tables} so we can
    scan across all years at once and catch makes that might
    only appear in certain years.
    """
    make_codes = set()  # a set automatically removes duplicates

    for year, tables in all_tables.items():
        # Get every unique MAKE code in this year's GV table
        # dropna() removes any blank/null values
        codes = tables['gv']['MAKE'].dropna().unique()
        make_codes.update(codes)

    # Build a dictionary mapping code -> label
    # If the code exists in our MAKE_LABELS lookup use that label
    # Otherwise fall back to just showing the raw code number
    makes = {}
    for code in sorted(make_codes):
        code_int = int(code)
        label = MAKE_LABELS.get(code_int, f"Make Code {code_int}")
        makes[code_int] = label

    # Sort the final dictionary alphabetically by label
    # so the dropdown reads A-Z instead of by numeric code
    makes_sorted = dict(
        sorted(makes.items(), key=lambda item: item[1])
    )

    return makes_sorted


def get_models_for_make(all_tables, make_code):
    """
    Given a make code, scans GV tables across all loaded years
    and returns a sorted list of every unique model name
    for that make.

    This drives the second dropdown - once a user picks a make,
    we call this to populate the model options.
    """
    models = set()

    for year, tables in all_tables.items():
        gv = tables['gv']

        # Filter to just this make, then get unique model values
        # We also decode any byte strings and strip whitespace
        make_models = gv[gv['MAKE'] == float(make_code)]['MODEL'].dropna()
        for model in make_models:
            decoded = decode_bytes(model)
            # Skip if the value is a float/number - these are
            # null-like placeholder values, not real model names
            if isinstance(decoded, float):
                continue
            if decoded and decoded.strip():
                models.add(decoded.strip().upper())

    return sorted(list(models))


def get_year_range(all_tables):
    """
    Returns the min and max model years across all loaded data.
    Used to set the bounds of the year range slider in the UI.
    """
    all_years = []

    for year, tables in all_tables.items():
        years = tables['gv']['MODELYR'].dropna()
        all_years.extend(years.tolist())

    return int(min(all_years)), int(max(all_years))

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def decode_bytes(value):
    """
    SAS files store some strings as bytes objects like b'F' or
    b'1-10-2024-001-02'. This function converts them to regular
    strings. If it's already a string or number, it passes
    through unchanged.
    """
    if isinstance(value, bytes):
        return value.decode('utf-8').strip()
    return value


def decode_column(series):
    """
    Applies decode_bytes to an entire DataFrame column at once.
    'series' is what pandas calls a single column.
    """
    return series.apply(decode_bytes)


# ============================================================
# DATA LOADING
# ============================================================

def get_year_path(year):
    return os.path.join(DATA_DIR, f"CISS_{year}_SAS_files")


def load_tables(year):
    """
    Loads all needed tables for a given year and decodes
    byte-string columns automatically.
    """
    path = get_year_path(year)
    print(f"Loading {year} data...")

    tables = {}
    tables['gv']         = pd.read_sas(os.path.join(path, 'gv.sas7bdat'))
    tables['event']      = pd.read_sas(os.path.join(path, 'event.sas7bdat'))
    tables['cdc']        = pd.read_sas(os.path.join(path, 'cdc.sas7bdat'))
    tables['edrcollect'] = pd.read_sas(os.path.join(path, 'edrcollect.sas7bdat'))
    tables['edrevent']   = pd.read_sas(os.path.join(path, 'edrevent.sas7bdat'))

    # Decode byte string columns in each table
    # The event table uses VEHNUM instead of VEHNO - we rename
    # it here so all tables use the same name for easier joining
    tables['event'] = tables['event'].rename(columns={'VEHNUM': 'VEHNO'})

    # Decode GAD1 and GAD2 in event table
    tables['event']['GAD1'] = decode_column(tables['event']['GAD1'])
    tables['event']['GAD2'] = decode_column(tables['event']['GAD2'])

    # Decode VIN and CASENUMBER in gv table
    tables['gv']['VIN']        = decode_column(tables['gv']['VIN'])
    tables['gv']['CASENUMBER'] = decode_column(tables['gv']['CASENUMBER'])

    return tables


# ============================================================
# DELTA-V CALCULATION
# ============================================================

def compute_edr_resultant(maxdvlong, maxdvlat):
    """
    EDR events only report lateral and longitudinal delta-V
    components separately. This function computes the resultant
    (total) delta-V using the Pythagorean theorem:
    
        resultant = sqrt(long^2 + lat^2)
    
    Both inputs can be negative (direction matters for components)
    but the resultant is always a positive absolute value.
    """
    return np.sqrt(maxdvlong**2 + maxdvlat**2)


# ============================================================
# MAIN SEARCH FUNCTION
# ============================================================

def search_ciss(tables, make, model, year_min, year_max,
                damage_plane, dv_min, dv_max):
    """
    Searches loaded CISS tables and returns matching cases.

    Parameters:
        tables      : dict of DataFrames from load_tables()
        make        : int, MAKE code (e.g. 49 for Toyota)
        model       : str, model name to search (e.g. 'CAMRY')
        year_min    : int, earliest model year (e.g. 2018)
        year_max    : int, latest model year (e.g. 2022)
        damage_plane: str, GAD code (e.g. 'F' for Front)
        dv_min      : float, minimum delta-V in search range
        dv_max      : float, maximum delta-V in search range

    Returns:
        DataFrame of matching cases sorted by delta-V
    """

    # --- STEP 1: Filter GV table ---
    # Start with the vehicle table and apply make/model/year filters
    # The '&' means AND - all conditions must be true
    # The '|' means OR - we'll use that later
    gv = tables['gv']

    gv_filtered = gv[
        (gv['MAKE']    == make) &
        (gv['MODEL'].str.upper().str.contains(model.upper(), na=False)) &
        (gv['MODELYR'] >= year_min) &
        (gv['MODELYR'] <= year_max)
    ][['CASEID', 'VEHNO', 'MAKE', 'MODEL', 'MODELYR', 'VIN']].copy()

    print(f"  Step 1 - GV filter: {len(gv_filtered)} vehicles match "
          f"make/model/year")

    if gv_filtered.empty:
        print("  No vehicles found matching make/model/year criteria.")
        return pd.DataFrame()


    # --- STEP 2: Filter EVENT table by damage plane ---
    # A vehicle can appear in the event table in TWO ways:
    #
    # WAY 1: As VEHNUM (the first vehicle in the event)
    #        → damage plane is stored in GAD1
    #
    # WAY 2: As the contacted vehicle (OBJCONT codes 1-30)
    #        → damage plane is stored in GAD2
    #
    # We need to capture BOTH scenarios so we don't miss
    # cases where our subject vehicle is in the second position

    event = tables['event']

    # Way 1: subject vehicle is VEHNUM, check GAD1
    way1 = event[
        event['GAD1'] == damage_plane
    ][['CASEID', 'VEHNUM', 'GAD1']].copy()
    way1 = way1.rename(columns={'VEHNUM': 'VEHNO', 'GAD1': 'MATCHED_GAD'})

    # Way 2: subject vehicle is OBJCONT (values 1-30 = vehicle numbers)
    # check GAD2 for the damage plane
    way2 = event[
        (event['OBJCONT'].between(1, 30)) &
        (event['GAD2'] == damage_plane)
    ][['CASEID', 'OBJCONT', 'GAD2']].copy()
    way2 = way2.rename(columns={
        'OBJCONT': 'VEHNO',
        'GAD2': 'MATCHED_GAD'
    })

    # Combine both and drop any duplicate CASEID/VEHNO pairs
    # (a vehicle could theoretically match both ways in
    # different events within the same crash)
    event_filtered = pd.concat([way1, way2], ignore_index=True)
    event_filtered = event_filtered.drop_duplicates(
        subset=['CASEID', 'VEHNO']
    )

    print(f"  Step 2 - Event filter: {len(event_filtered)} vehicles "
          f"match damage plane '{damage_plane}' "
          f"(Way1: {len(way1)}, Way2: {len(way2)})")


    # --- STEP 3: Join GV results with EVENT results ---
    # 'merge' is pandas' way of joining two tables together
    # 'on' specifies the columns to match on
    # 'inner' means only keep rows that exist in BOTH tables
    matched = gv_filtered.merge(
        event_filtered,
        on=['CASEID', 'VEHNO'],
        how='inner'
    )

    print(f"  Step 3 - After joining GV + Event: {len(matched)} matches")

    if matched.empty:
        return pd.DataFrame()


    # --- STEP 4: Get CDC delta-V ---
    # CDC table has DVTOTAL - the reconstructed resultant delta-V
    # DVBASIS tells us how it was calculated
    # We keep only the columns we need
    cdc = tables['cdc'][
        ['CASEID', 'VEHNO', 'DVTOTAL', 'DVBASIS', 'CDCPLANE']
    ].copy()

    # Rename DVTOTAL so we know it came from CDC
    cdc = cdc.rename(columns={'DVTOTAL': 'CDC_DV'})

    # Take the maximum CDC delta-V per vehicle in case there
    # are multiple CDC events for the same vehicle
    cdc_max = cdc.groupby(
        ['CASEID', 'VEHNO']
    )['CDC_DV'].max().reset_index()


    # --- STEP 5: Get EDR delta-V ---
    # First check if EDR was obtained (EDROBTAINED = 1 or 2)
    edrcollect = tables['edrcollect']

    edr_valid = edrcollect[
        edrcollect['EDROBTAINED'].isin([1.0, 2.0])
    ][['CASEID', 'VEHNO', 'EDROBTAINED']].copy()

    # For EDROBTAINED = 2 (collected, no event = under 5 mph)
    # we assign a delta-V of 0 as a placeholder
    # For EDROBTAINED = 1 we get the actual value from edrevent
    edrevent = tables['edrevent'].copy()

    # Compute EDR resultant delta-V from components
    edrevent['EDR_DV'] = compute_edr_resultant(
        edrevent['MAXDVLONG'],
        edrevent['MAXDVLAT']
    )

    # Take maximum EDR delta-V per vehicle across all events
    edr_max = edrevent.groupby(
        ['CASEID', 'VEHNO']
    )['EDR_DV'].max().reset_index()

    # Join EDR collection status with EDR event values
    edr_combined = edr_valid.merge(
        edr_max,
        on=['CASEID', 'VEHNO'],
        how='left'  # left keeps all valid EDR rows even if
                    # no matching event (EDROBTAINED=2 case)
    )

    # Where EDROBTAINED=2 (no event recorded), fill EDR_DV with 0
    edr_combined['EDR_DV'] = edr_combined['EDR_DV'].fillna(0)


    # --- STEP 6: Join delta-V data onto matched vehicles ---
    # Left join keeps all matched vehicles even if no CDC or EDR
    matched = matched.merge(cdc_max,  on=['CASEID', 'VEHNO'], how='left')
    matched = matched.merge(
        edr_combined[['CASEID', 'VEHNO', 'EDROBTAINED', 'EDR_DV']],
        on=['CASEID', 'VEHNO'],
        how='left'
    )


    # --- STEP 7: Filter - must have CDC or valid EDR delta-V ---
    # A vehicle qualifies if it has EITHER:
    #   - A CDC delta-V value (not null)
    #   - An EDR with EDROBTAINED of 1 or 2
    has_cdc = matched['CDC_DV'].notna()
    has_edr = matched['EDROBTAINED'].isin([1.0, 2.0])

    matched = matched[has_cdc | has_edr].copy()

    print(f"  Step 4-7 - After delta-V filter: {len(matched)} matches "
          f"have CDC or EDR data")

    if matched.empty:
        return pd.DataFrame()


    # --- STEP 8: Compute best available delta-V for ranging ---
    # We prefer CDC_DV if available, otherwise use EDR_DV
    # This gives us one delta-V value per row to filter against
    matched['BEST_DV'] = matched['CDC_DV'].combine_first(
        matched['EDR_DV']
    )

    # --- STEP 9: Apply delta-V range filter ---
    matched = matched[
        (matched['BEST_DV'] >= dv_min) &
        (matched['BEST_DV'] <= dv_max)
    ].copy()

    print(f"  Step 9 - After delta-V range filter: {len(matched)} "
          f"matches within {dv_min}-{dv_max} mph")

    if matched.empty:
        return pd.DataFrame()


    # --- STEP 10: Add CrashViewer hyperlink ---
    # The CISS CrashViewer URL pattern takes a CaseID
    # We'll build a clickable link for each result
    matched['CRASHVIEWER_URL'] = matched['CASEID'].apply(
        lambda x: f"https://crashviewer.nhtsa.dot.gov/CISS/{int(x)}"
    )


    # --- STEP 11: Sort by BEST_DV ascending ---
    matched = matched.sort_values('BEST_DV').reset_index(drop=True)


    # --- STEP 12: Return clean final columns ---
    return matched[[
        'CASEID', 'VEHNO', 'MAKE', 'MODEL', 'MODELYR',
        'VIN', 'GAD1', 'CDC_DV', 'EDR_DV', 'EDROBTAINED',
        'BEST_DV', 'CRASHVIEWER_URL'
    ]]


# ============================================================
# TEST RUN
# ============================================================
if __name__ == "__main__":

    # Load all years into one dictionary
    # This is the structure our dropdown functions expect
    print("Loading all years...")
    all_tables = {}
    for year in range(2017, 2025):
        try:
            all_tables[year] = load_tables(year)
        except Exception as e:
            print(f"  Could not load {year}: {e}")

    # Test the make dropdown
    print("\nBuilding make dropdown...")
    makes = get_all_makes(all_tables)
    print(f"Total unique makes found: {len(makes)}")
    print("\nFirst 10 makes (alphabetical):")
    for code, label in list(makes.items())[:10]:
        print(f"  {code}: {label}")

    # Test the model dropdown for Toyota (code 49)
    print("\nModels available for Toyota (code 49):")
    toyota_models = get_models_for_make(all_tables, 49)
    print(toyota_models)

    # Test year range
    yr_min, yr_max = get_year_range(all_tables)
    print(f"\nModel year range across all data: {yr_min} - {yr_max}")