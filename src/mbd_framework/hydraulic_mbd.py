# -*- coding: utf-8 -*-
"""
水利系统MBD应用模块
Hydraulic System MBD Application Module

为阀门控制器(IVCU)、水泵控制器(IPCU)、闸门控制器(IGCU)
提供完整的MBD模型实现、ODD定义和降级策略
"""

import sys
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# 导入MBD框架
from .mbd_core import (
    MBDModel, MBDWorkflow, VModelPhase, ModelType,
    RequirementTrace, DesignSpecification, ModelArtifact,
    ModelValidator, VerificationStatus
)
from .odd_framework import (
    ODDDefinition, ODDBoundary, OperatingCondition, ODDMonitor,
    ODDCategory, ConditionType, BoundaryType, ViolationSeverity
)
from .functional_safety import (
    SafetyGoal, SafetyRequirement, ASILLevel, SafetyLevel,
    DegradationStrategy, DegradationStateMachine, DegradationLevel,
    Fault, FaultType, FaultCategory, FaultSeverity, SafetyMonitor
)


# ============================================================
# 阀门控制器 (IVCU) MBD实现
# ============================================================

class ValveMBDModel(MBDModel):
    """阀门控制器MBD模型

    基于IVCU控制器的MBD模型实现
    实现两阶段液压关闭曲线、水锤防护等功能
    """

    def __init__(self, model_id: str = "IVCU_MBD_001"):
        super().__init__(model_id, "智能阀门控制柜模型", ModelType.CONTROLLER)

        # 模型参数
        self._parameters = {
            # 设计参数
            'design_pressure': 1.6,         # 设计压力 (MPa)
            'max_pressure_ratio': 1.2,      # 最大压力比
            'min_pressure': 0.05,           # 最小压力 (MPa)
            'reversal_cutoff': 0.30,        # 倒流截断开度

            # 阀门动作参数
            'valve_speed': 0.1,             # 正常动作速度 (%/s)
            'fast_close_speed': 0.5,        # 快关速度 (%/s)
            'slow_close_speed': 0.02,       # 慢关速度 (%/s)

            # 两阶段关闭参数
            'stage1_target': 0.3,           # 第一阶段目标开度
            'stage1_speed': 0.3,            # 第一阶段速度
            'stage2_speed': 0.05,           # 第二阶段速度
            'stage_pause_time': 2.0,        # 阶段间暂停时间 (s)

            # 卡涩检测参数
            'stall_detect_time': 2.0,       # 卡涩检测时间 (s)
            'stall_threshold': 0.01,        # 卡涩阈值
        }

        # 定义输入输出
        self.artifact.inputs = [
            'position_setpoint',    # 位置设定值
            'P1',                   # 上游压力
            'P2',                   # 下游压力
            'Q',                    # 流量
            'opening',              # 当前开度
            'power_fail',           # 断电信号
            'enable'                # 使能信号
        ]

        self.artifact.outputs = [
            'valve_command',        # 阀门指令
            'valve_mode',           # 控制模式
            'protection_active',    # 保护激活
            'alarm_code',           # 报警代码
            'water_hammer_risk'     # 水锤风险等级
        ]

        self.artifact.states = [
            'closing_stage',        # 关闭阶段
            'stage_timer',          # 阶段计时器
            'stall_timer',          # 卡涩计时器
            'power_fail_detected',  # 断电检测
            'high_flow_lockout'     # 高流速锁定
        ]

        # 关联需求
        self.artifact.requirements = [
            'REQ_IVCU_001',  # 响应时间<=50ms
            'REQ_IVCU_002',  # 压力峰值<=1.2倍设计压力
            'REQ_IVCU_003',  # 防断流弥合
            'REQ_IVCU_004',  # 倒流截断
            'REQ_IVCU_005',  # 两阶段关闭曲线
        ]

    def initialize(self):
        """初始化模型状态"""
        self._states = {
            'closing_stage': 0,
            'stage_timer': 0.0,
            'stall_timer': 0.0,
            'power_fail_detected': False,
            'high_flow_lockout': False,
            'last_position': 1.0,
            'valve_position': 1.0,
            'current_mode': 'POSITION'
        }

        self._outputs = {
            'valve_command': 1.0,
            'valve_mode': 'POSITION',
            'protection_active': False,
            'alarm_code': 0,
            'water_hammer_risk': 'LOW'
        }

    def update(self, dt: float):
        """更新模型状态"""
        # 获取输入
        setpoint = self._inputs.get('position_setpoint', 1.0)
        P1 = self._inputs.get('P1', 0.0)
        P2 = self._inputs.get('P2', 0.0)
        Q = self._inputs.get('Q', 0.0)
        opening = self._inputs.get('opening', self._states['valve_position'])
        power_fail = self._inputs.get('power_fail', False)
        enable = self._inputs.get('enable', True)

        self._states['valve_position'] = opening

        # 保护逻辑
        protection_active = False
        alarm_code = 0

        # 1. 断电保护
        if power_fail and not self._states['power_fail_detected']:
            self._states['power_fail_detected'] = True
            self._states['current_mode'] = 'TWO_STAGE_CLOSE'
            self._states['closing_stage'] = 0
            protection_active = True
            alarm_code = 1

        # 2. 超压保护
        max_allowed = self._parameters['design_pressure'] * self._parameters['max_pressure_ratio']
        if P1 > max_allowed or P2 > max_allowed:
            self._states['current_mode'] = 'TWO_STAGE_CLOSE'
            protection_active = True
            alarm_code = 2

        # 3. 负压保护
        if P2 < self._parameters['min_pressure']:
            self._parameters['stage2_speed'] = 0.01  # 减缓关闭
            protection_active = True
            alarm_code = 3

        # 4. 计算水锤风险
        pipe_area = 3.14159 * 1.0 ** 2
        velocity = Q / pipe_area if pipe_area > 0 and Q > 0 else 0
        wave_speed = 1000
        potential_pressure = wave_speed * velocity / 9.81 / 1e6

        if potential_pressure + P1 > max_allowed:
            water_hammer_risk = 'HIGH'
        elif potential_pressure + P1 > self._parameters['design_pressure']:
            water_hammer_risk = 'MEDIUM'
        else:
            water_hammer_risk = 'LOW'

        # 5. 高流速锁定
        if velocity > 3.0 and setpoint < 0.5:
            self._states['high_flow_lockout'] = True
            self._states['current_mode'] = 'SLOW_CLOSE'
            protection_active = True
            alarm_code = 4

        # 控制逻辑
        mode = self._states['current_mode']

        if mode == 'POSITION':
            # 位置控制
            error = setpoint - opening
            max_change = self._parameters['valve_speed'] * dt
            if abs(error) < max_change:
                command = setpoint
            else:
                command = opening + (1 if error > 0 else -1) * max_change

        elif mode == 'TWO_STAGE_CLOSE':
            # 两阶段关闭
            command = self._two_stage_close(opening, dt)

        elif mode == 'EMERGENCY_CLOSE':
            # 紧急关闭
            if opening > 0.01:
                command = opening - self._parameters['fast_close_speed'] * dt
                command = max(command, 0.0)
            else:
                command = 0.0

        elif mode == 'SLOW_CLOSE':
            # 慢速关闭
            if opening > 0.01:
                command = opening - self._parameters['slow_close_speed'] * dt
                command = max(command, 0.0)
            else:
                command = 0.0
        else:
            command = opening

        # 更新输出
        self._outputs = {
            'valve_command': max(0.0, min(1.0, command)),
            'valve_mode': mode,
            'protection_active': protection_active,
            'alarm_code': alarm_code,
            'water_hammer_risk': water_hammer_risk
        }

    def _two_stage_close(self, opening: float, dt: float) -> float:
        """两阶段关闭控制"""
        stage = self._states['closing_stage']

        if stage == 0:
            self._states['closing_stage'] = 1
            self._states['stage_timer'] = 0.0

        if stage == 1:
            # 第一阶段：快关到30%
            if opening > self._parameters['stage1_target']:
                new_opening = opening - self._parameters['stage1_speed'] * dt
                return max(new_opening, self._parameters['stage1_target'])
            else:
                self._states['closing_stage'] = 2
                self._states['stage_timer'] = 0.0
                return opening

        elif stage == 2:
            # 暂停阶段
            self._states['stage_timer'] += dt
            if self._states['stage_timer'] >= self._parameters['stage_pause_time']:
                self._states['closing_stage'] = 3
            return opening

        elif stage == 3:
            # 第二阶段：慢关到全关
            if opening > 0.01:
                new_opening = opening - self._parameters['stage2_speed'] * dt
                return max(new_opening, 0.0)
            else:
                self._states['closing_stage'] = 0
                self._states['current_mode'] = 'POSITION'
                return 0.0

        return opening

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


