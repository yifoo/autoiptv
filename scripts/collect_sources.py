#!/usr/bin/env python3
"""
电视直播源收集脚本 - 优化分类版
分类：央视、卫视、地方台、少儿台、综艺台、港澳台、体育台、影视台、其他台
"""

import requests
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os

print("=" * 60)
print("电视直播源收集脚本 v2.0")
print("优化分类：央视、卫视、地方台、少儿台、综艺台、港澳台、体育台、影视台、其他台")
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

# 新的分类规则 - 按优先级顺序匹配
# 注意：匹配顺序很重要，先匹配更具体的规则
category_rules = {
    # 央视 - 最具体，最先匹配
    "央视": [
        r"CCTV[-_\s]?[0-9]+",  # CCTV1, CCTV-1, CCTV_1
        r"CCTV[一二三四五六七八九十]+",  # CCTV一, CCTV二
        r"央视[一二三四五六七八九十]+",  # 央视一, 央视二
        r"中央电视台[0-9]*",  # 中央电视台, 中央电视台1
        r"CCTV1", r"CCTV2", r"CCTV3", r"CCTV4", r"CCTV5", 
        r"CCTV6", r"CCTV7", r"CCTV8", r"CCTV9", r"CCTV10",
        r"CCTV11", r"CCTV12", r"CCTV13", r"CCTV14", r"CCTV15",
        r"CCTV16", r"CCTV17",
        r"CCTV4K", r"CCTV8K", r"CCTV5[+加]"
    ],
    
    # 卫视
    "卫视": [
        r"卫视$",  # 以"卫视"结尾
        r"[^\s]+卫视",  # XX卫视
        r"湖南卫视", r"浙江卫视", r"江苏卫视", r"东方卫视",
        r"北京卫视", r"天津卫视", r"安徽卫视", r"山东卫视", 
        r"广东卫视", r"深圳卫视", r"黑龙江卫视", r"辽宁卫视",
        r"湖北卫视", r"河南卫视", r"江西卫视", r"广西卫视",
        r"东南卫视", r"贵州卫视", r"四川卫视", r"重庆卫视",
        r"云南卫视", r"陕西卫视", r"山西卫视", r"河北卫视",
        r"吉林卫视", r"甘肃卫视", r"宁夏卫视", r"青海卫视",
        r"新疆卫视", r"西藏卫视", r"内蒙古卫视", r"海南卫视"
    ],
    
    # 少儿台
    "少儿台": [
        r"少儿", r"卡通", r"动漫", r"动画", r"卡通", r"金鹰卡通",
        r"优漫卡通", r"嘉佳卡通", r"炫动卡通", r"卡酷少儿",
        r"哈哈炫动", r"少儿频道", r"儿童频道"
    ],
    
    # 综艺台
    "综艺台": [
        r"综艺", r"文艺", r"娱乐", r"快乐垂钓", r"电竞",
        r"生活", r"时尚", r"女性", r"购物", r"旅游", r"纪实",
        r"科教", r"文化", r"戏曲", r"相声", r"小品"
    ],
    
    # 港澳台
    "港澳台": [
        r"凤凰", r"翡翠", r"明珠", r"TVB", r"ATV", r"澳视",
        r"澳门", r"香港", r"台湾", r"中天", r"东森", r"华视",
        r"民视", r"三立", r"无线", r"翡翠台", r"明珠台",
        r"本港台", r"国际台", r"星空卫视", r"华娱卫视",
        r"澳亚卫视", r"莲花卫视"
    ],
    
    # 体育台
    "体育台": [
        r"体育", r"足球", r"篮球", r"NBA", r"CBA", r"英超",
        r"西甲", r"意甲", r"德甲", r"法甲", r"欧冠",
        r"高尔夫", r"网球", r"乒羽", r"搏击", r"格斗",
        r"赛车", r"F1", r"奥运", r"赛事", r"竞技"
    ],
    
    # 影视台
    "影视台": [
        r"电影", r"影院", r"影视频道", r"好莱坞", r"CHC",
        r"电影台", r"家庭影院", r"动作电影", r"喜剧电影",
        r"爱情电影", r"科幻电影", r"恐怖电影", r"战争电影",
        r"武侠电影", r"古装电影", r"现代电影"
    ],
    
    # 地方台
    "地方台": [
        r"地方", r"都市", r"民生", r"新闻", r"公共", r"经济",
        r"法制", r"农业", r"交通", r"都市频道", r"新闻频道",
        r"公共频道", r"经济频道", r"法制频道", r"农业频道",
        r"交通频道", r"城市频道", r"省会频道"
    ]
}

