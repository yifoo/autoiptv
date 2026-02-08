#!/usr/bin/env python3
"""
M3U文件处理模块
"""

import requests
import re
import time
from .speed_test import is_ipv6_url
from .channel_cleaner import clean_channel_name
from config.categories import (
    categorize_channel, get_channel_sort_key, 
    CCTV_MAPPING, get_source_priority
)

def fetch_m3u(url, retry=2):
    """获取M3U文件，支持重试"""
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
                print(f"❌ 获取失败 {url}: HTTP {response.status_code} (尝试 {attempt + 1}/{retry + 1})")
                if attempt < retry:
                    time.sleep(2)
                
        except requests.exceptions.Timeout:
            print(f"❌ 请求超时 {url} (尝试 {attempt + 1}/{retry + 1})")
            if attempt < retry:
                time.sleep(2)
        except requests.exceptions.ConnectionError:
            print(f"❌ 连接错误 {url} (尝试 {attempt + 1}/{retry + 1})")
            if attempt < retry:
                time.sleep(2)
        except Exception as e:
            print(f"❌ 请求错误 {url}: {e} (尝试 {attempt + 1}/{retry + 1})")
            if attempt < retry:
                time.sleep(2)
    
    return None

def parse_channels(content, source_url):
    """解析M3U内容，返回频道列表"""
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
            
            # 提取分组
            group = None
            match = re.search(r'group-title="([^"]+)"', line)
            if match:
                group = match.group(1).strip()
            
            # 提取logo
            logo = None
            match = re.search(r'tvg-logo="([^"]+)"', line)
            if match:
                logo = match.group(1).strip()
            
            # 提取清晰度信息
            quality = "未知"
            if re.search(r'4K|超清|UHD|2160', name, re.IGNORECASE):
                quality = "4K"
            elif re.search(r'高清|HD|1080|FHD', name, re.IGNORECASE):
                quality = "高清"
            elif re.search(r'标清|SD|720', name, re.IGNORECASE):
                quality = "标清"
            elif re.search(r'流畅|360|480', name, re.IGNORECASE):
                quality = "流畅"
            
            # 获取URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    # 深度清理频道名称
                    clean_name = clean_channel_name(name)
                    
                    channels.append({
                        'original_name': name,
                        'clean_name': clean_name,
                        'url': url,
                        'group': group,
                        'logo': logo,
                        'quality': quality,
                        'source': source_url,
                        'extinf_line': line
                    })
                    i += 1
        i += 1
    
    return channels

def merge_channels(all_channels, speed_test_results=None):
    """合并同名电视台，支持多源，IPv6优先排序，过滤黑名单"""
    merged = {}
    
    for channel in all_channels:
        key = channel['clean_name']
        
        if key not in merged:
            # 创建新的合并频道
            merged[key] = {
                'clean_name': key,
                'original_names': [channel['original_name']],
                'sources': [{
                    'url': channel['url'],
                    'quality': channel['quality'],
                    'source': channel['source'],
                    'logo': channel['logo'],
                    'priority': 0,  # 稍后计算
                    'is_ipv6': is_ipv6_url(channel['url']),
                    'is_whitelist': channel.get('is_whitelist', False),
                    'speed_score': speed_test_results.get(channel['url'], {}).get('score', 0.0) if speed_test_results else 0.0,
                    'test_details': speed_test_results.get(channel['url'], {}) if speed_test_results else {}
                }],
                'logos': [],
                'categories': set(),
                'first_seen': channel
            }
            
            # 收集logo
            if channel['logo']:
                merged[key]['logos'].append(channel['logo'])
            
            # 确定分类
            category = categorize_channel(key)
            merged[key]['categories'].add(category)
        else:
            # 添加到现有频道
            merged[key]['original_names'].append(channel['original_name'])
            
            # 检查URL是否已存在，避免重复
            urls = [s['url'] for s in merged[key]['sources']]
            if channel['url'] not in urls:
                merged[key]['sources'].append({
                    'url': channel['url'],
                    'quality': channel['quality'],
                    'source': channel['source'],
                    'logo': channel['logo'],
                    'priority': 0,
                    'is_ipv6': is_ipv6_url(channel['url']),
                    'is_whitelist': channel.get('is_whitelist', False),
                    'speed_score': speed_test_results.get(channel['url'], {}).get('score', 0.0) if speed_test_results else 0.0,
                    'test_details': speed_test_results.get(channel['url'], {}) if speed_test_results else {}
                })
            
            # 收集logo
            if channel['logo'] and channel['logo'] not in merged[key]['logos']:
                merged[key]['logos'].append(channel['logo'])
            
            # 更新分类
            category = categorize_channel(key)
            merged[key]['categories'].add(category)
    
    # 为每个频道的源计算优先级并排序
    for key in merged:
        for source in merged[key]['sources']:
            source['priority'] = get_source_priority(source)
        
        # 按优先级降序排序
        merged[key]['sources'].sort(key=lambda x: x['priority'], reverse=True)
        
        # 为每个合并后的频道选择一个主分类
        categories = list(merged[key]['categories'])
        if categories:
            non_other = [c for c in categories if c != "其他台"]
            if non_other:
                merged[key]['category'] = non_other[0]
            else:
                merged[key]['category'] = "其他台"
        else:
            merged[key]['category'] = "其他台"
    
    return merged