def create_valve_odd() -> ODDDefinition:
    """创建阀门控制器ODD定义"""
    odd = ODDDefinition(
        odd_id="ODD_IVCU_001",
        name="智能阀门控制柜ODD",
        description="IVCU阀门控制器的运行设计域定义"
    )

    # 环境条件
    odd.add_condition(OperatingCondition(
        condition_id="IVCU_ENV_TEMP",
        name="环境温度",
        description="控制柜工作环境温度",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="ambient_temperature",
        unit="°C",
        min_value=-10.0,
        max_value=55.0,
        nominal_value=25.0
    ))

    # 运行条件 - 压力
    odd.add_condition(OperatingCondition(
        condition_id="IVCU_OP_P1",
        name="上游压力",
        description="阀门上游压力范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="P1",
        unit="MPa",
        min_value=0.0,
        max_value=1.92,  # 1.6 * 1.2
        nominal_value=1.0
    ))

    odd.add_condition(OperatingCondition(
        condition_id="IVCU_OP_P2",
        name="下游压力",
        description="阀门下游压力范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="P2",
        unit="MPa",
        min_value=0.05,  # 最小压力，防止负压
        max_value=1.92
    ))

    # 运行条件 - 流量
    odd.add_condition(OperatingCondition(
        condition_id="IVCU_OP_FLOW",
        name="流量",
        description="管道流量范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="Q",
        unit="m³/s",
        min_value=0.0,
        max_value=50.0
    ))

    # 运行条件 - 流速
    odd.add_condition(OperatingCondition(
        condition_id="IVCU_OP_VELOCITY",
        name="流速",
        description="管道流速范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="velocity",
        unit="m/s",
        min_value=0.0,
        max_value=5.0,  # 超过此值需要慢关
        nominal_value=2.0
    ))

    # 运行条件 - 开度
    odd.add_condition(OperatingCondition(
        condition_id="IVCU_OP_OPENING",
        name="阀门开度",
        description="阀门开度范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="opening",
        unit="%",
        min_value=0.0,
        max_value=100.0
    ))

    # 基础设施条件
    odd.add_condition(OperatingCondition(
        condition_id="IVCU_INFRA_POWER",
        name="电源状态",
        description="控制柜电源状态",
        category=ODDCategory.INFRASTRUCTURE,
        condition_type=ConditionType.STATIC,
        parameter_name="power_status",
        allowed_values=["NORMAL", "BACKUP", "UPS", "BATTERY"]
    ))

    # 添加边界
    # 压力硬边界
    pressure_boundary = ODDBoundary(
        boundary_id="IVCU_BOUND_PRESSURE",
        name="压力安全边界",
        description="管道压力不得超过设计值的1.2倍",
        boundary_type=BoundaryType.HARD,
        violation_severity=ViolationSeverity.CRITICAL,
        response_action="启动两阶段关闭",
        recovery_procedure="检查压力源,确认安全后恢复",
        max_violation_duration=0.0
    )
    pressure_boundary.add_condition(odd.conditions["IVCU_OP_P1"])
    pressure_boundary.add_condition(odd.conditions["IVCU_OP_P2"])
    odd.add_boundary(pressure_boundary)

    # 负压软边界
    negative_pressure_boundary = ODDBoundary(
        boundary_id="IVCU_BOUND_NEG_PRESSURE",
        name="负压边界",
        description="下游压力不得低于最小值",
        boundary_type=BoundaryType.SOFT,
        violation_severity=ViolationSeverity.WARNING,
        response_action="减缓关闭速度",
        max_violation_duration=5.0
    )
    negative_pressure_boundary.add_condition(odd.conditions["IVCU_OP_P2"])
    odd.add_boundary(negative_pressure_boundary)

    # 流速边界
    velocity_boundary = ODDBoundary(
        boundary_id="IVCU_BOUND_VELOCITY",
        name="流速边界",
        description="高流速时禁止快关",
        boundary_type=BoundaryType.SOFT,
        violation_severity=ViolationSeverity.WARNING,
        response_action="锁定快关功能,切换慢关",
        max_violation_duration=60.0
    )
    velocity_boundary.add_condition(odd.conditions["IVCU_OP_VELOCITY"])
    odd.add_boundary(velocity_boundary)

    return odd


