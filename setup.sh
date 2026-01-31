#!/bin/bash
echo "📦 设置电视直播源项目..."

# 创建目录
mkdir -p .github/workflows
mkdir -p scripts
mkdir -p categories

echo "✅ 目录结构创建完成"
echo ""
echo "📝 请创建以下文件:"
echo "1. .github/workflows/update-live-sources.yml"
echo "2. scripts/collect_sources.py"
echo "3. sources.txt"
echo ""
echo "然后执行:"
echo "git add ."
echo 'git commit -m "初始提交"'
echo "git push"