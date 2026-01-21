# -*- coding: utf-8 -*-
"""
Functional Safety - 功能安全和降级策略模块
Functional Safety and Degradation Strategy Module

基于ISO 26262和IEC 61508标准实现功能安全框架
包含ASIL等级定义、安全目标、降级状态机和故障处理
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Set, Tuple
from datetime import datetime
import threading
import copy


class SafetyLevel(Enum):
    """安全等级 - 基于IEC 61508"""
    SIL_0 = 0       # 无安全要求
    SIL_1 = 1       # 安全完整性等级1
    SIL_2 = 2       # 安全完整性等级2
    SIL_3 = 3       # 安全完整性等级3
    SIL_4 = 4       # 安全完整性等级4 (最高)


class ASILLevel(Enum):
    """ASIL等级 - 基于ISO 26262"""
    QM = 0          # 质量管理 (无安全要求)
    ASIL_A = 1      # 最低安全等级
    ASIL_B = 2
    ASIL_C = 3
    ASIL_D = 4      # 最高安全等级


class FaultCategory(Enum):
    """故障类别"""
    TRANSIENT = auto()          # 瞬态故障
    INTERMITTENT = auto()       # 间歇故障
    PERMANENT = auto()          # 永久故障


class FaultSeverity(Enum):
    """故障严重度"""
    NEGLIGIBLE = auto()         # 可忽略
    MARGINAL = auto()           # 边缘
    CRITICAL = auto()           # 严重
    CATASTROPHIC = auto()       # 灾难性


class FaultType(Enum):
    """故障类型"""
    SENSOR_FAULT = auto()           # 传感器故障
    ACTUATOR_FAULT = auto()         # 执行器故障
    CONTROLLER_FAULT = auto()       # 控制器故障
    COMMUNICATION_FAULT = auto()    # 通信故障
    POWER_FAULT = auto()            # 电源故障
    SOFTWARE_FAULT = auto()         # 软件故障
    HARDWARE_FAULT = auto()         # 硬件故障
    HUMAN_ERROR = auto()            # 人为错误


class DegradationLevel(Enum):
    """降级等级"""
    NORMAL = 0              # 正常运行
    DEGRADED_L1 = 1         # 一级降级 - 轻微功能受限
    DEGRADED_L2 = 2         # 二级降级 - 中度功能受限
    DEGRADED_L3 = 3         # 三级降级 - 严重功能受限
    LIMP_HOME = 4           # 跛行回家模式
    SAFE_STATE = 5          # 安全状态
    EMERGENCY_STOP = 6      # 紧急停机


class SystemState(Enum):
    """系统状态"""
    INITIALIZING = auto()       # 初始化中
    OPERATIONAL = auto()        # 运行中
    DEGRADED = auto()           # 降级运行
    FAULT_DETECTED = auto()     # 检测到故障
    TRANSITIONING = auto()      # 状态转换中
    SAFE_STATE = auto()         # 安全状态
    SHUTDOWN = auto()           # 停机


@dataclass
class SafetyGoal:
    """安全目标"""
    goal_id: str                            # 目标ID
    name: str                               # 名称
    description: str                        # 描述
    asil_level: ASILLevel                   # ASIL等级
    sil_level: SafetyLevel                  # SIL等级

    # 危害分析
    hazard_id: str = ""                     # 关联危害ID
    hazard_description: str = ""            # 危害描述
    exposure: str = "E2"                    # 暴露度: E0-E4
    controllability: str = "C2"             # 可控性: C0-C3
    severity: str = "S2"                    # 严重度: S0-S3

    # 安全状态
    safe_state: str = ""                    # 安全状态描述
    fault_tolerant_time: float = 0.0        # 容错时间(秒)
    max_response_time: float = 0.0          # 最大响应时间(秒)

    # 关联
    requirements: List[str] = field(default_factory=list)
    verification_methods: List[str] = field(default_factory=list)

    def calculate_asil(self) -> ASILLevel:
        """根据S/E/C计算ASIL等级"""
        # 简化的ASIL计算矩阵
        s_val = int(self.severity[1]) if self.severity else 0
        e_val = int(self.exposure[1]) if self.exposure else 0
        c_val = int(self.controllability[1]) if self.controllability else 0

        score = s_val + e_val + c_val
        if score <= 3:
            return ASILLevel.QM
        elif score <= 5:
            return ASILLevel.ASIL_A
        elif score <= 7:
            return ASILLevel.ASIL_B
        elif score <= 9:
            return ASILLevel.ASIL_C
        else:
            return ASILLevel.ASIL_D


@dataclass
class SafetyRequirement:
    """安全需求"""
    req_id: str                             # 需求ID
    name: str                               # 名称
    description: str                        # 描述
    safety_goal_id: str                     # 关联安全目标
    asil_level: ASILLevel                   # ASIL等级

    # 需求分类
    category: str = "FUNCTIONAL"            # FUNCTIONAL/TECHNICAL/SW/HW
    allocation: str = ""                    # 分配到的组件

    # 验证
    verification_status: str = "OPEN"       # OPEN/IN_PROGRESS/VERIFIED/FAILED
    verification_method: str = "TEST"       # TEST/ANALYSIS/INSPECTION
    test_cases: List[str] = field(default_factory=list)

    # 追溯
    parent_req: Optional[str] = None
    derived_reqs: List[str] = field(default_factory=list)


@dataclass
class Fault:
    """故障定义"""
    fault_id: str                           # 故障ID
    name: str                               # 名称
    description: str                        # 描述
    fault_type: FaultType                   # 故障类型
    category: FaultCategory                 # 故障类别
    severity: FaultSeverity                 # 严重度

    # 检测
    detection_method: str = ""              # 检测方法
    detection_time: float = 0.0             # 检测时间(秒)
    detection_coverage: float = 0.0         # 检测覆盖率(0-1)

    # 响应
    required_action: str = ""               # 所需动作
    max_response_time: float = 0.0          # 最大响应时间

    # 统计
    failure_rate: float = 0.0               # 失效率(FIT)
    mtbf: float = 0.0                       # 平均故障间隔时间(小时)


@dataclass
class DegradationStrategy:
    """降级策略"""
    strategy_id: str                        # 策略ID
    name: str                               # 名称
    description: str                        # 描述
    current_level: DegradationLevel         # 当前降级等级
    target_level: DegradationLevel          # 目标降级等级

    # 触发条件
    trigger_faults: List[str] = field(default_factory=list)  # 触发故障列表
    trigger_conditions: Dict[str, Any] = field(default_factory=dict)  # 触发条件

    # 动作
    actions: List[str] = field(default_factory=list)  # 执行动作
    disabled_features: List[str] = field(default_factory=list)  # 禁用功能
    enabled_features: List[str] = field(default_factory=list)  # 启用功能
    parameter_overrides: Dict[str, Any] = field(default_factory=dict)  # 参数覆盖

    # 时间约束
    min_hold_time: float = 0.0              # 最小保持时间
    max_transition_time: float = 0.0        # 最大转换时间

    # 恢复条件
    recovery_conditions: Dict[str, Any] = field(default_factory=dict)
    recovery_actions: List[str] = field(default_factory=list)


class DegradationStateMachine:
    """降级状态机 - 管理系统降级状态转换"""

    def __init__(self, system_id: str):
        self.system_id = system_id
        self.current_level = DegradationLevel.NORMAL
        self.current_state = SystemState.INITIALIZING
        self.strategies: Dict[str, DegradationStrategy] = {}
        self.state_history: List[Dict] = []
        self.active_faults: Dict[str, Fault] = {}
        self._lock = threading.Lock()

        # 转换规则: (当前等级, 目标等级) -> 是否允许
        self.allowed_transitions: Dict[Tuple[DegradationLevel, DegradationLevel], bool] = {
            # 从正常状态可以转到任何等级
            (DegradationLevel.NORMAL, DegradationLevel.DEGRADED_L1): True,
            (DegradationLevel.NORMAL, DegradationLevel.DEGRADED_L2): True,
            (DegradationLevel.NORMAL, DegradationLevel.DEGRADED_L3): True,
            (DegradationLevel.NORMAL, DegradationLevel.SAFE_STATE): True,
            (DegradationLevel.NORMAL, DegradationLevel.EMERGENCY_STOP): True,

            # 降级状态之间的转换
            (DegradationLevel.DEGRADED_L1, DegradationLevel.NORMAL): True,
            (DegradationLevel.DEGRADED_L1, DegradationLevel.DEGRADED_L2): True,
            (DegradationLevel.DEGRADED_L1, DegradationLevel.SAFE_STATE): True,

            (DegradationLevel.DEGRADED_L2, DegradationLevel.DEGRADED_L1): True,
            (DegradationLevel.DEGRADED_L2, DegradationLevel.DEGRADED_L3): True,
            (DegradationLevel.DEGRADED_L2, DegradationLevel.SAFE_STATE): True,

            (DegradationLevel.DEGRADED_L3, DegradationLevel.DEGRADED_L2): True,
            (DegradationLevel.DEGRADED_L3, DegradationLevel.LIMP_HOME): True,
            (DegradationLevel.DEGRADED_L3, DegradationLevel.SAFE_STATE): True,

            (DegradationLevel.LIMP_HOME, DegradationLevel.SAFE_STATE): True,
            (DegradationLevel.LIMP_HOME, DegradationLevel.EMERGENCY_STOP): True,

            # 安全状态
            (DegradationLevel.SAFE_STATE, DegradationLevel.NORMAL): True,
            (DegradationLevel.SAFE_STATE, DegradationLevel.DEGRADED_L1): True,

            # 紧急停机后需要手动恢复
            (DegradationLevel.EMERGENCY_STOP, DegradationLevel.SAFE_STATE): True,
        }

        # 状态转换回调
        self.transition_callbacks: List[Callable] = []

    def add_strategy(self, strategy: DegradationStrategy) -> None:
        """添加降级策略"""
        self.strategies[strategy.strategy_id] = strategy

    def register_transition_callback(self, callback: Callable) -> None:
        """注册状态转换回调"""
        self.transition_callbacks.append(callback)

    def can_transition(self, from_level: DegradationLevel,
                      to_level: DegradationLevel) -> bool:
        """检查是否可以转换"""
        return self.allowed_transitions.get((from_level, to_level), False)

    def transition_to(self, target_level: DegradationLevel,
                     reason: str = "") -> bool:
        """转换到目标降级等级"""
        with self._lock:
            if not self.can_transition(self.current_level, target_level):
                return False

            old_level = self.current_level
            self.current_level = target_level

            # 更新系统状态
            if target_level == DegradationLevel.NORMAL:
                self.current_state = SystemState.OPERATIONAL
            elif target_level in [DegradationLevel.DEGRADED_L1,
                                  DegradationLevel.DEGRADED_L2,
                                  DegradationLevel.DEGRADED_L3,
                                  DegradationLevel.LIMP_HOME]:
                self.current_state = SystemState.DEGRADED
            elif target_level == DegradationLevel.SAFE_STATE:
                self.current_state = SystemState.SAFE_STATE
            elif target_level == DegradationLevel.EMERGENCY_STOP:
                self.current_state = SystemState.SHUTDOWN

            # 记录历史
            record = {
                'timestamp': datetime.now().isoformat(),
                'from_level': old_level.name,
                'to_level': target_level.name,
                'reason': reason,
                'active_faults': list(self.active_faults.keys())
            }
            self.state_history.append(record)

            # 调用回调
            for callback in self.transition_callbacks:
                try:
                    callback(old_level, target_level, reason)
                except Exception as e:
                    print(f"Transition callback error: {e}")

            return True

    def report_fault(self, fault: Fault) -> DegradationLevel:
        """报告故障并确定降级等级"""
        with self._lock:
            self.active_faults[fault.fault_id] = fault
            self.current_state = SystemState.FAULT_DETECTED

            # 根据故障严重度确定降级等级
            target_level = self._determine_degradation_level(fault)

            # 查找匹配的降级策略
            matching_strategy = self._find_matching_strategy(fault)
            if matching_strategy:
                target_level = matching_strategy.target_level

            # 执行降级
            if target_level.value > self.current_level.value:
                self.transition_to(target_level, f"Fault: {fault.name}")

            return self.current_level

    def clear_fault(self, fault_id: str) -> bool:
        """清除故障"""
        with self._lock:
            if fault_id in self.active_faults:
                del self.active_faults[fault_id]

                # 检查是否可以恢复
                if not self.active_faults:
                    self.transition_to(DegradationLevel.NORMAL, "All faults cleared")

                return True
            return False

    def _determine_degradation_level(self, fault: Fault) -> DegradationLevel:
        """根据故障确定降级等级"""
        severity_mapping = {
            FaultSeverity.NEGLIGIBLE: DegradationLevel.DEGRADED_L1,
            FaultSeverity.MARGINAL: DegradationLevel.DEGRADED_L2,
            FaultSeverity.CRITICAL: DegradationLevel.DEGRADED_L3,
            FaultSeverity.CATASTROPHIC: DegradationLevel.EMERGENCY_STOP
        }
        return severity_mapping.get(fault.severity, DegradationLevel.SAFE_STATE)

    def _find_matching_strategy(self, fault: Fault) -> Optional[DegradationStrategy]:
        """查找匹配的降级策略"""
        for strategy in self.strategies.values():
            if fault.fault_id in strategy.trigger_faults:
                return strategy
        return None

    def get_status(self) -> Dict[str, Any]:
        """获取状态机状态"""
        return {
            'system_id': self.system_id,
            'current_level': self.current_level.name,
            'current_state': self.current_state.name,
            'active_faults': list(self.active_faults.keys()),
            'fault_count': len(self.active_faults),
            'history_count': len(self.state_history)
        }

    def get_available_features(self) -> Dict[str, bool]:
        """获取当前可用功能"""
        features = {
            'auto_control': True,
            'remote_control': True,
            'advanced_protection': True,
            'optimization': True,
            'data_logging': True,
            'diagnostics': True
        }

        # 根据降级等级禁用功能
        if self.current_level.value >= DegradationLevel.DEGRADED_L1.value:
            features['optimization'] = False

        if self.current_level.value >= DegradationLevel.DEGRADED_L2.value:
            features['advanced_protection'] = False
            features['remote_control'] = False

        if self.current_level.value >= DegradationLevel.DEGRADED_L3.value:
            features['auto_control'] = False

        if self.current_level.value >= DegradationLevel.SAFE_STATE.value:
            features['data_logging'] = False

        if self.current_level == DegradationLevel.EMERGENCY_STOP:
            features = {k: False for k in features}
            features['diagnostics'] = True  # 保留诊断功能

        return features


class FaultHandler:
    """故障处理器"""

    def __init__(self):
        self.fault_detectors: Dict[str, Callable] = {}
        self.fault_responses: Dict[FaultType, List[Callable]] = {
            ft: [] for ft in FaultType
        }
        self.detected_faults: List[Fault] = []
        self.fault_log: List[Dict] = []

    def register_detector(self, name: str, detector: Callable[[], Optional[Fault]]):
        """注册故障检测器"""
        self.fault_detectors[name] = detector

    def register_response(self, fault_type: FaultType,
                         response: Callable[[Fault], None]):
        """注册故障响应"""
        self.fault_responses[fault_type].append(response)

    def check_faults(self) -> List[Fault]:
        """检查所有故障"""
        new_faults = []
        for name, detector in self.fault_detectors.items():
            try:
                fault = detector()
                if fault:
                    new_faults.append(fault)
                    self._log_fault(fault, "DETECTED")
            except Exception as e:
                print(f"Fault detector {name} error: {e}")

        self.detected_faults.extend(new_faults)
        return new_faults

    def handle_fault(self, fault: Fault):
        """处理故障"""
        self._log_fault(fault, "HANDLING")
        responses = self.fault_responses.get(fault.fault_type, [])
        for response in responses:
            try:
                response(fault)
            except Exception as e:
                print(f"Fault response error: {e}")
        self._log_fault(fault, "HANDLED")

    def _log_fault(self, fault: Fault, action: str):
        """记录故障日志"""
        self.fault_log.append({
            'timestamp': datetime.now().isoformat(),
            'fault_id': fault.fault_id,
            'fault_name': fault.name,
            'fault_type': fault.fault_type.name,
            'severity': fault.severity.name,
            'action': action
        })


class SafetyMonitor:
    """安全监控器 - 综合安全监控"""

    def __init__(self, system_id: str):
        self.system_id = system_id
        self.safety_goals: Dict[str, SafetyGoal] = {}
        self.safety_requirements: Dict[str, SafetyRequirement] = {}
        self.degradation_sm = DegradationStateMachine(system_id)
        self.fault_handler = FaultHandler()
        self.monitoring = False

        # 监控参数
        self.monitored_values: Dict[str, Any] = {}
        self.safety_margins: Dict[str, float] = {}
        self.violation_count = 0

        # 回调
        self.safety_callbacks: List[Callable] = []

    def add_safety_goal(self, goal: SafetyGoal):
        """添加安全目标"""
        self.safety_goals[goal.goal_id] = goal

    def add_safety_requirement(self, req: SafetyRequirement):
        """添加安全需求"""
        self.safety_requirements[req.req_id] = req

    def start_monitoring(self):
        """启动监控"""
        self.monitoring = True
        self.degradation_sm.current_state = SystemState.OPERATIONAL

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False

    def update(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """更新监控状态"""
        if not self.monitoring:
            return {'status': 'not_monitoring'}

        self.monitored_values = values

        # 检查故障
        faults = self.fault_handler.check_faults()
        for fault in faults:
            self.degradation_sm.report_fault(fault)
            self.fault_handler.handle_fault(fault)

        # 检查安全裕度
        self._check_safety_margins(values)

        # 调用回调
        for callback in self.safety_callbacks:
            try:
                callback(self.get_status())
            except Exception as e:
                print(f"Safety callback error: {e}")

        return self.get_status()

    def _check_safety_margins(self, values: Dict[str, Any]):
        """检查安全裕度"""
        # 这里可以根据具体的安全目标检查各参数的安全裕度
        pass

    def get_status(self) -> Dict[str, Any]:
        """获取安全监控状态"""
        return {
            'system_id': self.system_id,
            'monitoring': self.monitoring,
            'degradation_status': self.degradation_sm.get_status(),
            'available_features': self.degradation_sm.get_available_features(),
            'active_faults': len(self.degradation_sm.active_faults),
            'safety_goals_count': len(self.safety_goals),
            'safety_requirements_count': len(self.safety_requirements)
        }

    def generate_safety_report(self) -> Dict[str, Any]:
        """生成安全报告"""
        report = {
            'system_id': self.system_id,
            'generated_at': datetime.now().isoformat(),
            'safety_goals': {},
            'requirement_coverage': {},
            'degradation_history': self.degradation_sm.state_history,
            'fault_log': self.fault_handler.fault_log
        }

        for goal_id, goal in self.safety_goals.items():
            report['safety_goals'][goal_id] = {
                'name': goal.name,
                'asil': goal.asil_level.name,
                'requirements': goal.requirements
            }

        for req_id, req in self.safety_requirements.items():
            report['requirement_coverage'][req_id] = {
                'name': req.name,
                'status': req.verification_status,
                'test_cases': req.test_cases
            }

        return report


# 预定义的水利系统降级策略
def create_hydraulic_degradation_strategies() -> List[DegradationStrategy]:
    """创建水利系统降级策略"""
    strategies = []

    # 策略1: 传感器故障 -> 一级降级
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_SENSOR_L1",
        name="传感器单点故障降级",
        description="单个传感器故障时启用冗余传感器",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["SENSOR_SINGLE_FAULT"],
        actions=[
            "切换到冗余传感器",
            "启用软件估计值",
            "记录故障信息"
        ],
        disabled_features=["高精度测量"],
        parameter_overrides={"control_gain": 0.8},
        recovery_conditions={"sensor_restored": True}
    ))

    # 策略2: 执行器响应慢 -> 二级降级
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_ACTUATOR_L2",
        name="执行器性能下降降级",
        description="执行器响应变慢时降低控制要求",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["ACTUATOR_SLOW_RESPONSE"],
        actions=[
            "降低控制速率",
            "增加死区",
            "启用软限位"
        ],
        disabled_features=["快速响应", "精确控制"],
        parameter_overrides={
            "max_rate": 0.5,
            "deadband": 0.05
        }
    ))

    # 策略3: 通信中断 -> 三级降级
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_COMM_L3",
        name="通信中断降级",
        description="与上位机通信中断时进入本地控制模式",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L3,
        trigger_faults=["COMM_TIMEOUT", "SCADA_DISCONNECT"],
        actions=[
            "切换到本地控制",
            "使用预设参数",
            "启动本地报警"
        ],
        disabled_features=["远程控制", "在线参数修改", "数据上传"],
        min_hold_time=60.0
    ))

    # 策略4: 严重故障 -> 安全状态
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_SAFE_STATE",
        name="安全状态转换",
        description="严重故障时进入安全状态",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.SAFE_STATE,
        trigger_faults=["CRITICAL_FAULT", "MULTIPLE_FAULTS"],
        actions=[
            "停止自动控制",
            "保持当前位置",
            "启动应急程序",
            "发送紧急报警"
        ],
        disabled_features=["所有自动功能"],
        recovery_actions=["人工确认", "故障排除", "系统重启"]
    ))

    # 策略5: 紧急停机
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_EMERGENCY",
        name="紧急停机",
        description="危险情况下紧急停机",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.EMERGENCY_STOP,
        trigger_faults=["OVERPRESSURE", "PIPE_BURST", "WATER_HAMMER_CRITICAL"],
        actions=[
            "紧急关闭阀门",
            "停止所有泵",
            "开启泄压阀",
            "切断动力源"
        ],
        max_transition_time=0.5
    ))

    return strategies


def create_multi_energy_degradation_strategies() -> List[DegradationStrategy]:
    """创建多能互补系统降级策略"""
    strategies = []

    # 策略1: 储能SOC低 -> 一级降级
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_SOC_LOW",
        name="储能容量不足降级",
        description="储能SOC低于阈值时限制功率输出",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["SOC_LOW_WARNING"],
        trigger_conditions={"sc_soc": "<30", "bess_soc": "<20"},
        actions=[
            "限制储能放电功率",
            "增加常规水电出力",
            "启用功率备用"
        ],
        parameter_overrides={
            "max_sc_discharge": 0.5,
            "max_bess_discharge": 0.3
        }
    ))

    # 策略2: 新能源脱网 -> 二级降级
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_RE_DISCONNECT",
        name="新能源脱网降级",
        description="风电或光伏脱网时调整功率平衡",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["WIND_DISCONNECT", "PV_DISCONNECT"],
        actions=[
            "启动储能快速响应",
            "增加常规机组出力",
            "降低系统负荷"
        ],
        disabled_features=["新能源优先调度"]
    ))

    # 策略3: 频率异常 -> 三级降级
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_FREQ_ABNORMAL",
        name="频率异常降级",
        description="电网频率超出正常范围时启用紧急调频",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L3,
        trigger_faults=["FREQ_HIGH", "FREQ_LOW"],
        trigger_conditions={"grid_frequency": "<49.5 or >50.5"},
        actions=[
            "全功率储能调频",
            "PSH紧急投入",
            "切除非关键负荷"
        ],
        parameter_overrides={
            "sc_droop_gain": 2.0,
            "bess_response_time": 0.1
        }
    ))

    # 策略4: PSH故障 -> 安全状态
    strategies.append(DegradationStrategy(
        strategy_id="DEGRADE_PSH_FAULT",
        name="抽水蓄能故障降级",
        description="PSH机组故障时转移负荷",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.SAFE_STATE,
        trigger_faults=["PSH_TRIP", "PSH_MECHANICAL_FAULT"],
        actions=[
            "紧急停止PSH",
            "储能接管功率",
            "请求外部支援"
        ]
    ))

    return strategies