def create_valve_safety_goals() -> List[SafetyGoal]:
    """创建阀门控制器安全目标"""
    goals = []

    # SG1: 水锤防护
    goals.append(SafetyGoal(
        goal_id="SG_IVCU_WATER_HAMMER",
        name="水锤防护",
        description="防止阀门快关导致的水锤效应造成管道超压",
        asil_level=ASILLevel.ASIL_C,
        sil_level=SafetyLevel.SIL_2,
        hazard_id="HAZ_001",
        hazard_description="阀门快关产生水锤压力波,导致管道破裂",
        exposure="E3",
        controllability="C2",
        severity="S3",
        safe_state="阀门保持当前位置或缓慢关闭",
        fault_tolerant_time=0.5,
        max_response_time=0.05,
        requirements=["REQ_IVCU_002", "REQ_IVCU_005"]
    ))

    # SG2: 断电保护
    goals.append(SafetyGoal(
        goal_id="SG_IVCU_POWER_FAIL",
        name="断电安全",
        description="断电时阀门应能安全关闭防止倒流",
        asil_level=ASILLevel.ASIL_B,
        sil_level=SafetyLevel.SIL_1,
        hazard_id="HAZ_002",
        hazard_description="断电后泵倒转产生倒流",
        exposure="E2",
        controllability="C2",
        severity="S2",
        safe_state="阀门关闭至30%以下",
        fault_tolerant_time=120.0,
        requirements=["REQ_IVCU_004"]
    ))

    # SG3: 负压防护
    goals.append(SafetyGoal(
        goal_id="SG_IVCU_NEG_PRESSURE",
        name="负压防护",
        description="防止管道出现负压导致断流弥合",
        asil_level=ASILLevel.ASIL_B,
        sil_level=SafetyLevel.SIL_1,
        hazard_id="HAZ_003",
        hazard_description="管道负压导致水柱分离和弥合冲击",
        safe_state="减缓阀门关闭速度",
        requirements=["REQ_IVCU_003"]
    ))

    return goals


