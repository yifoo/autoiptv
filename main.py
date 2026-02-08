#!/usr/bin/env python3
"""
电视直播源收集脚本 - 带黑白名单的IPv6优先多源合并版
主程序入口
"""

import os
import sys
import time
import concurrent.futures
from pathlib import Path

# 导入自定义模块
from config.config_loader import load_config, load_sources_from_file
from utils.black_white_list import load_whitelist, load_blacklist, save_to_blacklist, is_in_whitelist, get_beijing_time
from utils.speed_test import test_url_speed, is_ipv6_url
from utils.m3u_processor import fetch_m3u, parse_channels, merge_channels
from utils.channel_cleaner import clean_channel_name
from config.categories import categorize_channel, get_channel_sort_key
from outputs.m3u_generator import generate_multi_source_m3u
from outputs.json_generator import generate_json_file

def print_header():
    """打印脚本头部信息"""
    print("=" * 70)
    print("电视直播源收集脚本 v10.0 - 新增广播和MV分类版")
    print("功能：支持配置黑名单/白名单/测速开关，白名单自动加入，IPv6优先，智能测速过滤")
    print("特点：新增调频广播和歌曲MV分类，更完善的频道分类系统")
    print("播放器：支持PotPlayer、VLC、TiviMate、Kodi等多源切换功能")
    print("=" * 70)

def test_urls_with_progress(urls, blacklist, whitelist_data, config):
    """并发测试URL速度，显示进度，考虑白名单"""
    if not config['ENABLE_SPEED_TEST']:
        print("⚡ 测速功能已禁用，跳过速度测试")
        return {}, set(), {}
    
    results = {}
    slow_urls = set()
    detailed_results = {}
    
    print(f"⚡ 开始智能速度测试")
    print(f"📊 配置: 连接超时={config['CONNECT_TIMEOUT']}s, 流测试超时={config['STREAM_TIMEOUT']}s")
    print(f"📊 需要测试 {len(urls)} 个URL")
    
    # 过滤掉已经在黑名单中的URL（如果黑名单启用且白名单不覆盖）
    urls_to_test = []
    skipped_blacklisted = 0
    whitelist_override_count = 0
    
    for url in urls:
        # 检查是否在白名单中
        is_whitelisted = config['ENABLE_WHITELIST'] and is_in_whitelist(url, whitelist_data, config)
        
        # 检查是否在黑名单中
        is_blacklisted = config['ENABLE_BLACKLIST'] and (url in blacklist)
        
        if is_whitelisted and config['WHITELIST_OVERRIDE_BLACKLIST']:
            # 白名单覆盖黑名单，即使URL在黑名单中也测试
            urls_to_test.append(url)
            if is_blacklisted:
                whitelist_override_count += 1
        elif not is_blacklisted:
            # URL不在黑名单中，正常测试
            urls_to_test.append(url)
        else:
            # URL在黑名单中且不在白名单中，跳过
            skipped_blacklisted += 1
    
    print(f"🔍 实际需要测试 {len(urls_to_test)} 个URL")
    if skipped_blacklisted > 0:
        print(f"   跳过了 {skipped_blacklisted} 个黑名单中的URL")
    if whitelist_override_count > 0:
        print(f"   白名单覆盖了 {whitelist_override_count} 个黑名单URL")
    
    if not urls_to_test:
        print("✅ 所有URL都在黑名单中，跳过速度测试")
        return results, slow_urls, detailed_results
    
    # 按URL类型分组（M3U8优先测试）
    m3u8_urls = []
    other_urls = []
    whitelist_m3u8 = []
    whitelist_other = []
    
    for url in urls_to_test:
        is_whitelisted = config['ENABLE_WHITELIST'] and is_in_whitelist(url, whitelist_data, config)
        
        if '.m3u8' in url.lower():
            if is_whitelisted:
                whitelist_m3u8.append(url)
            else:
                m3u8_urls.append(url)
        else:
            if is_whitelisted:
                whitelist_other.append(url)
            else:
                other_urls.append(url)
    
    print(f"  M3U8流媒体源: {len(m3u8_urls)} 个普通, {len(whitelist_m3u8)} 个白名单")
    print(f"  其他类型源: {len(other_urls)} 个普通, {len(whitelist_other)} 个白名单")
    
    # 合并测试列表：白名单优先
    test_order = whitelist_m3u8 + m3u8_urls + whitelist_other + other_urls
    
    # 使用线程池并发测试
    with concurrent.futures.ThreadPoolExecutor(max_workers=config['MAX_WORKERS']) as executor:
        # 提交所有测试任务
        future_to_url = {executor.submit(test_url_speed, url, config): url for url in test_order}
        
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
                    
                    # 检查是否在白名单中
                    is_whitelisted = config['ENABLE_WHITELIST'] and is_in_whitelist(url, whitelist_data, config)
                    
                    # 判断是否为慢速源（白名单可忽略）
                    if score < config['MIN_SPEED_SCORE'] and not (is_whitelisted and config['WHITELIST_IGNORE_SPEED_TEST']):
                        slow_urls.add(url)
                        speed_desc = f"评分低({score:.2f})"
                    else:
                        speed_desc = f"评分{score:.2f}"
                    
                    # 标记白名单
                    if is_whitelisted:
                        speed_desc = f"✅白名单 {speed_desc}"
                    
                    # 每测试5个URL显示一次进度
                    if completed % 5 == 0 or completed == total:
                        elapsed = time.time() - start_time
                        avg_time = elapsed / completed if completed > 0 else 0
                        remaining = (total - completed) * avg_time if avg_time > 0 else 0
                        
                        print(f"  ⏳ {completed}/{total} ({completed/total*100:.1f}%) "
                              f"用时:{elapsed:.1f}s 剩余:{remaining:.0f}s "
                              f"最新:{speed_desc} {url[:50]}...")
                else:
                    # 失败情况：白名单可忽略失败
                    is_whitelisted = config['ENABLE_WHITELIST'] and is_in_whitelist(url, whitelist_data, config)
                    if not (is_whitelisted and config['WHITELIST_IGNORE_SPEED_TEST']):
                        slow_urls.add(url)
                    
                    error_msg = result.get('error', '未知错误')
                    if is_whitelisted:
                        print(f"  ⚠️  白名单失败: {url[:60]}... - {error_msg}")
                    else:
                        print(f"  ❌ 失败: {url[:60]}... - {error_msg}")
                    
            except Exception as e:
                url = future_to_url[future]
                # 白名单可忽略异常
                is_whitelisted = config['ENABLE_WHITELIST'] and is_in_whitelist(url, whitelist_data, config)
                if not (is_whitelisted and config['WHITELIST_IGNORE_SPEED_TEST']):
                    slow_urls.add(url)
                
                detailed_results[url] = {
                    'success': False,
                    'error': f"测试异常: {str(e)}",
                    'score': 0.0
                }
                
                if is_whitelisted:
                    print(f"  ⚠️  白名单测试异常: {url[:60]}... - {str(e)[:50]}")
                else:
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

