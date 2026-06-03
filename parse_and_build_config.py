
import re
import json
from collections import defaultdict

# Read xsrpst.py file
xsrpst_path = r'd:\auto-xbox\streaming\xsrpst.py'

with open(xsrpst_path, 'r', encoding='utf-8') as f:
    content = f.read()

# First, let's extract all the schema definitions properly
# We need to match each schema = [ ... ] block
# but we need to be careful with the comments inside
schemas = []

# Split the content by lines to process line by line
lines = content.split('\n')
in_schema = False
current_schema = []
current_numbers = []

for line in lines:
    # Check if we're starting a schema
    if 'schema = [' in line:
        in_schema = True
        current_schema = []
        current_numbers = []
        continue
    
    # Check if we're ending a schema
    if in_schema and ']' in line:
        # Add any remaining numbers from this line
        numbers = re.findall(r'-?\d+', line)
        current_numbers.extend(numbers)
        
        # If we have exactly 15 numbers, it's a valid schema
        if len(current_numbers) == 15:
            schema = list(map(int, current_numbers))
            schemas.append(schema)
            print(f"Valid schema found: {schema[0]} template {schema[3]}")
        
        in_schema = False
        continue
    
    # If we're in a schema, extract numbers
    if in_schema:
        # Skip comment lines (but extract numbers from them carefully)
        # Only extract numbers from lines that have # but also have actual data
        numbers = re.findall(r'-?\d+', line)
        # Only add numbers if the line seems to contain actual schema data
        # (not just comments with numbers)
        if numbers and not line.strip().startswith('#'):
            current_numbers.extend(numbers)
        # Also handle commented lines that still have the data
        elif numbers and any(c.isdigit() for c in line.split('#')[0]):
            # Extract numbers from before the comment
            before_comment = line.split('#')[0]
            numbers = re.findall(r'-?\d+', before_comment)
            current_numbers.extend(numbers)

print(f"\nTotal valid schemas found: {len(schemas)}")

# Now let's read the scene descriptions
desc_file = r'd:\auto-xbox\team-management\.trae\documents\scene_descriptions.json'
try:
    with open(desc_file, 'r', encoding='utf-8') as f:
        scene_descriptions = json.load(f)
except:
    scene_descriptions = {}

# Build the config file
output_file = r'd:\auto-xbox\team-management\bend-agent\configs\scene_schemas.py'

config_content = '''"""
Scene Template Schemas - Streaming项目场景模板配置
=================================================

本配置文件定义了Xbox串流场景识别所需的模板配置，
参考Streaming项目 (D:\\auto-xbox\\streaming\\xsrpst.py) 的设计。

场景模板配置说明：
- 每个场景包含一个或多个模板
- 每个模板定义了搜索区域和匹配参数
- 使用 TM_CCORR_NORMED 算法 (编号3) 进行匹配

模板文件命名规则：{场景ID}.{模板ID}.png
示例：1.1.png = 场景1的模板1

使用方式：
    from configs.scene_schemas import SCENE_SCHEMAS, SCENE_COLUMNS

"""

SCENE_SCHEMAS = [
'''

# Group schemas by scene_id
scene_groups = defaultdict(list)
for schema in schemas:
    scene_id = schema[0]
    scene_groups[scene_id].append(schema)

# Add schemas to config
for scene_id in sorted(scene_groups.keys()):
    desc = scene_descriptions.get(str(scene_id), f"场景{scene_id}")
    # Escape quotes in description
    desc_escaped = desc.replace('"', '\\"')
    config_content += f"    # 场景{scene_id}：{desc_escaped}\n"
    for schema in scene_groups[scene_id]:
        config_content += f"    {schema},\n"
    config_content += "\n"

config_content += ''']

SCENE_COLUMNS = [
    'scene_id',           # 场景编号 (1, 2, 3...)
    'scene_width',        # 场景宽度 (960)
    'scene_height',       # 场景高度 (540)
    'template_id',        # 模板编号 (1, 2, 3...)
    'template_left',      # 模板区域 左上角X
    'template_top',       # 模板区域 左上角Y
    'template_right',     # 模板区域 右下角X
    'template_bottom',    # 模板区域 右下角Y
    'search_id',          # 搜索区域编号
    'search_left',        # 搜索区域 左上角X
    'search_top',         # 搜索区域 左上角Y
    'search_right',       # 搜索区域 右下角X
    'search_bottom',      # 搜索区域 右下角Y
    'likeness',          # 相似度阈值 (0-100%)
    'algorithm'           # 匹配算法编号 (3=TM_CCORR_NORMED)
]

SCENE_NAMES = {
'''

# Add scene names
for scene_id in sorted(scene_groups.keys()):
    desc = scene_descriptions.get(str(scene_id), f"场景{scene_id}")
    desc_escaped = desc.replace('"', '\\"')
    config_content += f"    {scene_id}: \"{desc_escaped}\",\n"

config_content += '''}

ALGORITHM_NAMES = {
    0: "TM_SQDIFF",
    1: "TM_SQDIFF_NORMED",
    2: "TM_CCORR",
    3: "TM_CCORR_NORMED",
    4: "TM_CCOEFF",
    5: "TM_CCOEFF_NORMED",
}
'''

# Write the config file
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(config_content)

print(f"\nComplete config written to: {output_file}")
print(f"Total scenes: {len(scene_groups)}")
print(f"Total templates: {len(schemas)}")

# Let's verify the first few schemas
print("\nFirst 3 schemas:")
for i, schema in enumerate(schemas[:3]):
    print(f"  {i+1}: {schema}")