def get_beijing_time():
    """获取东八区北京时间"""
    utc_now = datetime.now(timezone.utc)
    beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

def fetch_m3u(url):
    """获取M3U文件"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
    """为频道分类 - 按新规则"""
    # 首先检查已有的分组
    if channel_name in ["测试频道", "测试"]:
        return "测试频道"
    
    # 按优先级顺序匹配分类规则
    for category, patterns in category_rules.items():
        for pattern in patterns:
            try:
                if re.search(pattern, channel_name, re.IGNORECASE):
                    return category
            except re.error:
                # 如果正则表达式有误，尝试直接字符串匹配
                if pattern.lower() in channel_name.lower():
                    return category
    
    # 如果没有匹配到任何规则，返回"其他台"
    return "其他台"

# 主收集过程
all_channels = []
channel_urls = set()  # 用于去重
total_collected = 0

# 统计分类数量
category_stats = {
    "央视": 0, "卫视": 0, "地方台": 0, "少儿台": 0, 
    "综艺台": 0, "港澳台": 0, "体育台": 0, "影视台": 0, "其他台": 0
}

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
            category = categorize_channel(channel['name'])
            channel['group'] = category
            all_channels.append(channel)
            
            # 更新分类统计
            if category in category_stats:
                category_stats[category] += 1
            else:
                category_stats[category] = 1
            
            added += 1
    
    total_collected += len(channels)
    print(f"   新增 {added} 个唯一频道")
    
    # 避免请求过快
    if idx < len(sources):
        time.sleep(1)

print(f"\n✅ 采集完成！")
print(f"   总计采集: {total_collected} 个频道")
print(f"   去重后: {len(all_channels)} 个频道")
print("\n📊 分类统计:")
for category, count in category_stats.items():
    if count > 0:
        print(f"   {category}: {count} 个")

if len(all_channels) == 0:
    print("\n❌ 没有采集到任何频道，退出")
    exit(1)

# 生成文件 - 使用北京时间
timestamp = get_beijing_time()
print(f"\n📅 当前北京时间: {timestamp}")

# 1. 按分类组织频道
categories = {}
for channel in all_channels:
    category = channel['group']
    if category not in categories:
        categories[category] = []
    categories[category].append(channel)

# 确保所有分类都存在（即使为空）
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    if category not in categories:
        categories[category] = []

# 创建categories目录
Path("categories").mkdir(exist_ok=True)

# 2. 生成完整M3U文件
print("\n📄 生成 live_sources.m3u...")
with open("live_sources.m3u", "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    f.write(f"# 电视直播源 - 优化分类版\n")
    f.write(f"# 更新时间(北京时间): {timestamp}\n")
    f.write(f"# 频道总数: {len(all_channels)}\n")
    f.write(f"# 数据源: {len(sources)}\n\n")
    
    # 按指定顺序写入分类
    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        cat_channels = categories[category]
        if cat_channels:
            f.write(f"# {category} ({len(cat_channels)}个频道)\n")
            for channel in sorted(cat_channels, key=lambda x: x['name']):
                line = f"#EXTINF:-1"
                line += f' group-title="{channel["group"]}"'
                if channel['logo']:
                    line += f' tvg-logo="{channel["logo"]}"'
                line += f',{channel["name"]}\n'
                line += f"{channel['url']}\n"
                f.write(line)

# 3. 生成分类M3U文件
print("📄 生成分类文件...")
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    cat_channels = categories[category]
    if cat_channels:
        filename = f"categories/{category}.m3u"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"# {category}频道列表\n")
            f.write(f"# 更新时间(北京时间): {timestamp}\n")
            f.write(f"# 频道数量: {len(cat_channels)}\n\n")
            
            for channel in sorted(cat_channels, key=lambda x: x['name']):
                line = f"#EXTINF:-1"
                line += f' group-title="{channel["group"]}"'
                if channel['logo']:
                    line += f' tvg-logo="{channel["logo"]}"'
                line += f',{channel["name"]}\n'
                line += f"{channel['url']}\n"
                f.write(line)
        print(f"  ✅ 生成 {filename}")

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
        'category_stats': category_stats,
        'channels': channel_list
    }, f, ensure_ascii=False, indent=2)

# 5. 生成HTML文件
print("📄 生成 index.html...")
html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源 - 优化分类版</title>
    <style>
        :root {{
            --cctv-color: #e60012;
            --satellite-color: #0078d7;
            --local-color: #107c10;
            --kids-color: #ff8c00;
            --variety-color: #9a0089;
            --hongkong-color: #e3008c;
            --sports-color: #0078d4;
            --movie-color: #68217a;
            --other-color: #666666;
        }}
        
        body {{
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            margin: 0;
            font-size: 2.8rem;
            font-weight: 300;
        }}
        
        .subtitle {{
            margin: 15px 0 0 0;
            font-size: 1.2rem;
            opacity: 0.9;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-number {{
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .cctv-stat {{ color: var(--cctv-color); }}
        .satellite-stat {{ color: var(--satellite-color); }}
        .local-stat {{ color: var(--local-color); }}
        .kids-stat {{ color: var(--kids-color); }}
        .variety-stat {{ color: var(--variety-color); }}
        .hongkong-stat {{ color: var(--hongkong-color); }}
        .sports-stat {{ color: var(--sports-color); }}
        .movie-stat {{ color: var(--movie-color); }}
        .other-stat {{ color: var(--other-color); }}
        
        .category-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 25px;
            margin-top: 30px;
        }}
        
        .category-card {{
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
        }}
        
        .category-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.12);
        }}
        
        .category-header {{
            padding: 20px;
            color: white;
            font-size: 1.3rem;
            font-weight: 500;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .cctv-header {{ background: var(--cctv-color); }}
        .satellite-header {{ background: var(--satellite-color); }}
        .local-header {{ background: var(--local-color); }}
        .kids-header {{ background: var(--kids-color); }}
        .variety-header {{ background: var(--variety-color); }}
        .hongkong-header {{ background: var(--hongkong-color); }}
        .sports-header {{ background: var(--sports-color); }}
        .movie-header {{ background: var(--movie-color); }}
        .other-header {{ background: var(--other-color); }}
        
        .channel-count {{
            background: rgba(255,255,255,0.2);
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.9rem;
        }}
        
        .channel-list {{
            max-height: 400px;
            overflow-y: auto;
            padding: 15px;
        }}
        
        .channel-item {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s ease;
        }}
        
        .channel-item:hover {{
            background: #f8f9fa;
        }}
        
        .channel-item:last-child {{
            border-bottom: none;
        }}
        
        .channel-name {{
            font-weight: 500;
            flex-grow: 1;
            margin-right: 15px;
            word-break: break-word;
        }}
        
        .play-btn {{
            background: #48bb78;
            color: white;
            border: none;
            padding: 6px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: background 0.3s ease;
            white-space: nowrap;
        }}
        
        .play-btn:hover {{
            background: #38a169;
        }}
        
        .download-section {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin: 40px 0;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }}
        
        .download-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 20px;
        }}
        
        .btn {{
            display: inline-flex;
            align-items: center;
            padding: 12px 25px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        
        .btn:hover {{
            background: #5a67d8;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        footer {{
            margin-top: 50px;
            padding: 30px;
            background: white;
            border-radius: 15px;
            text-align: center;
            color: #666;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }}
        
        @media (max-width: 768px) {{
            .category-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .download-buttons {{
                flex-direction: column;
            }}
            
            .btn {{
                width: 100%;
                justify-content: center;
            }}
            
            h1 {{
                font-size: 2rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📺 电视直播源</h1>
            <p class="subtitle">优化分类版 | 自动收集整理 | 每日更新</p>
            <div style="margin-top: 20px; font-size: 0.9rem; opacity: 0.8;">
                <p>更新时间(北京时间): {timestamp}</p>
            </div>
        </header>
        
        <div class="stats-grid">
"""

