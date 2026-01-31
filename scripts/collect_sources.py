#!/usr/bin/env python3
"""
电视直播源收集脚本 - 带黑名单的IPv6优先多源合并版
功能：1. 频道名称精简 2. 同名电视台合并（IPv6优先）3. 支持源切换 4. 统一央视频道命名 5. 智能速度测试和黑名单过滤
特点：支持配置黑名单是否启用、电视线路是否测速，改进测速算法，更精准识别可用直播源
分类：央视、卫视、地方台（按省份）、少儿台、综艺台、港澳台、体育台、影视台、景区频道、其他台
播放器支持：PotPlayer、VLC、TiviMate、Kodi等支持多源切换的播放器
"""

import requests
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os
import sys
import ipaddress
import concurrent.futures
import threading
from urllib.parse import urlparse

print("=" * 70)
print("电视直播源收集脚本 v8.0 - 配置化智能测速版")
print("功能：支持配置黑名单/测速开关，IPv6优先，智能测速过滤")
print("特点：可通过配置文件控制黑名单和测速功能，减少误判")
print("播放器：支持PotPlayer、VLC、TiviMate、Kodi等多源切换功能")
print("=" * 70)

# 配置文件路径
CONFIG_FILE = "config.txt"

def load_config():
    """加载配置文件"""
    config = {
        'ENABLE_BLACKLIST': True,      # 是否启用黑名单
        'ENABLE_SPEED_TEST': True,     # 是否启用测速
        'CONNECT_TIMEOUT': 3,          # 连接超时时间
        'STREAM_TIMEOUT': 10,          # 流媒体测试超时时间
        'MIN_SPEED_SCORE': 0.5,        # 最低速度评分
        'MAX_WORKERS': 20,             # 并发测试线程数
    }
    
    if not os.path.exists(CONFIG_FILE):
        print(f"📝 配置文件 {CONFIG_FILE} 不存在，使用默认配置")
        print(f"   黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}")
        print(f"   测速功能: {'启用' if config['ENABLE_SPEED_TEST'] else '禁用'}")
        return config
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 布尔值处理
                    if key in ['ENABLE_BLACKLIST', 'ENABLE_SPEED_TEST']:
                        if value.lower() in ['true', 'yes', '1', 'on']:
                            config[key] = True
                        elif value.lower() in ['false', 'no', '0', 'off']:
                            config[key] = False
                        else:
                            print(f"⚠️  配置第{line_num}行: {key} 值 '{value}' 无效，使用默认值 {config[key]}")
                    
                    # 整数处理
                    elif key in ['CONNECT_TIMEOUT', 'STREAM_TIMEOUT', 'MAX_WORKERS']:
                        try:
                            config[key] = int(value)
                        except ValueError:
                            print(f"⚠️  配置第{line_num}行: {key} 值 '{value}' 不是有效整数，使用默认值 {config[key]}")
                    
                    # 浮点数处理
                    elif key == 'MIN_SPEED_SCORE':
                        try:
                            val = float(value)
                            if 0 <= val <= 1:
                                config[key] = val
                            else:
                                print(f"⚠️  配置第{line_num}行: {key} 值 '{value}' 超出范围(0-1)，使用默认值 {config[key]}")
                        except ValueError:
                            print(f"⚠️  配置第{line_num}行: {key} 值 '{value}' 不是有效浮点数，使用默认值 {config[key]}")
                    
                    else:
                        print(f"⚠️  配置第{line_num}行: 未知配置项 '{key}'，跳过")
        
        print(f"✅ 从 {CONFIG_FILE} 加载配置:")
        print(f"   黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}")
        print(f"   测速功能: {'启用' if config['ENABLE_SPEED_TEST'] else '禁用'}")
        print(f"   连接超时: {config['CONNECT_TIMEOUT']}秒")
        print(f"   流测试超时: {config['STREAM_TIMEOUT']}秒")
        print(f"   最低评分: {config['MIN_SPEED_SCORE']}")
        print(f"   并发线程: {config['MAX_WORKERS']}")
        
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}，使用默认配置")
    
    return config

# 加载配置
config = load_config()

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

# 黑名单管理
BLACKLIST_FILE = "blacklist.txt"

# 智能测速配置
class SpeedTestConfig:
    """测速配置类"""
    
    # M3U8测试配置
    M3U8_TEST_SIZE = 1024 * 10  # 测试数据大小 (10KB)
    M3U8_HEAD_TIMEOUT = 2  # HEAD请求超时
    M3U8_PARTIAL_TIMEOUT = 5  # 部分内容请求超时
    
    # 评分权重
    CONNECTION_WEIGHT = 0.3  # 连接速度权重
    STABILITY_WEIGHT = 0.4   # 稳定性权重
    RESPONSE_WEIGHT = 0.3    # 响应权重
    
    # IPv6宽容度
    IPV6_BONUS = 0.2  # IPv6源加分
    IPV6_CONNECT_TIMEOUT = 5  # IPv6连接超时时间

# IPv6检测函数
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

def get_smart_timeout(url):
    """获取智能超时时间"""
    if is_ipv6_url(url):
        return SpeedTestConfig.IPV6_CONNECT_TIMEOUT
    return config['CONNECT_TIMEOUT']

