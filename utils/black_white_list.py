#!/usr/bin/env python3
"""
黑白名单管理模块
"""

import os
import re
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

BLACKLIST_FILE = "blacklist.txt"

def get_beijing_time():
    """获取东八区北京时间"""
    utc_now = datetime.now(timezone.utc)
    beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
    return beijing_time.strftime('%Y-%m-%d %H:%M:%S')

def load_whitelist(config):
    """加载白名单，支持多种格式：规则、完整URL、频道定义"""
    if not config['ENABLE_WHITELIST']:
        print("📋 白名单功能已禁用，跳过加载")
        return {'patterns': set(), 'urls': set(), 'channels': []}
    
    whitelist_file = config['WHITELIST_FILE']
    whitelist_data = {
        'patterns': set(),  # 规则模式
        'urls': set(),      # 完整URL
        'channels': []      # 完整频道定义
    }
    
    if not os.path.exists(whitelist_file):
        print(f"📝 {whitelist_file} 文件不存在，将创建空白名单")
        # 创建空白的白名单文件
        try:
            with open(whitelist_file, "w", encoding="utf-8") as f:
                f.write("# 直播源白名单\n")
                f.write("# 该文件包含永不删除的直播源\n")
                f.write("# 支持格式:\n")
                f.write("# 1. 规则匹配: *example.com* (匹配所有包含example.com的URL)\n")
                f.write("# 2. 完整URL: https://example.com/live.m3u8\n")
                f.write("# 3. 频道定义: url=https://example.com/live.m3u8, name=频道名称, group=分组, logo=logo.png\n")
                f.write("# 4. 正则表达式: /.*cctv.*\\.m3u8/\n")
                f.write("# 生成时间: " + get_beijing_time() + "\n")
                f.write("# 配置文件: config.txt\n\n")
                f.write("# 示例:\n")
                f.write("# *cctv.com*\n")
                f.write("# https://example.com/important-stream.m3u8\n")
                f.write("# url=https://example.com/live.m3u8, name=测试频道, group=测试分组, logo=http://example.com/logo.png\n")
                f.write("# /.*4k.*\\.m3u8/\n")
                f.write("\n")
            print(f"✅ 已创建空白白名单文件 {whitelist_file}")
        except Exception as e:
            print(f"❌ 创建白名单文件失败: {e}")
        return whitelist_data
    
    try:
        with open(whitelist_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # 处理频道定义格式：url=..., name=..., group=..., logo=...
                if line.startswith("url="):
                    try:
                        # 解析频道定义
                        params = {}
                        for part in line.split(','):
                            part = part.strip()
                            if '=' in part:
                                key, value = part.split('=', 1)
                                params[key.strip()] = value.strip()
                        
                        if 'url' in params:
                            url = params['url']
                            name = params.get('name', '白名单频道')
                            group = params.get('group', '白名单')
                            logo = params.get('logo', '')
                            quality = params.get('quality', '未知')
                            
                            channel_info = {
                                'url': url,
                                'name': name,
                                'group': group,
                                'logo': logo,
                                'quality': quality,
                                'is_whitelist': True
                            }
                            whitelist_data['channels'].append(channel_info)
                            whitelist_data['urls'].add(url)
                            print(f"   ✅ 加载白名单频道: {name} - {url[:50]}...")
                    except Exception as e:
                        print(f"⚠️  白名单第{line_num}行解析失败: {line} - {e}")
                
                # 处理完整URL
                elif line.startswith("http://") or line.startswith("https://"):
                    whitelist_data['urls'].add(line)
                    # 如果是直播源URL，也自动创建频道
                    if any(ext in line.lower() for ext in ['.m3u8', '.m3u', '.ts', '.flv', '.rtmp', '.rtsp']):
                        # 从URL中提取频道名称
                        try:
                            parsed = urlparse(line)
                            hostname = parsed.netloc
                            name = f"白名单-{hostname}"
                            
                            channel_info = {
                                'url': line,
                                'name': name,
                                'group': '白名单',
                                'logo': '',
                                'quality': '未知',
                                'is_whitelist': True
                            }
                            whitelist_data['channels'].append(channel_info)
                        except:
                            pass
                
                # 处理正则表达式
                elif line.startswith('/') and line.endswith('/'):
                    whitelist_data['patterns'].add(line)
                
                # 处理通配符规则
                else:
                    whitelist_data['patterns'].add(line)
        
        print(f"✅ 从 {whitelist_file} 加载白名单:")
        print(f"   规则数量: {len(whitelist_data['patterns'])} 个")
        print(f"   URL数量: {len(whitelist_data['urls'])} 个")
        print(f"   频道数量: {len(whitelist_data['channels'])} 个")
        
        # 显示白名单内容（最多显示10条）
        if whitelist_data['patterns'] and len(whitelist_data['patterns']) <= 10:
            print(f"   规则内容:")
            for item in sorted(whitelist_data['patterns']):
                print(f"     - {item}")
        
    except Exception as e:
        print(f"⚠️  读取白名单失败: {e}")
    
    return whitelist_data

def is_in_whitelist(url, whitelist_data, config):
    """检查URL是否在白名单中"""
    if not config['ENABLE_WHITELIST'] or not whitelist_data:
        return False
    
    url_lower = url.lower()
    
    # 检查完整URL匹配
    if url in whitelist_data['urls']:
        return True
    
    # 检查规则匹配
    for pattern in whitelist_data['patterns']:
        pattern_lower = pattern.lower()
        
        # 通配符匹配
        if pattern.startswith('*') and pattern.endswith('*'):
            pattern_clean = pattern[1:-1]
            if pattern_clean in url_lower:
                return True
        
        # 正则表达式匹配（以/开头和结尾）
        elif pattern.startswith('/') and pattern.endswith('/'):
            try:
                regex_pattern = pattern[1:-1]
                if re.search(regex_pattern, url_lower):
                    return True
            except re.error:
                continue  # 正则表达式有误，跳过
        
        # 部分匹配（包含关系）
        elif pattern_lower in url_lower:
            return True
    
    return False

def load_blacklist(config):
    """加载黑名单"""
    if not config['ENABLE_BLACKLIST']:
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

def save_to_blacklist(slow_urls, config, reason="响应时间超过阈值"):
    """保存慢速URL到黑名单"""
    if not config['ENABLE_BLACKLIST'] or not slow_urls:
        return
    
    # 加载现有黑名单
    existing_blacklist = load_blacklist(config)
    
    # 添加新的慢速URL
    existing_blacklist.update(slow_urls)
    
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            f.write("# 直播源黑名单\n")
            f.write("# 该文件包含测试失败的直播源\n")
            f.write("# 每行一个URL，下次更新时会跳过这些源\n")
            f.write("# 生成时间: " + get_beijing_time() + "\n")
            f.write(f"# 过滤原因: {reason}\n")
            f.write(f"# 配置文件: config.txt\n")
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