# 生成统计卡片
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    count = len(categories[category])
    if count > 0:
        html_content += f"""            <div class="stat-card">
                <div class="stat-number {category.lower()}-stat">{count}</div>
                <div>{category}</div>
            </div>
"""

html_content += f"""        </div>
        
        <div class="download-section">
            <h2 style="color: #2c3e50; margin-bottom: 10px;">📥 下载播放列表</h2>
            <p style="color: #666; margin-bottom: 20px;">选择需要的播放列表文件下载</p>
            
            <div class="download-buttons">
                <a href="live_sources.m3u" class="btn">
                    <span style="margin-right: 10px;">📺</span>
                    完整列表 (所有{len(all_channels)}个频道)
                </a>
                <a href="channels.json" class="btn">
                    <span style="margin-right: 10px;">📊</span>
                    JSON 数据文件
                </a>
            </div>
            
            <h3 style="color: #2c3e50; margin: 30px 0 15px 0;">📂 分类列表下载</h3>
            <div class="download-buttons">
"""

# 生成分类下载按钮
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    count = len(categories[category])
    if count > 0:
        html_content += f"""                <a href="categories/{category}.m3u" class="btn" style="background: var(--{category.lower()}-color);">
                    <span style="margin-right: 8px;">📺</span>
                    {category} ({count})
                </a>
"""