def add_whitelist_channels(whitelist_data, config):
    """添加白名单频道到频道列表"""
    if not config['ENABLE_WHITELIST'] or not config['WHITELIST_AUTO_ADD']:
        return []
    
    whitelist_channels = []
    
    if 'channels' in whitelist_data and whitelist_data['channels']:
        print(f"\n📋 自动添加白名单频道...")
        for channel_info in whitelist_data['channels']:
            url = channel_info['url']
            name = channel_info['name']
            group = channel_info['group']
            logo = channel_info['logo']
            quality = channel_info['quality']
            is_whitelist = channel_info.get('is_whitelist', True)
            
            # 清理频道名称
            clean_name = clean_channel_name(name)
            
            # 创建频道对象
            channel = {
                'original_name': name,
                'clean_name': clean_name,
                'url': url,
                'group': group,
                'logo': logo,
                'quality': quality,
                'source': 'whitelist',
                'extinf_line': f'#EXTINF:-1 tvg-name="{clean_name}" group-title="{group}" tvg-logo="{logo}",{clean_name}',
                'is_whitelist': is_whitelist
            }
            
            whitelist_channels.append(channel)
            print(f"  ✅ 添加白名单频道: {clean_name} - {url[:50]}...")
    
    return whitelist_channels

def fetch_whitelist_streams(whitelist_data, config):
    """获取白名单中的M3U文件流"""
    if not config['ENABLE_WHITELIST']:
        return []
    
    whitelist_channels = []
    
    # 检查白名单中的M3U文件URL
    print(f"\n📡 检查白名单中的M3U文件...")
    for url in whitelist_data.get('urls', []):
        # 检查是否是M3U文件
        if any(ext in url.lower() for ext in ['.m3u', '.m3u8']):
            print(f"  处理白名单M3U文件: {url[:60]}...")
            try:
                content = fetch_m3u(url)
                if content:
                    channels = parse_channels(content, f"whitelist:{url}")
                    # 标记这些频道为白名单频道
                    for channel in channels:
                        channel['is_whitelist'] = True
                    whitelist_channels.extend(channels)
                    print(f"    ✅ 解析到 {len(channels)} 个频道")
                else:
                    print(f"    ❌ 无法获取内容")
            except Exception as e:
                print(f"    ❌ 处理失败: {e}")
    
    return whitelist_channels