def test_m3u8_stream(url, timeout=None):
    """智能测试M3U8流媒体源"""
    if timeout is None:
        timeout = config['STREAM_TIMEOUT']
    
    test_results = {
        'connect_time': None,
        'response_time': None,
        'success': False,
        'error': None,
        'content_type': None,
        'content_length': 0
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Range": f"bytes=0-{SpeedTestConfig.M3U8_TEST_SIZE-1}",
            "Connection": "close"
        }
        
        # 第一阶段：测试连接速度
        start_connect = time.time()
        
        # 首先尝试HEAD请求（轻量级）
        try:
            head_response = requests.head(
                url, 
                headers=headers, 
                timeout=get_smart_timeout(url),
                allow_redirects=True,
                verify=False
            )
            head_response.close()
        except:
            pass  # HEAD请求失败也没关系，继续测试GET
        
        # 第二阶段：测试部分内容获取
        start_partial = time.time()
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            stream=True,
            allow_redirects=True,
            verify=False
        )
        
        # 记录响应信息
        end_partial = time.time()
        
        test_results['connect_time'] = start_partial - start_connect
        test_results['response_time'] = end_partial - start_partial
        test_results['content_type'] = response.headers.get('Content-Type', '')
        test_results['content_length'] = int(response.headers.get('Content-Length', 0))
        
        # 验证内容是否为视频流
        content_type = test_results['content_type'].lower()
        is_video_stream = any(marker in content_type for marker in [
            'video', 'application/vnd.apple.mpegurl', 'application/x-mpegurl'
        ])
        
        # 检查响应状态码
        if response.status_code in [200, 206]:  # 206是部分内容
            # 尝试读取一小部分数据验证可用性
            bytes_read = 0
            for chunk in response.iter_content(chunk_size=1024):
                bytes_read += len(chunk)
                if bytes_read >= 1024:  # 至少读取1KB
                    test_results['success'] = True
                    break
                if time.time() - start_partial > timeout:
                    break
        else:
            test_results['error'] = f"HTTP {response.status_code}"
        
        response.close()
        
    except requests.exceptions.Timeout:
        test_results['error'] = "连接超时"
    except requests.exceptions.ConnectionError as e:
        test_results['error'] = f"连接错误: {str(e)}"
    except requests.exceptions.TooManyRedirects:
        test_results['error'] = "重定向过多"
    except Exception as e:
        test_results['error'] = f"其他错误: {str(e)}"
    
    return test_results

def calculate_speed_score(test_results, url):
    """计算速度评分（0-1分）"""
    if not test_results['success']:
        return 0.0
    
    score = 0.0
    
    # 1. 连接速度评分（30%）
    if test_results['connect_time'] is not None:
        connect_score = 1.0 - min(test_results['connect_time'] / (config['CONNECT_TIMEOUT'] * 2), 1.0)
        score += connect_score * SpeedTestConfig.CONNECTION_WEIGHT
    
    # 2. 响应速度评分（30%）
    if test_results['response_time'] is not None:
        # 理想响应时间小于2秒
        response_score = 1.0 - min(test_results['response_time'] / 4.0, 1.0)
        score += response_score * SpeedTestConfig.RESPONSE_WEIGHT
    
    # 3. 内容验证评分（40%）
    content_score = 0.0
    
    # 检查是否为视频流
    content_type = test_results['content_type'].lower()
    if any(marker in content_type for marker in ['video', 'mpegurl', 'm3u8']):
        content_score += 0.5
    
    # 检查是否有内容长度
    if test_results['content_length'] > 0:
        content_score += 0.3
    
    # 检查是否为直播源常见格式
    if 'm3u8' in url.lower() or 'ts' in url.lower():
        content_score += 0.2
    
    score += content_score * SpeedTestConfig.STABILITY_WEIGHT
    
    # 4. IPv6加分
    if is_ipv6_url(url):
        score += SpeedTestConfig.IPV6_BONUS
    
    # 确保分数在0-1之间
    return min(max(score, 0.0), 1.0)

def test_url_speed(url):
    """智能测试URL速度，返回评分和详细结果"""
    start_time = time.time()
    
    # 如果是M3U8或TS流，使用智能测试
    if url.lower().endswith('.m3u8') or '.m3u8?' in url.lower():
        test_results = test_m3u8_stream(url)
        test_time = time.time() - start_time
        speed_score = calculate_speed_score(test_results, url)
        
        return {
            'score': speed_score,
            'success': test_results['success'],
            'test_time': test_time,
            'connect_time': test_results.get('connect_time'),
            'response_time': test_results.get('response_time'),
            'error': test_results.get('error'),
            'is_ipv6': is_ipv6_url(url)
        }
    else:
        # 对于其他类型URL，使用简单测试
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Connection": "close"
            }
            
            response_start = time.time()
            response = requests.head(
                url, 
                headers=headers, 
                timeout=get_smart_timeout(url),
                allow_redirects=True
            )
            response_time = time.time() - response_start
            
            # 简单评分
            if response.status_code < 400:
                # 基础分 + IPv6加分
                score = 0.7 - min(response_time / 5.0, 0.7)
                if is_ipv6_url(url):
                    score += SpeedTestConfig.IPV6_BONUS
                
                return {
                    'score': score,
                    'success': True,
                    'test_time': time.time() - start_time,
                    'connect_time': response_time,
                    'response_time': response_time,
                    'error': None,
                    'is_ipv6': is_ipv6_url(url)
                }
            else:
                return {
                    'score': 0.0,
                    'success': False,
                    'test_time': time.time() - start_time,
                    'connect_time': None,
                    'response_time': None,
                    'error': f"HTTP {response.status_code}",
                    'is_ipv6': is_ipv6_url(url)
                }
                
        except Exception as e:
            test_time = time.time() - start_time
            return {
                'score': 0.0,
                'success': False,
                'test_time': test_time,
                'connect_time': None,
                'response_time': None,
                'error': str(e)[:100],
                'is_ipv6': is_ipv6_url(url)
            }

def get_source_priority(source_info):
    """获取源的优先级分数（用于排序）"""
    priority = 0
    
    # IPv6源最高优先级（+100分）
    if source_info.get('is_ipv6', False):
        priority += 100
    
    # 速度评分优先级（如果测速功能启用）
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
    
    return priority

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
}

