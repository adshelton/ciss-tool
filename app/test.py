
import re


with open(r'C:\Users\andyd\Documents\ciss-tool\data\CISS_2024_SAS_files\FORMAT24.sas', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

pattern = re.compile(r"^(\d+)='(.+)'", re.MULTILINE)

# Parse VPICMAKE24F
make_start = content.find('VALUE VPICMAKE24F')
make_end = content.find('VALUE VPICMODEL24F')
make_block = content[make_start:make_end]
vpic_makes = {}
for match in pattern.finditer(make_block):
    vpic_makes[int(match.group(1))] = match.group(2)
print(f'VPICMAKE entries parsed: {len(vpic_makes)}')
print('Sample:', list(vpic_makes.items())[:5])

# Parse VPICMODEL24F - runs to end of file
model_start = content.find('VALUE VPICMODEL24F')
model_block = content[model_start:]
vpic_models = {}
for match in pattern.finditer(model_block):
    vpic_models[int(match.group(1))] = match.group(2)
print(f'\nVPICMODEL entries parsed: {len(vpic_models)}')

# Test our known Toyota codes
print('\nToyota model codes:')
for code in [2469, 2217, 2213, 2467, 2208, 2465, 2468]:
    print(f'  {code}: {vpic_models.get(code, "NOT FOUND")}')