#!/usr/bin/env python3
"""
电视直播源收集脚本 - 精简合并版
功能：1. 频道名称精简 2. 同名电视台合并 3. 支持多源切换
分类：央视、卫视、地方台、少儿台、综艺台、港澳台、体育台、影视台、其他台
"""

import requests
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os
import sys

print("=" * 70)
print("电视直播源收集脚本 v3.0 - 精简合并版")
print("功能：频道名称精简、同名电视台合并、支持多源切换")
print("=" * 70)

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

# 频道名称清理规则 - 移除冗余信息
CLEAN_RULES = [
    # 移除清晰度标记
    (r'\[[^\]]*\]', ''),  # 移除方括号内容
    (r'\([^\)]*\)', ''),  # 移除圆括号内容
    (r'【[^】]*】', ''),  # 移除中文方括号内容
    
    # 移除常见冗余词
    (r'直播$', ''),
    (r'频道$', ''),
    (r'台$', ''),
    (r'电视台$', ''),
    (r'卫视台$', '卫视'),
    
    # 统一清晰度标记
    (r'[_-]?4K$', ''),
    (r'[_-]?高清$', ''),
    (r'[_-]?HD$', ''),
    (r'[_-]?超清$', ''),
    (r'[_-]?标清$', ''),
    (r'[_-]?流畅$', ''),
    
    # 统一协议标记
    (r'[_-]?IPV6$', ''),
    (r'[_-]?IPV4$', ''),
    (r'[_-]?HLS$', ''),
    (r'[_-]?RTMP$', ''),
    
    # 移除多余空格和分隔符
    (r'\s+', ' '),
    (r'^\s+|\s+$', ''),
    (r'[_-]{2,}', '-'),
    (r'\s*[|]\s*', ' '),
]

