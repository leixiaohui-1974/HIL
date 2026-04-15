# HydroMind P0 / P1 / P2 分层实施细化方案

**作者：** Manus AI  
**日期：** 2026-04-15

---

## 一、文档目的

这份文档是在此前总体评审、GPT handoff 校正，以及 P3 界面自动化验收层规划的基础上，对 **P0 / P1 / P2 三个分层计划**进行进一步细化。目标不是再重复战略判断，而是把三个层次落成可以直接进入排期、分仓开发和验收的实施方案。

这里采用的基本判断不变：`research` 是历史研发现场，`hydromind` 才是未来平台主线；`six-case` 是重要样本与回归资产，但不能继续主导平台语义；真正需要优先打通的是 **contracts truth layer、runtime/session/trace、provider adapter layer、host binding** 这四条主线。基于这一判断，P0 / P1 / P2 需要形成逐层推进的建设顺序，而不是并行摊开。

---

## 二、三个分层的总目标与边界

P0、P1、P2 不是简单按时间顺序划分，而是按**平台成熟度门槛**来定义。P0 解决“平台骨架是否站住”；P1 解决“宿主与执行面是否真正解耦”；P2 解决“平台是否已经具备通用 case 的真实端到端能力”。

| 分层 | 核心目标 | 关注点 | 明确不做的事 |
|------|----------|--------|--------------|
| P0 | 夯实 contracts 与 runtime 的主真相层 | 对象、状态、入口、事件、artifact | 不追求 UI 完整，不追求所有 provider 一次到位 |
| P1 | 切断 Studio 对 legacy 执行面的直接耦合 | host binding、bridge、adapter、runtime 接线 | 不急于扩展大量新功能页面 |
| P2 | 用新 case 验证平台通用性与端到端主链 | onboarding、run、review、release、provider 实战 | 不再以 six-case 补壳为核心目标 |

这个分层顺序非常关键。**如果没有 P0，P1 只是换壳；如果没有 P1，P2 只是把 legacy 能力重新包装；只有 P0 和 P1 做扎实，P2 才能证明 HydroMind 真的是平台，而不是重命名后的历史脚本总装。**

---

## 三、总体现实施工顺序

为了避免多个仓库同时大改导致失控，我建议采用“先收真相，再收接口，最后做通用性验证”的实施顺序。

| 阶段顺序 | 主攻对象 | 产出标志 |
|------|----------|----------|
| 第一步 | `hydromind-contracts` + `hydromind` | runtime/session/contract 有统一主语义 |
| 第二步 | `hydromind-studio` + `hydromind` | 页面动作全部落到 façade/runtime，而不是 legacy gateway |
| 第三步 | `hydromind-model-core` + `hydromind` | 至少一个新 case 跑通 onboarding → run → review → release |
| 第四步 | `hydromind-studio` + 测试层 | 为后续 P3 浏览器自动化做好稳定验收面 |

这份文档聚焦前三步，也就是 P0 / P1 / P2。

---

# 四、P0 细化方案：夯实 contracts truth layer 与 runtime 主骨架

## 4.1 P0 的完成定义

P0 的完成，不是“写了一套 schema”，也不是“CLI 能多跑几个命令”，而是要满足以下条件：

第一，平台已经有统一的 **session / state / trace / artifact** 主语义。  
第二，`hydromind` 主 CLI 已成为稳定 façade，而不是对 legacy smart CLI 的薄转发。  
第三，关键 contract 已经能表达运行态，而不仅仅是静态对象。  
第四，任意宿主和前端都可以围绕这些对象工作，而不需要知道 legacy 脚本路径。

## 4.2 P0 的核心任务包

### 4.2.1 任务包 A：补全 TeamRunState 与运行态 contract 体系

