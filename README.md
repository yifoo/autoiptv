# 📺 电视直播源自动收集项目

此项目会自动从多个源收集电视直播频道，并整理归类。

## 🚀 快速部署

1. **Fork** 此仓库
2. **添加 Secret**: 在仓库 Settings → Secrets and variables → Actions 中添加：
   - 名称: `LIVEIPTV`
   - 值: 你的GitHub个人访问令牌(PAT)
3. **运行工作流**: 在 Actions 页面手动触发

## 📁 生成的文件

工作流运行后会生成:
- `live_sources.m3u` - 完整的直播源文件
- `channels.json` - 频道数据(JSON格式)
- `index.html` - 网页播放界面
- `categories/` - 分类播放列表
- `README.md` - 项目文档(自动更新)

## ⚙️ 自定义配置

编辑 `sources.txt` 文件可以添加更多直播源URL。

## 📅 自动更新

每天自动运行一次，保持直播源更新。

---

*项目初始化模板 - 首次运行后会更新此文档*