# 中文数字到阿拉伯数字映射
CHINESE_NUMBERS = {
    '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
    '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
    '十一': '11', '十二': '12', '十三': '13', '十四': '14', '十五': '15',
    '十六': '16', '十七': '17'
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
        r"景区$", r"旅游$", r"风光$", r"景点$", r"导视$",
        r"^峨眉山", r"^九寨沟", r"^黄山", r"^泰山", r"^华山",
        r"^张家界", r"^西湖", r"^漓江", r"^鼓浪屿", r"^故宫",
        r"^长城", r"^兵马俑", r"^布达拉宫", r"^天安门", r"^外滩",
        r"^维多利亚港", r"^澳门塔", r"^日月潭", r"^阿里山"
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
    ]
}

# 播放器多源支持配置
PLAYER_SUPPORT = {
    "PotPlayer": {
        "multi_source": True,
        "format": "stream-multi-url",
        "separator": "|",
        "note": "在播放时按Alt+W可以切换源，IPv6源优先排列"
    },
    "VLC": {
        "multi_source": True,
        "format": "stream-multi-url",
        "separator": "#",
        "note": "在播放列表中点右键选择不同源，IPv6源在前"
    },
    "TiviMate": {
        "multi_source": True,
        "format": "same-name",
        "separator": None,
        "note": "自动合并相同名称的频道，播放时自动切换"
    },
    "Kodi": {
        "multi_source": True,
        "format": "m3u_plus",
        "separator": None,
        "note": "使用IPTV Simple Client插件"
    }
}

# 黑名单管理函数
def load_blacklist():
    """加载黑名单"""
    if not config['ENABLE_BLACKLIST']:
        print("📋 黑名单功能已禁用，跳过加载")
        return set()
    
    blacklist = set()
    if os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        blacklist.add(line)
            print(f"📋 从 {BLACKLIST_FILE} 加载了 {len(blacklist)} 个黑名单条目")
        except Exception as e:
            print(f"⚠️  读取黑名单失败: {e}")
    else:
        print(f"📝 {BLACKLIST_FILE} 文件不存在")
    return blacklist

def save_to_blacklist(slow_urls, reason="响应时间超过阈值"):
    """保存慢速URL到黑名单"""
    if not config['ENABLE_BLACKLIST'] or not slow_urls:
        return
    
    # 加载现有黑名单
    existing_blacklist = load_blacklist()
    
    # 添加新的慢速URL
    existing_blacklist.update(slow_urls)
    
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            f.write("# 直播源黑名单\n")
            f.write("# 该文件包含测试失败的直播源\n")
            f.write("# 每行一个URL，下次更新时会跳过这些源\n")
            f.write("# 生成时间: " + get_beijing_time() + "\n")
            f.write(f"# 过滤原因: {reason}\n")
            f.write(f"# 配置文件: {CONFIG_FILE}\n")
            f.write(f"# 黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}\n\n")
            
            # 按域名分组排序
            url_groups = {}
            for url in existing_blacklist:
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc
                    if domain not in url_groups:
                        url_groups[domain] = []
                    url_groups[domain].append(url)
                except:
                    if 'unknown' not in url_groups:
                        url_groups['unknown'] = []
                    url_groups['unknown'].append(url)
            
            # 按域名排序写入
            for domain in sorted(url_groups.keys()):
                if domain == 'unknown':
                    f.write(f"\n# 未知域名\n")
                else:
                    f.write(f"\n# 域名: {domain}\n")
                
                for url in sorted(url_groups[domain]):
                    f.write(url + "\n")
        
        print(f"📝 已保存 {len(slow_urls)} 个慢速源到 {BLACKLIST_FILE}")
    except Exception as e:
        print(f"❌ 保存黑名单失败: {e}")

def test_urls_with_progress(urls, blacklist):
    """并发测试URL速度，显示进度"""
    if not config['ENABLE_SPEED_TEST']:
        print("⚡ 测速功能已禁用，跳过速度测试")
        return {}, set(), {}
    
    results = {}
    slow_urls = set()
    detailed_results = {}
    
    print(f"⚡ 开始智能速度测试")
    print(f"📊 配置: 连接超时={config['CONNECT_TIMEOUT']}s, 流测试超时={config['STREAM_TIMEOUT']}s")
    print(f"📊 需要测试 {len(urls)} 个URL")
    
    # 过滤掉已经在黑名单中的URL（如果黑名单启用）
    if config['ENABLE_BLACKLIST']:
        urls_to_test = [url for url in urls if url not in blacklist]
    else:
        urls_to_test = urls
    
    if not urls_to_test:
        print("✅ 所有URL都在黑名单中，跳过速度测试")
        return results, slow_urls, detailed_results
    
    print(f"🔍 实际需要测试 {len(urls_to_test)} 个URL")
    
    # 按URL类型分组（M3U8优先测试）
    m3u8_urls = []
    other_urls = []
    
    for url in urls_to_test:
        if '.m3u8' in url.lower():
            m3u8_urls.append(url)
        else:
            other_urls.append(url)
    
    print(f"  M3U8流媒体源: {len(m3u8_urls)} 个")
    print(f"  其他类型源: {len(other_urls)} 个")
    
    # 合并测试列表
    test_order = m3u8_urls + other_urls
    
    # 使用线程池并发测试
    with concurrent.futures.ThreadPoolExecutor(max_workers=config['MAX_WORKERS']) as executor:
        # 提交所有测试任务
        future_to_url = {executor.submit(test_url_speed, url): url for url in test_order}
        
        # 进度统计
        completed = 0
        total = len(test_order)
        start_time = time.time()
        
        for future in concurrent.futures.as_completed(future_to_url):
            completed += 1
            url = future_to_url[future]
            
            try:
                result = future.result()
                detailed_results[url] = result
                
                if result['success']:
                    score = result['score']
                    results[url] = score
                    
                    # 判断是否为慢速源
                    if score < config['MIN_SPEED_SCORE']:
                        slow_urls.add(url)
                        speed_desc = f"评分低({score:.2f})"
                    else:
                        speed_desc = f"评分{score:.2f}"
                    
                    # 每测试5个URL显示一次进度
                    if completed % 5 == 0 or completed == total:
                        elapsed = time.time() - start_time
                        avg_time = elapsed / completed if completed > 0 else 0
                        remaining = (total - completed) * avg_time if avg_time > 0 else 0
                        
                        print(f"  ⏳ {completed}/{total} ({completed/total*100:.1f}%) "
                              f"用时:{elapsed:.1f}s 剩余:{remaining:.0f}s "
                              f"最新:{speed_desc} {url[:50]}...")
                else:
                    slow_urls.add(url)
                    error_msg = result.get('error', '未知错误')
                    print(f"  ❌ 失败: {url[:60]}... - {error_msg}")
                    
            except Exception as e:
                slow_urls.add(url)
                detailed_results[url] = {
                    'success': False,
                    'error': f"测试异常: {str(e)}",
                    'score': 0.0
                }
                print(f"  ⚠️  异常: {url[:60]}... - {str(e)[:50]}")
    
    # 统计结果
    fast_urls = len(results)
    print(f"\n✅ 速度测试完成")
    print(f"  快速源: {fast_urls} 个 (评分≥{config['MIN_SPEED_SCORE']})")
    print(f"  慢速源: {len(slow_urls)} 个 (评分<{config['MIN_SPEED_SCORE']}或失败)")
    
    # 显示评分分布
    if results:
        scores = list(results.values())
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        
        print(f"  评分统计: 平均{avg_score:.2f}, 最高{max_score:.2f}, 最低{min_score:.2f}")
        
        # 评分分段统计
        score_ranges = {
            "优秀(0.9-1.0)": sum(1 for s in scores if s >= 0.9),
            "良好(0.7-0.9)": sum(1 for s in scores if 0.7 <= s < 0.9),
            "一般(0.5-0.7)": sum(1 for s in scores if 0.5 <= s < 0.7),
            "较差(0.0-0.5)": sum(1 for s in scores if s < 0.5)
        }
        
        print(f"  评分分布:")
        for desc, count in score_ranges.items():
            if count > 0:
                percentage = count / len(scores) * 100
                print(f"    {desc}: {count}个 ({percentage:.1f}%)")
    
    return results, slow_urls, detailed_results

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
    for pattern, replacement in CLEAN_RULES:  # 修复：直接遍历列表
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

