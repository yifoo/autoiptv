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
    "央视": [r"CCTV", r"央视"],
    "卫视": [r"卫视"],
    "地方台": [r"地方", r"都市", r"民生", r"新闻"],
    "港澳台": [r"凤凰", r"翡翠", r"明珠", r"TVB", r"香港", r"台湾"],
    "体育": [r"体育", r"NBA", r"足球", r"篮球"],
    "电影": [r"电影", r"影院"],
    "音乐": [r"音乐", r"MTV"]
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
        # 匹配格式: #EXTINF:-1,Channel Name
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
        
        # 生成简单的index.html
        self.generate_simple_html(categorized, timestamp)
        
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
    
    def generate_simple_html(self, categorized, timestamp):
        """生成简单的HTML页面"""
        html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源播放列表</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        header { background: #4CAF50; color: white; padding: 20px; border-radius: 5px; }
        .stats { margin: 20px 0; }
        .category { margin: 20px 0; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }
        .channel { margin: 5px 0; padding: 5px; background: #f5f5f5; border-radius: 3px; }
        .download { margin: 20px 0; }
        .btn { display: inline-block; background: #2196F3; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; margin: 5px; }
    </style>
</head>
<body>
    <header>
        <h1>📺 电视直播源播放列表</h1>
        <p>自动收集整理的电视直播源</p>
    </header>
    
    <div class="stats">
        <p><strong>最后更新:</strong> ''' + timestamp + '''</p>
        <p><strong>频道总数:</strong> ''' + str(self.processed_count) + '''</p>
        <p><strong>数据源:</strong> ''' + str(len(SOURCES)) + ''' 个</p>
    </div>
    
    <div class="download">
        <h3>📥 下载播放列表</h3>
        <a href="live_sources.m3u" class="btn">完整列表</a>
        <a href="channels.json" class="btn">JSON 数据</a>
'''
        
        for category in sorted(categorized.keys()):
            if len(categorized[category]) > 0:
                html_content += f'        <a href="categories/{category}.m3u" class="btn">{category}</a>\n'
        
        html_content += '''    </div>
    
    <h3>📂 频道分类</h3>
'''
        
        for category in sorted(categorized.keys()):
            channels = categorized[category]
            html_content += f'''    <div class="category">
        <h4>{category} ({len(channels)}个频道)</h4>
'''
            
            for channel in sorted(channels[:10], key=lambda x: x.name):  # 只显示前10个
                html_content += f'''        <div class="channel">
            {channel.name}
            <button onclick="window.open('{channel.url}', '_blank')">播放</button>
        </div>
'''
            
            if len(channels) > 10:
                html_content += f'''        <p>... 还有 {len(channels) - 10} 个频道</p>
'''
            
            html_content += '''    </div>
'''
        
        html_content += '''    
    <footer style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
        <p>自动更新于 GitHub Actions | 最后更新: ''' + timestamp + '''</p>
    </footer>
    
    <script>
        function copyUrl(url) {
            navigator.clipboard.writeText(url).then(() => {
                alert('URL已复制到剪贴板');
            });
        }
    </script>
</body>
</html>'''
        
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

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
            
            # 设置GitHub Actions输出
            with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
                print(f'changed=true', file=fh)
                print(f'channels={collector.processed_count}', file=fh)
        else:
            print("\n❌ 未采集到任何有效频道")
            with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
                print(f'changed=false', file=fh)
    
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print(f'changed=false', file=fh)
        sys.exit(1)

if __name__ == "__main__":
    main()