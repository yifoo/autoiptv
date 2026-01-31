#!/usr/bin/env python3
"""
电视直播源自动采集工具
"""

import requests
import re
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import hashlib
import json
import os
import sys

# 默认源列表
DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/fanmingming/live/main/tv/m3u/ipv6.m3u",
    "https://raw.githubusercontent.com/chao921125/source/refs/heads/main/iptv/index.m3u"
]

# 源列表文件
SOURCES_FILE = "sources.txt"

# 频道分类规则
CATEGORIES = {
    "央视": ["CCTV", "央视", "中央"],
    "卫视": ["卫视", "湖南卫视", "浙江卫视", "江苏卫视", "北京卫视", "东方卫视"],
    "地方台": ["地方", "都市", "新闻", "公共", "生活", "教育", "少儿"],
    "港澳台": ["凤凰", "翡翠", "明珠", "TVB", "香港", "台湾", "澳门"],
    "体育": ["体育", "足球", "篮球", "NBA", "奥运", "赛事"],
    "电影": ["电影", "影院", "影视频道", "CHC"],
    "音乐": ["音乐", "MTV", "演唱会", "戏曲"],
    "国际": ["BBC", "CNN", "NHK", "DW", "美国", "英国", "法国", "德国", "韩国", "日本"]
}

class TVChannel:
    """电视频道类"""
    
    def __init__(self, name, url, group=None, logo=None):
        self.name = name.strip()
        self.url = url.strip()
        self.group = group
        self.logo = logo
        # 生成唯一ID用于去重
        self.id = hashlib.md5(f"{self.name}_{self.url}".encode()).hexdigest()
    
    def to_m3u(self):
        """转换为M3U格式"""
        line = f'#EXTINF:-1'
        if self.group:
            line += f' group-title="{self.group}"'
        if self.logo:
            line += f' tvg-logo="{self.logo}"'
        line += f',{self.name}\n{self.url}\n'
        return line