def merge_channels(all_channels, speed_test_results=None):
    """合并同名电视台，支持多源，IPv6优先排序，过滤黑名单"""
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
                    'is_ipv6': is_ipv6_url(channel['url']),
                    'speed_score': speed_test_results.get(channel['url'], {}).get('score', 0.0) if speed_test_results else 0.0,
                    'test_details': speed_test_results.get(channel['url'], {}) if speed_test_results else {}
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
                    'priority': 0,
                    'is_ipv6': is_ipv6_url(channel['url']),
                    'speed_score': speed_test_results.get(channel['url'], {}).get('score', 0.0) if speed_test_results else 0.0,
                    'test_details': speed_test_results.get(channel['url'], {}) if speed_test_results else {}
                })
            
            # 收集logo
            if channel['logo'] and channel['logo'] not in merged[key]['logos']:
                merged[key]['logos'].append(channel['logo'])
            
            # 更新分类
            category = categorize_channel(key)
            merged[key]['categories'].add(category)
    
    # 为每个频道的源计算优先级并排序
    for key in merged:
        for source in merged[key]['sources']:
            source['priority'] = get_source_priority(source)
        
        # 按优先级降序排序
        merged[key]['sources'].sort(key=lambda x: x['priority'], reverse=True)
        
        # 为每个合并后的频道选择一个主分类
        categories = list(merged[key]['categories'])
        if categories:
            non_other = [c for c in categories if c != "其他台"]
            if non_other:
                merged[key]['category'] = non_other[0]
            else:
                merged[key]['category'] = "其他台"
        else:
            merged[key]['category'] = "其他台"
    
    return merged