def create_valve_degradation_strategies() -> List[DegradationStrategy]:
    """创建阀门控制器降级策略"""
    strategies = []

    # 策略1: 位置传感器故障
    strategies.append(DegradationStrategy(
        strategy_id="IVCU_DEG_POS_SENSOR",
        name="位置传感器故障降级",
        description="位置反馈丢失时切换到时间控制",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["IVCU_FAULT_POS_SENSOR"],
        actions=[
            "切换到时间控制模式",
            "使用预设关闭曲线",
            "启用备用行程开关"
        ],
        disabled_features=["精确位置控制", "位置反馈显示"],
        parameter_overrides={
            'control_mode': 'TIME_BASED',
            'close_time': 60.0
        },
        recovery_conditions={'position_sensor_ok': True}
    ))

    # 策略2: 压力传感器故障
    strategies.append(DegradationStrategy(
        strategy_id="IVCU_DEG_PRESSURE_SENSOR",
        name="压力传感器故障降级",
        description="压力反馈丢失时采用保守控制",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["IVCU_FAULT_P1_SENSOR", "IVCU_FAULT_P2_SENSOR"],
        actions=[
            "禁用自动超压保护",
            "强制使用两阶段关闭",
            "降低关闭速度"
        ],
        disabled_features=["超压自动保护", "负压检测"],
        parameter_overrides={
            'force_two_stage': True,
            'stage1_speed': 0.2,
            'stage2_speed': 0.02
        }
    ))

    # 策略3: 执行机构响应慢
    strategies.append(DegradationStrategy(
        strategy_id="IVCU_DEG_ACTUATOR_SLOW",
        name="执行机构响应慢降级",
        description="阀门动作变慢时调整控制参数",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["IVCU_FAULT_ACTUATOR_SLOW"],
        actions=[
            "增加指令提前量",
            "降低响应要求"
        ],
        parameter_overrides={
            'response_time_factor': 2.0
        }
    ))

    # 策略4: 通信中断
    strategies.append(DegradationStrategy(
        strategy_id="IVCU_DEG_COMM_LOSS",
        name="通信中断降级",
        description="与上位机通信中断时本地控制",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["IVCU_FAULT_COMM_TIMEOUT"],
        actions=[
            "切换到本地控制模式",
            "保持当前设定",
            "启用本地报警"
        ],
        disabled_features=["远程控制", "远程参数修改"],
        min_hold_time=60.0
    ))

    # 策略5: 严重故障安全停机
    strategies.append(DegradationStrategy(
        strategy_id="IVCU_DEG_SAFE_STOP",
        name="安全停机",
        description="多重故障时进入安全状态",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.SAFE_STATE,
        trigger_faults=["IVCU_FAULT_MULTIPLE", "IVCU_FAULT_CRITICAL"],
        actions=[
            "执行两阶段关闭",
            "锁定控制",
            "等待人工确认"
        ],
        recovery_actions=["人工检查", "故障确认", "手动复位"]
    ))

    return strategies


# ============================================================
# 水泵控制器 (IPCU) MBD实现
# ============================================================