class IPTVCollector:
    """IPTV收集器"""
    
    def __init__(self):
        self.channels = []
        self.channel_ids = set()
        self.stats = {
            'total_fetched': 0,
            'total_unique': 0,
            'sources_processed': 0
        }
    
    def load_sources(self):
        """加载源列表"""
        sources = DEFAULT_SOURCES.copy()
        
        # 从文件读取额外源
        if Path(SOURCES_FILE).exists():
            try:
                with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            sources.append(line)
            except Exception as e:
                print(f"⚠️  读取源文件失败: {e}")
        
        print(f"📡 共加载 {len(sources)} 个数据源")
        return sources
    
    def fetch_m3u(self, url):
        """获取M3U文件内容"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response.text
            else:
                print(f"❌ 请求失败 {url}: HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 获取失败 {url}: {e}")
            return None
    
    def parse_m3u(self, content):
        """解析M3U内容"""
        channels = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                # 解析频道信息
                channel_info = self.parse_extinf(line)
                
                # 获取URL
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and not url.startswith('#'):
                        channel = TVChannel(
                            name=channel_info['name'],
                            url=url,
                            group=channel_info.get('group'),
                            logo=channel_info.get('logo')
                        )
                        channels.append(channel)
                        i += 1
            i += 1
        
        return channels
    
    def parse_extinf(self, extinf_line):
        """解析EXTINF行"""
        info = {'name': '未知频道'}
        
        # 提取频道名称（最后逗号后的内容）
        name_match = re.search(r',([^,\n]+)$', extinf_line)
        if name_match:
            info['name'] = name_match.group(1).strip()
        
        # 提取分组
        group_match = re.search(r'group-title="([^"]+)"', extinf_line)
        if group_match:
            info['group'] = group_match.group(1).strip()
        
        # 提取logo
        logo_match = re.search(r'tvg-logo="([^"]+)"', extinf_line)
        if logo_match:
            info['logo'] = logo_match.group(1).strip()
        
        return info
    
    def categorize_channel(self, channel):
        """为频道分类"""
        channel_name = channel.name.lower()
        
        for category, keywords in CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in channel_name:
                    return category
        
        # 如果已有分组，使用原分组
        if channel.group:
            return channel.group
        
        return '其他'
    
    def collect_channels(self):
        """收集所有频道"""
        print("🚀 开始采集电视直播源...")
        print("=" * 50)
        
        sources = self.load_sources()
        
        for idx, source_url in enumerate(sources, 1):
            print(f"\n[{idx}/{len(sources)}] 正在处理: {source_url}")
            
            content = self.fetch_m3u(source_url)
            if not content:
                continue
            
            channels = self.parse_m3u(content)
            print(f"   解析到 {len(channels)} 个频道")
            
            # 去重并添加
            added_count = 0
            for channel in channels:
                if channel.id not in self.channel_ids:
                    self.channel_ids.add(channel.id)
                    self.channels.append(channel)
                    added_count += 1
            
            self.stats['total_fetched'] += len(channels)
            self.stats['sources_processed'] += 1
            print(f"   新增 {added_count} 个唯一频道")
            
            # 避免请求过快
            if idx < len(sources):
                time.sleep(1)
        
        self.stats['total_unique'] = len(self.channels)
        
        print("\n" + "=" * 50)
        print(f"✅ 采集完成！")
        print(f"   处理源数: {self.stats['sources_processed']}/{len(sources)}")
        print(f"   采集频道: {self.stats['total_fetched']}")
        print(f"   去重后: {self.stats['total_unique']}")
        
        return len(self.channels) > 0
    
    def generate_files(self):
        """生成所有输出文件"""
        if not self.channels:
            print("❌ 没有频道数据，无法生成文件")
            return False
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 为频道分类
        categorized = defaultdict(list)
        for channel in self.channels:
            category = self.categorize_channel(channel)
            channel.group = category
            categorized[category].append(channel)
        
        # 创建输出目录
        Path('categories').mkdir(exist_ok=True)
        
        # 1. 生成完整的M3U文件
        self.generate_main_m3u(categorized, timestamp)
        
        # 2. 生成分类M3U文件
        self.generate_category_m3us(categorized, timestamp)
        
        # 3. 生成JSON数据文件
        self.generate_json_data(timestamp)
        
        # 4. 生成README文件
        self.generate_readme(categorized, timestamp)
        
        # 5. 生成HTML页面
        self.generate_html_page(categorized, timestamp)
        
        print("\n📁 文件生成完成:")
        print(f"   ✅ live_sources.m3u (主播放列表)")
        print(f"   ✅ channels.json (数据文件)")
        print(f"   ✅ index.html (网页界面)")
        print(f"   ✅ README.md (说明文档)")
        print(f"   ✅ categories/*.m3u (分类列表)")
        
        return True
    
    def generate_main_m3u(self, categorized, timestamp):
        """生成主M3U文件"""
        with open('live_sources.m3u', 'w', encoding='utf-8') as f:
            f.write('#EXTM3U x-tvg-url=""\n')
            f.write(f'# 电视直播源 - 自动收集\n')
            f.write(f'# 更新时间: {timestamp}\n')
            f.write(f'# 频道总数: {self.stats["total_unique"]}\n')
            f.write(f'# 数据源: {self.stats["sources_processed"]}\n\n')
            
            # 按分类写入频道
            for category in sorted(categorized.keys()):
                channels = sorted(categorized[category], key=lambda x: x.name)
                f.write(f'# 分类: {category} ({len(channels)}个频道)\n')
                for channel in channels:
                    f.write(channel.to_m3u())
    
    def generate_category_m3us(self, categorized, timestamp):
        """生成分类M3U文件"""
        for category, channels in categorized.items():
            if channels:
                filename = f"categories/{category}.m3u"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('#EXTM3U\n')
                    f.write(f'# {category}频道列表\n')
                    f.write(f'# 更新时间: {timestamp}\n')
                    f.write(f'# 频道数量: {len(channels)}\n\n')
                    
                    for channel in sorted(channels, key=lambda x: x.name):
                        f.write(channel.to_m3u())
    
    def generate_json_data(self, timestamp):
        """生成JSON数据文件"""
        channel_data = []
        for channel in sorted(self.channels, key=lambda x: x.name):
            channel_data.append({
                'name': channel.name,
                'url': channel.url,
                'category': channel.group,
                'logo': channel.logo
            })
        
        data = {
            'last_updated': timestamp,
            'total_channels': self.stats['total_unique'],
            'sources_count': self.stats['sources_processed'],
            'channels': channel_data
        }
        
        with open('channels.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def generate_readme(self, categorized, timestamp):
        """生成README文件"""
        readme = f"""# 📺 电视直播源收集项目

自动收集整理多个源的电视直播频道，每日自动更新。

## 📊 统计信息
- **最后更新**: {timestamp}
- **频道总数**: {self.stats['total_unique']}
- **数据源数**: {self.stats['sources_processed']}

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| [live_sources.m3u](live_sources.m3u) | 完整的直播源文件 |
| [channels.json](channels.json) | 频道数据(JSON格式) |
| [index.html](index.html) | 网页播放界面 |
| [sources.txt](sources.txt) | 自定义源列表 |
| categories/ | 按分类的播放列表 |

