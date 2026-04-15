# HydroMind 首批可执行 PR 清单

**作者：** Manus AI  
**日期：** 2026-04-15

---

## 一、文档目的

这份文档是在既有评审、分层实施方案和 backlog 清单基础上，进一步向前压缩得到的 **首批可执行 PR 计划**。它的目标不是覆盖全部工作，而是选择最关键、最能形成平台拐点的那一批改动，作为下一阶段正式代码落地的起手顺序。

这里继续遵循同一条主线：**先建立 runtime truth，再切断 Studio 与 legacy 的直接耦合，最后为 new-case 主链做准备。** 因此，首批 PR 不追求大而全，而追求“落一层、稳一层、提一层”。

---

## 二、首批 PR 的选择原则

| 原则 | 含义 | 实施要求 |
|------|------|----------|
| 真相优先 | 先立对象与运行态主语义 | 先改 contracts 与 hydromind façade |
| 小步闭环 | 每个 PR 都形成独立价值 | 不做跨仓超大混合提交 |
| 宿主去耦 | 页面只消费平台接口 | 不允许再新增 UI 直连 legacy 路径 |
| 可验收 | 每个 PR 都有明确测试与验收口 | 至少包含 contract 测试、CLI 行为或前端 fixture |
| 可继续云端开发 | 提交后即可作为下一轮协作基线 | 文档、代码、测试同步入 Git |

---

## 三、建议的首批 PR 总览

| PR 编号 | 主仓库 | PR 标题建议 | 对应层次 | 核心目标 |
|------|--------|-------------|----------|----------|
| PR-01 | `hydromind-contracts` | `feat(contracts): enrich team run state and runtime validation` | P0 | 把 TeamRunState、TraceEvent、ArtifactIndex 立成运行态真相层 |
| PR-02 | `hydromind` | `feat(hydromind): add session trace artifact facade skeleton` | P0 | 让 hydromind CLI 成为统一 session/trace/artifact 入口 |
| PR-03 | `hydromind-studio` | `refactor(studio): replace legacy gateway calls with platform session bridge` | P1 | 切断主前台对 legacy gateway 的直接依赖 |
| PR-04 | `hydromind` + `hydromind-model-core` | `feat(runtime): register execution adapters and provider contracts` | P1 | 把 provider/shim/legacy 能力收口到 adapter layer |
| PR-05 | `hydromind` | `feat(hydromind): add case bootstrap and onboarding commands` | P2 | 为新 case onboarding 建立原生命令入口 |

这 5 个 PR 并不是全部工作，但足以把平台从“规划明确”推进到“主链开始站住”。

---

# 四、PR-01：补强运行态 contract 与校验体系

## 4.1 目标

PR-01 是整个首批改动的起点。它要解决的问题是：当前平台虽然已经出现了 TeamRunState 等对象，但运行态语义仍然不够厚，无法稳定承载 session 生命周期、降级语义、event 序列与 artifact 索引。因此，第一步必须把 contract 真相层立稳。

## 4.2 涉及仓库与文件

| 仓库 | 关键文件 | 动作 |
|------|----------|------|
| `hydromind-contracts` | `hydromind_contracts/models.py` | 扩展 `TeamRunState`，引入 `TraceEvent`、`ArtifactIndex` 相关对象 |
| `hydromind-contracts` | `hydromind_contracts/program_validation.py` | 增加状态迁移、一致性、关联字段校验 |
| `hydromind-contracts` | `tests/test_program_validation.py` | 增加 planned/running/degraded/blocked/completed/failed 场景测试 |

## 4.3 改动边界

| 边界 | 应做 | 不应做 |
|------|------|--------|
| 运行态对象 | 明确定义生命周期字段、provider 关联、artifact 摘要 | 不把 UI 展示字段直接塞进 contracts |
| 校验逻辑 | 聚焦状态机与对象一致性 | 不在 contracts 层写宿主或 provider 细节逻辑 |
| 测试 | 用行为场景锁住 contract 语义 | 不只做字段存在性测试 |

## 4.4 交付标准

| 验收项 | 标准 |
|------|------|
| TeamRunState | 能表达一次真实运行中的状态推进、阻塞、降级与完成语义 |
| TraceEvent | 能表达 session 关键事件序列 |
| ArtifactIndex | 能表达运行产物索引及其引用方式 |
| Validation | 能拒绝非法 transition 和关键上下文缺失 |
| Tests | 测试通过且可作为后续 façade 回归基线 |