当前 TeamRunState 已经出现，但语义仍偏薄，更多是“带状态字段的对象”，还不是完整运行态真相层。因此 P0 的第一优先级，是把运行态合同做厚。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P0-A1 | `hydromind-contracts` | `hydromind_contracts/models.py` | 扩展 `TeamRunState` 字段，增加 stage、step、current_workflow、provider_refs、artifact_summary、failure_semantics、degrade_reason | 更新后的模型定义 | TeamRunState 能表达一次真实运行中的状态推进与降级信息 |
| P0-A2 | `hydromind-contracts` | `hydromind_contracts/program_validation.py` | 增加状态迁移校验、阶段字段一致性校验、关键关联字段存在性校验 | 更新后的验证器 | 非法 transition、缺失上下文、错误状态组合可被拒绝 |
| P0-A3 | `hydromind-contracts` | `tests/test_program_validation.py` | 增加 TeamRunState transition、blocked/degraded/completed 等语义测试 | 新测试集 | 测试不只验证字段存在，还验证状态机约束 |
| P0-A4 | `hydromind-contracts` | 新增 `trace_event` / `artifact_index` 相关模型文件或统一 models 区域 | 定义 session events 与 artifact index 的结构化对象 | 新 contract 定义 | 运行事件与产物列表可被结构化消费 |

这里的关键不是“字段越多越好”，而是确保运行态对象能成为后续 CLI、UI、测试、发布、验收的共同依赖面。

### 4.2.2 任务包 B：把 hydromind CLI façade 从转发器提升为统一运行入口

当前 `hydromind/scripts/hydromind.py` 已经是平台 façade 的真实入口，这是一个很好的起点。但它还需要从“若干命令集的集合”提升成“平台运行入口”。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P0-B1 | `hydromind` | `scripts/hydromind.py` | 整理命令分组，明确 `session-*`、`smart-*`、`contracts-*`、`artifacts-*`、`trace-*` 的边界 | 命令树重构 | 用户可从命令树看出平台语义，而不是 legacy 语义 |
| P0-B2 | `hydromind` | `scripts/hydromind.py` | 新增 `session-status`、`session-events`、`session-artifacts` 等查询入口 | 新 CLI 子命令 | 不依赖页面也能完整读取运行态 |
| P0-B3 | `hydromind` | `scripts/hydromind.py` 或拆分出的 runtime 模块 | 将 session 生命周期写入统一目录结构与标准 JSON/NDJSON 产物 | 统一 session 工件目录 | 每次 run 都有稳定的状态、事件、artifact 出口 |
| P0-B4 | `hydromind` | 测试目录 | 为 façade 建立行为测试，覆盖 start / advance / status / events / error | CLI 行为测试 | CLI 输出可作为宿主与自动化的基准面 |

### 4.2.3 任务包 C：定义 artifact 与 contract 的统一落盘规则

如果对象存在但落盘位置和命名不统一，后续宿主、自动化和验收都会继续靠猜。P0 必须统一这些规则。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P0-C1 | `hydromind` | runtime/session 存储模块 | 约定 session 目录、contracts 目录、events、artifacts 的相对路径 | 存储规范 | 任意 session 的关键产物都可被稳定定位 |
| P0-C2 | `hydromind-contracts` | 相关模型或文档 | 规定 artifact index 引用规范、路径语义与 mime/type 信息 | 统一 artifact 引用规范 | 页面和 CLI 不再手工拼路径 |
| P0-C3 | `hydromind` | 文档目录 | 输出一份 runtime artifact layout 文档 | 平台存储规范文档 | 后续各仓开发统一引用同一规范 |

## 4.3 P0 的仓库分工

| 仓库 | P0 职责 |
|------|----------|
| `hydromind-contracts` | 定义运行态 contract、校验器、测试 |
| `hydromind` | 提供 façade、session 生命周期、trace/artifact 查询 |
| `hydromind-studio` | 暂不主导开发，只适配已稳定的 façade |
| `hydromind-model-core` | 保持 provider 能力，但不主导运行态真相 |
| `research/Hydrology` | 仅保留 legacy shim 参考，不新增平台真相逻辑 |

## 4.4 P0 的先后顺序

P0 不应一开始就写很多 UI 配套，而应该先把真相层做对。建议顺序如下。

| 顺序 | 任务 |
|------|------|
| 1 | 扩展 TeamRunState 与相关运行态模型 |
| 2 | 增加 program validation 的状态机校验 |
| 3 | 调整 hydromind CLI 的 session/trace/artifact 入口 |
| 4 | 统一 session 落盘与 artifact layout |
| 5 | 完善 CLI 与 contract 测试 |

## 4.5 P0 的最终验收标准

