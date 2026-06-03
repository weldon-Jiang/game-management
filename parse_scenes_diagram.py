
"""
解析 streaming 项目中的场景转移配置
=====================================

从 xsrpst.py 中提取 get_scenes_diagram() 函数中的所有场景转移配置
并转换为 Agent 项目可用的格式
"""

import re
import json
import os
from typing import List, Dict, Any


def parse_scenes_diagram() -> List[Dict[str, Any]]:
    """
    解析 xsrpst.py 中的场景转移配置
    
    返回：
        场景转移配置列表
    """
    xsrpst_path = r'd:\auto-xbox\streaming\xsrpst.py'
    
    if not os.path.exists(xsrpst_path):
        print(f"文件不存在: {xsrpst_path}")
        return []
    
    with open(xsrpst_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    diagrams = []
    
    # 匹配 diagram = [...] 块
    # 这种方式比较复杂，我们直接提取所有的 diagram 定义
    pattern = r'diagram\s*=\s*\[([^\]]*?)\]\s*diagrams\s*\+=\s*\[diagram\]'
    matches = re.findall(pattern, content, re.DOTALL)
    
    print(f"找到 {len(matches)} 个 diagram 块")
    
    for match in matches:
        try:
            # 清理和解析
            # 移除注释
            cleaned = re.sub(r'#.*$', '', match, flags=re.MULTILINE)
            # 移除多余的空白
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            
            # 尝试直接解析
            # 我们需要手动构建，因为可能有换行和注释
            # 让我们尝试另一种方法
            
            # 提取所有数字
            numbers = re.findall(r'-?\d+', cleaned)
            
            if len(numbers) &gt;= 4:
                # 解析结构
                scene_id = int(numbers[0])
                transition_id = int(numbers[1])
                
                # 找到手柄操作和目标场景
                # 这需要更智能的解析，让我们尝试另一种方式
                
                # 让我们直接在原始内容中查找这个 diagram
                # 找到对应的注释
                comment_match = re.search(
                    rf'#\s*场景编号---[^\n]*\s*diagram\s*=\s*\[.*?{scene_id}.*?\]\s*diagrams\s*\+=\s*\[diagram\]',
                    content,
                    re.DOTALL
                )
                
                description = f"场景 {scene_id}"
                if comment_match:
                    # 提取注释
                    comment_line = re.search(r'#\s*场景编号---[^\n]*', comment_match.group(0))
                    if comment_line:
                        description = comment_line.group(0).replace('#', '').strip()
                
                # 简化的解析，我们知道基本结构
                # [scene_id, transition_id, [[duration, count, buttons, ...], ...], [target1, target2, ...]]
                
                diagrams.append({
                    'scene_id': scene_id,
                    'transition_id': transition_id,
                    'description': description,
                    'raw': match.strip()
                })
                
        except Exception as e:
            print(f"解析 diagram 时出错: {e}")
            continue
    
    return diagrams


def extract_full_diagrams() -&gt; List[Dict[str, Any]]:
    """
    提取完整的场景转移配置（手工解析）
    """
    diagrams_data = [
        {
            'scene_id': 1,
            'transition_id': 1,
            'description': '刚串流上的主页界面',
            'controller_options': [
                [50, 1, 2, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [2]
        },
        {
            'scene_id': 2,
            'transition_id': 1,
            'description': '主页初始界面',
            'controller_options': [
                [50, 0, 512, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [203]
        },
        {
            'scene_id': 203,
            'transition_id': 1,
            'description': '选择游戏--fc25--XSS--游戏',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [101]
        },
        {
            'scene_id': 101,
            'transition_id': 1,
            'description': '登陆游戏--开场--1',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [126]
        },
        {
            'scene_id': 126,
            'transition_id': 1,
            'description': 'UT 选择界面',
            'controller_options': [
                [50, 0, 512, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [127]
        },
        {
            'scene_id': 127,
            'transition_id': 1,
            'description': '登陆游戏--UT 选中界面',
            'controller_options': [
                [50, 0, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [147]
        },
        {
            'scene_id': 147,
            'transition_id': 1,
            'description': 'UT主菜单--新闻',
            'controller_options': [
                [50, 2, 8192, 0, 255, 0, 0, 0, 0]
            ],
            'target_scenes': [149]
        },
        {
            'scene_id': 149,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [155]
        },
        {
            'scene_id': 155,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--Rush',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [156]
        },
        {
            'scene_id': 156,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--Squad Battles',
            'controller_options': [
                [50, 0, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [168]
        },
        {
            'scene_id': 168,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--左上--未打过状态',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [177]
        },
        {
            'scene_id': 169,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--左上--打过状态',
            'controller_options': [
                [50, 1, 2048, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [177]
        },
        {
            'scene_id': 170,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--右上--未打过状态',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [177]
        },
        {
            'scene_id': 171,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--右上--打过状态',
            'controller_options': [
                [50, 1, 512, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [177]
        },
        {
            'scene_id': 172,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--右下--未打过状态',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [177]
        },
        {
            'scene_id': 173,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--右下--打过状态',
            'controller_options': [
                [50, 1, 1024, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [177]
        },
        {
            'scene_id': 174,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--左下--未打过状态',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [177]
        },
        {
            'scene_id': 175,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--选择对手--对手--左下--打过状态',
            'controller_options': [
                [50, 1, 64, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [168]
        },
        {
            'scene_id': 177,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--难度选择--业余--按 A 选择',
            'controller_options': [
                [50, 1, 256, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [176]
        },
        {
            'scene_id': 177,
            'transition_id': 2,
            'description': 'UT主菜单--开始游戏--难度选择--业余--按 A 选择',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [183]
        },
        {
            'scene_id': 183,
            'transition_id': 1,
            'description': 'UT主菜单--开始游戏--您的阵容满足参赛条件--A--继续',
            'controller_options': [
                [50, 10, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [189]
        },
        # 关机流程
        {
            'scene_id': 1,
            'transition_id': 2,
            'description': '西瓜主页界面 - 关机',
            'controller_options': [
                [1000, 1, 2, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [7]
        },
        {
            'scene_id': 7,
            'transition_id': 1,
            'description': '您希望做什么--关闭',
            'controller_options': [
                [50, 1, 256, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [8]
        },
        {
            'scene_id': 8,
            'transition_id': 1,
            'description': '您希望做什么--关机',
            'controller_options': [
                [50, 1, 16, 0, 0, 0, 0, 0, 0]
            ],
            'target_scenes': [8]
        }
    ]
    
    return diagrams_data


def save_diagrams_to_json(diagrams: List[Dict[str, Any]], output_path: str):
    """
    保存场景转移配置到 JSON 文件
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(diagrams, f, ensure_ascii=False, indent=2)
    
    print(f"场景转移配置已保存到: {output_path}")
    print(f"共 {len(diagrams)} 个转移配置")


def generate_scene_transition_config(diagrams: List[Dict[str, Any]], output_path: str):
    """
    生成 Python 配置文件
    """
    config_content = '''"""
场景转移配置
============

从 streaming 项目的 get_scenes_diagram() 提取的完整场景转移配置

配置结构：
[
    {
        'scene_id': 场景ID,
        'transition_id': 转移ID,
        'description': 描述,
        'controller_options': [
            [duration_ms, count, buttons, left_trigger, right_trigger, left_thumb_x, left_thumb_y, right_thumb_x, right_thumb_y],
            ...
        ],
        'target_scenes': [目标场景ID列表]
    },
    ...
]

作者：技术团队
版本：1.0
"""

SCENE_TRANSITIONS = [
'''

    for i, diagram in enumerate(diagrams):
        config_content += f"    # {diagram['description']}\n"
        config_content += "    {\n"
        config_content += f"        'scene_id': {diagram['scene_id']},\n"
        config_content += f"        'transition_id': {diagram['transition_id']},\n"
        config_content += f"        'description': \"{diagram['description']}\",\n"
        config_content += "        'controller_options': [\n"
        
        for opt in diagram['controller_options']:
            config_content += f"            {opt},\n"
        
        config_content += "        ],\n"
        config_content += f"        'target_scenes': {diagram['target_scenes']}\n"
        
        if i &lt; len(diagrams) - 1:
            config_content += "    },\n\n"
        else:
            config_content += "    }\n"

    config_content += ''']


# 按场景ID分组的快速访问
def get_transitions_by_scene(scene_id: int):
    """获取指定场景的所有转移配置"""
    return [t for t in SCENE_TRANSITIONS if t['scene_id'] == scene_id]


def get_all_scene_ids():
    """获取所有场景ID"""
    return list({t['scene_id'] for t in SCENE_TRANSITIONS})
'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"场景转移配置已保存到: {output_path}")


if __name__ == '__main__':
    print("开始提取场景转移配置...")
    
    diagrams = extract_full_diagrams()
    
    # 保存 JSON 格式
    json_output = r'd:\auto-xbox\team-management\.trae\documents\scene_transitions.json'
    save_diagrams_to_json(diagrams, json_output)
    
    # 生成 Python 配置文件
    py_output = r'd:\auto-xbox\team-management\bend-agent\configs\scene_transitions.py'
    generate_scene_transition_config(diagrams, py_output)
    
    print("\n完成！")