html_content += """            </div>
        </div>
        
        <h2 style="color: #2c3e50; margin-bottom: 20px;">🎯 频道分类浏览</h2>
        <div class="category-grid">
"""

# 生成分类卡片
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    cat_channels = categories[category]
    if cat_channels:
        html_content += f"""            <div class="category-card">
                <div class="category-header {category.lower()}-header">
                    <span>{category}</span>
                    <span class="channel-count">{len(cat_channels)} 个频道</span>
                </div>
                <div class="channel-list">
"""
        
        for channel in sorted(cat_channels[:15], key=lambda x: x['name']):
            html_content += f"""                    <div class="channel-item">
                        <span class="channel-name">{channel['name']}</span>
                        <button class="play-btn" onclick="playChannel('{channel['url']}')">播放</button>
                    </div>
"""
        
        if len(cat_channels) > 15:
            html_content += f"""                    <div class="channel-item" style="justify-content: center; color: #666; font-style: italic;">
                        还有 {len(cat_channels) - 15} 个频道...
                    </div>
"""
        
        html_content += """                </div>
            </div>
"""

html_content += f"""        </div>
        
        <footer>
            <p>🔄 本项目自动更新于 GitHub Actions</p>
            <p>📅 最后更新时间(北京时间): {timestamp}</p>
            <p>🎮 支持播放器: VLC、PotPlayer、IINA、nPlayer、Kodi 等</p>
            <p style="margin-top: 20px; font-size: 0.9rem; color: #999;">
                💡 提示: 点击"播放"按钮将在新窗口打开直播流，需要播放器支持流媒体协议
            </p>
            <div id="current-time" style="margin-top: 15px; font-size: 0.9rem; color: #888;"></div>
        </footer>
    </div>
    
    <script>
        function playChannel(url) {{
            if (confirm('是否在播放器中打开此直播源？\\n\\nURL: ' + url)) {{
                window.open(url, '_blank');
            }}
        }}
        
        // 显示当前北京时间
        function updateBeijingTime() {{
            const now = new Date();
            // 转换为北京时间 (UTC+8)
            const beijingTime = new Date(now.getTime() + 8 * 60 * 60 * 1000);
            
            // 格式化时间
            const year = beijingTime.getUTCFullYear();
            const month = String(beijingTime.getUTCMonth() + 1).padStart(2, '0');
            const day = String(beijingTime.getUTCDate()).padStart(2, '0');
            const hours = String(beijingTime.getUTCHours()).padStart(2, '0');
            const minutes = String(beijingTime.getUTCMinutes()).padStart(2, '0');
            const seconds = String(beijingTime.getUTCSeconds()).padStart(2, '0');
            
            const timeString = `\${year}-\${month}-\${day} \${hours}:\${minutes}:\${seconds}`;
            
            const timeElement = document.getElementById('current-time');
            if (timeElement) {{
                timeElement.innerHTML = `🕐 当前北京时间: \${timeString}`;
            }}
        }}
        
        // 每秒更新一次时间
        setInterval(updateBeijingTime, 1000);
        updateBeijingTime();
        
        // 平滑滚动
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                const targetId = this.getAttribute('href');
                if (targetId === '#') return;
                const targetElement = document.querySelector(targetId);
                if (targetElement) {{
                    targetElement.scrollIntoView({{
                        behavior: 'smooth',
                        block: 'start'
                    }});
                }}
            }});
        }});
    </script>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

# 6. 生成README
print("📄 生成 README.md...")
readme_content = f"""# 📺 电视直播源项目 - 优化分类版

