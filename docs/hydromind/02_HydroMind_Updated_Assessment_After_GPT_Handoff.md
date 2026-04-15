# HydroMind 更新版评审与规划结论

**作者：** Manus AI  
**日期：** 2026-04-15

---

## 一、校正后的总体判断

结合您补充的 GPT 历史研发进展材料，以及我对 `research`、`hydromind`、`hydromind-studio`、`hydromind-contracts` 等目录与关键文件的复核，我对当前项目状态的判断需要做一个重要校正：**HydroMind 的主问题已经不再是“六案例怎么继续补齐”，而是“如何把已被六案例验证过的一批真实能力，上升为通用的自主运行水网端到端自主建模平台能力”。**

也就是说，`six-case` 在当前体系里更适合作为**验收样本、回归样本和 smoke/regression 基线**，而不应继续充当平台语义本身。您补充的 handoff 中明确强调，当前最 authoritative 的方向是把平台真相收敛到 **case registry、workflow catalog、contracts truth layer、runtime/orchestrator、provider adapters、host bindings** 这一组对象与边界上；我复核 `hydromind/docs/platform_bridge_design.md`、`hydromind/docs/contracts_detailed_design.md`、`hydromind/scripts/hydromind.py` 之后，认为这一判断是正确的，而且比我前一版评审更接近当前真实开发状态。

换句话说，当前 HydroMind 已经从“研究仓里的能力堆叠”进入“平台化骨架成形但尚未完全解耦”的阶段。这个阶段最重要的不是再去补更多页面、更多脚本壳或更多 six-case 特例，而是把**平台 façade、contracts、session lifecycle、provider adapter、host bridge**做成真正可持续的真相层。

---

## 二、我对当前进展的更新认识

在您补充材料之前，我对项目的理解偏向于“从 research 向多仓解耦迁移，核心任务是稳步把能力搬入 hydromind 体系”。这个判断并不错误，但**不够精确**。吸收 handoff 之后，当前更精确的结论如下。

| 维度 | 之前的理解 | 结合 handoff 后的校正结论 |
|------|------------|---------------------------|
| 六案例定位 | 平台当前主线的重要组成 | **只是验收样本，不应再主导平台语义** |
| 当前开发重心 | 多仓拆分与产品化重构 | **平台真相层、runtime/orchestrator、provider 解耦** |
| HydroDesk 定位 | 已较明确的产品前台 | **方向明确，但实现上仍深度耦合 legacy Hydrology** |
| hydromind CLI | 元仓聚合入口 | **已成为平台 façade 的最关键真实入口** |
| contracts 层 | 重要基础设施 | **已上升为唯一真相层，优先级高于页面、prompt 和宿主平台对象** |
| 下一阶段优先级 | 打通更多产品面与案例面 | **先补 session-run / trace / TeamRunState / adapter layer，再谈宿主与前台彻底解耦** |

这种变化非常关键，因为它决定了后续所有规划应围绕“平台能力抽象”而非“案例壳继续堆叠”来展开。

---

## 三、当前已经成立的“平台真相面”

从 handoff 文字、设计文档和代码实现综合来看，HydroMind 目前已经出现了一个清晰的平台骨架，而且这部分骨架并不是概念，而是已经部分落地。

### 3.1 平台 façade 已出现

`hydromind/scripts/hydromind.py` 已经不是单纯的元仓辅助脚本，而是一个实际承担平台 façade 角色的统一入口。它已经具备如下特征：一方面，它聚合了 `hydromind-model-core`、`hydromind-flow-control`、`hydromind-control-verification`、`hydromind-contracts`、`hydromind-case-registry` 等多个 sibling repo 的能力；另一方面，它已经开始提供**平台级 discoverability 与 session lifecycle** 能力，包括 contracts 枚举、capabilities 枚举、provider 显示、role 推荐、session 状态管理等。

更重要的是，`hydromind.py` 中已经明确引入了 `SESSION_ADVANCE_TRANSITIONS`、`SESSION_TERMINAL_STATUSES`、`_build_team_run_state` 等运行时骨架，这表明当前工作已经不再是“单次脚本执行器”，而是在向**通用 runtime/session/orchestrator** 演化。

### 3.2 contracts 已从“规范文档”变成“行为约束层”

