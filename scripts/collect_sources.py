#!/usr/bin/env python3
"""
电视直播源收集脚本 - 精简合并版
功能：1. 频道名称精简 2. 同名电视台合并 3. 支持多源切换 4. 统一央视频道命名
特点：所有电视源统一从sources.txt文件获取
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
print("电视直播源收集脚本 v3.1 - 深度精简合并版")
print("功能：频道名称深度精简、统一央视频道命名、支持多源切换")
print("特点：所有电视源统一从sources.txt文件获取")
print("=" * 70)

def load_sources_from_file():
    """从sources.txt文件加载所有电视源"""
    sources_file = "sources.txt"
    sources = []
    
    if not os.path.exists(sources_file):
        print(f"❌ 错误: {sources_file} 文件不存在")
        print(f"📝 请创建 {sources_file} 文件，每行添加一个M3U文件URL")
        return sources
    
    try:
        with open(sources_file, "r", encoding="utf-8") as f:
            line_number = 0
            for line in f:
                line_number += 1
                line = line.strip()
                
                # 跳过空行和注释行
                if not line:
                    continue
                if line.startswith("#"):
                    continue
                
                # 验证URL格式
                if line.startswith("http://") or line.startswith("https://"):
                    sources.append(line)
                else:
                    print(f"⚠️  第{line_number}行格式错误，跳过: {line}")
        
        print(f"📡 从 {sources_file} 加载了 {len(sources)} 个数据源")
        
        if len(sources) == 0:
            print(f"❌ 错误: {sources_file} 中没有找到有效的URL")
            print(f"📝 请在 {sources_file} 中添加M3U文件URL，格式: https://example.com/live.m3u")
        
    except Exception as e:
        print(f"❌ 读取 {sources_file} 失败: {e}")
    
    return sources

# 从sources.txt文件加载所有源
sources = load_sources_from_file()

if len(sources) == 0:
    print("❌ 没有可用的数据源，退出")
    sys.exit(1)

# 频道名称清理规则 - 深度精简
CLEAN_RULES = [
    # 移除技术参数标记
    (r'50\s*FPS', ''),  # 移除50 FPS
    (r'HEVC', ''),  # 移除HEVC
    (r'H\.?264', ''),  # 移除H.264
    (r'H\.?265', ''),  # 移除H.265
    (r'AAC', ''),  # 移除AAC
    (r'AC3', ''),  # 移除AC3
    (r'[\[\(][^\]\)]*[\]\)]', ''),  # 移除所有括号内容
    (r'【[^】]*】', ''),  # 移除所有中文括号内容
    
    # 移除清晰度标记
    (r'[_\-\s]?4K[_\-\s]?', ' '),  # 移除4K标记
    (r'[_\-\s]?高清[_\-\s]?', ' '),  # 移除高清标记
    (r'[_\-\s]?HD[_\-\s]?', ' '),  # 移除HD标记
    (r'[_\-\s]?超清[_\-\s]?', ' '),  # 移除超清标记
    (r'[_\-\s]?标清[_\-\s]?', ' '),  # 移除标清标记
    (r'[_\-\s]?流畅[_\-\s]?', ' '),  # 移除流畅标记
    (r'[_\-\s]?1080[Pp]?[_\-\s]?', ' '),  # 移除1080P标记
    (r'[_\-\s]?720[Pp]?[_\-\s]?', ' '),  # 移除720P标记
    
    # 移除协议标记
    (r'[_\-\s]?IPV6[_\-\s]?', ' '),  # 移除IPV6标记
    (r'[_\-\s]?IPV4[_\-\s]?', ' '),  # 移除IPV4标记
    (r'[_\-\s]?HLS[_\-\s]?', ' '),  # 移除HLS标记
    (r'[_\-\s]?RTMP[_\-\s]?', ' '),  # 移除RTMP标记
    (r'[_\-\s]?RTSP[_\-\s]?', ' '),  # 移除RTSP标记
    (r'[_\-\s]?FLV[_\-\s]?', ' '),  # 移除FLV标记
    
    # 移除冗余词
    (r'\s+直播$', ''),  # 移除"直播"后缀
    (r'\s+频道$', ''),  # 移除"频道"后缀
    (r'\s+台$', ''),  # 移除"台"后缀
    (r'\s+电视台$', ''),  # 移除"电视台"后缀
    (r'\s+卫视台$', '卫视'),  # 卫视台改为卫视
    
    # 统一符号
    (r'\s+', ' '),  # 多个空格合并为一个
    (r'^\s+|\s+$', ''),  # 去除首尾空格
    (r'[_\-\|]+', ' '),  # 统一分隔符为空格
    (r'\s*&\s*', ' '),  # &符号替换为空格
]

# 央视频道标准化映射
CCTV_MAPPING = {
    # 标准CCTV数字频道
    r'^CCTV[_\-\s]?1$': 'CCTV-1 综合',
    r'^CCTV[_\-\s]?2$': 'CCTV-2 财经',
    r'^CCTV[_\-\s]?3$': 'CCTV-3 综艺',
    r'^CCTV[_\-\s]?4$': 'CCTV-4 中文国际',
    r'^CCTV[_\-\s]?5$': 'CCTV-5 体育',
    r'^CCTV[_\-\s]?5\+$': 'CCTV-5+ 体育赛事',
    r'^CCTV[_\-\s]?6$': 'CCTV-6 电影',
    r'^CCTV[_\-\s]?7$': 'CCTV-7 国防军事',
    r'^CCTV[_\-\s]?8$': 'CCTV-8 电视剧',
    r'^CCTV[_\-\s]?9$': 'CCTV-9 纪录',
    r'^CCTV[_\-\s]?10$': 'CCTV-10 科教',
    r'^CCTV[_\-\s]?11$': 'CCTV-11 戏曲',
    r'^CCTV[_\-\s]?12$': 'CCTV-12 社会与法',
    r'^CCTV[_\-\s]?13$': 'CCTV-13 新闻',
    r'^CCTV[_\-\s]?14$': 'CCTV-14 少儿',
    r'^CCTV[_\-\s]?15$': 'CCTV-15 音乐',
    r'^CCTV[_\-\s]?16$': 'CCTV-16 奥林匹克',
    r'^CCTV[_\-\s]?17$': 'CCTV-17 农业农村',
    
    # 央视中文数字频道
    r'^CCTV[一二三四五六七八九十]$': 'CCTV-{num}',
    r'^央视[一二三四五六七八九十]$': 'CCTV-{num}',
    r'^中央电视台[一二三四五六七八九十]?$': 'CCTV-1 综合',
    
    # 央视高清/4K频道
    r'^CCTV4K$': 'CCTV-4K 超高清',
    r'^CCTV8K$': 'CCTV-8K 超高清',
    r'^CCTV[_\-\s]?高清$': 'CCTV-高清',
    
    # 央视其他频道
    r'^CCTV[_\-\s]?戏曲$': 'CCTV-11 戏曲',
    r'^CCTV[_\-\s]?音乐$': 'CCTV-15 音乐',
    r'^CCTV[_\-\s]?少儿$': 'CCTV-14 少儿',
    r'^CCTV[_\-\s]?新闻$': 'CCTV-13 新闻',
    r'^CCTV[_\-\s]?纪录$': 'CCTV-9 纪录',
    r'^CCTV[_\-\s]?体育$': 'CCTV-5 体育',
    r'^CCTV[_\-\s]?电影$': 'CCTV-6 电影',
    r'^CCTV[_\-\s]?电视剧$': 'CCTV-8 电视剧',
    r'^CCTV[_\-\s]?综艺$': 'CCTV-3 综艺',
    r'^CCTV[_\-\s]?财经$': 'CCTV-2 财经',
    
    # 地方卫视统一命名
    r'^北京卫视$': '北京卫视',
    r'^湖南卫视$': '湖南卫视',
    r'^浙江卫视$': '浙江卫视',
    r'^江苏卫视$': '江苏卫视',
    r'^东方卫视$': '东方卫视',
    r'^天津卫视$': '天津卫视',
    r'^安徽卫视$': '安徽卫视',
    r'^山东卫视$': '山东卫视',
    r'^广东卫视$': '广东卫视',
    r'^深圳卫视$': '深圳卫视',
    r'^黑龙江卫视$': '黑龙江卫视',
    r'^辽宁卫视$': '辽宁卫视',
    r'^湖北卫视$': '湖北卫视',
    r'^河南卫视$': '河南卫视',
    r'^四川卫视$': '四川卫视',
    r'^重庆卫视$': '重庆卫视',
}

# 中文数字到阿拉伯数字映射
CHINESE_NUMBERS = {
    '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
    '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
    '十一': '11', '十二': '12', '十三': '13', '十四': '14', '十五': '15',
    '十六': '16', '十七': '17'
}

# 分类规则 - 按优先级顺序匹配
CATEGORY_RULES = {
    # 央视 - 最具体，最先匹配
    "央视": [
        r"^CCTV[-\s]?[\d一二三四五六七八九十]+",  # CCTV1, CCTV-1, CCTV一
        r"^央视[一二三四五六七八九十]+",  # 央视一, 央视二
        r"^中央电视台",  # 中央电视台
        r"^CCTV[-\s]?4K", r"^CCTV[-\s]?8K", r"^CCTV[-\s]?5\+",
        r"^CCTV[-\s]?综合$", r"^CCTV[-\s]?财经$", r"^CCTV[-\s]?综艺$",
        r"^CCTV[-\s]?体育$", r"^CCTV[-\s]?电影$", r"^CCTV[-\s]?电视剧$",
    ],
    
    # 卫视
    "卫视": [
        r"卫视$",  # 以"卫视"结尾
        r"^北京卫视$", r"^湖南卫视$", r"^浙江卫视$", r"^江苏卫视$",
        r"^东方卫视$", r"^天津卫视$", r"^安徽卫视$", r"^山东卫视$",
        r"^广东卫视$", r"^深圳卫视$", r"^黑龙江卫视$", r"^辽宁卫视$",
        r"^湖北卫视$", r"^河南卫视$", r"^四川卫视$", r"^重庆卫视$",
        r"^江西卫视$", r"^广西卫视$", r"^东南卫视$", r"^贵州卫视$",
        r"^云南卫视$", r"^陕西卫视$", r"^山西卫视$", r"^河北卫视$",
    ],
    
    # 少儿台
    "少儿台": [
        r"少儿$", r"卡通$", r"动漫$", r"动画$", r"金鹰卡通",
        r"卡酷少儿", r"哈哈炫动", r"优漫卡通", r"嘉佳卡通",
        r"炫动卡通", r"宝贝"
    ],
    
    # 综艺台
    "综艺台": [
        r"综艺$", r"文艺$", r"娱乐$", r"音乐$", r"戏曲$",
        r"相声$", r"小品$", r"文化$", r"艺术$"
    ],
    
    # 港澳台
    "港澳台": [
        r"凤凰", r"翡翠", r"明珠", r"TVB", r"ATV", r"澳视",
        r"澳门", r"香港", r"台湾", r"中天", r"东森", r"华视",
        r"民视", r"三立", r"无线"
    ],
    
    # 体育台
    "体育台": [
        r"体育$", r"足球$", r"篮球$", r"NBA", r"CBA", r"英超",
        r"欧冠$", r"高尔夫$", r"网球$", r"乒羽$", r"搏击$",
        r"赛车$", r"F1$", r"奥运$", r"赛事$"
    ],
    
    # 影视台
    "影视台": [
        r"电影$", r"影院$", r"影视频道$", r"好莱坞$", r"CHC",
        r"家庭影院$", r"动作电影$", r"喜剧电影$"
    ],
    
    # 地方台
    "地方台": [
        r"新闻$", r"都市$", r"民生$", r"公共$", r"经济$",
        r"法制$", r"农业$", r"交通$", r"城市$", r"省会$",
        r"地方$"
    ]
}

def get_beijing_time():
    """获取东八区北京时间"""
    utc_now = datetime.now(timezone.utc)
    beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

def chinese_to_arabic(chinese_num):
    """中文数字转阿拉伯数字"""
    if chinese_num in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[chinese_num]
    return chinese_num

def standardize_cctv_name(name):
    """标准化CCTV频道名称"""
    original_name = name
    
    # 首先尝试匹配CCTV_MAPPING中的规则
    for pattern, replacement in CCTV_MAPPING.items():
        if re.match(pattern, name, re.IGNORECASE):
            if '{num}' in replacement:
                # 提取数字部分
                match = re.search(r'[\d一二三四五六七八九十]+', name)
                if match:
                    num = chinese_to_arabic(match.group())
                    return replacement.replace('{num}', num)
            return replacement
    
    # 处理CCTV-数字格式
    cctv_match = re.match(r'^CCTV[_\-\s]?([\d一二三四五六七八九十]+)(?:\s+(.+))?$', name, re.IGNORECASE)
    if cctv_match:
        num = chinese_to_arabic(cctv_match.group(1))
        suffix = cctv_match.group(2) or ""
        
        # 根据数字确定频道名称
        cctv_names = {
            '1': '综合', '2': '财经', '3': '综艺', '4': '中文国际',
            '5': '体育', '5+': '体育赛事', '6': '电影', '7': '国防军事',
            '8': '电视剧', '9': '纪录', '10': '科教', '11': '戏曲',
            '12': '社会与法', '13': '新闻', '14': '少儿', '15': '音乐',
            '16': '奥林匹克', '17': '农业农村'
        }
        
        if num in cctv_names:
            channel_name = cctv_names[num]
            return f"CCTV-{num} {channel_name}"
        else:
            if suffix:
                return f"CCTV-{num} {suffix}"
            else:
                return f"CCTV-{num}"
    
    # 处理央视开头
    if name.startswith('央视'):
        match = re.match(r'^央视([一二三四五六七八九十]+)(?:\s+(.+))?$', name)
        if match:
            num = chinese_to_arabic(match.group(1))
            suffix = match.group(2) or ""
            return f"CCTV-{num} {suffix}"
    
    return original_name

def clean_channel_name(name):
    """深度清理频道名称，移除冗余信息"""
    original_name = name
    
    # 深度清理：应用所有清理规则
    for pattern, replacement in CLEAN_RULES:
        name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
    
    # 额外清理：移除重复词
    name = re.sub(r'\b(\w+)(?:\s+\1)+\b', r'\1', name)
    
    # 标准化CCTV名称
    if re.match(r'^(CCTV|央视|中央电视台)', name, re.IGNORECASE):
        name = standardize_cctv_name(name)
    
    # 统一卫视命名
    if name.endswith('卫视') and len(name) > 2:
        # 移除卫视前的多余空格
        name = re.sub(r'\s+卫视$', '卫视', name)
    
    # 最终清理
    name = re.sub(r'\s+', ' ', name)  # 合并多个空格
    name = name.strip()
    
    # 如果清理后为空，使用原始名称
    if not name or len(name) < 2:
        name = original_name
    
    return name

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
            
            # 检查URL是否已存在，避免重复
            urls = [s['url'] for s in merged[key]['sources']]
            if channel['url'] not in urls:
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
print(f"📋 数据源列表 (从sources.txt加载):")
for i, source in enumerate(sources, 1):
    print(f"  {i:2d}. {source}")

all_channels = []
success_sources = 0
failed_sources = []

for idx, source_url in enumerate(sources, 1):
    print(f"\n[{idx}/{len(sources)}] 处理: {source_url}")
    
    content = fetch_m3u(source_url)
    if not content:
        failed_sources.append(source_url)
        print("   ❌ 无法获取内容，跳过")
        continue
    
    channels = parse_channels(content, source_url)
    
    # 统计频道名称变化
    changed_count = 0
    for channel in channels:
        if channel['original_name'] != channel['clean_name']:
            changed_count += 1
    
    print(f"   ✅ 解析到 {len(channels)} 个频道 ({changed_count}个已精简)")
    
    if changed_count > 0 and len(channels) <= 10:
        for channel in channels[:5]:
            if channel['original_name'] != channel['clean_name']:
                print(f"      '{channel['original_name']}' -> '{channel['clean_name']}'")
    
    all_channels.extend(channels)
    success_sources += 1
    
    # 避免请求过快
    if idx < len(sources):
        time.sleep(1)

print(f"\n{'='*50}")
print(f"✅ 采集完成统计:")
print(f"   成功源数: {success_sources}/{len(sources)}")
print(f"   失败源数: {len(failed_sources)}")
print(f"   总计采集: {len(all_channels)} 个原始频道")

if len(failed_sources) > 0:
    print(f"\n⚠️  失败的源:")
    for failed in failed_sources:
        print(f"   - {failed}")

if len(all_channels) == 0:
    print("\n❌ 没有采集到任何频道，退出")
    sys.exit(1)

# 合并同名电视台
print("\n🔄 正在合并同名电视台...")
merged_channels = merge_channels(all_channels)
print(f"   合并后: {len(merged_channels)} 个唯一电视台")

# 显示一些合并示例
print("\n📝 合并示例:")
merged_examples = list(merged_channels.items())[:5]
for clean_name, data in merged_examples:
    source_count = len(data['sources'])
    if source_count > 1:
        print(f"   {clean_name}: {source_count}个源")

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
        f.write(f"# 电视直播源 - 深度精简合并版\n")
        f.write(f"# 更新时间(北京时间): {timestamp}\n")
        f.write(f"# 电视台总数: {len(merged_channels)}\n")
        f.write(f"# 原始频道数: {len(all_channels)}\n")
        f.write(f"# 数据源: {len(sources)} 个 (成功: {success_sources}, 失败: {len(failed_sources)})\n")
        f.write(f"# 说明: 同名电视台已合并，支持多源切换\n")
        f.write(f"# 特点: 移除技术参数，统一央视频道命名\n")
        f.write(f"# 源文件: sources.txt\n\n")
        
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
                    if source_count > 1:
                        display_name = f"{channel['clean_name']} [{source_count}源]"
                    else:
                        display_name = channel['clean_name']
                    
                    # 写入第一个源
                    main_source = channel['sources'][0]
                    line = "#EXTINF:-1"
                    line += f' tvg-name="{channel["clean_name"]}"'
                    line += f' group-title="{category}"'
                    if main_logo:
                        line += f' tvg-logo="{main_logo}"'
                    if main_source['quality'] != "未知":
                        line += f' tvg-quality="{main_source["quality"]}"'
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
                            if source['quality'] != "未知":
                                alt_line += f' tvg-quality="{source["quality"]}"'
                            alt_line += f',{channel["clean_name"]} [源{i}]\n'
                            alt_line += f"{source['url']}\n"
                            f.write(alt_line)
    
    print(f"  ✅ live_sources.m3u 生成成功，包含 {len(merged_channels)} 个电视台")
except Exception as e:
    print(f"  ❌ 生成live_sources.m3u失败: {e}")

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
                    
                    if source_count > 1:
                        display_name = f"{channel['clean_name']} [{source_count}源]"
                    else:
                        display_name = channel['clean_name']
                    
                    # 写入第一个源
                    main_source = channel['sources'][0]
                    line = "#EXTINF:-1"
                    line += f' tvg-name="{channel["clean_name"]}"'
                    line += f' group-title="{category}"'
                    if main_logo:
                        line += f' tvg-logo="{main_logo}"'
                    if main_source['quality'] != "未知":
                        line += f' tvg-quality="{main_source["quality"]}"'
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
        'original_channel_count': len(all_channels),
        'sources_count': len(sources),
        'success_sources': success_sources,
        'failed_sources': failed_sources,
        'category_stats': category_stats,
        'channels': channel_list,
        'source_file': 'sources.txt'
    }
    
    # 写入文件
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"  ✅ channels.json 生成成功，包含 {len(merged_channels)} 个电视台的详细信息")
except Exception as e:
    print(f"  ❌ 生成channels.json失败: {e}")

# 4. 生成精简版M3U（每个电视台只保留最佳源）
print("\n📄 生成 merged/精简版.m3u...")
try:
    with open("merged/精简版.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# 电视直播源 - 精简版\n")
        f.write(f"# 更新时间(北京时间): {timestamp}\n")
        f.write(f"# 电视台总数: {len(merged_channels)}\n")
        f.write(f"# 说明: 每个电视台只保留最佳源\n")
        f.write(f"# 特点: 移除技术参数，统一央视频道命名\n")
        f.write(f"# 源文件: sources.txt\n\n")
        
        for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
            cat_channels = categories[category]
            if cat_channels:
                f.write(f"\n# {category} ({len(cat_channels)}个电视台)\n")
                
                for channel in sorted(cat_channels, key=lambda x: x['clean_name']):
                    # 选择最佳源（优先选择高清源）
                    best_source = None
                    for source in channel['sources']:
                        if source['quality'] == "4K":
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
                    if best_source['quality'] != "未知":
                        line += f' tvg-quality="{best_source["quality"]}"'
                    line += f',{channel["clean_name"]}\n'
                    line += f"{best_source['url']}\n"
                    f.write(line)
    
    print(f"  ✅ 精简版.m3u 生成成功")
except Exception as e:
    print(f"  ❌ 生成精简版.m3u失败: {e}")

# 5. 生成HTML页面
print("\n📄 生成 index.html...")
try:
    # 简化频道数据用于JavaScript
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
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源 - 深度精简合并版</title>
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
        
        .features-list {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin: 20px 0;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }}
        
        .features-list ul {{
            list-style: none;
            padding: 0;
        }}
        
        .features-list li {{
            padding: 8px 0;
            display: flex;
            align-items: center;
        }}
        
        .features-list li:before {{
            content: "✓";
            color: var(--success-color);
            font-weight: bold;
            margin-right: 10px;
        }}
        
        footer {{
            text-align: center;
            padding: 30px;
            color: #7f8c8d;
            font-size: 0.9rem;
            background: white;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-top: 30px;
        }}
        
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .download-buttons {{
                flex-direction: column;
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
            <h1>📺 电视直播源 - 深度精简合并版</h1>
            <p class="subtitle">移除技术参数 | 统一央视频道命名 | 支持多源切换</p>
            <div style="margin-top: 15px; font-size: 0.9rem; opacity: 0.8;">
                <p>更新时间(北京时间): {timestamp}</p>
                <p>源文件: sources.txt</p>
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" style="color: #667eea;">{len(merged_channels)}</div>
                <div>电视台总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #e74c3c;">{len(all_channels)}</div>
                <div>原始频道数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #27ae60;">{len(sources)}</div>
                <div>数据源数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" style="color: #9b59b6;">{success_sources}</div>
                <div>成功源数</div>
            </div>
        </div>
        
        <div class="features-list">
            <h3 style="color: var(--primary-color); margin-bottom: 15px;">✨ 主要特点</h3>
            <ul>
                <li>移除技术参数: 50 FPS、HEVC、H.264等</li>
                <li>统一央视频道命名: CCTV-1 综合、CCTV-2 财经等</li>
                <li>深度清理冗余信息: 直播、频道、台等后缀</li>
                <li>智能合并同名电视台: 自动识别和合并</li>
                <li>支持多源切换: 每个电视台可能有多个播放源</li>
                <li>智能分类: 自动分类到9大类别</li>
            </ul>
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
            
            <div style="margin-top: 25px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <p style="color: #666; margin: 0; font-size: 0.9rem;">
                    <strong>💡 使用提示:</strong> 
                    <br>• 完整版: 包含所有源，适合需要切换源的用户
                    <br>• 精简版: 每个电视台只保留最佳源，适合普通用户
                    <br>• JSON数据: 包含所有电视台的详细信息
                </p>
            </div>
        </div>
        
        <div class="features-list">
            <h3 style="color: var(--primary-color); margin-bottom: 15px;">📋 分类统计</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
"""
    
    # 添加分类统计
    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        count = len(categories[category])
        if count > 0:
            html_content += f"""                <div style="text-align: center;">
                    <div style="font-size: 1.5rem; font-weight: bold; color: var(--primary-color);">{count}</div>
                    <div style="font-size: 0.9rem; color: #666;">{category}</div>
                </div>
"""
    
    html_content += f"""            </div>
        </div>
        
        <div style="margin: 30px 0; text-align: center;">
            <h3 style="color: var(--primary-color); margin-bottom: 15px;">🎯 央视频道命名示例</h3>
            <div style="display: inline-block; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.05);">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; text-align: left;">
                    <div>
                        <div style="color: #666; font-size: 0.9rem;">原始名称</div>
                        <div style="color: #e74c3c;">→</div>
                        <div style="color: #666; font-size: 0.9rem;">精简后名称</div>
                    </div>
                    <div>
                        <div>CCTV1 4K HEVC</div>
                        <div style="color: #e74c3c; text-align: center;">→</div>
                        <div>CCTV-1 综合</div>
                    </div>
                    <div>
                        <div>央视二台 高清</div>
                        <div style="color: #e74c3c; text-align: center;">→</div>
                        <div>CCTV-2 财经</div>
                    </div>
                    <div>
                        <div>CCTV5+ 体育 50FPS</div>
                        <div style="color: #e74c3c; text-align: center;">→</div>
                        <div>CCTV-5+ 体育赛事</div>
                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            <p>🔄 本项目自动更新于 GitHub Actions | 最后更新(北京时间): {timestamp}</p>
            <p>🎮 支持播放器: VLC、PotPlayer、IINA、nPlayer、Kodi、TiviMate等</p>
            <p style="margin-top: 15px; font-size: 0.8rem; color: #bdc3c7;">
                💡 提示: 如需修改数据源，请编辑 <code>sources.txt</code> 文件
            </p>
            <div id="currentTime" style="margin-top: 15px; font-size: 0.8rem; color: #95a5a6;"></div>
        </footer>
    </div>
    
    <script>
        // 显示当前北京时间
        function updateTime() {{
            const now = new Date();
            const beijingTime = new Date(now.getTime() + 8 * 60 * 60 * 1000);
            const timeStr = beijingTime.toISOString().replace('T', ' ').substring(0, 19);
            const timeElement = document.getElementById('currentTime');
            if (timeElement) {{
                timeElement.textContent = `当前北京时间: \${timeStr}`;
            }}
        }}
        
        // 每5秒更新一次时间
        setInterval(updateTime, 5000);
        updateTime();
    </script>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"  ✅ index.html 生成成功")
except Exception as e:
    print(f"  ❌ 生成index.html失败: {e}")

# 6. 生成README
print("\n📄 生成 README.md...")
try:
    readme_content = f"""# 📺 电视直播源项目 - 深度精简合并版

