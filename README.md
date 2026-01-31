# 📺 电视直播源自动收集项目

此项目会自动收集电视直播源，并整理为M3U格式。

## 🚀 快速开始

1. **克隆或Fork此仓库**
2. **等待GitHub Actions自动运行**
3. **下载生成的 `live_sources.m3u` 文件**

## 📁 项目结构
├── .github/workflows/update-live-sources.yml # GitHub Actions工作流
├── scripts/collect_sources.py # 采集脚本
├── sources.txt # 源列表
├── live_sources.m3u # 自动生成：完整直播源
├── channels.json # 自动生成：频道数据
├── index.html # 自动生成：网页界面
└── categories/ # 自动生成：分类直播源
## ⚙️ 配置

编辑 `sources.txt` 文件可以添加更多直播源URL。

## 📅 更新频率

每天自动更新一次。

---

*此README将在首次运行后被更新*