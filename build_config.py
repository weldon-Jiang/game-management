
import json

# Read all the extracted data
with open(r'd:\auto-xbox\team-management\.trae\documents\full_scene_schemas.json', 'r', encoding='utf-8') as f:
    full_schemas = json.load(f)

with open(r'd:\auto-xbox\team-management\.trae\documents\scene_descriptions.json', 'r', encoding='utf-8') as f:
    scene_descriptions = json.load(f)

# Process the schemas - we need to add the missing likeness and algorithm fields
# Looking at xsrpst.py, the format is: [scene_id, width, height, template_id, t_left, t_top, t_right, t_bottom, search_id, s_left, s_top, s_right, s_bottom, likeness=90, algorithm=3]
complete_schemas = []
for schema in full_schemas:
    if len(schema) == 13:
        # Add the missing fields with default values
        schema = schema + [90, 3]
    complete_schemas.append(schema)

# Group by scene_id
from collections import defaultdict
scene_groups = defaultdict(list)
for schema in complete_schemas:
    scene_id = schema[0]
    scene_groups[scene_id].append(schema)

# Build the config file
output_file = r'd:\auto-xbox\team-management\bend-agent\configs\scene_schemas.py'

config_content = '''"""
Scene Template Schemas - Streaming项目场景模板配置
=================================================

本配置文件定义了Xbox串流场景识别所需的模板配置，
参考Streaming项目 (D:\\\\auto-xbox\\\\streaming\\\\xsrpst.py) 的设计。

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

# Add all schemas
for scene_id in sorted(scene_groups.keys()):
    desc = scene_descriptions.get(str(scene_id), f"场景{scene_id}")
    config_content += f"    # 场景{scene_id}：{desc}\n"
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
    # Escape quotes in description
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

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(config_content)

print(f"Complete config written to: {output_file}")
print(f"Total scenes: {len(scene_groups)}")
print(f"Total templates: {len(complete_schemas)}")