---

# 五、PR-02：建立 hydromind façade 的 session / trace / artifact 主入口

## 5.1 目标

PR-02 的目标是把 `hydromind` 从“已有命令集合”提升为“平台统一 façade”。换句话说，宿主、自动化、后续 orchestration 都必须开始围绕它来组织，而不是继续绕回 legacy scripts。

## 5.2 涉及仓库与文件

| 仓库 | 关键文件 | 动作 |
|------|----------|------|
| `hydromind` | `scripts/hydromind.py` | 整理命令树，明确 `session-*`、`trace-*`、`artifacts-*` 边界 |
| `hydromind` | runtime/session 相关模块 | 建立统一 session layout、status/events/artifacts 出口 |
| `hydromind` | tests 目录 | 增加 CLI façade 行为测试 |

## 5.3 关键子任务

| 子任务 | 说明 |
|------|------|
| 命令树收口 | 增加 `session-status`、`session-events`、`session-artifacts` |
| 落盘规范统一 | 统一 session 目录结构与 JSON/NDJSON 输出 |
| façade 测试 | 用行为测试锁住输出面，供 Studio 与自动化消费 |

## 5.4 交付标准

| 验收项 | 标准 |
|------|------|
| CLI 一致性 | 不进入 legacy 仓库也能查询 session 主状态、事件与产物 |
| 产物稳定性 | 每次运行都有稳定 layout，便于 UI 与 E2E 消费 |
| 测试基线 | façade 输出可作为宿主对接与自动化断言的公共基准 |

---

# 六、PR-03：重构 Studio bridge，切断对 legacy gateway 的主依赖

## 6.1 目标

PR-03 是 P1 阶段的真正开始。它不要求一次性改完所有页面，但要求先切断最关键的一条依赖链：Studio 不再以 `agent_loop_gateway` 作为主调用语义，而改为消费平台 session/runtime 语义。

## 6.2 涉及仓库与文件

| 仓库 | 关键文件 | 动作 |
|------|----------|------|
| `hydromind-studio` | `api/tauri_bridge.js` | 用 `sessionStart`、`sessionStatus`、`sessionArtifacts` 等平台语义替换 legacy gateway 语义 |
| `hydromind-studio` | `hooks/useAgentLoopGatewaySession.js` | 重构为 `usePlatformSession` 一类 host-agnostic hook |
| `hydromind-studio` | `pages/AgentWorkspace.jsx` | 移除 legacy 路径、shell、脚本位置的直接感知 |
| `hydromind-studio` | tests / fixtures | 增加 bridge 与 hook 的前端 fixture 测试 |

## 6.3 改动边界

| 边界 | 应做 | 不应做 |
|------|------|--------|
| Bridge 层 | 改为消费平台 façade | 不再向前台暴露 `agent_loop_gateway_*` 命名 |
| Hook 层 | 统一 session/status/events/artifacts 语义 | 不再把 legacy 命令结果直接塞给页面 |
| 页面层 | 页面只负责展示与交互 | 不再自行推导研究目录路径与脚本命令 |

## 6.4 交付标准

| 验收项 | 标准 |
|------|------|
| 主调用路径 | 页面主动作全部通过平台 bridge 到 runtime |
| 页面瘦身 | AgentWorkspace 不再承担 legacy 路径推导职责 |
| 可测试性 | 页面状态、事件与产物区域可被稳定 fixture 验证 |

---

# 七、PR-04：建立 adapter layer，收口 provider 与 shim

## 7.1 目标

PR-04 是跨仓配合 PR，目标是把 platform bridge、execution adapter catalog 和 model-core provider 调用统一起来。只有这一步做好，legacy 才能被放到合法位置，Studio 才不会再次绕回脚本路径。

## 7.2 涉及仓库与文件

| 仓库 | 关键文件 | 动作 |
|------|----------|------|
| `hydromind` | `configs/bridges/platform_bridge_manifest.v1.yaml` | 明确 host → runtime → provider 边界 |
| `hydromind` | `configs/adapters/execution_adapter_catalog.v1.yaml` | 统一登记 legacy provider、shim provider、新 provider |
| `hydromind-model-core` | provider / workflow 执行入口 | 统一 provider 调用签名与返回对象 |
| `research`（必要时） | legacy workflow 参考位置 | 仅作为 shim 映射参考，不再暴露产品级 API |

## 7.3 交付标准

