# HydroMind P3 界面自动化验收层规划

**作者：** Manus AI  
**日期：** 2026-04-15

---

## 一、P3 的定位

P3 不是再做一层新的业务逻辑，也不是把已有 CLI 简单套到页面上，而是要建立一套**可被界面消费、可被浏览器自动化执行、可被标准化验收复现**的端到端验收层。其目标是把 HydroMind 从“平台骨架可用”推进到“产品主链可验证、可回归、可演示、可签收”的阶段。

在这个阶段，真正需要验证的不是某个按钮是否能点击，而是下面这条链是否已经成为统一主链：**数据源选择 → case/onboarding 识别 → 数据挖掘与准备 → workflow 执行 → session/trace 可观测 → 产物汇聚 → 报告输出 → 结果回看与签发。**

因此，P3 的本质不是前端美化，而是为自主运行水网平台建立**面向宿主、面向测试、面向验收**的统一交互层与自动化层。

---

## 二、P3 想解决的核心问题

当前 HydroMind 已经具备平台化骨架，但从界面自动化角度看，还存在一个明显断层：运行时骨架、contracts、provider 和宿主界面之间尚未形成统一的、可自动化消费的产品链路。浏览器自动化如果现在直接介入，很容易沦为“点页面后触发 legacy 脚本”，这不是真正的平台验收。

P3 的核心任务，就是把“界面动作”和“平台动作”对齐。界面上的每一次操作，最终都应落到统一的 runtime/session/contract 语义上，而不是散落在特定宿主的脚本拼接与路径约定之中。

| P3 核心问题 | 当前风险 | P3 目标 |
|------|------|------|
| 数据源选择依赖人工目录操作 | 自动化难、复现差 | 形成标准化数据源选择能力 |
| 页面按钮仍可能绕过平台真相层 | CLI 与界面行为不一致 | 页面统一调用 hydromind façade / bridge |
| 长任务执行不可稳定观测 | E2E 测试无法判定中间阶段 | 暴露 session、events、trace、artifacts |
| 报告输出不稳定或对象不统一 | 验收无法标准化 | 统一落到 ReviewBundle / ReleaseManifest / FinalReport |
| 桌面宿主与浏览器宿主分叉 | 自动化脚本难复用 | 先定义 host-agnostic 交互协议，再适配具体宿主 |

---

## 三、P3 的验收目标

P3 完成后，至少应具备一条**可被浏览器自动化完整执行**的验收主链。这条主链不要求一次性覆盖所有复杂场景，但必须覆盖最关键的产品闭环。

### 3.1 标准 E2E 主链

建议将第一条标准主链定义为：

| 阶段 | 页面动作 | 平台动作 | 期望产物 |
|------|----------|----------|----------|
| 1 | 选择数据源目录或数据包 | 解析并建立数据源会话上下文 | SourceBundle / 导入记录 |
| 2 | 选择或创建 case | 生成或绑定 CaseManifest | CaseManifest |
| 3 | 点击开始数据准备/挖掘 | 触发数据准备 workflow | DataPack / WorkflowRun |
| 4 | 点击执行建模或自主运行链 | 启动 session-run / workflow orchestration | TeamRunState / WorkflowRun / trace |
| 5 | 查看运行中状态 | 拉取 session-status / events / artifact index | TeamRunState / event stream |
| 6 | 查看评审与报告 | 聚合 review / release / final report | ReviewBundle / ReleaseManifest / FinalReport |
| 7 | 导出或打开结果 | 访问标准化产物出口 | 报告文件、结构化 JSON、可视结果 |

### 3.2 P3 的完成标准

P3 不以“页面功能越来越多”为完成标准，而以以下条件成立为完成标准：

第一，浏览器自动化可以稳定重放一条完整主链。  
第二，界面、CLI、宿主桥接消费的是同一套 runtime 和 contract truth。  
第三，结果判定可以依赖标准产物，而不是靠页面文案猜测。  
第四，至少能在一个 six-case 样例和一个非 six-case 新 case 上通过。

---

## 四、P3 的推荐架构边界

P3 要成功，最关键的是不要再让界面层直接持有领域执行真相。界面层只应负责选择、触发、展示和验收，而不应直接知道 legacy workflow 路径。

建议采用下表中的职责切分。

