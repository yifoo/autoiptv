#!/usr/bin/env python3
"""
自动采集并归类电视直播源
"""

import requests
import re
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import os
import sys

# 要采集的源列表
SOURCES = [
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/chao921125/source/refs/heads/main/iptv/index.m3u"
]

# 可以添加更多源
ADDITIONAL_SOURCES_FILE = "sources.txt"

# 分类规则（正则表达式匹配频道名称）
CATEGORY_RULES = {
    "央视": [
        r"CCTV[-_\s]?\d+", r"CCTV[一二三四五六七八九十]+",
        r"央视[一二三四五六七八九十]+", r"中央电视台", r"CCTV1", r"CCTV2"
    ],
    "卫视": [
        r"卫视", r"湖南卫视", r"浙江卫视", r"江苏卫视", r"东方卫视",
        r"北京卫视", r"天津卫视", r"安徽卫视", r"山东卫视", r"广东卫视",
        r"深圳卫视", r"黑龙江卫视", r"辽宁卫视", r"湖北卫视", r"河南卫视"
    ],
    "地方台": [
        r"地方", r"都市", r"民生", r"新闻", r"公共", r"生活",
        r"教育", r"少儿", r"综艺", r"经济", r"法制", r"农业"
    ],
    "港澳台": [
        r"凤凰", r"翡翠", r"明珠", r"TVB", r"ATV", r"澳视",
        r"澳门", r"香港", r"台湾", r"中天", r"东森", r"华视",
        r"民视", r"三立", r"无线"
    ],
    "体育": [
        r"体育", r"NBA", r"足球", r"篮球", r"高尔夫", r"网球",
        r"乒羽", r"搏击", r"赛车", r"奥运"
    ],
    "电影": [
        r"电影", r"影院", r"影视频道", r"好莱坞", r"CHC"
    ],
    "音乐": [
        r"音乐", r"MTV", r"演唱会", r"K歌", r"戏曲"
    ],
    "国际": [
        r"BBC", r"CNN", r"NHK", r"DW", r"法国", r"德国",
        r"俄罗斯", r"韩国", r"日本", r"美国"
    ]
}

class Channel:
    """频道类"""
    def __init__(self, name, url, group=None, logo=None):
        self.name = name.strip()
        self.url = url.strip()
        self.group = group
        self.logo = logo
        self.hash = hashlib.md5(f"{self.name}{self.url}".encode()).hexdigest()
    
    def __eq__(self, other):
        return self.hash == other.hash
    
    def __hash__(self):
        return int(self.hash, 16)
    
    def to_m3u_line(self):
        """转换为M3U格式行"""
        line = f'#EXTINF:-1'
        if self.group:
            line += f' group-title="{self.group}"'
        if self.logo:
            line += f' tvg-logo="{self.logo}"'
        line += f',{self.name}\n{self.url}\n'
        return line