`hydromind/docs/contracts_detailed_design.md` 明确提出：**contract 优先于 prompt，contract 优先于页面临时计算，contract 优先于外部宿主平台自定义对象**。这实际上已经把 contracts 层提升为平台级权威对象层。

同时，`hydromind-contracts/hydromind_contracts/models.py` 已经定义了 `CaseManifest`、`WorkflowRun`、`ReviewBundle`、`ReleaseManifest`、`FinalReport`、`ReadinessBoard`、`PlatformCapability`、`ExecutionProvider`、`HostSessionBinding`、`TeamRunState` 等核心对象所需字段。这说明平台对象面并非停留在文档层，而是已经具备可验证、可被 CLI 和测试消费的代码实现基础。

### 3.3 session lifecycle 已经落下最小骨架

根据您提供的 handoff，以及我复核的 `hydromind/tests/test_hydromind_cli_and_status.py` 与 `hydromind/scripts/hydromind.py`，当前已经完成的不是一个抽象设想，而是**最小可用 session 生命周期骨架**：

| 已落地能力 | 当前状态 |
|-----------|----------|
| `session-start` | 已有最小实现 |
| `session-status` | 已有最小实现 |
| `session-events` | 已有最小实现 |
| `session-stop` | 已有最小实现 |
| `session-advance` | 已落地并有测试约束 |
| `planned -> running` | 已支持 |
| `running -> completed/blocked/degraded/failed` | 已支持 |
| 非法状态迁移失败 | 已有测试覆盖 |
| 幂等行为 | 已有测试约束 |

这意味着，平台已经从“workflow 调用器”迈入“session-aware runtime”的第一阶段。这个节点非常重要，因为它决定了后面应该继续增强状态机、trace、event stream 与 orchestration，而不是再回退到脚本堆叠式开发。

---

## 四、当前最真实的结构性问题

尽管平台骨架已经出现，但 handoff 也非常明确地指出：**当前真正的瓶颈，不是文档缺不缺，而是平台层、宿主层、provider 层、legacy 层之间仍未彻底切开。** 我同意这个判断。

### 4.1 HydroDesk 仍然深度耦合 legacy Hydrology

这是我在复核 `hydromind-studio/config/hydrodesk_commands.js` 后最确定的结论之一。该文件顶部默认路径几乎全部仍然直接指向：

> `Hydrology/workflows/*`、`Hydrology/scripts/*`、`Hydrology/configs/*`

例如 `nl_mcp_gateway.py`、`run_case_pipeline.py`、`agent_loop_gateway.py`、`build_review_bundle.py`、`run_source_sync.py` 等都仍然通过 Studio 侧命令工厂直接拼接调用。这说明 **HydroDesk 虽然在产品叙事上已经被定位为平台前台，但在实现层依然是以 Hydrology 为中心的专用壳，而不是 host-agnostic 的通用工作台。**

这也是为什么 handoff 明确提醒：后续平台化时，Studio/gateway 应该改成**只消费 hydromind/bridge/contracts**，而不是继续直连 `Hydrology/workflows/*`。

### 4.2 provider adapter layer 仍然只是骨架，不是完整隔离层

`hydromind/configs/adapters/execution_adapter_catalog.v1.yaml` 已经给出了 `model`、`assimilate`、`verify`、`report` 四类 adapter 与 provider 绑定关系。这是一个正确的方向，但目前仍然更像**结构占位**，还不是一个成熟的 provider 解耦层。

原因在于：

第一，真正的执行逻辑仍大量依赖 sibling repo 的内部实现与路径。  
第二，`hydromind` 主 CLI 中仍显式引用 `research/Hydrology` 与多个 sibling repo 的目录常量。  
第三，HydroDesk 前端也还没有通过 adapter catalog 完整解析 provider，而是在很多场景继续构造 legacy command。

因此，目前可以说**adapter catalog 已经形成了设计真相层的入口，但尚未形成运行时真相层的唯一执行入口**。

### 4.3 TeamRunState 只是“存在”，还不是“完整状态机”

`TeamRunState` 进入 contracts 与代码模型，已经非常有价值。但 handoff 也明确指出，当前停止点只是**最小 session lifecycle skeleton**。这意味着：