def generate_multi_source_m3u(merged_channels, categories, final_category_order, timestamp, output_file, mode="multi"):
    """
    生成支持多源的M3U文件
    mode: 
      "multi" - 多源合并成一个条目（PotPlayer格式）
      "separate" - 每个源分开条目但相同名称
      "single" - 只保留最佳源
    """
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            if mode == "multi":
                f.write(f"# 电视直播源 - IPv6优先多源合并版\n")
                f.write(f"# 每个电视台只显示一个条目，IPv6源优先排列\n")
                f.write(f"# 播放器切换源方法：PotPlayer按Alt+W，VLC右键选择源\n")
                f.write(f"# 排序规则：IPv6源 > 4K > 高清 > 标清 > 流畅\n")
            elif mode == "separate":
                f.write(f"# 电视直播源 - IPv6优先多源分离版\n")
                f.write(f"# 同名电视台显示为多个条目，IPv6源优先，播放器自动合并\n")
            else:
                f.write(f"# 电视直播源 - IPv6优先精简版\n")
                f.write(f"# 每个电视台只保留最佳源（IPv6优先）\n")
            
            f.write(f"# 更新时间(北京时间): {timestamp}\n")
            f.write(f"# 电视台总数: {len(merged_channels)}\n")
            f.write(f"# 数据源: {len(sources)} 个 (成功: {success_sources}, 失败: {len(failed_sources)})\n")
            f.write(f"# 特点: 移除技术参数，统一央视频道命名，按省份分类地方台，IPv6优先\n")
            f.write(f"# 配置文件: {CONFIG_FILE}\n")
            f.write(f"# 黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}\n")
            f.write(f"# 测速功能: {'启用' if config['ENABLE_SPEED_TEST'] else '禁用'}\n")
            
            if config['ENABLE_SPEED_TEST']:
                f.write(f"# 已过滤低质量源（评分 < {config['MIN_SPEED_SCORE']}）\n")
            
            f.write(f"# 源文件: sources.txt\n")
            if config['ENABLE_BLACKLIST']:
                f.write(f"# 黑名单: {BLACKLIST_FILE}\n")
            f.write("\n")
            
            # 按分类顺序写入
            for category in final_category_order:
                cat_channels = categories[category]
                if cat_channels:
                    # 对频道进行排序
                    sorted_channels = sorted(
                        cat_channels,
                        key=lambda x: get_channel_sort_key(x['clean_name'], category)
                    )
                    
                    f.write(f"\n# 分类: {category} ({len(cat_channels)}个电视台)\n")
                    
                    for channel in sorted_channels:
                        # 选择主logo（第一个非空的logo）
                        main_logo = channel['logos'][0] if channel['logos'] else ""
                        source_count = len(channel['sources'])
                        
                        # 统计IPv6源数量
                        ipv6_count = sum(1 for s in channel['sources'] if s.get('is_ipv6', False))
                        
                        # 统计高质量源数量（评分≥0.7）
                        high_quality_sources = [s for s in channel['sources'] if s.get('speed_score', 0) >= 0.7]
                        high_quality_count = len(high_quality_sources)
                        
                        if mode == "multi":
                            # PotPlayer/VLC多源格式：一个条目包含多个URL，用"|"分隔
                            source_desc = []
                            if ipv6_count > 0:
                                source_desc.append(f"{ipv6_count}IPv6")
                            if high_quality_count > 0 and config['ENABLE_SPEED_TEST']:
                                source_desc.append(f"{high_quality_count}高速")
                            if source_count > ipv6_count:
                                source_desc.append(f"{source_count}源")
                            
                            if source_desc:
                                display_name = f"{channel['clean_name']} [{'+'.join(source_desc)}]"
                            else:
                                display_name = f"{channel['clean_name']} [{source_count}源]"
                            
                            # 收集所有URL（已按优先级排序）
                            urls = []
                            qualities = []
                            ipv6_sources = []
                            ipv4_sources = []
                            
                            for source in channel['sources']:
                                if source.get('is_ipv6', False):
                                    ipv6_sources.append(source)
                                else:
                                    ipv4_sources.append(source)
                            
                            # 确保IPv6源在前面
                            sorted_sources = ipv6_sources + ipv4_sources
                            
                            for source in sorted_sources:
                                urls.append(source['url'])
                                if source['quality'] != "未知":
                                    qualities.append(source['quality'])
                            
                            # 生成多源URL
                            multi_url = "|".join(urls)
                            
                            # 写入条目
                            line = "#EXTINF:-1"
                            line += f' tvg-name="{channel["clean_name"]}"'
                            line += f' group-title="{category}"'
                            if main_logo:
                                line += f' tvg-logo="{main_logo}"'
                            if qualities:
                                quality_desc = "/".join(sorted(set(qualities), key=lambda x: ["4K","高清","标清","流畅","未知"].index(x) if x in ["4K","高清","标清","流畅","未知"] else 10))
                                line += f' tvg-quality="{quality_desc}"'
                            if ipv6_count > 0:
                                line += f' tvg-ipv6="true"'
                            line += f',{display_name}\n'
                            line += f"{multi_url}\n"
                            f.write(line)
                            
                        elif mode == "separate":
                            # TiviMate/Kodi格式：相同名称的多个条目，IPv6源优先
                            display_name = channel['clean_name']
                            
                            # 分离IPv6和IPv4源
                            ipv6_sources = []
                            ipv4_sources = []
                            for source in channel['sources']:
                                if source.get('is_ipv6', False):
                                    ipv6_sources.append(source)
                                else:
                                    ipv4_sources.append(source)
                            
                            # 确保IPv6源在前面
                            sorted_sources = ipv6_sources + ipv4_sources
                            
                            for i, source in enumerate(sorted_sources, 1):
                                source_type = "IPv6" if source.get('is_ipv6', False) else "IPv4"
                                speed_info = ""
                                if source.get('speed_score') and config['ENABLE_SPEED_TEST']:
                                    speed_info = f" ({source['speed_score']:.2f})"
                                
                                line = "#EXTINF:-1"
                                line += f' tvg-name="{channel["clean_name"]}"'
                                line += f' group-title="{category}"'
                                if main_logo:
                                    line += f' tvg-logo="{main_logo}"'
                                if source['quality'] != "未知":
                                    line += f' tvg-quality="{source["quality"]}"'
                                if source.get('is_ipv6', False):
                                    line += f' tvg-ipv6="true"'
                                if source_count > 1:
                                    line += f',{display_name} [{source_type}源{i}{speed_info}]\n'
                                else:
                                    line += f',{display_name}{speed_info}\n'
                                line += f"{source['url']}\n"
                                f.write(line)
                                
                        else:  # mode == "single"
                            # 精简版：只保留最佳源（IPv6优先）
                            display_name = channel['clean_name']
                            
                            # 选择最佳源（优先选择IPv6快速源）
                            best_source = None
                            
                            # 如果测速功能启用，优先选择高速源
                            if config['ENABLE_SPEED_TEST']:
                                # 首先找IPv6高速源（评分≥0.7）
                                for source in channel['sources']:
                                    if source.get('is_ipv6', False) and source.get('speed_score', 0) >= 0.7:
                                        best_source = source
                                        break
                                
                                # 然后找IPv4高速源
                                if not best_source:
                                    for source in channel['sources']:
                                        if not source.get('is_ipv6', False) and source.get('speed_score', 0) >= 0.7:
                                            best_source = source
                                            break
                            
                            # 如果没找到高速源或测速禁用，按默认规则选择
                            if not best_source:
                                # 首先找IPv6高清源
                                for source in channel['sources']:
                                    if source.get('is_ipv6', False) and source['quality'] == "高清":
                                        best_source = source
                                        break
                                
                                # 然后找IPv4高清源
                                if not best_source:
                                    for source in channel['sources']:
                                        if not source.get('is_ipv6', False) and source['quality'] == "高清":
                                            best_source = source
                                            break
                                
                                # 最后选第一个源
                                if not best_source:
                                    best_source = channel['sources'][0]
                            
                            line = "#EXTINF:-1"
                            line += f' tvg-name="{channel["clean_name"]}"'
                            line += f' group-title="{category}"'
                            if main_logo:
                                line += f' tvg-logo="{main_logo}"'
                            if best_source['quality'] != "未知":
                                line += f' tvg-quality="{best_source["quality"]}"'
                            if best_source.get('is_ipv6', False):
                                line += f' tvg-ipv6="true"'
                                display_name = f"{display_name} [IPv6]"
                            if best_source.get('speed_score') and config['ENABLE_SPEED_TEST']:
                                line += f' tvg-score="{best_source["speed_score"]:.2f}"'
                                display_name = f"{display_name} ({best_source['speed_score']:.2f})"
                            line += f',{display_name}\n'
                            line += f"{best_source['url']}\n"
                            f.write(line)
        
        print(f"  ✅ {output_file} 生成成功")
        return True
    except Exception as e:
        print(f"  ❌ 生成{output_file}失败: {e}")
        return False

