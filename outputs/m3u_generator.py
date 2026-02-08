#!/usr/bin/env python3
"""
M3U文件生成模块
"""

from config.categories import get_channel_sort_key
from utils.black_white_list import get_beijing_time

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

def generate_multi_source_m3u(merged_channels, categories, final_category_order, 
                              timestamp, output_file, config, 
                              sources, success_sources, failed_sources, mode="multi"):
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
                f.write(f"# 电视直播源 - IPv6优先多源合并版（新增广播/MV分类）\n")
                f.write(f"# 每个电视台只显示一个条目，IPv6源优先排列，白名单源标记\n")
                f.write(f"# 播放器切换源方法：PotPlayer按Alt+W，VLC右键选择源\n")
                f.write(f"# 排序规则：IPv6源 > 白名单源 > 4K > 高清 > 标清 > 流畅\n")
                f.write(f"# 新增分类：调频广播、歌曲MV\n")
            elif mode == "separate":
                f.write(f"# 电视直播源 - IPv6优先多源分离版（新增广播/MV分类）\n")
                f.write(f"# 同名电视台显示为多个条目，IPv6源优先，播放器自动合并\n")
            else:
                f.write(f"# 电视直播源 - IPv6优先精简版（新增广播/MV分类）\n")
                f.write(f"# 每个电视台只保留最佳源（IPv6优先，白名单优先）\n")
            
            f.write(f"# 更新时间(北京时间): {timestamp}\n")
            f.write(f"# 电视台总数: {len(merged_channels)}\n")
            f.write(f"# 数据源: {len(sources)} 个 (成功: {success_sources}, 失败: {len(failed_sources)})\n")
            f.write(f"# 特点: 移除技术参数，统一央视频道命名，按省份分类地方台，IPv6优先\n")
            f.write(f"# 配置文件: config.txt\n")
            f.write(f"# 黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}\n")
            f.write(f"# 白名单功能: {'启用' if config['ENABLE_WHITELIST'] else '禁用'}\n")
            f.write(f"# 测速功能: {'启用' if config['ENABLE_SPEED_TEST'] else '禁用'}\n")
            
            if config['ENABLE_WHITELIST']:
                f.write(f"# 白名单文件: {config['WHITELIST_FILE']}\n")
                f.write(f"# 覆盖黑名单: {'是' if config['WHITELIST_OVERRIDE_BLACKLIST'] else '否'}\n")
                f.write(f"# 忽略测速: {'是' if config['WHITELIST_IGNORE_SPEED_TEST'] else '否'}\n")
                f.write(f"# 自动加入: {'是' if config['WHITELIST_AUTO_ADD'] else '否'}\n")
            
            if config['ENABLE_SPEED_TEST']:
                f.write(f"# 已过滤低质量源（评分 < {config['MIN_SPEED_SCORE']}）\n")
            
            f.write(f"# 源文件: sources.txt\n")
            if config['ENABLE_BLACKLIST']:
                f.write(f"# 黑名单: blacklist.txt\n")
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
                    
                    # 在M3U文件中为新增分类添加说明
                    if category in ["调频广播", "歌曲MV"]:
                        f.write(f"\n# 分类: {category} ({len(cat_channels)}个频道) [新增分类]\n")
                    else:
                        f.write(f"\n# 分类: {category} ({len(cat_channels)}个频道)\n")
                    
                    for channel in sorted_channels:
                        # 选择主logo（第一个非空的logo）
                        main_logo = channel['logos'][0] if channel['logos'] else ""
                        source_count = len(channel['sources'])
                        
                        # 统计IPv6源数量
                        ipv6_count = sum(1 for s in channel['sources'] if s.get('is_ipv6', False))
                        
                        # 统计白名单源数量
                        whitelist_count = sum(1 for s in channel['sources'] if s.get('is_whitelist', False))
                        
                        # 统计高质量源数量（评分≥0.7）
                        high_quality_sources = [s for s in channel['sources'] if s.get('speed_score', 0) >= 0.7]
                        high_quality_count = len(high_quality_sources)
                        
                        if mode == "multi":
                            # PotPlayer/VLC多源格式：一个条目包含多个URL，用"|"分隔
                            source_desc = []
                            if ipv6_count > 0:
                                source_desc.append(f"{ipv6_count}IPv6")
                            if whitelist_count > 0:
                                source_desc.append(f"{whitelist_count}白名单")
                            if high_quality_count > 0 and config['ENABLE_SPEED_TEST']:
                                source_desc.append(f"{high_quality_count}高速")
                            if source_count > ipv6_count + whitelist_count:
                                source_desc.append(f"{source_count}源")
                            
                            if source_desc:
                                display_name = f"{channel['clean_name']} [{'+'.join(source_desc)}]"
                            else:
                                display_name = f"{channel['clean_name']} [{source_count}源]"
                            
                            # 收集所有URL（已按优先级排序）
                            urls = []
                            qualities = []
                            ipv6_sources = []
                            whitelist_sources = []
                            other_sources = []
                            
                            for source in channel['sources']:
                                if source.get('is_ipv6', False):
                                    ipv6_sources.append(source)
                                elif source.get('is_whitelist', False):
                                    whitelist_sources.append(source)
                                else:
                                    other_sources.append(source)
                            
                            # 确保IPv6源在前面，然后是白名单源
                            sorted_sources = ipv6_sources + whitelist_sources + other_sources
                            
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
                            if whitelist_count > 0:
                                line += f' tvg-whitelist="true"'
                            line += f',{display_name}\n'
                            line += f"{multi_url}\n"
                            f.write(line)
                            
                        elif mode == "separate":
                            # TiviMate/Kodi格式：相同名称的多个条目，IPv6源优先
                            display_name = channel['clean_name']
                            
                            # 分离不同类型的源
                            ipv6_sources = []
                            whitelist_sources = []
                            other_sources = []
                            for source in channel['sources']:
                                if source.get('is_ipv6', False):
                                    ipv6_sources.append(source)
                                elif source.get('is_whitelist', False):
                                    whitelist_sources.append(source)
                                else:
                                    other_sources.append(source)
                            
                            # 确保IPv6源在前面，然后是白名单源
                            sorted_sources = ipv6_sources + whitelist_sources + other_sources
                            
                            for i, source in enumerate(sorted_sources, 1):
                                source_type = []
                                if source.get('is_ipv6', False):
                                    source_type.append("IPv6")
                                if source.get('is_whitelist', False):
                                    source_type.append("白名单")
                                
                                source_type_str = "".join(source_type)
                                if not source_type_str:
                                    source_type_str = "普通"
                                
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
                                if source.get('is_whitelist', False):
                                    line += f' tvg-whitelist="true"'
                                if source_count > 1:
                                    line += f',{display_name} [{source_type_str}源{i}{speed_info}]\n'
                                else:
                                    line += f',{display_name}{speed_info}\n'
                                line += f"{source['url']}\n"
                                f.write(line)
                                
                        else:  # mode == "single"
                            # 精简版：只保留最佳源（IPv6优先，白名单优先）
                            display_name = channel['clean_name']
                            
                            # 选择最佳源（优先选择IPv6白名单源）
                            best_source = None
                            
                            # 如果测速功能启用，优先选择高速源
                            if config['ENABLE_SPEED_TEST']:
                                # 首先找IPv6白名单高速源
                                for source in channel['sources']:
                                    if source.get('is_ipv6', False) and source.get('is_whitelist', False) and source.get('speed_score', 0) >= 0.7:
                                        best_source = source
                                        break
                                
                                # 然后找IPv4白名单高速源
                                if not best_source:
                                    for source in channel['sources']:
                                        if not source.get('is_ipv6', False) and source.get('is_whitelist', False) and source.get('speed_score', 0) >= 0.7:
                                            best_source = source
                                            break
                                
                                # 然后找IPv6高速源
                                if not best_source:
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
                                # 首先找IPv6白名单高清源
                                for source in channel['sources']:
                                    if source.get('is_ipv6', False) and source.get('is_whitelist', False) and source['quality'] == "高清":
                                        best_source = source
                                        break
                                
                                # 然后找IPv4白名单高清源
                                if not best_source:
                                    for source in channel['sources']:
                                        if not source.get('is_ipv6', False) and source.get('is_whitelist', False) and source['quality'] == "高清":
                                            best_source = source
                                            break
                                
                                # 然后找IPv6高清源
                                if not best_source:
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
                            if best_source.get('is_whitelist', False):
                                line += f' tvg-whitelist="true"'
                                display_name = f"{display_name} [白名单]"
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