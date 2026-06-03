
import re
import json
import os

# Read xsrpst.py file
xsrpst_path = r'd:\auto-xbox\streaming\xsrpst.py'

with open(xsrpst_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("Starting to parse xsrpst.py...")

# Pattern to match schema = [...] blocks
schema_pattern = r'schema\s*=\s*\[([^\]]*)\]'
schemas = []

matches = re.finditer(schema_pattern, content, re.DOTALL)

for match in matches:
    schema_str = match.group(1)
    numbers = re.findall(r'-?\d+', schema_str)
    if numbers and len(numbers) >= 13:
        schema = list(map(int, numbers[:13]))
        schemas.append(schema)

print(f"Found {len(schemas)} scene template configs")

from collections import defaultdict
scene_groups = defaultdict(list)
for schema in schemas:
    scene_id = schema[0]
    scene_groups[scene_id].append(schema)

print(f"\nScene stats:")
print(f"Total scenes: {len(scene_groups)}")
if scene_groups:
    print(f"Scene ID range: {min(scene_groups.keys())} - {max(scene_groups.keys())}")
    
    print(f"\nScene distribution:")
    for scene_id in sorted(scene_groups.keys()):
        count = len(scene_groups[scene_id])
        print(f"  Scene {scene_id}: {count} templates")

output_file = r'd:\auto-xbox\team-management\.trae\documents\full_scene_schemas.json'
os.makedirs(os.path.dirname(output_file), exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(schemas, f, ensure_ascii=False, indent=2)

print(f"\nFull config saved to: {output_file}")

grouped_schemas = {}
for scene_id, scene_schemas in scene_groups.items():
    grouped_schemas[str(scene_id)] = scene_schemas

grouped_file = r'd:\auto-xbox\team-management\.trae\documents\grouped_scene_schemas.json'
with open(grouped_file, 'w', encoding='utf-8') as f:
    json.dump(grouped_schemas, f, ensure_ascii=False, indent=2)

print(f"Grouped config saved to: {grouped_file}")

print("\n" + "="*50)
print("Parsing xsrp.py...")

xsrp_path = r'd:\auto-xbox\streaming\xsrp.py'
with open(xsrp_path, 'r', encoding='utf-8') as f:
    xsrp_content = f.read()

scene_constants = {}
constant_pattern = r'SCENE_ID_([A-Z_]+)\s*=\s*(\d+)'
matches = re.finditer(constant_pattern, xsrp_content)

for match in matches:
    name = match.group(1)
    value = int(match.group(2))
    scene_constants[f'SCENE_ID_{name}'] = value

print(f"Found {len(scene_constants)} scene constants:")
for name, value in sorted(scene_constants.items(), key=lambda x: x[1]):
    print(f"  {name} = {value}")

scene_constants_file = r'd:\auto-xbox\team-management\.trae\documents\scene_constants.json'
with open(scene_constants_file, 'w', encoding='utf-8') as f:
    json.dump(scene_constants, f, ensure_ascii=False, indent=2)

print(f"\nScene constants saved to: {scene_constants_file}")

print("\n" + "="*50)
print("Generating scene descriptions...")

scene_descriptions = {}

desc_pattern = r'#\s*(\d+)\s+([^\n]+)'
desc_matches = re.finditer(desc_pattern, content)

for match in desc_matches:
    scene_id = int(match.group(1))
    desc = match.group(2).strip()
    if scene_id not in scene_descriptions:
        scene_descriptions[scene_id] = desc

print(f"Found {len(scene_descriptions)} scene descriptions")

desc_file = r'd:\auto-xbox\team-management\.trae\documents\scene_descriptions.json'
with open(desc_file, 'w', encoding='utf-8') as f:
    json.dump(scene_descriptions, f, ensure_ascii=False, indent=2)

print(f"Scene descriptions saved to: {desc_file}")

print("\n" + "="*50)
print("Data extraction complete!")