- 目前还没有真正的 `session-run` 或 `session-execute` 统一执行器；
- 还没有更完整的 trace / event stream 语义；
- TeamRunState 还没有发展成覆盖多阶段、多 agent、多 provider 的完整 stage/state machine。

因此，当前的 TeamRunState 更适合被定义为：**已经被“制度化”但还没有被“工程化完成”的平台对象。**

### 4.4 新 case onboarding 仍未证明平台真正通用

handoff 特别强调：**后续真正的平台级验收，不是 six-case 全过，而是能对非六案例的新 case 完成 onboarding → run → review → release。** 这一点非常关键。

这意味着当前项目虽然已经拥有一批强样例和很强的案例能力，但平台的“通用性证明”仍然不足。换句话说，现阶段仍存在“样例驱动成功，但平台抽象尚未完全摆脱样例经验”的风险。

---

## 五、对 `research` 与 `hydromind` 关系的更新判断

现在我会把二者关系定义得更清楚一些。

| 层次 | 当前角色 | 评审结论 |
|------|----------|----------|
| `research` | 历史现场、legacy 执行面、能力来源地 | **仍是关键能力来源，但不应再充当平台真相源** |
| `hydromind` | 平台元仓、docs/configs/CLI façade | **正在成为 authoritative 的平台定义面** |
| `hydromind-contracts` | 对象真相层 | **已经是平台稳定化的核心基础设施** |
| `hydromind-model-core` | 主建模与报告 provider | **承接 legacy Hydrology 的主要平台化迁移方向** |
| `hydromind-studio` | 前台宿主/工作台 | **产品定位正确，但实现尚未完成 host-agnostic 解耦** |

因此，后续不应再把“research 里有什么能力”视为首要问题，而应把“哪些能力已经上升为 platform contract / adapter / runtime / host binding”视为首要问题。

---

## 六、我建议采用的下一阶段开发顺序

结合 handoff 中给出的建议顺序、当前代码状态以及我自己的评审，我认为后续最合理的推进路径应当分成 **P0、P1、P2** 三层，而不是平均铺开。

### 6.1 P0：把平台运行时骨架补完整

P0 不是 UI，也不是再写更多文档，而是把 `hydromind` 真正做成平台 runtime façade。优先内容如下：

| P0 子项 | 目的 | 结论 |
|--------|------|------|
| `session-run` / `session-execute` | 从“状态骨架”升级为“统一执行入口” | **最高优先级** |
| trace / events 语义细化 | 让 TeamRunState 能表达阶段推进、失败、降级、交接 | **最高优先级** |
| WorkflowRun 与 TeamRunState 联动 | 把 workflow 事实和 session 事实统一起来 | **最高优先级** |
| stage/state machine 扩展 | 从最小状态集合升级为真实 orchestration 模型 | **高优先级** |

如果这一层不先完成，后续 HydroDesk 去耦、WorkBuddy 接线、Claude Code/Codex 接线都只能停留在“外壳统一”，而不是“运行面统一”。

### 6.2 P1：切断 Studio 与主流程对 legacy 的直连

P1 的核心不是“重写 HydroDesk 页面”，而是把命令构造和执行面改成只走 `hydromind` façade 与 bridge 语义。

这一步建议按如下顺序推进：

1. 把 `hydromind-studio/config/hydrodesk_commands.js` 中高频主链命令逐步替换为 `hydromind ...` 调用；  
2. 让 gateway / session hook 面向统一 session API，而不是 `agent_loop_gateway.py` 的 legacy 语义；  
3. 页面读取 contract、run state、artifact index，而不是脚本路径与旁路 JSON；  
4. 保留 legacy adapter/shim 作为过渡，但不让产品面继续感知它。

也就是说，P1 的目标不是“删掉 legacy”，而是**把 legacy 收缩到 provider/shim 层，退出产品前台与宿主接口层。**

### 6.3 P2：验证平台通用性，而非样例成功率

当前 six-case 已经完成了“样例能力证明”的大部分任务，P2 应切换到“平台抽象验证”。这意味着：

- 建立非六案例的新 case onboarding 流程；
- 用新 case 证明 `CaseManifest -> WorkflowRun -> ReviewBundle -> ReleaseManifest -> FinalReport` 的链条是通用的；
- 验证 HydroDesk、CLI、外部宿主是否能消费同一 contract 与 artifact truth；
- 验证 provider 失败语义、blocked/degraded/failed 在各宿主中的表现是否一致。

