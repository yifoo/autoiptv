#!/usr/bin/env python3
"""
频道处理模块
"""
import re
from .config import CLEAN_RULES, CCTV_MAPPING, CATEGORY_RULES, PROVINCES, PROVINCE_ABBR
from .utils import chinese_to_arabic


def standardize_cctv_name(name):
    """标准化CCTV频道名称，确保CCTV大写"""
    original_name = name
    
    # 将cctv小写转为大写
    if 'cctv' in name.lower():
        name = re.sub(r'cctv', 'CCTV', name, flags=re.IGNORECASE)
    
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
    """深度清理频道名称，移除冗余信息，统一CCTV大写"""
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
    
    # 强制将cctv转为CCTV（大小写统一）
    if 'cctv' in name.lower():
        name = re.sub(r'cctv', 'CCTV', name, flags=re.IGNORECASE)
    
    # 最终清理
    name = re.sub(r'\s+', ' ', name)  # 合并多个空格
    name = name.strip()
    
    # 如果清理后为空，使用原始名称
    if not name or len(name) < 2:
        name = original_name
    
    return name


def get_channel_sort_key(channel_name, category):
    """获取频道排序键值"""
    from .config import CHANNEL_ORDER_RULES
    
    if category in CHANNEL_ORDER_RULES:
        if channel_name in CHANNEL_ORDER_RULES[category]:
            return (0, CHANNEL_ORDER_RULES[category][channel_name])
        else:
            # 查找匹配的模式
            for pattern, order in CHANNEL_ORDER_RULES[category].items():
                if pattern in channel_name:
                    return (1, order, channel_name)
    
    # 按字母顺序排序
    return (2, channel_name)


def categorize_channel(channel_name):
    """为频道分类，支持省份分类"""
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
    
    # 尝试匹配省份分类
    for province_full in PROVINCES:
        if province_full in channel_name:
            return province_full
    
    # 尝试匹配省份简称
    for abbr, full in PROVINCE_ABBR.items():
        if abbr in channel_name and len(abbr) >= 2:
            return full
    
    # 如果没有匹配到任何规则，返回"其他台"
    return "其他台"


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
            quality_patterns = [
                (r'4K|超清|UHD|2160', "4K"),
                (r'高清|HD|1080|FHD', "高清"),
                (r'标清|SD|720', "标清"),
                (r'流畅|360|480', "流畅")
            ]
            
            for pattern, q in quality_patterns:
                if re.search(pattern, name, re.IGNORECASE):
                    quality = q
                    break
            
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
    """合并同名电视台，支持多源，IPv6优先排序"""
    from .utils import is_ipv6_url, get_source_priority
    
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
                    'is_ipv6': False,  # 稍后计算
                    'speed': speed_test_results.get(channel['url'], None) if speed_test_results else None
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
                    'priority': 0,  # 稍后计算
                    'is_ipv6': False,  # 稍后计算
                    'speed': speed_test_results.get(channel['url'], None) if speed_test_results else None
                })
            
            # 收集logo
            if channel['logo'] and channel['logo'] not in merged[key]['logos']:
                merged[key]['logos'].append(channel['logo'])
            
            # 更新分类
            category = categorize_channel(key)
            merged[key]['categories'].add(category)
    
    # 为每个频道的源计算优先级并排序
    for key in merged:
        # 计算每个源的优先级和IPv6状态
        for source in merged[key]['sources']:
            source['is_ipv6'] = is_ipv6_url(source['url'])
            source['priority'] = get_source_priority(source)
        
        # 按优先级降序排序（优先级高的在前，IPv6优先）
        merged[key]['sources'].sort(key=lambda x: x['priority'], reverse=True)
        
        # 为每个合并后的频道选择一个主分类
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