# 分类规则 - 按优先级顺序匹配
CATEGORY_RULES = {
    # 央视 - 最具体，最先匹配
    "央视": [
        r"^CCTV[-\s]?[\d一二三四五六七八九十]+",  # CCTV1, CCTV-1, CCTV一
        r"^央视[一二三四五六七八九十]+",  # 央视一, 央视二
        r"^中央电视台",  # 中央电视台
        r"^CCTV1$", r"^CCTV2$", r"^CCTV3$", r"^CCTV4$", r"^CCTV5$",
        r"^CCTV6$", r"^CCTV7$", r"^CCTV8$", r"^CCTV9$", r"^CCTV10$",
        r"^CCTV11$", r"^CCTV12$", r"^CCTV13$", r"^CCTV14$", r"^CCTV15$",
        r"^CCTV16$", r"^CCTV17$",
        r"^CCTV4K$", r"^CCTV8K$", r"^CCTV5\+$"
    ],
    
    # 卫视
    "卫视": [
        r"卫视$",  # 以"卫视"结尾
        r"^湖南卫视$", r"^浙江卫视$", r"^江苏卫视$", r"^东方卫视$",
        r"^北京卫视$", r"^天津卫视$", r"^安徽卫视$", r"^山东卫视$",
        r"^广东卫视$", r"^深圳卫视$", r"^黑龙江卫视$", r"^辽宁卫视$",
        r"^湖北卫视$", r"^河南卫视$", r"^江西卫视$", r"^广西卫视$",
        r"^东南卫视$", r"^贵州卫视$", r"^四川卫视$", r"^重庆卫视$",
        r"^云南卫视$", r"^陕西卫视$", r"^山西卫视$", r"^河北卫视$",
        r"^吉林卫视$", r"^甘肃卫视$", r"^宁夏卫视$", r"^青海卫视$",
        r"^新疆卫视$", r"^西藏卫视$", r"^内蒙古卫视$", r"^海南卫视$"
    ],
    
    # 少儿台
    "少儿台": [
        r"少儿", r"卡通", r"动漫", r"动画", r"金鹰卡通",
        r"优漫卡通", r"嘉佳卡通", r"炫动卡通", r"卡酷少儿",
        r"哈哈炫动", r"少儿频道", r"儿童频道", r"宝贝"
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
        r"爱情电影", r"科幻电影", r"恐怖电影", r"战争电影"
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

def clean_channel_name(name):
    """清理频道名称，移除冗余信息"""
    original_name = name
    for pattern, replacement in CLEAN_RULES:
        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
    
    # 特殊情况处理
    name = re.sub(r'^CCTV[_\s]', 'CCTV', name)  # CCTV_1 -> CCTV1
    name = re.sub(r'^CCTV[一二三四五六七八九十]', lambda m: f'CTV{m.group(0)[4:]}', name)  # 中文数字转阿拉伯
    
    # 最终清理
    name = name.strip()
    
    # 如果清理后为空，使用原始名称
    if not name:
        name = original_name
    
    return name

def fetch_m3u(url):
    """获取M3U文件"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        else:
            print(f"❌ 获取失败 {url}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 请求错误 {url}: {e}")
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
            if re.search(r'4K|超清|UHD', name, re.IGNORECASE):
                quality = "4K超清"
            elif re.search(r'高清|HD|1080', name, re.IGNORECASE):
                quality = "高清"
            elif re.search(r'标清|SD|720', name, re.IGNORECASE):
                quality = "标清"
            
            # 获取URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    # 清理频道名称
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

def categorize_channel(channel_name):
    """为频道分类"""
    # 按优先级顺序匹配分类规则
    for category, patterns in CATEGORY_RULES.items():
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

def merge_channels(all_channels):
    """合并同名电视台，支持多源"""
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
                    'logo': channel['logo']
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
            
            # 添加源
            merged[key]['sources'].append({
                'url': channel['url'],
                'quality': channel['quality'],
                'source': channel['source'],
                'logo': channel['logo']
            })
            
            # 收集logo
            if channel['logo'] and channel['logo'] not in merged[key]['logos']:
                merged[key]['logos'].append(channel['logo'])
            
            # 更新分类
            category = categorize_channel(key)
            merged[key]['categories'].add(category)
    
    # 为每个合并后的频道选择一个主分类
    for key in merged:
        categories = list(merged[key]['categories'])
        if categories:
            # 优先选择非"其他台"的分类
            non_other = [c for c in categories if c != "其他台"]
            if non_other:
                merged[key]['category'] = non_other[0]
            else:
                merged[key]['category'] = "其他台"
        else:
            merged[key]['category'] = "其他台"
    
    return merged

# 主收集过程
print("🚀 开始采集电视直播源...")

all_channels = []
total_collected = 0

for idx, source_url in enumerate(sources, 1):
    print(f"\n[{idx}/{len(sources)}] 处理: {source_url}")
    
    content = fetch_m3u(source_url)
    if not content:
        print("   ⚠️  无法获取内容，跳过")
        continue
    
    channels = parse_channels(content, source_url)
    print(f"   解析到 {len(channels)} 个频道")
    
    all_channels.extend(channels)
    total_collected += len(channels)
    
    # 避免请求过快
    if idx < len(sources):
        time.sleep(1)

print(f"\n✅ 采集完成！")
print(f"   总计采集: {total_collected} 个原始频道")

if len(all_channels) == 0:
    print("\n❌ 没有采集到任何频道，退出")
    sys.exit(1)

# 合并同名电视台
print("\n🔄 正在合并同名电视台...")
merged_channels = merge_channels(all_channels)
print(f"   合并后: {len(merged_channels)} 个唯一电视台")

# 统计分类数量
category_stats = {
    "央视": 0, "卫视": 0, "地方台": 0, "少儿台": 0,
    "综艺台": 0, "港澳台": 0, "体育台": 0, "影视台": 0, "其他台": 0
}

for channel in merged_channels.values():
    category = channel['category']
    if category in category_stats:
        category_stats[category] += 1
    else:
        category_stats[category] = 1

print("\n📊 分类统计:")
for category, count in category_stats.items():
    if count > 0:
        print(f"   {category}: {count} 个电视台")

# 生成文件 - 使用北京时间
timestamp = get_beijing_time()
print(f"\n📅 当前北京时间: {timestamp}")

# 按分类组织频道
categories = {}
for channel in merged_channels.values():
    category = channel['category']
    if category not in categories:
        categories[category] = []
    categories[category].append(channel)

# 确保所有分类都存在（即使为空）
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    if category not in categories:
        categories[category] = []

# 创建输出目录
Path("categories").mkdir(exist_ok=True)
Path("merged").mkdir(exist_ok=True)

# 1. 生成完整的M3U文件（精简合并版）
print("\n📄 生成 live_sources.m3u（精简合并版）...")
try:
    with open("live_sources.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# 电视直播源 - 精简合并版\n")
        f.write(f"# 更新时间(北京时间): {timestamp}\n")
        f.write(f"# 电视台总数: {len(merged_channels)}\n")
        f.write(f"# 原始频道数: {total_collected}\n")
        f.write(f"# 数据源: {len(sources)}\n")
        f.write(f"# 说明: 同名电视台已合并，支持多源切换\n")
        f.write(f"# 每个电视台显示为: 电视台名称 [源1/源2...]\n\n")
        
        # 按分类写入
        for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
            cat_channels = categories[category]
            if cat_channels:
                f.write(f"\n# 分类: {category} ({len(cat_channels)}个电视台)\n")
                
                for channel in sorted(cat_channels, key=lambda x: x['clean_name']):
                    # 选择主logo（第一个非空的logo）
                    main_logo = channel['logos'][0] if channel['logos'] else ""
                    
                    # 写入电视台信息
                    source_count = len(channel['sources'])
                    display_name = f"{channel['clean_name']} [{source_count}源]"
                    
                    # 写入第一个源
                    main_source = channel['sources'][0]
                    line = "#EXTINF:-1"
                    line += f' tvg-name="{channel["clean_name"]}"'
                    line += f' group-title="{category}"'
                    if main_logo:
                        line += f' tvg-logo="{main_logo}"'
                    line += f',{display_name}\n'
                    line += f"{main_source['url']}\n"
                    f.write(line)
                    
                    # 如果有多个源，写入其他源作为备用
                    if len(channel['sources']) > 1:
                        for i, source in enumerate(channel['sources'][1:], 2):
                            alt_line = "#EXTINF:-1"
                            alt_line += f' tvg-name="{channel["clean_name"]}"'
                            alt_line += f' group-title="{category}"'
                            alt_line += f' tvg-logo="{main_logo}"'
                            alt_line += f',{channel["clean_name"]} [源{i}]\n'
                            alt_line += f"{source['url']}\n"
                            f.write(alt_line)
    
    print(f"  ✅ live_sources.m3u 生成成功，包含 {len(merged_channels)} 个电视台")
except Exception as e:
    print(f"  ❌ 生成live_sources.m3u失败: {e}")
    import traceback
    traceback.print_exc()

# 2. 生成分类M3U文件
print("\n📄 生成分类文件...")
for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
    cat_channels = categories[category]
    if cat_channels:
        try:
            filename = f"categories/{category}.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"# {category}频道列表\n")
                f.write(f"# 更新时间(北京时间): {timestamp}\n")
                f.write(f"# 电视台数量: {len(cat_channels)}\n\n")
                
                for channel in sorted(cat_channels, key=lambda x: x['clean_name']):
                    main_logo = channel['logos'][0] if channel['logos'] else ""
                    source_count = len(channel['sources'])
                    display_name = f"{channel['clean_name']} [{source_count}源]"
                    
                    # 写入第一个源
                    main_source = channel['sources'][0]
                    line = "#EXTINF:-1"
                    line += f' tvg-name="{channel["clean_name"]}"'
                    line += f' group-title="{category}"'
                    if main_logo:
                        line += f' tvg-logo="{main_logo}"'
                    line += f',{display_name}\n'
                    line += f"{main_source['url']}\n"
                    f.write(line)
            
            print(f"  ✅ 生成 {filename}")
        except Exception as e:
            print(f"  ❌ 生成 {filename} 失败: {e}")

# 3. 生成合并的JSON文件（包含所有源信息）
print("\n📄 生成 channels.json...")
try:
    # 创建频道列表
    channel_list = []
    for clean_name, channel_data in sorted(merged_channels.items()):
        # 准备源信息
        sources_info = []
        for i, source in enumerate(channel_data['sources'], 1):
            sources_info.append({
                'index': i,
                'url': source['url'],
                'quality': source['quality'],
                'source': source['source'],
                'logo': source['logo'] if source['logo'] else ""
            })
        
        # 频道信息
        channel_info = {
            'clean_name': clean_name,
            'original_names': list(set(channel_data['original_names'])),  # 去重
            'category': channel_data['category'],
            'source_count': len(channel_data['sources']),
            'logos': channel_data['logos'],
            'sources': sources_info
        }
        channel_list.append(channel_info)
    
    # 创建JSON数据
    json_data = {
        'last_updated': timestamp,
        'total_channels': len(merged_channels),
        'original_channel_count': total_collected,
        'sources_count': len(sources),
        'category_stats': category_stats,
        'channels': channel_list
    }
    
    # 写入文件
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"  ✅ channels.json 生成成功，包含 {len(merged_channels)} 个电视台的详细信息")
except Exception as e:
    print(f"  ❌ 生成channels.json失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 生成精简版M3U（每个电视台只保留一个源）
print("\n📄 生成 merged/精简版.m3u...")
try:
    with open("merged/精简版.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# 电视直播源 - 精简版\n")
        f.write(f"# 更新时间(北京时间): {timestamp}\n")
        f.write(f"# 电视台总数: {len(merged_channels)}\n")
        f.write(f"# 说明: 每个电视台只保留最佳源\n\n")
        
        for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
            cat_channels = categories[category]
            if cat_channels:
                f.write(f"\n# {category} ({len(cat_channels)}个电视台)\n")
                
                for channel in sorted(cat_channels, key=lambda x: x['clean_name']):
                    # 选择最佳源（优先选择高清源）
                    best_source = None
                    for source in channel['sources']:
                        if source['quality'] == "4K超清":
                            best_source = source
                            break
                        elif source['quality'] == "高清":
                            best_source = source
                    
                    if not best_source:
                        best_source = channel['sources'][0]
                    
                    main_logo = channel['logos'][0] if channel['logos'] else ""
                    
                    line = "#EXTINF:-1"
                    line += f' tvg-name="{channel["clean_name"]}"'
                    line += f' group-title="{category}"'
                    if main_logo:
                        line += f' tvg-logo="{main_logo}"'
                    line += f',{channel["clean_name"]}\n'
                    line += f"{best_source['url']}\n"
                    f.write(line)
    
    print(f"  ✅ 精简版.m3u 生成成功")
except Exception as e:
    print(f"  ❌ 生成精简版.m3u失败: {e}")

# 5. 生成HTML页面
print("\n📄 生成 index.html...")
try:
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源 - 精简合并版</title>
    <style>
        :root {{
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --success-color: #27ae60;
            --warning-color: #f39c12;
            --danger-color: #e74c3c;
            --light-bg: #ecf0f1;
            --dark-bg: #34495e;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f7fa;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 300;
        }}
        
        .subtitle {{
            font-size: 1.1rem;
            opacity: 0.9;
            margin-bottom: 20px;
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
            font-size: 2.2rem;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .download-section {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin: 30px 0;
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
            background: var(--secondary-color);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
        }}
        
        .btn:hover {{
            background: #2980b9;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .btn-success {{
            background: var(--success-color);
        }}
        
        .btn-warning {{
            background: var(--warning-color);
        }}
        
        .category-tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 30px 0;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }}
        
        .tab-btn {{
            padding: 10px 20px;
            background: var(--light-bg);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 500;
        }}
        
        .tab-btn:hover {{
            background: var(--secondary-color);
            color: white;
        }}
        
        .tab-btn.active {{
            background: var(--secondary-color);
            color: white;
        }}
        
        .channels-container {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-bottom: 30px;
        }}
        
        .channel-card {{
            padding: 20px;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }}
        
        .channel-card:hover {{
            border-color: var(--secondary-color);
            box-shadow: 0 5px 15px rgba(52, 152, 219, 0.1);
        }}
        
        .channel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .channel-name {{
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--primary-color);
        }}
        
        .source-badge {{
            background: var(--success-color);
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9rem;
        }}
        
        .sources-container {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }}
        
        .source-item {{
            padding: 12px;
            background: #f8f9fa;
            border-radius: 6px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .source-info {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        
        .quality-badge {{
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }}
        
        .quality-4k {{ background: #9b59b6; color: white; }}
        .quality-hd {{ background: #3498db; color: white; }}
        .quality-sd {{ background: #95a5a6; color: white; }}
        .quality-unknown {{ background: #7f8c8d; color: white; }}
        
        .source-actions {{
            display: flex;
            gap: 10px;
        }}
        
        .play-btn {{
            padding: 8px 16px;
            background: var(--success-color);
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s ease;
        }}
        
        .play-btn:hover {{
            background: #219653;
        }}
        
        .copy-btn {{
            padding: 8px 16px;
            background: var(--warning-color);
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s ease;
        }}
        
        .copy-btn:hover {{
            background: #e67e22;
        }}
        
        footer {{
            text-align: center;
            padding: 30px;
            color: #7f8c8d;
            font-size: 0.9rem;
            background: white;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }}
        
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .download-buttons {{
                flex-direction: column;
            }}
            
            .channel-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }}
            
            .source-info {{
                flex-direction: column;
                align-items: flex-start;
                gap: 5px;
            }}
            
            .source-actions {{
                width: 100%;
                justify-content: space-between;
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
            <h1>📺 电视直播源 - 精简合并版</h1>
            <p class="subtitle">同名电视台自动合并 | 支持多源切换 | 每日自动更新</p>
            <div style="margin-top: 15px; font-size: 0.9rem; opacity: 0.8;">
                <p>更新时间(北京时间): {timestamp}</p>
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" style="color: #667eea;">{len(merged_channels)}</div>
                <div>电视台总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #e74c3c;">{total_collected}</div>
                <div>原始频道数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #27ae60;">{len(sources)}</div>
                <div>数据源数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #9b59b6;">{sum(category_stats.values())}</div>
                <div>分类总数</div>
            </div>
        </div>
        
        <div class="download-section">
            <h2 style="color: var(--primary-color); margin-bottom: 15px;">📥 下载播放列表</h2>
            <p style="color: #666; margin-bottom: 20px;">选择需要的播放列表格式下载</p>
            
            <div class="download-buttons">
                <a href="live_sources.m3u" class="btn">
                    <span style="margin-right: 10px;">📺</span>
                    完整版 (含多源)
                </a>
                <a href="merged/精简版.m3u" class="btn btn-success">
                    <span style="margin-right: 10px;">✨</span>
                    精简版 (最佳源)
                </a>
                <a href="channels.json" class="btn btn-warning">
                    <span style="margin-right: 10px;">📊</span>
                    JSON 数据
                </a>
            </div>
            
            <h3 style="color: var(--primary-color); margin: 25px 0 15px 0;">📂 分类列表下载</h3>
            <div class="download-buttons">
"""
    
    # 添加分类下载按钮
    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        count = len(categories[category])
        if count > 0:
            html_content += f"""                <a href="categories/{category}.m3u" class="btn" style="background: #95a5a6;">
                    {category} ({count})
                </a>
"""
    
    html_content += """            </div>
        </div>
        
        <h2 style="color: var(--primary-color); margin-bottom: 20px;">🎯 电视台浏览</h2>
        <div class="category-tabs" id="categoryTabs">
            <button class="tab-btn active" data-category="all">全部电视台</button>
"""
    
    # 添加分类标签
    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        count = len(categories[category])
        if count > 0:
            html_content += f'            <button class="tab-btn" data-category="{category}">{category} ({count})</button>\n'
    
    html_content += """        </div>
        
        <div class="channels-container" id="channelsList">
            <!-- 频道列表将通过JavaScript动态加载 -->
            <div style="text-align: center; padding: 40px; color: #7f8c8d;">
                <p>正在加载电视台列表...</p>
            </div>
        </div>
        
        <footer>
            <p>🔄 本项目自动更新于 GitHub Actions | 最后更新(北京时间): {timestamp}</p>
            <p>🎮 支持播放器: VLC、PotPlayer、IINA、nPlayer、Kodi、TiviMate等</p>
            <p style="margin-top: 15px; font-size: 0.8rem; color: #bdc3c7;">
                💡 提示: 每个电视台可能包含多个源，如果某个源无法播放，请尝试切换其他源
            </p>
            <div id="currentTime" style="margin-top: 15px; font-size: 0.8rem; color: #95a5a6;"></div>
        </footer>
    </div>
    
    <script>
        // 频道数据
        const channelData = """
    
    # 添加简化的频道数据到JavaScript
    simplified_channels = []
    for clean_name, channel_data in merged_channels.items():
        simplified = {
            'name': clean_name,
            'category': channel_data['category'],
            'sourceCount': len(channel_data['sources']),
            'sources': []
        }
        
        for source in channel_data['sources']:
            simplified['sources'].append({
                'url': source['url'],
                'quality': source['quality'],
                'logo': source['logo'] or ''
            })
        
        simplified_channels.append(simplified)
    
    html_content += json.dumps(simplified_channels, ensure_ascii=False)
    
    html_content += """;
        
        // 页面功能
        document.addEventListener('DOMContentLoaded', function() {
            // 初始化
            renderChannels('all');
            updateTime();
            
            // 标签切换
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    renderChannels(this.dataset.category);
                });
            });
            
            // 每5秒更新一次时间
            setInterval(updateTime, 5000);
        });
        
        function renderChannels(category) {
            const container = document.getElementById('channelsList');
            const filteredChannels = category === 'all' 
                ? channelData 
                : channelData.filter(c => c.category === category);
            
            if (filteredChannels.length === 0) {
                container.innerHTML = '<div style="text-align: center; padding: 40px; color: #7f8c8d;">该分类下没有电视台</div>';
                return;
            }
            
            // 按名称排序
            filteredChannels.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'));
            
            let html = '';
            
            filteredChannels.forEach(channel => {
                html += `
                <div class="channel-card">
                    <div class="channel-header">
                        <div class="channel-name">${channel.name}</div>
                        <div class="source-badge">${channel.sourceCount} 个源</div>
                    </div>
                    
                    <div class="sources-container">
                        <p style="margin-bottom: 10px; color: #666; font-size: 0.9rem;">切换源:</p>
                `;
                
                channel.sources.forEach((source, index) => {
                    const qualityClass = getQualityClass(source.quality);
                    html += `
                    <div class="source-item">
                        <div class="source-info">
                            <span style="font-weight: 500;">源 ${index + 1}</span>
                            <span class="quality-badge ${qualityClass}">${source.quality}</span>
                            ${source.logo ? `<span style="font-size: 0.8rem; color: #7f8c8d;">有Logo</span>` : ''}
                        </div>
                        <div class="source-actions">
                            <button class="copy-btn" onclick="copyToClipboard('${source.url.replace(/'/g, "\\'")}')">复制</button>
                            <button class="play-btn" onclick="playChannel('${source.url.replace(/'/g, "\\'")}', '${channel.name}')">播放</button>
                        </div>
                    </div>
                    `;
                });
                
                html += `
                    </div>
                </div>
                `;
            });
            
            container.innerHTML = html;
        }
        
        function getQualityClass(quality) {
            if (quality.includes('4K')) return 'quality-4k';
            if (quality.includes('高清')) return 'quality-hd';
            if (quality.includes('标清')) return 'quality-sd';
            return 'quality-unknown';
        }
        
        function playChannel(url, name) {
            if (confirm(`播放 ${name}？\\n\\nURL: ${url.substring(0, 100)}${url.length > 100 ? '...' : ''}`)) {
                window.open(url, '_blank');
            }
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('URL已复制到剪贴板！');
            }).catch(err => {
                console.error('复制失败:', err);
                alert('复制失败，请手动复制');
            });
        }
        
        function updateTime() {
            const now = new Date();
            const beijingTime = new Date(now.getTime() + 8 * 60 * 60 * 1000);
            const timeStr = beijingTime.toISOString().replace('T', ' ').substring(0, 19);
            const timeElement = document.getElementById('currentTime');
            if (timeElement) {
                timeElement.textContent = `当前北京时间: ${timeStr}`;
            }
        }
        
        // 搜索功能
        function initSearch() {
            const searchBox = document.createElement('div');
            searchBox.innerHTML = `
                <div style="margin-bottom: 20px;">
                    <input type="text" id="searchInput" placeholder="搜索电视台名称..." 
                           style="width: 100%; padding: 12px 20px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem;">
                </div>
            `;
            document.querySelector('.category-tabs').parentNode.insertBefore(searchBox, document.querySelector('.category-tabs'));
            
            document.getElementById('searchInput').addEventListener('input', function(e) {
                const searchTerm = e.target.value.toLowerCase();
                if (searchTerm) {
                    const filtered = channelData.filter(c => 
                        c.name.toLowerCase().includes(searchTerm) || 
                        c.category.toLowerCase().includes(searchTerm)
                    );
                    
                    const container = document.getElementById('channelsList');
                    if (filtered.length === 0) {
                        container.innerHTML = '<div style="text-align: center; padding: 40px; color: #7f8c8d;">未找到匹配的电视台</div>';
                    } else {
                        // 临时渲染搜索结果
                        const currentCategory = document.querySelector('.tab-btn.active').dataset.category;
                        if (currentCategory !== 'all') {
                            document.querySelector('.tab-btn[data-category="all"]').click();
                        }
                        renderSearchResults(filtered);
                    }
                } else {
                    // 恢复当前分类
                    const currentCategory = document.querySelector('.tab-btn.active').dataset.category;
                    renderChannels(currentCategory);
                }
            });
        }
        
        function renderSearchResults(channels) {
            const container = document.getElementById('channelsList');
            
            let html = '<div style="margin-bottom: 20px; color: #666; font-size: 0.9rem;">搜索结果:</div>';
            
            channels.forEach(channel => {
                html += `
                <div class="channel-card">
                    <div class="channel-header">
                        <div class="channel-name">${channel.name}</div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="background: #95a5a6; color: white; padding: 3px 10px; border-radius: 4px; font-size: 0.8rem;">
                                ${channel.category}
                            </span>
                            <div class="source-badge">${channel.sourceCount} 源</div>
                        </div>
                    </div>
                    
                    <div class="sources-container">
                        <p style="margin-bottom: 10px; color: #666; font-size: 0.9rem;">切换源:</p>
                `;
                
                channel.sources.forEach((source, index) => {
                    const qualityClass = getQualityClass(source.quality);
                    html += `
                    <div class="source-item">
                        <div class="source-info">
                            <span style="font-weight: 500;">源 ${index + 1}</span>
                            <span class="quality-badge ${qualityClass}">${source.quality}</span>
                        </div>
                        <div class="source-actions">
                            <button class="copy-btn" onclick="copyToClipboard('${source.url.replace(/'/g, "\\'")}')">复制</button>
                            <button class="play-btn" onclick="playChannel('${source.url.replace(/'/g, "\\'")}', '${channel.name}')">播放</button>
                        </div>
                    </div>
                    `;
                });
                
                html += `
                    </div>
                </div>
                `;
            });
            
            container.innerHTML = html;
        }
        
        // 初始化搜索功能
        initSearch();
    </script>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"  ✅ index.html 生成成功，包含 {len(merged_channels)} 个电视台的交互界面")
except Exception as e:
    print(f"  ❌ 生成index.html失败: {e}")
    import traceback
    traceback.print_exc()

# 6. 生成README
print("\n📄 生成 README.md...")
try:
    readme_content = f"""# 📺 电视直播源项目 - 精简合并版

自动收集整理的电视直播源，支持同名电视台合并和多源切换。

## ✨ 主要特性

1. **智能合并** - 自动合并同名电视台的不同源
2. **多源切换** - 每个电视台支持多个播放源
3. **名称精简** - 清理冗余信息，统一命名格式
4. **自动分类** - 智能分类到9大类别
5. **每日更新** - 自动获取最新直播源

## 📊 统计信息
- **更新时间(北京时间)**: {timestamp}
- **电视台总数**: {len(merged_channels)} (合并后)
- **原始频道数**: {total_collected}
- **数据源**: {len(sources)} 个

## 🏷️ 分类统计

| 分类 | 电视台数量 | 说明 |
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
                "其他台": "未分类的电视台"
            }.get(category, "")
            
            readme_content += f"| {category} | {count} | {description} |\n"
    
    readme_content += f"""
| **总计** | **{len(merged_channels)}** | **所有电视台** |

## 📁 文件列表

### 主要文件
| 文件 | 描述 | 用途 |
|------|------|------|
| [live_sources.m3u](live_sources.m3u) | 完整版播放列表 | 包含所有电视台和多个源，适合需要源切换的用户 |
| [merged/精简版.m3u](merged/精简版.m3u) | 精简版播放列表 | 每个电视台只保留最佳源，适合普通用户 |
| [channels.json](channels.json) | 详细数据文件 | 包含所有电视台的详细信息和多源数据 |
| [index.html](index.html) | 网页播放界面 | 在线浏览和切换播放源 |

### 分类文件
进入 [categories/](categories/) 目录下载分类播放列表：

"""

    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        count = len(categories[category])
        if count > 0:
            readme_content += f"- [{category}.m3u](categories/{category}.m3u) - {count} 个电视台\n"
    
    readme_content += """

## 🚀 使用方法

### 快速开始
1. 下载 [merged/精简版.m3u](merged/精简版.m3u) 文件
2. 用播放器打开 (支持VLC、PotPlayer、IINA等)
3. 选择电视台观看

### 多源切换使用
1. 下载 [live_sources.m3u](live_sources.m3u) 文件
2. 在播放器中，同一个电视台会出现多次（代表不同源）
3. 如果某个源无法播放，尝试播放该电视台的其他源

### 在线使用
1. 访问 [index.html](index.html)
2. 浏览电视台列表
3. 点击"播放"按钮直接播放，或点击"复制"获取URL
4. 如果某个源无法播放，切换到该电视台的其他源

## ⚙️ 自定义配置

编辑 `sources.txt` 文件可以添加更多直播源URL，每行一个。

## 🔧 技术特点

### 频道名称处理
- 自动移除清晰度标记（4K、高清、标清等）
- 统一命名格式（CCTV1、湖南卫视等）
- 清理冗余信息（直播、频道、台等后缀）

### 智能合并
- 自动识别同名电视台
- 合并多个源的播放地址
- 保留所有源的清晰度信息

### 分类系统
- 9大分类：央视、卫视、地方台、少儿台、综艺台、港澳台、体育台、影视台、其他台
- 基于名称的智能分类
- 支持手动调整分类规则

## ⏰ 自动更新

- **定时更新**: 每天UTC 18:00（北京时间凌晨2点）自动运行
- **手动触发**: 在GitHub Actions页面手动运行工作流
- **源更新触发**: 修改 `sources.txt` 后自动触发

## ⚠️ 免责声明

本项目的直播源来自公开网络，仅用于学习和测试。
请遵守当地法律法规，尊重版权。

---
*自动生成于 {timestamp}*
"""
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("  ✅ README.md 生成成功")
except Exception as e:
    print(f"  ❌ 生成README.md失败: {e}")

print(f"\n🎉 所有文件生成完成！")
print(f"📊 统计:")
print(f"  - 电视台总数: {len(merged_channels)}")
print(f"  - 原始频道数: {total_collected}")
print(f"  - 数据源: {len(sources)}")
print(f"📁 生成的文件:")
print(f"  - live_sources.m3u (完整多源版)")
print(f"  - merged/精简版.m3u (精简最佳源版)")
print(f"  - channels.json (详细数据)")
print(f"  - index.html (交互网页)")
print(f"  - README.md (说明文档)")
print(f"  - categories/*.m3u (分类列表)")