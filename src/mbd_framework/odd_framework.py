# -*- coding: utf-8 -*-
"""
ODD Framework - 运行设计域框架
Operational Design Domain Framework

定义系统运行的边界条件、约束和监控机制
基于ISO/PAS 21448 SOTIF和ISO 34503标准
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Tuple, Set
from datetime import datetime
import json


class ODDCategory(Enum):
    """ODD类别"""
    ENVIRONMENTAL = auto()      # 环境条件
    OPERATIONAL = auto()        # 运行条件
    INFRASTRUCTURE = auto()     # 基础设施
    CONNECTIVITY = auto()       # 连接性
    ZONES = auto()              # 区域/地理
    TEMPORAL = auto()           # 时间条件


class ConditionType(Enum):
    """条件类型"""
    STATIC = auto()             # 静态条件 - 不随时间变化
    DYNAMIC = auto()            # 动态条件 - 随时间变化
    PROBABILISTIC = auto()      # 概率条件 - 有一定概率发生


class BoundaryType(Enum):
    """边界类型"""
    HARD = auto()               # 硬边界 - 绝对不能超越
    SOFT = auto()               # 软边界 - 可临时超越
    ADVISORY = auto()           # 建议边界 - 超越需警告


class ViolationSeverity(Enum):
    """违规严重程度"""
    INFO = auto()               # 信息
    WARNING = auto()            # 警告
    MINOR = auto()              # 轻微
    MAJOR = auto()              # 重大
    CRITICAL = auto()           # 严重
    HAZARDOUS = auto()          # 危险


@dataclass
class OperatingCondition:
    """运行条件"""
    condition_id: str                       # 条件ID
    name: str                               # 名称
    description: str                        # 描述
    category: ODDCategory                   # 类别
    condition_type: ConditionType           # 条件类型

    # 参数范围
    parameter_name: str = ""                # 参数名
    unit: str = ""                          # 单位
    min_value: Optional[float] = None       # 最小值
    max_value: Optional[float] = None       # 最大值
    nominal_value: Optional[float] = None   # 标称值
    tolerance: Optional[float] = None       # 容差

    # 离散条件
    allowed_values: List[Any] = field(default_factory=list)  # 允许的离散值
    forbidden_values: List[Any] = field(default_factory=list)  # 禁止的离散值

    # 概率参数
    probability: float = 1.0                # 发生概率
    confidence_level: float = 0.95          # 置信水平

    # 元数据
    source: str = ""                        # 来源
    rationale: str = ""                     # 原理
    verification_method: str = ""           # 验证方法

    def check_value(self, value: Any) -> Tuple[bool, str]:
        """检查值是否在条件范围内"""
        if self.allowed_values:
            if value in self.allowed_values:
                return True, "Value is in allowed set"
            return False, f"Value {value} not in allowed values {self.allowed_values}"

        if self.forbidden_values and value in self.forbidden_values:
            return False, f"Value {value} is forbidden"

        if self.min_value is not None and value < self.min_value:
            return False, f"Value {value} below minimum {self.min_value}"

        if self.max_value is not None and value > self.max_value:
            return False, f"Value {value} above maximum {self.max_value}"

        return True, "Value within range"

    def get_margin(self, value: float) -> Optional[float]:
        """获取值到边界的裕度"""
        if self.min_value is None and self.max_value is None:
            return None

        margins = []
        if self.min_value is not None:
            margins.append(value - self.min_value)
        if self.max_value is not None:
            margins.append(self.max_value - value)

        return min(margins) if margins else None


@dataclass
class ODDBoundary:
    """ODD边界定义"""
    boundary_id: str                        # 边界ID
    name: str                               # 名称
    description: str                        # 描述
    boundary_type: BoundaryType             # 边界类型
    conditions: List[OperatingCondition] = field(default_factory=list)  # 相关条件

    # 违规处理
    violation_severity: ViolationSeverity = ViolationSeverity.WARNING
    response_action: str = ""               # 响应动作
    recovery_procedure: str = ""            # 恢复程序

    # 时间参数
    max_violation_duration: float = 0.0     # 最大违规持续时间(秒)
    cooldown_period: float = 0.0            # 冷却期(秒)

    # 关联
    related_boundaries: List[str] = field(default_factory=list)
    degradation_modes: List[str] = field(default_factory=list)

    def add_condition(self, condition: OperatingCondition):
        """添加条件"""
        self.conditions.append(condition)

    def check_all_conditions(self, values: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """检查所有条件"""
        all_passed = True
        messages = []

        for condition in self.conditions:
            if condition.parameter_name in values:
                passed, msg = condition.check_value(values[condition.parameter_name])
                if not passed:
                    all_passed = False
                    messages.append(f"{condition.name}: {msg}")

        return all_passed, messages


@dataclass
class ODDViolation:
    """ODD违规记录"""
    violation_id: str
    boundary_id: str
    condition_id: str
    timestamp: datetime
    severity: ViolationSeverity
    actual_value: Any
    expected_range: str
    duration: float = 0.0
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None
    response_taken: str = ""


class ODDDefinition:
    """ODD定义 - 完整的运行设计域"""

    def __init__(self, odd_id: str, name: str, description: str = ""):
        self.odd_id = odd_id
        self.name = name
        self.description = description
        self.version = "1.0"
        self.created_date = datetime.now()
        self.modified_date = datetime.now()

        # ODD组件
        self.conditions: Dict[str, OperatingCondition] = {}
        self.boundaries: Dict[str, ODDBoundary] = {}
        self.scenarios: Dict[str, 'ODDScenario'] = {}

        # 层次结构
        self.parent_odd: Optional[str] = None
        self.child_odds: List[str] = []

        # 关联
        self.requirements: List[str] = []
        self.safety_goals: List[str] = []

    def add_condition(self, condition: OperatingCondition) -> None:
        """添加运行条件"""
        self.conditions[condition.condition_id] = condition
        self.modified_date = datetime.now()

    def add_boundary(self, boundary: ODDBoundary) -> None:
        """添加边界"""
        self.boundaries[boundary.boundary_id] = boundary
        self.modified_date = datetime.now()

    def get_conditions_by_category(self, category: ODDCategory) -> List[OperatingCondition]:
        """按类别获取条件"""
        return [c for c in self.conditions.values() if c.category == category]

    def validate_operating_point(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """验证运行点是否在ODD内"""
        result = {
            'odd_id': self.odd_id,
            'timestamp': datetime.now().isoformat(),
            'in_odd': True,
            'boundary_violations': [],
            'condition_violations': [],
            'warnings': [],
            'margins': {}
        }

        # 检查所有边界
        for boundary_id, boundary in self.boundaries.items():
            passed, messages = boundary.check_all_conditions(values)
            if not passed:
                if boundary.boundary_type == BoundaryType.HARD:
                    result['in_odd'] = False
                    result['boundary_violations'].append({
                        'boundary_id': boundary_id,
                        'messages': messages,
                        'severity': boundary.violation_severity.name
                    })
                elif boundary.boundary_type == BoundaryType.SOFT:
                    result['warnings'].append({
                        'boundary_id': boundary_id,
                        'messages': messages,
                        'type': 'soft_boundary'
                    })
                else:
                    result['warnings'].append({
                        'boundary_id': boundary_id,
                        'messages': messages,
                        'type': 'advisory'
                    })

        # 计算裕度
        for cond_id, condition in self.conditions.items():
            if condition.parameter_name in values:
                margin = condition.get_margin(values[condition.parameter_name])
                if margin is not None:
                    result['margins'][cond_id] = margin

        return result

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'odd_id': self.odd_id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'conditions': {k: {
                'name': v.name,
                'category': v.category.name,
                'min': v.min_value,
                'max': v.max_value
            } for k, v in self.conditions.items()},
            'boundaries': {k: {
                'name': v.name,
                'type': v.boundary_type.name,
                'severity': v.violation_severity.name
            } for k, v in self.boundaries.items()}
        }


@dataclass
class ODDScenario:
    """ODD场景 - 特定运行场景"""
    scenario_id: str
    name: str
    description: str
    conditions: Dict[str, Any] = field(default_factory=dict)  # 条件值
    duration: float = 0.0                   # 场景持续时间
    probability: float = 0.0                # 发生概率
    criticality: str = "NORMAL"             # 关键性: LOW/NORMAL/HIGH/CRITICAL


class ODDMonitor:
    """ODD监控器 - 实时监控系统是否在ODD内运行"""

    def __init__(self, odd: ODDDefinition):
        self.odd = odd
        self.monitoring = False
        self.violations: List[ODDViolation] = []
        self.violation_handlers: Dict[ViolationSeverity, List[Callable]] = {
            sev: [] for sev in ViolationSeverity
        }
        self.current_values: Dict[str, Any] = {}
        self.last_check_time: Optional[datetime] = None
        self.violation_count = 0
        self._active_violations: Dict[str, ODDViolation] = {}

    def start_monitoring(self):
        """开始监控"""
        self.monitoring = True

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False

    def register_handler(self, severity: ViolationSeverity,
                        handler: Callable[[ODDViolation], None]):
        """注册违规处理器"""
        self.violation_handlers[severity].append(handler)

    def update(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """更新监控状态"""
        if not self.monitoring:
            return {'status': 'not_monitoring'}

        self.current_values = values
        self.last_check_time = datetime.now()

        # 验证运行点
        result = self.odd.validate_operating_point(values)

        # 处理违规
        if not result['in_odd']:
            for violation_info in result['boundary_violations']:
                violation = self._create_violation(violation_info)
                self._handle_violation(violation)

        # 检查之前的违规是否已解决
        self._check_resolved_violations(values)

        return result

    def _create_violation(self, violation_info: Dict) -> ODDViolation:
        """创建违规记录"""
        self.violation_count += 1
        violation = ODDViolation(
            violation_id=f"V{self.violation_count:06d}",
            boundary_id=violation_info['boundary_id'],
            condition_id="",
            timestamp=datetime.now(),
            severity=ViolationSeverity[violation_info['severity']],
            actual_value=self.current_values,
            expected_range=str(violation_info['messages'])
        )
        self.violations.append(violation)
        self._active_violations[violation.violation_id] = violation
        return violation

    def _handle_violation(self, violation: ODDViolation):
        """处理违规"""
        handlers = self.violation_handlers[violation.severity]
        for handler in handlers:
            try:
                handler(violation)
            except Exception as e:
                print(f"Error in violation handler: {e}")

    def _check_resolved_violations(self, values: Dict[str, Any]):
        """检查已解决的违规"""
        resolved_ids = []
        for vid, violation in self._active_violations.items():
            boundary = self.odd.boundaries.get(violation.boundary_id)
            if boundary:
                passed, _ = boundary.check_all_conditions(values)
                if passed:
                    violation.resolved = True
                    violation.resolution_timestamp = datetime.now()
                    resolved_ids.append(vid)

        for vid in resolved_ids:
            del self._active_violations[vid]

    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            'monitoring': self.monitoring,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'total_violations': len(self.violations),
            'active_violations': len(self._active_violations),
            'current_values': self.current_values
        }


class ODDValidator:
    """ODD验证器 - 验证ODD定义的完整性和一致性"""

    def __init__(self):
        self.validation_results: List[Dict] = []

    def validate_completeness(self, odd: ODDDefinition) -> Dict[str, Any]:
        """验证ODD完整性"""
        result = {
            'odd_id': odd.odd_id,
            'timestamp': datetime.now().isoformat(),
            'is_complete': True,
            'missing_categories': [],
            'warnings': [],
            'coverage': {}
        }

        # 检查是否覆盖所有类别
        covered_categories = set(c.category for c in odd.conditions.values())
        all_categories = set(ODDCategory)
        missing = all_categories - covered_categories

        if missing:
            result['missing_categories'] = [c.name for c in missing]
            result['warnings'].append(
                f"ODD does not cover categories: {result['missing_categories']}"
            )

        # 计算覆盖率
        for category in ODDCategory:
            conditions = odd.get_conditions_by_category(category)
            result['coverage'][category.name] = len(conditions)

        # 检查边界定义
        if not odd.boundaries:
            result['is_complete'] = False
            result['warnings'].append("No boundaries defined")

        self.validation_results.append(result)
        return result

    def validate_consistency(self, odd: ODDDefinition) -> Dict[str, Any]:
        """验证ODD一致性"""
        result = {
            'odd_id': odd.odd_id,
            'timestamp': datetime.now().isoformat(),
            'is_consistent': True,
            'conflicts': [],
            'warnings': []
        }

        # 检查条件范围是否有冲突
        for cond_id, condition in odd.conditions.items():
            if condition.min_value is not None and condition.max_value is not None:
                if condition.min_value > condition.max_value:
                    result['is_consistent'] = False
                    result['conflicts'].append(
                        f"Condition {cond_id}: min > max ({condition.min_value} > {condition.max_value})"
                    )

        # 检查边界条件引用
        for boundary in odd.boundaries.values():
            for condition in boundary.conditions:
                if condition.condition_id not in odd.conditions:
                    result['warnings'].append(
                        f"Boundary {boundary.boundary_id} references unknown condition {condition.condition_id}"
                    )

        self.validation_results.append(result)
        return result


class ODDViolationHandler:
    """ODD违规处理器 - 处理违规的默认策略"""

    def __init__(self):
        self.response_strategies: Dict[ViolationSeverity, str] = {
            ViolationSeverity.INFO: "LOG",
            ViolationSeverity.WARNING: "LOG_AND_ALERT",
            ViolationSeverity.MINOR: "DEGRADE_LEVEL_1",
            ViolationSeverity.MAJOR: "DEGRADE_LEVEL_2",
            ViolationSeverity.CRITICAL: "SAFE_STATE",
            ViolationSeverity.HAZARDOUS: "EMERGENCY_STOP"
        }

    def handle(self, violation: ODDViolation) -> str:
        """处理违规"""
        strategy = self.response_strategies.get(
            violation.severity,
            "LOG"
        )
        violation.response_taken = strategy
        return strategy


# 预定义的水利系统ODD模板
def create_hydraulic_system_odd() -> ODDDefinition:
    """创建水利系统ODD模板"""
    odd = ODDDefinition(
        odd_id="ODD_HYDRAULIC_001",
        name="水利枢纽智能控制ODD",
        description="水利枢纽智能控制系统的运行设计域定义"
    )

    # 环境条件
    odd.add_condition(OperatingCondition(
        condition_id="ENV_TEMP",
        name="环境温度",
        description="系统运行的环境温度范围",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="ambient_temperature",
        unit="°C",
        min_value=-20.0,
        max_value=50.0,
        nominal_value=25.0
    ))

    odd.add_condition(OperatingCondition(
        condition_id="ENV_HUMIDITY",
        name="环境湿度",
        description="系统运行的环境湿度范围",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="humidity",
        unit="%",
        min_value=10.0,
        max_value=95.0
    ))

    # 运行条件 - 水力参数
    odd.add_condition(OperatingCondition(
        condition_id="OP_PRESSURE",
        name="系统压力",
        description="水力系统最大运行压力",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="system_pressure",
        unit="MPa",
        min_value=0.0,
        max_value=10.0,
        nominal_value=2.5
    ))

    odd.add_condition(OperatingCondition(
        condition_id="OP_FLOW",
        name="系统流量",
        description="系统流量范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="flow_rate",
        unit="m³/s",
        min_value=0.0,
        max_value=100.0
    ))

    odd.add_condition(OperatingCondition(
        condition_id="OP_LEVEL",
        name="水位",
        description="水库/水池水位范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="water_level",
        unit="m",
        min_value=0.0,
        max_value=200.0
    ))

    # 基础设施条件
    odd.add_condition(OperatingCondition(
        condition_id="INFRA_POWER",
        name="电力供应",
        description="电力供应状态",
        category=ODDCategory.INFRASTRUCTURE,
        condition_type=ConditionType.STATIC,
        parameter_name="power_supply",
        allowed_values=["NORMAL", "BACKUP", "UPS"]
    ))

    # 连接性条件
    odd.add_condition(OperatingCondition(
        condition_id="CONN_SCADA",
        name="SCADA连接",
        description="SCADA系统连接状态",
        category=ODDCategory.CONNECTIVITY,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="scada_connected",
        allowed_values=[True, False]
    ))

    # 添加边界
    pressure_boundary = ODDBoundary(
        boundary_id="BOUND_PRESSURE",
        name="压力安全边界",
        description="系统压力不得超过安全阈值",
        boundary_type=BoundaryType.HARD,
        violation_severity=ViolationSeverity.CRITICAL,
        response_action="EMERGENCY_RELIEF",
        recovery_procedure="检查压力源,逐步恢复"
    )
    pressure_boundary.add_condition(odd.conditions["OP_PRESSURE"])
    odd.add_boundary(pressure_boundary)

    flow_boundary = ODDBoundary(
        boundary_id="BOUND_FLOW",
        name="流量边界",
        description="系统流量边界",
        boundary_type=BoundaryType.SOFT,
        violation_severity=ViolationSeverity.WARNING,
        response_action="REDUCE_FLOW",
        max_violation_duration=60.0
    )
    flow_boundary.add_condition(odd.conditions["OP_FLOW"])
    odd.add_boundary(flow_boundary)

    return odd


def create_multi_energy_odd() -> ODDDefinition:
    """创建多能互补系统ODD模板"""
    odd = ODDDefinition(
        odd_id="ODD_MULTI_ENERGY_001",
        name="多能互补系统ODD",
        description="水风光储多能互补系统的运行设计域定义"
    )

    # 电网频率条件
    odd.add_condition(OperatingCondition(
        condition_id="GRID_FREQ",
        name="电网频率",
        description="电网频率允许偏差范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="grid_frequency",
        unit="Hz",
        min_value=49.5,
        max_value=50.5,
        nominal_value=50.0
    ))

    # 风速条件
    odd.add_condition(OperatingCondition(
        condition_id="ENV_WIND",
        name="风速",
        description="风力发电运行风速范围",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="wind_speed",
        unit="m/s",
        min_value=3.0,  # 切入风速
        max_value=25.0  # 切出风速
    ))

    # 光照条件
    odd.add_condition(OperatingCondition(
        condition_id="ENV_IRRADIANCE",
        name="太阳辐照度",
        description="光伏发电辐照度范围",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="solar_irradiance",
        unit="W/m²",
        min_value=0.0,
        max_value=1200.0
    ))

    # 储能SOC条件
    odd.add_condition(OperatingCondition(
        condition_id="OP_SOC_SC",
        name="超级电容SOC",
        description="超级电容荷电状态范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="sc_soc",
        unit="%",
        min_value=20.0,
        max_value=95.0
    ))

    odd.add_condition(OperatingCondition(
        condition_id="OP_SOC_BESS",
        name="锂电池SOC",
        description="锂电池荷电状态范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="bess_soc",
        unit="%",
        min_value=10.0,
        max_value=90.0
    ))

    odd.add_condition(OperatingCondition(
        condition_id="OP_PSH_LEVEL",
        name="抽水蓄能水位",
        description="上库水位范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="psh_upper_level",
        unit="%",
        min_value=10.0,
        max_value=95.0
    ))

    # 功率平衡条件
    odd.add_condition(OperatingCondition(
        condition_id="OP_POWER_BALANCE",
        name="功率平衡偏差",
        description="发电与负荷功率平衡偏差",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="power_imbalance",
        unit="MW",
        min_value=-100.0,
        max_value=100.0
    ))

    # 添加关键边界
    freq_boundary = ODDBoundary(
        boundary_id="BOUND_FREQ",
        name="频率安全边界",
        description="电网频率必须维持在安全范围内",
        boundary_type=BoundaryType.HARD,
        violation_severity=ViolationSeverity.CRITICAL,
        response_action="ACTIVATE_FREQUENCY_SUPPORT",
        recovery_procedure="启动储能快速响应,调整发电出力"
    )
    freq_boundary.add_condition(odd.conditions["GRID_FREQ"])
    odd.add_boundary(freq_boundary)

    soc_boundary = ODDBoundary(
        boundary_id="BOUND_SOC",
        name="储能SOC边界",
        description="储能系统SOC维持边界",
        boundary_type=BoundaryType.SOFT,
        violation_severity=ViolationSeverity.WARNING,
        response_action="ADJUST_CHARGING_STRATEGY",
        max_violation_duration=300.0
    )
    soc_boundary.add_condition(odd.conditions["OP_SOC_SC"])
    soc_boundary.add_condition(odd.conditions["OP_SOC_BESS"])
    odd.add_boundary(soc_boundary)

    return odd
