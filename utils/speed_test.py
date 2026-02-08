#!/usr/bin/env python3
"""
速度测试模块
"""

import time
import requests
import ipaddress
from urllib.parse import urlparse

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

def get_smart_timeout(url, config):
    """获取智能超时时间"""
    if is_ipv6_url(url):
        return SpeedTestConfig.IPV6_CONNECT_TIMEOUT
    return config['CONNECT_TIMEOUT']

def test_m3u8_stream(url, config):
    """智能测试M3U8流媒体源"""
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
                timeout=get_smart_timeout(url, config),
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

def calculate_speed_score(test_results, url, config):
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

def test_url_speed(url, config):
    """智能测试URL速度，返回评分和详细结果"""
    start_time = time.time()
    
    # 如果是M3U8或TS流，使用智能测试
    if url.lower().endswith('.m3u8') or '.m3u8?' in url.lower():
        test_results = test_m3u8_stream(url, config)
        test_time = time.time() - start_time
        speed_score = calculate_speed_score(test_results, url, config)
        
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
                timeout=get_smart_timeout(url, config),
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