def main():
    """主函数"""
    print_header()
    
    # 1. 加载配置和源列表
    config = load_config()
    sources = load_sources_from_file()
    
    if not sources:
        print("❌ 没有可用的数据源，请检查sources.txt文件")
        return
    
    # 2. 加载黑名单和白名单
    print("📋 加载黑名单和白名单...")
    blacklist = load_blacklist(config)
    whitelist_data = load_whitelist(config)
    
    # 显示优先级说明
    if config['ENABLE_WHITELIST'] and config['ENABLE_BLACKLIST']:
        if config['WHITELIST_OVERRIDE_BLACKLIST']:
            print("⚠️  优先级: 白名单 > 黑名单（白名单URL将不会被黑名单过滤）")
        else:
            print("⚠️  优先级: 黑名单 > 白名单（黑名单中的URL即使也在白名单中也会被过滤）")
    
    # 主收集过程
    print("🚀 开始采集电视直播源...")
    
    all_channels = []
    success_sources = 0
    failed_sources = []
    
    # 3. 收集所有频道的原始数据
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
    
    # 4. 添加白名单频道
    if config['ENABLE_WHITELIST'] and config['WHITELIST_AUTO_ADD']:
        # 添加白名单定义的频道
        whitelist_defined_channels = add_whitelist_channels(whitelist_data, config)
        if whitelist_defined_channels:
            all_channels.extend(whitelist_defined_channels)
            print(f"✅ 添加了 {len(whitelist_defined_channels)} 个白名单定义的频道")
        
        # 获取白名单中的M3U文件流
        whitelist_stream_channels = fetch_whitelist_streams(whitelist_data, config)
        if whitelist_stream_channels:
            all_channels.extend(whitelist_stream_channels)
            print(f"✅ 添加了 {len(whitelist_stream_channels)} 个白名单M3U文件中的频道")
    
    # 5. 提取所有唯一的URL进行速度测试
    print("\n📊 提取所有唯一URL...")
    all_urls = set()
    for channel in all_channels:
        all_urls.add(channel['url'])
    
    print(f"   发现 {len(all_urls)} 个唯一URL")
    
    # 6. 进行智能速度测试
    print("\n⚡ 开始智能速度测试...")
    speed_test_results, slow_urls, detailed_results = test_urls_with_progress(
        all_urls, blacklist, whitelist_data, config
    )
    
    # 7. 保存失败和低质量URL到黑名单
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
        save_to_blacklist(slow_urls, config, reason)
    elif slow_urls:
        print(f"\n⚠️  发现 {len(slow_urls)} 个低质量源，但黑名单或测速功能已禁用，不保存")
    
    # 8. 过滤掉黑名单中的频道
    print("\n🚫 过滤黑名单中的频道...")
    filtered_channels = []
    blacklisted_count = 0
    whitelisted_count = 0
    
    for channel in all_channels:
        url = channel['url']
        is_whitelisted = config['ENABLE_WHITELIST'] and is_in_whitelist(url, whitelist_data, config)
        is_blacklisted = config['ENABLE_BLACKLIST'] and (url in blacklist or url in slow_urls)
        
        # 应用白名单规则
        if is_whitelisted and config['WHITELIST_OVERRIDE_BLACKLIST']:
            # 白名单覆盖黑名单，即使URL在黑名单中也保留
            filtered_channels.append(channel)
            whitelisted_count += 1
            if is_blacklisted:
                print(f"   ✅ 白名单覆盖: {channel['clean_name']} - 黑名单URL被保留")
        elif not is_blacklisted:
            # 不在黑名单中，正常保留
            filtered_channels.append(channel)
        else:
            # 在黑名单中且不在白名单中，过滤掉
            blacklisted_count += 1
    
    print(f"   原始频道数: {len(all_channels)}")
    print(f"   过滤后频道数: {len(filtered_channels)}")
    print(f"   黑名单过滤数: {blacklisted_count}")
    if whitelisted_count > 0:
        print(f"   白名单保留数: {whitelisted_count}")
    
    if len(filtered_channels) == 0:
        print("\n❌ 所有频道都被黑名单过滤，退出")
        return
    
    # 9. 合并同名电视台
    print("\n🔄 正在合并同名电视台...")
    merged_channels = merge_channels(filtered_channels, detailed_results)
    print(f"   合并后: {len(merged_channels)} 个唯一电视台")
    
    # 10. 显示统计信息
    multi_source_count = sum(1 for c in merged_channels.values() if len(c['sources']) > 1)
    single_source_count = len(merged_channels) - multi_source_count
    ipv6_channel_count = sum(1 for c in merged_channels.values() if any(s.get('is_ipv6', False) for s in c['sources']))
    whitelist_channel_count = sum(1 for c in merged_channels.values() if any(s.get('is_whitelist', False) for s in c['sources']))
    high_quality_channel_count = sum(1 for c in merged_channels.values() if any(s.get('speed_score', 0) >= 0.7 for s in c['sources']))
    
    print(f"   多源电视台: {multi_source_count} 个")
    print(f"   单源电视台: {single_source_count} 个")
    print(f"   含IPv6源电视台: {ipv6_channel_count} 个")
    print(f"   含白名单源电视台: {whitelist_channel_count} 个")
    if config['ENABLE_SPEED_TEST']:
        print(f"   含高质量源电视台: {high_quality_channel_count} 个")
    
    # 11. 按分类组织频道
    categories = {}
    for channel in merged_channels.values():
        category = channel['category']
        if category not in categories:
            categories[category] = []
        categories[category].append(channel)
    
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
    final_category_order = fixed_categories + province_categories + other_categories
    
    # 确保每个分类都存在（即使为空）
    for category in final_category_order:
        if category not in categories:
            categories[category] = []
    
    # 12. 生成文件
    timestamp = get_beijing_time()
    print(f"\n📅 当前北京时间: {timestamp}")
    
    # 创建输出目录
    Path("categories").mkdir(exist_ok=True)
    Path("merged").mkdir(exist_ok=True)
    
    # 13. 生成多源合并版M3U
    print("\n📄 生成 live_sources.m3u（IPv6优先多源合并版 - PotPlayer/VLC格式）...")
    generate_multi_source_m3u(
        merged_channels, categories, final_category_order, 
        timestamp, "live_sources.m3u", config,
        sources, success_sources, failed_sources, mode="multi"
    )
    
    # 14. 生成多源分离版M3U
    print("\n📄 生成 merged/多源分离版.m3u（IPv6优先多源分离版 - TiviMate/Kodi格式）...")
    generate_multi_source_m3u(
        merged_channels, categories, final_category_order,
        timestamp, "merged/多源分离版.m3u", config,
        sources, success_sources, failed_sources, mode="separate"
    )
    
    # 15. 生成精简版M3U
    print("\n📄 生成 merged/精简版.m3u（IPv6优先单源精简版）...")
    generate_multi_source_m3u(
        merged_channels, categories, final_category_order,
        timestamp, "merged/精简版.m3u", config,
        sources, success_sources, failed_sources, mode="single"
    )
    
    # 16. 生成分类M3U文件
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
                    f.write(f"# 配置文件: config.txt\n")
                    f.write(f"# 黑名单功能: {'启用' if config['ENABLE_BLACKLIST'] else '禁用'}\n")
                    f.write(f"# 白名单功能: {'启用' if config['ENABLE_WHITELIST'] else '禁用'}\n")
                    f.write(f"# 测速功能: {'启用' if config['ENABLE_SPEED_TEST'] else '禁用'}\n\n")
                    
                    for channel in sorted_channels:
                        # 选择主logo（第一个非空的logo）
                        main_logo = channel['logos'][0] if channel['logos'] else ""
                        source_count = len(channel['sources'])
                        
                        # 统计IPv6源数量
                        ipv6_count = sum(1 for s in channel['sources'] if s.get('is_ipv6', False))
                        
                        # 统计白名单源数量
                        whitelist_count = sum(1 for s in channel['sources'] if s.get('is_whitelist', False))
                        
                        # PotPlayer/VLC多源格式
                        source_desc = []
                        if ipv6_count > 0:
                            source_desc.append(f"{ipv6_count}IPv6")
                        if whitelist_count > 0:
                            source_desc.append(f"{whitelist_count}白名单")
                        if source_count > ipv6_count + whitelist_count:
                            source_desc.append(f"{source_count-ipv6_count-whitelist_count}普通")
                        
                        if source_desc:
                            display_name = f"{channel['clean_name']} [{'+'.join(source_desc)}]"
                        else:
                            display_name = f"{channel['clean_name']} [{source_count}源]"
                        
                        # 收集所有URL（IPv6优先，白名单优先）
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
                
                print(f"  ✅ 生成 {filename}")
            except Exception as e:
                print(f"  ❌ 生成 {filename} 失败: {e}")
    
    # 17. 生成JSON文件
    print("\n📄 生成 channels.json...")
    generate_json_file(
        merged_channels, categories, config,
        sources, success_sources, failed_sources,
        all_channels, filtered_channels,
        blacklisted_count, whitelisted_count,
        blacklist, slow_urls, whitelist_data,
        timestamp
    )
    
    # 18. 打印总结信息
    print(f"\n🎉 所有文件生成完成！")
    print(f"📊 统计:")
    print(f"  - 电视台总数: {len(merged_channels)}")
    print(f"  - 多源电视台: {multi_source_count}")
    print(f"  - 单源电视台: {single_source_count}")
    print(f"  - 含IPv6源电视台: {ipv6_channel_count}")
    print(f"  - 含白名单源电视台: {whitelist_channel_count}")
    if config['ENABLE_SPEED_TEST']:
        print(f"  - 含高质量源电视台: {high_quality_channel_count}")
    print(f"  - 原始频道数: {len(all_channels)}")
    print(f"  - 过滤后频道数: {len(filtered_channels)}")
    print(f"  - 黑名单过滤数: {blacklisted_count}")
    if whitelisted_count > 0:
        print(f"  - 白名单保留数: {whitelisted_count}")
    print(f"  - 数据源: {len(sources)}")
    if config['ENABLE_BLACKLIST']:
        print(f"  - 黑名单条目: {len(blacklist) + len(slow_urls)}")
    if config['ENABLE_WHITELIST']:
        print(f"  - 白名单条目: {len(whitelist_data.get('patterns', set())) + len(whitelist_data.get('urls', set()))}")
    
    print(f"📁 生成的文件:")
    print(f"  - live_sources.m3u (IPv6优先多源合并版 - PotPlayer/VLC格式)")
    print(f"  - merged/多源分离版.m3u (IPv6优先多源分离版 - TiviMate/Kodi格式)")
    print(f"  - merged/精简版.m3u (IPv6优先单源精简版)")
    print(f"  - channels.json (详细数据)")
    print(f"  - categories/*.m3u (分类列表)")
    if config['ENABLE_BLACKLIST']:
        print(f"  - blacklist.txt (低质量源黑名单)")
    if config['ENABLE_WHITELIST']:
        print(f"  - {config['WHITELIST_FILE']} (重要源白名单)")
    
    print(f"\n🎮 播放器使用说明:")
    print(f"  1. PotPlayer/VLC: 使用 live_sources.m3u，播放时按Alt+W切换源")
    print(f"  2. TiviMate/Kodi: 使用 merged/多源分离版.m3u，自动合并相同名称频道")
    print(f"  3. 其他播放器: 使用 merged/精简版.m3u，每个电视台IPv6源优先")

if __name__ == "__main__":
    main()