如果 P2 通过，才能证明 HydroMind 不是“把六案例包装成平台”，而是“借六案例打磨出来的通用平台”。

---

## 七、对后续规划表述方式的建议

我建议后续所有评审、roadmap、汇报材料，都逐步从“六案例自主建模平台”转成“**面向自主运行水网的通用端到端自主建模与运行智能体平台**”。

这不是文字游戏，而是治理口径的变化。因为一旦仍然以 six-case 为主语，团队就很容易回到：

- 继续补某个案例命令；
- 继续给某个 case 写特判；
- 继续把 readiness 当平台完成度；
- 继续默认 HydroDesk 只服务 Hydrology 主链。

而如果主语切换为平台，则所有设计判断都会自动改变：

- case registry 会优先于 case 脚本；
- workflow catalog 会优先于 workflow 壳文件；
- contracts truth layer 会优先于页面状态推断；
- runtime/session/trace 会优先于单次命令执行；
- host binding 会优先于某个前端壳的便捷实现。

这才是当前阶段最需要统一的口径。

---

## 八、我的最终更新结论

综合来看，我对当前项目状态的更新结论可以概括为以下四句话。

第一，**HydroMind 已经不是一个“准备重构”的项目，而是一个“平台骨架已形成，但运行面与宿主面尚未彻底脱离 legacy”的项目。**

第二，**当前最重要的技术主线，不是继续围绕 six-case 做增量修补，而是把 `hydromind` CLI、contracts、TeamRunState、trace/event、execution adapters 做成真正的平台真相层。**

第三，**HydroDesk 的产品定位已经正确，但工程实现仍然明显停留在“Hydrology 专用前台”的阶段；下一阶段必须从 command/gateway/session 三处切断对 legacy 的直连。**

第四，**真正的平台级验收标准，不是 six-case 全部看起来可跑，而是新 case 能在不依赖样例特判的情况下完成 onboarding、run、review、release，并且 CLI、Studio、外部宿主共享同一 contract truth。**

基于这个判断，如果您接下来要我继续往下做，我建议最有价值的两个方向分别是：

其一，我直接把这份更新版判断继续细化成一份 **P0/P1/P2 可执行开发清单**，精确到仓库、文件、动作和验收标准。  
其二，我针对您 handoff 中点名的关键入口，继续做一轮 **专项深评**，重点盯住：

- `hydromind/scripts/hydromind.py`
- `hydromind/tests/test_hydromind_cli_and_status.py`
- `hydromind-studio/config/hydrodesk_commands.js`
- `hydromind-studio/api/tauri_bridge.js`
- `hydromind-studio/hooks/useAgentLoopGatewaySession.js`
- `research/Hydrology/workflows/agent_loop_gateway.py`

如果继续做这两步，后面就可以很自然地进入真正的执行级规划，而不再停留在总体评审层面。

---

## 附：本次更新判断依赖的关键文件

| 类型 | 文件 |
|------|------|
| 用户补充材料 | `/home/ubuntu/upload/pasted_content.txt` |
| 总控规划 | `/Users/rainfields/.claude/plans/sleepy-jumping-patterson.md` |
| 平台设计 | `hydromind/docs/platform_bridge_design.md` |
| contracts 设计 | `hydromind/docs/contracts_detailed_design.md` |
| 平台 façade | `hydromind/scripts/hydromind.py` |
| CLI 行为规格 | `hydromind/tests/test_hydromind_cli_and_status.py` |
| bridge 配置 | `hydromind/configs/bridges/platform_bridge_manifest.v1.yaml` |
| adapter 配置 | `hydromind/configs/adapters/execution_adapter_catalog.v1.yaml` |
| contract 模型 | `hydromind-contracts/hydromind_contracts/models.py` |
| Studio 耦合证据 | `hydromind-studio/config/hydrodesk_commands.js` |

这份更新版结论的重点不在于重复已有规划，而在于把当前项目的**真实停止点、真实平台骨架和真实下一跳**重新校准出来。该校准完成后，后面的执行优先级将会清晰得多。