自动收集整理的电视直播源，支持深度精简和统一命名。

## ✨ 主要特性

### 1. **深度名称精简**
- 移除技术参数: `50 FPS`、`HEVC`、`H.264`、`AAC`等
- 移除清晰度标记: `4K`、`高清`、`HD`、`标清`等
- 移除协议标记: `IPV6`、`HLS`、`RTMP`等
- 清理冗余后缀: `直播`、`频道`、`台`等

### 2. **统一央视频道命名**
- `CCTV1` → `CCTV-1 综合`
- `央视二台` → `CCTV-2 财经`
- `CCTV5+ 体育` → `CCTV-5+ 体育赛事`
- `CCTV4K` → `CCTV-4K 超高清`

### 3. **智能合并**
- 自动识别和合并同名电视台
- 保留所有源的播放地址
- 支持多源切换功能

### 4. **智能分类**
- 9大分类: 央视、卫视、地方台、少儿台、综艺台、港澳台、体育台、影视台、其他台
- 基于名称的智能分类
- 支持手动调整分类规则

## 📊 统计信息
- **更新时间(北京时间)**: {timestamp}
- **电视台总数**: {len(merged_channels)} (合并后)
- **原始频道数**: {len(all_channels)}
- **数据源**: {len(sources)} 个
- **成功源数**: {success_sources}
- **失败源数**: {len(failed_sources)}

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
| [index.html](index.html) | 网页统计界面 | 查看统计信息和下载文件 |
| [sources.txt](sources.txt) | 数据源配置文件 | 编辑此文件可添加或修改数据源 |