| 层次 | 职责 | 不应承担的职责 |
|------|------|----------------|
| UI / Workbench | 选择数据源、配置运行、展示状态与报告 | 不直接拼接 sibling repo 脚本路径 |
| Bridge / Client | 把页面动作翻译为统一平台调用 | 不承载领域业务真相 |
| Runtime / Session | 负责编排、状态推进、事件记录、artifact 汇聚 | 不依赖具体前端组件 |
| Provider Adapter | 调用 model / control / verification / legacy shim | 不暴露宿主差异 |
| Contracts Layer | 定义 case、run、review、release、report 真相对象 | 不做页面兜底计算 |

这里的原则非常重要：**浏览器自动化测的是平台，不是某个宿主私有行为。** 因此 P3 的自动化脚本，应优先验证 contracts、session、artifact 和报告链，而不是验证 UI 层的特殊实现细节。

---

## 五、P3 的分层任务设计

我建议把 P3 再拆成四个可执行子阶段，这样既能与 P0/P1/P2 顺接，也便于逐步落地。

### 5.1 P3-A：建立“可自动化的数据源选择能力”

当前最容易卡住浏览器自动化的，并不是模型本身，而是“选择数据源目录”这一动作。如果它只能依赖原生系统文件选择框，那么自动化会脆弱且跨宿主不可复用。

因此，P3-A 的目标是把数据源选择抽象成统一能力，建议支持两种入口：一种是**浏览器可控的数据包导入**，另一种是**工作区相对路径/注册路径选择**。这样无论是 Web 工作台还是桌面宿主，都可以通过同一 contract 或 action 触发数据导入。

| 子项 | 建议仓库 | 关键文件/区域 | 推荐动作 | 验收标准 |
|------|----------|---------------|----------|----------|
| 数据源选择 contract | `hydromind-contracts` | 新增 SourceSelection 或 SourceBundle 输入约束 | 为界面选择动作定义结构化输入对象 | 能独立校验目录/数据包选择请求 |
| 数据源导入 façade | `hydromind` | `scripts/hydromind.py` | 增加 `source-select` / `source-import` 类入口 | CLI 与界面都可触发同一导入动作 |
| 界面选择器 | `hydromind-studio` | AgentWorkspace 或独立 DataSource 页面 | 提供“选择工作区目录 / 上传包 / 输入相对路径”三种入口 | 无需依赖原生系统文件弹窗即可完成测试 |
| 选择结果持久化 | `hydromind-runtime` 或 `hydromind` | session/context 存储位置 | 将选中的数据源绑定到 case/session | 后续 workflow 能复用同一上下文 |

### 5.2 P3-B：建立“可观测的运行主链界面”

页面若只能点击“开始”，却不能持续观测 session 状态、events、artifacts 和失败语义，那么自动化测试就只能靠固定等待时间与猜测结果，这是不可接受的。

因此，P3-B 的目标是让页面具有真正的运行态可观测性，并且这些状态来自平台真相层，而不是前端自算。

| 子项 | 建议仓库 | 关键文件/区域 | 推荐动作 | 验收标准 |
|------|----------|---------------|----------|----------|
| session-run 主入口 | `hydromind` | `scripts/hydromind.py` | 新增统一 `session-run` / `session-execute` | 页面不再直接调 legacy workflow |
| TeamRunState 扩展 | `hydromind-contracts` | `models.py`、`program_validation.py` | 引入 stage、step、provider、artifact summary 等字段 | 运行中每一阶段都有结构化状态 |
| trace / events API | `hydromind` 或 `hydromind-runtime` | session 事件读写模块 | 暴露标准事件流与 trace 查询 | 自动化脚本可轮询并可靠判断进度 |
| 运行态展示组件 | `hydromind-studio` | AgentRuntimeStatusPanel、AgentWorkspace | 页面显示 current stage、status、error、artifact links | 自动化脚本可基于稳定 DOM 或 JSON 数据断言 |

### 5.3 P3-C：建立“标准报告出口与验收断言面”

P3 的自动化不是只验证“任务跑完了”，而是要验证“产物齐、对象对、报告可读、结果可签”。因此必须把验收断言建立在标准报告出口上。

| 子项 | 建议仓库 | 关键文件/区域 | 推荐动作 | 验收标准 |
|------|----------|---------------|----------|----------|
| 报告聚合出口 | `hydromind` / `hydromind-model-core` | final report assembly 相关入口 | 确保页面读取统一 FinalReport | 页面不再依赖散乱 JSON 拼接 |
| artifact index | `hydromind-runtime` 或 `hydromind` | session/artifact registry | 输出标准 artifact 列表与路径 | 自动化可验证报告与证据是否齐全 |
| 报告浏览页面 | `hydromind-studio` | NLReportRenderer、Review/Release 页面 | 将 FinalReport、ReviewBundle、ReleaseManifest 渲染为稳定视图 | 页面断言与 JSON 断言一致 |
| 导出动作 | `hydromind-studio` / `hydromind` | 报告导出按钮与后台接口 | 支持下载或打开标准报告文件 | 自动化可完成下载与内容校验 |