自动收集整理的电视直播源，按9大分类整理。

## 📊 统计信息
- **更新时间(北京时间)**: {timestamp}
- **频道总数**: {len(all_channels)}
- **数据源**: {len(sources)} 个

## 🏷️ 分类统计

| 分类 | 频道数量 | 说明 |
|------|----------|------|
"""

# 添加分类统计表格
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    count = len(categories[category])
    if count > 0:
        description = {
            "央视": "中央电视台及CCTV系列频道",
            "卫视": "各省市卫星电视台",
            "地方台": "地方新闻、都市、民生频道",
            "少儿台": "少儿、卡通、动漫频道",
            "综艺台": "综艺、娱乐、文艺频道",
            "港澳台": "香港、澳门、台湾地区频道",
            "体育台": "体育赛事、足球、篮球等频道",
            "影视台": "电影、影院、影视剧频道",
            "其他台": "未分类的频道"
        }.get(category, "")
        
        readme_content += f"| {category} | {count} | {description} |\n"

readme_content += f"""
| **总计** | **{len(all_channels)}** | **所有频道** |

## 📁 文件列表

| 文件 | 描述 | 下载 |
|------|------|------|
| [live_sources.m3u](live_sources.m3u) | 完整的直播源文件 | [下载](live_sources.m3u) |
| [channels.json](channels.json) | 频道数据(JSON格式) | [下载](channels.json) |
| [index.html](index.html) | 网页播放界面 | [查看](index.html) |
| [sources.txt](sources.txt) | 自定义源列表 | [编辑](sources.txt) |

## 📂 分类文件

进入 [categories/](categories/) 目录下载分类播放列表：

"""

for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    count = len(categories[category])
    if count > 0:
        readme_content += f"- [{category}.m3u](categories/{category}.m3u) - {count} 个频道\n"

readme_content += """

## 🚀 使用方法

### 快速开始
1. 下载 [live_sources.m3u](live_sources.m3u) 文件
2. 用播放器打开 (支持VLC、PotPlayer、IINA等)
3. 选择频道观看

### 按分类使用
1. 进入 [categories/](categories/) 目录
2. 下载需要的分类文件 (如`央视.m3u`)
3. 用播放器打开

### 在线查看
访问 [index.html](index.html) 在线浏览所有频道

## ⚙️ 自定义配置

编辑 `sources.txt` 文件可以添加更多直播源URL，每行一个。

## ⏰ 自动更新

- **定时更新**: 每天UTC 18:00（北京时间凌晨2点）自动运行
- **手动触发**: 在GitHub Actions页面手动运行工作流
- **源更新触发**: 修改 `sources.txt` 后自动触发

## 🔧 分类规则

本项目使用智能分类规则，自动将频道分为9大类：
1. **央视**: CCTV系列、中央电视台
2. **卫视**: 各省市卫星电视台
3. **地方台**: 地方新闻、都市频道
4. **少儿台**: 少儿、卡通、动漫频道
5. **综艺台**: 综艺、娱乐、文艺频道
6. **港澳台**: 香港、澳门、台湾地区频道
7. **体育台**: 体育赛事频道
8. **影视台**: 电影、影视剧频道
9. **其他台**: 未分类频道

## ⚠️ 免责声明

本项目的直播源来自公开网络，仅用于学习和测试。
请遵守当地法律法规，尊重版权。

---
*自动生成于 {timestamp}*
"""

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)

print("\n✅ 所有文件生成完成！")
print(f"📁 生成的文件:")
print(f"  - live_sources.m3u (主播放列表)")
print(f"  - channels.json (频道数据)")
print(f"  - index.html (网页界面)")
print(f"  - README.md (说明文档)")
print(f"  - categories/ (分类播放列表)")
print(f"\n✨ 脚本执行成功！")