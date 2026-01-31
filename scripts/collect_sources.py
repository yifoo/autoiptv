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
from urllib.parse import urlparse
import json

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
        r"央视[一二三四五六七八九十]+", r"中央电视台"
    ],
    "卫视": [
        r"卫视", r"湖南卫视", r"浙江卫视", r"江苏卫视", r"东方卫视",
        r"北京卫视", r"天津卫视", r"安徽卫视", r"山东卫视", r"广东卫视"
    ],
    "地方台": [
        r"地方", r"都市", r"民生", r"新闻", r"公共", r"生活",
        r"教育", r"少儿", r"综艺"
    ],
    "港澳台": [
        r"凤凰", r"翡翠", r"明珠", r"TVB", r"ATV", r"澳视",
        r"澳门", r"香港", r"台湾", r"中天", r"东森"
    ],
    "体育": [
        r"体育", r"NBA", r"足球", r"篮球", r"高尔夫", r"网球"
    ],
    "电影": [
        r"电影", r"影院", r"影视频道"
    ],
    "音乐": [
        r"音乐", r"MTV", r"演唱会"
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
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
                        channel.source = source_name
                        channels.append(channel)
                        i += 1
            i += 1
        
        return channels
    
    def extract_channel_name(self, extinf_line):
        """从EXTINF行提取频道名称"""
        # 匹配格式: #EXTINF:-1 tvg-id="" tvg-name="CCTV1" tvg-logo="" group-title="央视",CCTV1
        match = re.search(r',([^,\n]+)$', extinf_line)
        if match:
            return match.group(1).strip()
        
        # 尝试从tvg-name提取
        match = re.search(r'tvg-name="([^"]+)"', extinf_line)
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
        patterns = [
            r'^https?://',
            r'^rtmp://',
            r'^rtsp://',
            r'^udp://',
            r'^http-flv://',
            r'^webrtc://'
        ]
        for pattern in patterns:
            if re.match(pattern, url):
                return True
        return False
    
    def categorize_channel(self, channel_name):
        """根据规则归类频道"""
        for category, patterns in CATEGORY_RULES.items():
            for pattern in patterns:
                if re.search(pattern, channel_name, re.IGNORECASE):
                    return category
        
        # 默认分类
        if any(keyword in channel_name for keyword in ['测试', 'Test']):
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
        
        for source_url in SOURCES:
            print(f"📡 正在处理: {source_url}")
            content = self.fetch_source(source_url)
            if content:
                channels = self.parse_m3u(content, source_url)
                new_count = len(channels)
                self.collected_count += new_count
                all_channels.update(channels)
                print(f"   ✅ 采集到 {new_count} 个频道")
                time.sleep(1)  # 避免请求过快
        
        self.all_channels = all_channels
        self.processed_count = len(all_channels)
        print(f"\n📊 采集完成！")
        print(f"   共采集: {self.collected_count} 个频道")
        print(f"   去重后: {self.processed_count} 个频道")
    
    def generate_m3u_file(self):
        """生成M3U文件"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 按分类组织频道
        categorized = defaultdict(list)
        for channel in self.all_channels:
            category = self.categorize_channel(channel.name)
            # 更新分组信息
            channel.group = category
            categorized[category].append(channel)
        
        # 生成完整的M3U文件
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
        
        # 生成按分类的文件
        Path('categories').mkdir(exist_ok=True)
        for category, channels in categorized.items():
            channels = sorted(channels, key=lambda x: x.name)
            with open(f'categories/{category}.m3u', 'w', encoding='utf-8') as f:
                f.write('#EXTM3U\n')
                f.write(f'# 分类: {category} ({len(channels)}个频道)\n')
                f.write(f'# 更新时间: {timestamp}\n\n')
                for channel in channels:
                    f.write(channel.to_m3u_line())
        
        # 生成频道列表JSON（用于网页展示）
        channel_list = []
        for channel in sorted(self.all_channels, key=lambda x: x.name):
            channel_list.append({
                'name': channel.name,
                'url': channel.url,
                'category': channel.group,
                'logo': channel.logo
            })
        
        with open('channels.json', 'w', encoding='utf-8') as f:
            json.dump({
                'last_updated': timestamp,
                'total_channels': self.processed_count,
                'channels': channel_list
            }, f, ensure_ascii=False, indent=2)
        
        # 生成README统计信息
        self.generate_readme(categorized, timestamp)
        
        return True
    
    def generate_readme(self, categorized, timestamp):
        """生成README文件"""
        readme_content = f"""# 📺 电视直播源收集项目

自动收集整理的电视直播源，每日自动更新。

## 📊 统计数据
- **最后更新**: {timestamp}
- **频道总数**: {self.processed_count}
- **数据源**: {len(SOURCES)} 个

## 📁 文件说明

| 文件名 | 描述 |
|--------|------|
| `live_sources.m3u` | 完整的直播源文件（所有频道） |
| `channels.json` | 频道信息JSON格式 |
| `categories/` | 按分类分开的M3U文件目录 |
| `sources.txt` | 自定义源列表（一行一个URL） |

## 📂 频道分类

"""
        for category in sorted(categorized.keys()):
            count = len(categorized[category])
            readme_content += f"- **{category}**: {count} 个频道\n"

        readme_content += """

## 📡 数据源

"""
        for source in SOURCES:
            readme_content += f"- {source}\n"

        readme_content += """

## 🔧 使用说明

1. **直接使用**: 下载 `live_sources.m3u` 文件，在支持M3U格式的播放器中打开
2. **按分类使用**: 下载 `categories/` 目录下对应分类的文件
3. **添加自定义源**: 编辑 `sources.txt` 文件，每行添加一个M3U源URL

## ⚙️ 自动更新

本项目使用 GitHub Actions 自动更新：
- 每天 UTC 时间 18:00（北京时间凌晨2点）自动运行
- 手动触发：在 GitHub Actions 页面点击 "Run workflow"
- 修改 `sources.txt` 后自动触发

## 📄 许可证

本项目收集的直播源来自网络，仅供学习和测试使用。
"""

        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(readme_content)

def main():
    """主函数"""
    collector = SourceCollector()
    collector.collect_all_sources()
    
    if collector.processed_count > 0:
        collector.generate_m3u_file()
        print("\n✅ 文件生成完成！")
        print(f"   完整文件: live_sources.m3u")
        print(f"   分类文件: categories/")
        print(f"   JSON数据: channels.json")
        print(f"   统计信息: README.md")
        
        # 设置GitHub Actions输出
        print(f"::set-output name=changed::true")
        print(f"::set-output name=channels::{collector.processed_count}")
    else:
        print("❌ 未采集到任何频道")
        print(f"::set-output name=changed::false")

if __name__ == "__main__":
    main()