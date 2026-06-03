
import sys
import os

# 添加streaming项目路径
streaming_path = r'd:\auto-xbox\streaming'
sys.path.insert(0, streaming_path)

try:
    import xsrpst
    print("成功导入 xsrpst 模块")
    
    # 获取场景配置
    print("\n正在获取场景配置...")
    schemas = xsrpst.get_templates_schema()
    print(f"成功获取 {len(schemas)} 个场景模板配置")
    
    # 按场景ID分组统计
    from collections import defaultdict
    scene_groups = defaultdict(list)
    for schema in schemas:
        scene_id = schema[0]
        scene_groups[scene_id].append(schema)
    
    print(f"\n场景统计:")
    print(f"总场景数: {len(scene_groups)}")
    print(f"场景ID范围: {min(scene_groups.keys())} - {max(scene_groups.keys())}")
    
    # 打印场景分布
    print(f"\n场景分布:")
    for scene_id in sorted(scene_groups.keys()):
        count = len(scene_groups[scene_id])
        print(f"  场景 {scene_id}: {count} 个模板")
    
    # 保存完整配置到文件
    import json
    output_file = r'd:\auto-xbox\team-management\.trae\documents\full_scene_schemas.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(schemas, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整配置已保存到: {output_file}")
    
    # 保存分组后的配置
    grouped_schemas = {}
    for scene_id, scene_schemas in scene_groups.items():
        grouped_schemas[str(scene_id)] = scene_schemas
    
    grouped_file = r'd:\auto-xbox\team-management\.trae\documents\grouped_scene_schemas.json'
    with open(grouped_file, 'w', encoding='utf-8') as f:
        json.dump(grouped_schemas, f, ensure_ascii=False, indent=2)
    
    print(f"分组配置已保存到: {grouped_file}")
    
    # 现在读取 xsrp.py 中的场景定义
    print("\n" + "="*50)
    print("正在读取 xsrp.py 中的场景定义...")
    
    import xsrp
    print("成功导入 xsrp 模块")
    
    # 获取 Graph 类的场景常量
    import inspect
    graph_members = inspect.getmembers(xsrp.Graph)
    
    scene_constants = {}
    for name, value in graph_members:
        if name.startswith('SCENE_ID_'):
            scene_constants[name] = value
    
    print(f"\n找到 {len(scene_constants)} 个场景常量:")
    for name, value in sorted(scene_constants.items(), key=lambda x: x[1]):
        print(f"  {name} = {value}")
    
    # 保存场景常量
    scene_constants_file = r'd:\auto-xbox\team-management\.trae\documents\scene_constants.json'
    with open(scene_constants_file, 'w', encoding='utf-8') as f:
        json.dump(scene_constants, f, ensure_ascii=False, indent=2)
    
    print(f"\n场景常量已保存到: {scene_constants_file}")
    
    print("\n" + "="*50)
    print("✅ 数据提取完成!")
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()