# 主收集过程
print("🚀 开始采集电视直播源...")

# 1. 加载黑名单
print("📋 加载黑名单...")
blacklist = load_blacklist()

print(f"📋 数据源列表 (从sources.txt加载):")
for i, source in enumerate(sources, 1):
    print(f"  {i:2d}. {source}")

all_channels = []
success_sources = 0
failed_sources = []

# 2. 收集所有频道的原始数据
print("\n📡 开始收集频道数据...")
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

# 3. 提取所有唯一的URL进行速度测试
print("\n📊 提取所有唯一URL...")
all_urls = set()
for channel in all_channels:
    all_urls.add(channel['url'])

print(f"   发现 {len(all_urls)} 个唯一URL")

# 4. 进行智能速度测试
print("\n⚡ 开始智能速度测试...")
speed_test_results, slow_urls, detailed_results = test_urls_with_progress(all_urls, blacklist)

# 5. 保存失败和低质量URL到黑名单
if slow_urls and config['ENABLE_BLACKLIST'] and config['ENABLE_SPEED_TEST']:
    # 分析失败原因
    error_types = {}
    for url in slow_urls:
        result = detailed_results.get(url, {})
        error = result.get('error', '评分过低')
        error_types[error] = error_types.get(error, 0) + 1
    
    print(f"\n📊 失败原因分析:")
    for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {error}: {count}个")
    
    reason = "评分过低或连接失败"
    if error_types:
        main_error = max(error_types.items(), key=lambda x: x[1])[0]
        reason = f"主要失败原因: {main_error}"
    
    print(f"\n📝 发现 {len(slow_urls)} 个低质量源，保存到黑名单...")
    save_to_blacklist(slow_urls, reason)
elif slow_urls:
    print(f"\n⚠️  发现 {len(slow_urls)} 个低质量源，但黑名单或测速功能已禁用，不保存")

# 6. 过滤掉黑名单中的频道（如果黑名单启用）
print("\n🚫 过滤黑名单中的频道...")
filtered_channels = []
blacklisted_count = 0

for channel in all_channels:
    if config['ENABLE_BLACKLIST'] and (channel['url'] in blacklist or channel['url'] in slow_urls):
        blacklisted_count += 1
    else:
        filtered_channels.append(channel)

print(f"   原始频道数: {len(all_channels)}")
print(f"   过滤后频道数: {len(filtered_channels)}")
print(f"   黑名单过滤数: {blacklisted_count}")

if len(filtered_channels) == 0:
    print("\n❌ 所有频道都被黑名单过滤，退出")
    sys.exit(1)

# 7. 合并同名电视台
print("\n🔄 正在合并同名电视台...")
merged_channels = merge_channels(filtered_channels, detailed_results)
print(f"   合并后: {len(merged_channels)} 个唯一电视台")

# 8. 显示多源统计和IPv6统计
multi_source_count = sum(1 for c in merged_channels.values() if len(c['sources']) > 1)
single_source_count = len(merged_channels) - multi_source_count
ipv6_channel_count = sum(1 for c in merged_channels.values() if any(s.get('is_ipv6', False) for s in c['sources']))
high_quality_channel_count = sum(1 for c in merged_channels.values() if any(s.get('speed_score', 0) >= 0.7 for s in c['sources']))

print(f"   多源电视台: {multi_source_count} 个")
print(f"   单源电视台: {single_source_count} 个")
print(f"   含IPv6源电视台: {ipv6_channel_count} 个")
if config['ENABLE_SPEED_TEST']:
    print(f"   含高质量源电视台: {high_quality_channel_count} 个")

# 显示一些多源示例
print("\n📝 IPv6多源电视台示例:")
ipv6_multi_examples = [(k, v) for k, v in merged_channels.items() 
                      if any(s.get('is_ipv6', False) for s in v['sources'])][:5]
for clean_name, data in ipv6_multi_examples:
    source_count = len(data['sources'])
    ipv6_count = sum(1 for s in data['sources'] if s.get('is_ipv6', False))
    high_quality_count = sum(1 for s in data['sources'] if s.get('speed_score', 0) >= 0.7)
    qualities = [s['quality'] for s in data['sources']]
    quality_desc = "/".join(set(qualities))
    quality_info = f" 高质量源:{high_quality_count}" if config['ENABLE_SPEED_TEST'] else ""
    print(f"   {clean_name}: {ipv6_count}IPv6+{source_count-ipv6_count}IPv4 [{quality_desc}]{quality_info}")

# 9. 统计分类数量
category_stats = {}
for channel in merged_channels.values():
    category = channel['category']
    if category in category_stats:
        category_stats[category] += 1
    else:
        category_stats[category] = 1

print("\n📊 分类统计:")
for category, count in sorted(category_stats.items()):
    print(f"   {category}: {count} 个电视台")