class PumpMBDModel(MBDModel):
    """水泵控制器MBD模型"""

    def __init__(self, model_id: str = "IPCU_MBD_001"):
        super().__init__(model_id, "智能泵控柜模型", ModelType.CONTROLLER)

        self._parameters = {
            # 额定参数
            'rated_speed': 1450.0,
            'rated_flow': 10.0,
            'rated_head': 100.0,
            'rated_power': 12000.0,

            # 软启停参数
            'min_start_time': 60.0,
            'min_stop_time': 60.0,

            # 倒转保护
            'max_reverse_ratio': 1.2,
            'max_reverse_time': 120.0,

            # 振动阈值
            'vibration_warning': 4.5,
            'vibration_alarm': 7.1,
            'vibration_trip': 11.2,

            # 温度阈值
            'temperature_warning': 65.0,
            'temperature_alarm': 75.0,
            'temperature_trip': 85.0,
        }

        self.artifact.inputs = [
            'speed_setpoint', 'start_command', 'stop_command',
            'speed', 'flow', 'P_suction', 'P_discharge',
            'vibration', 'temperature'
        ]

        self.artifact.outputs = [
            'speed_command', 'pump_mode', 'protection_active',
            'alarm_code', 'operating_zone', 'efficiency'
        ]

        self.artifact.requirements = [
            'REQ_IPCU_001',  # S形曲线软启停
            'REQ_IPCU_002',  # 运行区间限制
            'REQ_IPCU_003',  # 倒转保护
            'REQ_IPCU_004',  # 振动联动
        ]

    def initialize(self):
        self._states = {
            'current_speed': 0.0,
            'ramp_timer': 0.0,
            'ramp_start': 0.0,
            'ramp_target': 0.0,
            'reverse_timer': 0.0,
            'is_running': False,
            'mode': 'STOPPED'
        }

        self._outputs = {
            'speed_command': 0.0,
            'pump_mode': 'STOPPED',
            'protection_active': False,
            'alarm_code': 0,
            'operating_zone': 'STOPPED',
            'efficiency': 0.0
        }

    def update(self, dt: float):
        # 获取输入
        setpoint = self._inputs.get('speed_setpoint', 0.0)
        start_cmd = self._inputs.get('start_command', False)
        stop_cmd = self._inputs.get('stop_command', False)
        speed = self._inputs.get('speed', 0.0)
        flow = self._inputs.get('flow', 0.0)
        vibration = self._inputs.get('vibration', 0.0)
        temperature = self._inputs.get('temperature', 20.0)

        self._states['current_speed'] = speed

        protection_active = False
        alarm_code = 0

        # 保护逻辑
        # 1. 倒转保护
        if speed < -10:
            self._states['reverse_timer'] += dt
            reverse_ratio = abs(speed) / self._parameters['rated_speed']

            if reverse_ratio > self._parameters['max_reverse_ratio']:
                protection_active = True
                alarm_code = 1

            if self._states['reverse_timer'] > self._parameters['max_reverse_time']:
                protection_active = True
                alarm_code = 2
        else:
            self._states['reverse_timer'] = 0.0

        # 2. 振动保护
        if vibration > self._parameters['vibration_trip']:
            self._states['mode'] = 'EMERGENCY_STOP'
            protection_active = True
            alarm_code = 3
        elif vibration > self._parameters['vibration_alarm']:
            setpoint = speed * 0.8
            alarm_code = 4

        # 3. 温度保护
        if temperature > self._parameters['temperature_trip']:
            self._states['mode'] = 'EMERGENCY_STOP'
            protection_active = True
            alarm_code = 5

        # 启停控制
        mode = self._states['mode']

        if start_cmd and mode == 'STOPPED':
            self._states['mode'] = 'SOFT_START'
            self._states['ramp_timer'] = 0.0
            self._states['ramp_start'] = speed
            self._states['ramp_target'] = setpoint
            self._states['is_running'] = True

        if stop_cmd and mode not in ['STOPPED', 'SOFT_STOP', 'EMERGENCY_STOP']:
            self._states['mode'] = 'SOFT_STOP'
            self._states['ramp_timer'] = 0.0
            self._states['ramp_start'] = speed

        # 计算输出
        if mode == 'SOFT_START':
            command = self._soft_start(dt)
        elif mode == 'SOFT_STOP':
            command = self._soft_stop(dt)
        elif mode == 'EMERGENCY_STOP':
            command = 0.0
        elif mode == 'RUNNING':
            command = self._speed_control(setpoint, speed, dt)
        else:
            command = 0.0

        # 计算运行区
        operating_zone = self._get_operating_zone(speed, flow)

        # 计算效率
        if speed > 0 and flow > 0:
            speed_ratio = speed / self._parameters['rated_speed']
            flow_ratio = flow / (self._parameters['rated_flow'] * speed_ratio)
            efficiency = 0.88 * (1 - 0.5 * (flow_ratio - 1) ** 2)
        else:
            efficiency = 0.0

        self._outputs = {
            'speed_command': max(0.0, command),
            'pump_mode': self._states['mode'],
            'protection_active': protection_active,
            'alarm_code': alarm_code,
            'operating_zone': operating_zone,
            'efficiency': efficiency
        }

    def _soft_start(self, dt: float) -> float:
        """S形曲线软启动"""
        self._states['ramp_timer'] += dt
        progress = self._states['ramp_timer'] / self._parameters['min_start_time']

        if progress >= 1.0:
            self._states['mode'] = 'RUNNING'
            return self._states['ramp_target']

        # S形曲线
        import math
        s_curve = 1 / (1 + math.exp(-10 * (progress - 0.5)))
        return self._states['ramp_start'] + (self._states['ramp_target'] - self._states['ramp_start']) * s_curve

    def _soft_stop(self, dt: float) -> float:
        """S形曲线软停止"""
        self._states['ramp_timer'] += dt
        progress = self._states['ramp_timer'] / self._parameters['min_stop_time']

        if progress >= 1.0:
            self._states['mode'] = 'STOPPED'
            self._states['is_running'] = False
            return 0.0

        import math
        s_curve = 1 - 1 / (1 + math.exp(-10 * (progress - 0.5)))
        return self._states['ramp_start'] * s_curve

    def _speed_control(self, setpoint: float, current: float, dt: float) -> float:
        """转速控制"""
        max_rate = self._parameters['rated_speed'] / self._parameters['min_start_time']
        error = setpoint - current

        if abs(error) < max_rate * dt:
            return setpoint
        else:
            return current + (1 if error > 0 else -1) * max_rate * dt

    def _get_operating_zone(self, speed: float, flow: float) -> str:
        """获取运行区"""
        if speed < 100:
            return 'STOPPED'

        speed_ratio = speed / self._parameters['rated_speed']
        flow_ratio = flow / (self._parameters['rated_flow'] * speed_ratio) if speed_ratio > 0.1 else 0

        if flow_ratio < 0.4:
            return 'SADDLE'
        elif flow_ratio > 1.3:
            return 'CAVITATION'
        elif 0.6 <= flow_ratio <= 1.2:
            return 'HIGH_EFFICIENCY'
        else:
            return 'NORMAL'

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