### 5.4 P3-D：建立“浏览器 E2E 脚本与验收基线”

当 P3-A、P3-B、P3-C 成形后，最后才是把它们收束成自动化验收脚本。这里不建议先写很多脚本，而应先定义少而稳的验收基线。

| 子项 | 建议仓库 | 关键文件/区域 | 推荐动作 | 验收标准 |
|------|----------|---------------|----------|----------|
| smoke E2E | `hydromind-studio` | Playwright/Cypress 测试目录 | 跑通最短主链：选数据源 → 执行 → 出报告 | 每次提交都能跑 |
| regression E2E | `hydromind-studio` + `hydromind` | 测试配置与 fixture | 覆盖一个 six-case 样例与一个新 case | 平台通用性可证明 |
| host parity 验证 | `hydromind` | CLI 与页面对照脚本 | 对照 CLI 输出与页面输出是否一致 | contract 与 report 一致 |
| failure semantics 验证 | `hydromind` + `hydromind-studio` | blocked/degraded/failed 场景脚本 | 验证失败语义在界面中可正确显示 | 失败不再被页面吞没 |

---

## 六、浏览器自动化与桌面宿主的推荐路径

您前面特别关心“能不能通过界面看到并自动操作”，这里需要把路径明确成两段，而不是混在一起。

### 6.1 第一优先：先做浏览器可访问的工作台模式

最推荐的路径，是先让 HydroMind/Studio 具备一个**浏览器可访问的工作台模式**。这不一定要求彻底放弃桌面宿主，而是要求核心主链在浏览器中可被完整复现。原因很直接：浏览器自动化成熟、稳定、可 CI、可录制、可回放，也更适合您远程查看结果。

如果采用这一模式，后续可以做到：

| 能力 | 效果 |
|------|------|
| 浏览器自动化运行 | 可直接点击、输入、上传、断言结果 |
| 临时对外访问 | 可暴露临时地址供您直接打开查看 |
| 运行日志和产物归档 | 可稳定保存截图、页面 HTML、下载报告、trace |
| CI 回归 | 可作为平台每轮重构后的冒烟基线 |

### 6.2 第二优先：桌面宿主保留，但不作为第一验收面

HydroDesk 仍然非常重要，因为它代表桌面工作台与多宿主平台前台。但我建议在 P3 里把它定位成**第二验收面**。也就是说：先在浏览器工作台上把主链跑通，再把同一条主链映射回桌面宿主。

这么做的原因在于，桌面应用常涉及系统文件框、原生事件、子进程管理等复杂因素。如果把它作为第一 E2E 面，平台问题和宿主问题会混在一起，调试成本会很高。

---

## 七、P3 完成后应能支持的标准测试场景

P3 完成后，我建议至少支持下列四类测试场景。这样才能既覆盖产品主链，也覆盖平台级稳定性。

| 场景 | 目标 | 是否必须 |
|------|------|----------|
| 样例 smoke 测试 | 证明最短主链可运行 | 是 |
| 新 case onboarding 测试 | 证明平台不是为 six-case 硬编码 | 是 |
| degraded / blocked / failed 测试 | 证明失败语义能被产品面正确消费 | 是 |
| 报告导出与对照测试 | 证明页面报告与 contract/report truth 一致 | 是 |

这些场景应该共同构成 P3 的最小验收包，而不是只保留 happy path。

---

## 八、我建议的具体仓库分配

根据当前多仓结构，P3 不应全部塞进 `hydromind-studio`，否则会再次走向“前台承载平台真相”的老路。更合理的分工如下。

| 仓库 | P3 主要职责 |
|------|-------------|
| `hydromind` | 提供统一 façade、session-run、source-select、artifact-list、trace-show 等入口 |
| `hydromind-contracts` | 扩展 Source/Session/Trace/Artifact 等契约与校验 |
| `hydromind-runtime`（若已拆分或将拆分） | 承载运行态状态机、事件流、artifact index |
| `hydromind-studio` | 提供页面工作台、展示状态、触发动作、承接自动化脚本 |
| `hydromind-model-core` | 提供数据准备、建模、报告等 provider 执行能力 |
| `research/Hydrology` | 仅作为过渡 legacy/shim，不再直接暴露给页面 |

