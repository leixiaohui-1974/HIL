# HydroMind 按仓库分解的 Backlog / Issue 清单

**作者：** Manus AI  
**日期：** 2026-04-15

---

## 一、文档定位

这份清单是在前序评审、P0/P1/P2 分层实施方案，以及 P3 界面自动化验收规划的基础上，进一步压缩形成的**按仓库分解开发 backlog**。它的用途不是替代详细设计，而是作为后续云端协作开发时的直接任务入口，方便继续拆成 issue、PR 和里程碑。

本文默认采用以下推进顺序：**先 P0，后 P1，再 P2；先 runtime truth，再 host decoupling，最后 new-case proof。**

---

## 二、总控原则

| 原则 | 含义 | 落地要求 |
|------|------|----------|
| runtime-first | 先把运行态真相做对 | 先改 contracts 与 hydromind façade |
| contract-driven | 所有平台对象先有稳定 contract | 模型、校验、测试先行 |
| host-agnostic | 宿主不承载业务真相 | Studio 只调用 façade / runtime |
| provider-decoupled | 领域执行经 adapter 暴露 | legacy 不得再被页面直连 |
| new-case-oriented | 平台成熟度以新 case 为证明 | six-case 退回回归基线 |

---

## 三、建议的里程碑与分发方式

| 里程碑 | 对应层次 | 通过条件 | 推荐 PR 组织方式 |
|------|----------|----------|------------------|
| M1 | P0 | TeamRunState / events / artifacts / façade 成型 | contracts PR + hydromind façade PR |
| M2 | P1 | Studio 已不再直连 legacy gateway | studio host-binding PR + adapter PR |
| M3 | P2 | 新 case 跑通 onboarding → run → review → release | onboarding PR + orchestration PR + proof PR |

建议在 Git 中采用“**一里程碑一组 PR**”的方式，而不是大而全一次提交。这样后续无论在本地还是云端开发，都更容易衔接。

---

# 四、仓库一：`hydromind-contracts`

## 4.1 仓库目标

这个仓库在 P0 阶段承担**平台对象真相层**职责，在 P1/P2 阶段承担**约束收口与一致性校验**职责。它应当是所有宿主、runtime、provider 和测试共同依赖的对象定义源。

## 4.2 建议 issue 清单

| Issue ID | 优先级 | 层次 | 标题 | 关键文件 | 预期结果 |
|------|------|------|------|---------|----------|
| HC-01 | P0 | 高 | 扩展 TeamRunState 为完整运行态对象 | `hydromind_contracts/models.py` | 增加 stage、step、workflow、provider_refs、artifact_summary、failure_semantics |
| HC-02 | P0 | 高 | 为 TeamRunState 增加状态迁移与一致性校验 | `hydromind_contracts/program_validation.py` | 非法 transition、上下文缺失、状态组合错误可被拒绝 |
| HC-03 | P0 | 高 | 为运行态 contract 补充测试矩阵 | `tests/test_program_validation.py` | 测试覆盖 planned/running/degraded/blocked/completed/failed |
| HC-04 | P0 | 高 | 引入 TraceEvent 与 ArtifactIndex 合同 | `models.py` 及配套测试 | session events 与 artifacts 有统一对象 |
| HC-05 | P1 | 中 | 强化 HostSessionBinding 与 ExecutionProvider 约束 | `models.py`、`program_validation.py` | host binding 与 provider capability 有稳定表达 |
| HC-06 | P2 | 中 | 强化 CaseManifest 的 onboarding 最小输入约束 | `case_manifest` 模型/校验区 | 新 case 可按最小模板入场 |
| HC-07 | P2 | 中 | 增加 run/review/release 对象一致性校验 | 相关模型与测试 | WorkflowRun、ReviewBundle、ReleaseManifest、FinalReport 可交叉校验 |

## 4.3 推荐实施顺序

| 顺序 | Issue ID | 原因 |
|------|----------|------|
| 1 | HC-01 | 不先做厚 TeamRunState，后续 façade 与 UI 都无统一语义 |
| 2 | HC-02 | 先有状态机校验，避免运行态继续漂移 |
| 3 | HC-03 | 用测试把 P0 真相层锁住 |
| 4 | HC-04 | 为 trace/artifact 查询建立对象基础 |
| 5 | HC-05 ~ HC-07 | 支撑 P1/P2 的 host/provider/onboarding 扩展 |

## 4.4 验收标准

| 验收项 | 标准 |
|------|------|
| 运行态 contract | TeamRunState 能表达真实生命周期，不再只是带 status 的薄对象 |
| 校验器 | 至少能拒绝非法状态迁移与关键字段缺失 |
| 测试 | 合同测试可作为 runtime 与 UI 的公共回归基线 |