P0 验收时，不应只看代码完成量，而应满足下面这些标准。

| 验收项 | 标准 |
|------|------|
| Runtime truth | 至少存在统一的 TeamRunState、events、artifact index 三类对象 |
| CLI façade | `hydromind` 可独立完成 session 启停、状态查询、事件查询、artifact 查询 |
| 状态校验 | 非法 transition 能被 contracts 层拒绝 |
| 产物稳定性 | 任一 session 都能稳定找到状态、事件与关键产物 |
| 宿主可消费性 | 不读 legacy 脚本路径也能消费运行态 |

---

# 五、P1 细化方案：切断 Studio 对 legacy 执行面的直接耦合

## 5.1 P1 的完成定义

P1 的本质是：**Studio 不再直接依赖 `research/Hydrology` 的 gateway、脚本路径或命令拼接逻辑来驱动主流程。** 它可以继续通过 shim 兼容 legacy provider，但这种兼容必须经过 `hydromind` façade 或 adapter layer，而不是页面直连。

P1 完成后，至少要做到：页面上的动作统一落到平台入口；宿主只关心 host binding，不关心具体领域执行路径；legacy 只是 provider/shim，而不是 UI 的直接后端。

## 5.2 P1 的核心任务包

### 5.2.1 任务包 A：重构 Studio bridge，把页面动作统一收口到 hydromind façade

现阶段 `hydromind-studio/api/tauri_bridge.js` 与 `hooks/useAgentLoopGatewaySession.js` 明显还带着 legacy gateway 模式。P1 的第一任务，就是把这条线收回来。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P1-A1 | `hydromind-studio` | `api/tauri_bridge.js` | 把 `agent_loop_gateway_*` 相关直连调用抽象为 platform runtime 调用，如 `sessionStart`、`sessionSend`、`sessionStatus`、`sessionArtifacts` | 新版 bridge API | 页面不再感知 legacy gateway 名称 |
| P1-A2 | `hydromind-studio` | `hooks/useAgentLoopGatewaySession.js` | 重命名并重构为 host-agnostic session hook，例如 `usePlatformSession` | 新 hook | Hook 面向平台语义，不面向 gateway 细节 |
| P1-A3 | `hydromind` | façade 或 host binding 模块 | 提供 Studio 可直接消费的 host-safe 调用协议 | 平台宿主绑定入口 | 桌面宿主与浏览器宿主调用面一致 |
| P1-A4 | `hydromind-studio` | 测试目录 | 为 bridge 与 hook 建立 fixture 测试，验证平台调用而非 legacy 调用 | 测试用例 | 前端测试桩不再建立在 legacy 命令之上 |

### 5.2.2 任务包 B：清理 AgentWorkspace 中的 legacy 感知逻辑

`AgentWorkspace.jsx` 现在已经具有平台工作台雏形，但其中仍混有 case shell、review assets 路径、legacy 上下文拼接等旧执行面感知。P1 需要把这些逻辑从页面剥离。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P1-B1 | `hydromind-studio` | `pages/AgentWorkspace.jsx` | 把页面中的 case shell、contract path、notebook path 推导逻辑迁移到 platform client 层 | 更薄的页面组件 | 页面只负责展示与触发，不负责路径推断 |
| P1-B2 | `hydromind-studio` | `api/hydromind_client` 相关文件 | 建立明确的 `getCaseContext`、`getRunContext`、`chat`、`listArtifacts` 等 client 方法 | 新 client API | 页面通过统一 client 取上下文与产物 |
| P1-B3 | `hydromind` | façade | 提供 case context / run context / artifact index 接口 | 平台上下文接口 | 页面不再直读研究目录结构 |
| P1-B4 | `hydromind-studio` | 组件目录 | 将运行态展示、报告展示、上下文展示拆为独立组件 | 更清晰组件边界 | 便于后续 P3 自动化稳定定位 DOM |

### 5.2.3 任务包 C：建立 provider adapter layer，明确 legacy 的合法位置