| 验收项 | 标准 |
|------|------|
| Adapter 注册 | provider 与 shim 均通过 catalog 暴露 |
| Runtime 边界 | 宿主不再关心底层 workflow 或脚本路径 |
| Provider 一致性 | model-core 能按统一输入输出签名被平台调用 |

---

# 八、PR-05：建立新 case 的 onboarding 命令入口

## 8.1 目标

PR-05 是 P2 的起始 PR。它不要求一开始就跑通全部新 case 主链，但要先建立“新 case 可以原生进入平台”的入口。如果没有这一步，HydroMind 仍然会被 six-case 语义牵着走。

## 8.2 涉及仓库与文件

| 仓库 | 关键文件 | 动作 |
|------|----------|------|
| `hydromind` | `scripts/hydromind.py` | 增加 `case-init`、`case-validate`、`case-bootstrap` |
| `hydromind-contracts` | case manifest 相关 schema / model | 明确 onboarding 最小输入约束 |
| `hydromind-model-core` | 数据准备 provider 入口 | 为新 case 资料准备和校核建立标准接线 |

## 8.3 交付标准

| 验收项 | 标准 |
|------|------|
| 新 case 初始化 | 不复制 six-case 目录也能新建 case |
| case 校验 | 最小资料与配置可被平台验证 |
| bootstrap 能力 | 平台能生成运行所需基础上下文 |

---

# 九、建议的实施顺序

## 9.1 推荐顺序

| 顺序 | PR | 原因 |
|------|----|------|
| 1 | PR-01 | 不先立合同，后续 runtime 与 UI 都无统一语义 |
| 2 | PR-02 | 先把 hydromind façade 立稳，给宿主和测试稳定入口 |
| 3 | PR-03 | 再切 Studio 主调用路径，避免继续走 legacy 旁路 |
| 4 | PR-04 | 收 provider / shim / adapter 的边界 |
| 5 | PR-05 | 在平台骨架稳定后再引入新 case onboarding |

## 9.2 不建议的顺序

| 做法 | 问题 |
|------|------|
| 先改大量页面细节 | 页面会继续补 legacy 壳，而不是转向平台语义 |
| 先做新 case demo | 若 runtime 与 adapter 尚未稳定，新 case 只会把历史债务带进来 |
| 一次性跨仓大提交 | 难 review、难回滚，也不利于云端协作 |

---

# 十、每个 PR 的测试要求

为了让后续云端开发真正高效，首批 PR 必须自带测试与验收口，而不是只交代码。

| PR | 最低测试要求 | 推荐附加验证 |
|----|--------------|--------------|
| PR-01 | contract 单测与状态迁移测试 | 非法 state fixture 验证 |
| PR-02 | CLI 行为测试 | session layout 快照测试 |
| PR-03 | bridge / hook fixture 测试 | AgentWorkspace 关键 DOM 状态断言 |
| PR-04 | provider adapter 集成测试 | manifest / catalog 一致性验证 |
| PR-05 | case-init / case-validate 行为测试 | onboarding 最小资料样例验证 |

---

# 十一、建议的 Git 提交粒度

既然接下来要继续云端开发，那么提交粒度必须尽量清晰。建议如下。

| PR | 建议提交说明格式 |
|----|------------------|
| PR-01 | `feat(contracts): enrich runtime contracts and validation` |
| PR-02 | `feat(hydromind): add session trace artifact facade skeleton` |
| PR-03 | `refactor(studio): migrate legacy gateway calls to platform session bridge` |
| PR-04 | `feat(runtime): register adapters and normalize provider contracts` |
| PR-05 | `feat(hydromind): add case bootstrap and onboarding commands` |

每个 PR 最好都同时附带对应文档更新，避免代码与规划脱节。

---

# 十二、结论与下一步建议

这份首批 PR 清单的核心意思可以压缩为一句话：

> **先把 contract 和 façade 立住，再切前台耦合，再接 provider，再开 new-case。**

如果继续往前推进，我建议下一步不要再停留在规划层，而是直接开始落 **PR-01 与 PR-02**。这两步一旦完成，平台的运行态真相层和 façade 就会第一次真正站住，后续无论是 Studio 去耦、浏览器自动化，还是新 case onboarding，都会进入可控阶段。

与此同时，按照您提出的要求，后续每完成一轮文档或代码落地，都应**立即提交到 Git**，让云端开发始终围绕最新基线推进，而不是依赖本地临时状态。
