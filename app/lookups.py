import re
import os

# ============================================================
# LOOKUPS.PY
# Parses FORMAT24.sas to build make and model decode
# dictionaries. This file is imported by search.py and
# eventually by the Streamlit UI.
# ============================================================

# Path to the format file - we search all year folders
# and use the most recent one found
DATA_DIR = r"C:\Users\andyd\Documents\ciss-tool\data"


def find_format_file():
    """
    Searches all CISS year folders for a FORMAT .sas file
    and returns the path to the most recent one found.
    This means if NHTSA updates the format file in a new
    year's data release, we automatically use the latest.
    """
    format_path = None
    for year in range(2017, 2026):
        candidate = os.path.join(
            DATA_DIR,
            f"CISS_{year}_SAS_files",
            f"FORMAT{str(year)[2:]}.sas"
        )
        if os.path.exists(candidate):
            format_path = candidate

    if format_path is None:
        raise FileNotFoundError(
            "Could not find a FORMAT .sas file in any CISS year folder."
        )

    print(f"Using format file: {format_path}")
    return format_path


def parse_format_block(content, block_name, end_block_name=None):
    """
    Extracts a dictionary of {code: label} from a named
    VALUE block in a SAS format file.

    Parameters:
        content        : full text content of the .sas file
        block_name     : name of the VALUE block to parse
                         e.g. 'VPICMAKE24F'
        end_block_name : name of the next block to stop at
                         if None, reads to end of file

    Returns:
        dict of {int_code: label_string}
    """
    start = content.find(f'VALUE {block_name}')
    if start == -1:
        print(f"Warning: block {block_name} not found in format file")
        return {}

    if end_block_name:
        end = content.find(f'VALUE {end_block_name}', start)
        block = content[start:end]
    else:
        block = content[start:]

    # Match lines like: 2469='Camry'
    # re.MULTILINE makes ^ match start of each line
    pattern = re.compile(r"^(\d+)='(.+)'", re.MULTILINE)
    result = {}
    for match in pattern.finditer(block):
        code  = int(match.group(1))
        label = match.group(2).strip()
        result[code] = label

    return result


def parse_make24f(content):
    """
    Parses the MAKE24F block - these are the NHTSA legacy
    make codes used in the MAKE column of the GV table.
    e.g. 49 = Toyota, 12 = Ford
    """
    return parse_format_block(content, 'MAKE24F', 'MANCOLL24F')


def parse_vpicmake(content):
    """
    Parses the VPICMAKE24F block - VPIC make codes used
    in the VPICMAKE column of the GV table.
    These are more granular than MAKE24F.
    """
    return parse_format_block(content, 'VPICMAKE24F', 'VPICMODEL24F')


def parse_vpicmodel(content):
    """
    Parses the VPICMODEL24F block - VPIC model codes used
    in the VPICMODEL column of the GV table.
    e.g. 2469 = Camry, 2217 = RAV4
    Runs to end of file.
    """
    return parse_format_block(content, 'VPICMODEL24F', None)


def build_lookups():
    """
    Main function that loads the format file and builds
    all lookup dictionaries needed by the application.

    Returns a dict containing:
        'make24f'    : {code: label} for MAKE column
        'vpic_makes' : {code: label} for VPICMAKE column
        'vpic_models': {code: label} for VPICMODEL column
        'damage_plane: {code: label} for GAD/DAMPLANE
    """
    format_path = find_format_file()

    with open(format_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    lookups = {}
    lookups['make24f']     = parse_make24f(content)
    lookups['vpic_makes']  = parse_vpicmake(content)
    lookups['vpic_models'] = parse_vpicmodel(content)

    # Damage plane codes - these are fixed GAD values
    # from the $GAD24F format block we read earlier
    lookups['damage_plane'] = {
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

    print(f"Lookups built successfully:")
    print(f"  MAKE24F entries:    {len(lookups['make24f'])}")
    print(f"  VPICMAKE entries:   {len(lookups['vpic_makes'])}")
    print(f"  VPICMODEL entries:  {len(lookups['vpic_models'])}")
    print(f"  Damage plane codes: {len(lookups['damage_plane'])}")

    return lookups


# ============================================================
# DROPDOWN POPULATION FUNCTIONS
# These are called by the Streamlit UI to populate menus
# ============================================================

def get_makes_in_data(all_tables, lookups):
    """
    Returns a sorted dict of {make_code: make_label} for
    only the makes that actually appear in our loaded data.
    Uses VPICMAKE column and vpic_makes lookup.
    Filters out unknown/null values.
    """
    make_codes = set()
    for year, tables in all_tables.items():
        codes = tables['gv']['VPICMAKE'].dropna().unique()
        make_codes.update(codes)

    makes = {}
    for code in make_codes:
        code_int = int(code)
        label = lookups['vpic_makes'].get(
            code_int, f"Make Code {code_int}"
        )
        # Skip placeholder/unknown codes
        if 'unknown' in label.lower():
            continue
        makes[code_int] = label

    # Sort alphabetically by label
    return dict(sorted(makes.items(), key=lambda x: x[1]))


def get_models_in_data(all_tables, lookups, vpic_make_code):
    """
    Returns a sorted list of model name strings for a given
    VPICMAKE code, drawn only from models that actually
    appear in our loaded data.
    """
    model_codes = set()
    for year, tables in all_tables.items():
        gv = tables['gv']
        subset = gv[
            gv['VPICMAKE'] == float(vpic_make_code)
        ]['VPICMODEL'].dropna()
        model_codes.update(subset.unique())

    models = {}
    for code in model_codes:
        code_int = int(code)
        label = lookups['vpic_models'].get(
            code_int, f"Model Code {code_int}"
        )
        if 'unknown' in label.lower():
            continue
        models[code_int] = label

    # Sort alphabetically by label, return as list of
    # (code, label) tuples so UI can use either
    return sorted(models.items(), key=lambda x: x[1])


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    lookups = build_lookups()

    print("\nSample MAKE24F entries:")
    for code, label in list(lookups['make24f'].items())[:5]:
        print(f"  {code}: {label}")

    print("\nSample VPICMAKE entries:")
    for code, label in list(lookups['vpic_makes'].items())[:5]:
        print(f"  {code}: {label}")

    print("\nToyota VPIC models (sample):")
    toyota_models = [
        (c, l) for c, l in lookups['vpic_models'].items()
        if c in [2469, 2217, 2213, 2467, 2208, 2465, 2468]
    ]
    for code, label in toyota_models:
        print(f"  {code}: {label}")