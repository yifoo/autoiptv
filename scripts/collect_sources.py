#!/usr/bin/env python3
"""
电视直播源收集脚本 - 简化版
确保能生成文件
"""

import requests
import re
import time
from datetime import datetime
from pathlib import Path
import json
import os

print("=" * 60)
print("电视直播源收集脚本 v1.0")
print("=" * 60)

# 要采集的源列表
sources = [
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/chao921125/source/refs/heads/main/iptv/index.m3u"
]

# 从文件读取额外源
if os.path.exists("sources.txt"):
    try:
        with open("sources.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    sources.append(line)
    except Exception as e:
        print(f"读取sources.txt失败: {e}")

print(f"📡 共找到 {len(sources)} 个数据源")

# 分类规则
category_rules = {
    "央视": ["CCTV", "央视", "中央电视台"],
    "卫视": ["卫视"],
    "地方台": ["地方", "都市", "新闻", "公共", "生活", "教育"],
    "港澳台": ["凤凰", "翡翠", "明珠", "TVB", "香港", "台湾", "澳门"],
    "体育": ["体育", "足球", "篮球", "赛事"],
    "电影": ["电影", "影院"],
    "其他": []
}

def fetch_m3u(url):
    """获取M3U文件"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        else:
            print(f"❌ 获取失败 {url}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 请求错误 {url}: {e}")
        return None

def parse_channels(content):
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
            
            # 获取URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    channels.append({
                        'name': name,
                        'url': url,
                        'group': group,
                        'logo': logo
                    })
                    i += 1
        i += 1
    
    return channels

def categorize_channel(channel_name):
    """为频道分类"""
    name_lower = channel_name.lower()
    
    for category, keywords in category_rules.items():
        if category == "其他":
            continue
        for keyword in keywords:
            if keyword.lower() in name_lower:
                return category
    
    return "其他"

# 主收集过程
all_channels = []
channel_urls = set()  # 用于去重
total_collected = 0

for idx, source_url in enumerate(sources, 1):
    print(f"\n[{idx}/{len(sources)}] 处理: {source_url}")
    
    content = fetch_m3u(source_url)
    if not content:
        continue
    
    channels = parse_channels(content)
    print(f"   解析到 {len(channels)} 个频道")
    
    # 去重并添加
    added = 0
    for channel in channels:
        if channel['url'] not in channel_urls:
            channel_urls.add(channel['url'])
            # 确定分类
            if not channel['group']:
                channel['group'] = categorize_channel(channel['name'])
            all_channels.append(channel)
            added += 1
    
    total_collected += len(channels)
    print(f"   新增 {added} 个唯一频道")
    
    # 避免请求过快
    if idx < len(sources):
        time.sleep(1)

print(f"\n✅ 采集完成！")
print(f"   总计采集: {total_collected} 个频道")
print(f"   去重后: {len(all_channels)} 个频道")

if len(all_channels) == 0:
    print("\n❌ 没有采集到任何频道，退出")
    exit(1)

# 生成文件
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 1. 按分类组织频道
categories = {}
for channel in all_channels:
    category = channel['group']
    if category not in categories:
        categories[category] = []
    categories[category].append(channel)

# 创建categories目录
Path("categories").mkdir(exist_ok=True)

# 2. 生成完整M3U文件
print("\n📄 生成 live_sources.m3u...")
with open("live_sources.m3u", "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write(f"# 电视直播源\n")
    f.write(f"# 更新时间: {timestamp}\n")
    f.write(f"# 频道总数: {len(all_channels)}\n")
    f.write(f"# 数据源: {len(sources)}\n\n")
    
    for category in sorted(categories.keys()):
        cat_channels = categories[category]
        f.write(f"# {category} ({len(cat_channels)}个频道)\n")
        for channel in sorted(cat_channels, key=lambda x: x['name']):
            line = f"#EXTINF:-1"
            if channel['group']:
                line += f' group-title="{channel["group"]}"'
            if channel['logo']:
                line += f' tvg-logo="{channel["logo"]}"'
            line += f',{channel["name"]}\n'
            line += f"{channel['url']}\n"
            f.write(line)

# 3. 生成分类M3U文件
print("📄 生成分类文件...")
for category, cat_channels in categories.items():
    filename = f"categories/{category}.m3u"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# {category}频道列表\n")
        f.write(f"# 频道数量: {len(cat_channels)}\n\n")
        
        for channel in sorted(cat_channels, key=lambda x: x['name']):
            line = f"#EXTINF:-1"
            if channel['group']:
                line += f' group-title="{channel["group"]}"'
            if channel['logo']:
                line += f' tvg-logo="{channel["logo"]}"'
            line += f',{channel["name"]}\n'
            line += f"{channel['url']}\n"
            f.write(line)

# 4. 生成JSON文件
print("📄 生成 channels.json...")
channel_list = []
for channel in sorted(all_channels, key=lambda x: x['name']):
    channel_list.append({
        'name': channel['name'],
        'url': channel['url'],
        'category': channel['group'],
        'logo': channel['logo']
    })

with open("channels.json", "w", encoding="utf-8") as f:
    json.dump({
        'last_updated': timestamp,
        'total_channels': len(all_channels),
        'sources_count': len(sources),
        'channels': channel_list
    }, f, ensure_ascii=False, indent=2)

# 5. 生成HTML文件
print("📄 生成 index.html...")
html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            line-height: 1.6;
        }}
        header {{
            background: #4CAF50;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .stats {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .category {{
            margin: 15px 0;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .channel {{
            padding: 8px;
            margin: 5px 0;
            background: white;
            border-left: 4px solid #4CAF50;
        }}
        .btn {{
            display: inline-block;
            background: #2196F3;
            color: white;
            padding: 10px 15px;
            text-decoration: none;
            border-radius: 5px;
            margin: 5px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>📺 电视直播源</h1>
        <p>自动收集整理的电视直播频道</p>
    </header>
    
    <div class="stats">
        <p><strong>更新时间:</strong> {timestamp}</p>
        <p><strong>频道总数:</strong> {len(all_channels)}</p>
        <p><strong>数据源:</strong> {len(sources)} 个</p>
    </div>
    
    <div>
        <h3>📥 下载播放列表</h3>
        <a href="live_sources.m3u" class="btn">完整列表 (所有频道)</a>
        <a href="channels.json" class="btn">JSON 数据</a>
"""

# 添加分类下载按钮
for category in sorted(categories.keys()):
    count = len(categories[category])
    html_content += f'        <a href="categories/{category}.m3u" class="btn">{category} ({count})</a>\n'

html_content += """    </div>
    
    <h3>📺 频道分类</h3>
"""

# 添加分类内容
for category in sorted(categories.keys()):
    cat_channels = categories[category]
    html_content += f"""    <div class="category">
        <h4>{category} ({len(cat_channels)}个频道)</h4>
"""
    
    for channel in sorted(cat_channels[:10], key=lambda x: x['name']):
        html_content += f"""        <div class="channel">
            <strong>{channel['name']}</strong>
            <button onclick="window.open('{channel['url']}', '_blank')" style="margin-left: 10px; padding: 5px 10px; background: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">播放</button>
        </div>
"""
    
    if len(cat_channels) > 10:
        html_content += f"""        <p>... 还有 {len(cat_channels) - 10} 个频道</p>
"""
    
    html_content += "    </div>\n"

html_content += f"""
    <footer style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
        <p>自动更新于 GitHub Actions | 最后更新: {timestamp}</p>
        <p>使用 VLC、PotPlayer 等播放器打开 M3U 文件播放</p>
    </footer>
    
    <script>
        function playChannel(url) {{
            window.open(url, '_blank');
        }}
    </script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

# 6. 生成README
print("📄 生成 README.md...")
readme_content = f"""# 📺 电视直播源项目

自动收集整理的电视直播源。

## 📊 统计信息
- **更新时间**: {timestamp}
- **频道总数**: {len(all_channels)}
- **数据源**: {len(sources)} 个

## 📁 文件列表

| 文件 | 描述 |
|------|------|
| [live_sources.m3u](live_sources.m3u) | 完整的直播源 |
| [channels.json](channels.json) | 频道数据(JSON格式) |
| [index.html](index.html) | 网页播放界面 |
| [sources.txt](sources.txt) | 自定义源列表 |

## 📂 频道分类

"""

for category in sorted(categories.keys()):
    count = len(categories[category])
    readme_content += f"- **{category}**: {count} 个频道\n"

readme_content += """

## 🚀 使用方法

1. 下载 `live_sources.m3u` 文件
2. 使用支持M3U格式的播放器打开 (VLC、PotPlayer、IINA等)

## ⚙️ 自定义

编辑 `sources.txt` 文件添加更多直播源URL。

## ⏰ 自动更新

每天自动更新一次。
"""

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)

print("\n✅ 所有文件生成完成！")
print(f"📁 生成的文件:")
print(f"  - live_sources.m3u")
print(f"  - channels.json")
print(f"  - index.html")
print(f"  - README.md")
print(f"  - categories/*.m3u")
print(f"\n✨ 脚本执行成功！")