#!/usr/bin/env python3
"""
M3U文件生成模块
"""
import os
import json
from pathlib import Path
from .config import PLAYER_SUPPORT, SPEED_TEST_TIMEOUT, PROVINCES
from .channel_processor import get_channel_sort_key
from .utils import create_safe_filename


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
                f.write(f"# 电视直播源 - IPv6优先多源合并版（带黑名单过滤）\n")
                f.write(f"# 每个电视台只显示一个条目，IPv6源优先排列\n")
                f.write(f"# 播放器切换源方法：PotPlayer按Alt+W，VLC右键选择源\n")
                f.write(f"# 排序规则：IPv6源 > 4K > 高清 > 标清 > 流畅\n")
                f.write(f"# 已过滤黑名单慢速源（响应时间 > {SPEED_TEST_TIMEOUT}秒）\n")
            elif mode == "separate":
                f.write(f"# 电视直播源 - IPv6优先多源分离版（带黑名单过滤）\n")
                f.write(f"# 同名电视台显示为多个条目，IPv6源优先，播放器自动合并\n")
                f.write(f"# 已过滤黑名单慢速源（响应时间 > {SPEED_TEST_TIMEOUT}秒）\n")
            else:
                f.write(f"# 电视直播源 - IPv6优先精简版（带黑名单过滤）\n")
                f.write(f"# 每个电视台只保留最佳源（IPv6优先）\n")
                f.write(f"# 已过滤黑名单慢速源（响应时间 > {SPEED_TEST_TIMEOUT}秒）\n")
            
            f.write(f"# 更新时间(北京时间): {timestamp}\n")
            f.write(f"# 电视台总数: {len(merged_channels)}\n")
            f.write(f"# 播放器支持: {', '.join(PLAYER_SUPPORT.keys())}\n")
            f.write(f"# 特点: 移除技术参数，统一央视频道命名，按省份分类地方台，IPv6优先，黑名单过滤\n\n")
            
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
                        
                        # 统计快速源数量（速度信息）
                        fast_sources = [s for s in channel['sources'] if s.get('speed') and s['speed'] <= 2.0]
                        fast_count = len(fast_sources)
                        
                        if mode == "multi":
                            # PotPlayer/VLC多源格式：一个条目包含多个URL，用"|"分隔
                            source_desc = []
                            if ipv6_count > 0:
                                source_desc.append(f"{ipv6_count}IPv6")
                            if fast_count > 0:
                                source_desc.append(f"{fast_count}快速")
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
                                if source.get('speed'):
                                    speed_info = f" ({source['speed']:.1f}s)"
                                
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
                            
                            # 首先找IPv6快速源
                            for source in channel['sources']:
                                if source.get('is_ipv6', False) and source.get('speed') and source['speed'] <= 2.0:
                                    best_source = source
                                    break
                            
                            # 然后找IPv6高清源
                            if not best_source:
                                for source in channel['sources']:
                                    if source.get('is_ipv6', False) and source['quality'] == "高清":
                                        best_source = source
                                        break
                            
                            # 然后找IPv4快速源
                            if not best_source:
                                for source in channel['sources']:
                                    if not source.get('is_ipv6', False) and source.get('speed') and source['speed'] <= 2.0:
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
                            if best_source.get('speed'):
                                line += f' tvg-speed="{best_source["speed"]:.1f}s"'
                                display_name = f"{display_name} ({best_source['speed']:.1f}s)"
                            line += f',{display_name}\n'
                            line += f"{best_source['url']}\n"
                            f.write(line)
        
        print(f"  ✅ {output_file} 生成成功")
        return True
    except Exception as e:
        print(f"  ❌ 生成{output_file}失败: {e}")
        return False


def generate_category_m3us(merged_channels, categories, final_category_order, timestamp):
    """生成分类M3U文件"""
    print("\n📄 生成分类文件（IPv6优先多源合并格式）...")
    
    # 创建分类目录
    Path("categories").mkdir(exist_ok=True)
    
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
                safe_category_name = create_safe_filename(category)
                filename = f"categories/{safe_category_name}.m3u"
                
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    f.write(f"# {category}频道列表（IPv6优先多源合并版，带黑名单过滤）\n")
                    f.write(f"# 更新时间(北京时间): {timestamp}\n")
                    f.write(f"# 电视台数量: {len(cat_channels)}\n")
                    f.write(f"# 说明: 每个电视台包含多个源，IPv6源优先，PotPlayer按Alt+W切换\n")
                    f.write(f"# 已过滤黑名单慢速源（响应时间 > {SPEED_TEST_TIMEOUT}秒）\n\n")
                    
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


def generate_json_file(merged_channels, timestamp, sources, success_sources, failed_sources, 
                       all_channels, filtered_channels, blacklisted_count, blacklist, slow_urls):
    """生成合并的JSON文件（包含所有源信息）"""
    print("\n📄 生成 channels.json...")
    try:
        # 创建频道列表
        channel_list = []
        
        # 统计信息
        multi_source_count = sum(1 for c in merged_channels.values() if len(c['sources']) > 1)
        single_source_count = len(merged_channels) - multi_source_count
        ipv6_channel_count = sum(1 for c in merged_channels.values() if any(s.get('is_ipv6', False) for s in c['sources']))
        fast_channel_count = sum(1 for c in merged_channels.values() if any(s.get('speed') and s['speed'] <= 2.0 for s in c['sources']))
        
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
                    'speed': source.get('speed')
                })
            
            # 统计IPv6源数量
            ipv6_count = sum(1 for s in sources_info if s.get('is_ipv6', False))
            
            # 统计快速源数量
            fast_count = sum(1 for s in sources_info if s.get('speed') and s['speed'] <= 2.0)
            
            # 频道信息
            channel_info = {
                'clean_name': clean_name,
                'original_names': list(set(channel_data['original_names'])),  # 去重
                'category': channel_data['category'],
                'source_count': len(channel_data['sources']),
                'ipv6_source_count': ipv6_count,
                'fast_source_count': fast_count,
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
        
        # 分类统计
        category_stats = {}
        for channel in merged_channels.values():
            category = channel['category']
            if category in category_stats:
                category_stats[category] += 1
            else:
                category_stats[category] = 1
        
        # 创建JSON数据
        json_data = {
            'metadata': {
                'version': '7.0.0',
                'last_updated': timestamp,
                'tool': 'tv_collector',
                'author': 'TV Collector Team'
            },
            'stats': {
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
                'fast_channels': fast_channel_count,
                'blacklist_stats': blacklist_stats,
                'category_stats': category_stats
            },
            'settings': {
                'speed_test_timeout': SPEED_TEST_TIMEOUT,
                'max_workers': 20,
                'source_file': 'sources.txt',
                'blacklist_file': 'blacklist.txt'
            },
            'channels': channel_list,
            'player_support': PLAYER_SUPPORT
        }
        
        # 写入文件
        with open("channels.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"  ✅ channels.json 生成成功，包含 {len(merged_channels)} 个电视台的详细信息")
        return True
    except Exception as e:
        print(f"  ❌ 生成channels.json失败: {e}")
        return False