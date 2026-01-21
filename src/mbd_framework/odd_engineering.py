# -*- coding: utf-8 -*-
"""
ODD Engineering Framework - ODD工程表达框架
Enhanced Operational Design Domain Framework for Water Network Systems

基于六部分工程表达体系:
1. ODD适用对象与系统边界声明
2. ODD条件维度体系（五类维度）
3. 条件分级原则（有限分级）
4. 条件组合与运行策略等级映射
5. 越界判定规则与强制退化机制
6. 验证、仿真与在环测试的证据索引
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Tuple, Set, Union
from datetime import datetime
import json


# ============================================================================
# 第一部分: ODD适用对象与系统边界声明
# ============================================================================

class SystemType(Enum):
    """水网系统类型"""
    IRRIGATION_NETWORK = "灌区水网"
    WATER_TRANSFER = "调水工程"
    URBAN_WATER_SUPPLY = "城市供水"
    FLOOD_CONTROL = "防洪调度"
    RESERVOIR_REGULATION = "水库调度"
    MULTI_ENERGY = "多能互补"
    HYBRID = "综合系统"


class CoverageScope(Enum):
    """覆盖范围"""
    FULL_SYSTEM = "全系统"
    SUBSYSTEM = "子系统"
    COMPONENT = "单元设备"
    SEGMENT = "工程段"


@dataclass
class ExcludedScenario:
    """不适用场景声明"""
    scenario_id: str
    name: str
    description: str
    reason: str  # 排除原因
    alternative_handling: str  # 替代处理方式


@dataclass
class SystemNode:
    """系统节点"""
    node_id: str
    name: str
    node_type: str  # 水库、泵站、闸门、管道节点等
    location: str = ""
    is_covered: bool = True  # 是否在ODD覆盖范围内
    exclusion_reason: str = ""  # 若不覆盖，说明原因


@dataclass
class ODDSystemScope:
    """
    ODD适用对象与系统边界声明

    核心目的：避免"默认全系统自主"的模糊理解
    """
    scope_id: str
    name: str
    description: str

    # 系统范围
    system_type: SystemType
    coverage_scope: CoverageScope

    # 覆盖的节点与工程
    covered_nodes: List[SystemNode] = field(default_factory=list)
    covered_segments: List[str] = field(default_factory=list)  # 覆盖的工程段

    # 明确不适用的场景
    excluded_scenarios: List[ExcludedScenario] = field(default_factory=list)

    # 边界声明
    upstream_boundary: str = ""  # 上游边界
    downstream_boundary: str = ""  # 下游边界
    lateral_boundaries: List[str] = field(default_factory=list)  # 侧向边界

    # 接口声明
    external_interfaces: Dict[str, str] = field(default_factory=dict)  # 外部接口

    # 版本与责任
    version: str = "1.0"
    effective_date: datetime = field(default_factory=datetime.now)
    responsible_entity: str = ""  # 责任主体
    review_authority: str = ""  # 审查机构

    def add_node(self, node: SystemNode):
        """添加系统节点"""
        self.covered_nodes.append(node)

    def add_excluded_scenario(self, scenario: ExcludedScenario):
        """添加排除场景"""
        self.excluded_scenarios.append(scenario)

    def is_node_covered(self, node_id: str) -> Tuple[bool, str]:
        """检查节点是否在覆盖范围内"""
        for node in self.covered_nodes:
            if node.node_id == node_id:
                return node.is_covered, node.exclusion_reason
        return False, "节点未在系统范围内定义"

    def get_scope_summary(self) -> Dict[str, Any]:
        """获取范围摘要"""
        return {
            'scope_id': self.scope_id,
            'system_type': self.system_type.value,
            'coverage_scope': self.coverage_scope.value,
            'total_nodes': len(self.covered_nodes),
            'covered_nodes': sum(1 for n in self.covered_nodes if n.is_covered),
            'excluded_scenarios': len(self.excluded_scenarios),
            'version': self.version
        }


# ============================================================================
# 第二部分: ODD条件维度体系（五类维度）
# ============================================================================

class ConditionDimension(Enum):
    """
    ODD条件维度 - 五类维度

    该分类是工程责任完整性的最低要求
    """
    # 1. 水文与需水条件维度
    HYDROLOGY_DEMAND = "水文与需水条件"

    # 2. 工程与水力状态维度
    ENGINEERING_HYDRAULIC = "工程与水力状态"

    # 3. 设备与执行能力维度
    EQUIPMENT_EXECUTION = "设备与执行能力"

    # 4. 数据、感知与通信维度
    DATA_SENSING_COMMUNICATION = "数据感知与通信"

    # 5. 组织与人工接管能力维度
    ORGANIZATION_HUMAN = "组织与人工接管"


@dataclass
class DimensionCondition:
    """维度条件定义"""
    condition_id: str
    name: str
    description: str
    dimension: ConditionDimension

    # 参数定义
    parameter_name: str
    unit: str = ""

    # 数据来源
    data_source: str = ""  # 测量设备、模型预报等
    update_frequency: str = ""  # 更新频率
    reliability: float = 0.95  # 数据可靠度

    # 验证方法
    verification_method: str = ""

    def __post_init__(self):
        """后初始化处理"""
        if not self.condition_id:
            raise ValueError("condition_id不能为空")


# ============================================================================
# 第三部分: 条件分级原则（有限分级而非连续区间）
# ============================================================================

class ConditionLevel(Enum):
    """
    条件分级 - 有限等级

    采用有限分级的原因:
    - 连续区间难以审查
    - 连续区间难以触发明确越界判定
    - 工程责任不清晰
    """
    NORMAL = "正常"
    RESTRICTED = "受限"
    PROHIBITED = "不允许"


class ConditionGrade(Enum):
    """条件等级（三级制）"""
    GRADE_1 = "一级"  # 最优
    GRADE_2 = "二级"  # 可接受
    GRADE_3 = "三级"  # 临界


@dataclass
class GradedCondition:
    """
    分级条件 - 核心工程表达

    不采用连续区间，而采用有限等级
    """
    condition_id: str
    name: str
    description: str
    dimension: ConditionDimension
    parameter_name: str
    unit: str = ""

    # 等级阈值定义（边界值）
    grade_1_threshold: Optional[float] = None  # 一级/二级边界
    grade_2_threshold: Optional[float] = None  # 二级/三级边界
    grade_3_threshold: Optional[float] = None  # 三级/禁止边界

    # 阈值方向: True表示越大越好, False表示越小越好
    higher_is_better: bool = True

    # 离散等级（用于非数值条件）
    discrete_grades: Dict[str, ConditionGrade] = field(default_factory=dict)

    # 当前状态
    current_value: Optional[Any] = None
    current_grade: ConditionGrade = ConditionGrade.GRADE_1
    current_level: ConditionLevel = ConditionLevel.NORMAL

    def evaluate(self, value: Any) -> Tuple[ConditionGrade, ConditionLevel]:
        """
        评估条件等级

        Returns:
            (等级, 允许级别)
        """
        self.current_value = value

        # 离散条件
        if self.discrete_grades:
            if value in self.discrete_grades:
                grade = self.discrete_grades[value]
                self.current_grade = grade
                if grade == ConditionGrade.GRADE_1:
                    self.current_level = ConditionLevel.NORMAL
                elif grade == ConditionGrade.GRADE_2:
                    self.current_level = ConditionLevel.RESTRICTED
                else:
                    self.current_level = ConditionLevel.PROHIBITED
                return self.current_grade, self.current_level
            else:
                self.current_grade = ConditionGrade.GRADE_3
                self.current_level = ConditionLevel.PROHIBITED
                return self.current_grade, self.current_level

        # 数值条件
        if not isinstance(value, (int, float)):
            return ConditionGrade.GRADE_3, ConditionLevel.PROHIBITED

        if self.higher_is_better:
            # 值越大越好
            if self.grade_1_threshold is not None and value >= self.grade_1_threshold:
                self.current_grade = ConditionGrade.GRADE_1
                self.current_level = ConditionLevel.NORMAL
            elif self.grade_2_threshold is not None and value >= self.grade_2_threshold:
                self.current_grade = ConditionGrade.GRADE_2
                self.current_level = ConditionLevel.RESTRICTED
            elif self.grade_3_threshold is not None and value >= self.grade_3_threshold:
                self.current_grade = ConditionGrade.GRADE_3
                self.current_level = ConditionLevel.RESTRICTED
            else:
                self.current_grade = ConditionGrade.GRADE_3
                self.current_level = ConditionLevel.PROHIBITED
        else:
            # 值越小越好
            if self.grade_1_threshold is not None and value <= self.grade_1_threshold:
                self.current_grade = ConditionGrade.GRADE_1
                self.current_level = ConditionLevel.NORMAL
            elif self.grade_2_threshold is not None and value <= self.grade_2_threshold:
                self.current_grade = ConditionGrade.GRADE_2
                self.current_level = ConditionLevel.RESTRICTED
            elif self.grade_3_threshold is not None and value <= self.grade_3_threshold:
                self.current_grade = ConditionGrade.GRADE_3
                self.current_level = ConditionLevel.RESTRICTED
            else:
                self.current_grade = ConditionGrade.GRADE_3
                self.current_level = ConditionLevel.PROHIBITED

        return self.current_grade, self.current_level


# ============================================================================
# 第四部分: 条件组合与运行策略等级映射
# ============================================================================

class StrategyLevel(Enum):
    """
    运行策略等级

    S0: 人工主导运行
    S1: 规则约束下的半自动运行
    S2: 模型驱动的受限自主运行
    S3: 完全自主运行（在声明条件内）
    """
    S0_HUMAN_DOMINANT = "S0-人工主导"
    S1_RULE_CONSTRAINED = "S1-规则约束半自动"
    S2_MODEL_DRIVEN_LIMITED = "S2-模型驱动受限自主"
    S3_FULL_AUTONOMOUS = "S3-完全自主"


@dataclass
class ConditionCombination:
    """条件组合"""
    combination_id: str
    name: str
    description: str

    # 各维度条件要求 (维度 -> 最低等级)
    dimension_requirements: Dict[ConditionDimension, ConditionGrade] = field(default_factory=dict)

    # 特定条件要求 (条件ID -> 最低等级)
    specific_requirements: Dict[str, ConditionGrade] = field(default_factory=dict)

    # 允许的策略等级
    allowed_strategy: StrategyLevel = StrategyLevel.S0_HUMAN_DOMINANT

    # 优先级（用于多组合匹配时）
    priority: int = 0


@dataclass
class StrategyMapping:
    """
    条件组合-策略等级映射表

    ODD的核心工程内容
    """
    mapping_id: str
    name: str
    description: str

    # 条件组合列表
    combinations: List[ConditionCombination] = field(default_factory=list)

    # 默认策略（无匹配时）
    default_strategy: StrategyLevel = StrategyLevel.S0_HUMAN_DOMINANT

    def add_combination(self, combination: ConditionCombination):
        """添加条件组合"""
        self.combinations.append(combination)
        # 按优先级排序
        self.combinations.sort(key=lambda x: x.priority, reverse=True)

    def evaluate(self, condition_grades: Dict[str, ConditionGrade],
                 dimension_grades: Dict[ConditionDimension, ConditionGrade]) -> StrategyLevel:
        """
        评估当前条件组合，返回允许的策略等级

        Args:
            condition_grades: 各条件的当前等级
            dimension_grades: 各维度的综合等级

        Returns:
            允许的最高策略等级
        """
        for combination in self.combinations:
            match = True

            # 检查维度要求
            for dim, required_grade in combination.dimension_requirements.items():
                if dim in dimension_grades:
                    actual_grade = dimension_grades[dim]
                    if actual_grade.value > required_grade.value:  # 等级数值越大越差
                        match = False
                        break
                else:
                    match = False
                    break

            if not match:
                continue

            # 检查特定条件要求
            for cond_id, required_grade in combination.specific_requirements.items():
                if cond_id in condition_grades:
                    actual_grade = condition_grades[cond_id]
                    if actual_grade.value > required_grade.value:
                        match = False
                        break
                else:
                    match = False
                    break

            if match:
                return combination.allowed_strategy

        return self.default_strategy

    def get_mapping_table(self) -> List[Dict[str, Any]]:
        """获取映射表（用于文档生成）"""
        table = []
        for comb in self.combinations:
            row = {
                'combination_id': comb.combination_id,
                'name': comb.name,
                'dimension_requirements': {
                    dim.value: grade.value
                    for dim, grade in comb.dimension_requirements.items()
                },
                'allowed_strategy': comb.allowed_strategy.value,
                'priority': comb.priority
            }
            table.append(row)
        return table


# ============================================================================
# 第五部分: 越界判定规则与强制退化机制
# ============================================================================

class ViolationTriggerType(Enum):
    """越界触发类型"""
    INSTANTANEOUS = "瞬时触发"  # 立即响应
    SUSTAINED = "持续触发"  # 持续一定时间后触发
    CUMULATIVE = "累积触发"  # 累积达到阈值后触发


class ForcedAction(Enum):
    """强制行为"""
    LIMIT_AMPLITUDE = "限幅"  # 限制输出幅度
    FREEZE_OUTPUT = "冻结"  # 冻结当前输出
    SWITCH_MODE = "切换"  # 切换运行模式
    HUMAN_TAKEOVER = "人工接管"  # 请求人工接管
    SAFE_STATE = "安全状态"  # 进入安全状态
    EMERGENCY_STOP = "紧急停止"  # 紧急停机


@dataclass
class ViolationIndicator:
    """越界判定指标"""
    indicator_id: str
    name: str
    description: str

    # 指标来源
    source_condition_id: str
    parameter_name: str

    # 阈值
    warning_threshold: Optional[float] = None
    violation_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None

    # 触发类型
    trigger_type: ViolationTriggerType = ViolationTriggerType.INSTANTANEOUS

    # 持续触发参数
    sustained_duration: float = 0.0  # 持续时间阈值(秒)

    # 累积触发参数
    cumulative_threshold: float = 0.0  # 累积阈值
    cumulative_window: float = 0.0  # 累积窗口(秒)


@dataclass
class DegradationRule:
    """强制退化规则"""
    rule_id: str
    name: str
    description: str

    # 触发条件
    trigger_indicators: List[str] = field(default_factory=list)  # 指标ID列表
    trigger_logic: str = "ANY"  # ANY(任一) / ALL(全部) / MAJORITY(多数)

    # 强制行为
    forced_action: ForcedAction = ForcedAction.LIMIT_AMPLITUDE

    # 行为参数
    action_parameters: Dict[str, Any] = field(default_factory=dict)

    # 目标策略等级
    target_strategy: StrategyLevel = StrategyLevel.S0_HUMAN_DOMINANT

    # 恢复条件
    recovery_indicators: List[str] = field(default_factory=list)
    recovery_delay: float = 0.0  # 恢复延迟(秒)


class ViolationJudgment:
    """
    越界判定与强制退化机制

    构成ODD的工程安全底线，是审查与监管的重点
    """

    def __init__(self, judgment_id: str, name: str):
        self.judgment_id = judgment_id
        self.name = name

        # 判定指标
        self.indicators: Dict[str, ViolationIndicator] = {}

        # 退化规则
        self.rules: Dict[str, DegradationRule] = {}

        # 运行状态
        self._indicator_states: Dict[str, Dict[str, Any]] = {}
        self._active_rules: Set[str] = set()
        self._current_strategy: StrategyLevel = StrategyLevel.S3_FULL_AUTONOMOUS

    def add_indicator(self, indicator: ViolationIndicator):
        """添加判定指标"""
        self.indicators[indicator.indicator_id] = indicator
        self._indicator_states[indicator.indicator_id] = {
            'value': None,
            'violation_start': None,
            'cumulative': 0.0,
            'is_violated': False
        }

    def add_rule(self, rule: DegradationRule):
        """添加退化规则"""
        self.rules[rule.rule_id] = rule

    def update(self, values: Dict[str, Any], dt: float) -> Dict[str, Any]:
        """
        更新越界判定

        Args:
            values: 当前参数值 {parameter_name: value}
            dt: 时间步长(秒)

        Returns:
            判定结果
        """
        result = {
            'timestamp': datetime.now().isoformat(),
            'violated_indicators': [],
            'triggered_rules': [],
            'forced_actions': [],
            'current_strategy': self._current_strategy.value
        }

        # 更新各指标状态
        for ind_id, indicator in self.indicators.items():
            state = self._indicator_states[ind_id]

            if indicator.parameter_name in values:
                value = values[indicator.parameter_name]
                state['value'] = value

                # 检查是否越界
                is_violated = self._check_indicator_violation(indicator, value, state, dt)

                if is_violated and not state['is_violated']:
                    state['is_violated'] = True
                    state['violation_start'] = datetime.now()
                    result['violated_indicators'].append({
                        'indicator_id': ind_id,
                        'value': value,
                        'threshold': indicator.violation_threshold
                    })
                elif not is_violated and state['is_violated']:
                    state['is_violated'] = False
                    state['violation_start'] = None

        # 检查退化规则
        for rule_id, rule in self.rules.items():
            triggered = self._check_rule_trigger(rule)

            if triggered and rule_id not in self._active_rules:
                self._active_rules.add(rule_id)
                result['triggered_rules'].append(rule_id)
                result['forced_actions'].append({
                    'rule_id': rule_id,
                    'action': rule.forced_action.value,
                    'parameters': rule.action_parameters,
                    'target_strategy': rule.target_strategy.value
                })

                # 更新当前策略等级（取最保守的）
                if rule.target_strategy.value < self._current_strategy.value:
                    self._current_strategy = rule.target_strategy

            elif not triggered and rule_id in self._active_rules:
                # 检查恢复条件
                if self._check_rule_recovery(rule):
                    self._active_rules.discard(rule_id)

        result['current_strategy'] = self._current_strategy.value
        return result

    def _check_indicator_violation(self, indicator: ViolationIndicator,
                                   value: float, state: Dict, dt: float) -> bool:
        """检查指标是否越界"""
        if indicator.violation_threshold is None:
            return False

        is_over_threshold = value > indicator.violation_threshold

        if indicator.trigger_type == ViolationTriggerType.INSTANTANEOUS:
            return is_over_threshold

        elif indicator.trigger_type == ViolationTriggerType.SUSTAINED:
            if is_over_threshold:
                if state['violation_start'] is not None:
                    duration = (datetime.now() - state['violation_start']).total_seconds()
                    return duration >= indicator.sustained_duration
            return False

        elif indicator.trigger_type == ViolationTriggerType.CUMULATIVE:
            if is_over_threshold:
                state['cumulative'] += dt
            else:
                state['cumulative'] = max(0, state['cumulative'] - dt * 0.5)  # 缓慢恢复
            return state['cumulative'] >= indicator.cumulative_threshold

        return False

    def _check_rule_trigger(self, rule: DegradationRule) -> bool:
        """检查规则是否触发"""
        violated_count = 0
        total_count = len(rule.trigger_indicators)

        for ind_id in rule.trigger_indicators:
            if ind_id in self._indicator_states:
                if self._indicator_states[ind_id]['is_violated']:
                    violated_count += 1

        if rule.trigger_logic == "ANY":
            return violated_count > 0
        elif rule.trigger_logic == "ALL":
            return violated_count == total_count
        elif rule.trigger_logic == "MAJORITY":
            return violated_count > total_count / 2

        return False

    def _check_rule_recovery(self, rule: DegradationRule) -> bool:
        """检查规则恢复条件"""
        for ind_id in rule.recovery_indicators:
            if ind_id in self._indicator_states:
                if self._indicator_states[ind_id]['is_violated']:
                    return False
        return True

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            'judgment_id': self.judgment_id,
            'current_strategy': self._current_strategy.value,
            'active_rules': list(self._active_rules),
            'indicator_states': {
                ind_id: {
                    'value': state['value'],
                    'is_violated': state['is_violated']
                }
                for ind_id, state in self._indicator_states.items()
            }
        }


# ============================================================================
# 第六部分: 验证、仿真与在环测试的证据索引
# ============================================================================

class EvidenceType(Enum):
    """证据类型"""
    MODEL_ANALYSIS = "模型分析"
    SIMULATION = "仿真测试"
    SIL_TEST = "软件在环测试"
    HIL_TEST = "硬件在环测试"
    HITL_TEST = "人机在环测试"
    FIELD_TEST = "现场测试"
    OPERATIONAL_DATA = "运行数据"
    EXPERT_REVIEW = "专家评审"


class ScenarioCriticality(Enum):
    """场景关键性"""
    TYPICAL = "典型场景"
    BOUNDARY = "边界场景"
    EXTREME = "极端场景"
    FAILURE = "故障场景"


@dataclass
class TestEvidence:
    """测试证据"""
    evidence_id: str
    name: str
    description: str

    # 证据类型
    evidence_type: EvidenceType

    # 关联
    related_odd_statement: str  # 关联的ODD声明ID
    related_conditions: List[str] = field(default_factory=list)  # 关联的条件ID

    # 测试信息
    test_date: datetime = field(default_factory=datetime.now)
    test_environment: str = ""
    tester: str = ""

    # 场景信息
    scenario_description: str = ""
    scenario_criticality: ScenarioCriticality = ScenarioCriticality.TYPICAL

    # 结果
    result_summary: str = ""
    pass_fail: bool = True

    # 存储位置
    storage_path: str = ""  # 证据文件存储路径
    report_reference: str = ""  # 测试报告引用


@dataclass
class ModelAssumption:
    """模型假设"""
    assumption_id: str
    name: str
    description: str

    # 假设内容
    assumption_content: str
    validity_range: str = ""  # 有效范围

    # 验证状态
    is_verified: bool = False
    verification_method: str = ""
    verification_evidence: List[str] = field(default_factory=list)  # 证据ID列表


class EvidenceIndex:
    """
    验证证据索引

    每一项ODD声明都应当明确：
    - 使用了哪些模型与假设
    - 覆盖了哪些典型与极端运行场景
    - 对应的仿真或在环测试编号与存储位置
    """

    def __init__(self, index_id: str, name: str):
        self.index_id = index_id
        self.name = name

        # 证据库
        self.evidences: Dict[str, TestEvidence] = {}

        # 模型假设库
        self.assumptions: Dict[str, ModelAssumption] = {}

        # ODD声明-证据映射
        self.statement_evidence_map: Dict[str, List[str]] = {}

        # 场景覆盖矩阵
        self.scenario_coverage: Dict[str, Dict[ScenarioCriticality, List[str]]] = {}

    def add_evidence(self, evidence: TestEvidence):
        """添加测试证据"""
        self.evidences[evidence.evidence_id] = evidence

        # 更新声明-证据映射
        stmt_id = evidence.related_odd_statement
        if stmt_id not in self.statement_evidence_map:
            self.statement_evidence_map[stmt_id] = []
        self.statement_evidence_map[stmt_id].append(evidence.evidence_id)

        # 更新场景覆盖矩阵
        if stmt_id not in self.scenario_coverage:
            self.scenario_coverage[stmt_id] = {crit: [] for crit in ScenarioCriticality}
        self.scenario_coverage[stmt_id][evidence.scenario_criticality].append(evidence.evidence_id)

    def add_assumption(self, assumption: ModelAssumption):
        """添加模型假设"""
        self.assumptions[assumption.assumption_id] = assumption

    def get_evidence_for_statement(self, statement_id: str) -> List[TestEvidence]:
        """获取ODD声明的所有证据"""
        evidence_ids = self.statement_evidence_map.get(statement_id, [])
        return [self.evidences[eid] for eid in evidence_ids if eid in self.evidences]

    def get_coverage_report(self, statement_id: str) -> Dict[str, Any]:
        """获取场景覆盖报告"""
        if statement_id not in self.scenario_coverage:
            return {'statement_id': statement_id, 'coverage': {}, 'gaps': []}

        coverage = self.scenario_coverage[statement_id]
        gaps = []

        for crit in ScenarioCriticality:
            if not coverage.get(crit, []):
                gaps.append(crit.value)

        return {
            'statement_id': statement_id,
            'coverage': {
                crit.value: len(evidence_ids)
                for crit, evidence_ids in coverage.items()
            },
            'gaps': gaps,
            'is_complete': len(gaps) == 0
        }

    def generate_traceability_matrix(self) -> Dict[str, Any]:
        """生成追溯矩阵"""
        matrix = {
            'index_id': self.index_id,
            'timestamp': datetime.now().isoformat(),
            'statements': {}
        }

        for stmt_id, evidence_ids in self.statement_evidence_map.items():
            matrix['statements'][stmt_id] = {
                'evidence_count': len(evidence_ids),
                'evidences': [
                    {
                        'id': eid,
                        'type': self.evidences[eid].evidence_type.value,
                        'result': 'PASS' if self.evidences[eid].pass_fail else 'FAIL',
                        'storage': self.evidences[eid].storage_path
                    }
                    for eid in evidence_ids if eid in self.evidences
                ],
                'coverage': self.get_coverage_report(stmt_id)
            }

        return matrix


# ============================================================================
# 完整ODD工程表达类
# ============================================================================

class ODDEngineeringSpec:
    """
    完整的ODD工程表达

    整合六部分内容，形成可审查、验收和长期使用的ODD文档
    """

    def __init__(self, spec_id: str, name: str, description: str = ""):
        self.spec_id = spec_id
        self.name = name
        self.description = description
        self.version = "1.0"
        self.created_date = datetime.now()
        self.modified_date = datetime.now()

        # 六部分内容
        self.system_scope: Optional[ODDSystemScope] = None  # 第一部分
        self.conditions: Dict[str, GradedCondition] = {}  # 第二、三部分
        self.strategy_mapping: Optional[StrategyMapping] = None  # 第四部分
        self.violation_judgment: Optional[ViolationJudgment] = None  # 第五部分
        self.evidence_index: Optional[EvidenceIndex] = None  # 第六部分

        # 元数据
        self.author: str = ""
        self.reviewer: str = ""
        self.approval_date: Optional[datetime] = None
        self.next_review_date: Optional[datetime] = None

    def set_system_scope(self, scope: ODDSystemScope):
        """设置系统边界声明"""
        self.system_scope = scope
        self.modified_date = datetime.now()

    def add_condition(self, condition: GradedCondition):
        """添加分级条件"""
        self.conditions[condition.condition_id] = condition
        self.modified_date = datetime.now()

    def set_strategy_mapping(self, mapping: StrategyMapping):
        """设置策略映射"""
        self.strategy_mapping = mapping
        self.modified_date = datetime.now()

    def set_violation_judgment(self, judgment: ViolationJudgment):
        """设置越界判定机制"""
        self.violation_judgment = judgment
        self.modified_date = datetime.now()

    def set_evidence_index(self, index: EvidenceIndex):
        """设置证据索引"""
        self.evidence_index = index
        self.modified_date = datetime.now()

    def evaluate_operating_point(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估运行点

        Returns:
            包含等级评估、策略等级、越界状态的完整评估结果
        """
        result = {
            'spec_id': self.spec_id,
            'timestamp': datetime.now().isoformat(),
            'condition_grades': {},
            'dimension_grades': {},
            'allowed_strategy': StrategyLevel.S0_HUMAN_DOMINANT.value,
            'violations': [],
            'in_odd': True
        }

        # 评估各条件等级
        dimension_grades = {dim: ConditionGrade.GRADE_1 for dim in ConditionDimension}

        for cond_id, condition in self.conditions.items():
            if condition.parameter_name in values:
                grade, level = condition.evaluate(values[condition.parameter_name])
                result['condition_grades'][cond_id] = {
                    'grade': grade.value,
                    'level': level.value,
                    'value': values[condition.parameter_name]
                }

                # 更新维度等级（取最差的）
                if grade.value > dimension_grades[condition.dimension].value:
                    dimension_grades[condition.dimension] = grade

                # 检查是否禁止
                if level == ConditionLevel.PROHIBITED:
                    result['in_odd'] = False

        result['dimension_grades'] = {
            dim.value: grade.value for dim, grade in dimension_grades.items()
        }

        # 评估策略等级
        if self.strategy_mapping:
            condition_grades = {
                cond_id: cond.current_grade
                for cond_id, cond in self.conditions.items()
            }
            strategy = self.strategy_mapping.evaluate(condition_grades, dimension_grades)
            result['allowed_strategy'] = strategy.value

        return result

    def update_with_time(self, values: Dict[str, Any], dt: float) -> Dict[str, Any]:
        """
        带时间的更新（用于越界判定）
        """
        result = self.evaluate_operating_point(values)

        if self.violation_judgment:
            violation_result = self.violation_judgment.update(values, dt)
            result['violations'] = violation_result.get('violated_indicators', [])
            result['forced_actions'] = violation_result.get('forced_actions', [])
            result['current_strategy'] = violation_result.get('current_strategy', result['allowed_strategy'])

        return result

    def validate_completeness(self) -> Dict[str, Any]:
        """验证ODD工程表达完整性"""
        result = {
            'spec_id': self.spec_id,
            'is_complete': True,
            'missing_parts': [],
            'warnings': []
        }

        # 检查六部分是否完整
        if not self.system_scope:
            result['is_complete'] = False
            result['missing_parts'].append("第一部分: ODD适用对象与系统边界声明")

        if not self.conditions:
            result['is_complete'] = False
            result['missing_parts'].append("第二/三部分: ODD条件维度体系与分级")
        else:
            # 检查五类维度覆盖
            covered_dims = set(c.dimension for c in self.conditions.values())
            missing_dims = set(ConditionDimension) - covered_dims
            if missing_dims:
                result['warnings'].append(
                    f"条件维度未完全覆盖: {[d.value for d in missing_dims]}"
                )

        if not self.strategy_mapping:
            result['is_complete'] = False
            result['missing_parts'].append("第四部分: 条件组合与运行策略等级映射")

        if not self.violation_judgment:
            result['is_complete'] = False
            result['missing_parts'].append("第五部分: 越界判定规则与强制退化机制")

        if not self.evidence_index:
            result['is_complete'] = False
            result['missing_parts'].append("第六部分: 验证证据索引")

        return result

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            'spec_id': self.spec_id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'created_date': self.created_date.isoformat(),
            'modified_date': self.modified_date.isoformat(),
            'system_scope': self.system_scope.get_scope_summary() if self.system_scope else None,
            'conditions_count': len(self.conditions),
            'strategy_mapping': self.strategy_mapping.get_mapping_table() if self.strategy_mapping else None,
            'completeness': self.validate_completeness()
        }

    def generate_document(self) -> str:
        """生成ODD工程文档"""
        doc = []
        doc.append(f"# ODD工程表达文档: {self.name}")
        doc.append(f"\n版本: {self.version}")
        doc.append(f"创建日期: {self.created_date.strftime('%Y-%m-%d')}")
        doc.append(f"最后修改: {self.modified_date.strftime('%Y-%m-%d')}")

        # 第一部分
        doc.append("\n## 第一部分: ODD适用对象与系统边界声明\n")
        if self.system_scope:
            doc.append(f"- 系统类型: {self.system_scope.system_type.value}")
            doc.append(f"- 覆盖范围: {self.system_scope.coverage_scope.value}")
            doc.append(f"- 覆盖节点数: {len(self.system_scope.covered_nodes)}")
            doc.append(f"- 排除场景数: {len(self.system_scope.excluded_scenarios)}")
        else:
            doc.append("*未定义*")

        # 第二/三部分
        doc.append("\n## 第二/三部分: ODD条件维度体系与分级\n")
        for dim in ConditionDimension:
            dim_conditions = [c for c in self.conditions.values() if c.dimension == dim]
            doc.append(f"\n### {dim.value} ({len(dim_conditions)}项)")
            for cond in dim_conditions:
                doc.append(f"- {cond.name}: {cond.description}")

        # 第四部分
        doc.append("\n## 第四部分: 条件组合与运行策略等级映射\n")
        if self.strategy_mapping:
            doc.append("| 组合 | 维度要求 | 策略等级 |")
            doc.append("|------|---------|---------|")
            for comb in self.strategy_mapping.combinations:
                dims = ", ".join([f"{d.value}={g.value}" for d, g in comb.dimension_requirements.items()])
                doc.append(f"| {comb.name} | {dims} | {comb.allowed_strategy.value} |")
        else:
            doc.append("*未定义*")

        # 第五部分
        doc.append("\n## 第五部分: 越界判定规则与强制退化机制\n")
        if self.violation_judgment:
            doc.append(f"- 判定指标数: {len(self.violation_judgment.indicators)}")
            doc.append(f"- 退化规则数: {len(self.violation_judgment.rules)}")
        else:
            doc.append("*未定义*")

        # 第六部分
        doc.append("\n## 第六部分: 验证证据索引\n")
        if self.evidence_index:
            doc.append(f"- 证据总数: {len(self.evidence_index.evidences)}")
            doc.append(f"- 模型假设数: {len(self.evidence_index.assumptions)}")
        else:
            doc.append("*未定义*")

        return "\n".join(doc)