---

# 五、仓库二：`hydromind`

## 5.1 仓库目标

这个仓库是**平台 façade 与 runtime 主入口**。它在 P0 阶段负责建立统一 session/trace/artifact 出口，在 P1 阶段负责承接 host binding 与 provider adapter，在 P2 阶段负责 orchestration 和新 case onboarding。

## 5.2 建议 issue 清单

| Issue ID | 优先级 | 层次 | 标题 | 关键文件 | 预期结果 |
|------|------|------|------|---------|----------|
| HM-01 | P0 | 高 | 整理 hydromind CLI 命令树，明确 façade 分组 | `scripts/hydromind.py` | 命令边界清晰：session、trace、artifacts、smart、contracts |
| HM-02 | P0 | 高 | 增加 session-status / session-events / session-artifacts 查询命令 | `scripts/hydromind.py` | CLI 可独立读取运行态 |
| HM-03 | P0 | 高 | 统一 session 落盘布局与 artifact layout | runtime 相关模块 | 每次运行都有稳定目录结构与标准 JSON/NDJSON 出口 |
| HM-04 | P0 | 高 | 为 façade 建立行为测试 | tests 目录 | CLI 输出成为宿主与自动化共用基准 |
| HM-05 | P1 | 高 | 将 host binding 收口到平台调用协议 | façade / runtime / binding 模块 | Studio 与其他宿主只调用平台接口 |
| HM-06 | P1 | 高 | 固化 bridge manifest 中 host → runtime → provider 边界 | `configs/bridges/platform_bridge_manifest.v1.yaml` | 平台桥接语义可配置、可审阅 |
| HM-07 | P1 | 高 | 固化 execution adapter catalog | `configs/adapters/execution_adapter_catalog.v1.yaml` | legacy/new provider/shim 有统一登记面 |
| HM-08 | P2 | 高 | 增加 case-init / case-validate / case-bootstrap 命令 | `scripts/hydromind.py` | 新 case 不再靠复制样例目录进入系统 |
| HM-09 | P2 | 高 | 建立统一 run orchestration 入口 | orchestration 模块 | onboarding → run 主链由平台触发 |
| HM-10 | P2 | 中 | 聚合 review / release / final report 标准出口 | report / release 相关入口 | 评审与发布对象由平台统一产出 |
| HM-11 | P2 | 中 | 建立 six-case 回归与新 case 对照脚本 | tests / scripts | six-case 做回归，新 case 证明通用性 |

## 5.3 推荐 PR 主题

| PR 主题 | 对应 Issue | 建议提交内容 |
|------|-----------|--------------|
| PR-A：façade 与 runtime 真相层 | HM-01 ~ HM-04 | 命令树、session/trace/artifact、落盘规范、测试 |
| PR-B：host / provider 接线层 | HM-05 ~ HM-07 | bridge manifest、adapter catalog、binding 协议 |
| PR-C：new-case 主链 | HM-08 ~ HM-11 | onboarding 命令、orchestration、review/release、回归脚本 |

## 5.4 验收标准

| 验收项 | 标准 |
|------|------|
| façade 完整性 | 不进入 legacy 仓库也能读取与推进 session 主链 |
| host binding | 宿主接入走统一平台协议，而非脚本拼接 |
| onboarding | 新 case 可由平台原生命令接入 |
| orchestration | review / release / report 可由平台统一产出 |

---

# 六、仓库三：`hydromind-studio`

## 6.1 仓库目标

这个仓库的职责不是承载平台真相，而是作为**宿主前台与工作台界面**。P1 是该仓的重点阶段，核心是去掉对 legacy gateway 与研究目录路径的直接感知；P2 则负责把新 case 主链以可观察方式呈现出来。

## 6.2 建议 issue 清单