def create_pump_odd() -> ODDDefinition:
    """创建水泵控制器ODD定义"""
    odd = ODDDefinition(
        odd_id="ODD_IPCU_001",
        name="智能泵控柜ODD",
        description="IPCU水泵控制器的运行设计域定义"
    )

    # 转速条件
    odd.add_condition(OperatingCondition(
        condition_id="IPCU_OP_SPEED",
        name="转速",
        description="水泵运行转速范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="speed",
        unit="rpm",
        min_value=-1740,  # 允许倒转到1.2倍
        max_value=1595,   # 额定转速1.1倍
        nominal_value=1450
    ))

    # 流量条件
    odd.add_condition(OperatingCondition(
        condition_id="IPCU_OP_FLOW",
        name="流量",
        description="水泵流量范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="flow",
        unit="m³/s",
        min_value=0.0,
        max_value=13.0  # 额定流量1.3倍
    ))

    # 振动条件
    odd.add_condition(OperatingCondition(
        condition_id="IPCU_OP_VIBRATION",
        name="振动",
        description="轴承振动范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="vibration",
        unit="mm/s",
        min_value=0.0,
        max_value=11.2  # 跳闸值
    ))

    # 温度条件
    odd.add_condition(OperatingCondition(
        condition_id="IPCU_OP_TEMPERATURE",
        name="轴温",
        description="轴承温度范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="temperature",
        unit="°C",
        min_value=0.0,
        max_value=85.0  # 跳闸值
    ))

    # 吸入压力条件
    odd.add_condition(OperatingCondition(
        condition_id="IPCU_OP_NPSH",
        name="吸入压力",
        description="防止汽蚀的最小吸入压力",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="P_suction",
        unit="MPa",
        min_value=0.02,  # NPSHr要求
        max_value=0.5
    ))

    # 添加边界
    # 振动跳闸边界
    vibration_boundary = ODDBoundary(
        boundary_id="IPCU_BOUND_VIBRATION",
        name="振动安全边界",
        description="振动超限时紧急停机",
        boundary_type=BoundaryType.HARD,
        violation_severity=ViolationSeverity.CRITICAL,
        response_action="紧急停机",
        degradation_modes=["DEGRADED_L1", "DEGRADED_L2", "EMERGENCY_STOP"]
    )
    vibration_boundary.add_condition(odd.conditions["IPCU_OP_VIBRATION"])
    odd.add_boundary(vibration_boundary)

    # 倒转边界
    reverse_boundary = ODDBoundary(
        boundary_id="IPCU_BOUND_REVERSE",
        name="倒转边界",
        description="倒转速度和时间限制",
        boundary_type=BoundaryType.HARD,
        violation_severity=ViolationSeverity.CRITICAL,
        response_action="监控倒转时间,等待停止"
    )
    reverse_boundary.add_condition(odd.conditions["IPCU_OP_SPEED"])
    odd.add_boundary(reverse_boundary)

    return odd


# ============================================================
# 闸门控制器 (IGCU) MBD实现
# ============================================================

