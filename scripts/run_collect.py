#!/usr/bin/env python3
"""
电视直播源收集脚本 - 模块化版本启动脚本
"""
import sys
import os
import importlib.util
from pathlib import Path

# 添加当前目录和父目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

def import_module(module_name, file_path):
    """动态导入模块"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    """主函数"""
    print("=" * 70)
    print("电视直播源收集脚本 v7.0 - 模块化版本")
    print("=" * 70)
    
    # 检查tv_collector目录
    tv_collector_path = os.path.join(parent_dir, "tv_collector")
    if not os.path.exists(tv_collector_path):
        print(f"❌ tv_collector目录不存在: {tv_collector_path}")
        print("🔄 尝试使用简化版本...")
        
        # 检查简化版本
        simple_script = os.path.join(current_dir, "run_simple_collect.py")
        if os.path.exists(simple_script):
            print(f"✅ 找到简化版本: {simple_script}")
            exec(open(simple_script).read())
            return
        else:
            print("❌ 简化版本也不存在，退出")
            return
    
    # 导入模块
    try:
        # 导入collector模块
        collector = import_module("collector", os.path.join(tv_collector_path, "collector.py"))
        collect_and_process = collector.collect_and_process
        load_sources_from_file = collector.load_sources_from_file
        
        # 导入m3u_generator模块
        m3u_generator = import_module("m3u_generator", os.path.join(tv_collector_path, "m3u_generator.py"))
        generate_multi_source_m3u = m3u_generator.generate_multi_source_m3u
        generate_category_m3us = m3u_generator.generate_category_m3us
        generate_json_file = m3u_generator.generate_json_file
        
        # 导入utils模块
        utils = import_module("utils", os.path.join(tv_collector_path, "utils.py"))
        get_beijing_time = utils.get_beijing_time
        
        # 导入config模块
        config = import_module("config", os.path.join(tv_collector_path, "config.py"))
        PROVINCES = config.PROVINCES
        PLAYER_SUPPORT = config.PLAYER_SUPPORT
        SPEED_TEST_TIMEOUT = config.SPEED_TEST_TIMEOUT
        
        print("✅ 所有模块导入成功")
        
    except Exception as e:
        print(f"❌ 导入模块失败: {e}")
        print("🔄 尝试使用简化版本...")
        
        # 检查简化版本
        simple_script = os.path.join(current_dir, "run_simple_collect.py")
        if os.path.exists(simple_script):
            print(f"✅ 找到简化版本: {simple_script}")
            exec(open(simple_script).read())
            return
        else:
            print("❌ 简化版本也不存在，退出")
            return
    
    # 主逻辑
    try:
        # 加载数据源
        sources = load_sources_from_file()
        
        if len(sources) == 0:
            print("❌ 没有可用的数据源，退出")
            return
        
        # 收集和处理数据
        result = collect_and_process(sources)
        
        if not result:
            print("❌ 数据收集失败，退出")
            return
        
        # 提取结果数据
        merged_channels = result['merged_channels']
        all_channels = result['all_channels']
        filtered_channels = result['filtered_channels']
        success_sources = result['success_sources']
        failed_sources = result['failed_sources']
        blacklisted_count = result['blacklisted_count']
        speed_test_results = result['speed_test_results']
        slow_urls = result['slow_urls']
        blacklist = result['blacklist']
        sources = result['sources']
        
        # 统计信息
        multi_source_count = sum(1 for c in merged_channels.values() if len(c['sources']) > 1)
        single_source_count = len(merged_channels) - multi_source_count
        ipv6_channel_count = sum(1 for c in merged_channels.values() if any(s.get('is_ipv6', False) for s in c['sources']))
        fast_channel_count = sum(1 for c in merged_channels.values() if any(s.get('speed') and s['speed'] <= 2.0 for s in c['sources']))
        
        print(f"\n📊 统计:")
        print(f"  电视台总数: {len(merged_channels)}")
        print(f"  多源电视台: {multi_source_count}")
        print(f"  含IPv6源电视台: {ipv6_channel_count}")
        
        # 按分类组织频道
        categories = {}
        for channel in merged_channels.values():
            category = channel['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(channel)
        
        # 组织分类顺序
        fixed_categories = ["央视", "卫视", "景区频道", "少儿台", "综艺台", 
                           "港澳台", "体育台", "影视台", "其他台"]
        
        province_categories = []
        other_categories = []
        for category in categories.keys():
            if category in fixed_categories:
                continue
            elif category in PROVINCES or any(province in category for province in PROVINCES):
                province_categories.append(category)
            else:
                other_categories.append(category)
        
        province_categories.sort()
        final_category_order = fixed_categories + province_categories + other_categories
        
        # 生成文件
        timestamp = get_beijing_time()
        Path("merged").mkdir(exist_ok=True)
        
        # 生成主文件
        print("\n📄 生成 live_sources.m3u...")
        generate_multi_source_m3u(
            merged_channels, categories, final_category_order, 
            timestamp, "live_sources.m3u", mode="multi"
        )
        
        print("\n📄 生成 merged/多源分离版.m3u...")
        generate_multi_source_m3u(
            merged_channels, categories, final_category_order,
            timestamp, "merged/多源分离版.m3u", mode="separate"
        )
        
        print("\n📄 生成 merged/精简版.m3u...")
        generate_multi_source_m3u(
            merged_channels, categories, final_category_order,
            timestamp, "merged/精简版.m3u", mode="single"
        )
        
        print("\n📄 生成分类文件...")
        generate_category_m3us(merged_channels, categories, final_category_order, timestamp)
        
        print("\n📄 生成 channels.json...")
        generate_json_file(
            merged_channels, timestamp, sources, success_sources, failed_sources,
            all_channels, filtered_channels, blacklisted_count, blacklist, slow_urls
        )
        
        print(f"\n🎉 所有文件生成完成！")
        
    except Exception as e:
        print(f"❌ 运行过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()