# Extension 全部内容的功能与必要性判定（分析稿）

> 快照基线 `d36edb70f04c60128c2e07501c7eff5fa299c07f`（2026-09-11 功能全集与机制归属轮）；77份文件，2327个连续区间。由原2269区间在具体退出边界上细分；区间数增加不是功能或代码增加。基线轮 Extension 零改动。**区间行号与 SHA 只对该快照有效**，不随实现更新。
> 2026-09-20 由 `plan/1.9.1/2026-09-11-Extension功能全集与机制归属/` 迁入本目录 `归属存档/`（1.9.1 遗留 L14 落地）。基线之后的实现变化见下节「2026-09-20 漂移记录」；当前实现全盘分析见[00-全盘分析报告](../00-全盘分析报告.md)。
> 行内 M/H/T 等编号是纯文本引用，定义真源在 [01-归属判定与整体审查](../../../../plan/1.9.1/2026-09-11-Extension功能全集与机制归属/01-归属判定与整体审查.md)。本文件冻结为 09-11 轮诊断存档：不再逐行随实现同步，漂移只记「2026-09-20 漂移记录」节；长期维护清单只有 FEATURES 一份，本文件与 FEATURE-MAP 同为诊断存档。

每个区间的功能归属与同功能实现比较同时列出。**M不是泛化功能标签**：点击可看被放在一起比较的实现、为何保留/替换、接替者和不能丢的效果。R/D覆盖局部时以其准确动作优先，不能把整行范围机械删除。注释/常量/导入归所属职责，失效说明另列R18。

| 文件 | 行数 | 原字节SHA-256 |
|---|---:|---|
| [hooks/coding/author.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/coding/author.md:1) | 49 | `7e74f18863fabcccbf8624a8e420b63668b89e99517727d675e69e4ba10c7649` |
| [hooks/coding/post_check.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/coding/post_check.mjs:1) | 157 | `c40adca3afbb8186090d0fa4c24f70c955d6083a82e0846281a1dc9726f41015` |
| [hooks/plan/author.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/plan/author.md:1) | 47 | `053a0206efe0d8ef814c9fd7fb319c7e04aaedcf7fd25a2dc091c421fbc320a8` |
| [hooks/plan/post_check.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/plan/post_check.mjs:1) | 327 | `9a0b3543ccaff679149a0438a7512cf4872e736298fbebed971675e8c3cc756c` |
| [hooks/review/author.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/review/author.md:1) | 45 | `9cc2e864dd3027163fc6e440f58cdc6c0520492fad6856eee757ff13174738c7` |
| [hooks/review/post_check.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/review/post_check.mjs:1) | 124 | `3a97c32771e162a1bcefe4dd8e88c73ca79cd64b0b6a604184a088b0c0a0ba21` |
| [hooks/shared/contracts.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/contracts.mjs:1) | 186 | `bb3f34172ff216d9f1af36faeaeba3e24746ce6c70677cfd0ba6cee4609db302` |
| [hooks/shared/evidence.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/evidence.mjs:1) | 67 | `ae3a4ffc49f2badede39270fd31e3ce4de70a14f63d6ff77eccd3863f4c13cd5` |
| [hooks/shared/gate.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/gate.mjs:1) | 108 | `1023841f9074ea606808df14d2e081617db85aa6f173c112507cb4a4563bb95b` |
| [hooks/shared/knowledge-use.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/knowledge-use.mjs:1) | 664 | `d879e0228593f8c9f8822d26bc9c001de611a14fd8392cf02d0607f82e39d7bd` |
| [hooks/shared/knowledge.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/knowledge.mjs:1) | 427 | `3ea8785b435a6a2f5fe497d6943036db962c7be564e0c23d8932c0e7499bbbd8` |
| [hooks/shared/obligations.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/obligations.mjs:1) | 117 | `1450d7d6b32802a8015a9746b5bc0e4c8fdef21b5809bb498bf8427d2f44a354` |
| [hooks/shared/paths.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/paths.mjs:1) | 64 | `6d6738c3cc527e039d87f5302cea7c79f5a19db730a09359fa250702ec358453` |
| [hooks/shared/pre_verifier.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/pre_verifier.mjs:1) | 128 | `2a8b8af011fafc837fef738768341b8ab9071c7278ca41cb7912b3f51248cf84` |
| [hooks/shared/probes.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/probes.mjs:1) | 198 | `b9b9f378db931b8732ffc6e3d16381f4479cf2698830752735c9b16a2f699345` |
| [hooks/shared/reader-review-task.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/reader-review-task.mjs:1) | 236 | `ef861260e9ad85af7bfa30b802fd79e6c76d0ecea67370e93cbdabc48edd64d4` |
| [hooks/shared/verifier-report.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/verifier-report.mjs:1) | 242 | `381a164cc0de3c58b1bf10c86b8ec1b33581bc8bf5d42ce40a2c8da581c1f270` |
| [hooks/shared/yaml-lite.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/shared/yaml-lite.mjs:1) | 215 | `bcd350304dd00501dcebca5ccf34f1ddd26498621aa0152f8e05f48a62057a5e` |
| [hooks/spec/author.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/spec/author.md:1) | 60 | `3e166274e3f9ae7eaebaa9bcba5a2e4791d6e49c68a58c1317c77d951a575467` |
| [hooks/spec/author.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/spec/author.mjs:1) | 350 | `d95ae9bc78660c04a2bf5456ff81fd1586f4783e082aae659405f2a8ddd0ad6d` |
| [hooks/spec/post_check.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/spec/post_check.mjs:1) | 519 | `1a7713cf96fd92c5c141552472b0383c1f1b5afae8bbd27299b4fe6fb0c3e2ae` |
| [hooks/testing/author.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/testing/author.md:1) | 43 | `b82fc96eea6e24c3baad86ad88584f7694f5baaec36471fb0f9ad7487c8a2569` |
| [hooks/testing/post_check.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/testing/post_check.mjs:1) | 107 | `aa53e1c27f75b1a04d0f9d1d1aeb9e06b03ee3fa6a70610be4e3174bb1d480f7` |
| [hooks/ut/author.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/ut/author.md:1) | 43 | `f7b51723539f56865933c5572e4ded550ad162a12a171e60371c494d75775190` |
| [hooks/ut/post_check.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/hooks/ut/post_check.mjs:1) | 104 | `7087698fc48a61346d67a73618df28654ba74086b71676bee03ec147dd239bc5` |
| [knowledge/constraints/compatibility-checklist.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/compatibility-checklist.md:1) | 24 | `ca6aa0f212e4acbd750f13865364e54ccb64ab2930aee5f1276d287c08a8e4ce` |
| [knowledge/constraints/deliverables.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/deliverables.md:1) | 27 | `81eb191f97d116d0142deeb6a05894a87776f58da95e96a47c839cdc840271a2` |
| [knowledge/constraints/dfx-baseline.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/dfx-baseline.md:1) | 33 | `c670b6cdd45fbcf542ff0670aaece82f9e4c482580959c71bdd2426321af3fa5` |
| [knowledge/constraints/env-exceptions.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/env-exceptions.md:1) | 26 | `627fb425b467b6c52f07e4efdfbbfd13dff27866bf5a8c67fa65bcc0b2bda8da` |
| [knowledge/constraints/observability.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/observability.md:1) | 24 | `ec81ad9eac66f57324ac25ea241ce6482f133c2e5ed628ba79e02ca2dc5c14b4` |
| [knowledge/constraints/README.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/README.md:1) | 37 | `999a90c42c987049b3c80219b7939d03e5dac49a5056281741dc8ad3bce3a4c4` |
| [knowledge/constraints/resource-usage.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/resource-usage.md:1) | 25 | `9c38696a040c330f575b4bf1c45ee9c2563cbc2054182c6d265f7edb2dfdb9d9` |
| [knowledge/constraints/security-privacy.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/security-privacy.md:1) | 30 | `7bb47d0957257931bc47a26ecff2fe4a35af1b724767c4e56bc04dee25375aec` |
| [knowledge/constraints/ux-consistency.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/constraints/ux-consistency.md:1) | 26 | `d7b7e4e3fb6a2fb1f380e5530e688b68d359f61d97b08ba9395386061ee047d5` |
| [knowledge/design-patterns/decision-tree.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/design-patterns/decision-tree.md:1) | 178 | `9360521e22f99f9280b96d927798cac3cb92159ba3900f0864d2c062a9c6479f` |
| [knowledge/design-patterns/page-interaction.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/design-patterns/page-interaction.md:1) | 160 | `b491f53098fc754d18b1648cdc66785769c9b430c978fd5d2f97fc568d9d5308` |
| [knowledge/design-patterns/README.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/design-patterns/README.md:1) | 65 | `d185e8fabed98792053e1fff92a8e16eee88d9993e1e63f9419fef55acb5cba6` |
| [knowledge/facts/codebase-facts.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/facts/codebase-facts.md:1) | 68 | `7f3b9b6004c4e5b8d56359e74375c6e2fa917da2e12bb22e69034fda79ce14f1` |
| [knowledge/facts/component-profile.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/facts/component-profile.md:1) | 35 | `594261cc266f6b8b603451f90073cd8aa41c6d06250ea4c83cbd5dbae52b10b1` |
| [knowledge/facts/README.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/facts/README.md:1) | 20 | `6e7bad4796b455a78386e852bb453b59a55b720aa499aecfdb08ab1d2f4a4086` |
| [knowledge/README.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/knowledge/README.md:1) | 14 | `7ce8a86969579b27210c57ede56a091afb7e6edc5f7a24746df073d8e8b638bb` |
| [manifest.yaml:1](E:/Project/SimulatedWalletForHmos/doc/extensions/manifest.yaml:1) | 101 | `e1c2b448c9832faf098285adb305ba731c792352f9a80956b7b546d75d39ae9a` |
| [rules/coding-rules.overlay.yaml:1](E:/Project/SimulatedWalletForHmos/doc/extensions/rules/coding-rules.overlay.yaml:1) | 38 | `e2fa1cbeb0a83bbe0d7551fc0525b6079460caca7c1b968c6e9c071023f5dca3` |
| [rules/plan-rules.overlay.yaml:1](E:/Project/SimulatedWalletForHmos/doc/extensions/rules/plan-rules.overlay.yaml:1) | 65 | `826a5258650c152ebfadc209655a052b6521b62041d561f8f2d2964054f6ccd2` |
| [rules/review-rules.overlay.yaml:1](E:/Project/SimulatedWalletForHmos/doc/extensions/rules/review-rules.overlay.yaml:1) | 33 | `69db93e52f0e6316dd4a880f553c97d11dc3c85e2e85af4f202d601b8b37982e` |
| [rules/spec-rules.overlay.yaml:1](E:/Project/SimulatedWalletForHmos/doc/extensions/rules/spec-rules.overlay.yaml:1) | 162 | `40ac74ae807cc4e562dba0f99036f15b978cd1da33ddd7b3723c85561abd1dfa` |
| [rules/testing-rules.overlay.yaml:1](E:/Project/SimulatedWalletForHmos/doc/extensions/rules/testing-rules.overlay.yaml:1) | 22 | `75544037f58fb4917917c781fa50f97003195985068c81f3043953eae9a077c5` |
| [rules/ut-rules.overlay.yaml:1](E:/Project/SimulatedWalletForHmos/doc/extensions/rules/ut-rules.overlay.yaml:1) | 34 | `04388dda9a50f6e771ffbb23b845e8957360df643f59cda72355c0dda0e5d4a8` |
| [skills/story/AGENTS.section.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/AGENTS.section.md:1) | 7 | `51c95e68a1a84eeca509b568e42dfbd3a0ea4624581301bf0bd270bb2f3fe57d` |
| [skills/story/contracts/story-chapters.json:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/contracts/story-chapters.json:1) | 416 | `5311cdec447df0a6e19f2487ca5a8d0afbe855712425007f09b4acb4b02b0a9c` |
| [skills/story/phases/spec.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/phases/spec.md:1) | 142 | `e89f892c9703ebf859a0ddaeb502ab91f5b6080d48fd268000d82cd61265e7b3` |
| [skills/story/phases/story-write.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/phases/story-write.md:1) | 475 | `640f230878a2852d83a462b4d2f568fd3cc3a3d2a752777d338c0d07d8782a1a` |
| [skills/story/reference/evidence-rules.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/reference/evidence-rules.md:1) | 106 | `a394c811009aa2443f724a46f1155a433146cfdb5981e851339c82eb21649cb3` |
| [skills/story/rules/ar_design_init.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/rules/ar_design_init.md:1) | 143 | `d9913b869e6fea27ff0e7584d8e4ab99a9b37d8b41cd19b4702dc03627f0bc5e` |
| [skills/story/rules/inbox_import.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/rules/inbox_import.md:1) | 95 | `36cbe082a38e1b42002cea2ce0f8bed1e0914f3b5588de8038f33fe784d93d43` |
| [skills/story/rules/init_analysis.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/rules/init_analysis.md:1) | 234 | `e131f91ad9ef9c8964f66c7da45da7bb48dd421c2543babcc625e2531f837a06` |
| [skills/story/rules/review_reflow.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/rules/review_reflow.md:1) | 99 | `350722d1b59ed7ccb20d6c1a6fe9aeb4d4eb3c3718a343d9c91b56feace5bd06` |
| [skills/story/rules/scope_gate.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/rules/scope_gate.md:1) | 196 | `77d6203db7fd76280a55263233b962dfcb4113550aa744c8acabc5eeece1c8f2` |
| [skills/story/scripts/adapters/review.js:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/adapters/review.js:1) | 69 | `dce714a789e10e6f9f8dcd8c9f7425254be408cadb8f632277d5075c9f2fd3fa` |
| [skills/story/scripts/adapters/story.js:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/adapters/story.js:1) | 359 | `f638cb1314adf21fa8ac0827ef0e918d8f0d1dde82bb3c9a25712bb9b6bffce8` |
| [skills/story/scripts/adapters/token.js:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/adapters/token.js:1) | 18 | `ea3eeb921ba534d6c86d11a5f41d4ea0085d9045b5fba519ebed5a1d4b89401a` |
| [skills/story/scripts/core/flow-check.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/flow-check.mjs:1) | 395 | `4271a75951576adf769eea3fbdf6dd4b465e194acd6170e9100cf9705191be28` |
| [skills/story/scripts/core/headings.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/headings.mjs:1) | 140 | `7a954f0ac2fcf675b19a9c650242a612714d29df2b20f9b2f24885550723ebcd` |
| [skills/story/scripts/core/import_sources.py:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/import_sources.py:1) | 682 | `96f8c2b1501aaa0ec74fa19ed5cabc41ae7e4fb07eb92e93b1d9ffa4b759f050` |
| [skills/story/scripts/core/lint-rules.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/lint-rules.mjs:1) | 553 | `b59daa160d230a79cfcb197666a27bcdbdc255068e194ab94d40740ff7ce4df4` |
| [skills/story/scripts/core/materials.py:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/materials.py:1) | 337 | `737b8d13b0d2f0beaa27b9a68790fec9fe03829af2ce6b36074e891cea46a8e9` |
| [skills/story/scripts/core/review-render.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/review-render.mjs:1) | 303 | `b31c85647602ce4f0eae2dee609eb5d9a21ac33db15f1a5fa9b62ab2196db731` |
| [skills/story/scripts/core/story-build.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/story-build.mjs:1) | 3745 | `dbe7295e351d10d467a7160ad0d72a27131655b5daf3937aede16b6369a8489c` |
| [skills/story/scripts/core/story-sources.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/story-sources.mjs:1) | 761 | `ab8e5cc31c138d44089a9d9abd4b7837479f4454b4ce0a9e4dbcace5ce5bb7be` |
| [skills/story/scripts/core/story_flow.py:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/core/story_flow.py:1) | 1679 | `234beb41c4f1c7412bbbcf04e17a8faba48699b5112595baeae1373bf38a2860` |
| [skills/story/scripts/README.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/scripts/README.md:1) | 29 | `04511d3bd226cfc3c0bacf16b381efa65bbcb1ab72a2659e0838d0a987c9489b` |
| [skills/story/SKILL.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/SKILL.md:1) | 285 | `607647f3b8d9ff118f1ba1b7240bee2ce3318d43e21d7a72655177d02d736a3e` |
| [skills/story/templates/inbox-readme.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/templates/inbox-readme.md:1) | 28 | `ec2621d3b472c52a34ca6a71bee47bb68f97ccb7437bac52698ffb8de2c13ade` |
| [skills/story/templates/plan-sections.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/templates/plan-sections.md:1) | 136 | `c41c37ab3bc9057e7839ea24af68f9ec5cb02151e12e659ba345fe71480850b9` |
| [skills/story/templates/spec-sections.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story/templates/spec-sections.md:1) | 178 | `ee7283759d78a0bcc82cc6cc4eb6f744523d638f3cc7bc9e57d8ad642909e43e` |
| [skills/story-adaptation/scripts/adapt-scan.mjs:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story-adaptation/scripts/adapt-scan.mjs:1) | 676 | `b6da38a7e4c5c4053c6ce66e599aaafe0f4253a0ca7562438c1bb8b44d9e5074` |
| [skills/story-adaptation/SKILL.md:1](E:/Project/SimulatedWalletForHmos/doc/extensions/skills/story-adaptation/SKILL.md:1) | 107 | `f49634410706185d15aab2e3793f4fa424f4f8a6ae0e2e90993ffe937226b826` |

## 2026-09-20 漂移记录（基线 d36edb70 → HEAD `1af7fdf7`＋工作区）

对比 `doc/extensions` 全部文件（排除 `__pycache__`），物理行数与 SHA-256：未变 9、内容变化 61、已删除 7、新增 35。上表与各文件区间表保持快照原样，不随实现更新。

已删除与现职责承担者（删除发生在 2026-09-12 功能目录归位与 1.9.3 机制级替换）：

| 基线文件 | 基线行数 | 现职责承担者 |
|---|---:|---|
| hooks/shared/yaml-lite.mjs | 215 | hooks/shared/yaml.mjs（借 framework yaml 包，1.9.3 R1） |
| skills/story/scripts/core/flow-check.mjs | 395 | skills/story/scripts/core/flow/check.mjs |
| skills/story/scripts/core/headings.mjs | 140 | skills/story/scripts/core/story/document.mjs（R4 单点解析） |
| skills/story/scripts/core/lint-rules.mjs | 553 | skills/story/scripts/core/story/language.mjs ＋ 合同 language_redline（R6） |
| skills/story/scripts/core/materials.py | 337 | skills/story/scripts/core/materials/registry.py |
| skills/story/scripts/core/review-render.mjs | 303 | skills/story/scripts/core/story/review.mjs |
| skills/story/scripts/core/story-sources.mjs | 761 | skills/story/scripts/core/story/sources.mjs |

新增 35 份：core/flow/ 拆分 9 件、core/materials/ 拆分 3 件、core/story/ 拆分 15 件、hooks/shared/knowledge-use/ 拆分 3 件，另有 hooks/shared/yaml.mjs、skills/story/contracts/README.md、skills/story/phases/meeting-read.md。

内容变化 61 份中行数变化 ≥20 的（基线→当前，物理行）：

| 文件 | 基线→当前 | 文件 | 基线→当前 |
|---|---|---|---|
| core/story-build.mjs | 3745→247 | core/story_flow.py | 1679→141 |
| core/import_sources.py | 682→133 | hooks/shared/knowledge-use.mjs | 664→104 |
| skills/story/phases/story-write.md | 475→304 | skills/story/SKILL.md | 285→184 |
| skills/story/contracts/story-chapters.json | 416→339 | skills/story/templates/spec-sections.md | 178→78 |
| skills/story/templates/plan-sections.md | 136→91 | rules/spec-rules.overlay.yaml | 162→217 |
| hooks/shared/contracts.mjs | 186→274 | hooks/shared/pre_verifier.mjs | 128→205 |
| hooks/shared/knowledge.mjs | 427→535 | hooks/spec/author.mjs | 350→396 |
| hooks/shared/reader-review-task.mjs | 236→277 | hooks/shared/obligations.mjs | 117→150 |
| skills/story/rules/init_analysis.md | 234→256 | 其余 44 份 | 行数变化 <20 |

完整 61 份对照清单见 `证据/`[漂移对照-2026-09-20.txt](../证据/漂移对照-2026-09-20.txt)。

knowledge/design-patterns/decision-tree.md 与 page-interaction.md 的 §9 反模式于 2026-09-20 改写（现文 :172–176 / :155–159，工作区未提交）：区间行 P7f2b4ecd-174、P58a4ee39-157 的摘录已同步更新；§9 均为两文件末节，其余区间行号不受影响。

<a id="Pb9ae9229"></a>

## hooks/coding/author.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pb9ae9229-1 | 1–2 | coding 阶段 · 扩展要求（写之前读这一页） | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-3 | 3–4 | coding 阶段 · 扩展要求（写之前读这一页） / &gt; **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-5 | 5–9 | coding 阶段 · 扩展要求（写之前读这一页） / **契约实体上的 &#96;must&#96; 就是本阶段的知识来源**：plan 已经把每条规约义务挂到了扛着它的那个 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-10 | 10–11 | 一、读哪几个文件 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-12 | 12–16 | 一、读哪几个文件 / &#124; 文件 &#124; 拿什么 &#124; | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-17 | 17–18 | 一、读哪几个文件 / 规约文件本身不必读——&#96;must.text&#96; 已经带着本需求的专名了。 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-19 | 19–20 | 二、产出形态 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-21 | 21–24 | 二、产出形态 / 产出就是代码本身。任务是**让挂着 &#96;must&#96; 的那个实体在代码里真实存在并承担那件事**： | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-25 | 25–27 | 二、产出形态 / 标了 &#96;files&#91;&#93;.pattern&#96; 的文件，按该模式文档的**实现篇**落结构——角色类建出来还要**被调用**。 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-28 | 28–30 | 二、产出形态 / 每条义务在本阶段都要有个说法：**真实证据**（它落在哪）或**显式不适用 + 理由**。 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-31 | 31–32 | 三、跑哪条命令 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-33 | 33–36 | 三、跑哪条命令 / 示例或代码块 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-37 | 37–38 | 四、门禁会拦什么 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-39 | 39–45 | 四、门禁会拦什么 / - &#96;must&#96; 挂着的实体在代码里找不到（文件建了，但里面没有那个类 / 字段 / 枚举）。 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-46 | 46–48 | 四、门禁会拦什么 / 探针扫描 0 个文件时会告警「形态可能不匹配本工程」，那说明探针或落点有一个写错了， | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pb9ae9229-49 | 49–49 | 四、门禁会拦什么 / **只在注释或文档里写「已按要求处理」而代码里看不出的，等于没做**——本阶段的证据是代码本身。 | F4.6, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |

<a id="P5e70c0fd"></a>

## hooks/coding/post_check.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P5e70c0fd-1 | 1–16 | 文件头/元信息 | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-17 | 17–17 | import * as fs from 'node:fs'; | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-18 | 18–18 | import * as path from 'node:path'; | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-19 | 19–19 | import { STATUS } from '../shared/evidence.mjs'; | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-20 | 20–20 | import { contractFiles, readContracts, resolveEntityRef } from '../shared/contracts.m | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-21 | 21–21 | import { guard, gate } from '../shared/gate.mjs'; | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-22 | 22–22 | import { activeKnowledge, entryById } from '../shared/knowledge.mjs'; | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-23 | 23–23 | import { obligationsFromContracts, patternRolesFromContracts } from '../shared/obliga | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-24 | 24–25 | import { filesForEntity, runProbe } from '../shared/probes.mjs'; | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-26 | 26–26 | AUTHOR_DOC | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-27 | 27–30 | FIX | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P5e70c0fd-31 | 31–37 | tailIdentifier | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P5e70c0fd-38 | 38–51 | findIdentifier | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P5e70c0fd-52 | 52–157 | export default guard('coding', async (ctx) =&gt; { | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |

<a id="Pa01400a4"></a>

## hooks/plan/author.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pa01400a4-1 | 1–2 | plan 阶段 · 扩展要求（写之前读这一页） | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-3 | 3–4 | plan 阶段 · 扩展要求（写之前读这一页） / &gt; **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-5 | 5–7 | plan 阶段 · 扩展要求（写之前读这一页） / 本阶段是设计模式**唯一的选型点**，也是规约义务**唯一的落点**：coding / review / ut / testing | F4.5, F5.1 | M27, M30 | 按R23处理局部；不整块删 |
| Pa01400a4-8 | 8–9 | 一、读哪几个文件 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-10 | 10–15 | 一、读哪几个文件 / &#124; 文件 &#124; 拿什么 &#124; | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-16 | 16–17 | 二、产出形态 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-18 | 18–19 | 二、产出形态 / **① &#96;plan.md&#96; 里必须有一章「知识决策（设计输入）」，且排在第一个设计章之前。** | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-20 | 20–21 | 二、产出形态 / 位置就是语义：排在设计之前，后面每一章才可能按它展开（数据模型因此多一个字段、接口因此多一个方法）；排在设计之后就只是事后声明。 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-22 | 22–24 | 二、产出形态 / **② 每条命中的规约，在 &#96;contracts.yaml&#96; 里挂一条 &#96;must&#96; 到扛着它的那个实体上；** | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-25 | 25–28 | 二、产出形态 / 挂在哪五处、&#96;text&#96; / &#96;rule&#96; / &#96;verify&#96; 三个字段各写什么、&#96;verify&#96; 的五个取值分别把这条义务 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-29 | 29–30 | 二、产出形态 / **判据一句话：义务要挂在下游真的会读的那个实体上**——挂在别处就是又造了一本没人读的账本。 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-31 | 31–32 | 三、跑哪条命令 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-33 | 33–36 | 三、跑哪条命令 / 示例或代码块 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-37 | 37–38 | 四、门禁会拦什么 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-39 | 39–46 | 四、门禁会拦什么 / - 缺「知识决策（设计输入）」章，或它排在第一个设计章之后。 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |
| Pa01400a4-47 | 47–47 | 四、门禁会拦什么 / spec 全部单元都写「无候选」时，本阶段不应凭空选出一个模式——那说明选型依据不是从需求来的。 | F4.5, F5.1 | M27, M30 | 按M27,M30比较结论保留其必要职责 |

<a id="P4cf2f673"></a>

