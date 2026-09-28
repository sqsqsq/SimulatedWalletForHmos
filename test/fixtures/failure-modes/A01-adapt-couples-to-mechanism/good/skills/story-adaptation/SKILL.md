---
name: story-adaptation
description: 适配指南（正夹具：只认类别边界）
---

# 适配

升级时把机制类目录（`hooks/`、`rules/`）整体换成包的版本；知识类按 frontmatter 的 `kind`
搬到对应目录，正文一字不动；清单按目标目录里实际存在的文件重算。
