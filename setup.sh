#!/bin/bash
# 电视直播源收集工具安装脚本

set -e

echo "📦 安装电视直播源收集工具..."
echo "========================================"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要Python3，请先安装Python3"
    exit 1
fi

echo "✅ Python3 已安装: $(python3 --version)"

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ 需要pip3，请先安装pip3"
    exit 1
fi

echo "✅ pip3 已安装"

# 安装依赖
echo "📦 安装Python依赖..."
pip3 install -r requirements.txt

# 创建必要的目录
echo "📁 创建目录结构..."
mkdir -p categories
mkdir -p merged
mkdir -p tv_collector
mkdir -p scripts

# 检查是否已有模块文件
if [ -f "collect_sources.py" ]; then
    echo "📝 复制原始脚本..."
    cp collect_sources.py scripts/run_simple_collect.py
    chmod +x scripts/run_simple_collect.py
fi

# 创建必要的配置文件
echo "📝 创建配置文件..."

# sources.txt
if [ ! -f "sources.txt" ]; then
    cat > sources.txt << 'EOF'
# 电视直播源列表
# 每行一个M3U文件URL
# 请添加可用的直播源地址

# 示例直播源：
https://raw.githubusercontent.com/iptv-org/iptv/master/index.m3u
https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u

# 更多源可以参考：
# https://github.com/iptv-org/iptv
# https://github.com/imDazui/Tvlist-awesome-m3u-m3u8
EOF
    echo "✅ 创建 sources.txt"
else
    echo "✅ sources.txt 已存在"
fi

# blacklist.txt
if [ ! -f "blacklist.txt" ]; then
    cat > blacklist.txt << 'EOF'
# 直播源黑名单
# 该文件包含响应时间超过6秒的慢速直播源
# 每行一个URL，下次更新时会跳过这些源
# 生成时间: 2024-01-01 00:00:00

# 示例：
# http://example.com/slow-stream.m3u8
EOF
    echo "✅ 创建 blacklist.txt"
else
    echo "✅ blacklist.txt 已存在"
fi

# 检查模块文件
echo "🔍 检查模块文件..."
if [ -d "tv_collector" ] && [ -f "tv_collector/__init__.py" ]; then
    echo "✅ 模块文件已存在"
else
    echo "📝 创建基本模块结构..."
    
    # 创建 __init__.py
    cat > tv_collector/__init__.py << 'EOF'
#!/usr/bin/env python3
"""
电视直播源收集包
"""
__version__ = "7.0.0"
print(f"✅ tv_collector v{__version__} 已加载")
EOF
    
    echo "✅ 创建基本模块结构"
fi

echo ""
echo "🎉 安装完成！"
echo "========================================"
echo ""
echo "📋 使用方法："
echo "1. 编辑 sources.txt 添加直播源URL"
echo "2. 运行收集脚本:"
echo "   - 模块化版本: python scripts/run_collect.py"
echo "   - 简化版本: python scripts/run_simple_collect.py"
echo "   - 原始版本: python collect_sources.py"
echo ""
echo "🔄 GitHub Actions 自动更新："
echo "   - 每天北京时间凌晨2点自动运行"
echo "   - 可手动在仓库的 Actions 页面触发"
echo ""
echo "📁 生成的文件："
echo "   - live_sources.m3u (主播放列表)"
echo "   - channels.json (详细数据)"
echo "   - categories/*.m3u (分类列表)"
echo "   - merged/*.m3u (其他版本)"
echo ""
echo "🔗 访问地址："
echo "   - GitHub: https://github.com/你的用户名/仓库名"
echo "   - 播放列表: https://你的用户名.github.io/仓库名/live_sources.m3u"