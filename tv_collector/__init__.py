#!/usr/bin/env python3
"""
电视直播源收集包
"""

__version__ = "7.0.0"
__author__ = "TV Collector Team"
__description__ = "电视直播源收集工具，支持IPv6优先、多源合并、黑名单过滤"

print(f"✅ tv_collector v{__version__} 已加载")
print(f"📺 功能: {__description__}")

# 导出主要功能
from .collector import collect_and_process, load_sources_from_file
from .channel_processor import clean_channel_name, categorize_channel
from .blacklist_manager import load_blacklist, save_to_blacklist
from .speed_tester import test_urls_with_progress
from .m3u_generator import (
    generate_multi_source_m3u, 
    generate_category_m3us, 
    generate_json_file
)
from .utils import get_beijing_time, is_ipv6_url, fetch_m3u

# 导出配置
from .config import (
    CLEAN_RULES,
    CCTV_MAPPING,
    CHANNEL_ORDER_RULES,
    CATEGORY_RULES,
    PROVINCES,
    PROVINCE_ABBR,
    PLAYER_SUPPORT,
    SPEED_TEST_TIMEOUT,
    BLACKLIST_FILE
)

__all__ = [
    'collect_and_process',
    'load_sources_from_file',
    'clean_channel_name',
    'categorize_channel',
    'load_blacklist',
    'save_to_blacklist',
    'test_urls_with_progress',
    'generate_multi_source_m3u',
    'generate_category_m3us',
    'generate_json_file',
    'get_beijing_time',
    'is_ipv6_url',
    'fetch_m3u',
    'CLEAN_RULES',
    'CCTV_MAPPING',
    'CHANNEL_ORDER_RULES',
    'CATEGORY_RULES',
    'PROVINCES',
    'PROVINCE_ABBR',
    'PLAYER_SUPPORT',
    'SPEED_TEST_TIMEOUT',
    'BLACKLIST_FILE'
]