| Issue ID | 优先级 | 层次 | 标题 | 关键文件 | 预期结果 |
|------|------|------|------|---------|----------|
| HS-01 | P1 | 高 | 将 `tauri_bridge.js` 从 legacy gateway 语义迁移到 platform runtime 语义 | `api/tauri_bridge.js` | 不再暴露 `agent_loop_gateway_*` 作为主调用面 |
| HS-02 | P1 | 高 | 将 `useAgentLoopGatewaySession` 重构为 host-agnostic 平台 session hook | `hooks/useAgentLoopGatewaySession.js` | hook 面向 session/status/events/artifacts 语义 |
| HS-03 | P1 | 高 | 清理 `AgentWorkspace.jsx` 中的 legacy 路径与 shell 感知 | `pages/AgentWorkspace.jsx` | 页面只负责触发、展示、写入，不负责路径推导 |
| HS-04 | P1 | 中 | 为平台 session/trace/artifact 增加稳定展示组件 | runtime status / report 相关组件 | 便于后续浏览器自动化断言 |
| HS-05 | P1 | 中 | 将 case context / run context / artifacts 查询收口到 client 层 | `api/hydromind_client` | 页面通过统一 client 取上下文 |
| HS-06 | P1 | 中 | 为 bridge 与 hook 建立 fixture 测试 | tests 目录 | 前端测试不再依赖 legacy 命令输出 |
| HS-07 | P2 | 中 | 增加新 case onboarding 的界面入口 | 页面与组件目录 | 页面可引导新 case 初始化与校验 |
| HS-08 | P2 | 中 | 增加 run/review/release 的可观测工作面 | 页面与组件目录 | 页面能完整展示新 case 主链 |
| HS-09 | P2 | 中 | 增加 six-case 与新 case 结果对照视图 | 页面与数据层 | 用户可看到回归基线与平台通用性证明 |

## 6.3 推荐实施顺序

| 顺序 | Issue ID | 原因 |
|------|----------|------|
| 1 | HS-01 | 先收 bridge，切断主调用面的 legacy 名称与路径 |
| 2 | HS-02 | 再统一 hook 语义，避免页面继续绑死 gateway |
| 3 | HS-03 | 页面瘦身，移除 legacy 感知 |
| 4 | HS-05 + HS-04 | 再收 client 层与展示层 |
| 5 | HS-06 ~ HS-09 | 补测试与 onboarding / 对照能力 |

## 6.4 验收标准

| 验收项 | 标准 |
|------|------|
| 页面调用路径 | Studio 主动作全部落到 hydromind façade / runtime |
| 页面职责边界 | 页面不再推断 legacy case shell、研究目录路径、脚本位置 |
| 展示稳定性 | 状态、事件、产物、报告可稳定呈现并可供自动化测试断言 |

---

# 七、仓库四：`hydromind-model-core`

## 7.1 仓库目标

这个仓库不应承担平台真相层，而应承担**领域 provider 与建模执行能力**。P1 的重点是把执行入口适配成 provider layer，P2 的重点是用真实数据准备、建模、评审与报告流程来支撑新 case 主链。

## 7.2 建议 issue 清单

| Issue ID | 优先级 | 层次 | 标题 | 关键区域 | 预期结果 |
|------|------|------|------|---------|----------|
| HMC-01 | P1 | 高 | 统一 provider 调用签名与返回对象 | 主要 workflow / provider 入口 | 平台层可以稳定调用 model-core 能力 |
| HMC-02 | P1 | 中 | 清理对 sibling repo 的隐式路径依赖并显式 adapter 化 | 现有 gateway / pipeline 入口 | provider 依赖可配置、可声明、可替换 |
| HMC-03 | P2 | 高 | 建立新 case 数据准备 provider 流 | 数据准备、预处理、校核入口 | 新 case 可完成从资料到可运行输入的转换 |
| HMC-04 | P2 | 高 | 建立模型计算主 provider 流 | simulation / learning / control 入口 | 平台 orchestration 可真正驱动模型计算 |
| HMC-05 | P2 | 中 | 建立报告与评审聚合 provider 流 | review / report / validation 入口 | model-core 输出可稳定被平台汇总 |
| HMC-06 | P2 | 中 | 产出一条新 case 的真实演示通路 | case config / provider config | 用非 six-case 验证平台通用性 |

## 7.3 验收标准

| 验收项 | 标准 |
|------|------|
| provider 统一性 | 平台调用 model-core 时不需要知道具体历史脚本细节 |
| 新 case 支撑力 | 能从数据准备推进到模型计算与结果产出 |
| 报告协同 | 输出可被 hydromind 聚合为 ReviewBundle / FinalReport |

---

# 八、仓库五：`research`（含 `Hydrology` 等 legacy 区）

## 8.1 仓库目标

`research` 在后续阶段不再承担平台主入口职责，而是作为**历史算法资产、参考实现与过渡 shim 层**。这里的重点不是继续扩展产品面，而是**收边界、做映射、保可复用价值**。

## 8.2 建议 issue 清单