P1 的另一个核心，不是彻底删掉 legacy，而是**把 legacy 放到 provider adapter 层的正确位置**。这需要 platform bridge、provider catalog、execution adapter 一起定义。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P1-C1 | `hydromind` | `configs/bridges/platform_bridge_manifest.v1.yaml` | 明确 host → runtime → provider 的桥接边界 | 更新后的 bridge manifest | 平台层与 provider 层职责明确 |
| P1-C2 | `hydromind` | `configs/adapters/execution_adapter_catalog.v1.yaml` | 将 legacy provider、shim provider、新 provider 统一登记 | adapter catalog | provider 不再藏在页面或脚本拼接里 |
| P1-C3 | `hydromind-model-core` | provider 执行入口 | 统一 provider 调用签名，确保由平台发起调用 | provider adapter 接口 | 平台可替换 provider 而不改 UI |
| P1-C4 | `research/Hydrology` | legacy gateway / workflow | 标记 legacy 仅作为 shim，不再新增 UI 直连入口 | 遗留适配边界 | legacy 不再对前台暴露产品级 API |

## 5.3 P1 的仓库分工

| 仓库 | P1 职责 |
|------|----------|
| `hydromind-studio` | 清理 bridge、hook、workspace 页面中的 legacy 耦合 |
| `hydromind` | 提供稳定 façade、host binding、runtime 调用协议 |
| `hydromind-model-core` | 将领域执行暴露为 provider adapter，而非宿主私有入口 |
| `hydromind-contracts` | 根据需要补强 host binding、provider capability 合同 |
| `research/Hydrology` | 限制为兼容层与参考实现 |

## 5.4 P1 的先后顺序

| 顺序 | 任务 |
|------|------|
| 1 | 重构 tauri bridge 的平台调用接口 |
| 2 | 重构 session hook 为 host-agnostic 平台 hook |
| 3 | 从 AgentWorkspace 剥离 legacy 路径感知逻辑 |
| 4 | 整理 bridge manifest 与 execution adapter catalog |
| 5 | 用测试桩验证前端只调用平台语义 |

## 5.5 P1 的最终验收标准

| 验收项 | 标准 |
|------|------|
| 页面调用面 | 页面主动作全部落到 hydromind façade / runtime |
| Legacy 去耦 | Studio 代码中不再直接依赖 `agent_loop_gateway.py` 作为主路径 |
| Host binding | 浏览器模式与桌面模式消费同一平台接口语义 |
| Provider 注册 | provider 调用统一经 adapter catalog 暴露 |
| 前端稳定性 | 关键页面状态与运行态展示可被稳定测试与断言 |

---

# 六、P2 细化方案：用新 case 证明平台通用性与端到端主链

## 6.1 P2 的完成定义

P2 的目标不是再把 six-case 做得更漂亮，而是要回答一个关键问题：**HydroMind 是否已经可以脱离历史样例中心主义，服务一个新的涉水场景，从基础资料进入自主运行主链。**

因此，P2 的完成必须包含一个非 six-case 新 case 的真实 onboarding → run → review → release 验证。six-case 仍然重要，但它们此时应退回到回归样本与质量基线，而不是平台主语义来源。

## 6.2 P2 的核心任务包

### 6.2.1 任务包 A：建立新 case onboarding 标准链

P2 第一件事，是把“新 case 如何进入平台”做成标准链，而不是手工复制样例目录。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P2-A1 | `hydromind-contracts` | `case_manifest` 相关 schema / model | 明确新 case onboarding 的最小输入集、来源描述、依赖能力声明 | 更完整的 CaseManifest 约束 | 新 case 可依据模板独立建档 |
| P2-A2 | `hydromind` | façade / case bootstrap 命令 | 新增 `case-init`、`case-validate`、`case-bootstrap` 一类入口 | 新 case 初始化命令 | 不需要复制 six-case 才能新建 case |
| P2-A3 | `hydromind-model-core` | 数据准备入口 | 为数据预处理、建模前置检查、参数治理建立标准 provider 调用 | onboarding provider | 新 case 能完成基础数据准备 |
| P2-A4 | 文档层 | 平台 docs | 写清新 case onboarding 操作说明与最小资料要求 | onboarding 指南 | 团队成员可按文档接入新 case |

### 6.2.2 任务包 B：打通 run → review → release 的完整主链