class GateMBDModel(MBDModel):
    """闸门控制器MBD模型"""

    def __init__(self, model_id: str = "IGCU_MBD_001"):
        super().__init__(model_id, "智能闸门控制柜模型", ModelType.CONTROLLER)

        self._parameters = {
            # 闸门参数
            'gate_width': 10.0,
            'max_opening': 5.0,
            'gate_cd': 0.6,

            # 速度参数
            'normal_speed': 0.01,
            'fast_speed': 0.05,
            'slow_speed': 0.002,

            # 控制参数
            'flow_tolerance': 0.02,
            'flow_kp': 0.1,
            'flow_ki': 0.01,

            # 波涌参数
            'max_surge': 0.3,
            'surge_threshold': 0.2
        }

        self.artifact.inputs = [
            'opening_setpoint', 'flow_setpoint',
            'opening', 'Z_up', 'Z_down', 'Q'
        ]

        self.artifact.outputs = [
            'gate_command', 'gate_mode', 'protection_active',
            'alarm_code', 'surge_level', 'flow_error'
        ]

        self.artifact.requirements = [
            'REQ_IGCU_001',  # 流量伺服精度<=2%
            'REQ_IGCU_002',  # 波涌抑制<0.3m
            'REQ_IGCU_003',  # 防冲刷均流
        ]

    def initialize(self):
        self._states = {
            'current_opening': 0.0,
            'flow_integral': 0.0,
            'surge_detected': False,
            'surge_timer': 0.0,
            'initial_level': 3.0,
            'mode': 'OPENING'
        }

        self._outputs = {
            'gate_command': 0.0,
            'gate_mode': 'OPENING',
            'protection_active': False,
            'alarm_code': 0,
            'surge_level': 0.0,
            'flow_error': 0.0
        }

    def update(self, dt: float):
        # 获取输入
        opening_sp = self._inputs.get('opening_setpoint', 0.0)
        flow_sp = self._inputs.get('flow_setpoint', 0.0)
        opening = self._inputs.get('opening', 0.0)
        Z_up = self._inputs.get('Z_up', 3.0)
        Z_down = self._inputs.get('Z_down', 2.0)
        Q = self._inputs.get('Q', 0.0)

        self._states['current_opening'] = opening

        protection_active = False
        alarm_code = 0

        # 计算波涌
        surge = abs(Z_up - self._states['initial_level'])

        # 波涌保护
        if surge > self._parameters['max_surge']:
            protection_active = True
            alarm_code = 1
            self._states['mode'] = 'SURGE_SUPPRESS'

        # 计算流量误差
        flow_error = (Q - flow_sp) / max(flow_sp, 1.0) if flow_sp > 0 else 0

        # 控制逻辑
        mode = self._states['mode']

        if mode == 'OPENING':
            command = self._opening_control(opening_sp, opening, dt)
        elif mode == 'FLOW':
            command = self._flow_control(flow_sp, Q, opening, dt)
        elif mode == 'SURGE_SUPPRESS':
            command = self._surge_suppress(opening_sp, opening, surge, dt)
        else:
            command = opening

        self._outputs = {
            'gate_command': max(0.0, min(self._parameters['max_opening'], command)),
            'gate_mode': mode,
            'protection_active': protection_active,
            'alarm_code': alarm_code,
            'surge_level': surge,
            'flow_error': flow_error
        }

    def _opening_control(self, setpoint: float, current: float, dt: float) -> float:
        """开度控制"""
        error = setpoint - current
        max_change = self._parameters['normal_speed'] * dt

        if abs(error) < max_change:
            return setpoint
        else:
            return current + (1 if error > 0 else -1) * max_change

    def _flow_control(self, flow_sp: float, flow: float, opening: float, dt: float) -> float:
        """流量伺服控制"""
        error = flow_sp - flow
        error_ratio = error / max(flow_sp, 1.0)

        if abs(error_ratio) < self._parameters['flow_tolerance']:
            return opening

        self._states['flow_integral'] += error * dt
        self._states['flow_integral'] = max(-10, min(10, self._states['flow_integral']))

        adjustment = self._parameters['flow_kp'] * error + self._parameters['flow_ki'] * self._states['flow_integral']
        new_opening = opening + adjustment * 0.1 * dt

        return max(0, min(self._parameters['max_opening'], new_opening))

    def _surge_suppress(self, setpoint: float, current: float, surge: float, dt: float) -> float:
        """波涌抑制控制"""
        if surge > self._parameters['surge_threshold']:
            return current  # 暂停动作

        # 使用慢速
        error = setpoint - current
        max_change = self._parameters['slow_speed'] * dt

        if abs(error) < max_change:
            self._states['mode'] = 'OPENING'
            return setpoint
        else:
            return current + (1 if error > 0 else -1) * max_change

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


def create_gate_odd() -> ODDDefinition:
    """创建闸门控制器ODD定义"""
    odd = ODDDefinition(
        odd_id="ODD_IGCU_001",
        name="智能闸门控制柜ODD",
        description="IGCU闸门控制器的运行设计域定义"
    )

    # 开度条件
    odd.add_condition(OperatingCondition(
        condition_id="IGCU_OP_OPENING",
        name="闸门开度",
        description="闸门开度范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="opening",
        unit="m",
        min_value=0.0,
        max_value=5.0
    ))

    # 上游水位条件
    odd.add_condition(OperatingCondition(
        condition_id="IGCU_OP_Z_UP",
        name="上游水位",
        description="上游水位范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="Z_up",
        unit="m",
        min_value=0.0,
        max_value=10.0
    ))

    # 波涌条件
    odd.add_condition(OperatingCondition(
        condition_id="IGCU_OP_SURGE",
        name="波涌幅度",
        description="水位波涌幅度限制",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="surge",
        unit="m",
        min_value=0.0,
        max_value=0.3
    ))

    # 流量条件
    odd.add_condition(OperatingCondition(
        condition_id="IGCU_OP_FLOW",
        name="过闸流量",
        description="闸门过流量范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="Q",
        unit="m³/s",
        min_value=0.0,
        max_value=500.0
    ))

    # 波涌边界
    surge_boundary = ODDBoundary(
        boundary_id="IGCU_BOUND_SURGE",
        name="波涌边界",
        description="波涌超限时暂停动作",
        boundary_type=BoundaryType.SOFT,
        violation_severity=ViolationSeverity.WARNING,
        response_action="暂停闸门动作,等待波涌平息",
        max_violation_duration=30.0
    )
    surge_boundary.add_condition(odd.conditions["IGCU_OP_SURGE"])
    odd.add_boundary(surge_boundary)

    # 漫堤边界
    overflow_boundary = ODDBoundary(
        boundary_id="IGCU_BOUND_OVERFLOW",
        name="漫堤边界",
        description="水位接近漫堤时紧急泄流",
        boundary_type=BoundaryType.HARD,
        violation_severity=ViolationSeverity.CRITICAL,
        response_action="紧急开大闸门"
    )
    overflow_boundary.add_condition(odd.conditions["IGCU_OP_Z_UP"])
    odd.add_boundary(overflow_boundary)

    return odd


