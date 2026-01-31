#!/usr/bin/env python3
"""
黑名单管理模块
"""
import os
from .config import BLACKLIST_FILE
from .utils import get_beijing_time


def load_blacklist():
    """加载黑名单"""
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
        print(f"📝 {BLACKLIST_FILE} 文件不存在，将创建新文件")
    return blacklist


def save_to_blacklist(slow_urls):
    """保存慢速URL到黑名单"""
    if not slow_urls:
        return
    
    # 加载现有黑名单
    existing_blacklist = load_blacklist()
    
    # 添加新的慢速URL
    existing_blacklist.update(slow_urls)
    
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            f.write("# 直播源黑名单\n")
            f.write("# 该文件包含响应时间超过6秒的慢速直播源\n")
            f.write("# 每行一个URL，下次更新时会跳过这些源\n")
            f.write("# 生成时间: " + get_beijing_time() + "\n\n")
            
            # 排序后写入
            for url in sorted(existing_blacklist):
                f.write(url + "\n")
        
        print(f"📝 已保存 {len(slow_urls)} 个慢速源到 {BLACKLIST_FILE}")
    except Exception as e:
        print(f"❌ 保存黑名单失败: {e}")


def add_to_blacklist(urls, reason="slow"):
    """添加URL到黑名单"""
    if not urls:
        return
    
    existing_blacklist = load_blacklist()
    existing_blacklist.update(urls)
    
    try:
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            f.write("# 直播源黑名单\n")
            f.write("# 该文件包含响应时间超过6秒的慢速直播源\n")
            f.write("# 每行一个URL，下次更新时会跳过这些源\n")
            f.write("# 生成时间: " + get_beijing_time() + "\n")
            f.write(f"# 原因: {reason}\n\n")
            
            # 排序后写入
            for url in sorted(existing_blacklist):
                f.write(url + "\n")
        
        print(f"📝 已将 {len(urls)} 个源添加到黑名单，原因: {reason}")
    except Exception as e:
        print(f"❌ 添加黑名单失败: {e}")


def remove_from_blacklist(urls):
    """从黑名单中移除URL"""
    if not urls:
        return
    
    existing_blacklist = load_blacklist()
    removed_count = 0
    
    for url in urls:
        if url in existing_blacklist:
            existing_blacklist.remove(url)
            removed_count += 1
    
    if removed_count > 0:
        try:
            with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
                f.write("# 直播源黑名单\n")
                f.write("# 该文件包含响应时间超过6秒的慢速直播源\n")
                f.write("# 每行一个URL，下次更新时会跳过这些源\n")
                f.write("# 生成时间: " + get_beijing_time() + "\n\n")
                
                # 排序后写入
                for url in sorted(existing_blacklist):
                    f.write(url + "\n")
            
            print(f"📝 已从黑名单中移除 {removed_count} 个源")
        except Exception as e:
            print(f"❌ 更新黑名单失败: {e}")
    else:
        print("ℹ️  没有找到要移除的URL")


def check_blacklist(url):
    """检查URL是否在黑名单中"""
    blacklist = load_blacklist()
    return url in blacklist


def get_blacklist_stats():
    """获取黑名单统计信息"""
    blacklist = load_blacklist()
    return {
        'total': len(blacklist),
        'urls': sorted(blacklist)
    }