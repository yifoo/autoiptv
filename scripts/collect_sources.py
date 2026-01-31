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
try:
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
    print("  ✅ live_sources.m3u 生成成功")
except Exception as e:
    print(f"  ❌ 生成live_sources.m3u失败: {e}")

# 3. 生成分类M3U文件
print("📄 生成分类文件...")
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    cat_channels = categories[category]
    if cat_channels:
        try:
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
        except Exception as e:
            print(f"  ❌ 生成 {filename} 失败: {e}")

# 4. 生成JSON文件 - 修复这里的问题
print("📄 生成 channels.json...")
try:
    # 创建可JSON序列化的频道列表
    channel_list = []
    for channel in sorted(all_channels, key=lambda x: x['name']):
        # 确保所有字段都是可序列化的
        channel_data = {
            'name': str(channel['name']) if channel['name'] else "",
            'url': str(channel['url']) if channel['url'] else "",
            'category': str(channel['group']) if channel['group'] else "其他台",
            'logo': str(channel['logo']) if channel['logo'] else ""
        }
        channel_list.append(channel_data)
    
    # 创建JSON数据
    json_data = {
        'last_updated': str(timestamp),
        'total_channels': int(len(all_channels)),
        'sources_count': int(len(sources)),
        'category_stats': {str(k): int(v) for k, v in category_stats.items()},
        'channels': channel_list
    }
    
    # 写入文件
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print("  ✅ channels.json 生成成功")
except Exception as e:
    print(f"  ❌ 生成channels.json失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 生成HTML文件
print("📄 生成 index.html...")
try:
    # 构建HTML内容
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源 - 优化分类版</title>
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
        .btn:hover {{
            background: #1976D2;
        }}
        .btn-cctv {{ background: #e60012; }}
        .btn-satellite {{ background: #0078d7; }}
        .btn-local {{ background: #107c10; }}
        .btn-kids {{ background: #ff8c00; }}
        .btn-variety {{ background: #9a0089; }}
        .btn-hk {{ background: #e3008c; }}
        .btn-sports {{ background: #0078d4; }}
        .btn-movie {{ background: #68217a; }}
        .btn-other {{ background: #666666; }}
    </style>
</head>
<body>
    <header>
        <h1>📺 电视直播源 - 优化分类版</h1>
        <p>自动收集整理的电视直播频道</p>
        <p>更新时间(北京时间): {timestamp}</p>
    </header>
    
    <div class="stats">
        <p><strong>频道总数:</strong> {len(all_channels)}</p>
        <p><strong>数据源:</strong> {len(sources)} 个</p>
    </div>
    
    <div>
        <h3>📥 下载播放列表</h3>
        <a href="live_sources.m3u" class="btn">完整列表 (所有频道)</a>
        <a href="channels.json" class="btn">JSON 数据</a>
    </div>
    
    <div>
        <h3>📂 分类列表下载</h3>
"""
    
    # 添加分类下载按钮
    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        count = len(categories[category])
        if count > 0:
            btn_class = f"btn-{category.lower().replace('台', '')}"
            html_content += f'        <a href="categories/{category}.m3u" class="btn {btn_class}">{category} ({count})</a>\n'
    
    html_content += """    </div>
    
    <h3>📺 频道分类浏览</h3>
"""
    
    # 添加分类内容
    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        cat_channels = categories[category]
        if cat_channels:
            html_content += f"""    <div class="category">
        <h4>{category} ({len(cat_channels)}个频道)</h4>
"""
            
            for channel in sorted(cat_channels[:10], key=lambda x: x['name']):
                safe_url = channel['url'].replace("'", "\\'").replace('"', '\\"')
                html_content += f"""        <div class="channel">
            <strong>{channel['name']}</strong>
            <button onclick="playChannel('{safe_url}')" style="margin-left: 10px; padding: 5px 10px; background: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">播放</button>
        </div>
"""
            
            if len(cat_channels) > 10:
                html_content += f"""        <p>... 还有 {len(cat_channels) - 10} 个频道</p>
"""
            
            html_content += "    </div>\n"
    
    html_content += f"""
    <footer style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
        <p>自动更新于 GitHub Actions | 最后更新(北京时间): {timestamp}</p>
        <p>使用 VLC、PotPlayer 等播放器打开 M3U 文件播放</p>
    </footer>
    
    <script>
        function playChannel(url) {{
            if (confirm('是否在播放器中打开此直播源？')) {{
                window.open(url, '_blank');
            }}
        }}
        
        // 显示当前北京时间
        function updateBeijingTime() {{
            const now = new Date();
            const beijingTime = new Date(now.getTime() + 8 * 60 * 60 * 1000);
            const year = beijingTime.getUTCFullYear();
            const month = String(beijingTime.getUTCMonth() + 1).padStart(2, '0');
            const day = String(beijingTime.getUTCDate()).padStart(2, '0');
            const hours = String(beijingTime.getUTCHours()).padStart(2, '0');
            const minutes = String(beijingTime.getUTCMinutes()).padStart(2, '0');
            const seconds = String(beijingTime.getUTCSeconds()).padStart(2, '0');
            const timeString = `\{{year}}-\{{month}}-\{{day}} \{{hours}}:\{{minutes}}:\{{seconds}}`;
            
            const timeElement = document.createElement('p');
            timeElement.innerHTML = `当前北京时间: \${timeString}`;
            timeElement.style.textAlign = 'center';
            timeElement.style.color = '#666';
            timeElement.style.marginTop = '10px';
            
            const footer = document.querySelector('footer');
            if (footer) {{
                footer.appendChild(timeElement);
            }}
        }}
        
        // 页面加载完成后更新时间
        document.addEventListener('DOMContentLoaded', updateBeijingTime);
    </script>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("  ✅ index.html 生成成功")
except Exception as e:
    print(f"  ❌ 生成index.html失败: {e}")

# 6. 生成README
print("📄 生成 README.md...")
try:
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

| 文件 | 描述 |
|------|------|
| [live_sources.m3u](live_sources.m3u) | 完整的直播源文件 |
| [channels.json](channels.json) | 频道数据(JSON格式) |
| [index.html](index.html) | 网页播放界面 |
| [sources.txt](sources.txt) | 自定义源列表 |

## 🚀 使用方法

1. 下载 `live_sources.m3u` 文件
2. 使用支持M3U格式的播放器打开 (VLC、PotPlayer、IINA等)
3. 选择频道观看

## ⚙️ 自定义配置

编辑 `sources.txt` 文件可以添加更多直播源URL。

## ⏰ 自动更新

每天自动更新一次。

---
*自动生成于 {timestamp}*
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("  ✅ README.md 生成成功")
except Exception as e:
    print(f"  ❌ 生成README.md失败: {e}")

print(f"\n✅ 脚本执行完成！")
print(f"📁 已生成的文件:")
print(f"  - live_sources.m3u")
print(f"  - channels.json")  
print(f"  - index.html")
print(f"  - README.md")
print(f"  - categories/*.m3u")