## hooks/plan/post_check.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P4cf2f673-1 | 1–21 | 文件头/元信息 | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-22 | 22–22 | import * as path from 'node:path'; | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-23 | 23–23 | import { STATUS } from '../shared/evidence.mjs'; | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-24 | 24–24 | import { guard, gate } from '../shared/gate.mjs'; | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-25 | 25–25 | import { activeKnowledge, entryById } from '../shared/knowledge.mjs'; | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-26 | 26–27 | import { obligationsFromContracts, misplacedMust, patternRolesFromContracts, VERIFY_K | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-28 | 28–28 | import { readUse, UseError } from '../shared/knowledge-use.mjs'; | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-29 | 29–29 | import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs'; | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-30 | 30–31 | import { contractsPath, readContracts } from '../shared/contracts.mjs'; | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-32 | 32–32 | SECTIONS_DOC | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-33 | 33–47 | FIX | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-48 | 48–48 | DESIGN_HEADING_RE | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-49 | 49–50 | DECISION_HEADING_RE | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-51 | 51–70 | findHeadings | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-71 | 71–94 | specHitIds | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-95 | 95–115 | tableRows | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-116 | 116–127 | chapterAt | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| P4cf2f673-128 | 128–151 | specPatternHits | F4.4, F4.5 | M26 | 保留功能，修D03 |
| P4cf2f673-152 | 152–164 | planPatternChoices | F4.4, F4.5 | M26 | 保留功能，修D03 |
| P4cf2f673-165 | 165–327 | export default guard('plan', async (ctx) =&gt; { | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |

<a id="P5e948c22"></a>

## hooks/review/author.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P5e948c22-1 | 1–2 | review 阶段 · 扩展要求（写之前读这一页） | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-3 | 3–4 | review 阶段 · 扩展要求（写之前读这一页） / &gt; **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-5 | 5–8 | review 阶段 · 扩展要求（写之前读这一页） / **契约实体上的 &#96;must&#96; 就是本阶段的知识来源**：plan 已经把每条规约义务挂到了扛着它的 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-9 | 9–10 | 一、读哪几个文件 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-11 | 11–15 | 一、读哪几个文件 / &#124; 文件 &#124; 拿什么 &#124; | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-16 | 16–17 | 二、产出形态 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-18 | 18–19 | 二、产出形态 / 审查报告里须有一节 **&#96;## 知识义务复核&#96;**，契约里的每条 &#96;must&#96; 一行： | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-20 | 20–25 | 二、产出形态 / 示例或代码块 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-26 | 26–28 | 二、产出形态 / 契约里标了 &#96;pattern&#96; 的模式也要有行：核实现是否按该模式的结构落——角色是否各就各位、 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-29 | 29–31 | 二、产出形态 / 每条义务二选一：**真实证据**（落在哪）或**显式不适用 + 理由**。不能什么都不写—— | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-32 | 32–33 | 三、跑哪条命令 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-34 | 34–37 | 三、跑哪条命令 / 示例或代码块 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-38 | 38–39 | 四、门禁会拦什么 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-40 | 40–43 | 四、门禁会拦什么 / - 缺 &#96;## 知识义务复核&#96; 节，或表的行集与契约里的 &#96;must&#96; 集对不上。 | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |
| P5e948c22-44 | 44–45 | 四、门禁会拦什么 / **上游阶段声明过、本次变更里却找不到落点的，正是本阶段该抓的。** | F4.7, F5.1 | M28, M30 | 按M28,M30比较结论保留其必要职责 |

<a id="P2cb62240"></a>

## hooks/review/post_check.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P2cb62240-1 | 1–12 | 文件头/元信息 | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-13 | 13–13 | import * as path from 'node:path'; | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-14 | 14–14 | import { featureRoot, lines, readTextOrNull } from '../shared/paths.mjs'; | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-15 | 15–15 | import { readContracts } from '../shared/contracts.mjs'; | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-16 | 16–16 | import { obligationsFromContracts, patternRolesFromContracts } from '../shared/obliga | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-17 | 17–18 | import { guard, gate } from '../shared/gate.mjs'; | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-19 | 19–19 | SECTION_TITLE | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-20 | 20–22 | VERDICTS | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-23 | 23–28 | cellOf | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-29 | 29–48 | reviewTable | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P2cb62240-49 | 49–124 | export default guard('review', async (ctx) =&gt; { | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |

<a id="P583825d8"></a>

## hooks/shared/contracts.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P583825d8-1 | 1–6 | 文件头/元信息 | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-7 | 7–7 | import * as path from 'node:path'; | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-8 | 8–8 | import { featureRoot, readTextOrNull } from './paths.mjs'; | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-9 | 9–14 | import { parseYaml } from './yaml-lite.mjs'; | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-15 | 15–31 | ENTITY_KINDS | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-32 | 32–40 | contractsPath | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-41 | 41–52 | readContracts | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| P583825d8-53 | 53–59 | asArray | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-60 | 60–66 | entityName | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-67 | 67–84 | memberNames | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| P583825d8-85 | 85–138 | resolveEntityRef | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| P583825d8-139 | 139–154 | contractFiles | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P583825d8-155 | 155–164 | readAcceptance | F4.8, F4.9, F4.3 | M29 | 按R19处理局部；不整块删 |
| P583825d8-165 | 165–174 | readAcceptance | F4.8, F4.9, F4.3 | M29 | 按M29比较结论保留其必要职责 |
| P583825d8-175 | 175–185 | knowledgeCriteria | F4.8, F4.9, F4.3 | M29 | 按R19处理局部；不整块删 |
| P583825d8-186 | 186–186 | knowledgeCriteria | F4.8, F4.9, F4.3 | M29 | 保留功能，修D01 |

<a id="Pbfd0b8c5"></a>

## hooks/shared/evidence.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pbfd0b8c5-1 | 1–10 | 文件头/元信息 | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-11 | 11–11 | import * as crypto from 'node:crypto'; | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-12 | 12–12 | import * as fs from 'node:fs'; | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-13 | 13–13 | import * as path from 'node:path'; | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-14 | 14–16 | import { featureRoot, readTextOrNull, relDisplay } from './paths.mjs'; | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-17 | 17–19 | EVIDENCE_FILE | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-20 | 20–25 | STATUS | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-26 | 26–39 | sha256 | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| Pbfd0b8c5-40 | 40–67 | writePostCheckEvidence | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |

<a id="P2db84dee"></a>

## hooks/shared/gate.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P2db84dee-1 | 1–21 | 文件头/元信息 | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| P2db84dee-22 | 22–24 | import { STATUS, writePostCheckEvidence } from './evidence.mjs'; | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| P2db84dee-25 | 25–34 | authorDoc | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| P2db84dee-35 | 35–69 | guard | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |
| P2db84dee-70 | 70–108 | gate | F5.3, F5.7 | M32, M34 | 按M32,M34比较结论保留其必要职责 |

<a id="P9aa3042d"></a>

## hooks/shared/knowledge-use.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P9aa3042d-1 | 1–28 | 文件头/元信息 | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-29 | 29–29 | import * as fs from 'node:fs'; | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-30 | 30–30 | import * as path from 'node:path'; | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-31 | 31–31 | import { createHash } from 'node:crypto'; | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-32 | 32–32 | import { fileURLToPath } from 'node:url'; | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-33 | 33–33 | import { parseYaml } from './yaml-lite.mjs'; | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-34 | 34–34 | import { activeKnowledge, knowledgeFiles } from './knowledge.mjs'; | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-35 | 35–36 | import { featureRoot, readTextOrNull, relDisplay } from './paths.mjs'; | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-37 | 37–37 | SCHEMA | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-38 | 38–40 | USE_FILE | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-41 | 41–41 | BEGIN | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-42 | 42–44 | END | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-45 | 45–49 | ZONES | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-50 | 50–51 | NO_CANDIDATE | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-52 | 52–53 | UseError | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-54 | 54–57 | fail | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-58 | 58–67 | usePath | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-68 | 68–79 | manifestDigest | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| P9aa3042d-80 | 80–85 | asList | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-86 | 86–95 | text | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-96 | 96–117 | isEmptyReason | F4.3, F4.4 | M24 | 按M24比较结论保留其必要职责 |
| P9aa3042d-118 | 118–139 | contractNames | F4.3, F4.4 | M24 | 按M24比较结论保留其必要职责 |
| P9aa3042d-140 | 140–172 | readUse | F4.3, F4.4 | M24 | 按M24比较结论保留其必要职责 |
| P9aa3042d-173 | 173–338 | coverageProblems | F4.3 | M24 | 保留功能，修D02 |
| P9aa3042d-339 | 339–343 | cell | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-344 | 344–395 | renderConstraints | F4.3 | M25 | 按M25比较结论保留其必要职责 |
| P9aa3042d-396 | 396–403 | requirements | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-404 | 404–413 | renderPatterns | F4.4, F4.5 | M25 | 按M25比较结论保留其必要职责 |
| P9aa3042d-414 | 414–420 | renderZones | F4.3, F4.4, F2.2 | M25 | 按M25比较结论保留其必要职责 |
| P9aa3042d-421 | 421–430 | zoneBlock | F4.3, F4.4, F2.2 | M25 | 按M25比较结论保留其必要职责 |
| P9aa3042d-431 | 431–450 | zoneOf | F4.3, F4.4, F2.2 | M25 | 按M25比较结论保留其必要职责 |
| P9aa3042d-451 | 451–483 | applyZones | F4.3, F4.4, F2.2 | M25 | 按M25比较结论保留其必要职责 |
| P9aa3042d-484 | 484–500 | chapterSpan | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P9aa3042d-501 | 501–543 | zoneProblems | F4.3, F4.4, F2.2 | M25 | 按M25比较结论保留其必要职责 |
| P9aa3042d-544 | 544–599 | renderSkeleton | F4.3, F4.4 | M26 | 按M26比较结论保留其必要职责 |
| P9aa3042d-600 | 600–612 | cmdInit | F4.3, F4.4 | M24 | 按M24比较结论保留其必要职责 |
| P9aa3042d-613 | 613–621 | parseArgs | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-622 | 622–661 | main | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |
| P9aa3042d-662 | 662–664 | if (process.argv&#91;1&#93; &amp;&amp; fileURLToPath(import.meta.url) === path.resolve(process.argv&#91;1 | F4.3, F4.4 | M24, M25, M26 | 按M24,M25,M26比较结论保留其必要职责 |

<a id="Pef6ceb7a"></a>

## hooks/shared/knowledge.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pef6ceb7a-1 | 1–19 | 文件头/元信息 | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-20 | 20–20 | import * as fs from 'node:fs'; | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-21 | 21–21 | import * as path from 'node:path'; | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-22 | 22–22 | import { extensionRoot, lines, readTextOrNull, relDisplay } from './paths.mjs'; | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-23 | 23–25 | import { parseYaml } from './yaml-lite.mjs'; | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-26 | 26–28 | KNOWLEDGE_KINDS | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-29 | 29–31 | INDEX_KIND | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-32 | 32–34 | MANIFEST_NAME | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-35 | 35–36 | REVIEW_ACTION_MARK | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-37 | 37–38 | KnowledgeError | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-39 | 39–43 | fail | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-44 | 44–50 | splitFrontmatter | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-51 | 51–60 | frontmatterPairs | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-61 | 61–73 | fmList | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-74 | 74–90 | splitCells | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-91 | 91–108 | markdownTable | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-109 | 109–114 | pick | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-115 | 115–117 | ENTRY_ID_RE | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-118 | 118–120 | PROBE_COLUMN | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-121 | 121–136 | PROBE_KINDS | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-137 | 137–160 | parseProbe | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-161 | 161–211 | parseConstraintFile | F4.3 | M24, M25 | 按M24,M25比较结论保留其必要职责 |
| Pef6ceb7a-212 | 212–236 | parsePatternFile | F4.4, F4.5 | M26, M27 | 按M26,M27比较结论保留其必要职责 |
| Pef6ceb7a-237 | 237–269 | parseFactFile | F4.2 | M23 | 按M23比较结论保留其必要职责 |
| Pef6ceb7a-270 | 270–296 | knowledgeFiles | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-297 | 297–339 | activeKnowledge | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-340 | 340–357 | entryById | F4.1 | M22 | 按M22比较结论保留其必要职责 |
| Pef6ceb7a-358 | 358–427 | selfCheck | F4.1 | M22 | 按M22比较结论保留其必要职责 |

<a id="Pf51c4105"></a>

## hooks/shared/obligations.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pf51c4105-1 | 1–18 | 文件头/元信息 | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| Pf51c4105-19 | 19–20 | VERIFY_KINDS | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| Pf51c4105-21 | 21–21 | arr | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| Pf51c4105-22 | 22–23 | name | F4.5, F4.6, F4.8, F4.9 | M27, M29 | 按M27,M29比较结论保留其必要职责 |
| Pf51c4105-24 | 24–34 | mustOf | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pf51c4105-35 | 35–81 | obligationsFromContracts | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pf51c4105-82 | 82–104 | misplacedMust | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pf51c4105-105 | 105–117 | patternRolesFromContracts | F4.4, F4.5 | M26, M27 | 按M26,M27比较结论保留其必要职责 |

<a id="P7b12f336"></a>

## hooks/shared/paths.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P7b12f336-1 | 1–6 | 文件头/元信息 | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-7 | 7–7 | import * as fs from 'node:fs'; | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-8 | 8–10 | import * as path from 'node:path'; | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-11 | 11–19 | readConfig | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-20 | 20–25 | extensionRoot | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-26 | 26–31 | featuresDir | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-32 | 32–36 | featureRoot | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-37 | 37–41 | relDisplay | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-42 | 42–51 | readTextOrNull | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-52 | 52–61 | readJsonOrNull | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P7b12f336-62 | 62–64 | lines | F7.1 | M36 | 按M36比较结论保留其必要职责 |

<a id="P17056b41"></a>

## hooks/shared/pre_verifier.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P17056b41-1 | 1–19 | 文件头/元信息 | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-20 | 20–20 | import * as path from 'node:path'; | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-21 | 21–21 | import { extensionRoot, lines, readTextOrNull } from './paths.mjs'; | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-22 | 22–24 | import { readerReviewTask } from './reader-review-task.mjs'; | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-25 | 25–27 | KNOWLEDGE_CHECK_PREFIX | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-28 | 28–30 | READER_REVIEW_ID | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-31 | 31–48 | SOURCE_OF_TRUTH | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-49 | 49–69 | overlayCheckIds | F5.5, F4.7 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P17056b41-70 | 70–128 | preVerifier | F5.5, F4.7 | M33 | 按M33比较结论保留其必要职责 |

<a id="P217c29f4"></a>

## hooks/shared/probes.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P217c29f4-1 | 1–12 | 文件头/元信息 | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P217c29f4-13 | 13–13 | import * as fs from 'node:fs'; | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P217c29f4-14 | 14–25 | import * as path from 'node:path'; | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P217c29f4-26 | 26–61 | blankComments | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P217c29f4-62 | 62–76 | readOrNull | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P217c29f4-77 | 77–92 | filesForEntity | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P217c29f4-93 | 93–120 | methodBody | F4.6 | M27 | 按M27比较结论保留其必要职责 |
| P217c29f4-121 | 121–198 | runProbe | F4.6 | M27 | 按M27比较结论保留其必要职责 |

<a id="Pa27ccc8e"></a>

## hooks/shared/reader-review-task.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pa27ccc8e-1 | 1–7 | 文件头/元信息 | F5.5, F2.7, F5.7 | M33, M34, M38 | 按M33,M34,M38比较结论保留其必要职责 |
| Pa27ccc8e-8 | 8–8 | import * as fs from 'node:fs'; | F5.5, F2.7, F5.7 | M33, M34, M38 | 按M33,M34,M38比较结论保留其必要职责 |
| Pa27ccc8e-9 | 9–9 | import * as path from 'node:path'; | F5.5, F2.7, F5.7 | M33, M34, M38 | 按M33,M34,M38比较结论保留其必要职责 |
| Pa27ccc8e-10 | 10–11 | import { extensionRoot, featureRoot, readJsonOrNull, readTextOrNull } from './paths.m | F5.5, F2.7, F5.7 | M33, M34, M38 | 按M33,M34,M38比较结论保留其必要职责 |
| Pa27ccc8e-12 | 12–22 | contractOf | F5.5, F2.7, F5.7 | M33, M34, M38 | 按M33,M34,M38比较结论保留其必要职责 |
| Pa27ccc8e-23 | 23–43 | imageRows | F2.4.2, F1.3 | M03, M14, M15, M16 | 按M03,M14,M15,M16比较结论保留其必要职责 |
| Pa27ccc8e-44 | 44–72 | sourceCatalogue | F5.5, F5.7, F2.2 | M09 | 按R09处理局部；不整块删 |
| Pa27ccc8e-73 | 73–74 | sourceCatalogue | F5.5, F5.7, F2.2 | M09 | 按M09比较结论保留其必要职责 |
| Pa27ccc8e-75 | 75–82 | planJson | F5.5, F5.7, F2.2 | M09 | 按R09处理局部；不整块删 |
| Pa27ccc8e-83 | 83–90 | planJson | F5.5, F5.7, F2.2 | M09 | 按M09比较结论保留其必要职责 |
| Pa27ccc8e-91 | 91–177 | readerReviewTask | F5.5, F5.7, F2.4.2 | M33 | 按M33比较结论保留其必要职责 |
| Pa27ccc8e-178 | 178–195 | readerReviewTask | F5.5, F5.7, F2.4.2 | M33 | 按R20处理局部；不整块删 |
| Pa27ccc8e-196 | 196–196 | readerReviewTask | F5.5, F5.7, F2.4.2 | M33 | 按R02,R20处理局部；不整块删 |
| Pa27ccc8e-197 | 197–198 | readerReviewTask | F5.5, F5.7, F2.4.2 | M33 | 按R20处理局部；不整块删 |
| Pa27ccc8e-199 | 199–212 | readerReviewTask | F5.5, F5.7, F2.4.2 | M33 | 按M33比较结论保留其必要职责 |
| Pa27ccc8e-213 | 213–234 | readerReviewTask | F5.5, F5.7, F2.4.2 | M33 | 按R20处理局部；不整块删 |
| Pa27ccc8e-235 | 235–236 | readerReviewTask | F5.5, F5.7, F2.4.2 | M33 | 按M33比较结论保留其必要职责 |

<a id="P9e0e1fc3"></a>

## hooks/shared/verifier-report.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P9e0e1fc3-1 | 1–23 | 文件头/元信息 | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-24 | 24–24 | import * as path from 'node:path'; | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-25 | 25–25 | import { featureRoot, readJsonOrNull, readTextOrNull } from './paths.mjs'; | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-26 | 26–28 | import { parseYaml } from './yaml-lite.mjs'; | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-29 | 29–31 | STORY_REVIEW_ID | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-32 | 32–34 | DETAIL_KEYS | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-35 | 35–42 | SUMMARY_COLUMNS | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-43 | 43–53 | INVALID_EVIDENCE | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-54 | 54–68 | reportLocation | F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-69 | 69–79 | summaryRow | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-80 | 80–92 | yamlBlocks | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-93 | 93–113 | checksIn | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-114 | 114–148 | readerReviewDetails | F5.5, F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P9e0e1fc3-149 | 149–242 | storyReviewProblems | F5.6 | M33 | 按M33比较结论保留其必要职责 |

<a id="P1ed38028"></a>

## hooks/shared/yaml-lite.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P1ed38028-1 | 1–15 | 文件头/元信息 | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-16 | 16–17 | import { lines } from './paths.mjs'; | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-18 | 18–18 | KV_RE | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-19 | 19–20 | ITEM_RE | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-21 | 21–23 | BLOCK_RE | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-24 | 24–58 | scalar | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-59 | 59–78 | blockScalar | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-79 | 79–86 | inlineSeq | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-87 | 87–90 | indentOf | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-91 | 91–100 | isBlank | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-101 | 101–178 | parseBlock | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-179 | 179–188 | parseSeqItemMap | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-189 | 189–196 | nextMeaningfulIndent | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-197 | 197–208 | isSeqAt | F7.1 | M36 | 按M36比较结论保留其必要职责 |
| P1ed38028-209 | 209–215 | parseYaml | F7.1 | M36 | 按M36比较结论保留其必要职责 |

<a id="Pf87c4656"></a>

## hooks/spec/author.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pf87c4656-1 | 1–2 | spec 阶段 · 扩展要求（写之前读这一页） | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-3 | 3–4 | spec 阶段 · 扩展要求（写之前读这一页） / &gt; **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-5 | 5–7 | spec 阶段 · 扩展要求（写之前读这一页） / **这一页写原则与写法**。这一次的数据（你在哪、激活几条、有哪几张图、哪些词不能用）由同一个钩子生成的**任务包**给出。 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-8 | 8–9 | 先分清你在哪一组 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-10 | 10–11 | 先分清你在哪一组 / 这个需求走了 &#96;/story&#96; 链吗（需求目录里有 &#96;AR/story-src/story-flow.json&#96;）？ | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-12 | 12–16 | 先分清你在哪一组 / &#124; &#124; 走 &#96;/story&#96; &#124; 直接跑 spec &#124; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-17 | 17–19 | 先分清你在哪一组 / 这是**判据本身的分组**，不是建议：§9 与术语解释列是扩展新增的，对只跑原生 spec 的人 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-20 | 20–21 | 知识判断怎么填 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-22 | 22–24 | 知识判断怎么填 / **§10 与 §11 不手写**。它们是 &#96;spec/knowledge-use.yaml&#96; 的投影，由 &#96;render&#96; 写进 sp | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-25 | 25–34 | 知识判断怎么填 / - **命中**：&#96;requirement&#96; 写成**列表，一条要求一句**（§10 逐条成行）——把编号遮住还能 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-35 | 35–37 | 知识判断怎么填 / **知识只读激活清单里的那些**：&#96;manifest.yaml&#96; 的 &#96;provides.knowledge&#96; 是本阶段生效的全部， | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-38 | 38–39 | 写字的三条 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-40 | 40–43 | 写字的三条 / **数值要标来源**。阈值、时长、次数三选一标明：&#96;（上游约束：&lt;文档名&gt;）&#96; / | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-44 | 44–47 | 写字的三条 / **验收要接回规约**。&#96;doc/features/&lt;需求名&gt;/acceptance.yaml&#96; 里，每条命中的规约要有一条带 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-48 | 48–49 | 写字的三条 / 判定的推演、决策论证与规约条目的逐条回显都不进 spec：它是交给代码的要求说明书，回显在归档件附录里。 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-50 | 50–51 | 写字的三条 / **上游画过的图搬进 story**，围栏第一行写来源标记，只搬图不搬文字；哪几张、原文长什么样见任务包里那两节。 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-52 | 52–53 | 跑哪条命令 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-54 | 54–57 | 跑哪条命令 / 示例或代码块 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-58 | 58–59 | 跑哪条命令 / 走 &#96;/story&#96; 链时，这一段的顺序由 &#96;story_flow.py status&#96; 逐步打印（它也给出这一步要写的文件长什么样）， | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| Pf87c4656-60 | 60–60 | 跑哪条命令 / 取证怎么做、结论怎么写才能按名回查，见 &#91;&#96;skills/story/reference/evidence-rules.md&#96;&#93;(../ | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |

<a id="P2aad25c7"></a>

## hooks/spec/author.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P2aad25c7-1 | 1–19 | 文件头/元信息 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-20 | 20–20 | import { spawnSync } from 'node:child_process'; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-21 | 21–21 | import * as fs from 'node:fs'; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-22 | 22–22 | import * as path from 'node:path'; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-23 | 23–23 | import { fileURLToPath } from 'node:url'; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-24 | 24–24 | import { featureRoot, readJsonOrNull, relDisplay } from '../shared/paths.mjs'; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-25 | 25–25 | import { activeKnowledge } from '../shared/knowledge.mjs'; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-26 | 26–26 | import { clientVocabulary } from '../../skills/story/scripts/core/lint-rules.mjs'; | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-27 | 27–29 | import { carryableBlock, DECISION_FIELDS, diagramsOf, diagramTopic, relFromStory, she | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-30 | 30–31 | SELF | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-32 | 32–32 | WRITE_DOC | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-33 | 33–40 | SKILL_ROOT | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-41 | 41–54 | flowStatus | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-55 | 55–69 | positionSection | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-70 | 70–114 | knowledgeSection | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-115 | 115–140 | acceptanceKeys | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按R19处理局部；不整块删 |
| P2aad25c7-141 | 141–145 | acceptancePath | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-146 | 146–157 | decisionSection | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-158 | 158–199 | imageSection | F2.4.2, F1.3, F5.1 | M03, M14, M15, M16 | 按R12处理局部；不整块删 |
| P2aad25c7-200 | 200–210 | imageSection | F2.4.2, F1.3, F5.1 | M03, M14, M15, M16 | 按M03,M14,M15,M16比较结论保留其必要职责 |
| P2aad25c7-211 | 211–226 | diagramSection | F2.4.2, F1.3, F2.3, F5.1 | M16 | 按R10处理局部；不整块删 |
| P2aad25c7-227 | 227–228 | diagramSection | F2.4.2, F1.3, F2.3, F5.1 | M16 | 按M16比较结论保留其必要职责 |
| P2aad25c7-229 | 229–242 | docText | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-243 | 243–268 | draftEntrySection | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-269 | 269–296 | vocabularySection | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-297 | 297–329 | taskPackage | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-330 | 330–331 | USAGE | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-332 | 332–342 | main | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P2aad25c7-343 | 343–350 | if (process.argv&#91;1&#93; &amp;&amp; fileURLToPath(import.meta.url) === path.resolve(process.argv&#91;1 | F5.1, F2.2, F4.3, F4.4 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |

<a id="Pf46b01c8"></a>

## hooks/spec/post_check.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pf46b01c8-1 | 1–18 | 文件头/元信息 | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-19 | 19–19 | import * as fs from 'node:fs'; | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-20 | 20–20 | import * as path from 'node:path'; | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-21 | 21–21 | import { parseYaml } from '../shared/yaml-lite.mjs'; | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-22 | 22–22 | import { scanBannedTerms, formatHits } from '../../skills/story/scripts/core/lint-rul | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-23 | 23–23 | import { flowProblems, isStoryFeature, storyProduced } from '../../skills/story/scrip | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-24 | 24–24 | import { STATUS } from '../shared/evidence.mjs'; | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-25 | 25–25 | import { guard, gate } from '../shared/gate.mjs'; | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-26 | 26–26 | import { activeKnowledge, selfCheck } from '../shared/knowledge.mjs'; | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-27 | 27–29 | import { | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-30 | 30–31 | import { featureRoot as featureRootOf, relDisplay } from '../shared/paths.mjs'; | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-32 | 32–32 | SECTIONS_DOC | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-33 | 33–35 | EVIDENCE_DOC | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-36 | 36–44 | sectionBody | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-45 | 45–48 | isSeparatorRow | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-49 | 49–54 | rowCells | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-55 | 55–59 | hasTemplatePlaceholder | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-60 | 60–85 | sectionFilled | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-86 | 86–87 | DOC_COORD_RE | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-88 | 88–110 | scanDocCoords | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pf46b01c8-111 | 111–111 | NUMERIC_RE | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-112 | 112–113 | SOURCE_TAG_RE | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-114 | 114–123 | UNIT_ALIASES | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-124 | 124–163 | scanNumericSources | F2.6, F4.3, F2.2 | M24 | 按R16处理局部；不整块删 |
| Pf46b01c8-164 | 164–166 | scanNumericSources | F2.6, F4.3, F2.2 | M24 | 按M24比较结论保留其必要职责 |
| Pf46b01c8-167 | 167–174 | findHeading | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-175 | 175–194 | sectionRange | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-195 | 195–262 | knowledgeExitProblems | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-263 | 263–268 | acceptanceCoverage | F2.2, F4.3, F4.4, F5.3, F5.5, F4.8, F4.9, F2.5, F5.1 | M29 | 按R19处理局部；不整块删 |
| Pf46b01c8-269 | 269–269 | acceptanceCoverage | F2.2, F4.3, F4.4, F5.3, F5.5, F4.8, F4.9, F2.5, F5.1 | M29 | 按R18,R19处理局部；不整块删 |
| Pf46b01c8-270 | 270–313 | acceptanceCoverage | F2.2, F4.3, F4.4, F5.3, F5.5, F4.8, F4.9, F2.5, F5.1 | M29 | 按R19处理局部；不整块删 |
| Pf46b01c8-314 | 314–333 | acceptanceCoverage | F2.2, F4.3, F4.4, F5.3, F5.5, F4.8, F4.9, F2.5, F5.1 | M29 | 按M29比较结论保留其必要职责 |
| Pf46b01c8-334 | 334–348 | strayProse | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-349 | 349–352 | SPEC_EXT_SECTIONS | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| Pf46b01c8-353 | 353–519 | export default guard('spec', async (ctx) =&gt; { | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |

<a id="P66e23afd"></a>

## hooks/testing/author.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P66e23afd-1 | 1–2 | testing 阶段 · 扩展要求（写之前读这一页） | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-3 | 3–4 | testing 阶段 · 扩展要求（写之前读这一页） / &gt; **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-5 | 5–7 | testing 阶段 · 扩展要求（写之前读这一页） / **契约实体上的 &#96;must&#96; 就是本阶段的知识来源**：plan 已经把每条规约义务挂到了扛着它的 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-8 | 8–9 | testing 阶段 · 扩展要求（写之前读这一页） / **本阶段是最后一道关**——这些约束再往后就没有验证环节了。 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-10 | 10–11 | 一、读哪几个文件 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-12 | 12–16 | 一、读哪几个文件 / &#124; 文件 &#124; 拿什么 &#124; | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-17 | 17–18 | 二、产出形态 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-19 | 19–20 | 二、产出形态 / **&#96;must.verify&#96; 就是分派单源**： | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-21 | 21–26 | 二、产出形态 / &#124; verify &#124; 本阶段 &#124; | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-27 | 27–28 | 二、产出形态 / 按验收条目的 &#96;device_focus&#96; 走查或测量，给**可复核证据**：截图、数值、日志。 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-29 | 29–30 | 二、产出形态 / **「已验证」三个字不构成结论**——只写「符合要求」而没有可复核证据的，记为未验证。 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-31 | 31–33 | 二、产出形态 / 确实到不了的（环境不具备、依赖未就绪），诚实写「待验证 + 阻塞原因」，不要标成已验证。 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-34 | 34–35 | 三、跑哪条命令 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-36 | 36–39 | 三、跑哪条命令 / 示例或代码块 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-40 | 40–41 | 四、门禁会拦什么 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P66e23afd-42 | 42–43 | 四、门禁会拦什么 / - &#96;verify&#96; 为 &#96;device&#96; / &#96;both&#96; 的义务在本阶段没有覆盖，也没有说法。 | F4.9, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |

<a id="P11d3a6c3"></a>

## hooks/testing/post_check.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P11d3a6c3-1 | 1–16 | 文件头/元信息 | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P11d3a6c3-17 | 17–17 | import * as fs from 'node:fs'; | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P11d3a6c3-18 | 18–18 | import * as path from 'node:path'; | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P11d3a6c3-19 | 19–19 | import { featureRoot, readTextOrNull } from '../shared/paths.mjs'; | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P11d3a6c3-20 | 20–20 | import { knowledgeCriteria, readAcceptance, readContracts } from '../shared/contracts | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P11d3a6c3-21 | 21–21 | import { obligationsFromContracts } from '../shared/obligations.mjs'; | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P11d3a6c3-22 | 22–30 | import { guard, gate } from '../shared/gate.mjs'; | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P11d3a6c3-31 | 31–56 | referencedAcceptanceIds | F4.9 | M29 | 按M29比较结论保留其必要职责 |
| P11d3a6c3-57 | 57–107 | export default guard('testing', async (ctx) =&gt; { | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |

<a id="P39c90524"></a>

## hooks/ut/author.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P39c90524-1 | 1–2 | ut 阶段 · 扩展要求（写之前读这一页） | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-3 | 3–4 | ut 阶段 · 扩展要求（写之前读这一页） / &gt; **推进不逐段问**：门禁报错怎么修、check 过了下一步做什么、进 harness 还是进 verifier——这些是义务不是选 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-5 | 5–7 | ut 阶段 · 扩展要求（写之前读这一页） / **契约实体上的 &#96;must&#96; 就是本阶段的知识来源**：plan 已经把每条规约义务挂到了扛着它的 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-8 | 8–9 | 一、读哪几个文件 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-10 | 10–14 | 一、读哪几个文件 / &#124; 文件 &#124; 拿什么 &#124; | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-15 | 15–16 | 二、产出形态 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-17 | 17–18 | 二、产出形态 / **&#96;must.verify&#96; 就是分派单源**，不必另找豁免清单： | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-19 | 19–24 | 二、产出形态 / &#124; verify &#124; 本阶段 &#124; | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-25 | 25–26 | 二、产出形态 / 不由 UT 验的条目不必也不应为它硬造用例。 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-27 | 27–28 | 二、产出形态 / 每条义务二选一：**真实证据**（哪个用例覆盖了它）或**显式不适用 + 理由**。不能什么都不写。 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-29 | 29–30 | 三、跑哪条命令 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-31 | 31–34 | 三、跑哪条命令 / 示例或代码块 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-35 | 35–36 | 四、门禁会拦什么 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-37 | 37–42 | 四、门禁会拦什么 / - &#96;verify&#96; 为 &#96;ut&#96; / &#96;both&#96; 的义务在本阶段没有覆盖，也没有说法。 | F4.8, F5.1 | M29, M30 | 按M29,M30比较结论保留其必要职责 |
| P39c90524-43 | 43–43 | R06 / 覆盖不了就回 plan 把 &#96;must.verify&#96; 改成 &#96;device&#96;，不要留一条名字对得上、断言不相干的用例充数。 | F4.8, F5.1 | M29, M30 | 按R06处理局部；不整块删 |

<a id="P074e60a5"></a>

## hooks/ut/post_check.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P074e60a5-1 | 1–16 | 文件头/元信息 | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-17 | 17–17 | import * as fs from 'node:fs'; | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-18 | 18–18 | import * as path from 'node:path'; | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-19 | 19–19 | import { featureRoot, readTextOrNull } from '../shared/paths.mjs'; | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-20 | 20–20 | import { knowledgeCriteria, readAcceptance, readContracts } from '../shared/contracts | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-21 | 21–21 | import { obligationsFromContracts } from '../shared/obligations.mjs'; | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-22 | 22–24 | import { guard, gate } from '../shared/gate.mjs'; | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-25 | 25–57 | coveredAcceptanceIds | F4.8 | M29 | 按M29比较结论保留其必要职责 |
| P074e60a5-58 | 58–91 | export default guard('ut', async (ctx) =&gt; { | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P074e60a5-92 | 92–92 | export default guard('ut', async (ctx) =&gt; { | F4.8, F5.5 | M29, M33 | 按R06处理局部；不整块删 |
| P074e60a5-93 | 93–104 | export default guard('ut', async (ctx) =&gt; { | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |

<a id="P35e5bb95"></a>

## knowledge/constraints/compatibility-checklist.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P35e5bb95-1 | 1–6 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P35e5bb95-7 | 7–8 | 兼容性检查表 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P35e5bb95-9 | 9–10 | 兼容性检查表 / 兼容性逐项过表的数据源：判定时对本表逐项过，命中项给分析结论与兼容方案；未命中类别汇总一行「不涉及」。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P35e5bb95-11 | 11–12 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P35e5bb95-13 | 13–17 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P35e5bb95-18 | 18–19 | 判定附注 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P35e5bb95-20 | 20–24 | 判定附注 / - **命中判定须指回具体变更的名字**（如新增接口 &#96;createBusinessOrder&#96; 的入参字段）， | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="Pb5a8f608"></a>

## knowledge/constraints/deliverables.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pb5a8f608-1 | 1–6 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pb5a8f608-7 | 7–8 | 资料交付 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pb5a8f608-9 | 9–10 | 资料交付 / 管代码之外的交付杂项——易被遗忘、却阻塞上线或影响协作的流程性事项。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pb5a8f608-11 | 11–12 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pb5a8f608-13 | 13–17 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pb5a8f608-18 | 18–19 | 落法附注 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pb5a8f608-20 | 20–27 | 落法附注 / - **DLV-01**：翻译提交流程 &#96;&lt;待补充：翻译提交流程&gt;&#96;。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="P1cbb8906"></a>

## knowledge/constraints/dfx-baseline.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P1cbb8906-1 | 1–6 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-7 | 7–8 | DFX 基线（性能/功耗/ROM/RAM） | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-9 | 9–10 | DFX 基线（性能/功耗/ROM/RAM） / 管性能量化基线与功耗、包体、内存的引入评估；性能指标本体由需求自身声明。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-11 | 11–12 | 基线值 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-13 | 13–19 | 基线值 / &#124; 指标 &#124; 基线 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-20 | 20–21 | 基线值 / 数值基线补齐前不得臆造数值：量化指标须由需求自身论证，不得引用本表。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-22 | 22–23 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-24 | 24–28 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-29 | 29–30 | 落法附注 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-31 | 31–32 | 落法附注 / 只列本工程决策与平台易错点，通用用法不赘述。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P1cbb8906-33 | 33–33 | 落法附注 / - **DFX-01**：端云接口另排查定时任务、开机启动任务、定时是否离散、是否并发、有无缓存方案、请求间隔是否合理。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="P65753a34"></a>

## knowledge/constraints/env-exceptions.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P65753a34-1 | 1–6 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P65753a34-7 | 7–8 | 环境异常标准场景库 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P65753a34-9 | 9–10 | 环境异常标准场景库 / 管「用户调整设备环境」导致的异常场景——基础三类（网络/空数据/权限）之外最易遗漏的一族。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P65753a34-11 | 11–12 | 异常三分类 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P65753a34-13 | 13–18 | 异常三分类 / &#124; 分类 &#124; 定义 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P65753a34-19 | 19–20 | 异常三分类 / 前两类由需求自身的异常场景清单承载。特殊分支不属于异常场景，在实现方案中说明分支处理细节。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P65753a34-21 | 21–22 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P65753a34-23 | 23–26 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="P976a8bf4"></a>

## knowledge/constraints/observability.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P976a8bf4-1 | 1–7 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P976a8bf4-8 | 8–9 | 可观测性 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P976a8bf4-10 | 10–11 | 可观测性 / 管新增或改动业务流程的观测覆盖。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P976a8bf4-12 | 12–13 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P976a8bf4-14 | 14–19 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P976a8bf4-20 | 20–21 | 判定附注 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P976a8bf4-22 | 22–24 | 判定附注 / - 命中看有没有新的业务过程，与有没有界面无关。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="P81b126c3"></a>

## knowledge/constraints/README.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P81b126c3-1 | 1–5 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P81b126c3-6 | 6–7 | 规约 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P81b126c3-8 | 8–9 | 规约 / 各域同一张条目表，列义如下；判定边界见各域的「判定附注 / 落法附注」。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P81b126c3-10 | 10–18 | 规约 / &#124; 列 &#124; 含义 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P81b126c3-19 | 19–20 | 读条目须知 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P81b126c3-21 | 21–25 | 读条目须知 / - &#96;&lt;待补充：…&gt;&#96; 是空缺登记：判定时写「基准待补充，按条目语义定性评估」，不得臆造数值。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P81b126c3-26 | 26–27 | 域清单 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P81b126c3-28 | 28–37 | 域清单 / &#124; 文件 &#124; 域前缀 &#124; applies_when &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="P8e53b7cd"></a>

## knowledge/constraints/resource-usage.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P8e53b7cd-1 | 1–7 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P8e53b7cd-8 | 8–9 | 资源使用 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P8e53b7cd-10 | 10–11 | 资源使用 / 管图片与字符串的来源选择：先复用，再新增。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P8e53b7cd-12 | 12–13 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P8e53b7cd-14 | 14–18 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P8e53b7cd-19 | 19–20 | 判定附注 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P8e53b7cd-21 | 21–25 | 判定附注 / - **10KB 是本工程设定值**（非平台限制）。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="Pce1f6404"></a>

## knowledge/constraints/security-privacy.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pce1f6404-1 | 1–6 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-7 | 7–8 | 安全隐私 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-9 | 9–10 | 安全隐私 / 管个人数据、权限、对外暴露面的红线。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-11 | 11–12 | 覆盖面 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-13 | 13–15 | 覆盖面 / 个人数据的采集、传递与输出；用户协议同意与更新；对外暴露接口与页面；敏感权限申请。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-16 | 16–17 | 覆盖面 / 新增权限获取、采集新的个人数据、新增特性或业务出海三种情形须重点评估。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-18 | 18–19 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-20 | 20–23 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-24 | 24–25 | 落法附注 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-26 | 26–27 | 落法附注 / 只列本工程决策与平台易错点，通用用法不赘述。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| Pce1f6404-28 | 28–30 | 落法附注 / - **SEC-01**：脱敏在**采集处**做，输出端过滤不作为落实方式。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="P6805ef8a"></a>

## knowledge/constraints/ux-consistency.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P6805ef8a-1 | 1–6 | 文件头/元信息 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P6805ef8a-7 | 7–8 | UX 一致性 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P6805ef8a-9 | 9–10 | UX 一致性 / 管新增/改版界面在多形态设备与系统显示设置下的一致性。产品有对应形态的设计是各条的共同前提。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P6805ef8a-11 | 11–12 | 条目 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P6805ef8a-13 | 13–16 | 条目 / &#124; 编号 &#124; 约束 &#124; 强制力 &#124; 命中条件 &#124; 处置 &#124; 验证（执行体） &#124; 探针 &#124; | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P6805ef8a-17 | 17–18 | 落法附注 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P6805ef8a-19 | 19–20 | 落法附注 / 只列本工程决策与平台易错点，通用 ArkUI 用法不赘述。 | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |
| P6805ef8a-21 | 21–26 | 落法附注 / - **UX-01** | F4.3 | M24, M37 | 按M24,M37比较结论保留其必要职责 |

<a id="P7f2b4ecd"></a>

## knowledge/design-patterns/decision-tree.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P7f2b4ecd-1 | 1–11 | 文件头/元信息 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-12 | 12–13 | 流程分支编排（决策树） | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-14 | 14–16 | 流程分支编排（决策树） / 把一段复杂业务流程拆成**节点表**：每个节点做一件事，并返回下一个要执行的节点。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-17 | 17–18 | 流程分支编排（决策树） / --- | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-19 | 19–20 | 上篇 · 适用与选型（读者：plan） | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-21 | 21–22 | 1. 解决什么问题 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-23 | 23–26 | 1. 解决什么问题 / 一段流程有多个分支，每个分支自身是多步的功能，各有自己的失败处理。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-27 | 27–29 | 1. 解决什么问题 / 节点表把它们拆开：**一个节点一件事，节点之间只通过「返回哪个节点」和「共享的上下文对象」耦合**。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-30 | 30–31 | 2. 什么时候不该用 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-32 | 32–35 | 2. 什么时候不该用 / - 流程是线性的，没有分叉——直接写方法更好读； | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-36 | 36–37 | 3. 契约投影 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-38 | 38–39 | 3. 契约投影 / 选型结论要落到 plan 的既有契约字段里，不自造字段： | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-40 | 40–47 | 3. 契约投影 / &#124; 模式概念 &#124; 投影到 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按R22处理局部；不整块删 |
| P7f2b4ecd-48 | 48–51 | 3. 契约投影 / **边界判据**：&#96;state_model.phases&#96; 是对外业务状态——UI 订阅它、业务用例断言它。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-52 | 52–53 | 3.1 plan 应用步骤 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-54 | 54–60 | 3.1 plan 应用步骤 / 1. 以一个有独立业务目标和明确起止的流程段为单位，逐条写出命中信号与反证；不适用就登记零命中。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-61 | 61–62 | 3.1 plan 应用步骤 / --- | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-63 | 63–64 | 下篇 · 结构与落地（读者：coding、review） | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-65 | 65–66 | 4. SDK 行为事实 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-67 | 67–68 | 4. SDK 行为事实 / 以下逐条是编排 SDK 的**实际运行时行为**（依据其类型声明与实现），不是使用建议： | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-69 | 69–81 | 4. SDK 行为事实 / - **状态机连续推进**：&#96;BaseStateMachine.fireEvents&#96; 是循环——节点返回下一个事件，它就接着执行下一个 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-82 | 82–83 | 5. 角色与文件落点 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-84 | 84–85 | 5. 角色与文件落点 / 一个决策树实例通常由这几个角色组成，按职责分文件： | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-86 | 86–93 | 5. 角色与文件落点 / &#124; 角色 &#124; 职责 &#124; 命名惯例 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-94 | 94–95 | 6. 结构骨架 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-96 | 96–151 | 6. 结构骨架 / 示例或代码块 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-152 | 152–153 | 7. 使用约定（人为纪律，SDK 不强制——review 逐条核查） | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-154 | 154–161 | 7. 使用约定（人为纪律，SDK 不强制——review 逐条核查） / 1. **决策逻辑只在节点表内**：分支判断写在节点函数里，不在调用方再包一层 if/else 决定调哪个树。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-162 | 162–163 | 8. 验证清单 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-164 | 164–171 | 8. 验证清单 / &#124; 阶段 &#124; 完成判据 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-172 | 172–173 | 9. 反模式 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P7f2b4ecd-174 | 174–176 | 9. 反模式 / **分支先后靠方法互调和改共享状态推进**：完整走向不可读，加分支要动全身。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责；2026-09-20 §9 改写，见[全盘分析](../00-全盘分析报告.md) §6 |

<a id="P58a4ee39"></a>

## knowledge/design-patterns/page-interaction.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P58a4ee39-1 | 1–11 | 文件头/元信息 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-12 | 12–13 | 页面交互编排 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-14 | 14–16 | 页面交互编排 / 把一个页面内的用户交互拆成**动作表**：每个动作做一件事，**业务逻辑执行完可以返回下一个动作**， | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-17 | 17–18 | 页面交互编排 / --- | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-19 | 19–20 | 上篇 · 适用与选型（读者：plan） | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-21 | 21–22 | 1. 解决什么问题 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-23 | 23–26 | 1. 解决什么问题 / 一个页面上用户交互非常多，且它们不是彼此独立的：确认之后要拉起验证，验证通过要提交， | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-27 | 27–29 | 1. 解决什么问题 / 动作表把交互与业务逻辑关联起来：**每个动作只写自己那一件事，把「接下来做什么」作为返回值交出去**。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-30 | 30–31 | 2. 什么时候不该用 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-32 | 32–35 | 2. 什么时候不该用 / - 页面只有两三个独立按钮，点完就结束——套编排是徒增间接层； | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-36 | 36–37 | 3. 契约投影 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-38 | 38–45 | 3. 契约投影 / &#124; 模式概念 &#124; 投影到 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按R22处理局部；不整块删 |
| P58a4ee39-46 | 46–47 | 3. 契约投影 / 边界同决策树：动作枚举是实现步骤，业务状态才是对外可观察的——两者不要混。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-48 | 48–49 | 3.1 plan 应用步骤 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-50 | 50–56 | 3.1 plan 应用步骤 / 1. 以一个页面或组件为单元，列出用户动作、业务结果驱动的后继动作与纯 UI 状态；独立按钮不纳入编排。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-57 | 57–58 | 3.1 plan 应用步骤 / --- | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-59 | 59–60 | 下篇 · 结构与落地（读者：coding、review） | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-61 | 61–62 | 4. SDK 行为事实 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-63 | 63–74 | 4. SDK 行为事实 / - **动作可以驱动下一个动作**：&#96;PageOperator&#96; 的返回类型是 &#96;void &#124; A &#124; Promise&lt;A &#124; void | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-75 | 75–76 | 5. 角色与文件落点 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-77 | 77–84 | 5. 角色与文件落点 / &#124; 角色 &#124; 职责 &#124; 命名惯例 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-85 | 85–86 | 6. 结构骨架 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-87 | 87–131 | 6. 结构骨架 / 示例或代码块 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-132 | 132–133 | 6. 结构骨架 / 用户在面板里提交验证码后，由面板回调再次 &#96;doOperator(CheckoutActions.SUBMIT)&#96; 续跑。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-134 | 134–135 | 7. 使用约定（人为纪律，SDK 不强制——review 逐条核查） | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-136 | 136–144 | 7. 使用约定（人为纪律，SDK 不强制——review 逐条核查） / 1. **页面动作必经 &#96;doOperator&#96;**：页面组件不直接调业务方法串流程，只发起动作； | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-145 | 145–146 | 8. 验证清单 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-147 | 147–154 | 8. 验证清单 / &#124; 阶段 &#124; 完成判据 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-155 | 155–156 | 9. 反模式 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| P58a4ee39-157 | 157–159 | 9. 反模式 / **交互顺序串在回调里**：交互链只存在于调用链中，插一步要逐个改回调。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责；2026-09-20 §9 改写，见[全盘分析](../00-全盘分析报告.md) §6 |

<a id="Pd2c1a3f3"></a>

## knowledge/design-patterns/README.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pd2c1a3f3-1 | 1–6 | 文件头/元信息 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-7 | 7–8 | 设计模式 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-9 | 9–10 | 设计模式 / 本目录是 **spec 阶段候选判定**与 **plan 阶段选型**的共同输入。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-11 | 11–13 | 设计模式 / &#96;pattern_id&#96; 是全链的受控标识：候选登记、知识决策表、各阶段门禁都只认它。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-14 | 14–18 | 设计模式 / **本文件是索引，不是判定书。** 某个模式什么时候适用、什么时候不适用、反例长什么样， | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-19 | 19–20 | 适用单元 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-21 | 21–22 | 适用单元 / 判断前先把需求切成单元，再逐个单元核对信号。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-23 | 23–27 | 适用单元 / &#124; 粒度 &#124; 含义 &#124; 用于 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-28 | 28–29 | 适用单元 / 一个需求通常有多个单元；同一单元可命中多个模式（叠加），也可一个都不命中。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-30 | 30–31 | 模式清单 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-32 | 32–36 | 模式清单 / &#124; &#96;pattern_id&#96; &#124; 文档 &#124; 解决什么 &#124; 依赖 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-37 | 37–38 | 模式清单 / 每份模式文档分上篇（适用与选型、契约投影）与下篇（SDK 行为事实、角色、骨架、约定、反模式），末尾有按阶段的验证清单。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-39 | 39–40 | 候选登记规则 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-41 | 41–43 | 候选登记规则 / **逐模式的命中信号与反例，读对应模式文件的上篇「适用与选型」**——先把需求切成单元， | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-44 | 44–46 | 候选登记规则 / 信号来自**业务流程本身**：数分支、数步数、看失败处理时，以需求描述的那个业务过程为准。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-47 | 47–52 | 候选登记规则 / **零命中同样要举证。** 反证要指向本需求的具体业务事实——哪一段流程、它有哪些分支、 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-53 | 53–54 | 多模式组合 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-55 | 55–56 | 多模式组合 / 组合不是把两个模式的角色揉成一套类。先分别完成每个单元的判断与契约投影，再声明衔接： | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |
| Pd2c1a3f3-57 | 57–64 | 多模式组合 / &#124; 要回答的问题 &#124; 契约落点 &#124; 代码判据 &#124; | F4.4, F4.5, F4.6 | M26, M37 | 按R22处理局部；不整块删 |
| Pd2c1a3f3-65 | 65–65 | 多模式组合 / 组合完成的判断是各自边界、上下文所有权、交接、等待与失败收敛都能从契约追到代码；没有组合需求时不创建组合层。 | F4.4, F4.5, F4.6 | M26, M37 | 按M26,M37比较结论保留其必要职责 |

<a id="P21b2c3ab"></a>

## knowledge/facts/codebase-facts.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P21b2c3ab-1 | 1–6 | 文件头/元信息 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-7 | 7–8 | 工程取证事实登记 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-9 | 9–11 | 工程取证事实登记 / **这个工程各类能力的现状：有没有、长什么样、怎么认出来。** 先找下面的既有实现，照它写； | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-12 | 12–14 | 工程取证事实登记 / **技术栈**：HarmonyOS 应用（ArkTS / ArkUI，hvigor 构建，模块级 &#96;oh-package.json5&#96;） | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-15 | 15–16 | 1. 对外暴露面 — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-17 | 17–20 | 1. 对外暴露面 — &#96;confirmed: 已确认&#96; / 应用清单 &#96;src/main/module.json5&#96; 的 &#96;abilities&#91;&#93;&#96;（看 &#96;exported&#96; 与 &#96;skills&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-21 | 21–22 | 2. 端云接口 — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-23 | 23–25 | 2. 端云接口 — &#96;confirmed: 已确认&#96; / **无端云封装（已核对）**：&#96;@ohos.net.http&#96; / &#96;http.createHttp&#96; / &#96;rcp&#96; / &#96;axios | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-26 | 26–27 | 3. 数据存储 — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-28 | 28–31 | 3. 数据存储 — &#96;confirmed: 已确认&#96; / 关系型持久化用 &#96;relationalStore&#96;（&#96;@kit.ArkData&#96;），封装在 Feature 模块的 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-32 | 32–33 | 4. 配置项 — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-34 | 34–37 | 4. 配置项 — &#96;confirmed: 已确认&#96; / 常量开关在各模块 &#96;src/main/ets/shared/constant/*Constants.ets&#96; 中，形态为 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-38 | 38–39 | 5. 可观测性 — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-40 | 40–41 | 5. 可观测性 — &#96;confirmed: 已确认&#96; / 日志、VOC、Chart 三渠道齐备，都在 &#96;CommFunc&#96;，惯例如下： | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-42 | 42–53 | 5. 可观测性 — &#96;confirmed: 已确认&#96; / - **日志** &#96;Logger&#96;（&#96;shared/log/Logger.ets&#96;，封装 &#96;hilog&#96;，&#96;debug&#96; / &#96;info | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-54 | 54–55 | 6. 敏感数据处理 — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-56 | 56–58 | 6. 敏感数据处理 — &#96;confirmed: 已确认&#96; / 通用脱敏 &#96;MaskUtil&#96;（&#96;CommFunc&#96; &#96;shared/utils/MaskUtil.ets&#96;）：&#96;maskPhone&#96;  | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-59 | 59–60 | 7. 资源 — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-61 | 61–64 | 7. 资源 — &#96;confirmed: 已确认&#96; / 字符串、颜色、尺寸在各模块 &#96;src/main/resources/base/element/&#96; 下的 &#96;string.json&#96; /  | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-65 | 65–66 | 8. 依赖变更（SDK / 组件 / TA） — &#96;confirmed: 已确认&#96; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P21b2c3ab-67 | 67–68 | 8. 依赖变更（SDK / 组件 / TA） — &#96;confirmed: 已确认&#96; / 模块依赖声明在各模块根 &#96;oh-package.json5&#96; 的 &#96;dependencies&#96;（&#96;CommFunc&#96; 为空）；模块清单在 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |

<a id="P960ae9dd"></a>

## knowledge/facts/component-profile.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P960ae9dd-1 | 1–6 | 文件头/元信息 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-7 | 7–8 | 部件画像 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-9 | 9–10 | 部件画像 / **本部件是谁、承担什么、与谁交互。** | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-11 | 11–12 | 1. 部件申明 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-13 | 13–18 | 1. 部件申明 / - **部件名称**：单框架钱包 / 纯鸿蒙钱包 / 钱包客户端 / WalletForHMOS | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-19 | 19–21 | 1. 部件申明 / 职责范围具体化：卡证票券（银行卡、交通卡、门钥匙、证件、票券等）在手机上的添加、展示、 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-22 | 22–23 | 2. 交互方清单 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-24 | 24–25 | 2. 交互方清单 / 判定「某段上游内容是否与本部件相关」时，按以下六类交互方逐一核对： | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-26 | 26–34 | 2. 交互方清单 / &#124; # &#124; 交互方 &#124; 交互方式 &#124; 说明 &#124; | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P960ae9dd-35 | 35–35 | 2. 交互方清单 / 命中任一交互方 → 与本部件相关；均不命中（如纯云侧内部改造、其他部件独立排期项）→ 不相关。 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |

<a id="P398c66b1"></a>

## knowledge/facts/README.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P398c66b1-1 | 1–5 | 文件头/元信息 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P398c66b1-6 | 6–7 | 项目知识 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P398c66b1-8 | 8–9 | 项目知识 / 一节一面（一类能力）：有没有、叫什么、在哪。照它写。 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P398c66b1-10 | 10–10 | 项目知识 / - &#96;confirmed: 已确认&#96; = 已对仓核实；&#96;未确认&#96; = 用前先核。 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P398c66b1-11 | 11–11 | 项目知识 / - &#96;confirmed: 已确认&#96; = 已对仓核实；&#96;未确认&#96; = 用前先核。 | F4.2 | M23, M37 | 按R17处理局部；不整块删 |
| P398c66b1-12 | 12–13 | 项目知识 / - &#96;confirmed: 已确认&#96; = 已对仓核实；&#96;未确认&#96; = 用前先核。 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P398c66b1-14 | 14–15 | 这一类里固定的一份：部件画像 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P398c66b1-16 | 16–19 | 这一类里固定的一份：部件画像 / &#96;component-profile.md&#96; —— 这个仓是什么部件、有哪些交互方、职责边界到哪。装扩展时第一份写的就是它， | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |
| P398c66b1-20 | 20–20 | 这一类里固定的一份：部件画像 / 其余项目事实按面另起文件，名字随内容——**只有进了激活清单的才读得到**，目录里躺着的没人看。 | F4.2 | M23, M37 | 按M23,M37比较结论保留其必要职责 |

<a id="P40d54a8c"></a>

## knowledge/README.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P40d54a8c-1 | 1–5 | 文件头/元信息 | F4.1 | M22, M37 | 按M22,M37比较结论保留其必要职责 |
| P40d54a8c-6 | 6–7 | 知识 | F4.1 | M22, M37 | 按M22,M37比较结论保留其必要职责 |
| P40d54a8c-8 | 8–9 | 知识 / 三类，各在一个目录： | F4.1 | M22, M37 | 按M22,M37比较结论保留其必要职责 |
| P40d54a8c-10 | 10–13 | 知识 / - **规约** &#96;constraints/&#96;：必须做或禁止做的事。逐条判命中；命中即义务，落实并验证。 | F4.1 | M22, M37 | 按M22,M37比较结论保留其必要职责 |
| P40d54a8c-14 | 14–14 | 知识 / 需要具体封装看 facts；需要时机与要求看 constraints；需要代码结构看 design-patterns。 | F4.1 | M22, M37 | 按M22,M37比较结论保留其必要职责 |

<a id="P7a130749"></a>

## manifest.yaml

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P7a130749-1 | 1–1 | schema_version | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-2 | 2–2 | name | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-3 | 3–3 | version | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-4 | 4–4 | description | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-5 | 5–5 | provides | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-6 | 6–6 | provides.skills | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-7 | 7–7 | provides.skills.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-8 | 8–13 | provides.skills.1 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-14 | 14–14 | provides.bridges | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-15 | 15–15 | provides.bridges.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-16 | 16–16 | provides.bridges.1 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-17 | 17–17 | provides.bridges.2 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-18 | 18–32 | provides.bridges.3 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-33 | 33–33 | provides.knowledge | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-34 | 34–34 | provides.knowledge.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-35 | 35–35 | provides.knowledge.1 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-36 | 36–36 | provides.knowledge.2 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-37 | 37–37 | provides.knowledge.3 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-38 | 38–38 | provides.knowledge.4 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-39 | 39–39 | provides.knowledge.5 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-40 | 40–40 | provides.knowledge.6 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-41 | 41–41 | provides.knowledge.7 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-42 | 42–42 | provides.knowledge.8 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-43 | 43–43 | provides.knowledge.9 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-44 | 44–44 | provides.knowledge.10 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-45 | 45–45 | provides.knowledge.11 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-46 | 46–46 | provides.knowledge.12 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-47 | 47–47 | provides.knowledge.13 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-48 | 48–48 | provides.knowledge.14 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-49 | 49–62 | provides.knowledge.15 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-63 | 63–63 | provides.hooks | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-64 | 64–64 | provides.hooks.spec | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-65 | 65–65 | provides.hooks.spec.post_check | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-66 | 66–66 | provides.hooks.spec.post_check.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-67 | 67–67 | provides.hooks.spec.pre_verifier | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-68 | 68–68 | provides.hooks.spec.pre_verifier.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-69 | 69–69 | provides.hooks.plan | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-70 | 70–70 | provides.hooks.plan.post_check | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-71 | 71–71 | provides.hooks.plan.post_check.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-72 | 72–72 | provides.hooks.plan.pre_verifier | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-73 | 73–73 | provides.hooks.plan.pre_verifier.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-74 | 74–74 | provides.hooks.coding | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-75 | 75–75 | provides.hooks.coding.post_check | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-76 | 76–76 | provides.hooks.coding.post_check.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-77 | 77–77 | provides.hooks.coding.pre_verifier | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-78 | 78–78 | provides.hooks.coding.pre_verifier.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-79 | 79–79 | provides.hooks.review | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-80 | 80–80 | provides.hooks.review.post_check | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-81 | 81–81 | provides.hooks.review.post_check.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-82 | 82–82 | provides.hooks.review.pre_verifier | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-83 | 83–83 | provides.hooks.review.pre_verifier.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-84 | 84–84 | provides.hooks.ut | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-85 | 85–85 | provides.hooks.ut.post_check | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-86 | 86–86 | provides.hooks.ut.post_check.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-87 | 87–87 | provides.hooks.ut.pre_verifier | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-88 | 88–88 | provides.hooks.ut.pre_verifier.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-89 | 89–89 | provides.hooks.testing | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-90 | 90–90 | provides.hooks.testing.post_check | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-91 | 91–91 | provides.hooks.testing.post_check.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-92 | 92–92 | provides.hooks.testing.pre_verifier | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-93 | 93–94 | provides.hooks.testing.pre_verifier.0 | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-95 | 95–95 | provides.phase_rules_overlays | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-96 | 96–96 | provides.phase_rules_overlays.spec | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-97 | 97–97 | provides.phase_rules_overlays.plan | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-98 | 98–98 | provides.phase_rules_overlays.coding | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-99 | 99–99 | provides.phase_rules_overlays.review | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-100 | 100–100 | provides.phase_rules_overlays.ut | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |
| P7a130749-101 | 101–101 | provides.phase_rules_overlays.testing | F4.1, F5.5, F6.4 | M22, M33, M35 | 按M22,M33,M35比较结论保留其必要职责 |

<a id="Pb04de125"></a>

## rules/coding-rules.overlay.yaml

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pb04de125-1 | 1–5 | 文件头/元信息 | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-6 | 6–6 | phase | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-7 | 7–7 | version | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-8 | 8–11 | semantic_checks | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-12 | 12–12 | semantic_checks.knowledge_must_carried | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-13 | 13–19 | semantic_checks.knowledge_must_carried.description | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-20 | 20–20 | semantic_checks.knowledge_must_carried.severity | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-21 | 21–35 | semantic_checks.knowledge_must_carried.ai_prompt_hint | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-36 | 36–36 | exploration_thresholds | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-37 | 37–37 | exploration_thresholds.phase_input_snippets_extra | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Pb04de125-38 | 38–38 | exploration_thresholds.phase_input_snippets_extra.0 | F4.6, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |

<a id="Paafa935f"></a>

## rules/plan-rules.overlay.yaml

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Paafa935f-1 | 1–5 | 文件头/元信息 | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-6 | 6–6 | phase | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-7 | 7–7 | version | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-8 | 8–8 | semantic_checks | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-9 | 9–9 | semantic_checks.knowledge_obligation_substance | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-10 | 10–18 | semantic_checks.knowledge_obligation_substance.description | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-19 | 19–19 | semantic_checks.knowledge_obligation_substance.severity | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-20 | 20–28 | semantic_checks.knowledge_obligation_substance.ai_prompt_hint | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-29 | 29–29 | semantic_checks.knowledge_facts_reuse | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-30 | 30–35 | semantic_checks.knowledge_facts_reuse.description | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-36 | 36–36 | semantic_checks.knowledge_facts_reuse.severity | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-37 | 37–42 | semantic_checks.knowledge_facts_reuse.ai_prompt_hint | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-43 | 43–43 | semantic_checks.review_gate_acknowledged | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-44 | 44–47 | semantic_checks.review_gate_acknowledged.description | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-48 | 48–48 | semantic_checks.review_gate_acknowledged.severity | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-49 | 49–62 | semantic_checks.review_gate_acknowledged.ai_prompt_hint | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-63 | 63–63 | exploration_thresholds | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-64 | 64–64 | exploration_thresholds.phase_input_snippets_extra | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |
| Paafa935f-65 | 65–65 | exploration_thresholds.phase_input_snippets_extra.0 | F4.5, F5.5 | M27, M33 | 按M27,M33比较结论保留其必要职责 |

<a id="P8820de89"></a>

## rules/review-rules.overlay.yaml

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P8820de89-1 | 1–5 | 文件头/元信息 | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-6 | 6–6 | phase | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-7 | 7–7 | version | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-8 | 8–8 | semantic_checks | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-9 | 9–9 | semantic_checks.knowledge_obligation_reviewed | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-10 | 10–15 | semantic_checks.knowledge_obligation_reviewed.description | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-16 | 16–16 | semantic_checks.knowledge_obligation_reviewed.severity | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-17 | 17–30 | semantic_checks.knowledge_obligation_reviewed.ai_prompt_hint | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-31 | 31–31 | exploration_thresholds | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-32 | 32–32 | exploration_thresholds.phase_input_snippets_extra | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |
| P8820de89-33 | 33–33 | exploration_thresholds.phase_input_snippets_extra.0 | F4.7, F5.5 | M28, M33 | 按M28,M33比较结论保留其必要职责 |

<a id="P4ccef0f2"></a>

## rules/spec-rules.overlay.yaml

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P4ccef0f2-1 | 1–2 | 文件头/元信息 | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-3 | 3–3 | phase | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-4 | 4–4 | version | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-5 | 5–5 | semantic_checks | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-6 | 6–6 | semantic_checks.knowledge_spec_exit_substance | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-7 | 7–14 | semantic_checks.knowledge_spec_exit_substance.description | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-15 | 15–15 | semantic_checks.knowledge_spec_exit_substance.severity | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-16 | 16–22 | semantic_checks.knowledge_spec_exit_substance.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-23 | 23–23 | semantic_checks.knowledge_candidates_registered | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-24 | 24–33 | semantic_checks.knowledge_candidates_registered.description | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-34 | 34–34 | semantic_checks.knowledge_candidates_registered.severity | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-35 | 35–42 | semantic_checks.knowledge_candidates_registered.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-43 | 43–43 | semantic_checks.spec_ext_conclusion_validity | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-44 | 44–50 | semantic_checks.spec_ext_conclusion_validity.description | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-51 | 51–51 | semantic_checks.spec_ext_conclusion_validity.severity | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-52 | 52–57 | semantic_checks.spec_ext_conclusion_validity.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-58 | 58–58 | semantic_checks.spec_ext_conclusion_validity.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按R16处理局部；不整块删 |
| P4ccef0f2-59 | 59–67 | semantic_checks.spec_ext_conclusion_validity.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-68 | 68–68 | semantic_checks.upstream_inputs_coverage | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-69 | 69–72 | semantic_checks.upstream_inputs_coverage.description | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-73 | 73–73 | semantic_checks.upstream_inputs_coverage.severity | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-74 | 74–81 | semantic_checks.upstream_inputs_coverage.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-82 | 82–82 | semantic_checks.split_boundary_consistency | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-83 | 83–88 | semantic_checks.split_boundary_consistency.description | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-89 | 89–89 | semantic_checks.split_boundary_consistency.severity | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-90 | 90–100 | semantic_checks.split_boundary_consistency.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-101 | 101–101 | semantic_checks.story_reader_review | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-102 | 102–120 | semantic_checks.story_reader_review.description | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-121 | 121–121 | semantic_checks.story_reader_review.severity | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-122 | 122–159 | semantic_checks.story_reader_review.ai_prompt_hint | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-160 | 160–160 | exploration_thresholds | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-161 | 161–161 | exploration_thresholds.phase_input_snippets_extra | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |
| P4ccef0f2-162 | 162–162 | exploration_thresholds.phase_input_snippets_extra.0 | F2.2, F4.3, F4.4, F5.3, F5.5 | M09, M10, M24, M25, M26, M32, M33 | 按M09,M10,M24,M25,M26,M32,M33比较结论保留其必要职责 |

<a id="Pa3bfe6c6"></a>

## rules/testing-rules.overlay.yaml

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pa3bfe6c6-1 | 1–5 | 文件头/元信息 | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| Pa3bfe6c6-6 | 6–6 | phase | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| Pa3bfe6c6-7 | 7–7 | version | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| Pa3bfe6c6-8 | 8–8 | semantic_checks | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| Pa3bfe6c6-9 | 9–9 | semantic_checks.knowledge_obligation_verified | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| Pa3bfe6c6-10 | 10–14 | semantic_checks.knowledge_obligation_verified.description | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| Pa3bfe6c6-15 | 15–15 | semantic_checks.knowledge_obligation_verified.severity | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| Pa3bfe6c6-16 | 16–22 | semantic_checks.knowledge_obligation_verified.ai_prompt_hint | F4.9, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |

<a id="P3bed6c8d"></a>

## rules/ut-rules.overlay.yaml

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P3bed6c8d-1 | 1–5 | 文件头/元信息 | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-6 | 6–6 | phase | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-7 | 7–7 | version | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-8 | 8–8 | semantic_checks | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-9 | 9–9 | semantic_checks.knowledge_obligation_verified | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-10 | 10–15 | semantic_checks.knowledge_obligation_verified.description | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-16 | 16–16 | semantic_checks.knowledge_obligation_verified.severity | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-17 | 17–31 | semantic_checks.knowledge_obligation_verified.ai_prompt_hint | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-32 | 32–32 | exploration_thresholds | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-33 | 33–33 | exploration_thresholds.phase_input_snippets_extra | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |
| P3bed6c8d-34 | 34–34 | exploration_thresholds.phase_input_snippets_extra.0 | F4.8, F5.5 | M29, M33 | 按M29,M33比较结论保留其必要职责 |

<a id="P1c4934f5"></a>

## skills/story/AGENTS.section.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P1c4934f5-1 | 1–3 | 文件头/元信息 | F5.1 | M30 | 按M30比较结论保留其必要职责 |
| P1c4934f5-4 | 4–7 | 前言 / - **需求流程入口**：&#96;/story &lt;init&#124;archive&#124;restore&#124;review&#124;adapt&#124;help&gt; &#91;AR编号&#93; | F5.1 | M30 | 按M30比较结论保留其必要职责 |

<a id="Pe4cb5df8"></a>

## skills/story/contracts/story-chapters.json

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pe4cb5df8-1 | 1–1 | 文件头/元信息 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-2 | 2–2 | version | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-3 | 3–3 | note | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-4 | 4–4 | skeleton_note | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-5 | 5–5 | sources_note | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-6 | 6–6 | sources | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-7 | 7–7 | sources.PRD | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-8 | 8–8 | sources.PRD.path | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-9 | 9–9 | sources.PRD.required | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-10 | 10–11 | sources.PRD.label | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-12 | 12–12 | sources.SE | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-13 | 13–13 | sources.SE.path | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-14 | 14–14 | sources.SE.required | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-15 | 15–16 | sources.SE.label | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-17 | 17–17 | sources.SPEC | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-18 | 18–18 | sources.SPEC.path | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-19 | 19–19 | sources.SPEC.required | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-20 | 20–21 | sources.SPEC.label | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-22 | 22–22 | sources.DESIGN | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-23 | 23–23 | sources.DESIGN.path | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-24 | 24–24 | sources.DESIGN.required | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-25 | 25–26 | sources.DESIGN.label | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-27 | 27–27 | sources.UPSTREAM | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-28 | 28–28 | sources.UPSTREAM.path | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-29 | 29–29 | sources.UPSTREAM.required | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-30 | 30–31 | sources.UPSTREAM.label | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-32 | 32–32 | sources.UX | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-33 | 33–33 | sources.UX.path | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-34 | 34–34 | sources.UX.required | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-35 | 35–37 | sources.UX.label | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-38 | 38–38 | chapters | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-39 | 39–39 | chapters.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-40 | 40–40 | chapters.0.id | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-41 | 41–41 | chapters.0.title | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-42 | 42–42 | chapters.0.questions | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-43 | 43–43 | chapters.0.questions.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-44 | 44–44 | chapters.0.questions.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-45 | 45–45 | chapters.0.questions.2 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-46 | 46–47 | chapters.0.questions.3 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-48 | 48–48 | chapters.0.form | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-49 | 49–51 | chapters.0.form.sections | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-52 | 52–52 | chapters.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-53 | 53–53 | chapters.1.id | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-54 | 54–54 | chapters.1.title | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-55 | 55–55 | chapters.1.questions | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-56 | 56–56 | chapters.1.questions.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-57 | 57–58 | chapters.1.questions.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-59 | 59–59 | chapters.1.form | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-60 | 60–60 | chapters.1.form.sections | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-61 | 61–61 | chapters.1.form.slots | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-62 | 62–65 | chapters.1.form.slots..table | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-66 | 66–66 | chapters.2 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-67 | 67–67 | chapters.2.id | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-68 | 68–68 | chapters.2.title | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-69 | 69–69 | chapters.2.subsections | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-70 | 70–71 | chapters.2.subsections.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-72 | 72–72 | chapters.2.subsections_note | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-73 | 73–73 | chapters.2.questions | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-74 | 74–74 | chapters.2.questions.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-75 | 75–75 | chapters.2.questions.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-76 | 76–76 | chapters.2.questions.2 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-77 | 77–78 | chapters.2.questions.3 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-79 | 79–79 | chapters.2.form | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-80 | 80–80 | chapters.2.form.sections | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-81 | 81–81 | chapters.2.form.slots | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-82 | 82–85 | chapters.2.form.slots.交接约定.when | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-86 | 86–86 | chapters.3 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-87 | 87–87 | chapters.3.id | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-88 | 88–88 | chapters.3.title | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-89 | 89–89 | chapters.3.questions | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-90 | 90–90 | chapters.3.questions.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-91 | 91–91 | chapters.3.questions.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-92 | 92–92 | chapters.3.questions.2 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-93 | 93–94 | chapters.3.questions.3 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-95 | 95–95 | chapters.3.subsections | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-96 | 96–97 | chapters.3.subsections.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-98 | 98–98 | chapters.3.subsections_note | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-99 | 99–99 | chapters.3.form | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-100 | 100–102 | chapters.3.form.sections | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-103 | 103–103 | chapters.4 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-104 | 104–104 | chapters.4.id | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-105 | 105–105 | chapters.4.title | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-106 | 106–106 | chapters.4.questions | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-107 | 107–107 | chapters.4.questions.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-108 | 108–108 | chapters.4.questions.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-109 | 109–110 | chapters.4.questions.2 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-111 | 111–111 | chapters.4.form | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-112 | 112–112 | chapters.4.form.sections | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-113 | 113–113 | chapters.4.form.slots | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-114 | 114–117 | chapters.4.form.slots..diagram | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-118 | 118–118 | chapters.5 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-119 | 119–119 | chapters.5.id | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-120 | 120–120 | chapters.5.title | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-121 | 121–121 | chapters.5.questions | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-122 | 122–122 | chapters.5.questions.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-123 | 123–123 | chapters.5.questions.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-124 | 124–125 | chapters.5.questions.2 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-126 | 126–126 | chapters.5.form | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-127 | 127–129 | chapters.5.form.sections | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-130 | 130–130 | chapters.6 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-131 | 131–131 | chapters.6.id | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-132 | 132–132 | chapters.6.title | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-133 | 133–133 | chapters.6.questions | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-134 | 134–134 | chapters.6.questions.0 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-135 | 135–136 | chapters.6.questions.1 | F2.4.1 | M15 | 按M15比较结论保留其必要职责 |
| Pe4cb5df8-137 | 137–137 | chapters.6.form | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-138 | 138–140 | chapters.6.form.sections | F2.4.1, F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| Pe4cb5df8-141 | 141–141 | chapters.7 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-142 | 142–142 | chapters.7.id | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-143 | 143–143 | chapters.7.title | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-144 | 144–144 | chapters.7.questions | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-145 | 145–145 | chapters.7.questions.0 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-146 | 146–146 | chapters.7.questions.1 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-147 | 147–148 | chapters.7.questions.2 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-149 | 149–149 | chapters.7.form | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-150 | 150–150 | chapters.7.form.sections | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-151 | 151–151 | chapters.7.form.slots | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-152 | 152–155 | chapters.7.form.slots..table | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-156 | 156–156 | chapters.8 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-157 | 157–157 | chapters.8.id | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-158 | 158–158 | chapters.8.title | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-159 | 159–159 | chapters.8.questions | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-160 | 160–160 | chapters.8.questions.0 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-161 | 161–161 | chapters.8.questions.1 | F2.4.3, F2.4.1 | M15, M38 | 按R21处理局部；不整块删 |
| Pe4cb5df8-162 | 162–163 | chapters.8.questions.2 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-164 | 164–164 | chapters.8.banned_terms_exempt | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-165 | 165–165 | chapters.8.banned_terms_note | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-166 | 166–166 | chapters.8.subsections | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-167 | 167–167 | chapters.8.subsections.0 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-168 | 168–169 | chapters.8.subsections.1 | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-170 | 170–170 | chapters.8.subsections_note | F2.4.3 | M15, M38 | 按M15,M38比较结论保留其必要职责 |
| Pe4cb5df8-171 | 171–171 | chapters.8.form | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-172 | 172–172 | chapters.8.form.sections | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-173 | 173–173 | chapters.8.form.slots | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-174 | 174–177 | chapters.8.form.slots.交付物.table | F2.4.3, F2.4.2 | M14, M15, M16, M38 | 按M14,M15,M16,M38比较结论保留其必要职责 |
| Pe4cb5df8-178 | 178–178 | chapters.9 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-179 | 179–179 | chapters.9.id | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-180 | 180–180 | chapters.9.title | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-181 | 181–181 | chapters.9.appendix | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-182 | 182–182 | chapters.9.subsections | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-183 | 183–183 | chapters.9.subsections.0 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-184 | 184–184 | chapters.9.subsections.1 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-185 | 185–185 | chapters.9.subsections.2 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-186 | 186–186 | chapters.9.subsections.3 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-187 | 187–188 | chapters.9.subsections.4 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-189 | 189–189 | chapters.9.questions | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-190 | 190–190 | chapters.9.questions.0 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-191 | 191–191 | chapters.9.questions.1 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-192 | 192–193 | chapters.9.questions.2 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-194 | 194–194 | chapters.9.subsections_note | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-195 | 195–195 | chapters.9.subsection_tables.改动边界 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-196 | 196–196 | chapters.9.subsection_tables_note | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-197 | 197–197 | chapters.9.subsection_form | F2.5, F2.4.2 | M14, M15, M16, M17, M18 | 按M14,M15,M16,M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-198 | 198–198 | chapters.9.subsection_form.applies_to | F2.5, F2.4.2 | M14, M15, M16, M17, M18 | 按M14,M15,M16,M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-199 | 199–199 | chapters.9.subsection_form.note | F2.5, F2.4.2, F2.6 | M14, M15, M16, M17, M18 | 按R15处理局部；不整块删 |
| Pe4cb5df8-200 | 200–200 | chapters.9.subsection_form.note | F2.5, F2.4.2, F2.6 | M14, M15, M16, M17, M18 | 按M14,M15,M16,M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-201 | 201–201 | chapters.9.form | F2.5, F2.4.2 | M14, M15, M16, M17, M18 | 按M14,M15,M16,M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-202 | 202–205 | chapters.9.form.sections | F2.5, F2.4.2 | M14, M15, M16, M17, M18 | 按M14,M15,M16,M17,M18比较结论保留其必要职责 |
| Pe4cb5df8-206 | 206–206 | id_shapes | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-207 | 207–207 | id_shapes._note | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-208 | 208–208 | id_shapes.keep | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-209 | 209–210 | id_shapes.keep.0 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-211 | 211–211 | id_shapes.drop | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-212 | 212–212 | id_shapes.drop.0 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-213 | 213–213 | id_shapes.drop.1 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-214 | 214–214 | id_shapes.drop.2 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-215 | 215–215 | id_shapes.drop.3 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-216 | 216–218 | id_shapes.drop.4 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-219 | 219–219 | language_redline | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-220 | 220–220 | language_redline._note | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-221 | 221–221 | language_redline.scope | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-222 | 222–222 | language_redline.kinds | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-223 | 223–223 | language_redline.kinds.0 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-224 | 224–224 | language_redline.kinds.1 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-225 | 225–225 | language_redline.kinds.2 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-226 | 226–226 | language_redline.kinds.2.kind | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-227 | 227–228 | language_redline.kinds.2.scope | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-229 | 229–229 | language_redline.kinds.3 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-230 | 230–230 | language_redline.kinds.4 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-231 | 231–231 | language_redline.kinds.5 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-232 | 232–232 | language_redline.kinds.6 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-233 | 233–233 | language_redline.kinds.7 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-234 | 234–234 | language_redline.kinds.7.kind | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-235 | 235–237 | language_redline.kinds.7.scope | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-238 | 238–238 | language_redline.harness_terms | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-239 | 239–239 | language_redline.harness_terms.0 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-240 | 240–240 | language_redline.harness_terms.1 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-241 | 241–241 | language_redline.harness_terms.2 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-242 | 242–242 | language_redline.harness_terms.3 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-243 | 243–243 | language_redline.harness_terms.4 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-244 | 244–244 | language_redline.harness_terms.5 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-245 | 245–245 | language_redline.harness_terms.6 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-246 | 246–246 | language_redline.harness_terms.7 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-247 | 247–247 | language_redline.harness_terms.8 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-248 | 248–248 | language_redline.harness_terms.9 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-249 | 249–249 | language_redline.harness_terms.10 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-250 | 250–250 | language_redline.harness_terms.11 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-251 | 251–251 | language_redline.harness_terms.12 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-252 | 252–252 | language_redline.harness_terms.13 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-253 | 253–253 | language_redline.harness_terms.14 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-254 | 254–254 | language_redline.harness_terms.15 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-255 | 255–255 | language_redline.harness_terms.16 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-256 | 256–256 | language_redline.harness_terms.17 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-257 | 257–257 | language_redline.harness_terms.18 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-258 | 258–258 | language_redline.harness_terms.19 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-259 | 259–260 | language_redline.harness_terms.20 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-261 | 261–261 | language_redline.client_vocabulary_note | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-262 | 262–262 | language_redline.client_vocabulary | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-263 | 263–263 | language_redline.client_vocabulary.0 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-264 | 264–264 | language_redline.client_vocabulary.0.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-265 | 265–266 | language_redline.client_vocabulary.0.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-267 | 267–267 | language_redline.client_vocabulary.1 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-268 | 268–268 | language_redline.client_vocabulary.1.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-269 | 269–270 | language_redline.client_vocabulary.1.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-271 | 271–271 | language_redline.client_vocabulary.2 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-272 | 272–272 | language_redline.client_vocabulary.2.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-273 | 273–274 | language_redline.client_vocabulary.2.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-275 | 275–275 | language_redline.client_vocabulary.3 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-276 | 276–276 | language_redline.client_vocabulary.3.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-277 | 277–278 | language_redline.client_vocabulary.3.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-279 | 279–279 | language_redline.client_vocabulary.4 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-280 | 280–280 | language_redline.client_vocabulary.4.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-281 | 281–282 | language_redline.client_vocabulary.4.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-283 | 283–283 | language_redline.client_vocabulary.5 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-284 | 284–284 | language_redline.client_vocabulary.5.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-285 | 285–286 | language_redline.client_vocabulary.5.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-287 | 287–287 | language_redline.client_vocabulary.6 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-288 | 288–288 | language_redline.client_vocabulary.6.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-289 | 289–290 | language_redline.client_vocabulary.6.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-291 | 291–291 | language_redline.client_vocabulary.7 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-292 | 292–292 | language_redline.client_vocabulary.7.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-293 | 293–294 | language_redline.client_vocabulary.7.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-295 | 295–295 | language_redline.client_vocabulary.8 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-296 | 296–296 | language_redline.client_vocabulary.8.term | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-297 | 297–300 | language_redline.client_vocabulary.8.hint | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-301 | 301–301 | verdicts | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-302 | 302–302 | verdicts._note | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-303 | 303–303 | verdicts.chapter_dimensions | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-304 | 304–304 | verdicts.chapter_dimensions.0 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-305 | 305–305 | verdicts.chapter_dimensions.1 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-306 | 306–306 | verdicts.chapter_dimensions.2 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-307 | 307–307 | verdicts.chapter_dimensions.3 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-308 | 308–308 | verdicts.chapter_dimensions.4 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-309 | 309–309 | verdicts.chapter_dimensions.5 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-310 | 310–310 | verdicts.chapter_dimensions.6 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-311 | 311–313 | verdicts.chapter_dimensions.7 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-314 | 314–314 | decision_categories | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-315 | 315–315 | decision_categories.0 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-316 | 316–316 | decision_categories.0.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-317 | 317–318 | decision_categories.0.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-319 | 319–319 | decision_categories.1 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-320 | 320–320 | decision_categories.1.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-321 | 321–322 | decision_categories.1.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-323 | 323–323 | decision_categories.2 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-324 | 324–324 | decision_categories.2.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-325 | 325–325 | decision_categories.2.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-326 | 326–326 | decision_categories.2.banned_terms_exempt | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-327 | 327–328 | decision_categories.2.banned_terms_note | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-329 | 329–329 | decision_categories.3 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-330 | 330–330 | decision_categories.3.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-331 | 331–332 | decision_categories.3.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-333 | 333–333 | decision_categories.4 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-334 | 334–334 | decision_categories.4.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-335 | 335–336 | decision_categories.4.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-337 | 337–337 | decision_categories.5 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-338 | 338–338 | decision_categories.5.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-339 | 339–340 | decision_categories.5.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-341 | 341–341 | decision_categories.6 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-342 | 342–342 | decision_categories.6.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-343 | 343–344 | decision_categories.6.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-345 | 345–345 | decision_categories.7 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-346 | 346–346 | decision_categories.7.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-347 | 347–348 | decision_categories.7.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-349 | 349–349 | decision_categories.8 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-350 | 350–350 | decision_categories.8.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-351 | 351–352 | decision_categories.8.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-353 | 353–353 | decision_categories.9 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-354 | 354–354 | decision_categories.9.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-355 | 355–355 | decision_categories.9.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-356 | 356–356 | decision_categories.9.banned_terms_exempt | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-357 | 357–358 | decision_categories.9.banned_terms_note | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-359 | 359–359 | decision_categories.10 | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-360 | 360–360 | decision_categories.10.key | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-361 | 361–363 | decision_categories.10.section | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-364 | 364–364 | decision_categories_note | F3.1, F5.5 | M20, M33 | 按M20,M33比较结论保留其必要职责 |
| Pe4cb5df8-365 | 365–365 | gates | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pe4cb5df8-366 | 366–366 | gates.material_scope | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pe4cb5df8-367 | 367–367 | gates.material_scope.options | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pe4cb5df8-368 | 368–368 | gates.material_scope.options.0.request | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pe4cb5df8-369 | 369–372 | gates.material_scope.options.1.label | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pe4cb5df8-373 | 373–373 | gates_note | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pe4cb5df8-374 | 374–374 | material_dirs | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-375 | 375–375 | material_dirs.0 | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-376 | 376–376 | material_dirs.1 | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-377 | 377–377 | material_dirs.2 | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-378 | 378–379 | material_dirs.3 | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-380 | 380–380 | material_dirs_note | F1.3, F2.1 | M03, M07, M08 | 按M03,M07,M08比较结论保留其必要职责 |
| Pe4cb5df8-381 | 381–381 | story_image_dir | F1.3, F2.1, F2.6 | M03, M07, M08 | 按R11处理局部；不整块删 |
| Pe4cb5df8-382 | 382–382 | story_image_dir_note | F1.3, F2.1, F2.6 | M03, M07, M08 | 按R11处理局部；不整块删 |
| Pe4cb5df8-383 | 383–383 | heading_counters | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-384 | 384–384 | heading_counters.0 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-385 | 385–385 | heading_counters.1 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-386 | 386–386 | heading_counters.2 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-387 | 387–387 | heading_counters.3 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-388 | 388–388 | heading_counters.4 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-389 | 389–389 | heading_counters.5 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-390 | 390–390 | heading_counters.6 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-391 | 391–391 | heading_counters.7 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-392 | 392–392 | heading_counters.8 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-393 | 393–393 | heading_counters.9 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-394 | 394–394 | heading_counters.10 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-395 | 395–395 | heading_counters.11 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-396 | 396–396 | heading_counters.12 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-397 | 397–397 | heading_counters.13 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-398 | 398–398 | heading_counters.14 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-399 | 399–399 | heading_counters.15 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-400 | 400–400 | heading_counters.16 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-401 | 401–401 | heading_counters.17 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-402 | 402–402 | heading_counters.18 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-403 | 403–403 | heading_counters.19 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-404 | 404–404 | heading_counters.20 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-405 | 405–405 | heading_counters.21 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-406 | 406–406 | heading_counters.22 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-407 | 407–407 | heading_counters.23 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-408 | 408–408 | heading_counters.24 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-409 | 409–409 | heading_counters.25 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-410 | 410–410 | heading_counters.26 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-411 | 411–411 | heading_counters.27 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-412 | 412–413 | heading_counters.28 | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-414 | 414–414 | heading_counters_note | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |
| Pe4cb5df8-415 | 415–416 | form_note | F2.6, F7.1 | M19, M36 | 按M19,M36比较结论保留其必要职责 |

<a id="P57e420ad"></a>

## skills/story/phases/spec.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P57e420ad-1 | 1–2 | &#96;/story&#96; 链 · spec 阶段作业包 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-3 | 3–6 | &#96;/story&#96; 链 · spec 阶段作业包 / &gt; 从 &#96;/story&#96; 链进入 spec 阶段时读这一页。扩展对 spec 的通用要求见 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-7 | 7–8 | 一、上游输入必读 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-9 | 9–10 | 一、上游输入必读 / 正文生成前必须读下面三份（存在时），并在 &#96;spec/context-exploration.md&#96; 的 &#96;key_inputs_rea | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-11 | 11–16 | 一、上游输入必读 / &#124; 文件 &#124; 是什么 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-17 | 17–23 | 一、上游输入必读 / **「本 AR 范围与拆分说明」是 Scope 与功能清单的边界依据**：该节含拆分表时，表里归**兄弟 AR | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-24 | 24–25 | 二、本阶段产出三份文档 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-26 | 26–27 | 二、本阶段产出三份文档 / spec 阶段是**一次 pass 产出三份**，作者与读者各不相同，事实同源，不得只交 &#96;spec.md&#96; 就宣告闭环： | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-28 | 28–33 | 二、本阶段产出三份文档 / &#124; 产物 &#124; 作者 &#124; 持有什么 &#124; 读者 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-34 | 34–41 | 二、本阶段产出三份文档 / - &#96;AR/review.md&#96; **由 &#96;AR/story-src/decisions.json&#96; 渲染，不手写**：AI 负责把每条 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-42 | 42–45 | 二、本阶段产出三份文档 / **story 不是 spec 的排版件**：spec 的可标识事实、PRD 的业务语境、SE 的全局方案，以及无编号的 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-46 | 46–47 | 阶段内顺序（story 在这里成文，不另起一步） | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-48 | 48–51 | 阶段内顺序（story 在这里成文，不另起一步） / &#96;spec.md&#96; 与 &#96;decisions.json&#96; **定稿之后**、跑 harness **之前**，按下面七步走完。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-52 | 52–70 | 阶段内顺序（story 在这里成文，不另起一步） / 示例或代码块 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-71 | 71–104 | 阶段内顺序（story 在这里成文，不另起一步） / - **④b 是唯一一次通读全篇**：③④ 把整篇切成十次有界的小任务，代价就是没有人从头读到尾—— | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-105 | 105–106 | 三、§9 技术契约怎么写 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-107 | 107–110 | 三、§9 技术契约怎么写 / core spec 模板缺少交付流程要求 spec 承载的接口契约 / 存储 / 配置 / 埋点 / 依赖，所以在 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-111 | 111–114 | 三、§9 技术契约怎么写 / **形式一律表格，不按条目数切换**：每个小节要么是一张表（表头固定、每行一个编号实体、 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-115 | 115–116 | 三、§9 技术契约怎么写 / 写之前先读**两份**——「方法 + 数据」缺一不可： | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-117 | 117–121 | 三、§9 技术契约怎么写 / &#124; 读什么 &#124; 给你什么 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-122 | 122–125 | 三、§9 技术契约怎么写 / **代码库现状**（仓内文件路径、检索零命中结论）是结论的一部分，作为表格的一列写进正文—— | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-126 | 126–129 | 三、§9 技术契约怎么写 / **防重复**：写之前先查 spec 已有章节，同一件事只写一处。加密 / 脱敏 / 调用方校验归 §7.3； | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-130 | 130–131 | 四、闭环后的下一步 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-132 | 132–135 | 四、闭环后的下一步 / **交付门通过之后停下问一次**（成文登记不是闭环——那时 harness、verifier、交付门 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-136 | 136–139 | 四、闭环后的下一步 / &#96;AR/review.md&#96; 是首版草稿，请开发按其中议题逐条审核并写下意见； | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P57e420ad-140 | 140–142 | 四、闭环后的下一步 / **两条互不阻塞，指的是可以并行开始，不是下游可以不管上游变更**：选了 plan 之后 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |

<a id="P3907448a"></a>

## skills/story/phases/story-write.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P3907448a-1 | 1–2 | story 成文（四步：初筛 → 整篇编排 → 按编排成文 → 写后核对） | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-3 | 3–5 | story 成文（四步：初筛 → 整篇编排 → 按编排成文 → 写后核对） / 读者是评审人：他们没参与开发，只有这一份文档，要据此判断 | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-6 | 6–7 | 写给这样的读者，意味着什么（十条，写之前读一遍） | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-8 | 8–25 | 写给这样的读者，意味着什么（十条，写之前读一遍） / - Story 面向**第一次接触需求**的人类评审者，他无需先读规格、产品需求、系统设计或代码。 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-26 | 26–27 | 写给这样的读者，意味着什么（十条，写之前读一遍） / 成文分四步： | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-28 | 28–34 | 写给这样的读者，意味着什么（十条，写之前读一遍） / 示例或代码块 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-35 | 35–37 | 写给这样的读者，意味着什么（十条，写之前读一遍） / **为什么不是「一次写完整篇」**：整篇是全有或全无——中途断了，磁盘上什么都没有， | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-38 | 38–40 | 写给这样的读者，意味着什么（十条，写之前读一遍） / **为什么先编排一次**：十章各自重新决定同一项业务，同一件事就会在三章各讲一遍， | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-41 | 41–44 | 写给这样的读者，意味着什么（十条，写之前读一遍） / **编排不是「先分配」。** 它不是给每个材料单元定一个落点、落成一份账再照着写—— | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-45 | 45–46 | 写给这样的读者，意味着什么（十条，写之前读一遍） / --- | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-47 | 47–48 | 第一步 · 初筛（进 spec 之前） | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-49 | 49–50 | 第一步 · 初筛（进 spec 之前） / S4 收口之后、进 /spec 之前，跑一次 | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-51 | 51–54 | 第一步 · 初筛（进 spec 之前） / 示例或代码块 | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-55 | 55–57 | 第一步 · 初筛（进 spec 之前） / 它把原材料切成可引用的内容单元，给出每段的 ID、标题路径与行范围， | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-58 | 58–62 | 第一步 · 初筛（进 spec 之前） / **按它 INPUT 列的位置读原文**，把此刻已经有的初步判断写进那份初筛表： | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-63 | 63–65 | 第一步 · 初筛（进 spec 之前） / 真实的业务未决当场登记进 &#96;decisions.json&#96; 并在那一项里引用它的 ID： | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-66 | 66–68 | 第一步 · 初筛（进 spec 之前） / 这一遍**不写业务方案**，也不必为了填满而给每一段都下判断。它要留住的是 | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-69 | 69–70 | 第一步 · 初筛（进 spec 之前） / --- | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-71 | 71–72 | 第二步 · 整篇编排（Spec 之后） | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-73 | 73–74 | 第二步 · 整篇编排（Spec 之后） / &#96;spec.md&#96; 正文、&#96;knowledge-use.yaml&#96; 与验收草稿都形成之后、跑 harness 之前，先跑 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-75 | 75–78 | 第二步 · 整篇编排（Spec 之后） / 示例或代码块 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-79 | 79–80 | 第二步 · 整篇编排（Spec 之后） / 它把本轮规格并进来源索引，并起头 &#96;AR/story-src/story-template.md&#96;——一份需求一份写作设计。 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-81 | 81–82 | 第二步 · 整篇编排（Spec 之后） / **这一次要做三件事，做完再动笔：** | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-83 | 83–85 | 第二步 · 整篇编排（Spec 之后） / **一、对照原材料、初筛、Spec 与决策，找出新增结论、冲突与遗漏。** 原材料里的义务不会 | F2.1 | M07, M08 | 按M07,M08比较结论保留其必要职责 |
| P3907448a-86 | 86–89 | 第二步 · 整篇编排（Spec 之后） / **二、把已有的可靠结论保存下来，把还要讲清的关系识别出来**：参与方、对象、规则、交接、 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-90 | 90–90 | 第二步 · 整篇编排（Spec 之后） / **三、给出整篇的阅读主线、主要解释位置与形式建议。** 多方调用优先解释调用与返回， | F2.2, F2.4.1, F2.4.3 | M09, M10 | 按R21处理局部；不整块删 |
| P3907448a-91 | 91–93 | 第二步 · 整篇编排（Spec 之后） / **三、给出整篇的阅读主线、主要解释位置与形式建议。** 多方调用优先解释调用与返回， | F2.2, F2.4.1, F2.4.3 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-94 | 94–96 | 第二步 · 整篇编排（Spec 之后） / 最后回到原始来源核一遍：重要的业务要求有没有具体的解释位置，尤其是混合用途的那些段落、 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-97 | 97–98 | 编排调整规则（后面几段都引它，不另说一遍） | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-99 | 99–104 | 编排调整规则（后面几段都引它，不另说一遍） / - 有依据的表达深化、分节与措辞，**直接改稿**，不必先回来改编排； | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-105 | 105–106 | 编排调整规则（后面几段都引它，不另说一遍） / --- | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-107 | 107–108 | 动笔前 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-109 | 109–113 | 动笔前 / 上游画过的图、本轮激活的知识、词表在**本阶段任务包**里，不必边写边找。 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-114 | 114–115 | 动笔前 / 未定的判断只作边界，正文里不替它下结论。 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-116 | 116–119 | 动笔前 / **叙述不落附录**。附录是查阅件：读者顺着正文读下来要能读懂这件事， | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| P3907448a-120 | 120–120 | 动笔前 / **同一件事在多份材料里出现，正文只讲一次**——选它最该待的那一章讲透，别在两章各写一遍。 | F2.4, F2.4.1, F2.6, F2.4.2 | M13, M15, M19 | 按R14处理局部；不整块删 |
| P3907448a-121 | 121–121 | 动笔前 / **同一件事在多份材料里出现，正文只讲一次**——选它最该待的那一章讲透，别在两章各写一遍。 | F2.4, F2.4.1, F2.6, F2.4.2 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-122 | 122–123 | 动笔前 / --- | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-124 | 124–125 | 决策登记 | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-126 | 126–134 | 决策登记 / **什么算一条议题**：review 是**判断的台账**——已决策的呈现结果供评审人过目， | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-135 | 135–137 | 决策登记 / **找议题时对着这十一类过一遍**（类型即登记表的 &#96;category&#96;，也决定它在评审记录里成哪一节）。 | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-138 | 138–152 | 决策登记 / &#124; 类型 &#124; 读到什么就检查 &#124; 对号入座的问题 &#124; | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-153 | 153–159 | 决策登记 / **已定的决策写进它的取舍位置**。理由材料里本来就没有，是起草时判出来的， | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-160 | 160–161 | 决策登记 / --- | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-162 | 162–163 | 第三步 · 按编排成文 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-164 | 164–165 | 第三步 · 按编排成文 / **先建材料视图与草稿**： | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-166 | 166–171 | 第三步 · 按编排成文 / 示例或代码块 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-172 | 172–173 | 第三步 · 按编排成文 / &#96;skeleton&#96; 按当前编排铺两样东西，**已有的草稿一个字节不碰**： | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-174 | 174–179 | 第三步 · 按编排成文 / - &#96;AR/story-src/chapters/&lt;章ID&gt;.md&#96;——**这一章的工作输入**：本 AR 当前承载什么、 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-180 | 180–182 | 第三步 · 按编排成文 / **材料视图是工作输入，不是内容上限。** 写到需要的东西不在里面，从来源目录直读原件； | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-183 | 183–186 | 第三步 · 按编排成文 / **落盘只有 &#96;chapter&#96; 这一条路，不要自己去改 &#96;AR/story.md&#96;。** 命令替换的区间就是那一章， | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-187 | 187–188 | 第三步 · 按编排成文 / 中断之后从哪续问 &#96;prepare&#96;：它按磁盘上有什么回答下一个动作与要读的位置，**不改任何文件**。 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-189 | 189–197 | 第三步 · 按编排成文 / &#124; 输入 &#124; 拿它做什么 &#124; | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-198 | 198–201 | 第三步 · 按编排成文 / 写完这一章就跑一次 &#96;chapter&#96; 落盘，再写下一章。**篇幅由内容定**： | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-202 | 202–203 | 怎么写一章 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-204 | 204–207 | 怎么写一章 / **写给人读，不是把材料列成条目。** 材料是**素材**，不是提纲—— | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-208 | 208–208 | 怎么写一章 / - **表格转成散文时，每一列都要有落点**——最容易丢的正是非首列：触发条件、字段名、编号； | F2.4.2, F2.3, F5.1 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-209 | 209–213 | 怎么写一章 / - **表格转成散文时，每一列都要有落点**——最容易丢的正是非首列：触发条件、字段名、编号； | F2.4.2, F2.3, F5.1 | M14, M15, M16 | 按R10处理局部；不整块删 |
| P3907448a-214 | 214–217 | 怎么写一章 / - **表格转成散文时，每一列都要有落点**——最容易丢的正是非首列：触发条件、字段名、编号； | F2.4.2, F2.3, F5.1 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-218 | 218–222 | 怎么写一章 / 示例或代码块 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-223 | 223–239 | 怎么写一章 / 登记完就不必在正文里交代它了。理由跟着图的内容走，改名或复制到第二个落点都还在； | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-240 | 240–242 | 怎么写一章 / **空章**：确实不涉及的章，正文恰好写「本需求不涉及。」一句。 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-243 | 243–244 | 决策登记的澄清正文 | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-245 | 245–248 | 决策登记的澄清正文 / 三段式，小标题写成**加粗段首**（不用 &#96;#&#96; 标题行——议题在 review.md 里已有三级层次， | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-249 | 249–253 | 决策登记的澄清正文 / &#124; status &#124; 三段 &#124; | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-254 | 254–256 | 决策登记的澄清正文 / **「根据」必须指名材料或核查**：哪份稿的哪一节怎么说的、查了工程的什么。 | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-257 | 257–259 | 决策登记的澄清正文 / 标题写成陈述句：已定的陈述结论（「两块能力由本单一次交付」）， | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-260 | 260–261 | 什么内容用什么形态 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-262 | 262–266 | 什么内容用什么形态 / **先比一遍已经讲过的**：材料视图末尾的「与某章：某某」列着这一章与哪几章互补、 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-267 | 267–269 | 什么内容用什么形态 / **每句结论都指得出依据**：既有能力的依据是工程现状，本轮要新建的依据是已确认的需求与设计， | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-270 | 270–271 | 什么内容用什么形态 / **形式由内容的关系定，不由章号定。** 四步，写每一段之前过一遍： | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-272 | 272–274 | 什么内容用什么形态 / 1. **读者在这里要理解或判断什么**——它归哪一章，就在那一章讲透。 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-275 | 275–286 | 什么内容用什么形态 / &#124; 内容的关系 &#124; 表达 &#124; | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-287 | 287–292 | 什么内容用什么形态 / 3. **按复杂度决定分不分层**：简单的短写，一段说清就不建表；复杂的先给总览再展开局部， | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-293 | 293–297 | 什么内容用什么形态 / **必要结构上面列着**，缺了读者拿不到凭据，表头已经搭好，你在上面填。除此之外没有配额： | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-298 | 298–300 | 什么内容用什么形态 / **源材料里是图的，到这里还得是图**：把流程图压成「A → B → C」这样的箭头文字、 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-301 | 301–302 | 哪种图讲什么 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-303 | 303–305 | 哪种图讲什么 / &#124; 图 &#124; 讲什么 &#124; 什么时候用 &#124; | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-306 | 306–306 | R02 / &#124; 时序图 sequenceDiagram &#124; 多方之间谁先调谁、回什么 &#124; 参与方三个以上且交互顺序本身是要审的内容（如鉴权必须在创建之前 | F2.4.2 | M14, M15, M16 | 按R02处理局部；不整块删 |
| P3907448a-307 | 307–310 | R02 / &#124; 时序图 sequenceDiagram &#124; 多方之间谁先调谁、回什么 &#124; 参与方三个以上且交互顺序本身是要审的内容（如鉴权必须在创建之前 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-311 | 311–318 | 哪种图讲什么 / 1. 业务流程章**章首一张完整的图**，覆盖主路径与全部分支去向。零散的三四张小图不如 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-319 | 319–319 | 哪种图讲什么 / **章首那张图讲给评审者的是什么**——按内容在三种里选一种。 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-320 | 320–320 | R02 / **画哪种在动笔前就定得下来，看第 4 章列了几个参与方**：三个以上， | F2.4, F2.4.1, F2.6, F2.4.2 | M13, M14, M15, M16, M19 | 按R02处理局部；不整块删 |
| P3907448a-321 | 321–321 | R02 / 画时序图或泳道图，讲清谁先调谁、结果回到谁；两个以内，画流程图或状态图。 | F2.4.2 | M14, M15, M16 | 按R02处理局部；不整块删 |
| P3907448a-322 | 322–323 | R02 / 画时序图或泳道图，讲清谁先调谁、结果回到谁；两个以内，画流程图或状态图。 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-324 | 324–327 | 哪种图讲什么 / - **端到端旅程**：用户、本部件、云侧各自在这条业务里做什么，一步接一步走到终态 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-328 | 328–328 | R02 / - **谁先调谁**：参与方三个以上、顺序本身是要审的内容时（时序图）。 | F2.4.2 | M14, M15, M16 | 按R02处理局部；不整块删 |
| P3907448a-329 | 329–329 | R02 / - **谁先调谁**：参与方三个以上、顺序本身是要审的内容时（时序图）。 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-330 | 330–334 | 哪种图讲什么 / 上游画的那几张讲的是接口与分支，视角是契约。**两者可以是同一张，也可以不是**—— | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-335 | 335–339 | 哪种图讲什么 / **「上游那张在 story 有对应」的含义是标记指向它**，不是照抄。同一件事在两份上游 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-340 | 340–341 | 机器不判、要你自己把关的几条 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-342 | 342–342 | 机器不判、要你自己把关的几条 / - **表**：表前一句引导，说清这张表给你看什么（整章就是一张表的除外）； | F2.4.2, F2.4.1 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-343 | 343–343 | 机器不判、要你自己把关的几条 / - **表**：表前一句引导，说清这张表给你看什么（整章就是一张表的除外）； | F2.4.2, F2.4.1 | M14, M15, M16 | 按R14处理局部；不整块删 |
| P3907448a-344 | 344–353 | 机器不判、要你自己把关的几条 / - **表**：表前一句引导，说清这张表给你看什么（整章就是一张表的除外）； | F2.4.2, F2.4.1 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-354 | 354–355 | 别写成长文 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-356 | 356–356 | 别写成长文 / **段落以百字上下为宜**，超过一百六十字就该动手：拆开、改成列表或表、 | F2.4.2, F2.4.1 | M14, M15, M16 | 按R14处理局部；不整块删 |
| P3907448a-357 | 357–360 | 别写成长文 / **段落以百字上下为宜**，超过一百六十字就该动手：拆开、改成列表或表、 | F2.4.2, F2.4.1 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-361 | 361–364 | 别写成长文 / **拆开之后要换形态**：把一个 200 字的长段拆成三个 120 字的段连排，读起来还是一堵墙， | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-365 | 365–367 | 别写成长文 / **没有句子长度限制**。中文里 45–60 字的完整复句很常见，为了凑短而在逗号处断开， | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-368 | 368–369 | 归档件自包含（四条红线） | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-370 | 370–371 | 归档件自包含（四条红线） / 这份文档会被上传到需求系统，读者手上没有这个仓库： | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-372 | 372–379 | 归档件自包含（四条红线） / 1. 不写仓内路径（需求目录、模块目录名）——读者打不开。**唯一的例外是附录材料清单里的 | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| P3907448a-380 | 380–384 | 归档件自包含（四条红线） / **需求不是演示。** 工程当前可能用本地或模拟的方式承载某些能力（云侧还没接、 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-385 | 385–387 | 归档件自包含（四条红线） / 这一条不设词表——「演示」是常用词，机器拦它会误伤（「演示视频」「向客户演示」 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-388 | 388–389 | 归档件自包含（四条红线） / --- | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-390 | 390–391 | 第四步 · 写后核对 | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-392 | 392–395 | 第四步 · 写后核对 / 逐章成文是十次各自有界的小任务，这是它的代价：**没有任何一步是通读全篇的**。 | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-396 | 396–399 | 第四步 · 写后核对 / 写完最后一章之后，**读当前完整的一篇、整篇写作设计与本次的来源与决策**，做下面四个动作。 | F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P3907448a-400 | 400–403 | 第四步 · 写后核对 / 与第二步的分工是清楚的：**编排时保存已知义务与要解释的关系，这里从来源、编排与新认识 | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-404 | 404–410 | 第四步 · 写后核对 / **一、回到来源核落点。** 打开来源目录，对着原文逐项问：这一段原始义务与已定判断， | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-411 | 411–418 | 第四步 · 写后核对 / **二、比较信息归属。** 对同一件事在多处的叙述，逐处问它有没有别处没有的信息。 | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-419 | 419–429 | 第四步 · 写后核对 / **三、推演关系与结果。** 从已确认的范围与依据出发，把关键流程逐条推一遍： | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-430 | 430–437 | 第四步 · 写后核对 / **四、核重组之后的表达。** 指代指得准吗、单位与数值一致吗、因果说得通吗、 | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P3907448a-438 | 438–441 | 第四步 · 写后核对 / **发现问题回哪里，按「编排调整规则」**：业务根因回 Spec 或 decisions， | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P3907448a-442 | 442–446 | 第四步 · 写后核对 / 改的时候仍然一章一章改：在那一章的草稿上改，再跑一次 | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-447 | 447–448 | 第四步 · 写后核对 / 改完重跑一次 &#96;check&#96;——核对动了正文，确定性判据要跟着重核。 | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-449 | 449–450 | 第四步 · 写后核对 / --- | F2.7 | M38 | 按M38比较结论保留其必要职责 |
| P3907448a-451 | 451–452 | 交回前 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-453 | 453–454 | 交回前 / 全部章都渲染完之后跑： | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-455 | 455–458 | 交回前 / 示例或代码块 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-459 | 459–460 | 交回前 / 判据全过才算完。**check 没过就别交。** | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-461 | 461–463 | 交回前 / 报错说的是**这一类事实的落点长什么样**，不是一张待抄的字面清单—— | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-464 | 464–465 | 叙述是你自己的 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-466 | 466–471 | 叙述是你自己的 / 顺序服务于人的理解——先为什么 → 再是什么 → 再怎么做 → 再哪里会坏 → 最后怎么算做对。 | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |
| P3907448a-472 | 472–475 | 叙述是你自己的 / 理由是 story 存在的意义——规格只有结论。**只复述效果的不算理由**： | F2.4, F2.4.1, F2.6 | M13, M15, M19 | 按M13,M15,M19比较结论保留其必要职责 |

<a id="P73dcd951"></a>

## skills/story/reference/evidence-rules.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P73dcd951-1 | 1–2 | spec 取证规则 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-3 | 3–5 | spec 取证规则 / spec 技术契约章每条结论的**唯一合法产出方式**：信息源 → 提取步骤 → 输出规则。 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-6 | 6–7 | 1. 核心公式 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-8 | 8–9 | 1. 核心公式 / &gt; **事实 = 变更意图 × 代码库现状** | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-10 | 10–13 | 1. 核心公式 / 变更意图从 AR / SR / RR 与 spec 前几章来；**现状先看激活清单里的项目知识**（有什么、叫什么、在哪）， | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-14 | 14–16 | 1. 核心公式 / **现状不能用平台常识顶替**：某个 API 在别的工程常见，不等于本工程在用； | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-17 | 17–18 | 2. 信息源总表 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-19 | 19–20 | 变更意图 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-21 | 21–27 | 变更意图 / &#124; 源 &#124; 用途 &#124; 缺失时 &#124; | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-28 | 28–29 | 代码库现状 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-30 | 30–38 | 代码库现状 / &#124; 源 &#124; 用途 &#124; | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-39 | 39–40 | 3. 各节取证 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-41 | 41–45 | 3. 各节取证 / **现状怎么取（三步，各节通用）**：① 先查项目知识有没有登记该类能力的既有实现，有就照它写； | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-46 | 46–51 | 端云接口 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-52 | 52–57 | 数据存储 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-58 | 58–63 | 配置项 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-64 | 64–69 | 埋点 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-70 | 70–74 | 依赖变更 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-75 | 75–76 | 4. 结论写法 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-77 | 77–78 | 4. 结论写法 / 取证是**生成过程**，产物是一条具体、可回查的结论——不是一条结论加一个出处坐标。 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-79 | 79–80 | 4.1 具体到可按名回查 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-81 | 81–82 | 4.1 具体到可按名回查 / 每条结论写全它谈论的那个东西的名字：接口名、存储键、事件名、配置项名、模块名、错误码、路由名。 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-83 | 83–88 | 4.1 具体到可按名回查 / &#124; 反例（空话，无从核对） &#124; 正例（可按名回查） &#124; | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-89 | 89–91 | 4.1 具体到可按名回查 / 名字写全了，verifier 与证据抽查关卡才能按名搜遍 spec / SR / RR / 代码去核对。 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-92 | 92–93 | 4.2 三类必须写进结论的信息 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-94 | 94–99 | 4.2 三类必须写进结论的信息 / &#124; 类别 &#124; 怎么写 &#124; | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-100 | 100–101 | 4.2 三类必须写进结论的信息 / **story 侧不同**：归档件里数值不带来源括注——来源由 spec 承担，可议的值登记决策件后在正文引用。 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-102 | 102–103 | 4.3 不写的东西 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |
| P73dcd951-104 | 104–106 | 4.3 不写的东西 / **文档坐标**（&#96;spec §x&#96; / &#96;SR §x&#96; / &#96;RR §x&#96; / &#96;AR §x&#96;）与**小节互指**（&#96;见 A5&#96;）一律 | F2.2, F4.3, F5.5 | M09, M10, M24, M25, M33 | 按M09,M10,M24,M25,M33比较结论保留其必要职责 |

<a id="Pacd7f161"></a>

## skills/story/rules/ar_design_init.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pacd7f161-1 | 1–2 | ar_design_init — AR 提取稿的生成规则 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-3 | 3–6 | ar_design_init — AR 提取稿的生成规则 / 从上游材料提取，写成 &#96;AR/story-src/design-draft.md&#96;，再由 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-7 | 7–11 | ar_design_init — AR 提取稿的生成规则 / **你写提取稿，覆盖由收口那一步做**：&#96;AR/design.md&#96; 是上游给进来的输入件，也是一份登记 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-12 | 12–13 | ar_design_init — AR 提取稿的生成规则 / **输入四源**（存在即读，彼此平权）： | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-14 | 14–20 | ar_design_init — AR 提取稿的生成规则 / &#124; 源 &#124; 是什么 &#124; | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-21 | 21–23 | ar_design_init — AR 提取稿的生成规则 / 上游预填与补录材料**与 RR/SR 同等参与提取，无「必须保留原文」义务**——它们是输入，不是需要 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-24 | 24–25 | ar_design_init — AR 提取稿的生成规则 / **定位**：AR/design.md 是**部件视角的需求输入件**——只承载「上游要本部件做什么」。开发侧内容（方案、异常、安全、D | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-26 | 26–27 | 1. 两把裁剪标尺（读部件画像） | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-28 | 28–30 | 1. 两把裁剪标尺（读部件画像） / 「本部件是谁、承担什么、与谁交互」是**工程级事实**，权威在部件画像，本文件不复述—— | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-31 | 31–35 | 1. 两把裁剪标尺（读部件画像） / &#124; 标尺 &#124; 画像章节 &#124; 怎么用 &#124; | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-36 | 36–37 | 1. 两把裁剪标尺（读部件画像） / 上游内容命中任一交互方 → 与本部件相关，纳入提取；均不命中（如纯云侧内部改造、其他部件独立排期项）→ 不纳入，仅在「上游索引」登记为「 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-38 | 38–39 | 2. 提取原则 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-40 | 40–48 | 2. 提取原则 / 1. 本部件**直接参与**的部分需提取； | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-49 | 49–50 | 3. 生成规则（需求提取五段结构） | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-51 | 51–54 | 3. 生成规则（需求提取五段结构） / 通读四源（见文首输入表，本文 §2 原则 6：多源平等），以**画像 §1、§2** 为标尺、 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-55 | 55–104 | 3. 生成规则（需求提取五段结构） / 示例或代码块 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-105 | 105–106 | 3. 生成规则（需求提取五段结构） / **上游信息类别清单（写 design.md §4 时逐类扫描 RR/SR，登记命中项）**： | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-107 | 107–123 | 3. 生成规则（需求提取五段结构） / &#124; 信息类别 &#124; 下游消费方 &#124; | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-124 | 124–125 | 3. 生成规则（需求提取五段结构） / **登记与否的判定（元规则）**：该内容会不会成为下游某产物的**必填输入或硬约束**？会 → 必须登记（正文可只写一句话，细节留在 S | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-126 | 126–127 | 3. 生成规则（需求提取五段结构） / **上游原文位置（design.md §4 表前必写，一行）**： | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-128 | 128–132 | 3. 生成规则（需求提取五段结构） / 示例或代码块 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-133 | 133–134 | 4. 不做的事 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |
| Pacd7f161-135 | 135–143 | 4. 不做的事 / 1. 不生成开发侧章节——实现方案→plan、页面/异常→spec、安全/配置→spec §7/§9、合规与兼容判定→story 影响面 | F1.5, F1.7 | M05, M06 | 按M05,M06比较结论保留其必要职责 |

<a id="Pbf4c9f32"></a>

## skills/story/rules/inbox_import.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pbf4c9f32-1 | 1–2 | S2 规则：上游材料导入 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-3 | 3–5 | S2 规则：上游材料导入 / &gt; &#91;SKILL.md&#93;(../SKILL.md)「各步的规则在哪」表里 S2 导入 那一行指来。**inbox 里有文件时完整读一遍* | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-6 | 6–8 | S2 规则：上游材料导入 / 收件箱存在的原因：需求系统里 PRD / SE 设计有时没归档，人工拿到的文档与界面设计图 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-9 | 9–10 | 材料怎么放 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-11 | 11–13 | 材料怎么放 / 材料放 &#96;doc/features/&lt;AR&gt;/inbox/&#96;（**告知用户这个路径，不要求他记**）。 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-14 | 14–17 | 材料怎么放 / **格式**：能不能读由你判断，脚本只负责物化，三条策略——文本原样并入、&#96;.docx&#96; 转换 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-18 | 18–20 | 材料怎么放 / 碰到脚本物化不了的（如 pdf）：**你读得懂就自己转写成 &#96;.md&#96; 放回收件箱**再归类—— | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-21 | 21–22 | 归类：这份内容将来被哪一章按哪个源读取 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-23 | 23–24 | 归类：这份内容将来被哪一章按哪个源读取 / **归类由你判断**，四类。按内容主体归，不是按文件名像什么归： | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-25 | 25–32 | 归类：这份内容将来被哪一章按哪个源读取 / &#124; 类 &#124; 内容判据（回答什么问题） &#124; 谁来消费 &#124; 落点 &#124; | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-33 | 33–36 | 归类：这份内容将来被哪一章按哪个源读取 / **什么时候选 &#96;IMAGES&#96;**：目标正文已存在，而这份补料与它讲的是同一件事、只是版本更早或更粗。 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-37 | 37–40 | 归类：这份内容将来被哪一章按哪个源读取 / 判断依据按优先级：**用户在申报里的说明**（人说了算）&gt; **读内容判主体**（你能读全文， | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-41 | 41–42 | 归类：这份内容将来被哪一章按哪个源读取 / **读 &#96;.docx&#96; 用预览，不要自己写解析**： | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-43 | 43–46 | 归类：这份内容将来被哪一章按哪个源读取 / 示例或代码块 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-47 | 47–50 | 归类：这份内容将来被哪一章按哪个源读取 / 它输出正文与图清单、**不落盘任何东西**，用的是导入那一步同一个解析器—— | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-51 | 51–52 | 落盘：先写判断，再跑脚本 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-53 | 53–55 | 落盘：先写判断，再跑脚本 / 1. 写 &#96;doc/features/&lt;AR&gt;/inbox/.classify.json&#96;，内容 &#96;{"&lt;文件名&gt;":"RR&#124;SR&#124;AR | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-56 | 56–59 | 落盘：先写判断，再跑脚本 / **为什么写文件而不是当参数传**：JSON 全是引号，而任何 shell 都要对参数再解析一遍—— | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-60 | 60–63 | 落盘：先写判断，再跑脚本 / **导入是整体覆盖**：某类的目标文件全文 = 该类材料按文件名排序拼接的转换结果； | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-64 | 64–67 | 落盘：先写判断，再跑脚本 / **之后**：本轮导入的文件名记入契约当轮 &#96;imported&#96;（见 &#91;init_analysis.md&#93;(init_analysis. | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-68 | 68–69 | 内嵌图里的界面设计图 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-70 | 70–73 | 内嵌图里的界面设计图 / docx 里的图混着流程图与界面图。判据以**图在正文中的上下文**为准——紧邻 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-74 | 74–77 | 内嵌图里的界面设计图 / **每张抽出来的图都要有一句说明**——它是什么。不是界面的图（流程图、时序图、状态机） | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-78 | 78–81 | 内嵌图里的界面设计图 / 示例或代码块 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-82 | 82–83 | 内嵌图里的界面设计图 / 判为界面设计图的**再多一步当场登记**，一张一条命令： | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-84 | 84–88 | 内嵌图里的界面设计图 / 示例或代码块 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-89 | 89–92 | 内嵌图里的界面设计图 / 你给两样：**语义名**（文件名是视觉链路的匹配键，&#96;image1.png&#96; 没有匹配价值）与**一句说明**。 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| Pbf4c9f32-93 | 93–95 | 内嵌图里的界面设计图 / 那句说明不是可选的：成文时作者面上关于这张图的全部信息就是路径与它。 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |

<a id="Peb731b33"></a>

## skills/story/rules/init_analysis.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Peb731b33-1 | 1–2 | S2 规则：材料盘点、需求分析与流程契约 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-3 | 3–5 | S2 规则：材料盘点、需求分析与流程契约 / &gt; &#91;SKILL.md&#93;(../SKILL.md)「各步的规则在哪」表里 S2 初析与流程契约 那一行指来。**S2 开始前完整读一遍* | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-6 | 6–7 | 0. 分两段做，中间隔着材料确认关卡 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-8 | 8–13 | 0. 分两段做，中间隔着材料确认关卡 / 示例或代码块 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-14 | 14–16 | 0. 分两段做，中间隔着材料确认关卡 / **为什么不能一口气写完**：先花几分钟盘点材料、问一句还缺什么，比先写两千字分析 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-17 | 17–24 | 0. 分两段做，中间隔着材料确认关卡 / **轮次 = 一次材料状态**：料导入 → 材料变 → 新一轮；材料没变，重跑 &#96;round&#96; 幂等。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-25 | 25–26 | 1. AR/story-src/init-analysis.md — 决策支撑件 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-27 | 27–30 | 1. AR/story-src/init-analysis.md — 决策支撑件 / 给 S3 关卡上做决策的人看的分析。它**不是交付件**：&#96;/spec&#96; 不读它、归档不含它、 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-31 | 31–33 | 1. AR/story-src/init-analysis.md — 决策支撑件 / **S2a 只写第 ⑤ 节的 1、2 两段**（材料清单 + 缺口判断）；材料确认后再补齐 ①–④ 与 ⑤3、⑤4。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-34 | 34–35 | ① 需求概览 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-36 | 36–37 | ① 需求概览 / 这个需求是什么、解决什么问题。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-38 | 38–39 | ② 本部件视角理解 —— 本需求落在本部件的哪一块 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-40 | 40–43 | ② 本部件视角理解 —— 本需求落在本部件的哪一块 / 本部件的申明（名称与别称、职责范围、运行形态）与六类交互方清单，在**项目事实**里—— | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-44 | 44–48 | ② 本部件视角理解 —— 本需求落在本部件的哪一块 / 1. **落在职责范围的哪一块**——按画像 §1 逐条对需求：哪些在职责内、具体是哪一块； | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-49 | 49–50 | ② 本部件视角理解 —— 本需求落在本部件的哪一块 / 第 ③ 节的「部件在本 SR 下的全量」以本节核对出的职责范围为准。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-51 | 51–52 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-53 | 53–54 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 / **整条范围链的起点。**三源逐条给结论，再收敛成一句。**按强度排序，先判强的**： | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-55 | 55–60 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 / &#124; 源 &#124; 怎么判 &#124; | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-61 | 61–63 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 / → **收敛一句：「本 AR 当前范围 = ______（来源：标题 / design.md 预填 / | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-64 | 64–67 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 / 这一节做的是**材料判读**：范围由上游材料给到哪一步。人对本次做多少有自己的打算是另一回事 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-68 | 68–70 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 / 三源都没给出范围时取部件在本 SR 下的全量，**同样要把全量是什么写出来**， | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-71 | 71–73 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 / **不先定下这一句，第 5 节的信号核对就没有施加对象**，只能默默按上游全量判—— | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-74 | 74–75 | ③ 本 AR 定位 —— 本 AR 当前范围是什么 / 写完落一份机器面副本到 &#96;AR/story-src/.positioning.json&#96;（格式见下）。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-76 | 76–77 | ④ 待实现功能清单 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-78 | 78–79 | ④ 待实现功能清单 / 本 AR 视角下要做的功能点，逐条可数。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-80 | 80–81 | ⑤ 材料现状与范围定法 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-82 | 82–83 | ⑤ 材料现状与范围定法 / 四段，缺一段就不成立： | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-84 | 84–86 | ⑤ 材料现状与范围定法 / 1. **材料清单**——人要先知道手上有什么，才谈得上要不要补。三列：**源 / 来源 / 是什么**， | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-87 | 87–93 | ⑤ 材料现状与范围定法 / &#124; 源 &#124; 来源 &#124; 是什么 &#124; 状态 &#124; | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-94 | 94–128 | ⑤ 材料现状与范围定法 / - **只列实际存在的输入源**。&#96;AR/story-src/upstream.md&#96; 这类**导入落点产物**不是材料， | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-129 | 129–133 | ⑤ 材料现状与范围定法 / &#124; 维度来源 &#124; 判据不满足时 &#124; | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-134 | 134–146 | ⑤ 材料现状与范围定法 / 用户指的方向即便不完美**也必须出现在选项集里**：判据是给他的参考，不是替他下的否决。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-147 | 147–149 | ⑤ 材料现状与范围定法 / 写完把**整个选项集**落 &#96;AR/story-src/.scope-options.json&#96;（格式见下）。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-150 | 150–152 | ⑤ 材料现状与范围定法 / **每轮重生成整个文件**（材料变了回到 S2 即 round+1），旧版进 &#96;.backup/&#96;。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-153 | 153–154 | 2. AR/story-src/story-flow.json — 流程契约 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-155 | 155–157 | 2. AR/story-src/story-flow.json — 流程契约 / 记录每一步的输入、输出与交互：**摆出了哪些选项**、谁在什么依据下选了哪一项， | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-158 | 158–160 | 2. AR/story-src/story-flow.json — 流程契约 / **它同时是这条流程的状态机**：&#96;status&#96; 读它就回答「现在走到哪、下一步干什么」。 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-161 | 161–165 | 2. AR/story-src/story-flow.json — 流程契约 / **你不写这个文件**——&#91;scripts/core/story_flow.py&#93;(../scripts/core/story_flow | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-166 | 166–174 | 2. AR/story-src/story-flow.json — 流程契约 / &#124; 时机 &#124; 命令 &#124; | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-175 | 175–176 | 侧车文件 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-177 | 177–178 | 侧车文件 / 结构化数据一律走文件（为什么不当参数传，见 &#91;inbox_import.md&#93;(inbox_import.md)「落盘：先写判断，再跑脚 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-179 | 179–185 | 侧车文件 / &#124; 侧车 &#124; 谁写 &#124; 何时被消费 &#124; | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-186 | 186–201 | 侧车文件 / 示例或代码块 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-202 | 202–204 | 侧车文件 / &#96;sr_related_ars&#96; 只列**同一 SR 下的其它 AR**，没有就给空数组——**不含本 AR 自己** | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-205 | 205–210 | 侧车文件 / 示例或代码块 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-211 | 211–213 | 侧车文件 / &#96;gate&#96; 必须写明是给哪一级摆的。三级共用这一个文件名，不写明的话， | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-214 | 214–217 | 侧车文件 / **三级的选项文案都不由你写**：第一级摆哪两项是固定的，&#96;label&#96; 由合同给（你写了也以合同为准， | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-218 | 218–219 | 四条纪律 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-220 | 220–228 | 四条纪律 / - **&#96;--basis&#96; 写人的原话**，不写你的转述——它是契约的审计价值所在； | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-229 | 229–232 | 四条纪律 / 拆分定案的范围文字由份表中本 AR 那一份的 &#96;scope&#96; 推导进契约，S4 从那里逐字抄进 | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |
| Peb731b33-233 | 233–234 | 四条纪律 / **防跳步**：spec 阶段 post_check 见本文件存在且未收口即 BLOCKER， | F1.4, F1.5, F1.6, F5.2 | M04, M05, M31 | 按M04,M05,M31比较结论保留其必要职责 |

<a id="P2adb3d49"></a>

## skills/story/rules/review_reflow.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P2adb3d49-1 | 1–2 | 评审回流规则：按 review.md 修订 spec | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-3 | 3–5 | 评审回流规则：按 review.md 修订 spec / 评审意见回来之后怎么处置。**输入唯一就是 &#96;AR/review.md&#96;**——人可能在系统上批注、 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-6 | 6–8 | 评审回流规则：按 review.md 修订 spec / **不重建 story、不重新归档**：story 定稿于评审时点，系统上那份就是评审依据。 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-9 | 9–13 | 评审回流规则：按 review.md 修订 spec / **冻结件登记之后只读。** &#96;AR/story-src/decisions.json&#96; 随 story 登记冻结， | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-14 | 14–15 | 1. 逐项处置 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-16 | 16–19 | 1. 逐项处置 / 每条议题的表态是评审人写在「审核结果：」后面的**自由文本**，没有勾选项—— | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-20 | 20–27 | 1. 逐项处置 / &#124; 评审人写的是 &#124; 处置 &#124; | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-28 | 28–32 | 1. 逐项处置 / 其他意见有正式落点：&#96;review.md&#96; 的「其他意见」一章 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-33 | 33–36 | 1. 逐项处置 / 其他意见没有对应的议题，是需求缺失还是叙述不清**只能由你判**。 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-37 | 37–40 | 1. 逐项处置 / **「改哪一条」也是你的判读**：登记表里没有指向 spec 编号的字段——那种字段会被填成 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-41 | 41–42 | 2. 处置台账 &#96;AR/review-disposition.json&#96; | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-43 | 43–44 | 2. 处置台账 &#96;AR/review-disposition.json&#96; / 交代每条意见的去向。读者是人（想知道意见到哪儿去了）与下游 plan（参考未处理项）。 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-45 | 45–56 | 2. 处置台账 &#96;AR/review-disposition.json&#96; / 示例或代码块 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-57 | 57–59 | 2. 处置台账 &#96;AR/review-disposition.json&#96; / &#96;from&#96; 用议题编号或 &#96;freeform#&lt;序&gt;&#96;；自由意见须带 &#96;kind&#96;（&#96;requirement&#96; / &#96;narrativ | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-60 | 60–61 | 3. spec 改动走 framework 既有的 correction 闭环 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-62 | 62–64 | 3. spec 改动走 framework 既有的 correction 闭环 / &#96;--correction-init --q-requirement y&#96; → 根因判 spec 层 → 级联重验下游已闭环阶段 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-65 | 65–66 | 4. 归档后的边界 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-67 | 67–71 | 4. 归档后的边界 / &#96;AR/review.md&#96; 的**人工区**归人所有——&#96;审核结果：&#96; 之后那几行，以及 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-72 | 72–73 | 回传意见写到哪 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-74 | 74–75 | 回传意见写到哪 / 评审人可能把意见给在别处（邮件、聊天、整份带批注的文档）。往回落的时候： | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-76 | 76–81 | 回传意见写到哪 / &#124; 意见的形态 &#124; 落到哪 &#124; | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-82 | 82–84 | 回传意见写到哪 / 整份覆盖会把渲染器生成的结构一起替换掉，下一次 &#96;build&#96; 与人手改的正本就对不上了； | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-85 | 85–86 | 5. 已知限制 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-87 | 87–88 | 5. 已知限制 / spec 修订后，系统上的正文（归档时的 story）停在评审时点，不再反映最新 spec。 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-89 | 89–91 | 5. 已知限制 / - 对下游无影响：plan/coding 看的是 spec； | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-92 | 92–93 | 5. 已知限制 / 台账里注明「本轮 spec 已修订 N 处，系统正文未同步」，是否手工更新由人决定。 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-94 | 94–95 | 已经开工的 plan 怎么办 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P2adb3d49-96 | 96–99 | 已经开工的 plan 怎么办 / 交付门之后两条路可以并行开始，**这不等于下游可以不管上游变更**。评审回流改了 | F3.4 | M21 | 按M21比较结论保留其必要职责 |

<a id="P366a5367"></a>

## skills/story/rules/scope_gate.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P366a5367-1 | 1–2 | S3 规则：材料与范围确认关卡 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-3 | 3–5 | S3 规则：材料与范围确认关卡 / &gt; &#91;SKILL.md&#93;(../SKILL.md)「各步的规则在哪」表里 S3 三级关卡 那一行指来。**进关卡前完整读一遍**。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-6 | 6–7 | S3 规则：材料与范围确认关卡 / 完整提取件 &#96;AR/design.md&#96; 此时**尚未生成**：范围还没定，先生成的完整草稿必然报废。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-8 | 8–9 | 三级，每级只问一件事 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-10 | 10–15 | 三级，每级只问一件事 / 示例或代码块 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-16 | 16–18 | 三级，每级只问一件事 / 第二级**有几项取决于分析找出几个可切维度**——分析只找到一个（即「不切」）时就只有一项， | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-19 | 19–22 | 三级，每级只问一件事 / **为什么分开问**：第一级问的是材料，第二级问的是范围——挤在一级里，人得同时权衡两件 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-23 | 23–25 | 三级，每级只问一件事 / **终止条件是「范围已定」**：第二级选了整体承载，或第三级完成定案——都直接进 S4。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-26 | 26–28 | 三级，每级只问一件事 / **第一级之前不做需求分析**：那一级只需要材料清单与一句缺口判断， | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-29 | 29–30 | 三级，每级只问一件事 / **选项从哪来**——三级各不相同，这是本关卡最要紧的一条： | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-31 | 31–36 | 三级，每级只问一件事 / &#124; 级 &#124; &#96;--gate&#96; &#124; 选项来源 &#124; 你要做什么 &#124; | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-37 | 37–40 | 三级，每级只问一件事 / **第二、三级不要现编选项**。分析给几项就摆几项，哪怕只有整体承载一项—— | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-41 | 41–44 | 三级，每级只问一件事 / **人想要分析里没有的切法**：口述修正 → 回 S2b 重做分析（补上该维度、重落 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-45 | 45–47 | 三级，每级只问一件事 / **顺序不可跳**：脚本按 &#96;status&#96; 的 &#96;next&#96; 校验——当前这一步不是它说的那一步就直接拒绝。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-48 | 48–52 | 三级，每级只问一件事 / **怎么呈现**：确认组件（如 AskUserQuestion）可用时**必须用组件**摆选项，同轮消息末尾 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-53 | 53–54 | 第一级：材料 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-55 | 55–57 | 第一级：材料 / 问的时候只给三段（格式见 SKILL「停等消息怎么写」）：**一句盘点结论**、 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-58 | 58–60 | 第一级：材料 / **这一级请人陈述的是事实**，不是判断：料放进去了，或者现有材料就是全部。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-61 | 61–63 | 第一级：材料 / 材料清单四列（源 / 来源 / 是什么 / 状态）写进 &#96;AR/story-src/init-analysis.md&#96; 第 ⑤ 节 1， | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-64 | 64–66 | 第一级：材料 / **这一级不呈现需求分析**——范围、功能清单、切法都还没做，此刻要人回答的只有 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-67 | 67–68 | 第一级：材料 / **缺口判断必须是结论句**——只列文件名等于没问。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-69 | 69–70 | 第一级：材料 / **推荐项由缺口判断决定**： | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-71 | 71–75 | 第一级：材料 / &#124; 第 ⑤ 节 2 判为 &#124; 推荐 &#124; | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-76 | 76–78 | 第一级：材料 / **诊断出缺口，推荐就必须跟上**，否则等于没诊断——推荐去定范围，就是让人在一个 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-79 | 79–80 | 人回答之后 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-81 | 81–83 | 人回答之后 / **收件箱里的原件一律会被导入**，人回哪一项都一样：文件已经在盘上，导入是脚本的活。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-84 | 84–85 | 人回答之后 / 人选「材料已放进 inbox」时，脚本在选中那一刻核**料到了没有**，两条都算数： | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-86 | 86–88 | 人回答之后 / - &#96;inbox/&#96; 里除 &#96;README.md&#96; 外有未导入的文件； | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-89 | 89–92 | 人回答之后 / 两条都不成立 → &#96;rejected&#96;，原地重提：人还没放，或者放到了别处。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-93 | 93–94 | 导入之后什么时候再停 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-95 | 95–96 | 导入之后什么时候再停 / 先**拿新材料重新盘点：还缺什么**。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-97 | 97–102 | 导入之后什么时候再停 / - 不缺了 → 直接进需求分析，**不再问**。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-103 | 103–105 | 导入之后什么时候再停 / **缺口写进 &#96;missing&#96; / &#96;why&#96; 与停等正文，不写进选项标签**：标签固定，改了它人就分不出 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-106 | 106–108 | 导入之后什么时候再停 / **上一轮缺的没补上，照样可以再问**——问的是「还缺什么」，人回答的是「放进去了」 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-109 | 109–111 | 导入之后什么时候再停 / 第 2 轮起，第一级**只在你为这一级摆出选项侧车时停**。侧车要写明 &#96;gate&#96;， | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-112 | 112–113 | 第二级：范围定法选项集 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-114 | 114–116 | 第二级：范围定法选项集 / 这一级之前先做完 S2b 需求分析（需求概览 → 本部件视角 → 本 AR 定位 → 待实现功能清单 → | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-117 | 117–119 | 第二级：范围定法选项集 / 问的时候也是三段：**一句当前范围**（含来源）、**一句要定什么**、 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-120 | 120–123 | 第二级：范围定法选项集 / **选项集恒定照出**，不因「看着不用切」而省略：人无从推翻一个从未被摆出来的选项。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-124 | 124–126 | 第二级：范围定法选项集 / 选整体承载 → 范围就是定位出的那个范围，直接进 S4。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-127 | 127–132 | 第二级：范围定法选项集 / **只有整体承载一项时，把出口一起说出来**：分析没找到可行切法，这一问对人来说更像通知 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-133 | 133–134 | 人提出自己的拆分诉求时 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-135 | 135–138 | 人提出自己的拆分诉求时 / 他可能在这一关口述（「本次先做 X」「按 Y 切开」），也可能在任务描述里早就说过。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-139 | 139–140 | 人提出自己的拆分诉求时 / 不要求他的话先长成一个「维度」。按下面五步跟他谈： | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-141 | 141–153 | 人提出自己的拆分诉求时 / 1. **落条目**：他说的那部分对应哪些具体功能条目（对照第 ④ 节功能清单与 SR 定位）， | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-154 | 154–155 | 第三级：本 AR 承载哪一份 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-156 | 156–158 | 第三级：本 AR 承载哪一份 / 让人从零描述范围是高成本输入，而你读过全部材料——份表已在初析备好，直接呈现， | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-159 | 159–162 | 第三级：本 AR 承载哪一份 / 按选定维度的份表逐份列出（序、范围一句话、依赖哪几份），取得选择。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-163 | 163–165 | 第三级：本 AR 承载哪一份 / 定案后**把整张份表写进侧车文件** &#96;AR/story-src/.split-parts.json&#96;，再跑 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-166 | 166–171 | 第三级：本 AR 承载哪一份 / 示例或代码块 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-172 | 172–178 | 第三级：本 AR 承载哪一份 / - &#96;carrier&#96; 恰有一份是**本 feature 名**——就是人选中的那份，且必须与 &#96;--chosen&#96; 的 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-179 | 179–183 | 第三级：本 AR 承载哪一份 / S4 生成时按契约份表转写进 &#96;AR/design.md&#96; 的「本 AR 范围与拆分说明」，并在 spec 阶段照常进 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-184 | 184–185 | 用户明说「别逐个问」时，这两级照停 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-186 | 186–189 | 用户明说「别逐个问」时，这两级照停 / **免不掉。** 材料关卡与范围关卡是本扩展仅有的两处停等点，它们**无条件**—— | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-190 | 190–192 | 用户明说「别逐个问」时，这两级照停 / 理由不是流程洁癖：这两件事**定错了后面全废**——范围定错，spec、plan、验收边界 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P366a5367-193 | 193–196 | 用户明说「别逐个问」时，这两级照停 / **你的判断进推荐项，不进决策。** 缺口判断照做、推荐项照给（见上面的推荐表）， | F1.6 | M05 | 按M05比较结论保留其必要职责 |

<a id="P09f94671"></a>

## skills/story/scripts/adapters/review.js

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P09f94671-1 | 1–16 | 文件头/元信息 | F3.4, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| P09f94671-17 | 17–17 | 'use strict'; | F3.4, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| P09f94671-18 | 18–18 | fs | F3.4, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| P09f94671-19 | 19–21 | path | F3.4, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| P09f94671-22 | 22–32 | FEEDBACK_FILE | F3.4, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| P09f94671-33 | 33–68 | fetchReview | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P09f94671-69 | 69–69 | module.exports = { fetchReview }; | F3.4, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |

<a id="Pc2301217"></a>

## skills/story/scripts/adapters/story.js

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pc2301217-1 | 1–58 | 文件头/元信息 | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-59 | 59–59 | 'use strict'; | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-60 | 60–60 | fs | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-61 | 61–63 | path | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-64 | 64–64 | DEFAULT_SYSTEM_DIR | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-65 | 65–66 | SYSTEM_DIR_ENV | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-67 | 67–70 | log | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-71 | 71–74 | emit | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-75 | 75–80 | fail | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-81 | 81–92 | featuresDir | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-93 | 93–102 | ts | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-103 | 103–113 | writeIfAbsent | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-114 | 114–123 | writeDetail | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-124 | 124–135 | systemRoot | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-136 | 136–151 | readTicket | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-152 | 152–157 | ticketText | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-158 | 158–164 | ticketTitle | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-165 | 165–174 | systemWrite | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-175 | 175–229 | cmdInit | F1.1, F6.3 | M01 | 按M01比较结论保留其必要职责 |
| Pc2301217-230 | 230–275 | cmdArchive | F3.3 | M21 | 按M21比较结论保留其必要职责 |
| Pc2301217-276 | 276–292 | cmdRestore | F3.3 | M21 | 按M21比较结论保留其必要职责 |
| Pc2301217-293 | 293–300 | cmdReview | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| Pc2301217-301 | 301–311 | cmdHelp | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-312 | 312–312 | cmd | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-313 | 313–313 | ar | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-314 | 314–314 | mcpToken | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-315 | 315–315 | projectRootArg | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-316 | 316–316 | argError | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-317 | 317–332 | for (let i = 4; i &lt; process.argv.length; i++) { | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-333 | 333–333 | USAGE | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-334 | 334–334 | CMDS | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-335 | 335–335 | if (argError) fail(&#96;${argError}。${USAGE}&#96;); | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-336 | 336–338 | if (!CMDS.includes(cmd)) { | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-339 | 339–342 | if (cmd === 'help') { | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-343 | 343–344 | if (!ar &#124;&#124; !/^&#91;\w.-&#93;+$/.test(ar)) fail(&#96;非法 AR 单号：「${ar ?? ''}」&#96;); | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-345 | 345–349 | if (!mcpToken) log('未传入 mcp-token（本地容忍；部署环境将拒绝执行）'); | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-350 | 350–351 | projectRoot | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-352 | 352–352 | featureRoot | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-353 | 353–353 | localAr | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-354 | 354–355 | system | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |
| Pc2301217-356 | 356–359 | if (cmd === 'init') cmdInit(ar, featureRoot, localAr, system); | F1.1, F3.3, F6.3 | M01, M21, M35 | 按M01,M21,M35比较结论保留其必要职责 |

<a id="P456ec299"></a>

## skills/story/scripts/adapters/token.js

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P456ec299-1 | 1–16 | 文件头/元信息 | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P456ec299-17 | 17–17 | 'use strict'; | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P456ec299-18 | 18–18 | process.stdout.write('local-mcp-token\n'); | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |

<a id="P4ec8b22e"></a>

## skills/story/scripts/core/flow-check.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P4ec8b22e-1 | 1–9 | 文件头/元信息 | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-10 | 10–10 | import * as fs from 'node:fs'; | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-11 | 11–11 | import * as path from 'node:path'; | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-12 | 12–22 | import { fileURLToPath } from 'node:url'; | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-23 | 23–23 | FLOW_FILE | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-24 | 24–25 | FLOW_SCHEMA | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-26 | 26–33 | FLOW_GATES | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-34 | 34–34 | materialChoices | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-35 | 35–42 | flowMaterialChoices | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P4ec8b22e-43 | 43–43 | FLOW_CARRY_ALL | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-44 | 44–44 | FLOW_OUTCOMES | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-45 | 45–55 | FLOW_FIX | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-56 | 56–64 | FLOW_STATES | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-65 | 65–69 | reached | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-70 | 70–88 | DESIGN_FILE | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-89 | 89–182 | currentScope | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P4ec8b22e-183 | 183–351 | flowProblems | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-352 | 352–367 | isStoryFeature | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-368 | 368–386 | storyProduced | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |
| P4ec8b22e-387 | 387–395 | readFlow | F1.6, F5.2, F5.3 | M05, M31, M32 | 按M05,M31,M32比较结论保留其必要职责 |

<a id="Pb26a1685"></a>

## skills/story/scripts/core/headings.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pb26a1685-1 | 1–21 | 文件头/元信息 | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pb26a1685-22 | 22–24 | NUMBER_PREFIX | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pb26a1685-25 | 25–33 | BARE_NUMBER_PREFIX | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pb26a1685-34 | 34–41 | takeAuthorNumber | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pb26a1685-42 | 42–49 | LETTER_PREFIX | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pb26a1685-50 | 50–57 | normalizeHeading | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pb26a1685-58 | 58–74 | FIGURE_PREFIX | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| Pb26a1685-75 | 75–140 | renumberStory | F2.6 | M19 | 按M19比较结论保留其必要职责 |

<a id="P5a530458"></a>

## skills/story/scripts/core/import_sources.py

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P5a530458-1 | 1–34 | """import_sources.py — 把人工放进 inbox/ 的上游材料转成流程能消费的形态。 | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-35 | 35–36 | from __future__ import annotations | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-37 | 37–37 | import argparse | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-38 | 38–38 | import json | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-39 | 39–39 | import re | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-40 | 40–40 | import shutil | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-41 | 41–41 | import sys | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-42 | 42–42 | import time | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-43 | 43–43 | import xml.etree.ElementTree as ET | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-44 | 44–44 | import zipfile | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-45 | 45–46 | from pathlib import Path | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-47 | 47–47 | W | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-48 | 48–48 | R | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-49 | 49–49 | A | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-50 | 50–51 | REL_NS | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-52 | 52–52 | DOC_EXT | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-53 | 53–54 | IMAGE_EXTS | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-55 | 55–56 | SKIP_NAMES | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-57 | 57–61 | CLASSIFY_FILE | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-62 | 62–65 | CLASSES | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-66 | 66–73 | DOC_TARGET | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-74 | 74–75 | UX_IMAGE_DIR | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-76 | 76–78 | GENERATED_MARK | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-79 | 79–82 | ImportError_ | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-83 | 83–86 | log | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-87 | 87–100 | features_dir | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-101 | 101–110 | scan_sources | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-111 | 111–125 | read_classify | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-126 | 126–138 | is_text | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-139 | 139–160 | validate | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-161 | 161–183 | read_media | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-184 | 184–207 | _heading_level | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-208 | 208–220 | _run_text | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-221 | 221–251 | _para_markdown | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-252 | 252–274 | _table_markdown | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-275 | 275–315 | docx_to_markdown | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-316 | 316–327 | backup | F1.2, F1.3, F7.2 | M02, M03, M36 | 按M02,M03,M36比较结论保留其必要职责 |
| P5a530458-328 | 328–341 | demote_headings | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-342 | 342–352 | render_target | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-353 | 353–372 | preview | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-373 | 373–412 | convert_sources | F1.2 | M02 | 按M02比较结论保留其必要职责 |
| P5a530458-413 | 413–419 | _no_such_image | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-420 | 420–440 | caption_image | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P5a530458-441 | 441–451 | resolve_image_arg | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-452 | 452–462 | _image_for_mark | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-463 | 463–479 | mark_unused | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P5a530458-480 | 480–489 | mark_used | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P5a530458-490 | 490–522 | register_ux | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P5a530458-523 | 523–680 | main | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |
| P5a530458-681 | 681–682 | if __name__ == "__main__": | F1.2, F1.3 | M02, M03 | 按M02,M03比较结论保留其必要职责 |

<a id="P7cd4d399"></a>

## skills/story/scripts/core/lint-rules.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P7cd4d399-1 | 1–16 | 文件头/元信息 | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-17 | 17–17 | import * as fs from 'node:fs'; | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-18 | 18–18 | import * as path from 'node:path'; | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-19 | 19–19 | import { fileURLToPath } from 'node:url'; | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-20 | 20–20 | import { activeKnowledge } from '../../../../hooks/shared/knowledge.mjs'; | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-21 | 21–22 | import { normalizeHeading } from './headings.mjs'; | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-23 | 23–25 | CONTRACT_PATH | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-26 | 26–32 | vocabularyCache | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-33 | 33–49 | clientVocabulary | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-50 | 50–55 | EXEMPT_LINE_PATTERNS | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-56 | 56–63 | escapeRe | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-64 | 64–84 | readConfig | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-85 | 85–90 | GENERIC_PATH_ALTS | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-91 | 91–97 | moduleLayerIds | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-98 | 98–117 | localPathRe | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-118 | 118–152 | scanBannedTerms | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-153 | 153–155 | SEARCH_PHRASE_RE | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-156 | 156–158 | SOURCE_TAG_RE | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-159 | 159–161 | DOC_COORDINATE_RE | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-162 | 162–162 | CAMEL_CASE_RE | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-163 | 163–165 | SNAKE_CASE_RE | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-166 | 166–168 | INLINE_CODE_RE | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-169 | 169–170 | AI_HEADING_TERMS | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-171 | 171–194 | REDLINE_HINTS | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-195 | 195–213 | narrativeLines | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-214 | 214–238 | redlineScopes | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-239 | 239–320 | scanLanguageRedline | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-321 | 321–334 | IMAGE_HINTS | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-335 | 335–374 | scanMaterialList | F2.6 | M18 | 按M18比较结论保留其必要职责 |
| P7cd4d399-375 | 375–390 | firstSegment | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-391 | 391–410 | scanLocalPaths | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-411 | 411–427 | DANGLING_REF_PATTERNS | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-428 | 428–429 | FRAMEWORK_ARTIFACT_NAMES | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-430 | 430–442 | constraintNames | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-443 | 443–454 | bareFileNameRule | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-455 | 455–485 | scanDanglingRefs | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-486 | 486–502 | formatHits | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-503 | 503–527 | scanBrokenImages | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P7cd4d399-528 | 528–553 | proseBlocks | F2.6 | M19 | 按M19比较结论保留其必要职责 |

<a id="Pa2f7a68f"></a>

## skills/story/scripts/core/materials.py

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pa2f7a68f-1 | 1–28 | """materials.py — 材料清单（&#96;AR/story-src/materials.json&#96;）的唯一算法与唯一写入者。 | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-29 | 29–30 | from __future__ import annotations | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-31 | 31–31 | import json | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-32 | 32–32 | from hashlib import sha256 | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-33 | 33–34 | from pathlib import Path | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-35 | 35–36 | import import_sources | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-37 | 37–37 | SCHEMA | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-38 | 38–40 | MANIFEST | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-41 | 41–46 | SOURCE_DOCS | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-47 | 47–47 | SOURCE_DIRS | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-48 | 48–50 | INBOX | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-51 | 51–53 | CAPTIONS | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-54 | 54–57 | MaterialError | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-58 | 58–64 | file_digest | F1.3, F1.4, F7.2 | M03, M04, M36 | 按M03,M04,M36比较结论保留其必要职责 |
| Pa2f7a68f-65 | 65–68 | kind_of | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-69 | 69–95 | read_captions | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| Pa2f7a68f-96 | 96–118 | _write_entry | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-119 | 119–123 | write_caption | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| Pa2f7a68f-124 | 124–128 | write_unused | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| Pa2f7a68f-129 | 129–133 | clear_unused | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| Pa2f7a68f-134 | 134–185 | collect_materials | F1.4 | M04 | 按M04比较结论保留其必要职责 |
| Pa2f7a68f-186 | 186–196 | compute_digest | F1.4 | M04 | 按M04比较结论保留其必要职责 |
| Pa2f7a68f-197 | 197–210 | digest_with | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-211 | 211–218 | source_sha | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-219 | 219–223 | _same_text | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-224 | 224–285 | collect_sources | F1.4 | M04 | 按M04比较结论保留其必要职责 |
| Pa2f7a68f-286 | 286–297 | build | F1.4 | M04 | 按M04比较结论保留其必要职责 |
| Pa2f7a68f-298 | 298–301 | path_of | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-302 | 302–309 | write | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-310 | 310–316 | refresh | F1.4 | M04 | 按M04比较结论保留其必要职责 |
| Pa2f7a68f-317 | 317–334 | read | F1.3, F1.4 | M03, M04 | 按M03,M04比较结论保留其必要职责 |
| Pa2f7a68f-335 | 335–337 | pending | F1.4 | M04 | 按M04比较结论保留其必要职责 |

<a id="P96d19165"></a>

## skills/story/scripts/core/review-render.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P96d19165-1 | 1–36 | 文件头/元信息 | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-37 | 37–39 | import * as crypto from 'node:crypto'; | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-40 | 40–44 | HUMAN_ZONE_MARK | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-45 | 45–46 | ISSUE_MARK | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-47 | 47–48 | DIGEST_IN_MARK | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-49 | 49–59 | issueMark | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-60 | 60–65 | projectionDigest | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-66 | 66–69 | recordedDigest | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-70 | 70–72 | ProjectionConflict | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-73 | 73–73 | FREEFORM_OPEN | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-74 | 74–79 | FREEFORM_CLOSE | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-80 | 80–83 | STATUS_CHAPTERS | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-84 | 84–86 | FREEFORM_CHAPTER | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-87 | 87–91 | DOC_HINT | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-92 | 92–95 | FREEFORM_HINT | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-96 | 96–112 | renderDocHeader | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-113 | 113–132 | renderMachineZone | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-133 | 133–147 | renderHumanZone | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-148 | 148–161 | humanZoneStart | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-162 | 162–181 | machineZoneOf | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-182 | 182–188 | issueHandEdited | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-189 | 189–206 | extractHumanZone | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-207 | 207–223 | extractFreeformZone | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-224 | 224–236 | renderFreeformSection | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-237 | 237–247 | sectionNameOf | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-248 | 248–269 | groupByCategory | F3.2 | M20 | 按M20比较结论保留其必要职责 |
| P96d19165-270 | 270–303 | renderReview | F3.2, F3.1 | M20 | 按M20比较结论保留其必要职责 |

<a id="P78aef573"></a>

## skills/story/scripts/core/story-build.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P78aef573-1 | 1–35 | 文件头/元信息 | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-36 | 36–36 | import { spawnSync } from 'node:child_process'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-37 | 37–37 | import { createRequire } from 'node:module'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-38 | 38–38 | import * as crypto from 'node:crypto'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-39 | 39–39 | import * as fs from 'node:fs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-40 | 40–40 | import * as path from 'node:path'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-41 | 41–41 | import { fileURLToPath } from 'node:url'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-42 | 42–42 | import { normalizeHeading, renumberStory } from './headings.mjs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-43 | 43–43 | import { currentScope } from './flow-check.mjs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-44 | 44–44 | import { readerReviewTask } from '../../../../hooks/shared/reader-review-task.mjs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-45 | 45–45 | import { readUse, UseError } from '../../../../hooks/shared/knowledge-use.mjs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-46 | 46–49 | import { | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-50 | 50–50 | import { activeKnowledge } from '../../../../hooks/shared/knowledge.mjs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-51 | 51–55 | import { | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-56 | 56–56 | import { storyReviewProblems } from '../../../../hooks/shared/verifier-report.mjs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-57 | 57–57 | import { featureRoot as featureRootOf } from '../../../../hooks/shared/paths.mjs'; | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-58 | 58–65 | import { | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-66 | 66–66 | COMMANDS | F2, F3.2, F5.3, F2.1 | M20, M32 | 按R01处理局部；不整块删 |
| P78aef573-67 | 67–74 | COMMANDS | F2, F3.2, F5.3, F2.1 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-75 | 75–89 | DECISION_FIELDS | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-90 | 90–92 | AR_ROOT_FILES | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-93 | 93–100 | DOMAIN_NA | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-101 | 101–109 | REVIEW_BANNED_LINES | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-110 | 110–114 | fail | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-115 | 115–130 | parseArgs | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-131 | 131–134 | readText | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-135 | 135–140 | readJson | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-141 | 141–156 | writeJson | F2, F3.2, F5.3, F7.2 | M20, M32, M36 | 按M20,M32,M36比较结论保留其必要职责 |
| P78aef573-157 | 157–176 | createOfflineContext | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-177 | 177–210 | createContext | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-211 | 211–222 | STORY_SRC_LEDGERS | F2, F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-223 | 223–239 | requireLedgers | F5.3, F5.4 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-240 | 240–248 | storyFrozen | F5.3, F5.4 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-249 | 249–261 | refuseIfFrozen | F5.3, F5.4 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-262 | 262–273 | digestOf | F2, F3.2, F5.3, F7.2 | M20, M32, M36 | 按M20,M32,M36比较结论保留其必要职责 |
| P78aef573-274 | 274–289 | activeKnowledgeEntries | F2.5 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-290 | 290–347 | knowledgeUseVerdicts | F2.5 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-348 | 348–366 | scanSources | F1.4, F3.1, F2.1, F5.3 | M07 | 按R13处理局部；不整块删 |
| P78aef573-367 | 367–374 | scanSources | F1.4, F3.1, F2.1, F5.3 | M07 | 按M07比较结论保留其必要职责 |
| P78aef573-375 | 375–377 | DIAGRAM_FENCE | F1.4, F3.1 | M04, M20 | 按M04,M20比较结论保留其必要职责 |
| P78aef573-378 | 378–401 | missingSourceLine | F1.4, F3.1 | M07 | 按M07比较结论保留其必要职责 |
| P78aef573-402 | 402–409 | ensureDecisions | F3.2, F3.1 | M07 | 按M07比较结论保留其必要职责 |
| P78aef573-410 | 410–428 | R01 / function cmdInit(ctx) { | F1.4, F3.1, F2.1 | M04, M07, M08, M20 | 按R01处理局部；不整块删 |
| P78aef573-429 | 429–433 | R01 / function cmdInit(ctx) { | F1.4, F3.1, F2.1 | M04, M07, M08, M20 | 按M04,M07,M08,M20比较结论保留其必要职责 |
| P78aef573-434 | 434–434 | SRC_INDEX | F1.4, F3.1 | M04, M20 | 按M04,M20比较结论保留其必要职责 |
| P78aef573-435 | 435–436 | SRC_SELECTION | F1.4, F3.1 | M04, M20 | 按M04,M20比较结论保留其必要职责 |
| P78aef573-437 | 437–445 | AR_ORIGINAL | F1.4, F3.1 | M04, M20 | 按M04,M20比较结论保留其必要职责 |
| P78aef573-446 | 446–447 | DERIVED_KEYS | F1.4, F3.1 | M04, M20 | 按M04,M20比较结论保留其必要职责 |
| P78aef573-448 | 448–448 | STAGE_SKIP | F1.4, F3.1 | M04, M20 | 按M04,M20比较结论保留其必要职责 |
| P78aef573-449 | 449–451 | DISPOSITIONS | F1.4, F3.1 | M04, M20 | 按M04,M20比较结论保留其必要职责 |
| P78aef573-452 | 452–456 | readBytesOrNull | F2.1, F2.2 | M07, M08, M09, M10 | 按M07,M08,M09,M10比较结论保留其必要职责 |
| P78aef573-457 | 457–469 | manifestDocs | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-470 | 470–496 | indexSources | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-497 | 497–507 | scopeRound | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-508 | 508–528 | indexImages | F1.3 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-529 | 529–559 | buildIndex | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-560 | 560–618 | selectionProblems | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-619 | 619–635 | staleSources | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-636 | 636–668 | driftReport | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-669 | 669–678 | missingRequired | F2.1, F1.4 | M07 | 按M07比较结论保留其必要职责 |
| P78aef573-679 | 679–707 | acceptSource | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-708 | 708–709 | TEMPLATE | F2.1, F2.2 | M07, M08, M09, M10 | 按M07,M08,M09,M10比较结论保留其必要职责 |
| P78aef573-710 | 710–710 | TODO_CONTENT | F2.1, F2.2 | M07, M08, M09, M10 | 按M07,M08,M09,M10比较结论保留其必要职责 |
| P78aef573-711 | 711–717 | TODO_FORM | F2.1, F2.2 | M07, M08, M09, M10 | 按M07,M08,M09,M10比较结论保留其必要职责 |
| P78aef573-718 | 718–732 | readTemplate | F2.2, F5.5 | M09 | 按R09处理局部；不整块删 |
| P78aef573-733 | 733–734 | readTemplate | F2.2, F5.5 | M09 | 按M09比较结论保留其必要职责 |
| P78aef573-735 | 735–745 | writeTemplateBasis | F2.2 | M10 | 按M10比较结论保留其必要职责 |
| P78aef573-746 | 746–756 | shape | F2.2 | M10 | 按M10比较结论保留其必要职责 |
| P78aef573-757 | 757–786 | templateSkeleton | F2.2 | M10 | 按M10比较结论保留其必要职责 |
| P78aef573-787 | 787–813 | renderTemplate | F2.2 | M10 | 按R09处理局部；不整块删 |
| P78aef573-814 | 814–853 | afterSpec | F2.2 | M10 | 按M10比较结论保留其必要职责 |
| P78aef573-854 | 854–966 | cmdSources | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P78aef573-967 | 967–982 | storySections | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-983 | 983–992 | appendixChapter | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-993 | 993–1017 | subsectionText | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1018 | 1018–1053 | subsectionSpan | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1054 | 1054–1058 | basename | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1059 | 1059–1065 | readManifest | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1066 | 1066–1096 | materialImages | F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P78aef573-1097 | 1097–1116 | materialListTargets | F2.5 | M18 | 按M18比较结论保留其必要职责 |
| P78aef573-1117 | 1117–1121 | relFromStory | F2.5, F2.6, F7.2 | M17, M18, M19, M36 | 按M17,M18,M19,M36比较结论保留其必要职责 |
| P78aef573-1122 | 1122–1125 | sameBytes | F2.5, F2.6, F7.2 | M17, M18, M19, M36 | 按M17,M18,M19,M36比较结论保留其必要职责 |
| P78aef573-1126 | 1126–1130 | relFromFeature | F2.5, F2.6, F7.2 | M17, M18, M19, M36 | 按M17,M18,M19,M36比较结论保留其必要职责 |
| P78aef573-1131 | 1131–1140 | joinPosix | F2.5, F2.6, F7.2 | M17, M18, M19, M36 | 按M17,M18,M19,M36比较结论保留其必要职责 |
| P78aef573-1141 | 1141–1159 | subsectionNames | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1160 | 1160–1173 | findSubsection | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1174 | 1174–1183 | slotApplies | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1184 | 1184–1203 | slotCondition | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1204 | 1204–1213 | specText | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1214 | 1214–1228 | specSection | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1229 | 1229–1243 | pipeTables | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1244 | 1244–1254 | isPlaceholderRow | F2.5, F2.6 | M17, M18, M19 | 按M17,M18,M19比较结论保留其必要职责 |
| P78aef573-1255 | 1255–1268 | specTerms | F2.4.2, F2.6 | M14, M15, M16, M19 | 按M14,M15,M16,M19比较结论保留其必要职责 |
| P78aef573-1269 | 1269–1280 | scopeList | F2.4.2, F2.6 | M14, M15, M16, M19 | 按M14,M15,M16,M19比较结论保留其必要职责 |
| P78aef573-1281 | 1281–1297 | scopeBoundaryRows | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| P78aef573-1298 | 1298–1316 | scopeRationale | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| P78aef573-1317 | 1317–1360 | diagramsOf | F2.4.2, F1.3 | M16 | 按M16比较结论保留其必要职责 |
| P78aef573-1361 | 1361–1373 | diagramTopic | F2.4.2, F1.3 | M16 | 按M16比较结论保留其必要职责 |
| P78aef573-1374 | 1374–1379 | diagramsNotCarried | F2.4.2, F1.3 | M16 | 按M16比较结论保留其必要职责 |
| P78aef573-1380 | 1380–1385 | carryableBlock | F2.4.2, F1.3 | M16 | 按M16比较结论保留其必要职责 |
| P78aef573-1386 | 1386–1399 | diagramBody | F2.4.2, F1.3 | M16 | 按M16比较结论保留其必要职责 |
| P78aef573-1400 | 1400–1414 | upstreamDocs | F2.4.2, F1.3 | M16 | 按M16比较结论保留其必要职责 |
| P78aef573-1415 | 1415–1418 | DROP_COLUMNS | F2.4.2, F2.6 | M14, M15, M16, M19 | 按M14,M15,M16,M19比较结论保留其必要职责 |
| P78aef573-1419 | 1419–1425 | APPENDIX_FROM_SPEC | F2.4.2, F2.6 | M14, M15, M16, M19 | 按M14,M15,M16,M19比较结论保留其必要职责 |
| P78aef573-1426 | 1426–1442 | appendixTables | F2.5 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-1443 | 1443–1459 | renderTable | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1460 | 1460–1466 | decisionList | F3.2, F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P78aef573-1467 | 1467–1476 | DECISION_SHAPE | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按R18处理局部；不整块删 |
| P78aef573-1477 | 1477–1477 | ZONE_BEGIN | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1478 | 1478–1483 | ZONE_END | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1484 | 1484–1497 | zoneBlock | F4.3, F4.4, F2.2 | M25 | 按M25比较结论保留其必要职责 |
| P78aef573-1498 | 1498–1508 | zoneHandEdited | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1509 | 1509–1519 | zoneSpan | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1520 | 1520–1522 | EMPTY_SECTION_TEXT | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1523 | 1523–1535 | materialSubsectionName | F2.5 | M18 | 按M18比较结论保留其必要职责 |
| P78aef573-1536 | 1536–1562 | materialLinkTargets | F2.5, F3.2, F2.6 | M18 | 按M18比较结论保留其必要职责 |
| P78aef573-1563 | 1563–1604 | redactReviewExemptZones | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1605 | 1605–1634 | redactMaterialLinks | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1635 | 1635–1655 | groupedProblems | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1656 | 1656–1677 | withoutDiagrams | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1678 | 1678–1694 | FORM_HINT | F2.5, F3.2, F2.6 | M17, M18, M19, M20 | 按M17,M18,M19,M20比较结论保留其必要职责 |
| P78aef573-1695 | 1695–1779 | chapterProblems | F2.6 | M14 | 按M14比较结论保留其必要职责 |
| P78aef573-1780 | 1780–1799 | cmdCheck | F5.3, F5.4 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-1800 | 1800–1811 | check/⓪a 声明的来源都在 | F5.3, F2.6, F1.4, F2.1 | M07 | 按R13处理局部；不整块删 |
| P78aef573-1812 | 1812–1828 | check/⓪b 台账没在登记之后被换过 | F5.3, F2.6 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-1829 | 1829–1842 | check/① 章标题与顺序 | F5.3, F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-1843 | 1843–1861 | check/①b 大标题带需求编号 | F5.3, F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-1862 | 1862–1877 | check/③ 编号形态 | F5.3, F2.6 | M19 | 按R18处理局部；不整块删 |
| P78aef573-1878 | 1878–1921 | check/⑤ 决策登记字段齐备 | F5.3, F2.6 | M20 | 按M20比较结论保留其必要职责 |
| P78aef573-1922 | 1922–1971 | check/⑦ 规约判定表 | F5.3, F2.6, F2.5 | M17 | 按R07处理局部；不整块删 |
| P78aef573-1972 | 1972–2001 | check/④ 图片身份 | F5.3, F2.6, F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P78aef573-2002 | 2002–2003 | check/④ 图片身份 | F5.3, F2.6, F1.3 | M03 | 按R11处理局部；不整块删 |
| P78aef573-2004 | 2004–2008 | check/④ 图片身份 | F5.3, F2.6, F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P78aef573-2009 | 2009–2020 | check/④ 图片身份 | F5.3, F2.6, F1.3 | M03 | 按R11处理局部；不整块删 |
| P78aef573-2021 | 2021–2059 | check/④ 图片身份 | F5.3, F2.6, F1.3 | M03 | 按M03比较结论保留其必要职责 |
| P78aef573-2060 | 2060–2093 | check/⑨ 归档件四红线 | F5.3, F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-2094 | 2094–2127 | check/⑩ 语言红线 | F5.3, F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-2128 | 2128–2140 | check/⑪ 必要结构 | F5.3, F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-2141 | 2141–2183 | check/⑫ 附录结构 | F5.3, F2.6, F2.5 | M18, M19 | 按M18,M19比较结论保留其必要职责 |
| P78aef573-2184 | 2184–2194 | check/⑫ 附录结构 | F5.3, F2.6, F2.5 | M18, M19 | 按R15处理局部；不整块删 |
| P78aef573-2195 | 2195–2209 | check/⑫ 附录结构 | F5.3, F2.6, F2.5 | M18, M19 | 按M18,M19比较结论保留其必要职责 |
| P78aef573-2210 | 2210–2233 | check/⑫b spec 契约不丢行 | F5.3, F2.6, F2.5 | M17 | 按R07处理局部；不整块删 |
| P78aef573-2234 | 2234–2250 | check/⑫b spec 契约不丢行 | F5.3, F2.6, F2.5 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2251 | 2251–2270 | check/⑫a 非占位 | F5.3, F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-2271 | 2271–2351 | check/⑫c 形态 lint | F5.3, F2.6 | M18, M19 | 按M18,M19比较结论保留其必要职责 |
| P78aef573-2352 | 2352–2366 | check/⑬ 评审记录只含渲染语法 | F5.3, F2.6 | M20 | 按M20比较结论保留其必要职责 |
| P78aef573-2367 | 2367–2384 | check/⑮ AR 根下只有交付文档 | F5.3, F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-2385 | 2385–2411 | check/⑯ 成文依据仍然成立 | F5.3, F2.6 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-2412 | 2412–2458 | check/⑭ 交付门 | F5.3, F2.6 | M33 | 按M33比较结论保留其必要职责 |
| P78aef573-2459 | 2459–2479 | receiptRunner | F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P78aef573-2480 | 2480–2518 | danglingFigures | F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P78aef573-2519 | 2519–2549 | deliveryNextSteps | F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P78aef573-2550 | 2550–2607 | deliveryProblems | F5.6 | M33 | 按M33比较结论保留其必要职责 |
| P78aef573-2608 | 2608–2632 | cmdNumber | F2.6 | M19 | 按M19比较结论保留其必要职责 |
| P78aef573-2633 | 2633–2633 | PENDING_MARK | F2.4, F2.5 | M13, M17, M18 | 按M13,M17,M18比较结论保留其必要职责 |
| P78aef573-2634 | 2634–2635 | PENDING_RE | F2.4, F2.5 | M13, M17, M18 | 按M13,M17,M18比较结论保留其必要职责 |
| P78aef573-2636 | 2636–2640 | pendingMark | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-2641 | 2641–2654 | pendingChapters | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-2655 | 2655–2689 | chapterSpan | F2.4, F2.5, F4.3, F5.1 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-2690 | 2690–2690 | chapterSpan | F2.4, F2.5, F4.3, F5.1 | M13 | 按R18处理局部；不整块删 |
| P78aef573-2691 | 2691–2691 | chapterSpan | F2.4, F2.5, F4.3, F5.1 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-2692 | 2692–2708 | renderSlot | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-2709 | 2709–2729 | chapterSeed | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-2730 | 2730–2745 | appendixTableHeader | F2.5 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2746 | 2746–2767 | appendixProjection | F2.5, F4.3, F5.1 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2768 | 2768–2768 | appendixProjection | F2.5, F4.3, F5.1 | M17 | 按R18处理局部；不整块删 |
| P78aef573-2769 | 2769–2805 | appendixProjection | F2.5, F4.3, F5.1 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2806 | 2806–2816 | specNotApplicable | F2.4, F2.5 | M13, M17, M18 | 按M13,M17,M18比较结论保留其必要职责 |
| P78aef573-2817 | 2817–2868 | projectAppendix | F2.5 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2869 | 2869–2883 | cmdProject | F2.5, F4.3, F5.1 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2884 | 2884–2884 | cmdProject | F2.5, F4.3, F5.1 | M17 | 按R18处理局部；不整块删 |
| P78aef573-2885 | 2885–2885 | cmdProject | F2.5, F4.3, F5.1 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2886 | 2886–2925 | verdictSkeleton | F2.5 | M17 | 按M17比较结论保留其必要职责 |
| P78aef573-2926 | 2926–2939 | materialListSkeleton | F2.5 | M18 | 按M18比较结论保留其必要职责 |
| P78aef573-2940 | 2940–2941 | DRAFTS | F2.5 | M17, M18 | 按M17,M18比较结论保留其必要职责 |
| P78aef573-2942 | 2942–2951 | draftPath | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-2952 | 2952–2982 | requiredShapes | F2.4 | M14 | 按R18处理局部；不整块删 |
| P78aef573-2983 | 2983–2987 | relToRoot | F2.3, F5.3 | M11, M12, M32 | 按M11,M12,M32比较结论保留其必要职责 |
| P78aef573-2988 | 2988–2992 | relDisplayPath | F2.3, F5.3 | M11, M12, M32 | 按M11,M12,M32比较结论保留其必要职责 |
| P78aef573-2993 | 2993–3010 | showPath | F2.3, F5.3 | M11, M12, M32 | 按M11,M12,M32比较结论保留其必要职责 |
| P78aef573-3011 | 3011–3018 | shellArg | F2.3, F5.3, F7.2 | M11, M12, M32, M36 | 按M11,M12,M32,M36比较结论保留其必要职责 |
| P78aef573-3019 | 3019–3019 | CHAPTERS_DIR | F2.3, F5.3 | M11, M12, M32 | 按M11,M12,M32比较结论保留其必要职责 |
| P78aef573-3020 | 3020–3022 | SHARED_VIEW | F2.3, F5.3 | M11, M12, M32 | 按M11,M12,M32比较结论保留其必要职责 |
| P78aef573-3023 | 3023–3048 | scopeOf | F2.3, F5.3 | M11, M12, M32 | 按M11,M12,M32比较结论保留其必要职责 |
| P78aef573-3049 | 3049–3064 | sourceDrift | F5.3, F5.4 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-3065 | 3065–3107 | assemblyInputs | F5.3, F5.4 | M32 | 按M32比较结论保留其必要职责 |
| P78aef573-3108 | 3108–3118 | sourceTexts | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P78aef573-3119 | 3119–3129 | unitBlock | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P78aef573-3130 | 3130–3137 | declarationText | F2.4.2 | M14 | 按M14比较结论保留其必要职责 |
| P78aef573-3138 | 3138–3173 | chapterLead | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P78aef573-3174 | 3174–3221 | writeViews | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P78aef573-3222 | 3222–3228 | dispositionNote | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P78aef573-3229 | 3229–3246 | viewEntries | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P78aef573-3247 | 3247–3260 | draftFor | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-3261 | 3261–3286 | writeDrafts | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-3287 | 3287–3312 | draftBody | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-3313 | 3313–3317 | imageRef | F2.4.2, F1.3 | M03, M14, M15, M16 | 按M03,M14,M15,M16比较结论保留其必要职责 |
| P78aef573-3318 | 3318–3334 | readViews | F2.3 | M12 | 按M12比较结论保留其必要职责 |
| P78aef573-3335 | 3335–3353 | viewDrift | F2.3 | M12 | 按M12比较结论保留其必要职责 |
| P78aef573-3354 | 3354–3364 | same | F2.3 | M12 | 按M12比较结论保留其必要职责 |
| P78aef573-3365 | 3365–3400 | cmdSkeleton | F2.3 | M11, M12 | 按M11,M12比较结论保留其必要职责 |
| P78aef573-3401 | 3401–3406 | chapterIdOf | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-3407 | 3407–3419 | specUsable | F5.2 | M31 | 按M31比较结论保留其必要职责 |
| P78aef573-3420 | 3420–3497 | cmdPrepare | F5.2 | M31 | 按M31比较结论保留其必要职责 |
| P78aef573-3498 | 3498–3552 | declaredStructureProblems | F2.4.2 | M14 | 按M14比较结论保留其必要职责 |
| P78aef573-3553 | 3553–3559 | stripGuidance | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-3560 | 3560–3580 | stripOwnHeading | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-3581 | 3581–3585 | cmdReviewTask | F5.5, F5.7 | M33, M34 | 按M33,M34比较结论保留其必要职责 |
| P78aef573-3586 | 3586–3674 | cmdChapter | F2.4 | M13 | 按M13比较结论保留其必要职责 |
| P78aef573-3675 | 3675–3683 | requireStoryFirst | F3.2, F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P78aef573-3684 | 3684–3709 | cmdBuild | F3.2, F3.1 | M20 | 按M20比较结论保留其必要职责 |
| P78aef573-3710 | 3710–3726 | main | F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |
| P78aef573-3727 | 3727–3727 | R01 / if (args.command === 'init') cmdInit(ctx); | F3.2, F5.3, F2.1 | M07, M08, M20, M32 | 按R01处理局部；不整块删 |
| P78aef573-3728 | 3728–3740 | R01 / if (args.command === 'init') cmdInit(ctx); | F3.2, F5.3, F2.1 | M07, M08, M20, M32 | 按M07,M08,M20,M32比较结论保留其必要职责 |
| P78aef573-3741 | 3741–3745 | if (process.argv&#91;1&#93; &amp;&amp; path.resolve(process.argv&#91;1&#93;) === fileURLToPath(import.meta.ur | F3.2, F5.3 | M20, M32 | 按M20,M32比较结论保留其必要职责 |

<a id="P5d48ac7f"></a>

## skills/story/scripts/core/story-sources.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P5d48ac7f-1 | 1–11 | 文件头/元信息 | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-12 | 12–12 | import path from 'node:path'; | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-13 | 13–15 | import crypto from 'node:crypto'; | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-16 | 16–17 | FENCE | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-18 | 18–19 | ATX | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-20 | 20–21 | HTML_COMMENT | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-22 | 22–41 | INLINE_REF | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-42 | 42–71 | splitUnits | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P5d48ac7f-72 | 72–89 | headingsOf | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P5d48ac7f-90 | 90–99 | ancestors | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P5d48ac7f-100 | 100–110 | trimRange | F2.1, F1.4 | M04, M07, M08 | 按M04,M07,M08比较结论保留其必要职责 |
| P5d48ac7f-111 | 111–116 | sliceRange | F2.1, F1.4 | M04, M07, M08 | 按M04,M07,M08比较结论保留其必要职责 |
| P5d48ac7f-117 | 117–124 | unitId | F2.1, F1.4 | M04, M07, M08 | 按M04,M07,M08比较结论保留其必要职责 |
| P5d48ac7f-125 | 125–133 | parseUnitId | F2.1, F1.4 | M04, M07, M08 | 按M04,M07,M08比较结论保留其必要职责 |
| P5d48ac7f-134 | 134–142 | sourceDigest | F2.1, F2.2, F2.3, F2.4.2, F7.2 | M08 | 按M08比较结论保留其必要职责 |
| P5d48ac7f-143 | 143–164 | refsIn | F2.1, F1.4 | M04, M07, M08 | 按M04,M07,M08比较结论保留其必要职责 |
| P5d48ac7f-165 | 165–183 | retarget | F2.1, F2.2, F2.3, F2.4.2, F7.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16, M36 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16,M36比较结论保留其必要职责 |
| P5d48ac7f-184 | 184–202 | relocate | F2.1, F1.4 | M08 | 按M08比较结论保留其必要职责 |
| P5d48ac7f-203 | 203–232 | indexLine | F2.3 | M11, M12 | 按M11,M12比较结论保留其必要职责 |
| P5d48ac7f-233 | 233–257 | contextRefs | F2.3 | M08 | 按M08比较结论保留其必要职责 |
| P5d48ac7f-258 | 258–309 | chapterView | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P5d48ac7f-310 | 310–323 | sharedView | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P5d48ac7f-324 | 324–333 | norm | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-334 | 334–350 | tableHeaders | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-351 | 351–355 | sectionKey | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P5d48ac7f-356 | 356–369 | flatSections | F2.2 | M09 | 按M09比较结论保留其必要职责 |
| P5d48ac7f-370 | 370–390 | placements | F2.2 | M09 | 按M09比较结论保留其必要职责 |
| P5d48ac7f-391 | 391–423 | effectiveDispositions | F2.2 | M09 | 按M09比较结论保留其必要职责 |
| P5d48ac7f-424 | 424–461 | replacedByProblems | F2.2 | M09, M10 | 按M09,M10比较结论保留其必要职责 |
| P5d48ac7f-462 | 462–487 | assignUnits | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P5d48ac7f-488 | 488–499 | push | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-500 | 500–520 | relatedTargets | F2.3 | M11 | 按M11比较结论保留其必要职责 |
| P5d48ac7f-521 | 521–527 | DIAGRAM_TYPES | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-528 | 528–557 | declarationProblems | F2.4.2 | M14 | 按M14比较结论保留其必要职责 |
| P5d48ac7f-558 | 558–573 | structureSeed | F2.4.2 | M14 | 按M14比较结论保留其必要职责 |
| P5d48ac7f-574 | 574–592 | fencesOf | F2.4.2 | M14, M15, M16 | 按M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-593 | 593–608 | sameFile | F2.1, F2.2, F2.3, F2.4.2, F7.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16, M36 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16,M36比较结论保留其必要职责 |
| P5d48ac7f-609 | 609–649 | structureProblems | F2.4.2 | M14 | 按M14比较结论保留其必要职责 |
| P5d48ac7f-650 | 650–684 | locateSection | F2.4.2 | M14 | 按M14比较结论保留其必要职责 |
| P5d48ac7f-685 | 685–719 | templateReadable | F2.2 | M10 | 按M10比较结论保留其必要职责 |
| P5d48ac7f-720 | 720–727 | isTodo | F2.1, F2.2, F2.3, F2.4.2 | M07, M08, M09, M10, M11, M12, M14, M15, M16 | 按M07,M08,M09,M10,M11,M12,M14,M15,M16比较结论保留其必要职责 |
| P5d48ac7f-728 | 728–761 | templateAssemblable | F2.2 | M10 | 按M10比较结论保留其必要职责 |

<a id="Pddb5eac2"></a>

## skills/story/scripts/core/story_flow.py

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pddb5eac2-1 | 1–53 | """story_flow.py — init→spec 流程契约（&#96;AR/story-src/story-flow.json&#96;）的**唯一写入者**。 | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-54 | 54–55 | from __future__ import annotations | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-56 | 56–56 | import argparse | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-57 | 57–57 | import json | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-58 | 58–58 | import re | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-59 | 59–59 | import shutil | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-60 | 60–60 | import subprocess | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-61 | 61–61 | import sys | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-62 | 62–62 | from datetime import datetime, timezone | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-63 | 63–63 | from hashlib import sha256 | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-64 | 64–65 | from pathlib import Path | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-66 | 66–66 | import import_sources | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-67 | 67–68 | import materials | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-69 | 69–69 | SCHEMA | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-70 | 70–70 | CONTRACT | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-71 | 71–72 | ANALYSIS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-73 | 73–74 | SPLIT_PARTS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-75 | 75–76 | GATE_OPTIONS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-77 | 77–79 | POSITIONING | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-80 | 80–80 | SCOPE_OPTIONS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-81 | 81–84 | DESIGN | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-85 | 85–87 | DESIGN_DRAFT | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-88 | 88–90 | AR_SOURCES | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-91 | 91–98 | S4_STEPS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-99 | 99–104 | STORY_SRC_FROZEN | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-105 | 105–108 | GATES | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-109 | 109–110 | STORY_CONTRACT | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-111 | 111–116 | CARRY_ALL | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-117 | 117–118 | ACTORS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-119 | 119–124 | WHY_ALL_OPTIONS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-125 | 125–127 | SCOPE_SOURCES | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-128 | 128–131 | FlowError | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-132 | 132–143 | material_options | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-144 | 144–146 | _MATERIAL_OPTIONS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-147 | 147–149 | MATERIAL_CHOICES | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-150 | 150–152 | MATERIAL_REQUEST_KEYS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-153 | 153–156 | log | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-157 | 157–160 | now | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-161 | 161–175 | ledger_digest | F5.3, F5.4, F7.2 | M32, M36 | 按M32,M36比较结论保留其必要职责 |
| Pddb5eac2-176 | 176–187 | load | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-188 | 188–193 | save | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-194 | 194–202 | require | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-203 | 203–207 | consume_sidecar | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-208 | 208–220 | read_sidecar | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-221 | 221–227 | POSITIONING_FIELDS | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-228 | 228–275 | read_positioning | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-276 | 276–329 | read_scope_options | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-330 | 330–342 | chosen_dimension | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-343 | 343–356 | split_carrier_options | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-357 | 357–369 | sidecar_gate | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-370 | 370–439 | read_gate_options | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-440 | 440–448 | after_complete | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-449 | 449–560 | cmd_round | F1.4 | M04 | 按M04比较结论保留其必要职责 |
| Pddb5eac2-561 | 561–581 | frozen_inbox_note | F5.2 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-582 | 582–603 | material_state | F1.4 | M04 | 按M04比较结论保留其必要职责 |
| Pddb5eac2-604 | 604–677 | read_split_parts | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-678 | 678–807 | cmd_decide | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-808 | 808–818 | round_gates | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-819 | 819–825 | last_gate | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-826 | 826–838 | settled_this_round | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-839 | 839–843 | SPEC_STAGE_AUTHORIZATION | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-844 | 844–856 | SPEC_STAGE_ORDER | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-857 | 857–899 | spec_stage_step | F5.2, F5.1 | M31 | 按R08处理局部；不整块删 |
| Pddb5eac2-900 | 900–901 | spec_stage_step | F5.2, F5.1 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-902 | 902–944 | sidecar_shape | F5.2 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-945 | 945–972 | material_gate_state | F5.2 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-973 | 973–978 | frozen_tail | F5.2 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-979 | 979–1001 | next_step | F5.2, F5.1 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-1002 | 1002–1002 | next_step | F5.2, F5.1 | M31 | 按R08处理局部；不整块删 |
| Pddb5eac2-1003 | 1003–1026 | next_step | F5.2, F5.1 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-1027 | 1027–1088 | scope_step | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| Pddb5eac2-1089 | 1089–1122 | cmd_reopen | F5.4 | M32 | 按M32比较结论保留其必要职责 |
| Pddb5eac2-1123 | 1123–1156 | cmd_status | F5.2 | M31 | 按M31比较结论保留其必要职责 |
| Pddb5eac2-1157 | 1157–1176 | read_ids | F1.1 | M01 | 按M01比较结论保留其必要职责 |
| Pddb5eac2-1177 | 1177–1212 | ar_design_skeleton | F1.1 | M01 | 按M01比较结论保留其必要职责 |
| Pddb5eac2-1213 | 1213–1262 | cmd_init | F1.1 | M01 | 按M01比较结论保留其必要职责 |
| Pddb5eac2-1263 | 1263–1265 | S4_HEADING | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-1266 | 1266–1283 | resolve_candidate | F1.7 | M06 | 按M06比较结论保留其必要职责 |
| Pddb5eac2-1284 | 1284–1300 | section_numbers | F1.7 | M06 | 按M06比较结论保留其必要职责 |
| Pddb5eac2-1301 | 1301–1309 | is_ar_skeleton | F1.7 | M06 | 按M06比较结论保留其必要职责 |
| Pddb5eac2-1310 | 1310–1329 | candidate_problems | F1.7 | M06 | 按M06比较结论保留其必要职责 |
| Pddb5eac2-1330 | 1330–1352 | prior_ar | F1.7 | M06 | 按M06比较结论保留其必要职责 |
| Pddb5eac2-1353 | 1353–1484 | cmd_complete | F1.7 | M06 | 按M06比较结论保留其必要职责 |
| Pddb5eac2-1485 | 1485–1485 | STORY | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-1486 | 1486–1488 | REVIEW | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-1489 | 1489–1573 | cmd_story | F5.3, F5.4 | M32 | 按M32比较结论保留其必要职责 |
| Pddb5eac2-1574 | 1574–1618 | cmd_archived | F3.3 | M21 | 按M21比较结论保留其必要职责 |
| Pddb5eac2-1619 | 1619–1677 | main | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |
| Pddb5eac2-1678 | 1678–1679 | if __name__ == "__main__": | F1.4, F1.6, F1.7, F5.2, F5.3, F5.4 | M04, M05, M06, M31, M32 | 按M04,M05,M06,M31,M32比较结论保留其必要职责 |

<a id="P597ffdca"></a>

## skills/story/scripts/README.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P597ffdca-1 | 1–2 | &#96;scripts/&#96; 的两层：谁写的，谁维护 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-3 | 3–4 | &#96;scripts/&#96; 的两层：谁写的，谁维护 / 这一层不放独立文件，只有两个目录。**一个文件归谁，看它在哪个目录**——不看后缀、不看文件头自述、不靠任何推断。 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-5 | 5–9 | &#96;scripts/&#96; 的两层：谁写的，谁维护 / &#124; 目录 &#124; 归谁 &#124; 升级时 &#124; | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-10 | 10–11 | &#96;scripts/&#96; 的两层：谁写的，谁维护 / 新增的公共脚本一律进 &#96;core/&#96;。往 &#96;scripts/&#96; 根下放文件会被 &#96;adapt-scan --check ⑧&#96; 拦下：放在 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-12 | 12–13 | &#96;adapters/&#96; 里那三个的输出合同 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-14 | 14–15 | &#96;adapters/&#96; 里那三个的输出合同 / 它们是需求系统的对接层。本仓这三份是**替身**（本地目录模拟需求系统），部署环境各自实现自己那份，从不调用扩展内容。 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-16 | 16–17 | &#96;adapters/&#96; 里那三个的输出合同 / 合同的真源是每个文件自己的 docstring——**改实现时先读它，那是唯一依据**： | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-18 | 18–23 | &#96;adapters/&#96; 里那三个的输出合同 / &#124; 文件 &#124; 干什么 &#124; 合同要点 &#124; | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-24 | 24–25 | &#96;adapters/&#96; 里那三个的输出合同 / 写盘落点也是合同的一部分：&#96;AR/design.md&#96;、&#96;AR/review.md&#96;、&#96;AR/detail.json&#96;、&#96;AR/.rev | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-26 | 26–27 | 换实现时要守住的两件 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P597ffdca-28 | 28–29 | 换实现时要守住的两件 / 1. **CLI 与 stdout 形态不变**：流程脚本按上表解析结果，多一层结构、少一个字段都会让调用方读到别的东西； | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |

<a id="P7729a47e"></a>

## skills/story/SKILL.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P7729a47e-1 | 1–5 | 文件头/元信息 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-6 | 6–7 | story — 需求开发流程编排 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-8 | 8–10 | story — 需求开发流程编排 / 本文件只讲**链条怎么走、关卡怎么判、产物各是什么**。 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-11 | 11–13 | story — 需求开发流程编排 / &#96;/story adapt&#96; 不在本文件——它是把本扩展装到／升级到别的工程的工程运维动作， | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-14 | 14–15 | 链条 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-16 | 16–29 | 链条 / 示例或代码块 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-30 | 30–35 | 链条 / **&#96;/story &lt;AR&gt;&#96; 的启动语义 = 做到 spec 闭环并通过交付门**（归档送审与进入 plan 由用户在交付门之后选）。 | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-36 | 36–38 | 链条 / **位置由契约回答，不靠回忆**：&#96;story_flow.py status --feature &lt;AR&gt;&#96; 读契约给出 &#96;next&#96; | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-39 | 39–41 | 链条 / **先做完对应产物，再问对应问题**：盘点完材料才问还缺什么，分析完范围才问范围怎么定 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-42 | 42–43 | 各步的规则在哪 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-44 | 44–55 | 各步的规则在哪 / &#124; 步 &#124; 规则 &#124; | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-56 | 56–57 | 推进契约 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-58 | 58–59 | 推进契约 / **这一节是本扩展里推进授权的唯一定义**，各阶段须知与作业书只引用它、不复述。 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-60 | 60–61 | 授权分两层 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-62 | 62–63 | 授权分两层 / &#124; 层 &#124; 谁说了算 &#124; 怎么推进 &#124; | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-64 | 64–64 | R04 / &#124; **story 流程段内**：S1→S4、spec 阶段内的成文与登记、S5 归档 &#124; 本节 &#124; 用户启动 &#96;/story&#96; 即构成明示 | F3.3, F5.4, F5.6 | M21, M32, M33 | 按R04处理局部；不整块删 |
| P7729a47e-65 | 65–66 | R04 / &#124; **story 流程段内**：S1→S4、spec 阶段内的成文与登记、S5 归档 &#124; 本节 &#124; 用户启动 &#96;/story&#96; 即构成明示 | F3.3, F5.4, F5.6 | M21, M32, M33 | 按M21,M32,M33比较结论保留其必要职责 |
| P7729a47e-67 | 67–69 | 授权分两层 / **story 契约 &#96;next&#96; 覆盖的就是第一层**：&#96;init → 材料 → 关卡 → design.md → spec 闭环 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-70 | 70–73 | 授权分两层 / **第二层不另造一套授权，也不替它问。** framework 的推进策略解析的是**用户消息**， | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-74 | 74–77 | 授权分两层 / **S4 收口之后直接进 spec，不问。** 本轮的终点在 &#96;/story&#96; 启动时就声明了（见上「启动语义」）： | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-78 | 78–79 | 停等点：只有两处，都无条件 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-80 | 80–80 | R04 / 本扩展**新增的**停等点只有这两处，此外一律不问： | F5.1, F5.2, F5.6 | M30, M31, M33 | 按R04处理局部；不整块删 |
| P7729a47e-81 | 81–81 | R04 / 本扩展**新增的**停等点只有这两处，此外一律不问： | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-82 | 82–86 | 停等点：只有两处，都无条件 / &#124; # &#124; 停在哪 &#124; 什么时候停 &#124; | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-87 | 87–90 | 停等点：只有两处，都无条件 / **两处都是无条件的。** 「要不要停」不由判断材料齐不齐、范围有没有变来决定—— | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-91 | 91–93 | 停等点：只有两处，都无条件 / **这一级请人陈述的是事实**：料放进去了，或者现有材料就是全部。够不够由你盘点、 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-94 | 94–100 | 停等点：只有两处，都无条件 / **导入之后再问，问的是「还缺什么」**。人回哪一项，收件箱里的原件都会被导入—— | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-101 | 101–103 | 停等点：只有两处，都无条件 / 侧车必须写明是给哪一级摆的——三级共用一个文件名，不写明的话，你为范围关卡摆的选项 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-104 | 104–106 | 停等点：只有两处，都无条件 / 「门禁报错了要不要修」「check 过了下一步做什么」「进 harness 还是进 verifier」 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-107 | 107–113 | 停等点：只有两处，都无条件 / **verifier PASS 之后的顺序是固定的**：&#96;check-receipt&#96; → | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-114 | 114–115 | 停等消息怎么写：三段，不超过 12 行 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-116 | 116–117 | 停等消息怎么写：三段，不超过 12 行 / 人在这里只做一个动作——选一项。让他为此读三十行，就是把成本从你这边挪到他那边。 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-118 | 118–124 | 停等消息怎么写：三段，不超过 12 行 / 示例或代码块 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-125 | 125–128 | 停等消息怎么写：三段，不超过 12 行 / **不放**：材料总表（清单在 &#96;init-analysis.md&#96; 里，要看他会去看）、已经说过的事、 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-129 | 129–131 | 停等消息怎么写：三段，不超过 12 行 / 需要展开的证据留在产物里：他要细节时会去读 &#96;AR/story-src/init-analysis.md&#96;， | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-132 | 132–133 | 失败出口（不是确认点） | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-134 | 134–136 | 失败出口（不是确认点） / 停下来说「我修不动了」不是问人要授权，是**报告修不动、请人接手**。它有前提， | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-137 | 137–137 | R03 / &gt; 同一判据类在 &#96;story-build check&#96; 的**连续三次运行**里都报了，且三次之间产物 | F5.1, F5.2, F5.6, F5.4 | M30, M31, M32, M33 | 按R03处理局部；不整块删 |
| P7729a47e-138 | 138–139 | R03 / &gt; 同一判据类在 &#96;story-build check&#96; 的**连续三次运行**里都报了，且三次之间产物 | F5.1, F5.2, F5.6, F5.4 | M30, M31, M32, M33 | 按M30,M31,M32,M33比较结论保留其必要职责 |
| P7729a47e-140 | 140–143 | 失败出口（不是确认点） / 不满足这个前提就不是合法停等——**照报错文案修，改完重跑**。 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-144 | 144–145 | 既有确认点（不计入上面两处） | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-146 | 146–148 | 既有确认点（不计入上面两处） / 归档、恢复这类不可逆或覆盖线上内容的操作，有它们**既有的**确认点。 | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-149 | 149–150 | 成文到闭环的衔接链 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-151 | 151–152 | 成文到闭环的衔接链 / &#96;story-build check&#96; 通过之后，到阶段闭环是**一条义务链，链内没有停等点**： | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-153 | 153–153 | 成文到闭环的衔接链 / 示例或代码块 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-154 | 154–154 | R05 / check 通过 → 取本阶段作者要求 → 写产物 → 主 agent 自己跑 harness | F5.1, F5.2, F5.6 | M30, M31, M33 | 按R05处理局部；不整块删 |
| P7729a47e-155 | 155–157 | R05 / check 通过 → 取本阶段作者要求 → 写产物 → 主 agent 自己跑 harness | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-158 | 158–162 | 成文到闭环的衔接链 / **作者要求怎么取**：原则页是 &#96;doc/extensions/hooks/&lt;阶段&gt;/author.md&#96;（六个阶段各一份）； | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-163 | 163–165 | 成文到闭环的衔接链 / &#96;check&#96; FAIL 时按报错文案修，改完重跑，直到通过或触发**失败出口**（见上，有可核前提）。 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-166 | 166–167 | 初始化 | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-168 | 168–170 | 初始化 / - **输入**：AR 单号 + &#96;&lt;mcp-token&gt;&#96;（取法见「需求系统 Token」） | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-171 | 171–175 | 初始化 / 示例或代码块 | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-176 | 176–177 | 初始化 / **② 是骨架的唯一写入者**：缺什么补什么，已有的一律不动，重跑安全。 | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-178 | 178–181 | 初始化 / **看骨架判材料**：&#96;RR/prd.md&#96;、&#96;SR/design.md&#96; 是正文还是占位件（占位件正文写着 | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-182 | 182–186 | 初始化 / **没有需求系统单据时**（问题单、别人发来的需求文档）：入口不变，仍是 &#96;/story init &lt;编号&gt;&#96;。 | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-187 | 187–188 | 归档 | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-189 | 189–192 | 归档 / - **前置**：spec 阶段已闭环（成文态 &#96;status = story_written&#96; 在那时登记），&#96;AR/story.md | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-193 | 193–198 | 归档 / 示例或代码块 | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-199 | 199–201 | 归档 / **③ 登记之后**，&#96;AR/review.md&#96; **归人所有——只备份，不重建**，评审人的线上批注与 | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-202 | 202–204 | 归档 / **决策件带着未勾的议题去归档是常态路径**——评审的形态就是评审人在线上批注表态， | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-205 | 205–206 | 恢复 | F3.3, F5.4 | M21, M32 | 按M21,M32比较结论保留其必要职责 |
| P7729a47e-207 | 207–209 | 恢复 / &#96;node .../story.js restore &lt;AR&gt; &lt;mcp-token&gt;&#96;——把需求系统上的正文恢复到上一版， | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-210 | 210–211 | 检视 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P7729a47e-212 | 212–213 | 检视 / &#96;/story review &lt;AR&gt;&#96; 把评审人在系统上留下的反馈拉回来，写入 &#96;AR/review.md&#96;（先备份原件）。 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P7729a47e-214 | 214–218 | 检视 / 评审表态由评审人填写——**你不代填表态、不动人工区**。人可能在系统上批注，也可能直接改本地 | F3.4 | M21 | 按M21比较结论保留其必要职责 |
| P7729a47e-219 | 219–220 | 交互关卡语义（所有关卡统一适用） | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-221 | 221–223 | 交互关卡语义（所有关卡统一适用） / **关卡是讨论的收敛点，不是选择题的交卷处。** 决策权在人、笔在 AI—— | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-224 | 224–229 | 交互关卡语义（所有关卡统一适用） / **呈现**：摆出分析结论与可选方案，每项写清它意味着什么。有确认组件就用组件， | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-230 | 230–231 | 交互关卡语义（所有关卡统一适用） / **人回应之后**只有两条路： | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-232 | 232–237 | 交互关卡语义（所有关卡统一适用） / - **回应对上了某一项** → 跑 &#96;story_flow.py decide&#96; 落契约（&#96;basis&#96; 引他的原话），按 &#96;next | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-238 | 238–239 | 交互关卡语义（所有关卡统一适用） / **三条底线**： | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-240 | 240–244 | 交互关卡语义（所有关卡统一适用） / 1. **人确认前不记录、不往下走。** 你需要写一段推理才能把他的话对上某个选项，说明还没确认，去问； | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-245 | 245–247 | 交互关卡语义（所有关卡统一适用） / **选项集必须落进契约**——它是给人事后推翻用的。四条记录纪律（选项集、&#96;--basis&#96;、 | F1.6 | M05 | 按M05比较结论保留其必要职责 |
| P7729a47e-248 | 248–249 | 产物定位 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-250 | 250–264 | 产物定位 / &#124; 产物 &#124; 回答什么 &#124; | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-265 | 265–266 | 产物定位 / &#96;spec&#96; 与 &#96;review&#96; 是 spec 阶段**并列**交付物，不是上下游——前者 AI 写、后者人写。 | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-267 | 267–271 | 产物定位 / &#124; &#124; &#96;AR/design.md&#96; &#124; &#96;AR/story.md&#96; &#124; | F5.1, F5.2, F5.6 | M30, M31, M33 | 按M30,M31,M33比较结论保留其必要职责 |
| P7729a47e-272 | 272–273 | 需求系统 Token | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-274 | 274–275 | 需求系统 Token / &#96;story.js&#96; 的每条命令都要 &#96;&lt;mcp-token&gt;&#96;。按顺序取，取到即用： | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-276 | 276–283 | 需求系统 Token / 1. 跑 &#96;node doc/extensions/skills/story/scripts/adapters/token.js&#96;——e | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P7729a47e-284 | 284–285 | 需求系统 Token / 要 token 时对用户说明：需要需求系统的访问 token 才能拉取需求单，请到需求系统的 | F1.1, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |

<a id="P685a03be"></a>

## skills/story/templates/inbox-readme.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P685a03be-1 | 1–2 | 上游材料收件箱 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P685a03be-3 | 3–5 | 上游材料收件箱 / 需求系统里 PRD / SE 设计还没归档时，把手上的材料放进**本目录**， | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P685a03be-6 | 6–7 | 放什么 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P685a03be-8 | 8–13 | 放什么 / &#124; 类型 &#124; 格式 &#124; 会发生什么 &#124; | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P685a03be-14 | 14–17 | 放什么 / 判断标准是**文件本身读不读得开**，不是扩展名。二进制格式（&#96;.pdf&#96; / &#96;.doc&#96; 等） | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P685a03be-18 | 18–19 | 几条约定 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P685a03be-20 | 20–26 | 几条约定 / - **文件名即章节标题**：转换后每份材料成为正文里的一节，标题就是文件名（不含扩展名）； | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |
| P685a03be-27 | 27–28 | 几条约定 / &gt; 导入会**整体覆盖**对应的上游正文（人工放的材料视为权威版本）；被覆盖的旧内容 | F1.1, F1.2, F6.3 | M01, M02, M35 | 按M01,M02,M35比较结论保留其必要职责 |

<a id="Pa8025ed4"></a>

## skills/story/templates/plan-sections.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| Pa8025ed4-1 | 1–3 | 文件头/元信息 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-4 | 4–7 | 前言 / 用途：plan 是三类知识里设计模式**唯一的选型点**，也是规约义务**唯一的落点**—— | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-8 | 8–13 | 前言 / ── 位置就是语义 ──────────────────────────────────────────────── | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-14 | 14–17 | 前言 / ── 判据一句话 ────────────────────────────────────────────────── | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-18 | 18–25 | 前言 / ── 三类知识的消费语义不同，不要混用同一套词 ────────────────────── | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-26 | 26–27 | 知识决策（设计输入） | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-28 | 28–30 | 知识决策（设计输入） / &lt;!-- 结构判据：本章必须出现在第一个设计章（如「## 1. 模块架构图」）之前；三节都要在， | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-31 | 31–32 | 设计模式选型 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-33 | 33–37 | 设计模式选型 / &lt;!-- 逐个候选单元一行。候选来自 spec §11 的登记；选或不选都要结论。 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-38 | 38–40 | 设计模式选型 / **spec §11 命中的候选，这里必须逐条有行**——漏掉一行，那条候选就在闭环内 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-41 | 41–46 | 设计模式选型 / **不选是一个表态有后果的正式决策**，理由列不能空：写清它是**业务信号的反证** | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-47 | 47–49 | 设计模式选型 / &#124; 适用单元 &#124; 候选 &#124; 选 / 不选 &#124; 实例名 &#124; 理由 &#124; | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-50 | 50–51 | 规约义务 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-52 | 52–54 | 规约义务 / &lt;!-- spec §10 的每条命中条目在这里都要变成一条有落点的义务，一条目一行，不要一行塞多条。 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-55 | 55–57 | 规约义务 / &#124; 条目编号 &#124; 本次要落实成什么 &#124; 落点实体 &#124; 承载设计章 &#124; | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-58 | 58–59 | 项目知识影响 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-60 | 60–62 | 项目知识影响 / &lt;!-- 按本方案**新增的能力**逐项写：复用了哪个登记入口 / 未复用的理由 / 与登记不符之处。 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-63 | 63–65 | 项目知识影响 / &#124; 新增能力 &#124; 复用了什么 &#124; 未复用的理由 &#124; 与登记不符之处 &#124; | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-66 | 66–67 | 项目知识影响 / --- | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-68 | 68–69 | &#96;contracts.yaml&#96;：义务挂在实体上 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-70 | 70–71 | &#96;contracts.yaml&#96;：义务挂在实体上 / 题材中性，只看形态。**每条命中的规约，挂一条 &#96;must&#96; 到扛着它的那个实体上**： | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-72 | 72–109 | &#96;contracts.yaml&#96;：义务挂在实体上 / 示例或代码块 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-110 | 110–111 | &#96;must&#96; 只能挂在这五处 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-112 | 112–114 | &#96;must&#96; 只能挂在这五处 / &#96;data_models&#91;&#93;.fields&#91;&#93;&#96; / &#96;interfaces&#91;&#93;.methods&#91;&#93;&#96; / &#96;components&#91;&#93;&#96; | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-115 | 115–118 | &#96;must&#96; 只能挂在这五处 / 挂在实体顶层（&#96;data_models.X&#96; 而不是它的 &#96;fields&#91;&#93;&#96;）或别的集合上，门禁会拦—— | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-119 | 119–120 | 三个字段各写什么 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-121 | 121–126 | 三个字段各写什么 / &#124; 字段 &#124; 写什么 &#124; 不算数的写法 &#124; | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-127 | 127–129 | 三个字段各写什么 / &#96;verify&#96; 同时是**四阶段分派的单源**，不另建第二份分派表：coding 执行探针、review 逐条复核、 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-130 | 130–131 | 有落点 vs 没落点 | F4.5 | M27 | 按M27比较结论保留其必要职责 |
| Pa8025ed4-132 | 132–136 | 有落点 vs 没落点 / - ❌ 在 &#96;plan.md&#96; 里写一段「本需求要落实流程标识与步骤标识」，契约里没有对应字段 | F4.5 | M27 | 按M27比较结论保留其必要职责 |

<a id="P12ec7582"></a>

## skills/story/templates/spec-sections.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P12ec7582-1 | 1–3 | 文件头/元信息 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-4 | 4–7 | 前言 / 用途：core spec 模板缺少交付流程要求 spec 承载的「接口契约 / 存储 / 配置 / 埋点 / 依赖」， | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-8 | 8–12 | 前言 / **哪几章对谁生效**：§10 与 §11 是知识判定的出口，对**所有需求**生效——判定产生的 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-13 | 13–19 | 前言 / 三章各回答一个不同的问题，**互不并入**： | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-20 | 20–22 | 前言 / ── spec 是什么：交付给代码的要求说明书 ────────────────────────────── | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-23 | 23–26 | 前言 / spec 各章（§2 场景 / §3 功能清单 / §4 页面 / §5 流程 / §6 异常 / §7 非功能 / §8 验收） | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-27 | 27–28 | 前言 / 内容三分，各有唯一归属： | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-29 | 29–34 | 前言 / &#124; 类别 &#124; 例子 &#124; 去哪 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-35 | 35–36 | 前言 / 判定的推演过程是 AI 的工作底稿，三份文档都不写。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-37 | 37–41 | 前言 / ── 形式：一律表格，不按条目数切换 ───────────────────────────────────── | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-42 | 42–49 | 前言 / ── 防重复 ──────────────────────────────────────────────────────── | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-50 | 50–51 | 前言 / 两种标记产物中都不应残留：&lt;!- 注释 -&gt; 生成时删除；{ … } 须替换为实际内容。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-52 | 52–58 | 前言 / ── 元叙述分层 ────────────────────────────────────────────────── | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-59 | 59–63 | 前言 / 可见正文引用工程规约的形态见 reference/evidence-rules.md §4.2 证据表（spec 与 story | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-64 | 64–65 | 9. 技术契约 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-66 | 66–71 | 9. 技术契约 / &lt;!-- 本章是**给下游 AI 用的要求**：plan 据此编码、test-plan 据此出用例。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-72 | 72–73 | 9.1 端云接口 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-74 | 74–76 | 9.1 端云接口 / &lt;!-- 表头固定。错误码列写新增/变更的错误码，无则写「无新增」。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-77 | 77–80 | 9.1 端云接口 / &#124; 云侧接口 &#124; 新增·复用·变更 &#124; 入参 → 出参 &#124; 错误码 &#124; 代码现状 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-81 | 81–82 | 9.2 数据存储 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-83 | 83–84 | 9.2 数据存储 / &lt;!-- 表头固定。**不写** schema 三问（→ 结论并入 §7.2 兼容性要求）、不写加密要求（→ §7.3 安全性要求）。  | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-85 | 85–88 | 9.2 数据存储 / &#124; 键名/表名 &#124; 介质 &#124; 值结构 &#124; 有效期 &#124; 用途 &#124; 代码现状 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-89 | 89–90 | 9.3 配置项 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-91 | 91–93 | 9.3 配置项 / &lt;!-- 表头固定。**不写**必要性评估（→ 决策件，那是决策论证）。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-94 | 94–97 | 9.3 配置项 / &#124; 配置项 &#124; 默认值 &#124; 关闭态行为 &#124; 历史版本兼容 &#124; 代码现状 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-98 | 98–99 | 9.4 埋点 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-100 | 100–101 | 9.4 埋点 / &lt;!-- 表头固定。通知谁属行动项（→ 决策件跨团队协同），本表不写。 --&gt; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-102 | 102–105 | 9.4 埋点 / &#124; 事件 &#124; 触发节点 &#124; 归属 &#124; 报表影响 &#124; 代码现状 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-106 | 106–107 | 9.5 依赖变更 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-108 | 108–109 | 9.5 依赖变更 / &lt;!-- 表头固定。无新增/升级时写一行「不涉及：&lt;当前依赖项清单&gt;」。 --&gt; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-110 | 110–113 | 9.5 依赖变更 / &#124; 依赖 &#124; 变更 &#124; 体积影响 &#124; 兼容风险 &#124; 代码现状 &#124; | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-114 | 114–115 | 10. 规约约束要求 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-116 | 116–119 | 10. 规约约束要求 / &lt;!-- 这一章的正文**由机器生成**，不手写：你编辑的是 &#96;spec/knowledge-use.yaml&#96;。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-120 | 120–126 | 10. 规约约束要求 / **怎么写 requirement**：写清它在本需求里具体要求做什么，可实现、可测——落在哪个接口、 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-127 | 127–130 | 10. 规约约束要求 / **不为任何域预留固定小节**：域清单在激活清单里，这里不复述。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-131 | 131–132 | 11. 设计模式候选登记 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-133 | 133–134 | 11. 设计模式候选登记 / &lt;!-- 同样由 &#96;spec/knowledge-use.yaml&#96; 的 &#96;patterns&#96; 段生成（字段见骨架与任务包）。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-135 | 135–137 | 11. 设计模式候选登记 / **只登记候选，不做选型**——选型缺少方案上下文，那是 plan 的事，结论落 &#96;contracts.yaml&#96;。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-138 | 138–141 | 11. 设计模式候选登记 / **「什么算一个适用单元」由激活清单里的模式索引定义**，照它切——此处不复述那个定义， | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-142 | 142–144 | 11. 设计模式候选登记 / **零候选是正常结论**，但要显式写出来（单元 + 为什么都不需要）—— | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-145 | 145–147 | 11. 设计模式候选登记 / 信号来自**业务流程本身**：数分支、数步数、看失败处理时，以需求描述的那个业务过程为准。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-148 | 148–151 | 11. 设计模式候选登记 / **反证同样要举证**：指向本需求的具体业务事实（哪一段流程、有哪些分支、每个分支后面 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-152 | 152–154 | 11. 设计模式候选登记 / 本章**不参与契约名守恒与专名派生**：候选是可选方案，不是已定契约。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-155 | 155–156 | 11. 设计模式候选登记 / &lt;!-- ── 对 core 模板既有章节的补充要求 ──────────────────────────────── | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-157 | 157–165 | 11. 设计模式候选登记 / **## 0. 术语映射表 —— 加一列「解释」** —— 业务名词的解释**只放这一张表**， | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-166 | 166–169 | 11. 设计模式候选登记 / **### A. 术语表（附录）** —— 只写一句索引，不重复内容： | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-170 | 170–173 | 11. 设计模式候选登记 / **### B. 参考资料（附录）** —— 列上游 RR/SR 单号，给 AI 回溯用。 | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |
| P12ec7582-174 | 174–178 | 11. 设计模式候选登记 / **## 宿主扩展治理项** —— 只写一句索引，不逐项列「是否涉及」： | F2.2, F4.3, F4.4, F5.1 | M09, M10, M24, M25, M26, M30 | 按M09,M10,M24,M25,M26,M30比较结论保留其必要职责 |

<a id="P8c0742fa"></a>

## skills/story-adaptation/scripts/adapt-scan.mjs

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P8c0742fa-1 | 1–17 | 文件头/元信息 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-18 | 18–18 | import { spawnSync } from 'node:child_process'; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-19 | 19–19 | import { createHash } from 'node:crypto'; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-20 | 20–22 | import { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-23 | 23–23 | import { dirname, join, relative, resolve, sep } from 'node:path'; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-24 | 24–24 | import { fileURLToPath } from 'node:url'; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-25 | 25–26 | import { parseYaml } from '../../../hooks/shared/yaml-lite.mjs'; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-27 | 27–29 | MODES | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-30 | 30–31 | ADAPTERS | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-32 | 32–33 | KNOWLEDGE | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-34 | 34–34 | SCRIPTS_DIR | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-35 | 35–36 | CORE | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-37 | 37–37 | EXT_BEGIN | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-38 | 38–38 | EXT_END | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-39 | 39–39 | SECTION | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-40 | 40–41 | ENTRIES | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-42 | 42–42 | argv | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-43 | 43–43 | mode | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-44 | 44–44 | opt | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-45 | 45–46 | die | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-47 | 47–47 | read | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-48 | 48–48 | rel | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-49 | 49–51 | sha | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-52 | 52–58 | findRoot | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-59 | 59–68 | config | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-69 | 69–69 | extDir | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-70 | 70–78 | featuresDir | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-79 | 79–101 | walk | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-102 | 102–114 | coveredFiles | F6.2, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P8c0742fa-115 | 115–134 | knowledgeBlock | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-135 | 135–158 | skeletonKnowledge | F6.1 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-159 | 159–186 | composeManifest | F6.4 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-187 | 187–196 | withVersionNotes | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-197 | 197–205 | TARGET_OWNED_KEYS | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-206 | 206–221 | versionNotes | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-222 | 222–237 | manifestValue | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-238 | 238–245 | freshIdentity | F6.1 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-246 | 246–271 | bridgesOf | F6.4 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-272 | 272–284 | missingGitignoreLines | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-285 | 285–297 | inWriteFace | F6.2, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P8c0742fa-298 | 298–307 | git | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-308 | 308–321 | isRepo | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-322 | 322–330 | dirtyPaths | F6.2, F6.3 | M01, M35 | 按M01,M35比较结论保留其必要职责 |
| P8c0742fa-331 | 331–331 | if (!mode) die(&#96;缺模式：${MODES.join(' &#124; ')}&#96;); | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-332 | 332–332 | if (!opt('--target')) die('缺 --target &lt;目标根&gt;'); | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-333 | 333–333 | TARGET | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-334 | 334–334 | if (!TARGET) die(&#96;目标不是有效仓库根（找不到 framework.config.json）：${opt('--target')}&#96;); | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-335 | 335–337 | PKG | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-338 | 338–339 | if (!PKG) die('包不是有效仓库根（找不到 framework.config.json）'); | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-340 | 340–340 | PDIR | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-341 | 341–341 | TDIR | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-342 | 342–343 | SAME_TREE | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-344 | 344–344 | pkgManifest | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-345 | 345–345 | if (!existsSync(pkgManifest)) die(&#96;包里没有 manifest.yaml：${pkgManifest}&#96;); | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-346 | 346–346 | PKG_MANIFEST_TEXT | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-347 | 347–348 | BRIDGES | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-349 | 349–350 | tgtManifest | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-351 | 351–362 | STATE | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-363 | 363–363 | MOCK_ADAPTER_PACKAGE | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-364 | 364–365 | PKG_NAME | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-366 | 366–369 | if (!PKG_NAME) { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-370 | 370–373 | WITH_ADAPTERS | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-374 | 374–500 | if (mode === '--apply') { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-501 | 501–505 | stripMarks | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-506 | 506–537 | replaceZone | F6.4 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-538 | 538–552 | extensionSectionEnd | F6.4 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-553 | 553–564 | bad | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-565 | 565–593 | { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-594 | 594–613 | if (existsSync(tgtManifest)) { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-614 | 614–639 | { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-640 | 640–647 | for (const line of missingGitignoreLines(TARGET)) { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-648 | 648–668 | { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-669 | 669–673 | if (bad.length) { | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8c0742fa-674 | 674–676 | console.log('&#91;adapt-scan&#93; 核对通过：机制面与包一致 / manifest 按所有权合成 / ' | F6 | M35 | 按M35比较结论保留其必要职责 |

<a id="P8b8e8eba"></a>

## skills/story-adaptation/SKILL.md

| 区间 | 源行 | 符号/段落/字段 | 功能 | 同功能实现比较 | 局部结论 |
|---|---|---|---|---|---|
| P8b8e8eba-1 | 1–5 | 文件头/元信息 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-6 | 6–7 | story adapt — 把 Story Extension 装到 / 升级到目标工程 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-8 | 8–10 | story adapt — 把 Story Extension 装到 / 升级到目标工程 / **包** = 发起本命令的仓库（缺省当前仓）。**目标** = &#96;/story adapt &lt;目标工程&gt;&#96; 的参数。 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-11 | 11–12 | 所有权由目录表达 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-13 | 13–20 | 所有权由目录表达 / &#124; 目录 &#124; 归谁 &#124; 复制时 &#124; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-21 | 21–22 | 所有权由目录表达 / **没有第三种要你判断的情形**：一个文件归谁，看它在哪个目录。 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-23 | 23–24 | 两种来源 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-25 | 25–29 | 两种来源 / &#124; 来源 &#124; 对接层 &#124; 为什么 &#124; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-30 | 30–31 | 两种来源 / 判来源看包 &#96;manifest.yaml&#96; 的 &#96;name&#96;——它归目标、升级不改，所以每个仓的 manifest 里那个名字始终是它自 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-32 | 32–33 | 两种来源 / Demo 装出来的仓没有 &#96;adapters/&#96;：目标要照 &#96;&lt;ext&gt;/skills/story/scripts/README.md&#96; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-34 | 34–35 | 你要做的四件事 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-36 | 36–37 | 1 前置（脚本自己查，不过就停） | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-38 | 38–41 | 1 前置（脚本自己查，不过就停） / 示例或代码块 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-42 | 42–43 | 1 前置（脚本自己查，不过就停） / 它先查三件，任一不满足就退出并点名： | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-44 | 44–46 | 1 前置（脚本自己查，不过就停） / - **目标是 git 仓库的根**、**这次要覆盖的路径上没有未提交改动**——升级会整份换掉那些文件，没存档的改动被盖掉就找不回来了 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-47 | 47–48 | 1 前置（脚本自己查，不过就停） / **不替用户动他的工作区**：不自动 stash、不自动提交。报错会点名脏的路径，让他自己先提交或暂存。 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-49 | 49–50 | 2 判态（脚本判，你不猜） | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-51 | 51–53 | 2 判态（脚本判，你不猜） / 目标有没有 &#96;manifest.yaml&#96;——**有就是升级，没有就是首次**。历史版本识别、结构签名、混合状态处理都不存在于本实现。 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-54 | 54–55 | 3 写入 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-56 | 56–58 | 3 写入 / &#96;--apply&#96; 一次做完全部确定性写入：删掉退场文件、复制机制面、合成 manifest、覆盖跳板、重写入口标记区、补 &#96;.giti | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-59 | 59–60 | 3 写入 / **升级不停等**：一次升级指令授权到写入完成加自检，只有失败才回头问人。写入面已由目录边界完全确定，没有可拍板的选项。 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-61 | 61–62 | 3 写入 / **首次安装多两件**，其中一件归你： | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-63 | 63–65 | 3 写入 / - 脚本做的：确保 &#96;framework.config.json&#96; 有 &#96;paths.extension_dir&#96; 这个键（缺就加），建 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-66 | 66–72 | 3 写入 / &#124; 项 &#124; 内容 &#124; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-73 | 73–74 | 3 写入 / 画像写完记得登记进 &#96;manifest.yaml&#96; 的 &#96;provides.knowledge&#96;——那份清单归目标，脚本不替它写。 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-75 | 75–76 | 4 确认 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-77 | 77–80 | 4 确认 / 示例或代码块 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-81 | 81–82 | 4 确认 / 四组，全过退出 0： | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-83 | 83–90 | 4 确认 / &#124; 组 &#124; 判什么 &#124; | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-91 | 91–93 | 4 确认 / &#96;--check&#96; 不查工作区干不干净、也不看 git（那是 &#96;--apply&#96; 的前置）：它只读，回答的是 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-94 | 94–97 | 4 确认 / 拿 &#96;git diff&#96; 判「升级碰了什么」不成立：目标自己改过知识、&#96;--apply&#96; 一个字节没写， | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-98 | 98–99 | 对接层的输出合同 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-100 | 100–101 | 对接层的输出合同 / &#96;adapters/&#96; 里那三个由目标仓自己实现，包里那份是替身。它们的 CLI 参数、stdout JSON 与写盘落点写在 &#96;&lt;ex | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-102 | 102–103 | 不做的事 | F6 | M35 | 按M35比较结论保留其必要职责 |
| P8b8e8eba-104 | 104–107 | 不做的事 / - **不做历史兼容**：旧结构、混合目录、部分迁移状态都不进设计、不进分支、不进验收。已有产物由用户手动调整。 | F6 | M35 | 按M35比较结论保留其必要职责 |

## 非交付缓存

- `skills/story/scripts/core/__pycache__/import_sources.cpython-313.pyc`
- `skills/story/scripts/core/__pycache__/materials.cpython-313.pyc`
- `skills/story/scripts/core/__pycache__/story_flow.cpython-313.pyc`

缓存未删除，不把它们计作机制退场收益。
