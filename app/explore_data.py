import pandas as pd
import os

# Path to our 2024 SAS files
DATA_PATH = r"C:\Users\andyd\Documents\ciss-tool\data\CISS_2024_SAS_files"

# --- STEP 1: Load the crash table ---
# This is the top-level table, one row per crash case
print("Loading crash table...")
crash = pd.read_sas(os.path.join(DATA_PATH, 'crash.sas7bdat'))

# Show us the shape - how many rows and columns
print(f"Crash table: {crash.shape[0]} rows, {crash.shape[1]} columns")

# Show us all column names
print("\nCrash table columns:")
print(crash.columns.tolist())

# Show us the first 3 rows
print("\nFirst 3 rows:")
print(crash.head(3))

# --- STEP 2: Load the vehicle specs table ---
# This should contain make, model, year
print("\n\nLoading vehspec table...")
vehspec = pd.read_sas(os.path.join(DATA_PATH, 'vehspec.sas7bdat'))

print(f"Vehspec table: {vehspec.shape[0]} rows, {vehspec.shape[1]} columns")
print("\nVehspec columns:")
print(vehspec.columns.tolist())
print("\nFirst 3 rows:")
print(vehspec.head(3))

# --- STEP 3: Load the general vehicle table ---
# This likely contains plane of damage
print("\n\nLoading gv table...")
gv = pd.read_sas(os.path.join(DATA_PATH, 'gv.sas7bdat'))

print(f"GV table: {gv.shape[0]} rows, {gv.shape[1]} columns")
print("\nGV columns:")
print(gv.columns.tolist())
print("\nFirst 3 rows:")
print(gv.head(3))