新 case 建进来以后，如果 run、review、release 仍然依赖手工脚本或人工串接，就无法证明平台能力。P2 必须把这条链变成真正的主链。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P2-B1 | `hydromind` | session/run orchestration 模块 | 实现从 case context 到 workflow orchestration 的标准入口 | run orchestration | 一条命令或一次平台调用即可起跑 |
| P2-B2 | `hydromind-model-core` | workflow 执行入口 | 将数据挖掘、模型计算、校核评估、报告整理接入标准 provider 流 | workflow provider 流 | 关键阶段可被统一编排 |
| P2-B3 | `hydromind` | report / review / release 聚合入口 | 统一产出 ReviewBundle、ReadinessBoard、ReleaseManifest、FinalReport | 报告与发布对象 | review 与 release 不再靠散文件拼接 |
| P2-B4 | `hydromind-contracts` | 相关 contract 与校验 | 校验 run / review / release 对象一致性 | contract consistency | 主链输出可被自动校验 |

### 6.2.3 任务包 C：建立 six-case 回归基线与新 case 对照验证

P2 不意味着抛弃 six-case。恰恰相反，six-case 应转为平台回归基线，用于判断平台重构有没有退化。同时，新 case 要作为通用性证明。

| 任务编号 | 建议仓库 | 关键文件 | 具体动作 | 交付物 | 验收标准 |
|------|----------|----------|----------|--------|----------|
| P2-C1 | `hydromind` | 测试/回归脚本 | 选定 1~2 个 six-case 作为回归基线 | 回归脚本 | 每轮重构可稳定复跑 |
| P2-C2 | `hydromind` + `hydromind-model-core` | 新 case 数据与配置 | 选择 1 个非 six-case 新场景进行真实接入 | 新 case 演示资产 | 不依赖样例硬编码可接入 |
| P2-C3 | `hydromind-studio` | case 浏览与结果展示页 | 展示回归样例与新 case 的结果对照 | 对照展示能力 | 能看出“样例通过”与“新 case 通过” |
| P2-C4 | 文档层 | 平台 docs | 写出平台通用性验证记录与差距清单 | 通用性验证文档 | 后续迭代有清晰 backlog |

## 6.3 P2 的仓库分工

| 仓库 | P2 职责 |
|------|----------|
| `hydromind` | 负责 onboarding façade、run/review/release 主链编排 |
| `hydromind-model-core` | 提供真实数据准备、建模与报告 provider 能力 |
| `hydromind-contracts` | 保障 case、run、review、release 对象的一致性与校验 |
| `hydromind-studio` | 提供可观察入口，但不主导业务真相 |
| `research` 系列 | 提供历史算法、资料与参考，但不再作为主入口 |

## 6.4 P2 的先后顺序

| 顺序 | 任务 |
|------|------|
| 1 | 新 case onboarding contract 与 CLI 初始化入口 |
| 2 | 标准 run orchestration 接通 provider 流 |
| 3 | review / release / final report 聚合出口 |
| 4 | six-case 回归与新 case 通用性对照验证 |
| 5 | 编写平台通用性验收记录 |

## 6.5 P2 的最终验收标准

| 验收项 | 标准 |
|------|------|
| 新 case onboarding | 一个非 six-case 新 case 可在不复制样例目录的情况下进入平台 |
| 主链打通 | 新 case 可完成 onboarding → run → review → release |
| 对象一致性 | CaseManifest、WorkflowRun、ReviewBundle、ReleaseManifest、FinalReport 全部齐备且可校验 |
| 回归基线 | 至少 1~2 个 six-case 样例可稳定复跑 |
| 通用性证明 | 平台已能服务新场景，而不是仅服务历史样例 |

---

# 七、三个分层之间的依赖关系

P0、P1、P2 之间有严格依赖，不应打乱顺序。

| 前置层 | 后续层依赖点 | 原因 |
|------|--------------|------|
| P0 → P1 | runtime/session/contract truth | 不先统一真相层，P1 只是在不同壳之间搬 legacy 逻辑 |
| P1 → P2 | façade / adapter / host binding | 不先切断 UI 与 legacy 直连，P2 只会把新 case 强行接到旧系统 |
| P0 → P2 | artifact / trace / review 输出规范 | 不先统一产物结构，P2 无法形成可验收主链 |