# ============================================================
# 综合系统MBD工作流
# ============================================================

def create_hydraulic_mbd_workflow() -> MBDWorkflow:
    """创建水利系统完整MBD工作流"""
    workflow = MBDWorkflow("水利枢纽智能控制系统")

    # 添加阀门需求
    valve_requirements = [
        RequirementTrace(
            requirement_id="REQ_IVCU_001",
            requirement_text="阀门控制器信号到指令延迟应不超过50ms",
            source="系统规格书 4.1.1",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B",
            verification_method="TEST"
        ),
        RequirementTrace(
            requirement_id="REQ_IVCU_002",
            requirement_text="阀门关闭过程中压力峰值不超过管道设计压力的1.2倍",
            source="安全分析报告 HAZ-001",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_C",
            verification_method="TEST"
        ),
        RequirementTrace(
            requirement_id="REQ_IVCU_003",
            requirement_text="阀门控制应防止管道出现负压(断流弥合)",
            source="安全分析报告 HAZ-003",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),
        RequirementTrace(
            requirement_id="REQ_IVCU_004",
            requirement_text="断电时阀门应在倒流达到最大前关闭至30%以下",
            source="安全分析报告 HAZ-002",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),
        RequirementTrace(
            requirement_id="REQ_IVCU_005",
            requirement_text="阀门应支持两阶段液压关闭曲线以防止水锤",
            source="系统规格书 4.1.3",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_C"
        ),
    ]

    for req in valve_requirements:
        workflow.add_requirement(req)

    # 添加水泵需求
    pump_requirements = [
        RequirementTrace(
            requirement_id="REQ_IPCU_001",
            requirement_text="水泵启停应采用S形曲线,启停时间不小于60秒",
            source="系统规格书 4.2.1",
            priority="HIGH",
            safety_related=False
        ),
        RequirementTrace(
            requirement_id="REQ_IPCU_002",
            requirement_text="禁止水泵在马鞍区或汽蚀区持续运行",
            source="系统规格书 4.2.2",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),
        RequirementTrace(
            requirement_id="REQ_IPCU_003",
            requirement_text="水泵倒转速度不超过1.2倍额定转速,倒转时间不超过120秒",
            source="安全分析报告 HAZ-004",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),
        RequirementTrace(
            requirement_id="REQ_IPCU_004",
            requirement_text="振动超标时自动降负荷或停机",
            source="系统规格书 4.2.4",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),
    ]

    for req in pump_requirements:
        workflow.add_requirement(req)

    # 添加闸门需求
    gate_requirements = [
        RequirementTrace(
            requirement_id="REQ_IGCU_001",
            requirement_text="流量伺服控制实际流量与目标偏差不超过2%",
            source="系统规格书 4.3.1",
            priority="MEDIUM",
            safety_related=False
        ),
        RequirementTrace(
            requirement_id="REQ_IGCU_002",
            requirement_text="闸门调节过程中上游水位波涌幅度小于0.3m",
            source="系统规格书 4.3.2",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_A"
        ),
        RequirementTrace(
            requirement_id="REQ_IGCU_003",
            requirement_text="多孔闸门应实现自动均流防止局部冲刷",
            source="系统规格书 4.3.3",
            priority="MEDIUM",
            safety_related=False
        ),
    ]

    for req in gate_requirements:
        workflow.add_requirement(req)

    # 注册模型
    valve_model = ValveMBDModel()
    valve_model.initialize()
    workflow.register_model(valve_model)

    pump_model = PumpMBDModel()
    pump_model.initialize()
    workflow.register_model(pump_model)

    gate_model = GateMBDModel()
    gate_model.initialize()
    workflow.register_model(gate_model)

    return workflow


def create_hydraulic_safety_monitor() -> SafetyMonitor:
    """创建水利系统安全监控器"""
    monitor = SafetyMonitor("HYDRAULIC_SAFETY_MONITOR")

    # 添加阀门安全目标
    for goal in create_valve_safety_goals():
        monitor.add_safety_goal(goal)

    # 配置降级状态机
    for strategy in create_valve_degradation_strategies():
        monitor.degradation_sm.add_strategy(strategy)

    return monitor
