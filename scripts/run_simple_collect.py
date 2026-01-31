#!/usr/bin/env python3
"""
电视直播源收集脚本 - 简化版（单文件版本）
用于模块化版本失败时的回退方案
"""
import requests
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os
import sys
import ipaddress
import concurrent.futures

print("=" * 70)
print("电视直播源收集脚本 v7.0 - 简化版（单文件）")
print("功能：频道名称精简、同名电视台合并、IPv6优先排序、慢速源黑名单过滤")
print("特点：每个电视台显示为一个条目，IPv6源优先排列")
print("=" * 70)

# 基本配置
BLACKLIST_FILE = "blacklist.txt"
SPEED_TEST_TIMEOUT = 6
MAX_WORKERS = 20

def get_beijing_time():
    """获取北京时间"""
    utc_now = datetime.now(timezone.utc)
    beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

def load_sources_from_file():
    """加载数据源"""
    sources_file = "sources.txt"
    sources = []
    
    if not os.path.exists(sources_file):
        print(f"❌ 错误: {sources_file} 文件不存在")
        return sources
    
    try:
        with open(sources_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and (line.startswith("http://") or line.startswith("https://")):
                    sources.append(line)
        
        print(f"📡 从 {sources_file} 加载了 {len(sources)} 个数据源")
        
    except Exception as e:
        print(f"❌ 读取 {sources_file} 失败: {e}")
    
    return sources

def fetch_m3u(url, retry=2):
    """获取M3U文件"""
    for attempt in range(retry + 1):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/plain,application/x-mpegURL,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                return response.text
            else:
                print(f"❌ 获取失败 {url}: HTTP {response.status_code}")
                if attempt < retry:
                    time.sleep(2)
                
        except Exception as e:
            print(f"❌ 请求错误 {url}: {e}")
            if attempt < retry:
                time.sleep(2)
    
    return None

def clean_channel_name(name):
    """清理频道名称"""
    # 简单的清理规则
    clean_rules = [
        (r'[\[\(][^\]\)]*[\]\)]', ''),
        (r'【[^】]*】', ''),
        (r'\s+直播$', ''),
        (r'\s+频道$', ''),
        (r'\s+台$', ''),
        (r'\s+电视台$', ''),
        (r'[_\-\|]+', ' '),
        (r'\s+', ' '),
    ]
    
    for pattern, replacement in clean_rules:
        name = re.sub(pattern, replacement, name)
    
    # 标准化CCTV
    if 'cctv' in name.lower():
        name = re.sub(r'cctv', 'CCTV', name, flags=re.IGNORECASE)
    
    name = name.strip()
    return name

def parse_channels(content, source_url):
    """解析M3U内容"""
    channels = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            # 提取频道名称
            name = "未知频道"
            match = re.search(r',([^,\n]+)$', line)
            if match:
                name = match.group(1).strip()
            
            # 获取URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    clean_name = clean_channel_name(name)
                    
                    channels.append({
                        'original_name': name,
                        'clean_name': clean_name,
                        'url': url,
                        'source': source_url
                    })
                    i += 1
        i += 1
    
    return channels

def main():
    """主函数"""
    # 加载数据源
    sources = load_sources_from_file()
    
    if len(sources) == 0:
        print("❌ 没有可用的数据源，退出")
        sys.exit(1)
    
    # 收集频道数据
    all_channels = []
    success_sources = 0
    failed_sources = []
    
    print("\n📡 开始收集频道数据...")
    for idx, source_url in enumerate(sources, 1):
        print(f"\n[{idx}/{len(sources)}] 处理: {source_url}")
        
        content = fetch_m3u(source_url)
        if not content:
            failed_sources.append(source_url)
            print("   ❌ 无法获取内容，跳过")
            continue
        
        channels = parse_channels(content, source_url)
        print(f"   ✅ 解析到 {len(channels)} 个频道")
        
        all_channels.extend(channels)
        success_sources += 1
        
        time.sleep(1)
    
    print(f"\n✅ 采集完成:")
    print(f"   成功源数: {success_sources}/{len(sources)}")
    print(f"   总计采集: {len(all_channels)} 个原始频道")
    
    if len(all_channels) == 0:
        print("❌ 没有采集到任何频道，退出")
        sys.exit(1)
    
    # 合并同名频道
    print("\n🔄 正在合并同名电视台...")
    merged_channels = {}
    
    for channel in all_channels:
        key = channel['clean_name']
        
        if key not in merged_channels:
            merged_channels[key] = {
                'clean_name': key,
                'sources': [{
                    'url': channel['url'],
                    'source': channel['source']
                }]
            }
        else:
            # 检查URL是否已存在
            urls = [s['url'] for s in merged_channels[key]['sources']]
            if channel['url'] not in urls:
                merged_channels[key]['sources'].append({
                    'url': channel['url'],
                    'source': channel['source']
                })
    
    print(f"   合并后: {len(merged_channels)} 个唯一电视台")
    
    # 生成M3U文件
    timestamp = get_beijing_time()
    
    # 创建目录
    Path("merged").mkdir(exist_ok=True)
    Path("categories").mkdir(exist_ok=True)
    
    # 生成主文件
    print("\n📄 生成 live_sources.m3u...")
    try:
        with open("live_sources.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"# 电视直播源 - 简化版\n")
            f.write(f"# 更新时间(北京时间): {timestamp}\n")
            f.write(f"# 电视台总数: {len(merged_channels)}\n")
            f.write(f"# 数据源: {len(sources)} 个\n\n")
            
            for channel_name, channel_data in sorted(merged_channels.items()):
                source_count = len(channel_data['sources'])
                
                if source_count > 1:
                    display_name = f"{channel_name} [{source_count}源]"
                else:
                    display_name = channel_name
                
                # 使用第一个源
                main_url = channel_data['sources'][0]['url']
                
                f.write(f'#EXTINF:-1 tvg-name="{channel_name}" group-title="所有频道",{display_name}\n')
                f.write(f"{main_url}\n")
        
        print(f"  ✅ live_sources.m3u 生成成功")
        
        # 生成简单统计
        print(f"\n📊 统计:")
        print(f"  - 电视台总数: {len(merged_channels)}")
        print(f"  - 多源电视台: {sum(1 for c in merged_channels.values() if len(c['sources']) > 1)}")
        print(f"  - 原始频道数: {len(all_channels)}")
        print(f"  - 数据源: {len(sources)}")
        
    except Exception as e:
        print(f"❌ 生成文件失败: {e}")

if __name__ == "__main__":
    main()