# ============================================================================
# 工厂函数 - 创建各类水网的ODD工程表达
# ============================================================================

def create_irrigation_odd_engineering() -> ODDEngineeringSpec:
    """创建灌区水网ODD工程表达"""
    spec = ODDEngineeringSpec(
        spec_id="ODD_ENG_IRRIGATION_001",
        name="灌区水网ODD工程表达",
        description="灌区水网智能调配系统的运行设计域工程表达"
    )

    # 第一部分: 系统边界声明
    scope = ODDSystemScope(
        scope_id="SCOPE_IRR_001",
        name="灌区水网系统边界",
        description="大型灌区水资源智能调配系统",
        system_type=SystemType.IRRIGATION_NETWORK,
        coverage_scope=CoverageScope.FULL_SYSTEM,
        upstream_boundary="水源枢纽取水口",
        downstream_boundary="各支渠末端",
        responsible_entity="灌区管理局"
    )

    # 添加典型节点
    scope.add_node(SystemNode("N001", "总干渠分水闸", "分水闸", is_covered=True))
    scope.add_node(SystemNode("N002", "一干分水口", "分水口", is_covered=True))
    scope.add_node(SystemNode("N003", "二干分水口", "分水口", is_covered=True))

    # 添加排除场景
    scope.add_excluded_scenario(ExcludedScenario(
        "EXC_001", "极端干旱应急", "年来水量<30%保证率的极端干旱",
        "需人工决策水权分配", "切换至S0人工主导模式"
    ))
    scope.add_excluded_scenario(ExcludedScenario(
        "EXC_002", "渠道重大事故", "渠道溃堤或重大淤堵",
        "超出自动控制能力", "立即停止自动调配，人工处置"
    ))

    spec.set_system_scope(scope)

    # 第二/三部分: 条件分级
    # 水文与需水条件
    spec.add_condition(GradedCondition(
        condition_id="COND_IRR_INFLOW",
        name="来水保证率",
        description="当年来水量占多年平均的比例",
        dimension=ConditionDimension.HYDROLOGY_DEMAND,
        parameter_name="inflow_ratio",
        unit="%",
        grade_1_threshold=80.0,  # >=80% 一级
        grade_2_threshold=50.0,  # >=50% 二级
        grade_3_threshold=30.0,  # >=30% 三级，<30%禁止
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_IRR_FAIRNESS",
        name="公平性指数",
        description="各用水户累积配水比例的基尼系数",
        dimension=ConditionDimension.HYDROLOGY_DEMAND,
        parameter_name="fairness_index",
        unit="",
        grade_1_threshold=0.1,   # <=0.1 一级
        grade_2_threshold=0.2,   # <=0.2 二级
        grade_3_threshold=0.3,   # <=0.3 三级
        higher_is_better=False
    ))

    # 工程与水力状态
    spec.add_condition(GradedCondition(
        condition_id="COND_IRR_CHANNEL",
        name="渠道过流能力",
        description="实际过流量/设计过流量",
        dimension=ConditionDimension.ENGINEERING_HYDRAULIC,
        parameter_name="channel_capacity_ratio",
        unit="%",
        grade_1_threshold=80.0,
        grade_2_threshold=60.0,
        grade_3_threshold=40.0,
        higher_is_better=True
    ))

    # 设备与执行能力
    spec.add_condition(GradedCondition(
        condition_id="COND_IRR_GATE",
        name="闸门可用率",
        description="可正常操作闸门占比",
        dimension=ConditionDimension.EQUIPMENT_EXECUTION,
        parameter_name="gate_availability",
        unit="%",
        grade_1_threshold=95.0,
        grade_2_threshold=80.0,
        grade_3_threshold=60.0,
        higher_is_better=True
    ))

    # 数据感知与通信
    spec.add_condition(GradedCondition(
        condition_id="COND_IRR_DATA",
        name="数据完整率",
        description="关键测点数据可用率",
        dimension=ConditionDimension.DATA_SENSING_COMMUNICATION,
        parameter_name="data_completeness",
        unit="%",
        grade_1_threshold=95.0,
        grade_2_threshold=80.0,
        grade_3_threshold=60.0,
        higher_is_better=True
    ))

    # 组织与人工接管
    spec.add_condition(GradedCondition(
        condition_id="COND_IRR_OPERATOR",
        name="值班人员状态",
        description="值班室人员配置状态",
        dimension=ConditionDimension.ORGANIZATION_HUMAN,
        parameter_name="operator_status",
        discrete_grades={
            "FULL_STAFF": ConditionGrade.GRADE_1,
            "REDUCED": ConditionGrade.GRADE_2,
            "MINIMAL": ConditionGrade.GRADE_3,
            "NONE": ConditionGrade.GRADE_3
        }
    ))

    # 第四部分: 策略映射
    mapping = StrategyMapping(
        mapping_id="MAP_IRR_001",
        name="灌区水网策略映射",
        description="灌区水网条件组合与策略等级映射"
    )

    # S3: 完全自主 - 所有条件一级
    mapping.add_combination(ConditionCombination(
        combination_id="COMB_IRR_S3",
        name="完全自主运行条件",
        description="所有维度达到一级时允许完全自主",
        dimension_requirements={
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_1,
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_1,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_1,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_1,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_1
        },
        allowed_strategy=StrategyLevel.S3_FULL_AUTONOMOUS,
        priority=100
    ))

    # S2: 受限自主 - 允许部分二级
    mapping.add_combination(ConditionCombination(
        combination_id="COMB_IRR_S2",
        name="受限自主运行条件",
        description="关键维度一级，其他可二级",
        dimension_requirements={
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_2,
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_1,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_2,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_1,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S2_MODEL_DRIVEN_LIMITED,
        priority=80
    ))

    # S1: 半自动 - 允许更多二级
    mapping.add_combination(ConditionCombination(
        combination_id="COMB_IRR_S1",
        name="半自动运行条件",
        description="有三级条件时降为半自动",
        dimension_requirements={
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_3,
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_2,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_3,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_2,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S1_RULE_CONSTRAINED,
        priority=60
    ))

    spec.set_strategy_mapping(mapping)

    # 第五部分: 越界判定
    judgment = ViolationJudgment("JUDGE_IRR_001", "灌区水网越界判定")

    judgment.add_indicator(ViolationIndicator(
        indicator_id="IND_IRR_FAIRNESS",
        name="公平性越界指标",
        description="公平性指数超限",
        source_condition_id="COND_IRR_FAIRNESS",
        parameter_name="fairness_index",
        warning_threshold=0.25,
        violation_threshold=0.35,
        trigger_type=ViolationTriggerType.SUSTAINED,
        sustained_duration=3600.0  # 持续1小时
    ))

    judgment.add_indicator(ViolationIndicator(
        indicator_id="IND_IRR_DATA",
        name="数据缺失指标",
        description="数据完整率过低",
        source_condition_id="COND_IRR_DATA",
        parameter_name="data_completeness",
        violation_threshold=50.0,
        trigger_type=ViolationTriggerType.INSTANTANEOUS
    ))

    judgment.add_rule(DegradationRule(
        rule_id="RULE_IRR_FAIRNESS",
        name="公平性退化规则",
        description="公平性持续超限时强制人工介入",
        trigger_indicators=["IND_IRR_FAIRNESS"],
        forced_action=ForcedAction.HUMAN_TAKEOVER,
        target_strategy=StrategyLevel.S0_HUMAN_DOMINANT
    ))

    judgment.add_rule(DegradationRule(
        rule_id="RULE_IRR_DATA",
        name="数据缺失退化规则",
        description="数据缺失时冻结输出",
        trigger_indicators=["IND_IRR_DATA"],
        forced_action=ForcedAction.FREEZE_OUTPUT,
        target_strategy=StrategyLevel.S1_RULE_CONSTRAINED
    ))

    spec.set_violation_judgment(judgment)

    # 第六部分: 证据索引
    evidence_index = EvidenceIndex("EVID_IRR_001", "灌区水网证据索引")

    evidence_index.add_evidence(TestEvidence(
        evidence_id="EV_IRR_SIL_001",
        name="公平性算法SIL测试",
        description="公平性调配算法软件在环测试",
        evidence_type=EvidenceType.SIL_TEST,
        related_odd_statement="COND_IRR_FAIRNESS",
        scenario_criticality=ScenarioCriticality.TYPICAL,
        result_summary="公平性指数控制在0.15以内",
        pass_fail=True,
        storage_path="/tests/sil/irrigation/fairness_001.json"
    ))

    evidence_index.add_evidence(TestEvidence(
        evidence_id="EV_IRR_HIL_001",
        name="闸门联动HIL测试",
        description="多闸门协调控制硬件在环测试",
        evidence_type=EvidenceType.HIL_TEST,
        related_odd_statement="COND_IRR_GATE",
        scenario_criticality=ScenarioCriticality.BOUNDARY,
        result_summary="响应时间<2s，位置误差<1%",
        pass_fail=True,
        storage_path="/tests/hil/irrigation/gate_coordination_001.json"
    ))

    evidence_index.add_assumption(ModelAssumption(
        assumption_id="ASM_IRR_001",
        name="渠道糙率假设",
        description="明渠流计算的糙率系数假设",
        assumption_content="采用曼宁公式，n=0.025",
        validity_range="混凝土衬砌渠道",
        is_verified=True,
        verification_method="现场实测率定"
    ))

    spec.set_evidence_index(evidence_index)

    return spec


def create_water_transfer_odd_engineering() -> ODDEngineeringSpec:
    """创建调水工程ODD工程表达"""
    spec = ODDEngineeringSpec(
        spec_id="ODD_ENG_TRANSFER_001",
        name="调水工程ODD工程表达",
        description="跨流域调水工程智能调度系统的运行设计域工程表达"
    )

    # 第一部分: 系统边界声明
    scope = ODDSystemScope(
        scope_id="SCOPE_TRANS_001",
        name="调水工程系统边界",
        description="跨流域长距离调水工程",
        system_type=SystemType.WATER_TRANSFER,
        coverage_scope=CoverageScope.FULL_SYSTEM,
        upstream_boundary="水源地取水枢纽",
        downstream_boundary="末端受水区配水点",
        responsible_entity="调水工程管理局"
    )

    scope.add_excluded_scenario(ExcludedScenario(
        "EXC_TRANS_001", "管道重大事故",
        "管道爆裂或严重泄漏", "需现场处置",
        "立即关闭相关阀门，人工处置"
    ))

    spec.set_system_scope(scope)

    # 第二/三部分: 条件分级
    # 核心条件: 时滞裕度
    spec.add_condition(GradedCondition(
        condition_id="COND_TRANS_DELAY_MARGIN",
        name="时滞裕度",
        description="调度间隔/传输时滞，避免调度修正来不及生效",
        dimension=ConditionDimension.ENGINEERING_HYDRAULIC,
        parameter_name="delay_margin",
        unit="",
        grade_1_threshold=0.5,   # >=0.5 一级（充裕）
        grade_2_threshold=0.3,   # >=0.3 二级（可接受）
        grade_3_threshold=0.2,   # >=0.2 三级（临界）
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_TRANS_COORDINATION",
        name="多受水区协调度",
        description="各受水区需求满足率的均衡程度",
        dimension=ConditionDimension.HYDROLOGY_DEMAND,
        parameter_name="coordination_index",
        unit="",
        grade_1_threshold=0.9,
        grade_2_threshold=0.7,
        grade_3_threshold=0.5,
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_TRANS_PIPELINE",
        name="管道运行状态",
        description="管道压力/流量异常程度",
        dimension=ConditionDimension.EQUIPMENT_EXECUTION,
        parameter_name="pipeline_health",
        unit="%",
        grade_1_threshold=95.0,
        grade_2_threshold=80.0,
        grade_3_threshold=60.0,
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_TRANS_COMM",
        name="跨区段通信状态",
        description="各调度中心通信连通性",
        dimension=ConditionDimension.DATA_SENSING_COMMUNICATION,
        parameter_name="comm_status",
        discrete_grades={
            "ALL_CONNECTED": ConditionGrade.GRADE_1,
            "PARTIAL_BACKUP": ConditionGrade.GRADE_2,
            "DEGRADED": ConditionGrade.GRADE_3
        }
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_TRANS_OPERATOR",
        name="多中心协调能力",
        description="各调度中心协调响应能力",
        dimension=ConditionDimension.ORGANIZATION_HUMAN,
        parameter_name="coordination_capability",
        discrete_grades={
            "FULL_CAPABILITY": ConditionGrade.GRADE_1,
            "REDUCED": ConditionGrade.GRADE_2,
            "MINIMAL": ConditionGrade.GRADE_3
        }
    ))

    # 第四部分: 策略映射
    mapping = StrategyMapping(
        mapping_id="MAP_TRANS_001",
        name="调水工程策略映射",
        description="调水工程条件组合与策略等级映射"
    )

    mapping.add_combination(ConditionCombination(
        combination_id="COMB_TRANS_S3",
        name="完全自主运行条件",
        description="时滞裕度充裕且各条件良好",
        dimension_requirements={
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_1,
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_1,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_1,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_1,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S3_FULL_AUTONOMOUS,
        priority=100
    ))

    mapping.add_combination(ConditionCombination(
        combination_id="COMB_TRANS_S2",
        name="受限自主运行条件",
        description="时滞裕度可接受",
        dimension_requirements={
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_2,
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_2,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_2,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_1,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S2_MODEL_DRIVEN_LIMITED,
        priority=80
    ))

    mapping.add_combination(ConditionCombination(
        combination_id="COMB_TRANS_S1",
        name="半自动运行条件",
        description="时滞裕度临界",
        dimension_requirements={
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_3,
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_2,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_2,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_2,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S1_RULE_CONSTRAINED,
        priority=60
    ))

    spec.set_strategy_mapping(mapping)

    # 第五部分: 越界判定
    judgment = ViolationJudgment("JUDGE_TRANS_001", "调水工程越界判定")

    judgment.add_indicator(ViolationIndicator(
        indicator_id="IND_TRANS_DELAY",
        name="时滞裕度越界指标",
        description="时滞裕度过低",
        source_condition_id="COND_TRANS_DELAY_MARGIN",
        parameter_name="delay_margin",
        warning_threshold=0.25,
        violation_threshold=0.15,
        trigger_type=ViolationTriggerType.INSTANTANEOUS
    ))

    judgment.add_rule(DegradationRule(
        rule_id="RULE_TRANS_DELAY",
        name="时滞裕度退化规则",
        description="时滞裕度不足时限制调度幅度",
        trigger_indicators=["IND_TRANS_DELAY"],
        forced_action=ForcedAction.LIMIT_AMPLITUDE,
        action_parameters={'amplitude_limit': 0.5},
        target_strategy=StrategyLevel.S1_RULE_CONSTRAINED
    ))

    spec.set_violation_judgment(judgment)

    # 第六部分: 证据索引
    evidence_index = EvidenceIndex("EVID_TRANS_001", "调水工程证据索引")

    evidence_index.add_evidence(TestEvidence(
        evidence_id="EV_TRANS_SIL_001",
        name="时滞补偿算法SIL测试",
        description="长时滞系统补偿算法测试",
        evidence_type=EvidenceType.SIL_TEST,
        related_odd_statement="COND_TRANS_DELAY_MARGIN",
        scenario_criticality=ScenarioCriticality.TYPICAL,
        pass_fail=True,
        storage_path="/tests/sil/transfer/delay_compensation_001.json"
    ))

    spec.set_evidence_index(evidence_index)

    return spec


def create_urban_water_supply_odd_engineering() -> ODDEngineeringSpec:
    """创建城市供水ODD工程表达"""
    spec = ODDEngineeringSpec(
        spec_id="ODD_ENG_URBAN_001",
        name="城市供水ODD工程表达",
        description="城市供水管网智能调度系统的运行设计域工程表达"
    )

    # 第一部分: 系统边界声明
    scope = ODDSystemScope(
        scope_id="SCOPE_URBAN_001",
        name="城市供水系统边界",
        description="城市供水管网调度系统",
        system_type=SystemType.URBAN_WATER_SUPPLY,
        coverage_scope=CoverageScope.FULL_SYSTEM,
        upstream_boundary="水厂出水口",
        downstream_boundary="用户接口阀门",
        responsible_entity="供水公司"
    )

    scope.add_excluded_scenario(ExcludedScenario(
        "EXC_URBAN_001", "管网爆管事故",
        "主干管爆裂", "需现场抢修",
        "关闭相关阀门，人工调度绕行"
    ))

    spec.set_system_scope(scope)

    # 第二/三部分: 条件分级
    # 核心条件: 压力稳定性
    spec.add_condition(GradedCondition(
        condition_id="COND_URBAN_PRESSURE",
        name="压力波动幅度",
        description="管网压力波动范围，目标<±0.05MPa",
        dimension=ConditionDimension.ENGINEERING_HYDRAULIC,
        parameter_name="pressure_fluctuation",
        unit="MPa",
        grade_1_threshold=0.03,   # <=0.03 一级（优秀）
        grade_2_threshold=0.05,   # <=0.05 二级（达标）
        grade_3_threshold=0.08,   # <=0.08 三级（临界）
        higher_is_better=False
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_URBAN_SERVICE",
        name="服务连续性",
        description="供水服务可用率",
        dimension=ConditionDimension.HYDROLOGY_DEMAND,
        parameter_name="service_continuity",
        unit="%",
        grade_1_threshold=99.5,
        grade_2_threshold=99.0,
        grade_3_threshold=98.0,
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_URBAN_PUMP",
        name="泵站切换安全",
        description="泵站切换时的压力冲击程度",
        dimension=ConditionDimension.EQUIPMENT_EXECUTION,
        parameter_name="pump_switch_safety",
        unit="%",
        grade_1_threshold=95.0,
        grade_2_threshold=85.0,
        grade_3_threshold=70.0,
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_URBAN_SCADA",
        name="SCADA数据质量",
        description="监测数据完整性与实时性",
        dimension=ConditionDimension.DATA_SENSING_COMMUNICATION,
        parameter_name="scada_quality",
        unit="%",
        grade_1_threshold=98.0,
        grade_2_threshold=90.0,
        grade_3_threshold=80.0,
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_URBAN_DISPATCH",
        name="调度中心状态",
        description="调度中心人员与系统状态",
        dimension=ConditionDimension.ORGANIZATION_HUMAN,
        parameter_name="dispatch_status",
        discrete_grades={
            "FULL_OPERATION": ConditionGrade.GRADE_1,
            "REDUCED_STAFF": ConditionGrade.GRADE_2,
            "EMERGENCY_ONLY": ConditionGrade.GRADE_3
        }
    ))

    # 第四部分: 策略映射
    mapping = StrategyMapping(
        mapping_id="MAP_URBAN_001",
        name="城市供水策略映射",
        description="城市供水条件组合与策略等级映射"
    )

    mapping.add_combination(ConditionCombination(
        combination_id="COMB_URBAN_S3",
        name="完全自主运行条件",
        description="压力稳定、服务连续",
        dimension_requirements={
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_1,
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_1,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_1,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_1,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S3_FULL_AUTONOMOUS,
        priority=100
    ))

    mapping.add_combination(ConditionCombination(
        combination_id="COMB_URBAN_S2",
        name="受限自主运行条件",
        description="压力波动在可接受范围",
        dimension_requirements={
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_2,
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_2,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_2,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_1,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S2_MODEL_DRIVEN_LIMITED,
        priority=80
    ))

    spec.set_strategy_mapping(mapping)

    # 第五部分: 越界判定
    judgment = ViolationJudgment("JUDGE_URBAN_001", "城市供水越界判定")

    judgment.add_indicator(ViolationIndicator(
        indicator_id="IND_URBAN_PRESSURE",
        name="压力越界指标",
        description="压力波动超限",
        source_condition_id="COND_URBAN_PRESSURE",
        parameter_name="pressure_fluctuation",
        warning_threshold=0.06,
        violation_threshold=0.10,
        trigger_type=ViolationTriggerType.INSTANTANEOUS
    ))

    judgment.add_rule(DegradationRule(
        rule_id="RULE_URBAN_PRESSURE",
        name="压力退化规则",
        description="压力超限时切换保守模式",
        trigger_indicators=["IND_URBAN_PRESSURE"],
        forced_action=ForcedAction.SWITCH_MODE,
        action_parameters={'target_mode': 'CONSERVATIVE'},
        target_strategy=StrategyLevel.S1_RULE_CONSTRAINED
    ))

    spec.set_violation_judgment(judgment)

    # 第六部分: 证据索引
    evidence_index = EvidenceIndex("EVID_URBAN_001", "城市供水证据索引")
    spec.set_evidence_index(evidence_index)

    return spec


def create_flood_control_odd_engineering() -> ODDEngineeringSpec:
    """创建防洪调度ODD工程表达"""
    spec = ODDEngineeringSpec(
        spec_id="ODD_ENG_FLOOD_001",
        name="防洪调度ODD工程表达",
        description="防洪调度决策支持系统的运行设计域工程表达"
    )

    # 第一部分: 系统边界声明
    scope = ODDSystemScope(
        scope_id="SCOPE_FLOOD_001",
        name="防洪调度系统边界",
        description="流域防洪调度决策支持系统",
        system_type=SystemType.FLOOD_CONTROL,
        coverage_scope=CoverageScope.FULL_SYSTEM,
        upstream_boundary="流域上游控制断面",
        downstream_boundary="下游防护区",
        responsible_entity="防汛指挥部"
    )

    scope.add_excluded_scenario(ExcludedScenario(
        "EXC_FLOOD_001", "超标准洪水",
        "超过设计标准的特大洪水", "超出系统设计能力",
        "立即人工接管，启动应急预案"
    ))
    scope.add_excluded_scenario(ExcludedScenario(
        "EXC_FLOOD_002", "预报严重失准",
        "实测与预报偏差>50%", "模型失效",
        "切换至保守策略，人工决策"
    ))

    spec.set_system_scope(scope)

    # 第二/三部分: 条件分级
    # 核心条件: 预报不确定性
    spec.add_condition(GradedCondition(
        condition_id="COND_FLOOD_FORECAST_ERROR",
        name="预报误差范围",
        description="洪水预报的不确定性区间",
        dimension=ConditionDimension.HYDROLOGY_DEMAND,
        parameter_name="forecast_error_band",
        unit="%",
        grade_1_threshold=15.0,   # <=15% 一级（可信）
        grade_2_threshold=30.0,   # <=30% 二级（可用）
        grade_3_threshold=50.0,   # <=50% 三级（需谨慎）
        higher_is_better=False
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_FLOOD_RISK_LEVEL",
        name="洪水风险等级",
        description="当前洪水风险评估等级",
        dimension=ConditionDimension.HYDROLOGY_DEMAND,
        parameter_name="flood_risk_level",
        discrete_grades={
            "LOW": ConditionGrade.GRADE_1,       # 蓝色
            "MODERATE": ConditionGrade.GRADE_2,  # 黄色
            "HIGH": ConditionGrade.GRADE_2,      # 橙色
            "EXTREME": ConditionGrade.GRADE_3    # 红色
        }
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_FLOOD_RESERVOIR",
        name="水库调节能力",
        description="水库剩余调节库容占比",
        dimension=ConditionDimension.ENGINEERING_HYDRAULIC,
        parameter_name="reservoir_capacity_ratio",
        unit="%",
        grade_1_threshold=60.0,
        grade_2_threshold=30.0,
        grade_3_threshold=10.0,
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_FLOOD_GATE",
        name="泄洪设施可用性",
        description="泄洪闸/溢洪道可用程度",
        dimension=ConditionDimension.EQUIPMENT_EXECUTION,
        parameter_name="spillway_availability",
        unit="%",
        grade_1_threshold=100.0,
        grade_2_threshold=80.0,
        grade_3_threshold=50.0,
        higher_is_better=True
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_FLOOD_WARNING",
        name="预警发布状态",
        description="预警信息发布与响应状态",
        dimension=ConditionDimension.DATA_SENSING_COMMUNICATION,
        parameter_name="warning_status",
        discrete_grades={
            "FULL_COVERAGE": ConditionGrade.GRADE_1,
            "PARTIAL": ConditionGrade.GRADE_2,
            "LIMITED": ConditionGrade.GRADE_3
        }
    ))

    spec.add_condition(GradedCondition(
        condition_id="COND_FLOOD_COMMAND",
        name="指挥部响应能力",
        description="防汛指挥部人员与决策能力",
        dimension=ConditionDimension.ORGANIZATION_HUMAN,
        parameter_name="command_capability",
        discrete_grades={
            "FULL_ACTIVATION": ConditionGrade.GRADE_1,
            "STANDBY": ConditionGrade.GRADE_2,
            "MINIMAL": ConditionGrade.GRADE_3
        }
    ))

    # 第四部分: 策略映射 - 防洪调度特殊设计
    mapping = StrategyMapping(
        mapping_id="MAP_FLOOD_001",
        name="防洪调度策略映射",
        description="明确自主决策vs人工介入的边界"
    )

    # 只有低风险+高确定性时才允许S2（防洪不允许S3完全自主）
    mapping.add_combination(ConditionCombination(
        combination_id="COMB_FLOOD_S2",
        name="受限自主运行条件",
        description="低风险、预报可信时允许受限自主",
        dimension_requirements={
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_1,
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_1,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_1,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_1,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_1
        },
        allowed_strategy=StrategyLevel.S2_MODEL_DRIVEN_LIMITED,  # 最高S2
        priority=100
    ))

    # 中等风险或中等不确定性 -> S1
    mapping.add_combination(ConditionCombination(
        combination_id="COMB_FLOOD_S1",
        name="半自动运行条件",
        description="中等风险或预报可用时半自动",
        dimension_requirements={
            ConditionDimension.HYDROLOGY_DEMAND: ConditionGrade.GRADE_2,
            ConditionDimension.ENGINEERING_HYDRAULIC: ConditionGrade.GRADE_2,
            ConditionDimension.EQUIPMENT_EXECUTION: ConditionGrade.GRADE_2,
            ConditionDimension.DATA_SENSING_COMMUNICATION: ConditionGrade.GRADE_2,
            ConditionDimension.ORGANIZATION_HUMAN: ConditionGrade.GRADE_2
        },
        allowed_strategy=StrategyLevel.S1_RULE_CONSTRAINED,
        priority=80
    ))

    # 默认S0人工主导
    mapping.default_strategy = StrategyLevel.S0_HUMAN_DOMINANT

    spec.set_strategy_mapping(mapping)

    # 第五部分: 越界判定 - 防洪特殊设计（保守退化）
    judgment = ViolationJudgment("JUDGE_FLOOD_001", "防洪调度越界判定")

    judgment.add_indicator(ViolationIndicator(
        indicator_id="IND_FLOOD_FORECAST",
        name="预报误差越界指标",
        description="预报误差过大",
        source_condition_id="COND_FLOOD_FORECAST_ERROR",
        parameter_name="forecast_error_band",
        warning_threshold=40.0,
        violation_threshold=60.0,
        trigger_type=ViolationTriggerType.INSTANTANEOUS
    ))

    judgment.add_indicator(ViolationIndicator(
        indicator_id="IND_FLOOD_CAPACITY",
        name="库容越界指标",
        description="调节库容不足",
        source_condition_id="COND_FLOOD_RESERVOIR",
        parameter_name="reservoir_capacity_ratio",
        warning_threshold=20.0,
        violation_threshold=5.0,
        trigger_type=ViolationTriggerType.INSTANTANEOUS
    ))

    # 防洪的保守退化策略
    judgment.add_rule(DegradationRule(
        rule_id="RULE_FLOOD_CONSERVATIVE",
        name="保守退化规则",
        description="预报误差大或库容不足时立即人工接管",
        trigger_indicators=["IND_FLOOD_FORECAST", "IND_FLOOD_CAPACITY"],
        trigger_logic="ANY",  # 任一触发
        forced_action=ForcedAction.HUMAN_TAKEOVER,
        target_strategy=StrategyLevel.S0_HUMAN_DOMINANT
    ))

    spec.set_violation_judgment(judgment)

    # 第六部分: 证据索引
    evidence_index = EvidenceIndex("EVID_FLOOD_001", "防洪调度证据索引")

    evidence_index.add_evidence(TestEvidence(
        evidence_id="EV_FLOOD_HITL_001",
        name="防洪调度HITL测试",
        description="人机协同防洪调度演练",
        evidence_type=EvidenceType.HITL_TEST,
        related_odd_statement="COND_FLOOD_COMMAND",
        scenario_criticality=ScenarioCriticality.EXTREME,
        result_summary="应急响应时间<10min",
        pass_fail=True,
        storage_path="/tests/hitl/flood/emergency_response_001.json"
    ))

    evidence_index.add_assumption(ModelAssumption(
        assumption_id="ASM_FLOOD_001",
        name="洪水演进模型假设",
        description="一维圣维南方程适用性假设",
        assumption_content="河道断面规则，顺直河段",
        validity_range="主要防洪河道",
        is_verified=True,
        verification_method="历史洪水过程验证"
    ))

    spec.set_evidence_index(evidence_index)

    return spec


# 导出
__all__ = [
    # 第一部分
    'SystemType', 'CoverageScope', 'ExcludedScenario', 'SystemNode', 'ODDSystemScope',
    # 第二部分
    'ConditionDimension', 'DimensionCondition',
    # 第三部分
    'ConditionLevel', 'ConditionGrade', 'GradedCondition',
    # 第四部分
    'StrategyLevel', 'ConditionCombination', 'StrategyMapping',
    # 第五部分
    'ViolationTriggerType', 'ForcedAction', 'ViolationIndicator',
    'DegradationRule', 'ViolationJudgment',
    # 第六部分
    'EvidenceType', 'ScenarioCriticality', 'TestEvidence',
    'ModelAssumption', 'EvidenceIndex',
    # 完整规范
    'ODDEngineeringSpec',
    # 工厂函数
    'create_irrigation_odd_engineering',
    'create_water_transfer_odd_engineering',
    'create_urban_water_supply_odd_engineering',
    'create_flood_control_odd_engineering',
]
