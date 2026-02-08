#!/usr/bin/env python3
"""
分类规则定义模块
"""

import re
from channel_cleaner import chinese_to_arabic

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
}

# 频道排序配置
CHANNEL_ORDER_RULES = {
    # 央视按数字顺序
    "央视": {
        "CCTV-1 综合": 1, "CCTV-2 财经": 2, "CCTV-3 综艺": 3, "CCTV-4 中文国际": 4,
        "CCTV-5 体育": 5, "CCTV-5+ 体育赛事": 6, "CCTV-6 电影": 7, "CCTV-7 国防军事": 8,
        "CCTV-8 电视剧": 9, "CCTV-9 纪录": 10, "CCTV-10 科教": 11, "CCTV-11 戏曲": 12,
        "CCTV-12 社会与法": 13, "CCTV-13 新闻": 14, "CCTV-14 少儿": 15, "CCTV-15 音乐": 16,
        "CCTV-16 奥林匹克": 17, "CCTV-17 农业农村": 18, "CCTV-4K 超高清": 19
    },
    
    # 卫视按拼音顺序（常用卫视在前）
    "卫视": {
        "北京卫视": 1, "上海东方卫视": 2, "天津卫视": 3, "重庆卫视": 4,
        "河北卫视": 5, "山西卫视": 6, "辽宁卫视": 7, "吉林卫视": 8,
        "黑龙江卫视": 9, "江苏卫视": 10, "浙江卫视": 11, "安徽卫视": 12,
        "福建卫视": 13, "江西卫视": 14, "山东卫视": 15, "河南卫视": 16,
        "湖北卫视": 17, "湖南卫视": 18, "广东卫视": 19, "广西卫视": 20,
        "海南卫视": 21, "四川卫视": 22, "贵州卫视": 23, "云南卫视": 24,
        "陕西卫视": 25, "甘肃卫视": 26, "青海卫视": 27, "宁夏卫视": 28,
        "新疆卫视": 29, "内蒙古卫视": 30, "西藏卫视": 31
    }
}

# 省份列表（用于地方台分类）
PROVINCES = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省", "上海市", "江苏省",
    "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区",
    "海南省", "重庆市", "四川省", "贵州省", "云南省",
    "西藏自治区", "陕西省", "甘肃省", "青海省", "宁夏回族自治区",
    "新疆维吾尔自治区", "台湾省", "香港", "澳门"
]

# 省份简称映射
PROVINCE_ABBR = {
    "北京": "北京市", "天津": "天津市", "河北": "河北省", "山西": "山西省",
    "内蒙古": "内蒙古自治区", "辽宁": "辽宁省", "吉林": "吉林省", "黑龙江": "黑龙江省",
    "上海": "上海市", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "广西": "广西壮族自治区",
    "海南": "海南省", "重庆": "重庆市", "四川": "四川省", "贵州": "贵州省",
    "云南": "云南省", "西藏": "西藏自治区", "陕西": "陕西省", "甘肃": "甘肃省",
    "青海": "青海省", "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
    "台湾": "台湾省", "香港": "香港", "澳门": "澳门"
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
        r"^海南卫视$", r"^宁夏卫视$", r"^新疆卫视$", r"^内蒙古卫视$",
    ],
    
    # 景区频道（新增）
    "景区频道": [
        r"景区$",r"直播中国$" r"旅游$", r"风光$", r"景点$", r"导视$",
        r"^峨眉山", r"^九寨沟", r"^黄山", r"^泰山", r"^华山",
        r"^张家界", r"^西湖", r"^漓江", r"^鼓浪屿", r"^故宫",
        r"^长城", r"^兵马俑", r"^布达拉宫", r"^天安门", r"^外滩",
        r"^维多利亚港", r"^澳门塔", r"^日月潭", r"^阿里山",r"^黟县",
        r"^云台山",r"^雁荡山",r"^张家界"
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
    
    # 调频广播 - 新增分类
    "调频广播": [
        r"FM[_\-\s]?\d+",  # FM广播频率
        r"广播$", r"电台$", r"频率$",
        r"^中央人民广播电台", r"^中国之声", r"^经济之声",
        r"^音乐之声", r"^文艺之声", r"^交通广播",
        r"^都市广播", r"^新闻广播", r"^体育广播",
        r"^农村广播", r"^老年广播", r"^少儿广播",
        r"^教育广播", r"^故事广播", r"^戏曲广播",
        r"^经典音乐广播", r"^流行音乐广播", r"^欧美音乐广播",
        r"^华语音乐广播", r"^粤语广播", r"^方言广播",
        r"^国际广播", r"^外语广播", r"^英语广播",
        r"^日语广播", r"^韩语广播", r"^法语广播",
        r"^德语广播", r"^俄语广播", r"^西语广播",
        r"^阿拉伯语广播", r"^葡萄牙语广播", r"^意大利语广播"
    ],
    
    # 歌曲MV - 新增分类
    "歌曲MV": [
        r"MV$", r"音乐电视$", r"MTV$", r"歌曲$",
        r"^流行音乐$", r"^摇滚音乐$", r"^古典音乐$",
        r"^民族音乐$", r"^轻音乐$", r"^纯音乐$",
        r"^背景音乐$", r"^钢琴曲$", r"^小提琴$",
        r"^吉他$", r"^萨克斯$", r"^爵士乐$",
        r"^蓝调$", r"^乡村音乐$", r"^电子音乐$",
        r"^舞曲$", r"^DJ$", r"^混音$",
        r"^原声$", r"^OST$", r"^演唱会$",
        r"^音乐会$", r"^音乐节$", r"^KTV$",
        r"^卡拉OK$", r"^伴奏$", r"^铃声$",
        r"^彩铃$", r"^手机铃声$", r"^来电铃声$",
        r"周深$", r"飞轮海$", r"精选$", r"音乐$",r"合集$",r"静心系列$"
    ],
}

def get_source_priority(source_info):
    """获取源的优先级分数（用于排序）"""
    priority = 0
    
    # IPv6源最高优先级（+100分）
    if source_info.get('is_ipv6', False):
        priority += 100
    
    # 速度评分优先级（如果测速功能启用）
    from config.config_loader import load_config
    config = load_config()
    if config['ENABLE_SPEED_TEST'] and 'speed_score' in source_info:
        score = source_info['speed_score']
        if score >= 0.9:
            priority += 50
        elif score >= 0.7:
            priority += 30
        elif score >= 0.5:
            priority += 10
    
    # 清晰度优先级
    quality_scores = {
        "4K": 40,
        "高清": 30,
        "标清": 20,
        "流畅": 10,
        "未知": 0
    }
    priority += quality_scores.get(source_info['quality'], 0)
    
    # 源质量标记优先级
    url_lower = source_info['url'].lower()
    if any(marker in url_lower for marker in ['cdn', 'akamai', 'cloudfront']):
        priority += 5  # CDN源加分
    if 'https://' in url_lower:
        priority += 3  # HTTPS源加分
    if 'm3u8' in url_lower:
        priority += 2  # HLS源加分
    
    # 白名单源额外加分
    if source_info.get('is_whitelist', False):
        priority += 80  # 白名单源优先级仅次于IPv6
    
    return priority

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

def get_channel_sort_key(channel_name, category):
    """获取频道排序键值"""
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