# 步骤A01：固定Framework与宿主组合

本步是完整施工单元，不是批次。完成结果：900c原生发布树、必要本地定制、interactive工具配置和开发Extension经现装配器形成一份可重建的消费组合，来源、物化与续跑配置一致。只验证装配/接口，不运行模型。预算G1/X1（manifest版本），其余测试装置/文档G0；2026-11-11用户已批准实施及预算，执行者按总Plan§7开工。

## 1. 输入、前提与文件边界

输入：有效Spec G03/G06、@30、总Plan预算；900c508d5c800bb77f9adb8db395b2964ef111d3:framework，tree 5a20d305386f781b2e8b9fdce5ff704c8160350c；现test/config/framework-under-test.json；现3.1.0-dsh.patch及维护操作§2。

文件动作限定：test/config/framework-under-test.json、test/fixtures/framework-local/3.1.0-dsh.patch、test/tests/test_verifier_chain_in_workspace.py、必要的test_cli_config_failover回归、doc/release/维护操作.md、本步交回；首次产品提交改extensions/manifest.yaml版本及按已批准方案记录预算台账。demo、根宿主物化件、tools/cli中央镜像、个人DSH profile和业务Case不改。

## 2. 补丁处置已定，不再让执行者选择

本轮设计者已按新原生正文逐项核：旧21个补丁文件中19个原块对900c静态apply --check通过；两个旧派发位置已由上游共同协调器接替，**退出本地差异，不重建旧Task调用段**。

| 文件/集合 | 确定动作 | 新承担及验证 |
|---|---|---|
| agents/shared/agent-bundle/templates/rules/framework-agent-execution.mdc | 从本地patch移除该文件整块diff，保持900c原字节 | 新§2用共同协调器运输独立审查；实际专用角色指引由仍在的harness输出/角色模板承担 |
| skills/reference/business-ut-workflow-detail.md | 从patch移除该文件整块diff，保持900c原字节 | 新Step8.2按实际签发request由共同协调器派审；不恢复原先主会话自己构造Task的文字 |
| 其余19块 | 保留现差异，除下一行dsh配置外不再扩写 | 范围和逐文件清单见下文设计证据patch-audit.json；它们只保既定三组定制，不改原生条件/数据协议 |
| agents/dsh/templates/agents/framework-verifier.patch.yml | 在该模板顶层追加现插件禁用：`- id: tool-goal`、`disabled: true` | 与首启/续跑使用同一overlay，保maison-verifier/只读运输，不禁用原生命令名中的goal |

设计证据：output/evidence/2.0.4-step-detail/20261111-135007/patch-audit.json及retained-19.patch（只读检查产物，未应用到产品）。新树核定两处原文为framework-agent-execution§2和business-ut-workflow-detail Step8.2；其余19文件名由该JSON逐一固定，不再临场增加/删除补丁范围。

## 3. 操作顺序与产物

1. 在output/scratch/2.0.4-A01中从固定git对象解出干净framework源；在其独立副本内建立临时Git基线用于导出patch。生成patch前不运行会写状态/依赖的harness，防止把运行态纳入差异；不在真实demo或共享被测副本上编辑。
2. 按上表删掉旧patch的两个完整diff块，对工作副本应用其余19块；编辑其中dsh模板加入禁用条目。用该临时仓的`git diff --binary --no-ext-diff`导出a/b相对框架根的patch；新增dsh文件先以intent-to-add纳入diff。临时Git仅用于差异生成，不提交主工作区。
3. 替换正式test/fixtures中的patch，再在第三份干净900c副本执行`git apply --check --directory=framework <新patch绝对路径>`。最终patch文件集合必须是固定19个；两份退出文件与900c原字节一致。只读19块的此前PASS不代替这份含DSH禁用项的新patch验证。
4. pin只改release_commit和tree_oid为上面的固定值，保framework_path/local_patch/materialized_adapters。现loader用该pin和patch装配，无第二取树来源。
5. 维护操作§2移除两份已退出差异，保三组实际功能及19文件清单；给定源码/原生说明依据，不留“执行者再看是否需要”的分支。
6. 将测试`TheVerifierCallTextNamesTheDedicatedRole.CALLS`中的RULE移到非专用调用文字集合OTHERS：不再要求新协调器规则必须包含本地专用短语，仍核无旧Task派发话术；新增两份退出文件与固定原生blob相同的断言。保其余真实专用调用输出、模板物化一致与receipt断言，不能删全项求绿。
7. 用实际物化的.dsh/framework-verifier.patch.yml对headless/batch-build跑`dsh --profile <档位> --patch <配置绝对路径> --dump-config`；只保存tool-goal禁用/角色插件和配置来源摘要，不公开整份本机配置。registry_snapshot的args/resume_args都须装同一overlay；它已有此行为，正常不改cli_config_group.py。
8. 获准的首次extensions提交把version升2.0.4；预算仍原包1806aa59/4250，新增估算和类型见总Plan，不能因版本/步骤重置。台账更新是机械记已批准值，不自行批准额度。

## 4. 完成条件及验证

仓根运行（产品实施获准后）：
```
python test/scripts/verify.py assembly
python test/scripts/verify.py affected test/tests/test_verifier_chain_in_workspace.py test/tests/test_cli_config_failover.py -k "not ASecondEmptyDirectoryRebuildsTheSameCombination"
```
第二次空目录重建由assembly承担，affected排除同类避免重复。预期退出0；包身份为900c/tree5a20…/source_commit bd06421c，新patch摘要一致，开发源逐字安装，两次物化一致，demo前后无改动。缺依赖/错tree/patch不适用须在相应入口报错，不换回旧树或跳校验。

静态dump只证配置，不证父子模型实际工具/停等；这些列D02。交回列19文件保留/2文件退出、命令/结果/组合身份/保护区diff、版本与官方预算。正常调用序列无额外产品机制；出现超出固定合同的新差异时停相关动作给设计者，不临场拼补丁。

## 5. 接续

完成本步的必要验证、写本步交回并按获准范围提交；A02依赖此组合。批次A是否进入下一批由00-批次方案的集中评审安排决定，本步不单独新增审批点，也不触发模型CLI。
