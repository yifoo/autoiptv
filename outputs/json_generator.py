#!/usr/bin/env python3
"""
JSON文件生成模块
"""

import json

def generate_json_file(merged_channels, categories, config, 
                      sources, success_sources, failed_sources,
                      all_channels, filtered_channels,
                      blacklisted_count, whitelisted_count,
                      blacklist, slow_urls, whitelist_data,
                      timestamp):
    """生成合并的JSON文件（包含所有源信息）"""
    try:
        # 统计多源和单源数量
        multi_source_count = sum(1 for c in merged_channels.values() if len(c['sources']) > 1)
        single_source_count = len(merged_channels) - multi_source_count
        
        # 统计IPv6源数量
        ipv6_channel_count = sum(1 for c in merged_channels.values() if any(s.get('is_ipv6', False) for s in c['sources']))
        whitelist_channel_count = sum(1 for c in merged_channels.values() if any(s.get('is_whitelist', False) for s in c['sources']))
        high_quality_channel_count = sum(1 for c in merged_channels.values() if any(s.get('speed_score', 0) >= 0.7 for s in c['sources']))
        
        # 统计分类数量
        category_stats = {}
        for channel in merged_channels.values():
            category = channel['category']
            if category in category_stats:
                category_stats[category] += 1
            else:
                category_stats[category] = 1
        
        # 确定分类顺序
        fixed_categories = ["央视", "卫视", "景区频道", "少儿台", "综艺台", 
                          "港澳台", "体育台", "影视台", "调频广播", "歌曲MV", "其他台"]
        province_categories = []
        other_categories = []
        
        for category in categories.keys():
            if category in fixed_categories:
                continue
            elif any(province in category for province in [
                "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
                "辽宁省", "吉林省", "黑龙江省", "上海市", "江苏省",
                "浙江省", "安徽省", "福建省", "江西省", "山东省",
                "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区",
                "海南省", "重庆市", "四川省", "贵州省", "云南省",
                "西藏自治区", "陕西省", "甘肃省", "青海省", "宁夏回族自治区",
                "新疆维吾尔自治区", "台湾省", "香港", "澳门"
            ]):
                province_categories.append(category)
            else:
                other_categories.append(category)
        
        province_categories.sort()
        
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
                    'is_whitelist': source.get('is_whitelist', False),
                    'priority': source.get('priority', 0),
                    'speed_score': source.get('speed_score', 0.0),
                    'test_details': source.get('test_details', {})
                })
            
            # 统计IPv6源数量
            ipv6_count = sum(1 for s in sources_info if s.get('is_ipv6', False))
            
            # 统计白名单源数量
            whitelist_count = sum(1 for s in sources_info if s.get('is_whitelist', False))
            
            # 统计高质量源数量
            high_quality_count = sum(1 for s in sources_info if s.get('speed_score', 0) >= 0.7)
            
            # 频道信息
            channel_info = {
                'clean_name': clean_name,
                'original_names': list(set(channel_data['original_names'])),  # 去重
                'category': channel_data['category'],
                'source_count': len(channel_data['sources']),
                'ipv6_source_count': ipv6_count,
                'whitelist_source_count': whitelist_count,
                'high_quality_source_count': high_quality_count,
                'logos': channel_data['logos'],
                'sources': sources_info
            }
            channel_list.append(channel_info)
        
        # 黑白名单统计
        blacklist_stats = {
            'total_blacklisted': len(blacklist) + len(slow_urls),
            'previously_blacklisted': len(blacklist),
            'newly_blacklisted': len(slow_urls)
        }
        
        whitelist_stats = {
            'total_whitelisted': len(whitelist_data.get('patterns', set())) + len(whitelist_data.get('urls', set())),
            'patterns_count': len(whitelist_data.get('patterns', set())),
            'urls_count': len(whitelist_data.get('urls', set())),
            'channels_count': len(whitelist_data.get('channels', [])),
            'whitelist_override_blacklist': config['WHITELIST_OVERRIDE_BLACKLIST'],
            'whitelist_ignore_speed_test': config['WHITELIST_IGNORE_SPEED_TEST'],
            'whitelist_auto_add': config['WHITELIST_AUTO_ADD']
        }
        
        # 创建JSON数据
        json_data = {
            'last_updated': timestamp,
            'config': {
                'enable_blacklist': config['ENABLE_BLACKLIST'],
                'enable_whitelist': config['ENABLE_WHITELIST'],
                'enable_speed_test': config['ENABLE_SPEED_TEST'],
                'connect_timeout': config['CONNECT_TIMEOUT'],
                'stream_timeout': config['STREAM_TIMEOUT'],
                'min_speed_score': config['MIN_SPEED_SCORE'],
                'max_workers': config['MAX_WORKERS'],
                'whitelist_file': config['WHITELIST_FILE'],
                'whitelist_override_blacklist': config['WHITELIST_OVERRIDE_BLACKLIST'],
                'whitelist_ignore_speed_test': config['WHITELIST_IGNORE_SPEED_TEST'],
                'whitelist_auto_add': config['WHITELIST_AUTO_ADD']
            },
            'total_channels': len(merged_channels),
            'original_channel_count': len(all_channels),
            'filtered_channel_count': len(filtered_channels),
            'blacklisted_channel_count': blacklisted_count,
            'whitelisted_channel_count': whitelisted_count,
            'sources_count': len(sources),
            'success_sources': success_sources,
            'failed_sources': failed_sources,
            'multi_source_channels': multi_source_count,
            'single_source_channels': single_source_count,
            'ipv6_channels': ipv6_channel_count,
            'whitelist_channels': whitelist_channel_count,
            'high_quality_channels': high_quality_channel_count,
            'category_stats': category_stats,
            'fixed_categories': fixed_categories,
            'province_categories': province_categories,
            'blacklist_stats': blacklist_stats,
            'whitelist_stats': whitelist_stats,
            'sorting_rules': {
                'ipv6_priority': 100,
                'whitelist_priority': 80,
                '4k_priority': 40,
                'hd_priority': 30,
                'sd_priority': 20,
                'fluent_priority': 10
            },
            'channels': channel_list,
            'player_support': {
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
            },
            'source_file': 'sources.txt',
            'blacklist_file': 'blacklist.txt',
            'whitelist_file': config['WHITELIST_FILE'],
            'config_file': 'config.txt'
        }
        
        # 写入文件
        with open("channels.json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"  ✅ channels.json 生成成功，包含 {len(merged_channels)} 个电视台的详细信息")
        return True
    except Exception as e:
        print(f"  ❌ 生成channels.json失败: {e}")
        return False