# 📺 电视直播源自动收集项目

此项目自动从多个源收集电视直播源，并归类整理为M3U格式。

## 🚀 快速开始

1. **Fork** 此仓库到你的GitHub账户
2. 在仓库设置中添加个人访问令牌 (PAT_TOKEN)
3. 工作流将自动开始收集直播源

## 📁 生成的文件

- `live_sources.m3u` - 完整的直播源文件
- `categories/` - 按分类分开的直播源
- `channels.json` - 频道信息JSON数据
- `index.html` - 网页播放界面

## ⚙️ 配置

编辑 `sources.txt` 文件可以添加更多直播源。

## 📅 自动更新

每天自动更新直播源，也可以通过 GitHub Actions 手动触发。