class SourceCollector:
    """源收集器"""
    
    def __init__(self):
        self.all_channels = set()
        self.collected_count = 0
        self.processed_count = 0
        
    def fetch_source(self, url):
        """获取单个源"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            print(f"❌ 获取源失败 {url}: {e}")
            return None
    
    def parse_m3u(self, content, source_name):
        """解析M3U内容"""
        channels = []
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            if lines[i].startswith('#EXTINF'):
                # 解析EXTINF行
                extinf = lines[i]
                channel_name = self.extract_channel_name(extinf)
                group = self.extract_group(extinf)
                logo = self.extract_logo(extinf)
                
                # 获取URL
                if i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith('#'):
                    url = lines[i + 1].strip()
                    if url and self.is_valid_url(url):
                        channel = Channel(channel_name, url, group, logo)
                        channels.append(channel)
                        i += 1
            i += 1
        
        return channels
    
    def extract_channel_name(self, extinf_line):
        """从EXTINF行提取频道名称"""
        # 匹配格式: #EXTINF:-1,Channel Name
        match = re.search(r',([^,\n]+)$', extinf_line)
        if match:
            return match.group(1).strip()
        
        # 尝试从tvg-name提取
        match = re.search(r'tvg-name="([^"]+)"', extinf_line)
        if match:
            return match.group(1).strip()
        
        # 最后尝试提取频道名
        match = re.search(r',([^,]+)$', extinf_line)
        if match:
            return match.group(1).strip()
        
        return "未知频道"
    
    def extract_group(self, extinf_line):
        """从EXTINF行提取分组"""
        match = re.search(r'group-title="([^"]+)"', extinf_line)
        if match:
            return match.group(1).strip()
        return None
    
    def extract_logo(self, extinf_line):
        """从EXTINF行提取logo"""
        match = re.search(r'tvg-logo="([^"]+)"', extinf_line)
        if match:
            return match.group(1).strip()
        return None
    
    def is_valid_url(self, url):
        """验证URL是否有效"""
        if not url or url.startswith('#'):
            return False
            
        patterns = [
            r'^https?://',
            r'^rtmp://',
            r'^rtsp://',
            r'^udp://',
            r'^http-flv://',
            r'^webrtc://'
        ]
        for pattern in patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def categorize_channel(self, channel_name):
        """根据规则归类频道"""
        channel_name_lower = channel_name.lower()
        
        for category, patterns in CATEGORY_RULES.items():
            for pattern in patterns:
                if re.search(pattern, channel_name, re.IGNORECASE):
                    return category
        
        # 默认分类
        if any(keyword in channel_name_lower for keyword in ['测试', 'test']):
            return '测试'
        return '其他'
    
    def collect_all_sources(self):
        """收集所有源"""
        print("🚀 开始采集直播源...")
        
        # 从文件读取额外源
        if Path(ADDITIONAL_SOURCES_FILE).exists():
            with open(ADDITIONAL_SOURCES_FILE, 'r', encoding='utf-8') as f:
                additional_sources = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                SOURCES.extend(additional_sources)
        
        all_channels = set()
        
        for idx, source_url in enumerate(SOURCES, 1):
            print(f"\n📡 [{idx}/{len(SOURCES)}] 正在处理: {source_url}")
            content = self.fetch_source(source_url)
            if content:
                channels = self.parse_m3u(content, source_url)
                new_count = len(channels)
                self.collected_count += new_count
                before_merge = len(all_channels)
                all_channels.update(channels)
                after_merge = len(all_channels)
                added = after_merge - before_merge
                print(f"   ✅ 采集到 {new_count} 个频道，新增 {added} 个")
            else:
                print(f"   ❌ 获取失败")
            
            if idx < len(SOURCES):
                time.sleep(1)  # 避免请求过快
        
        self.all_channels = all_channels
        self.processed_count = len(all_channels)
        print(f"\n📊 采集完成！")
        print(f"   共采集: {self.collected_count} 个频道")
        print(f"   去重后: {self.processed_count} 个频道")
        
        return len(all_channels) > 0
    
    def generate_output_files(self):
        """生成所有输出文件"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 按分类组织频道
        categorized = defaultdict(list)
        for channel in self.all_channels:
            category = self.categorize_channel(channel.name)
            # 更新分组信息
            channel.group = category
            categorized[category].append(channel)
        
        # 确保输出目录存在
        Path('categories').mkdir(exist_ok=True)
        
        # 生成完整的M3U文件
        self.generate_m3u_file(categorized, timestamp)
        
        # 生成分类文件
        self.generate_category_files(categorized, timestamp)
        
        # 生成JSON文件
        self.generate_json_file(categorized, timestamp)
        
        # 生成README
        self.generate_readme(categorized, timestamp)
        
        # 生成HTML页面
        self.generate_html_file(categorized, timestamp)
        
        return True
    
    def generate_m3u_file(self, categorized, timestamp):
        """生成完整的M3U文件"""
        with open('live_sources.m3u', 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url=""\n')
            f.write(f'# Generated by GitHub Actions at {timestamp}\n')
            f.write(f'# Total Channels: {self.processed_count}\n')
            f.write(f'# Sources: {len(SOURCES)}\n\n')
            
            # 按分类写入
            for category in sorted(categorized.keys()):
                channels = sorted(categorized[category], key=lambda x: x.name)
                f.write(f'\n# 分类: {category} ({len(channels)}个频道)\n')
                for channel in channels:
                    f.write(channel.to_m3u_line())
    
    def generate_category_files(self, categorized, timestamp):
        """生成分类M3U文件"""
        for category, channels in categorized.items():
            channels = sorted(channels, key=lambda x: x.name)
            with open(f'categories/{category}.m3u', 'w', encoding='utf-8') as f:
                f