
import json
import os


def main():
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
    
    json_output = r'd:\auto-xbox\team-management\.trae\documents\scene_transitions.json'
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(diagrams_data, f, ensure_ascii=False, indent=2)
    print(f"JSON已保存到: {json_output}")
    
    py_output = r'd:\auto-xbox\team-management\bend-agent\configs\scene_transitions.py'
    
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

    for i, diagram in enumerate(diagrams_data):
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
        
        if i < len(diagrams_data) - 1:
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

    with open(py_output, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"Python配置已保存到: {py_output}")
    print(f"共 {len(diagrams_data)} 个转移配置")


if __name__ == '__main__':
    main()