### 分类文件
进入 [categories/](categories/) 目录下载分类播放列表：

"""

    for category in ["央视", "卫视", "地方台", "少儿台", "综艺台", "港澳台", "体育台", "影视台", "其他台"]:
        count = len(categories[category])
        if count > 0:
            readme_content += f"- [{category}.m3u](categories/{category}.m3u) - {count} 个电视台\n"
    
    readme_content += f"""

## 🚀 使用方法

### 快速开始
1. 下载 [merged/精简版.m3u](merged/精简版.m3u) 文件
2. 用播放器打开 (支持VLC、PotPlayer、IINA等)
3. 选择电视台观看

### 多源切换使用
1. 下载 [live_sources.m3u](live_sources.m3u) 文件
2. 在播放器中，同一个电视台会出现多次（代表不同源）
3. 如果某个源无法播放，尝试播放该电视台的其他源

### 央视频道示例
- `CCTV-1 综合` - 中央电视台综合频道
- `CCTV-2 财经` - 中央电视台财经频道
- `CCTV-5 体育` - 中央电视台体育频道
- `CCTV-6 电影` - 中央电视台电影频道
- `CCTV-5+ 体育赛事` - 中央电视台体育赛事频道
- `CCTV-4K 超高清` - 中央电视台4K超高清频道

## ⚙️ 自定义配置

编辑 `sources.txt` 文件可以添加更多直播源URL，每行一个。

### sources.txt 格式示例
电视直播源列表
每行一个M3U文件URL
https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u
https://raw.githubusercontent.com/chao921125/source/refs/heads/main/iptv/index.m3u

可添加更多源
https://example.com/live.m3u


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
print(f"  - 原始频道数: {len(all_channels)}")
print(f"  - 数据源: {len(sources)}")
print(f"📁 生成的文件:")
print(f"  - live_sources.m3u (完整多源版)")
print(f"  - merged/精简版.m3u (精简最佳源版)")
print(f"  - channels.json (详细数据)")
print(f"  - index.html (统计网页)")
print(f"  - README.md (说明文档)")
print(f"  - categories/*.m3u (分类列表)")