## 🎯 频道分类

"""
        
        # 添加分类统计
        for category in sorted(categorized.keys()):
            count = len(categorized[category])
            readme += f"- **{category}**: {count} 个频道\n"
        
        readme += """

## 🚀 快速开始

### 方法一：直接播放
1. 下载 [live_sources.m3u](live_sources.m3u) 文件
2. 用支持M3U的播放器打开（如VLC、PotPlayer、IINA等）

### 方法二：按分类使用
进入 [categories/](categories/) 目录，下载需要的分类文件

### 方法三：在线查看
访问 [index.html](index.html) 在线查看频道列表

## ⚙️ 自定义配置

编辑 `sources.txt` 文件可以添加更多数据源，每行一个M3U文件URL。

## ⏰ 自动更新

- **定时更新**: 每天UTC 18:00（北京时间凌晨2点）自动运行
- **手动触发**: 在GitHub Actions页面手动运行
- **源更新触发**: 修改 `sources.txt` 后自动运行

## ⚠️ 免责声明

本项目的直播源来自公开网络，仅用于学习和测试。
请遵守当地法律法规，尊重版权。

---
*自动生成于 {timestamp}*
"""
        
        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(readme)
    
    def generate_html_page(self, categorized, timestamp):
        """生成HTML页面"""
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电视直播源播放列表</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            text-align: center;
        }}
        
        h1 {{
            color: #2c3e50;
            font-size: 2.8rem;
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            color: #7f8c8d;
            font-size: 1.2rem;
            margin-bottom: 20px;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            transition: transform 0.3s ease;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        
        .stat-card h3 {{
            color: #667eea;
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}
        
        .stat-card p {{
            color: #666;
            font-size: 1rem;
        }}
        
        .download-section {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin: 30px 0;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
        }}
        
        .download-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 20px;
        }}
        
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 12px 25px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
        }}
        
        .btn:hover {{
            background: #5a67d8;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}
        
        .btn-secondary {{
            background: #48bb78;
        }}
        
        .btn-secondary:hover {{
            background: #38a169;
        }}
        
        .categories {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 25px;
            margin-top: 30px;
        }}
        
        .category-card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
        }}
        
        .category-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.1);
        }}
        
        .category-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #667eea;
        }}
        
        .category-title {{
            font-size: 1.4rem;
            color: #2c3e50;
            font-weight: 600;
        }}
        
        .channel-count {{
            background: #667eea;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9rem;
        }}
        
        .channel-list {{
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .channel-item {{
            padding: 12px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .channel-item:last-child {{
            border-bottom: none;
        }}
        
        .channel-name {{
            font-weight: 500;
            color: #333;
        }}
        
        .play-btn {{
            padding: 6px 15px;
            background: #48bb78;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: background 0.3s ease;
        }}
        
        .play-btn:hover {{
            background: #38a169;
        }}
        
        footer {{
            margin-top: 50px;
            padding: 30px;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            text-align: center;
            color: #666;
            font-size: 0.9rem;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}
            
            header {{
                padding: 20px;
            }}
            
            h1 {{
                font-size: 2rem;
            }}
            
            .categories {{
                grid-template-columns: 1fr;
            }}
            
            .download-buttons {{
                flex-direction: column;
            }}
            
            .btn {{
                width: 100%;
                text-align: center;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📺 电视直播源播放列表</h1>
            <p class="subtitle">自动收集整理的电视直播频道，每日更新</p>
            
            <div class="stats">
                <div class="stat-card">
                    <h3>{self.stats['total_unique']}</h3>
                    <p>频道总数</p>
                </div>
                <div class="stat-card">
                    <h3>{len(categorized)}</h3>
                    <p>频道分类</p>
                </div>
                <div class="stat-card">
                    <h3>{self.stats['sources_processed']}</h3>
                    <p>数据源数</p>
                </div>
                <div class="stat-card">
                    <h3>{timestamp.split()[0]}</h3>
                    <p>最后更新</p>
                </div>
            </div>
        </header>
        
        <div class="download-section">
            <h2 style="color: #2c3e50; margin-bottom: 20px;">📥 下载播放列表</h2>
            <div class="download-buttons">
                <a href="live_sources.m3u" class="btn">
                    <span style="margin-right: 8px;">⬇️</span>
                    完整列表 (所有频道)
                </a>
                <a href="channels.json" class="btn btn-secondary">
                    <span style="margin-right: 8px;">📊</span>
                    JSON 数据文件
                </a>
                <a href="README.md" class="btn">
                    <span style="margin-right: 8px;">📖</span>
                    项目说明
                </a>
            </div>
            
            <div style="margin-top: 20px;">
                <h3 style="color: #2c3e50; margin-bottom: 15px;">📂 分类列表</h3>
                <div class="download-buttons">
'''

        # 添加分类下载按钮
        for category in sorted(categorized.keys()):
            count = len(categorized[category])
            html += f'''                    <a href="categories/{category}.m3u" class="btn" style="background: #e53e3e;">
                        <span style="margin-right: 8px;">📺</span>
                        {category} ({count})
                    </a>
'''

        html += '''                </div>
            </div>
        </div>
        
        <h2 style="color: white; margin: 30px 0 20px 0;">🎯 频道分类浏览</h2>
        <div class="categories">
'''

        # 添加分类卡片
        for category in sorted(categorized.keys()):
            channels = categorized[category]
            html += f'''            <div class="category-card">
                <div class="category-header">
                    <span class="category-title">{category}</span>
                    <span class="channel-count">{len(channels)} 个频道</span>
                </div>
                <div class="channel-list">
'''
            
            # 显示前10个频道
            for channel in sorted(channels[:10], key=lambda x: x.name):
                html += f'''                    <div class="channel-item">
                        <span class="channel-name">{channel.name}</span>
                        <button class="play-btn" onclick="playChannel('{channel.url}')">播放</button>
                    </div>
'''
            
            if len(channels) > 10:
                html += f'''                    <div class="channel-item" style="justify-content: center; color: #667eea; font-style: italic;">
                        ... 还有 {len(channels) - 10} 个频道
                    </div>
'''
            
            html += '''                </div>
            </div>
'''

        html += f'''        </div>
        
        <footer>
            <p>🔄 本项目自动更新于 GitHub Actions</p>
            <p>📅 最后更新时间: {timestamp}</p>
            <p>🎮 支持 VLC、PotPlayer、IINA、nPlayer 等播放器</p>
            <p style="margin-top: 15px; font-size: 0.8rem; color: #999;">
                提示: 点击"播放"按钮将在新窗口打开直播流，需要播放器支持
            </p>
        </footer>
    </div>
    
    <script>
        function playChannel(url) {{
            if (confirm('是否在播放器中打开: ' + url + '？')) {{
                window.open(url, '_blank');
            }}
        }}
        
        // 自动更新时间
        function updateTime() {{
            const now = new Date();
            const timeStr = now.toLocaleString('zh-CN');
            const timeElement = document.querySelector('footer p:nth-child(2)');
            if (timeElement) {{
                timeElement.textContent = '📅 当前时间: ' + timeStr;
            }}
        }}
        
        // 每秒更新一次时间
        setInterval(updateTime, 1000);
        updateTime();
        
        // 添加平滑滚动
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                const targetId = this.getAttribute('href');
                if (targetId === '#') return;
                const targetElement = document.querySelector(targetId);
                if (targetElement) {{
                    targetElement.scrollIntoView({{
                        behavior: 'smooth',
                        block: 'start'
                    }});
                }}
            }});
        }});
    </script>
</body>
</html>'''
        
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html)

def main():
    """主函数"""
    print("=" * 60)
    print("电视直播源自动采集工具 v2.0")
    print("=" * 60)
    
    collector = IPTVCollector()
    
    try:
        # 收集频道
        if not collector.collect_channels():
            print("\n❌ 没有收集到任何频道，请检查网络或源地址")
            sys.exit(1)
        
        # 生成文件
        if collector.generate_files():
            print("\n✨ 所有文件已成功生成！")
            
            # 输出到GitHub Actions
            if 'GITHUB_OUTPUT' in os.environ:
                with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                    f.write(f'changed=true\n')
                    f.write(f'channels={collector.stats["total_unique"]}\n')
            else:
                print(f"\n📊 统计信息:")
                print(f"changed=true")
                print(f"channels={collector.stats['total_unique']}")
        else:
            print("\n❌ 文件生成失败")
            if 'GITHUB_OUTPUT' in os.environ:
                with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                    f.write('changed=false\n')
    
    except Exception as e:
        print(f"\n💥 发生错误: {e}")
        import traceback
        traceback.print_exc()
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write('changed=false\n')
        sys.exit(1)

if __name__ == "__main__":
    main()