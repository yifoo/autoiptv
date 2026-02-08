#!/usr/bin/env python3
"""
配置加载模块
"""

import os

CONFIG_FILE = "config.txt"

def load_config():
    """加载配置文件"""
    config = {
        'ENABLE_BLACKLIST': True,      # 是否启用黑名单
        'ENABLE_WHITELIST': True,      # 是否启用白名单
        'ENABLE_SPEED_TEST': True,     # 是否启用测速
        'CONNECT_TIMEOUT': 3,          # 连接超时时间
        'STREAM_TIMEOUT': 10,          # 流媒体测试超时时间
        'MIN_SPEED_SCORE': 0.5,        # 最低速度评分
        'MAX_WORKERS': 20,             # 并发测试线程数
        'WHITELIST_FILE': 'whitelist.txt',  # 白名单文件路径
        'WHITELIST_OVERRIDE_BLACKLIST': True,  # 白名单覆盖黑名单
        'WHITELIST_IGNORE_SPEED_TEST': True,   # 白名单忽略速度测试
        'WHITELIST_AUTO_ADD': True,    # 白名单自动加入直播源
    }
    
    if not os.path.exists(CONFIG_FILE):
        print(f"📝 配置文件 {CONFIG_FILE} 不存在，使用默认配置")
        print(f"   黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}")
        print(f"   白名单功能: {'启用' if config['ENABLE_WHITELIST'] else '禁用'}")
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
                    if key in ['ENABLE_BLACKLIST', 'ENABLE_WHITELIST', 'ENABLE_SPEED_TEST', 
                               'WHITELIST_OVERRIDE_BLACKLIST', 'WHITELIST_IGNORE_SPEED_TEST',
                               'WHITELIST_AUTO_ADD']:
                        if value.lower() in ['true', 'yes', '1', 'on']:
                            config[key] = True
                        elif value.lower() in ['false', 'no', '0', 'off']:
                            config[key] = False
                        else:
                            print(f"⚠️  配置第{line_num}行: {key} 值 '{value}' 无效，使用默认值 {config[key]}")
                    
                    # 字符串处理
                    elif key in ['WHITELIST_FILE']:
                        config[key] = value
                    
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
        print(f"   白名单功能: {'启用' if config['ENABLE_WHITELIST'] else '禁用'}")
        print(f"   测速功能: {'启用' if config['ENABLE_SPEED_TEST'] else '禁用'}")
        if config['ENABLE_WHITELIST']:
            print(f"   白名单文件: {config['WHITELIST_FILE']}")
            print(f"   覆盖黑名单: {'是' if config['WHITELIST_OVERRIDE_BLACKLIST'] else '否'}")
            print(f"   忽略测速: {'是' if config['WHITELIST_IGNORE_SPEED_TEST'] else '否'}")
            print(f"   自动加入: {'是' if config['WHITELIST_AUTO_ADD'] else '否'}")
        print(f"   连接超时: {config['CONNECT_TIMEOUT']}秒")
        print(f"   流测试超时: {config['STREAM_TIMEOUT']}秒")
        print(f"   最低评分: {config['MIN_SPEED_SCORE']}")
        print(f"   并发线程: {config['MAX_WORKERS']}")
        
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}，使用默认配置")
    
    return config

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