因此，**推荐不要把 P2 提前到 P1 前面。** 任何试图“先接一个新 case 看看”的做法，都会把平台债务继续带入下一阶段。

---

# 八、建议的里程碑设置

为了便于排期与组织协作，我建议将三个分层各自定义一个里程碑门槛。

| 里程碑 | 对应层次 | 通过条件 |
|------|----------|----------|
| M1 | P0 完成 | contracts + session + trace + artifact truth 成型 |
| M2 | P1 完成 | Studio 已不再直连 legacy gateway，主动作全部走 façade |
| M3 | P2 完成 | 新 case 完成端到端主链，six-case 退回回归基线 |

如果要继续向后推进到 P3，那么 M3 应作为 P3 的前提，而不是可选项。

---

# 九、我建议优先落地的文件级动作

下面这张表把最值得优先动手的文件进一步收敛出来，便于直接进入开发。

| 优先级 | 仓库 | 文件 | 动作 |
|------|------|------|------|
| 高 | `hydromind-contracts` | `hydromind_contracts/models.py` | 扩展 TeamRunState、trace、artifact 相关模型 |
| 高 | `hydromind-contracts` | `hydromind_contracts/program_validation.py` | 增加状态迁移与运行态一致性校验 |
| 高 | `hydromind` | `scripts/hydromind.py` | 建立稳定 session/trace/artifact façade |
| 高 | `hydromind-studio` | `api/tauri_bridge.js` | 从 legacy gateway 语义迁移到平台 runtime 语义 |
| 高 | `hydromind-studio` | `hooks/useAgentLoopGatewaySession.js` | 改造为 host-agnostic 平台 session hook |
| 高 | `hydromind-studio` | `pages/AgentWorkspace.jsx` | 剥离 legacy 路径、shell、case 目录感知逻辑 |
| 中 | `hydromind` | `configs/bridges/platform_bridge_manifest.v1.yaml` | 固化 host→runtime→provider 边界 |
| 中 | `hydromind` | `configs/adapters/execution_adapter_catalog.v1.yaml` | 明确 provider / shim provider 注册与适配 |
| 中 | `hydromind-model-core` | provider 执行入口文件 | 统一 provider 调用签名与返回对象 |
| 中 | `hydromind` | case bootstrap / runtime 文档 | 输出 onboarding 与 artifact layout 文档 |

---

# 十、结论

如果把这三个分层进一步压缩成一句话，那么可以这样概括：

> **P0 建立平台真相，P1 切断宿主耦合，P2 证明平台通用性。**

P0 要解决的是“平台有没有统一语言”；P1 要解决的是“页面是不是还在偷偷依赖旧系统”；P2 要解决的是“除了六案例之外，平台能不能真正面对新的涉水场景”。这三个问题回答对了，HydroMind 才能从重构工程走向真正的自主运行水网平台。

在您当前的目标下，我建议开发推进时严格坚持以下原则：

| 原则 | 含义 |
|------|------|
| runtime-first | 先把运行态真相做对，再做宿主与页面 |
| contract-driven | 所有关键对象先立合同，再立实现 |
| host-agnostic | 宿主只负责绑定，不承载业务真相 |
| provider-decoupled | 领域能力通过 adapter 暴露，不直连到页面 |
| new-case-oriented | 以新 case 通用性作为平台成熟度的最终证明 |

如果继续往下推进，下一步最自然的动作不是再写一版概念规划，而是把这份文档直接转成 **按仓库的 backlog 和 issue 清单**。那样就可以进一步细化到：谁改哪个文件、先提哪一组 PR、每一轮 review 看什么、每一阶段用什么测试和 contract 校验来收口。

---

## 附：建议与既有规划联动阅读的文档

| 文档 | 作用 |
|------|------|
| `HydroMind_Review_and_Planning_Report.md` | 总体评审与战略判断 |
| `HydroMind_Updated_Assessment_After_GPT_Handoff.md` | 吸收 GPT handoff 后的校正版判断 |
| `HydroMind_P3_UI_Automation_Acceptance_Plan.md` | 界面自动化与浏览器 E2E 的后续验收层规划 |

这三份文档与本文配合起来，已经构成了从 **评审 → 校正 → 分层实施 → 验收演进** 的完整规划链。
