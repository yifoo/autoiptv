#!/usr/bin/env python3
"""
速度测试模块
"""
import requests
import time
import concurrent.futures
from .config import SPEED_TEST_TIMEOUT, MAX_WORKERS


def test_url_speed(url):
    """测试URL速度，返回响应时间（秒），超时返回None"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close",
            "Cache-Control": "no-cache"
        }
        
        start_time = time.time()
        
        # 使用stream=True，只获取头部信息，不下载整个文件
        response = requests.get(url, headers=headers, timeout=SPEED_TEST_TIMEOUT, 
                               stream=True, allow_redirects=True)
        
        # 只读取一小部分数据来确认连接正常
        response.close()
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # 检查HTTP状态码
        if response.status_code >= 400:
            return None  # 请求失败
            
        return response_time
        
    except requests.exceptions.Timeout:
        return None  # 超时
    except requests.exceptions.ConnectionError:
        return None  # 连接错误
    except requests.exceptions.TooManyRedirects:
        return None  # 重定向过多
    except Exception as e:
        return None  # 其他错误


def test_urls_with_progress(urls, blacklist):
    """并发测试URL速度，显示进度"""
    results = {}
    slow_urls = set()
    
    print(f"⚡ 开始速度测试，超时时间: {SPEED_TEST_TIMEOUT}秒，最大并发数: {MAX_WORKERS}")
    print(f"📊 需要测试 {len(urls)} 个URL")
    
    # 过滤掉已经在黑名单中的URL
    urls_to_test = [url for url in urls if url not in blacklist]
    
    if not urls_to_test:
        print("✅ 所有URL都在黑名单中，跳过速度测试")
        return results, slow_urls
    
    print(f"🔍 实际需要测试 {len(urls_to_test)} 个URL")
    
    # 使用线程池并发测试
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有测试任务
        future_to_url = {executor.submit(test_url_speed, url): url for url in urls_to_test}
        
        # 进度统计
        completed = 0
        total = len(urls_to_test)
        start_time = time.time()
        
        for future in concurrent.futures.as_completed(future_to_url):
            completed += 1
            url = future_to_url[future]
            
            try:
                speed = future.result()
                if speed is not None:
                    if speed <= SPEED_TEST_TIMEOUT:
                        results[url] = speed
                        
                        # 每测试10个URL显示一次进度
                        if completed % 10 == 0 or completed == total:
                            elapsed = time.time() - start_time
                            print(f"  ⏳ 进度: {completed}/{total} ({completed/total*100:.1f}%) - "
                                  f"已用时: {elapsed:.1f}秒 - 最新: {url[:50]}... - 速度: {speed:.2f}秒")
                    else:
                        slow_urls.add(url)
                        print(f"  🐌 慢速源: {url[:60]}... - 响应时间: {speed:.2f}秒")
                else:
                    slow_urls.add(url)
                    print(f"  ❌ 失败源: {url[:60]}... - 连接失败")
                    
            except Exception as e:
                slow_urls.add(url)
                print(f"  ⚠️  异常源: {url[:60]}... - 错误: {str(e)[:50]}")
    
    print(f"✅ 速度测试完成")
    print(f"  快速源: {len(results)} 个")
    print(f"  慢速源: {len(slow_urls)} 个")
    
    return results, slow_urls


def quick_test_url(url, timeout=5):
    """快速测试单个URL"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Connection": "close"
        }
        
        start_time = time.time()
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.close()
        
        elapsed = time.time() - start_time
        
        if response.status_code >= 400:
            return False, elapsed, f"HTTP {response.status_code}"
        
        return True, elapsed, "OK"
    except Exception as e:
        return False, timeout, str(e)


def batch_test_urls(urls, max_workers=10, timeout=5):
    """批量测试URL"""
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(quick_test_url, url, timeout): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                success, elapsed, message = future.result()
                results[url] = {
                    'success': success,
                    'elapsed': elapsed,
                    'message': message
                }
            except Exception as e:
                results[url] = {
                    'success': False,
                    'elapsed': timeout,
                    'message': str(e)
                }
    
    return results