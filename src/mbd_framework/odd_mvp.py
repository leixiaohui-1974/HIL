# -*- coding: utf-8 -*-
"""
MVP ODD Framework - 最小可行ODD框架
Minimum Viable Product ODD for Water Network Systems

核心原则：先做出可审查、可验收、可定责的最小ODD集，再逐步扩展

四条硬边界：
1. 规范硬约束边界 - 从规范与计算书直接抽取
2. 执行硬能力边界 - 从设备参数与工况试验抽取
3. 信息硬条件边界 - 从系统架构与监测质量抽取
4. 组织硬兜底边界 - 能被演练与验收

三个工程特性：
- 分级明确（正常/受限/禁止）
- 每个阈值都能追溯来源
- 每个等级都映射到策略等级与退化动作
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import json


# ============================================================================
# 硬边界分类
# ============================================================================

class HardBoundaryType(Enum):
    """
    四条硬边界类型

    没有它们就谈不上自主运行
    """
    # 1. 规范硬约束边界 - 从规范与计算书直接抽取
    REGULATORY = "规范硬约束"

    # 2. 执行硬能力边界 - 从设备参数与工况试验抽取
    EXECUTION = "执行硬能力"

    # 3. 信息硬条件边界 - 从系统架构与监测质量抽取
    INFORMATION = "信息硬条件"

    # 4. 组织硬兜底边界 - 能被演练与验收
    ORGANIZATION = "组织硬兜底"


class BoundaryLevel(Enum):
    """
    边界分级 - 少而硬、分级清晰

    三级制：正常/受限/禁止
    """
    NORMAL = "正常"      # 允许S3完全自主
    RESTRICTED = "受限"  # 降为S1/S2
    PROHIBITED = "禁止"  # 必须S0人工主导或停机


class SourceType(Enum):
    """
    来源类型 - 确保可追溯
    """
    REGULATION = "规范条款"        # 如：《水利水电工程运行管理规范》
    DESIGN_SPEC = "设计计算书"     # 如：闸门设计计算书
    EQUIPMENT_PARAM = "设备参数"   # 如：泵站铭牌参数
    TEST_REPORT = "试验报告"       # 如：工况试验报告
    SYSTEM_SPEC = "系统指标"       # 如：SCADA系统技术要求
    OPERATION_RULE = "运行规程"    # 如：调度规程
    EMERGENCY_PLAN = "应急预案"    # 如：防汛应急预案


@dataclass
class SourceReference:
    """
    来源引用 - 每个阈值都能追溯来源

    这是MVP ODD的核心工程特性之一
    """
    source_type: SourceType
    document_name: str         # 文档名称
    document_id: str = ""      # 文档编号
    section: str = ""          # 章节条款
    page: str = ""             # 页码
    revision: str = ""         # 版本
    effective_date: str = ""   # 生效日期
    extract_value: str = ""    # 抽取的具体数值/条款
    notes: str = ""            # 备注

    def to_citation(self) -> str:
        """生成引用字符串"""
        parts = [self.document_name]
        if self.section:
            parts.append(f"第{self.section}")
        if self.page:
            parts.append(f"P{self.page}")
        if self.document_id:
            parts.append(f"[{self.document_id}]")
        return ", ".join(parts)


# ============================================================================
# 硬边界定义
# ============================================================================

@dataclass
class HardBoundary:
    """
    硬边界定义

    MVP ODD的核心单元
    """
    boundary_id: str
    name: str
    description: str
    boundary_type: HardBoundaryType

    # 参数定义
    parameter_name: str
    unit: str = ""

    # 分级阈值（必须明确）
    normal_max: Optional[float] = None    # 正常上限
    normal_min: Optional[float] = None    # 正常下限
    restricted_max: Optional[float] = None  # 受限上限
    restricted_min: Optional[float] = None  # 受限下限
    # 超出restricted即为prohibited

    # 来源追溯（核心！）
    source: Optional[SourceReference] = None

    # 策略映射（必须有！）
    normal_strategy: str = "S3"      # 正常时允许的最高策略
    restricted_strategy: str = "S1"  # 受限时的策略
    prohibited_action: str = "S0+人工接管"  # 禁止时的动作

    # 退化动作
    restricted_degradation: str = ""  # 进入受限时的动作
    prohibited_degradation: str = ""  # 进入禁止时的动作

    # 验证状态
    is_verified: bool = False
    verification_date: Optional[datetime] = None
    verification_method: str = ""

    def evaluate(self, value: float) -> Tuple[BoundaryLevel, str]:
        """
        评估当前值的边界等级

        Returns:
            (等级, 说明)
        """
        # 检查正常范围
        in_normal = True
        if self.normal_max is not None and value > self.normal_max:
            in_normal = False
        if self.normal_min is not None and value < self.normal_min:
            in_normal = False

        if in_normal:
            return BoundaryLevel.NORMAL, f"在正常范围内 [{self.normal_min}, {self.normal_max}]"

        # 检查受限范围
        in_restricted = True
        if self.restricted_max is not None and value > self.restricted_max:
            in_restricted = False
        if self.restricted_min is not None and value < self.restricted_min:
            in_restricted = False

        if in_restricted:
            return BoundaryLevel.RESTRICTED, f"在受限范围内，超出正常范围"

        return BoundaryLevel.PROHIBITED, f"超出允许范围，必须{self.prohibited_action}"

    def get_strategy(self, level: BoundaryLevel) -> str:
        """获取对应等级的策略"""
        if level == BoundaryLevel.NORMAL:
            return self.normal_strategy
        elif level == BoundaryLevel.RESTRICTED:
            return self.restricted_strategy
        else:
            return self.prohibited_action

    def to_audit_record(self) -> Dict[str, Any]:
        """生成审计记录（用于验收）"""
        return {
            'boundary_id': self.boundary_id,
            'name': self.name,
            'type': self.boundary_type.value,
            'parameter': self.parameter_name,
            'unit': self.unit,
            'thresholds': {
                'normal': f"[{self.normal_min}, {self.normal_max}]",
                'restricted': f"[{self.restricted_min}, {self.restricted_max}]"
            },
            'source': self.source.to_citation() if self.source else "未追溯",
            'strategy_mapping': {
                '正常': self.normal_strategy,
                '受限': self.restricted_strategy,
                '禁止': self.prohibited_action
            },
            'verified': self.is_verified,
            'verification_method': self.verification_method
        }


# ============================================================================
# 四条硬边界具体定义
# ============================================================================

@dataclass
class RegulatoryBoundary(HardBoundary):
    """
    1. 规范硬约束边界

    从规范与计算书直接抽取，特点是"本来就存在于现行规范体系中，自主运行只是不得突破"
    典型包括：
    - 水位红线（防洪限制水位、兴利水位、死水位等）
    - 关键断面/管段的流量、压力安全边界
    - 生态下泄、供水保证率等硬约束条款
    """
    # 规范特有属性
    regulation_type: str = ""     # 规范类型：国标/行标/地标/企标
    mandatory_level: str = ""     # 强制等级：强制性/推荐性
    legal_consequence: str = ""   # 违反后果

    def __post_init__(self):
        self.boundary_type = HardBoundaryType.REGULATORY


@dataclass
class ExecutionBoundary(HardBoundary):
    """
    2. 执行硬能力边界

    从设备参数与工况试验抽取，决定"策略在物理上能不能实现"
    典型包括：
    - 闸门启闭速度、最小可控开度、卡阻风险区间
    - 泵站可用台数、调速范围、启停约束、爬坡时间
    - 备用与冗余条件
    """
    # 设备特有属性
    equipment_id: str = ""        # 设备编号
    equipment_type: str = ""      # 设备类型
    failure_mode: str = ""        # 失效模式
    redundancy_level: int = 0     # 冗余等级

    def __post_init__(self):
        self.boundary_type = HardBoundaryType.EXECUTION


@dataclass
class InformationBoundary(HardBoundary):
    """
    3. 信息硬条件边界

    从系统架构与监测质量抽取，决定"系统是不是在盲开"
    典型包括：
    - 关键量测误差上限、缺测允许时长
    - 通信延迟、丢包率上限
    - 预测更新频率与滞后容忍度
    """
    # 信息特有属性
    data_source: str = ""         # 数据来源设备
    measurement_type: str = ""    # 测量类型
    update_frequency: float = 0   # 更新频率(秒)
    max_latency: float = 0        # 最大允许延迟(秒)
    max_missing_duration: float = 0  # 最大允许缺测时长(秒)

    def __post_init__(self):
        self.boundary_type = HardBoundaryType.INFORMATION


@dataclass
class OrganizationBoundary(HardBoundary):
    """
    4. 组织硬兜底边界

    能被演练与验收，让"越界"不再是口头承诺，而是可执行制度
    典型包括：
    - 人工接管时间（接管响应SLA）
    - 权限链路（谁能接管、如何接管、接管后系统如何让权）
    - 退化策略触发后的组织动作
    """
    # 组织特有属性
    role_required: str = ""       # 需要的角色
    response_sla: float = 0       # 响应SLA(秒)
    takeover_procedure: str = ""  # 接管程序
    handover_mechanism: str = ""  # 让权机制
    drill_frequency: str = ""     # 演练频率
    last_drill_date: Optional[datetime] = None  # 上次演练日期

    def __post_init__(self):
        self.boundary_type = HardBoundaryType.ORGANIZATION


# ============================================================================
# MVP ODD 定义
# ============================================================================

class MVPODDStatus(Enum):
    """MVP ODD状态"""
    DRAFT = "草稿"
    UNDER_REVIEW = "审查中"
    APPROVED = "已批准"
    ACTIVE = "生效中"
    SUPERSEDED = "已替代"


@dataclass
class MVPODDDefinition:
    """
    MVP ODD定义

    核心原则：少而硬、分级清晰、来源可追溯
    """
    odd_id: str
    name: str
    description: str
    version: str = "1.0"
    status: MVPODDStatus = MVPODDStatus.DRAFT

    # 四条硬边界
    regulatory_boundaries: List[RegulatoryBoundary] = field(default_factory=list)
    execution_boundaries: List[ExecutionBoundary] = field(default_factory=list)
    information_boundaries: List[InformationBoundary] = field(default_factory=list)
    organization_boundaries: List[OrganizationBoundary] = field(default_factory=list)

    # 审批信息
    author: str = ""
    reviewer: str = ""
    approver: str = ""
    approval_date: Optional[datetime] = None

    # 适用范围
    applicable_system: str = ""
    applicable_scope: str = ""
    excluded_scenarios: List[str] = field(default_factory=list)

    def add_regulatory(self, boundary: RegulatoryBoundary):
        """添加规范硬约束边界"""
        self.regulatory_boundaries.append(boundary)

    def add_execution(self, boundary: ExecutionBoundary):
        """添加执行硬能力边界"""
        self.execution_boundaries.append(boundary)

    def add_information(self, boundary: InformationBoundary):
        """添加信息硬条件边界"""
        self.information_boundaries.append(boundary)

    def add_organization(self, boundary: OrganizationBoundary):
        """添加组织硬兜底边界"""
        self.organization_boundaries.append(boundary)

    def get_all_boundaries(self) -> List[HardBoundary]:
        """获取所有硬边界"""
        return (self.regulatory_boundaries +
                self.execution_boundaries +
                self.information_boundaries +
                self.organization_boundaries)

    def evaluate(self, values: Dict[str, float]) -> Dict[str, Any]:
        """
        评估当前运行点

        Returns:
            评估结果，包含各边界状态和允许的最高策略
        """
        result = {
            'odd_id': self.odd_id,
            'timestamp': datetime.now().isoformat(),
            'boundary_results': [],
            'overall_level': BoundaryLevel.NORMAL,
            'allowed_strategy': 'S3',
            'violations': [],
            'warnings': []
        }

        worst_level = BoundaryLevel.NORMAL
        strategy_map = {'S3': 3, 'S2': 2, 'S1': 1, 'S0': 0}
        min_strategy = 'S3'

        for boundary in self.get_all_boundaries():
            if boundary.parameter_name in values:
                value = values[boundary.parameter_name]
                level, msg = boundary.evaluate(value)
                strategy = boundary.get_strategy(level)

                result['boundary_results'].append({
                    'boundary_id': boundary.boundary_id,
                    'name': boundary.name,
                    'type': boundary.boundary_type.value,
                    'value': value,
                    'level': level.value,
                    'strategy': strategy,
                    'message': msg
                })

                # 更新最差等级
                if level == BoundaryLevel.PROHIBITED:
                    worst_level = BoundaryLevel.PROHIBITED
                    result['violations'].append({
                        'boundary': boundary.name,
                        'value': value,
                        'action': boundary.prohibited_action
                    })
                elif level == BoundaryLevel.RESTRICTED and worst_level != BoundaryLevel.PROHIBITED:
                    worst_level = BoundaryLevel.RESTRICTED
                    result['warnings'].append({
                        'boundary': boundary.name,
                        'value': value,
                        'degradation': boundary.restricted_degradation
                    })

                # 更新最保守策略
                strategy_base = strategy.split('+')[0] if '+' in strategy else strategy
                if strategy_base in strategy_map:
                    if strategy_map.get(strategy_base, 0) < strategy_map.get(min_strategy, 3):
                        min_strategy = strategy_base

        result['overall_level'] = worst_level.value
        result['allowed_strategy'] = min_strategy

        return result

    def validate_completeness(self) -> Dict[str, Any]:
        """
        验证MVP ODD完整性

        检查四条硬边界是否都有定义
        """
        result = {
            'odd_id': self.odd_id,
            'is_complete': True,
            'missing': [],
            'warnings': [],
            'statistics': {}
        }

        # 检查四条硬边界
        if not self.regulatory_boundaries:
            result['is_complete'] = False
            result['missing'].append("规范硬约束边界")

        if not self.execution_boundaries:
            result['is_complete'] = False
            result['missing'].append("执行硬能力边界")

        if not self.information_boundaries:
            result['is_complete'] = False
            result['missing'].append("信息硬条件边界")

        if not self.organization_boundaries:
            result['is_complete'] = False
            result['missing'].append("组织硬兜底边界")

        # 检查来源追溯
        all_boundaries = self.get_all_boundaries()
        missing_source = [b.name for b in all_boundaries if not b.source]
        if missing_source:
            result['warnings'].append(f"以下边界缺少来源追溯: {missing_source}")

        # 检查验证状态
        unverified = [b.name for b in all_boundaries if not b.is_verified]
        if unverified:
            result['warnings'].append(f"以下边界未经验证: {unverified}")

        # 统计
        result['statistics'] = {
            'regulatory': len(self.regulatory_boundaries),
            'execution': len(self.execution_boundaries),
            'information': len(self.information_boundaries),
            'organization': len(self.organization_boundaries),
            'total': len(all_boundaries),
            'with_source': len(all_boundaries) - len(missing_source),
            'verified': len(all_boundaries) - len(unverified)
        }

        return result

    def generate_audit_document(self) -> str:
        """
        生成审计文档

        用于验收和定责
        """
        doc = []
        doc.append(f"# MVP ODD 审计文档")
        doc.append(f"\n## 基本信息")
        doc.append(f"- ODD编号: {self.odd_id}")
        doc.append(f"- 名称: {self.name}")
        doc.append(f"- 版本: {self.version}")
        doc.append(f"- 状态: {self.status.value}")
        doc.append(f"- 适用系统: {self.applicable_system}")
        doc.append(f"- 适用范围: {self.applicable_scope}")

        if self.excluded_scenarios:
            doc.append(f"\n### 排除场景")
            for scenario in self.excluded_scenarios:
                doc.append(f"- {scenario}")

        # 四条硬边界
        doc.append(f"\n## 一、规范硬约束边界 ({len(self.regulatory_boundaries)}项)")
        doc.append('*特点：本来就存在于现行规范体系中，自主运行只是"不得突破"*\n')
        for b in self.regulatory_boundaries:
            doc.append(f"### {b.boundary_id}: {b.name}")
            doc.append(f"- 参数: {b.parameter_name} ({b.unit})")
            doc.append(f"- 正常范围: [{b.normal_min}, {b.normal_max}]")
            doc.append(f"- 受限范围: [{b.restricted_min}, {b.restricted_max}]")
            doc.append(f"- 来源: {b.source.to_citation() if b.source else '待追溯'}")
            doc.append(f"- 策略映射: 正常→{b.normal_strategy}, 受限→{b.restricted_strategy}, 禁止→{b.prohibited_action}")
            if b.regulation_type:
                doc.append(f"- 规范类型: {b.regulation_type}")
            doc.append("")

        doc.append(f"\n## 二、执行硬能力边界 ({len(self.execution_boundaries)}项)")
        doc.append('*特点：决定"策略在物理上能不能实现"*\n')
        for b in self.execution_boundaries:
            doc.append(f"### {b.boundary_id}: {b.name}")
            doc.append(f"- 参数: {b.parameter_name} ({b.unit})")
            doc.append(f"- 正常范围: [{b.normal_min}, {b.normal_max}]")
            doc.append(f"- 受限范围: [{b.restricted_min}, {b.restricted_max}]")
            doc.append(f"- 来源: {b.source.to_citation() if b.source else '待追溯'}")
            doc.append(f"- 策略映射: 正常→{b.normal_strategy}, 受限→{b.restricted_strategy}, 禁止→{b.prohibited_action}")
            if b.equipment_id:
                doc.append(f"- 设备编号: {b.equipment_id}")
            doc.append("")

        doc.append(f"\n## 三、信息硬条件边界 ({len(self.information_boundaries)}项)")
        doc.append('*特点：决定"系统是不是在盲开"*\n')
        for b in self.information_boundaries:
            doc.append(f"### {b.boundary_id}: {b.name}")
            doc.append(f"- 参数: {b.parameter_name} ({b.unit})")
            doc.append(f"- 正常范围: [{b.normal_min}, {b.normal_max}]")
            doc.append(f"- 受限范围: [{b.restricted_min}, {b.restricted_max}]")
            doc.append(f"- 来源: {b.source.to_citation() if b.source else '待追溯'}")
            doc.append(f"- 策略映射: 正常→{b.normal_strategy}, 受限→{b.restricted_strategy}, 禁止→{b.prohibited_action}")
            if b.max_latency > 0:
                doc.append(f"- 最大延迟: {b.max_latency}秒")
            doc.append("")

        doc.append(f"\n## 四、组织硬兜底边界 ({len(self.organization_boundaries)}项)")
        doc.append('*特点：让"越界"不再是口头承诺，而是可执行制度*\n')
        for b in self.organization_boundaries:
            doc.append(f"### {b.boundary_id}: {b.name}")
            doc.append(f"- 参数: {b.parameter_name} ({b.unit})")
            doc.append(f"- 正常范围: [{b.normal_min}, {b.normal_max}]")
            doc.append(f"- 受限范围: [{b.restricted_min}, {b.restricted_max}]")
            doc.append(f"- 来源: {b.source.to_citation() if b.source else '待追溯'}")
            doc.append(f"- 策略映射: 正常→{b.normal_strategy}, 受限→{b.restricted_strategy}, 禁止→{b.prohibited_action}")
            if b.response_sla > 0:
                doc.append(f"- 响应SLA: {b.response_sla}秒")
            if b.takeover_procedure:
                doc.append(f"- 接管程序: {b.takeover_procedure}")
            doc.append("")

        # 完整性验证
        completeness = self.validate_completeness()
        doc.append(f"\n## 完整性验证")
        doc.append(f"- 完整: {'是' if completeness['is_complete'] else '否'}")
        if completeness['missing']:
            doc.append(f"- 缺失: {completeness['missing']}")
        doc.append(f"- 边界总数: {completeness['statistics']['total']}")
        doc.append(f"- 已追溯来源: {completeness['statistics']['with_source']}")
        doc.append(f"- 已验证: {completeness['statistics']['verified']}")

        # 签署区
        doc.append(f"\n## 签署")
        doc.append(f"- 编制: {self.author}")
        doc.append(f"- 审核: {self.reviewer}")
        doc.append(f"- 批准: {self.approver}")
        if self.approval_date:
            doc.append(f"- 批准日期: {self.approval_date.strftime('%Y-%m-%d')}")

        return "\n".join(doc)


# ============================================================================
# 渐进扩展：软边界定义
# ============================================================================

class SoftBoundaryCategory(Enum):
    """
    软边界类别

    MVP ODD跑通后再纳入
    """
    FORECAST_UNCERTAINTY = "预测误差统计"  # 按季节、年景、流域状态分型
    SCENARIO_COMBINATION = "工况组合细化"  # 多水源、多工程联动、叠加事件
    RISK_PREFERENCE = "风险偏好参数"       # 更保守/更效率的策略选择
    ORG_MATURITY = "组织成熟度分级"        # 不同接管能力对应不同策略等级上限


@dataclass
class SoftBoundary:
    """
    软边界 - 第二阶段扩展

    在MVP ODD跑通后逐步纳入
    """
    boundary_id: str
    name: str
    description: str
    category: SoftBoundaryCategory

    # 参数
    parameter_name: str
    unit: str = ""

    # 分级（可以更细）
    levels: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    # 策略影响
    strategy_modifier: str = ""  # 对策略的调整影响

    # 状态
    is_calibrated: bool = False  # 是否已标定
    calibration_data: str = ""   # 标定数据来源


@dataclass
class ExtendedODD:
    """
    扩展ODD

    在MVP基础上增加软边界
    """
    mvp_odd: MVPODDDefinition
    soft_boundaries: List[SoftBoundary] = field(default_factory=list)

    # 扩展状态
    extension_version: str = "1.0"
    extension_date: Optional[datetime] = None
    extension_reason: str = ""

    def add_soft_boundary(self, boundary: SoftBoundary):
        """添加软边界"""
        self.soft_boundaries.append(boundary)

    def get_maturity_level(self) -> str:
        """
        获取ODD成熟度等级

        MVP: 只有四条硬边界
        L1: 加入预测误差统计
        L2: 加入工况组合细化
        L3: 加入风险偏好和组织成熟度
        """
        if not self.soft_boundaries:
            return "MVP"

        categories = set(b.category for b in self.soft_boundaries)

        if SoftBoundaryCategory.ORG_MATURITY in categories:
            return "L3-完整"
        elif SoftBoundaryCategory.SCENARIO_COMBINATION in categories:
            return "L2-增强"
        elif SoftBoundaryCategory.FORECAST_UNCERTAINTY in categories:
            return "L1-基础扩展"

        return "MVP+"


# ============================================================================
# 工厂函数：创建各类水网的MVP ODD
# ============================================================================

def create_reservoir_mvp_odd() -> MVPODDDefinition:
    """
    创建水库调度MVP ODD

    最简单的水利工程场景
    """
    odd = MVPODDDefinition(
        odd_id="MVP_ODD_RESERVOIR_001",
        name="水库调度MVP ODD",
        description="水库智能调度系统的最小可行运行设计域",
        applicable_system="XX水库调度系统",
        applicable_scope="水库日常调度运行"
    )

    odd.excluded_scenarios = [
        "超标准洪水（超过设计洪水）",
        "大坝安全事故",
        "通信全部中断超过2小时"
    ]

    # ===== 1. 规范硬约束边界 =====

    # 水位红线
    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_001",
        name="防洪限制水位",
        description="汛期最高运行水位限制",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="water_level",
        unit="m",
        normal_max=145.0,       # 正常运行上限
        normal_min=125.0,       # 兴利死水位
        restricted_max=148.0,   # 允许短时超蓄
        restricted_min=123.0,   # 允许短时低于死水位
        source=SourceReference(
            source_type=SourceType.REGULATION,
            document_name="XX水库调度规程",
            document_id="SD-2023-001",
            section="4.2.1",
            extract_value="汛限水位145.0m，死水位125.0m"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+立即报告调度中心",
        restricted_degradation="启动预警，准备泄洪",
        prohibited_degradation="紧急泄洪，人工接管",
        regulation_type="企业标准",
        mandatory_level="强制性",
        legal_consequence="违反调度规程",
        is_verified=True,
        verification_method="历史运行数据验证"
    ))

    # 下泄流量边界
    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_002",
        name="最小下泄流量",
        description="生态基流保障",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="outflow",
        unit="m³/s",
        normal_min=50.0,        # 正常生态流量
        normal_max=2000.0,      # 正常泄洪能力
        restricted_min=30.0,    # 极端枯水允许
        restricted_max=2500.0,  # 应急泄洪
        source=SourceReference(
            source_type=SourceType.REGULATION,
            document_name="XX河流域水量分配方案",
            section="3.1",
            extract_value="生态基流不低于50m³/s"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+启动应急预案"
    ))

    # ===== 2. 执行硬能力边界 =====

    # 闸门能力
    odd.add_execution(ExecutionBoundary(
        boundary_id="EXE_001",
        name="泄洪闸门开度",
        description="泄洪闸可控开度范围",
        boundary_type=HardBoundaryType.EXECUTION,
        parameter_name="gate_opening",
        unit="%",
        normal_min=5.0,         # 最小可控开度
        normal_max=100.0,
        restricted_min=0.0,     # 全关
        restricted_max=100.0,
        source=SourceReference(
            source_type=SourceType.EQUIPMENT_PARAM,
            document_name="泄洪闸门技术参数",
            document_id="EQ-GATE-001",
            extract_value="最小可控开度5%"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+检修",
        equipment_id="GATE-001",
        equipment_type="平板闸门",
        failure_mode="卡阻",
        redundancy_level=2
    ))

    # 闸门启闭速度
    odd.add_execution(ExecutionBoundary(
        boundary_id="EXE_002",
        name="闸门启闭速度",
        description="闸门动作速度限制",
        boundary_type=HardBoundaryType.EXECUTION,
        parameter_name="gate_speed",
        unit="m/min",
        normal_min=0.3,
        normal_max=1.0,
        restricted_min=0.1,
        restricted_max=1.5,
        source=SourceReference(
            source_type=SourceType.EQUIPMENT_PARAM,
            document_name="闸门启闭机说明书",
            extract_value="额定速度0.5m/min，最大1.0m/min"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+设备保护",
        equipment_type="卷扬式启闭机"
    ))

    # ===== 3. 信息硬条件边界 =====

    # 水位测量
    odd.add_information(InformationBoundary(
        boundary_id="INF_001",
        name="库水位测量误差",
        description="水位传感器测量精度",
        boundary_type=HardBoundaryType.INFORMATION,
        parameter_name="level_measurement_error",
        unit="cm",
        normal_max=2.0,         # 正常误差
        normal_min=0.0,
        restricted_max=5.0,     # 允许较大误差
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="水位监测系统技术规格",
            extract_value="测量精度±2cm"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+人工测量",
        data_source="压力式水位计",
        measurement_type="连续测量",
        update_frequency=60.0,
        max_latency=5.0,
        max_missing_duration=300.0
    ))

    # 通信延迟
    odd.add_information(InformationBoundary(
        boundary_id="INF_002",
        name="SCADA通信延迟",
        description="调度指令传输延迟",
        boundary_type=HardBoundaryType.INFORMATION,
        parameter_name="comm_latency",
        unit="ms",
        normal_max=500.0,
        normal_min=0.0,
        restricted_max=2000.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="SCADA系统技术要求",
            extract_value="端到端延迟<500ms"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+通信中断处理",
        max_latency=2.0
    ))

    # ===== 4. 组织硬兜底边界 =====

    # 人工接管时间
    odd.add_organization(OrganizationBoundary(
        boundary_id="ORG_001",
        name="人工接管响应时间",
        description="值班人员接管系统的响应时间",
        boundary_type=HardBoundaryType.ORGANIZATION,
        parameter_name="takeover_response_time",
        unit="min",
        normal_max=5.0,         # 5分钟内响应
        normal_min=0.0,
        restricted_max=15.0,    # 15分钟内响应
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.OPERATION_RULE,
            document_name="水库值班管理制度",
            section="5.3",
            extract_value="接到告警后5分钟内响应"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+启动应急值班",
        role_required="值班调度员",
        response_sla=300.0,  # 5分钟
        takeover_procedure="1.确认告警 2.评估状态 3.切换手动 4.执行操作",
        handover_mechanism="系统自动让权，显示人工控制状态",
        drill_frequency="每月1次"
    ))

    # 会商决策机制
    odd.add_organization(OrganizationBoundary(
        boundary_id="ORG_002",
        name="会商决策响应时间",
        description="重大决策会商响应时间",
        boundary_type=HardBoundaryType.ORGANIZATION,
        parameter_name="consultation_response_time",
        unit="min",
        normal_max=30.0,
        normal_min=0.0,
        restricted_max=60.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.EMERGENCY_PLAN,
            document_name="水库防汛应急预案",
            section="4.2",
            extract_value="Ⅲ级响应30分钟内启动会商"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+启动应急指挥",
        role_required="调度中心主任",
        response_sla=1800.0,  # 30分钟
        takeover_procedure="1.发起会商 2.汇报情况 3.形成决策 4.下达指令"
    ))

    odd.author = "调度中心"
    odd.reviewer = "安全监察部"
    odd.approver = "总工程师"

    return odd


def create_irrigation_mvp_odd() -> MVPODDDefinition:
    """创建灌区水网MVP ODD"""
    odd = MVPODDDefinition(
        odd_id="MVP_ODD_IRRIGATION_001",
        name="灌区水网MVP ODD",
        description="灌区智能配水系统的最小可行运行设计域",
        applicable_system="XX灌区配水调度系统",
        applicable_scope="灌区日常配水运行"
    )

    odd.excluded_scenarios = [
        "极端干旱（来水<30%保证率）",
        "渠道重大事故",
        "全系统断电超过4小时"
    ]

    # 规范硬约束
    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_IRR_001",
        name="渠道安全水深",
        description="干渠最大允许水深",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="channel_depth",
        unit="m",
        normal_max=2.5,
        normal_min=0.3,
        restricted_max=2.8,
        restricted_min=0.1,
        source=SourceReference(
            source_type=SourceType.DESIGN_SPEC,
            document_name="灌区渠道设计计算书",
            extract_value="设计水深2.5m，安全超高0.3m"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+紧急调节"
    ))

    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_IRR_002",
        name="配水公平性",
        description="各用水户配水比例偏差",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="fairness_deviation",
        unit="%",
        normal_max=10.0,
        normal_min=0.0,
        restricted_max=20.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.OPERATION_RULE,
            document_name="灌区用水管理办法",
            section="第12条",
            extract_value="配水偏差不超过10%"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+人工协调"
    ))

    # 执行硬能力
    odd.add_execution(ExecutionBoundary(
        boundary_id="EXE_IRR_001",
        name="分水闸可用率",
        description="分水闸门可正常操作的比例",
        boundary_type=HardBoundaryType.EXECUTION,
        parameter_name="gate_availability",
        unit="%",
        normal_min=90.0,
        normal_max=100.0,
        restricted_min=70.0,
        restricted_max=100.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="灌区自动化系统技术要求",
            extract_value="闸门可用率≥90%"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+人工操作"
    ))

    # 信息硬条件
    odd.add_information(InformationBoundary(
        boundary_id="INF_IRR_001",
        name="流量测量完整率",
        description="关键测点数据可用率",
        boundary_type=HardBoundaryType.INFORMATION,
        parameter_name="data_completeness",
        unit="%",
        normal_min=95.0,
        normal_max=100.0,
        restricted_min=80.0,
        restricted_max=100.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="灌区监测系统规范",
            extract_value="数据完整率≥95%"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+人工巡测",
        max_missing_duration=1800.0  # 30分钟
    ))

    # 组织硬兜底
    odd.add_organization(OrganizationBoundary(
        boundary_id="ORG_IRR_001",
        name="配水调度响应",
        description="配水调度员响应时间",
        boundary_type=HardBoundaryType.ORGANIZATION,
        parameter_name="dispatch_response",
        unit="min",
        normal_max=10.0,
        normal_min=0.0,
        restricted_max=30.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.OPERATION_RULE,
            document_name="灌区值班制度",
            extract_value="配水调整响应时间≤10分钟"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+启动应急",
        response_sla=600.0,
        role_required="配水调度员"
    ))

    return odd


def create_urban_supply_mvp_odd() -> MVPODDDefinition:
    """创建城市供水MVP ODD"""
    odd = MVPODDDefinition(
        odd_id="MVP_ODD_URBAN_001",
        name="城市供水MVP ODD",
        description="城市供水管网智能调度的最小可行运行设计域",
        applicable_system="XX市供水调度系统",
        applicable_scope="城市供水日常运行"
    )

    odd.excluded_scenarios = [
        "主干管爆管事故",
        "水源污染事件",
        "大面积停电超过2小时"
    ]

    # 规范硬约束 - 压力边界
    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_URB_001",
        name="管网服务压力",
        description="用户端最低服务压力",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="service_pressure",
        unit="MPa",
        normal_min=0.14,
        normal_max=0.45,
        restricted_min=0.10,
        restricted_max=0.50,
        source=SourceReference(
            source_type=SourceType.REGULATION,
            document_name="城市给水工程规划规范(GB50282)",
            section="4.0.7",
            extract_value="居民生活用水压力≥0.14MPa"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+启动应急供水"
    ))

    # 压力波动
    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_URB_002",
        name="压力波动幅度",
        description="管网压力波动控制",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="pressure_fluctuation",
        unit="MPa",
        normal_max=0.05,
        normal_min=0.0,
        restricted_max=0.08,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="供水服务质量标准",
            extract_value="压力波动≤±0.05MPa"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+泵站切换"
    ))

    # 执行硬能力 - 泵站
    odd.add_execution(ExecutionBoundary(
        boundary_id="EXE_URB_001",
        name="泵站可用容量",
        description="泵站可用出力占额定的比例",
        boundary_type=HardBoundaryType.EXECUTION,
        parameter_name="pump_capacity",
        unit="%",
        normal_min=80.0,
        normal_max=100.0,
        restricted_min=60.0,
        restricted_max=100.0,
        source=SourceReference(
            source_type=SourceType.EQUIPMENT_PARAM,
            document_name="泵站设备台账",
            extract_value="N+1冗余配置"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+启动备用",
        redundancy_level=1
    ))

    # 信息硬条件
    odd.add_information(InformationBoundary(
        boundary_id="INF_URB_001",
        name="SCADA数据质量",
        description="监测数据实时性和完整性",
        boundary_type=HardBoundaryType.INFORMATION,
        parameter_name="scada_quality",
        unit="%",
        normal_min=98.0,
        normal_max=100.0,
        restricted_min=90.0,
        restricted_max=100.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="供水SCADA系统规范",
            extract_value="数据可用率≥98%"
        ),
        normal_strategy="S3",
        restricted_strategy="S2",
        prohibited_action="S0+人工监测",
        update_frequency=10.0,
        max_latency=2.0
    ))

    # 组织硬兜底
    odd.add_organization(OrganizationBoundary(
        boundary_id="ORG_URB_001",
        name="调度员接管响应",
        description="24小时值班调度员响应",
        boundary_type=HardBoundaryType.ORGANIZATION,
        parameter_name="operator_response",
        unit="min",
        normal_max=3.0,
        normal_min=0.0,
        restricted_max=10.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.OPERATION_RULE,
            document_name="供水调度中心值班制度",
            extract_value="告警响应≤3分钟"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+启动应急",
        response_sla=180.0,
        role_required="值班调度员",
        drill_frequency="每周1次"
    ))

    return odd


def create_flood_control_mvp_odd() -> MVPODDDefinition:
    """创建防洪调度MVP ODD"""
    odd = MVPODDDefinition(
        odd_id="MVP_ODD_FLOOD_001",
        name="防洪调度MVP ODD",
        description="防洪调度决策支持系统的最小可行运行设计域",
        applicable_system="XX流域防洪调度系统",
        applicable_scope="汛期防洪调度"
    )

    odd.excluded_scenarios = [
        "超标准洪水（超过校核洪水）",
        "大坝安全事故",
        "预报系统完全失效",
        "通信全部中断"
    ]

    # 规范硬约束 - 水库水位
    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_FLD_001",
        name="汛限水位",
        description="汛期水库最高运行水位",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="flood_limit_level",
        unit="m",
        normal_max=145.0,
        normal_min=125.0,
        restricted_max=148.0,   # 允许超蓄
        restricted_min=123.0,
        source=SourceReference(
            source_type=SourceType.REGULATION,
            document_name="XX水库汛期调度规程",
            document_id="批准文号XXX",
            section="第4条",
            extract_value="汛限水位145.0m"
        ),
        normal_strategy="S2",  # 防洪最高S2
        restricted_strategy="S1",
        prohibited_action="S0+防指接管",
        regulation_type="政府批准",
        mandatory_level="强制性",
        legal_consequence="违反防洪法规"
    ))

    # 下游安全流量
    odd.add_regulatory(RegulatoryBoundary(
        boundary_id="REG_FLD_002",
        name="下游安全泄量",
        description="下游河道安全行洪能力",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="safe_discharge",
        unit="m³/s",
        normal_max=3000.0,
        normal_min=0.0,
        restricted_max=4000.0,  # 超保证流量
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.DESIGN_SPEC,
            document_name="XX河防洪规划",
            extract_value="安全泄量3000m³/s"
        ),
        normal_strategy="S2",
        restricted_strategy="S1",
        prohibited_action="S0+启动蓄滞洪区"
    ))

    # 执行硬能力 - 泄洪设施
    odd.add_execution(ExecutionBoundary(
        boundary_id="EXE_FLD_001",
        name="泄洪能力",
        description="泄洪设施可用泄洪能力",
        boundary_type=HardBoundaryType.EXECUTION,
        parameter_name="spillway_capacity",
        unit="%",
        normal_min=100.0,
        normal_max=100.0,
        restricted_min=80.0,
        restricted_max=100.0,
        source=SourceReference(
            source_type=SourceType.TEST_REPORT,
            document_name="泄洪设施检测报告",
            extract_value="泄洪能力合格"
        ),
        normal_strategy="S2",
        restricted_strategy="S1",
        prohibited_action="S0+应急抢修"
    ))

    # 信息硬条件 - 预报精度
    odd.add_information(InformationBoundary(
        boundary_id="INF_FLD_001",
        name="洪水预报精度",
        description="洪峰流量预报相对误差",
        boundary_type=HardBoundaryType.INFORMATION,
        parameter_name="forecast_error",
        unit="%",
        normal_max=20.0,
        normal_min=0.0,
        restricted_max=30.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="洪水预报方案",
            extract_value="预报合格率≥80%"
        ),
        normal_strategy="S2",
        restricted_strategy="S1",
        prohibited_action="S0+保守调度",
        measurement_type="洪水预报"
    ))

    # 通信可靠性
    odd.add_information(InformationBoundary(
        boundary_id="INF_FLD_002",
        name="水情通信可靠性",
        description="水情信息传输可靠性",
        boundary_type=HardBoundaryType.INFORMATION,
        parameter_name="comm_reliability",
        unit="%",
        normal_min=99.0,
        normal_max=100.0,
        restricted_min=95.0,
        restricted_max=100.0,
        source=SourceReference(
            source_type=SourceType.SYSTEM_SPEC,
            document_name="水情自动测报系统规范",
            extract_value="通信可靠性≥99%"
        ),
        normal_strategy="S2",
        restricted_strategy="S1",
        prohibited_action="S0+人工报汛"
    ))

    # 组织硬兜底 - 防指响应
    odd.add_organization(OrganizationBoundary(
        boundary_id="ORG_FLD_001",
        name="防指会商响应",
        description="防汛指挥部会商响应时间",
        boundary_type=HardBoundaryType.ORGANIZATION,
        parameter_name="command_response",
        unit="min",
        normal_max=30.0,
        normal_min=0.0,
        restricted_max=60.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.EMERGENCY_PLAN,
            document_name="XX流域防汛应急预案",
            section="5.2",
            extract_value="Ⅲ级响应30分钟内会商"
        ),
        normal_strategy="S2",
        restricted_strategy="S1",
        prohibited_action="S0+启动应急指挥",
        role_required="防指总指挥",
        response_sla=1800.0,
        takeover_procedure="1.发布预警 2.会商研判 3.制定方案 4.下达指令",
        drill_frequency="汛前演练"
    ))

    # 现场处置能力
    odd.add_organization(OrganizationBoundary(
        boundary_id="ORG_FLD_002",
        name="现场处置响应",
        description="现场抢险队伍响应时间",
        boundary_type=HardBoundaryType.ORGANIZATION,
        parameter_name="field_response",
        unit="min",
        normal_max=60.0,
        normal_min=0.0,
        restricted_max=120.0,
        restricted_min=0.0,
        source=SourceReference(
            source_type=SourceType.EMERGENCY_PLAN,
            document_name="防汛抢险预案",
            extract_value="抢险队伍1小时内到达"
        ),
        normal_strategy="S2",
        restricted_strategy="S1",
        prohibited_action="S0+请求支援",
        role_required="抢险队伍",
        response_sla=3600.0
    ))

    return odd


# ============================================================================
# 验收检查器
# ============================================================================

class MVPODDAcceptanceChecker:
    """
    MVP ODD验收检查器

    确保ODD"能验收、能定责、能复用"
    """

    def __init__(self):
        self.check_results: List[Dict] = []

    def check(self, odd: MVPODDDefinition) -> Dict[str, Any]:
        """
        执行验收检查

        Returns:
            检查结果
        """
        result = {
            'odd_id': odd.odd_id,
            'timestamp': datetime.now().isoformat(),
            'passed': True,
            'checks': [],
            'summary': {}
        }

        # 检查1: 四条硬边界完整性
        completeness = self._check_completeness(odd)
        result['checks'].append(completeness)
        if not completeness['passed']:
            result['passed'] = False

        # 检查2: 来源追溯
        traceability = self._check_traceability(odd)
        result['checks'].append(traceability)
        if not traceability['passed']:
            result['passed'] = False

        # 检查3: 策略映射
        mapping = self._check_strategy_mapping(odd)
        result['checks'].append(mapping)
        if not mapping['passed']:
            result['passed'] = False

        # 检查4: 验证状态
        verification = self._check_verification(odd)
        result['checks'].append(verification)
        # 验证状态不影响通过，只是警告

        # 汇总
        result['summary'] = {
            'total_checks': len(result['checks']),
            'passed_checks': sum(1 for c in result['checks'] if c['passed']),
            'total_boundaries': len(odd.get_all_boundaries()),
            'acceptance_ready': result['passed']
        }

        return result

    def _check_completeness(self, odd: MVPODDDefinition) -> Dict:
        """检查四条硬边界完整性"""
        check = {
            'name': "四条硬边界完整性",
            'passed': True,
            'details': []
        }

        if not odd.regulatory_boundaries:
            check['passed'] = False
            check['details'].append("缺少规范硬约束边界")
        else:
            check['details'].append(f"规范硬约束: {len(odd.regulatory_boundaries)}项")

        if not odd.execution_boundaries:
            check['passed'] = False
            check['details'].append("缺少执行硬能力边界")
        else:
            check['details'].append(f"执行硬能力: {len(odd.execution_boundaries)}项")

        if not odd.information_boundaries:
            check['passed'] = False
            check['details'].append("缺少信息硬条件边界")
        else:
            check['details'].append(f"信息硬条件: {len(odd.information_boundaries)}项")

        if not odd.organization_boundaries:
            check['passed'] = False
            check['details'].append("缺少组织硬兜底边界")
        else:
            check['details'].append(f"组织硬兜底: {len(odd.organization_boundaries)}项")

        return check

    def _check_traceability(self, odd: MVPODDDefinition) -> Dict:
        """检查来源追溯"""
        check = {
            'name': "来源追溯完整性",
            'passed': True,
            'details': []
        }

        all_boundaries = odd.get_all_boundaries()
        missing_source = []

        for b in all_boundaries:
            if not b.source:
                missing_source.append(b.name)

        if missing_source:
            check['passed'] = False
            check['details'].append(f"以下边界缺少来源: {missing_source}")
        else:
            check['details'].append(f"全部{len(all_boundaries)}项边界均有来源追溯")

        return check

    def _check_strategy_mapping(self, odd: MVPODDDefinition) -> Dict:
        """检查策略映射"""
        check = {
            'name': "策略映射完整性",
            'passed': True,
            'details': []
        }

        all_boundaries = odd.get_all_boundaries()
        missing_mapping = []

        for b in all_boundaries:
            if not b.normal_strategy or not b.restricted_strategy or not b.prohibited_action:
                missing_mapping.append(b.name)

        if missing_mapping:
            check['passed'] = False
            check['details'].append(f"以下边界策略映射不完整: {missing_mapping}")
        else:
            check['details'].append(f"全部{len(all_boundaries)}项边界均有策略映射")

        return check

    def _check_verification(self, odd: MVPODDDefinition) -> Dict:
        """检查验证状态"""
        check = {
            'name': "验证状态",
            'passed': True,  # 不影响通过
            'details': []
        }

        all_boundaries = odd.get_all_boundaries()
        unverified = [b.name for b in all_boundaries if not b.is_verified]

        if unverified:
            check['details'].append(f"以下边界待验证: {unverified}")
        else:
            check['details'].append(f"全部{len(all_boundaries)}项边界已验证")

        verified_count = len(all_boundaries) - len(unverified)
        check['details'].append(f"验证率: {100*verified_count/len(all_boundaries):.0f}%")

        return check


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 基础类型
    'HardBoundaryType', 'BoundaryLevel', 'SourceType', 'SourceReference',
    # 硬边界
    'HardBoundary', 'RegulatoryBoundary', 'ExecutionBoundary',
    'InformationBoundary', 'OrganizationBoundary',
    # MVP ODD
    'MVPODDStatus', 'MVPODDDefinition',
    # 扩展
    'SoftBoundaryCategory', 'SoftBoundary', 'ExtendedODD',
    # 工厂函数
    'create_reservoir_mvp_odd', 'create_irrigation_mvp_odd',
    'create_urban_supply_mvp_odd', 'create_flood_control_mvp_odd',
    # 验收
    'MVPODDAcceptanceChecker',
]
