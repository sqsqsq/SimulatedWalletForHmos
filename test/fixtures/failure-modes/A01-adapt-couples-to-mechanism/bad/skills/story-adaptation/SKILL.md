---
name: story-adaptation
description: 适配指南（反夹具：写死了扩展内部结构）
---

# 适配

升级时把 `hooks/alpha/post_check.mjs` 换成包的版本，再检查 `sample-domain` 有没有搬到新目录，
最后确认 `sample-pattern` 仍在清单里。
