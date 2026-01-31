#!/usr/bin/env python3
"""
主收集模块
"""
import os
import sys
import time
from pathlib import Path
from .utils import fetch_m3u, get_beijing_time
from .channel_processor import parse_channels, merge_channels, categorize_channel
from .speed_tester import test_urls_with_progress
from .blacklist_manager import load_blacklist, save_to_blacklist


def load_sources_from_file():
    """从sources.txt文件加载所有电视源"""
    sources_file = "sources.txt"
    sources = []
    
    if not os.path.exists(sources_file):
        print(f"❌ 错误: {sources_file} 文件不存在")
        print(f"📝 请创建 {sources_file} 文件，每行添加一个M3U文件URL")
        return sources
    
    try:
        with open(sources_file, "r", encoding="utf-8") as f:
            line_number = 0
            for line in f:
                line_number += 1
                line = line.strip()
                
                # 跳过空行和注释行
                if not line:
                    continue
                if line.startswith("#"):
                    continue
                
                # 验证URL格式
                if line.startswith("http://") or line.startswith("https://"):
                    sources.append(line)
                else:
                    print(f"⚠️  第{line_number}行格式错误，跳过: {line}")
        
        print(f"📡 从 {sources_file} 加载了 {len(sources)} 个数据源")
        
        if len(sources) == 0:
            print(f"❌ 错误: {sources_file} 中没有找到有效的URL")
            print(f"📝 请在 {sources_file} 中添加M3U文件URL，格式: https://example.com/live.m3u")
        
    except Exception as e:
        print(f"❌ 读取 {sources_file} 失败: {e}")
    
    return sources


def collect_and_process(sources):
    """主收集和处理函数"""
    print("🚀 开始采集电视直播源...")
    
    # 1. 加载黑名单
    print("📋 加载黑名单...")
    blacklist = load_blacklist()
    
    print(f"📋 数据源列表 (从sources.txt加载):")
    for i, source in enumerate(sources, 1):
        print(f"  {i:2d}. {source}")
    
    all_channels = []
    success_sources = 0
    failed_sources = []
    
    # 2. 收集所有频道的原始数据
    print("\n📡 开始收集频道数据...")
    for idx, source_url in enumerate(sources, 1):
        print(f"\n[{idx}/{len(sources)}] 处理: {source_url}")
        
        content = fetch_m3u(source_url)
        if not content:
            failed_sources.append(source_url)
            print("   ❌ 无法获取内容，跳过")
            continue
        
        channels = parse_channels(content, source_url)
        
        # 统计频道名称变化
        changed_count = 0
        for channel in channels:
            if channel['original_name'] != channel['clean_name']:
                changed_count += 1
        
        print(f"   ✅ 解析到 {len(channels)} 个频道 ({changed_count}个已精简)")
        
        if changed_count > 0 and len(channels) <= 10:
            for channel in channels[:5]:
                if channel['original_name'] != channel['clean_name']:
                    print(f"      '{channel['original_name']}' -> '{channel['clean_name']}'")
        
        all_channels.extend(channels)
        success_sources += 1
        
        # 避免请求过快
        if idx < len(sources):
            time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"✅ 采集完成统计:")
    print(f"   成功源数: {success_sources}/{len(sources)}")
    print(f"   失败源数: {len(failed_sources)}")
    print(f"   总计采集: {len(all_channels)} 个原始频道")
    
    if len(failed_sources) > 0:
        print(f"\n⚠️  失败的源:")
        for failed in failed_sources:
            print(f"   - {failed}")
    
    if len(all_channels) == 0:
        print("\n❌ 没有采集到任何频道，退出")
        return None
    
    # 3. 提取所有唯一的URL进行速度测试
    print("\n📊 提取所有唯一URL...")
    all_urls = set()
    for channel in all_channels:
        all_urls.add(channel['url'])
    
    print(f"   发现 {len(all_urls)} 个唯一URL")
    
    # 4. 进行速度测试
    print("\n⚡ 开始速度测试（过滤黑名单中的URL）...")
    speed_test_results, slow_urls = test_urls_with_progress(all_urls, blacklist)
    
    # 5. 保存新的慢速URL到黑名单
    if slow_urls:
        print(f"\n📝 发现 {len(slow_urls)} 个慢速源，保存到黑名单...")
        save_to_blacklist(slow_urls)
    else:
        print("\n✅ 没有发现新的慢速源")
    
    # 6. 过滤掉黑名单中的频道（包括之前黑名单和本次发现的慢速源）
    print("\n🚫 过滤黑名单中的频道...")
    filtered_channels = []
    blacklisted_count = 0
    
    for channel in all_channels:
        if channel['url'] in blacklist or channel['url'] in slow_urls:
            blacklisted_count += 1
        else:
            filtered_channels.append(channel)
    
    print(f"   原始频道数: {len(all_channels)}")
    print(f"   过滤后频道数: {len(filtered_channels)}")
    print(f"   黑名单过滤数: {blacklisted_count}")
    
    if len(filtered_channels) == 0:
        print("\n❌ 所有频道都被黑名单过滤，退出")
        return None
    
    # 7. 合并同名电视台
    print("\n🔄 正在合并同名电视台...")
    merged_channels = merge_channels(filtered_channels, speed_test_results)
    print(f"   合并后: {len(merged_channels)} 个唯一电视台")
    
    return {
        'merged_channels': merged_channels,
        'all_channels': all_channels,
        'filtered_channels': filtered_channels,
        'success_sources': success_sources,
        'failed_sources': failed_sources,
        'blacklisted_count': blacklisted_count,
        'speed_test_results': speed_test_results,
        'slow_urls': slow_urls,
        'blacklist': blacklist,
        'sources': sources
    }