| Issue ID | 优先级 | 层次 | 标题 | 关键区域 | 预期结果 |
|------|------|------|------|---------|----------|
| HR-01 | P1 | 高 | 标记 legacy gateway 为过渡 shim，不再作为 UI 主入口 | `Hydrology/workflows/agent_loop_gateway.py` | 页面不再把它当主后端 |
| HR-02 | P1 | 中 | 梳理 legacy workflow 到 provider catalog 的映射关系 | workflow / scripts / docs | 为 adapter layer 提供映射依据 |
| HR-03 | P2 | 中 | 选定 six-case 中 1~2 个作为平台回归基线 | case/workflow/报告资产 | 保留重构后的回归抓手 |
| HR-04 | P2 | 中 | 产出 research → hydromind 的能力迁移对照表 | docs / wiki | 明确哪些能力已迁移，哪些仍待 shim |

## 8.3 验收标准

| 验收项 | 标准 |
|------|------|
| legacy 定位 | 研究仓不再对前台暴露产品级执行入口 |
| 映射清晰度 | 历史能力可映射到 provider / adapter catalog |
| 回归价值 | six-case 仍可作为稳定回归基线 |

---

# 九、跨仓库总控 issue

有些问题必须跨仓协调，不适合只放在单一仓库中。建议单独建立总控 issue 或项目卡片。

| Cross Issue ID | 层次 | 标题 | 涉及仓库 | 说明 |
|------|------|------|----------|------|
| X-01 | P0 | 统一 runtime truth 与 artifact layout | `hydromind-contracts` + `hydromind` | contract 与 façade 必须同步落地 |
| X-02 | P1 | Studio 去 legacy 直连总控 | `hydromind-studio` + `hydromind` + `research` | 页面、bridge、shim 必须同步收口 |
| X-03 | P1 | provider adapter 收口 | `hydromind` + `hydromind-model-core` + `research` | 防止 provider 继续散落在脚本路径中 |
| X-04 | P2 | 新 case onboarding proof | `hydromind` + `hydromind-contracts` + `hydromind-model-core` | 证明平台不是为 six-case 定制 |
| X-05 | P2 | 回归基线与新 case 对照验收 | `hydromind` + `hydromind-studio` + `research` | 同时证明稳定性与通用性 |

---

# 十、建议的首批 PR/Issue 起手顺序

如果现在就要开始进入云端协作开发，我建议不要一次性铺开所有 issue，而是先启动下面这一组“起手 PR”。

| 起手顺序 | 推荐 PR / Issue 组合 | 目标 |
|------|----------------------|------|
| 1 | HC-01 + HC-02 + HC-03 | 先把 TeamRunState 和状态机约束锁住 |
| 2 | HM-01 + HM-02 + HM-03 | 让 hydromind façade 真正成为运行入口 |
| 3 | HS-01 + HS-02 | 切断 Studio 对 legacy gateway 的主调用依赖 |
| 4 | HM-06 + HM-07 + HMC-01 | 把 bridge / adapter / provider 收到统一目录下 |
| 5 | HM-08 + HM-09 + HMC-03 | 开始建立 new-case 主链 |
| 6 | HM-10 + HS-07 + HS-08 | 接通 run / review / release 的展示面 |
| 7 | HR-03 + HM-11 + HS-09 | 建立 six-case 回归与新 case 对照验证 |

---

# 十一、建议的 Git 提交策略

既然您明确提出要“及时提交到 Git，便于后续云端开发”，我建议后续采用下面这套提交纪律。

| 策略 | 建议 |
|------|------|
| 小步提交 | 一次提交只解决一组紧密相关 issue，不做大杂烩提交 |
| 文档先行 | 每轮关键设计与分层规划先提交文档，再推进代码 |
| 里程碑标签 | 提交信息中显式标记 P0 / P1 / P2 / P3 |
| PR 对齐 issue | 每个 PR 明确对应上表中的 issue ID |
| 云端连续开发 | 以 Git 中最新文档与 contracts 为真相源继续推进 |

建议提交信息格式统一为：

> `docs(hydromind): add backlog issue list for P0-P2 execution`

或：

> `feat(hydromind): introduce session trace artifact runtime skeleton`

---

# 十二、结论

如果把本文进一步压缩成一句话，那么它表达的是：

> **先把真相层和 façade 立住，再切断 Studio 与 legacy 的直连，最后用新 case 证明平台通用性。**

这份 backlog 清单已经可以直接作为后续云端开发的 issue 起点。最关键的不是“多写几个计划文档”，而是从现在开始让 **Git 中的文档、contracts、runtime façade 和 adapter catalog** 逐步成为真正的协作真相源。

如果继续往下推进，下一步最自然的动作有两个：其一，把这份 backlog 清单提交到 Git；其二，从首批起手 PR 的第一组 issue 开始，正式进入代码落地阶段。
