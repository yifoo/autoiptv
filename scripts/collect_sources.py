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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            print(f"❌ 获取源失败 {url}: {e}")
            return None
    
    def parse_m3u(self, content):
        """解析M3U内容"""
        channels = []
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            if lines[i].startswith('#EXTINF'):
                extinf = lines[i]
                channel_name = self.extract_channel_name(extinf)
                group = self.extract_group(extinf)
                logo = self.extract_logo(extinf)
                
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
        match = re.search(r',([^,\n]+)$', extinf_line)
        if match:
            return match.group(1).strip()
        
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
        if not url or url.startswith('#'):
            return False
            
        patterns = [r'^https?://', r'^rtmp://', r'^rtsp://']
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
                channels = self.parse_m3u(content)
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
                time.sleep(1)
        
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
            f.write('#EXTM3U\n')
            f.write(f'# Generated at {timestamp}\n')
            f.write(f'# Total Channels: {self.processed_count}\n\n')
            
            for category in sorted(categorized.keys()):
                channels = sorted(categorized[category], key=lambda x: x.name)
                f.write(f'# 分类: {category} ({len(channels)}个频道)\n')
                for channel in channels:
                    f.write(channel.to_m3u_line())
    
    def generate_category_files(self, categorized, timestamp):
        """生成分类M3U文件"""
        for category, channels in categorized.items():
            channels = sorted(channels, key=lambda x: x.name)
            with open(f'categories/{category}.m3u', 'w', encoding='utf-8') as f:
                f.write('#EXTM3U\n')
                f.write(f'# 分类: {category} ({len(channels)}个频道)\n')
                f.write(f'# 更新时间: {timestamp}\n\n')
                for channel in channels:
                    f.write(channel.to_m3u_line())
    
    def generate_json_file(self, categorized, timestamp):
        """生成JSON文件"""
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
                'sources_count': len(SOURCES),
                'channels': channel_list
            }, f, ensure_ascii=False, indent=2)
    
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
| `index.html` | 网页播放界面 |

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
    
    def generate_html_file(self, categorized, timestamp):
        """生成HTML页面"""
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源播放列表</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        header {{ background: #4CAF50; color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        h1 {{ margin: 0; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
        .stat {{ background: white; color: #333; padding: 15px; border-radius: 8px; flex: 1; min-width: 200px; }}
        .category {{ margin: 25px 0; padding: 20px; background: #f8f9fa; border-radius: 10px; border-left: 5px solid #4CAF50; }}
        .channels {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px; margin-top: 15px; }}
        .channel {{ padding: 10px; background: white; border-radius: 5px; border: 1px solid #ddd; }}
        .btn {{ display: inline-block; background: #4CAF50; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; margin: 5px; }}
        .btn:hover {{ background: #45a049; }}
        footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666; }}
        @media (max-width: 768px) {{
            .stats {{ flex-direction: column; }}
            .channels {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>📺 电视直播源播放列表</h1>
        <p>自动收集整理的电视直播源，支持多种播放器</p>
    </header>
    
    <div class="stats">
        <div class="stat">
            <h3>最后更新</h3>
            <p>{timestamp}</p>
        </div>
        <div class="stat">
            <h3>频道总数</h3>
            <p>{self.processed_count} 个</p>
        </div>
        <div class="stat">
            <h3>数据源</h3>
            <p>{len(SOURCES)} 个</p>
        </div>
    </div>
    
    <div>
        <h2>📥 下载播放列表</h2>
        <a href="live_sources.m3u" class="btn">完整列表 (所有频道)</a>
        <a href="channels.json" class="btn">JSON 格式数据</a>
'''

        for category in sorted(categorized.keys()):
            if len(categorized[category]) > 0:
                html += f'        <a href="categories/{category}.m3u" class="btn">{category} 列表</a>\n'

        html += '''    </div>
    
    <h2>📂 频道分类</h2>
'''

        for category in sorted(categorized.keys()):
            channels = categorized[category]
            html += f'''    <div class="category">
        <h3>{category} ({len(channels)}个频道)</h3>
        <div class="channels">
'''

            for channel in sorted(channels[:10], key=lambda x: x.name):
                html += f'''            <div class="channel">
                <strong>{channel.name}</strong><br>
                <button onclick="window.open('{channel.url}', '_blank')" style="margin-top: 5px; background: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">播放</button>
            </div>
'''

            if len(channels) > 10:
                html += f'''            <div class="channel" style="text-align: center;">
                ... 还有 {len(channels) - 10} 个频道
            </div>
'''

            html += '''        </div>
    </div>
'''

        html += f'''    
    <footer>
        <p>自动更新于 GitHub Actions | 最后更新: {timestamp}</p>
        <p>使用 VLC、PotPlayer、IINA 等播放器打开 M3U 文件即可播放</p>
    </footer>
    
    <script>
        function playChannel(url) {{
            window.open(url, '_blank');
        }}
    </script>
</body>
</html>'''

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html)

def main():
    """主函数"""
    print("=" * 60)
    print("电视直播源自动采集工具")
    print("=" * 60)
    
    collector = SourceCollector()
    
    try:
        has_data = collector.collect_all_sources()
        
        if has_data and collector.processed_count > 0:
            collector.generate_output_files()
            print("\n✅ 文件生成完成！")
            print(f"   完整文件: live_sources.m3u")
            print(f"   分类文件: categories/*.m3u")
            print(f"   JSON数据: channels.json")
            print(f"   网页界面: index.html")
            print(f"   统计信息: README.md")
            print(f"\n🎉 采集成功！共处理 {collector.processed_count} 个频道")
            
            if 'GITHUB_OUTPUT' in os.environ:
                with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
                    print(f'changed=true', file=fh)
                    print(f'channels={collector.processed_count}', file=fh)
            else:
                print(f"\n📝 输出信息:")
                print(f"changed=true")
                print(f"channels={collector.processed_count}")
        else:
            print("\n❌ 未采集到任何有效频道")
            if 'GITHUB_OUTPUT' in os.environ:
                with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
                    print(f'changed=false', file=fh)
    
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
                print(f'changed=false', file=fh)
        sys.exit(1)

if __name__ == "__main__":
    main()