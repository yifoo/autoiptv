#!/usr/bin/env python3
"""
工具函数模块
"""
import re
import ipaddress
from datetime import datetime, timezone, timedelta
import requests


def get_beijing_time():
    """获取东八区北京时间"""
    utc_now = datetime.now(timezone.utc)
    beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')


def is_ipv6_url(url):
    """检测URL是否为IPv6地址"""
    try:
        # 从URL中提取主机名
        if '://' in url:
            hostname = url.split('://')[1].split('/')[0]
        else:
            hostname = url.split('/')[0]
        
        # 移除端口号
        if ':' in hostname:
            # 处理IPv6地址的端口号格式 [::1]:8080
            if hostname.startswith('['):
                # IPv6地址带端口
                ip_part = hostname.split(']')[0][1:]
            else:
                ip_part = hostname.split(':')[0]
        else:
            ip_part = hostname
        
        # 尝试解析为IPv6地址
        ipaddress.IPv6Address(ip_part)
        return True
    except:
        # 也检查URL中是否包含IPv6关键字
        url_lower = url.lower()
        if 'ipv6' in url_lower or 'ip6' in url_lower or 'v6' in url_lower:
            return True
        # 检查是否包含IPv6地址格式（冒号数量多）
        if url_lower.count(':') >= 3:
            return True
        return False


def get_source_priority(source_info):
    """获取源的优先级分数（用于排序）"""
    priority = 0
    
    # IPv6源最高优先级（+100分）
    if is_ipv6_url(source_info['url']):
        priority += 100
        # 标记为IPv6源
        source_info['is_ipv6'] = True
    else:
        source_info['is_ipv6'] = False
    
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
    
    # 速度测试结果优先级（如果已经测试过）
    if 'speed' in source_info:
        if source_info['speed'] < 2.0:
            priority += 20  # 超快源
        elif source_info['speed'] < 4.0:
            priority += 10  # 快速源
    
    return priority


def chinese_to_arabic(chinese_num):
    """中文数字转阿拉伯数字"""
    CHINESE_NUMBERS = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '十一': '11', '十二': '12', '十三': '13', '十四': '14', '十五': '15',
        '十六': '16', '十七': '17'
    }
    
    if chinese_num in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[chinese_num]
    return chinese_num


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
                    import time
                    time.sleep(2)
                
        except requests.exceptions.Timeout:
            print(f"❌ 请求超时 {url} (尝试 {attempt + 1}/{retry + 1})")
            if attempt < retry:
                import time
                time.sleep(2)
        except requests.exceptions.ConnectionError:
            print(f"❌ 连接错误 {url} (尝试 {attempt + 1}/{retry + 1})")
            if attempt < retry:
                import time
                time.sleep(2)
        except Exception as e:
            print(f"❌ 请求错误 {url}: {e} (尝试 {attempt + 1}/{retry + 1})")
            if attempt < retry:
                import time
                time.sleep(2)
    
    return None


def create_safe_filename(name):
    """创建安全的文件名"""
    # 移除不安全字符
    unsafe_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    safe_name = name
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, '_')
    
    # 限制长度
    if len(safe_name) > 100:
        safe_name = safe_name[:100]
    
    return safe_name


def format_bytes(size):
    """格式化字节大小为可读字符串"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def print_progress_bar(iteration, total, prefix='', suffix='', length=50, fill='█'):
    """打印进度条"""
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    
    # 完成后换行
    if iteration == total:
        print()


def validate_url(url):
    """验证URL格式"""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return re.match(url_pattern, url) is not None