# 10. 生成文件 - 使用北京时间
timestamp = get_beijing_time()
print(f"\n📅 当前北京时间: {timestamp}")

# 11. 按分类组织频道
categories = {}
for channel in merged_channels.values():
    category = channel['category']
    if category not in categories:
        categories[category] = []
    categories[category].append(channel)

# 确定分类顺序（固定分类在前，省份分类在后，按拼音排序）
fixed_categories = ["央视", "卫视", "景区频道", "少儿台", "综艺台", 
                   "港澳台", "体育台", "影视台", "其他台"]

# 分离省份分类
province_categories = []
other_categories = []
for category in categories.keys():
    if category in fixed_categories:
        continue
    elif category in PROVINCES or any(province in category for province in PROVINCES):
        province_categories.append(category)
    else:
        other_categories.append(category)

# 按拼音排序省份分类
province_categories.sort()

# 最终分类顺序
final_category_order = fixed_categories + province_categories + other_categories

# 确保每个分类都存在（即使为空）
for category in final_category_order:
    if category not in categories:
        categories[category] = []

# 创建输出目录
Path("categories").mkdir(exist_ok=True)
Path("merged").mkdir(exist_ok=True)

print("\n🎯 播放器多源支持信息:")
for player, info in PLAYER_SUPPORT.items():
    if info['multi_source']:
        print(f"   ✅ {player}: {info['note']}")

# 12. 生成多源合并版M3U（PotPlayer/VLC格式）
print("\n📄 生成 live_sources.m3u（IPv6优先多源合并版 - PotPlayer/VLC格式）...")
generate_multi_source_m3u(
    merged_channels, categories, final_category_order, 
    timestamp, "live_sources.m3u", mode="multi"
)

# 13. 生成多源分离版M3U（TiviMate/Kodi格式）
print("\n📄 生成 merged/多源分离版.m3u（IPv6优先多源分离版 - TiviMate/Kodi格式）...")
generate_multi_source_m3u(
    merged_channels, categories, final_category_order,
    timestamp, "merged/多源分离版.m3u", mode="separate"
)

# 14. 生成精简版M3U（每个电视台只保留最佳源）
print("\n📄 生成 merged/精简版.m3u（IPv6优先单源精简版）...")
generate_multi_source_m3u(
    merged_channels, categories, final_category_order,
    timestamp, "merged/精简版.m3u", mode="single"
)

# 15. 生成分类M3U文件（IPv6优先多源合并格式）
print("\n📄 生成分类文件（IPv6优先多源合并格式）...")
for category in final_category_order:
    cat_channels = categories[category]
    if cat_channels:
        try:
            # 对频道进行排序
            sorted_channels = sorted(
                cat_channels,
                key=lambda x: get_channel_sort_key(x['clean_name'], category)
            )
            
            # 创建安全的文件名
            safe_category_name = category.replace('/', '_').replace('\\', '_')
            filename = f"categories/{safe_category_name}.m3u"
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"# {category}频道列表（IPv6优先多源合并版）\n")
                f.write(f"# 更新时间(北京时间): {timestamp}\n")
                f.write(f"# 电视台数量: {len(cat_channels)}\n")
                f.write(f"# 说明: 每个电视台包含多个源，IPv6源优先，PotPlayer按Alt+W切换\n")
                if config['ENABLE_SPEED_TEST']:
                    f.write(f"# 已过滤低质量源（评分 < {config['MIN_SPEED_SCORE']}）\n")
                f.write(f"# 配置文件: {CONFIG_FILE}\n")
                f.write(f"# 黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}\n")
                f.write(f"# 测速功能: {'启用' if config['ENABLE_SPEED_TEST'] else '禁用'}\n\n")
                
                for channel in sorted_channels:
                    # 选择主logo（第一个非空的logo）
                    main_logo = channel['logos'][0] if channel['logos'] else ""
                    source_count = len(channel['sources'])
                    
                    # 统计IPv6源数量
                    ipv6_count = sum(1 for s in channel['sources'] if s.get('is_ipv6', False))
                    
                    # PotPlayer/VLC多源格式
                    source_desc = []
                    if ipv6_count > 0:
                        source_desc.append(f"{ipv6_count}IPv6")
                    if source_count > ipv6_count:
                        source_desc.append(f"{source_count-ipv6_count}IPv4")
                    
                    if source_desc:
                        display_name = f"{channel['clean_name']} [{'+'.join(source_desc)}]"
                    else:
                        display_name = f"{channel['clean_name']} [{source_count}源]"
                    
                    # 收集所有URL（IPv6优先）
                    urls = []
                    qualities = []
                    ipv6_sources = []
                    ipv4_sources = []
                    
                    for source in channel['sources']:
                        if source.get('is_ipv6', False):
                            ipv6_sources.append(source)
                        else:
                            ipv4_sources.append(source)
                    
                    # 确保IPv6源在前面
                    sorted_sources = ipv6_sources + ipv4_sources
                    
                    for source in sorted_sources:
                        urls.append(source['url'])
                        if source['quality'] != "未知":
                            qualities.append(source['quality'])
                    
                    # 生成多源URL
                    multi_url = "|".join(urls)
                    
                    # 写入条目
                    line = "#EXTINF:-1"
                    line += f' tvg-name="{channel["clean_name"]}"'
                    line += f' group-title="{category}"'
                    if main_logo:
                        line += f' tvg-logo="{main_logo}"'
                    if qualities:
                        quality_desc = "/".join(sorted(set(qualities), key=lambda x: ["4K","高清","标清","流畅","未知"].index(x) if x in ["4K","高清","标清","流畅","未知"] else 10))
                        line += f' tvg-quality="{quality_desc}"'
                    if ipv6_count > 0:
                        line += f' tvg-ipv6="true"'
                    line += f',{display_name}\n'
                    line += f"{multi_url}\n"
                    f.write(line)
            
            print(f"  ✅ 生成 {filename}")
        except Exception as e:
            print(f"  ❌ 生成 {filename} 失败: {e}")