这个分工能够保证：界面层不再吞并平台层，平台层也不需要知道宿主组件细节。

---

## 九、P3 的建议实施顺序

为了降低风险，我建议 P3 按下面顺序推进，而不是并行铺开。

### 第一步：把“选择数据源”变成结构化动作

先解决目录选择与数据包导入，因为这是浏览器 E2E 最容易被系统弹窗阻断的地方。只要这个动作没有结构化，后面所有自动化都会不稳定。

### 第二步：把“运行主链”变成 session-run 驱动

接着解决页面触发统一主链的问题，让页面不再直连 legacy gateway，而是只触发 platform runtime。这样自动化脚本才是在测平台。

### 第三步：把“结果判断”变成 contract/report 断言

再之后把页面结果对齐到 `TeamRunState`、`WorkflowRun`、`ReviewBundle`、`FinalReport` 等对象。自动化脚本不应仅依赖肉眼 UI 文本，而应能校验结构化结果。

### 第四步：最后再补浏览器 E2E 套件

只有当前三步成立后，自动化脚本才值得系统化建设。否则脚本只会跟着不稳定界面反复修改。

---

## 十、P3 的最终验收定义

我建议把 P3 的最终验收定义为下面这个表，而不是一句模糊的“浏览器自动化可用了”。

| 验收项 | 验收标准 |
|------|----------|
| 数据源选择 | 浏览器中无需人工系统文件弹窗即可完成数据源导入或绑定 |
| 主链触发 | 页面点击后实际触发的是 hydromind runtime/session 主链 |
| 过程可观测 | 页面可稳定显示 session 状态、events、artifacts、错误语义 |
| 结果可交付 | 页面可查看并导出 FinalReport 等标准对象 |
| 样例回归 | 至少 1 个 six-case 样例通过完整 E2E |
| 通用性证明 | 至少 1 个非 six-case 新 case 通过 onboarding → run → review → release |
| 宿主一致性 | 页面结果与 CLI / contract truth 一致 |

只要这个表中的项目全部成立，就可以说 HydroMind 已经具备了**界面化端到端自动验收能力**。

---

## 十一、我的结论与建议

我的总体建议是：**P3 应被视为平台从“能开发”走向“能验收、能演示、能回归”的关键层。** 如果 P0/P1/P2 负责把平台骨架、宿主去耦和通用性验证做对，那么 P3 负责把这些能力变成真正可见、可测、可签收的产品闭环。

对于您关心的“能否通过界面完成数据源选择、数据挖掘、模型计算、结果报告输出，并进行端到端测试”，答案是：**能，但前提是 P3 必须坚持 host-agnostic、runtime-first、contract-driven 这三个原则。**

如果继续沿着这个方向推进，我建议下一步直接把本规划再收束成一份更细的 **P3 实施任务表**，精确到：

1. 每个仓库需要新增或修改的命令与文件；  
2. 页面上需要新增的交互控件与状态展示区；  
3. 自动化脚本的首批测试用例清单；  
4. 浏览器模式与桌面模式的分阶段验收方式。

这样下一轮就可以从“规划文档”直接过渡到“可执行开发 backlog”。

---

## 附：本规划直接依据的关键实现面

| 类型 | 文件 |
|------|------|
| 平台 façade | `hydromind/scripts/hydromind.py` |
| contracts 模型 | `hydromind-contracts/hydromind_contracts/models.py` |
| contracts 校验 | `hydromind-contracts/hydromind_contracts/program_validation.py` |
| 宿主桥接 | `hydromind-studio/api/tauri_bridge.js` |
| 宿主会话 hook | `hydromind-studio/hooks/useAgentLoopGatewaySession.js` |
| 工作台页面 | `hydromind-studio/pages/AgentWorkspace.jsx` |
| Studio 命令耦合面 | `hydromind-studio/config/hydrodesk_commands.js` |
| legacy gateway | `research/Hydrology/workflows/agent_loop_gateway.py` |

这份 P3 规划的核心价值，在于把“界面能不能自动化”这个问题，从单纯的测试问题，上升为平台设计与宿主接线问题来处理。只有这样，后续的端到端测试才不会沦为脆弱的页面脚本，而会真正成为 HydroMind 平台演进的标准验收面。