# 16. 生成合并的JSON文件（包含所有源信息）
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
                'logo': source['logo'] if source['logo'] else "",
                'is_ipv6': source.get('is_ipv6', False),
                'priority': source.get('priority', 0),
                'speed_score': source.get('speed_score', 0.0),
                'test_details': source.get('test_details', {})
            })
        
        # 统计IPv6源数量
        ipv6_count = sum(1 for s in sources_info if s.get('is_ipv6', False))
        
        # 统计高质量源数量
        high_quality_count = sum(1 for s in sources_info if s.get('speed_score', 0) >= 0.7)
        
        # 频道信息
        channel_info = {
            'clean_name': clean_name,
            'original_names': list(set(channel_data['original_names'])),  # 去重
            'category': channel_data['category'],
            'source_count': len(channel_data['sources']),
            'ipv6_source_count': ipv6_count,
            'high_quality_source_count': high_quality_count,
            'logos': channel_data['logos'],
            'sources': sources_info
        }
        channel_list.append(channel_info)
    
    # 黑名单统计
    blacklist_stats = {
        'total_blacklisted': len(blacklist) + len(slow_urls),
        'previously_blacklisted': len(blacklist),
        'newly_blacklisted': len(slow_urls)
    }
    
    # 创建JSON数据
    json_data = {
        'last_updated': timestamp,
        'config': {
            'enable_blacklist': config['ENABLE_BLACKLIST'],
            'enable_speed_test': config['ENABLE_SPEED_TEST'],
            'connect_timeout': config['CONNECT_TIMEOUT'],
            'stream_timeout': config['STREAM_TIMEOUT'],
            'min_speed_score': config['MIN_SPEED_SCORE'],
            'max_workers': config['MAX_WORKERS']
        },
        'total_channels': len(merged_channels),
        'original_channel_count': len(all_channels),
        'filtered_channel_count': len(filtered_channels),
        'blacklisted_channel_count': blacklisted_count,
        'sources_count': len(sources),
        'success_sources': success_sources,
        'failed_sources': failed_sources,
        'multi_source_channels': multi_source_count,
        'single_source_channels': single_source_count,
        'ipv6_channels': ipv6_channel_count,
        'high_quality_channels': high_quality_channel_count,
        'blacklist_stats': blacklist_stats,
        'category_stats': category_stats,
        'sorting_rules': {
            'ipv6_priority': 100,
            '4k_priority': 40,
            'hd_priority': 30,
            'sd_priority': 20,
            'fluent_priority': 10
        },
        'channels': channel_list,
        'player_support': PLAYER_SUPPORT,
        'source_file': 'sources.txt',
        'blacklist_file': BLACKLIST_FILE,
        'config_file': CONFIG_FILE
    }
    
    # 写入文件
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"  ✅ channels.json 生成成功，包含 {len(merged_channels)} 个电视台的详细信息")
except Exception as e:
    print(f"  ❌ 生成channels.json失败: {e}")

print(f"\n🎉 所有文件生成完成！")
print(f"📊 统计:")
print(f"  - 电视台总数: {len(merged_channels)}")
print(f"  - 多源电视台: {multi_source_count}")
print(f"  - 单源电视台: {single_source_count}")
print(f"  - 含IPv6源电视台: {ipv6_channel_count}")
if config['ENABLE_SPEED_TEST']:
    print(f"  - 含高质量源电视台: {high_quality_channel_count}")
print(f"  - 原始频道数: {len(all_channels)}")
print(f"  - 过滤后频道数: {len(filtered_channels)}")
print(f"  - 黑名单过滤数: {blacklisted_count}")
print(f"  - 数据源: {len(sources)}")
if config['ENABLE_BLACKLIST']:
    print(f"  - 黑名单条目: {len(blacklist) + len(slow_urls)}")
print(f"📁 生成的文件:")
print(f"  - live_sources.m3u (IPv6优先多源合并版 - PotPlayer/VLC格式)")
print(f"  - merged/多源分离版.m3u (IPv6优先多源分离版 - TiviMate/Kodi格式)")
print(f"  - merged/精简版.m3u (IPv6优先单源精简版)")
print(f"  - channels.json (详细数据)")
print(f"  - categories/*.m3u (分类列表)")
if config['ENABLE_BLACKLIST']:
    print(f"  - {BLACKLIST_FILE} (低质量源黑名单)")
print(f"\n🎮 播放器使用说明:")
print(f"  1. PotPlayer/VLC: 使用 live_sources.m3u，播放时按Alt+W切换源")
print(f"  2. TiviMate/Kodi: 使用 merged/多源分离版.m3u，自动合并相同名称频道")
print(f"  3. 其他播放器: 使用 merged/精简版.m3u，每个电视台IPv6源优先")
print(f"\n⚙️  当前配置:")
print(f"  - 黑名单功能: {'✅启用' if config['ENABLE_BLACKLIST'] else '❌禁用'}")
print(f"  - 测速功能: {'✅启用' if config['ENABLE_SPEED_TEST'] else '❌禁用'}")
if config['ENABLE_SPEED_TEST']:
    print(f"  - 最低评分要求: {config['MIN_SPEED_SCORE']}")
    print(f"  - 超时设置: {config['CONNECT_TIMEOUT']}s连接, {config['STREAM_TIMEOUT']}s流测试")
print(f"\n📝 配置文件说明:")
print(f"  修改 {CONFIG_FILE} 文件可以调整配置，如果文件不存在会使用默认值")
print(f"  示例配置:")
print(f"    ENABLE_BLACKLIST=true")
print(f"    ENABLE_SPEED_TEST=true")
print(f"    CONNECT_TIMEOUT=3")
print(f"    STREAM_TIMEOUT=10")
print(f"    MIN_SPEED_SCORE=0.5")
print(f"    MAX_WORKERS=20")