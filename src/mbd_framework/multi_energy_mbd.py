# -*- coding: utf-8 -*-
"""
多能互补系统MBD应用模块
Multi-Energy System MBD Application Module

为水风光储多能互补系统提供完整的MBD模型实现、ODD定义和降级策略
包括: 超级电容、锂电池、抽水蓄能、风电、光伏、常规水电、电网
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import math

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
# 储能系统MBD模型
# ============================================================

class SupercapacitorMBDModel(MBDModel):
    """超级电容MBD模型

    毫秒级响应，提供一次调频支撑
    """

    def __init__(self, model_id: str = "SC_MBD_001"):
        super().__init__(model_id, "超级电容储能模型", ModelType.PLANT)

        self._parameters = {
            # 容量参数
            'rated_power': 50.0,        # 额定功率 (MW)
            'rated_energy': 2.5,        # 额定能量 (MWh)
            'max_soc': 0.95,            # 最大SOC
            'min_soc': 0.20,            # 最小SOC

            # 响应参数
            'response_time': 0.005,     # 响应时间 (s)
            'ramp_rate': 1000.0,        # 爬坡率 (MW/s)

            # 下垂控制参数
            'droop_gain': 25.0,         # 下垂增益 (MW/Hz)
            'deadband': 0.02,           # 死区 (Hz)
            'freq_nominal': 50.0,       # 额定频率 (Hz)

            # 效率参数
            'charge_efficiency': 0.95,
            'discharge_efficiency': 0.95
        }

        self.artifact.inputs = ['grid_frequency', 'power_setpoint', 'enable']
        self.artifact.outputs = ['power_output', 'soc', 'mode', 'available_power']
        self.artifact.requirements = ['REQ_SC_001', 'REQ_SC_002', 'REQ_SC_003']

    def initialize(self):
        self._states = {
            'soc': 0.50,
            'power': 0.0,
            'energy': self._parameters['rated_energy'] * 0.50,
            'mode': 'STANDBY'
        }
        self._outputs = {
            'power_output': 0.0,
            'soc': 0.50,
            'mode': 'STANDBY',
            'available_power': self._parameters['rated_power']
        }

    def update(self, dt: float):
        freq = self._inputs.get('grid_frequency', 50.0)
        setpoint = self._inputs.get('power_setpoint', 0.0)
        enable = self._inputs.get('enable', True)

        if not enable:
            self._outputs['power_output'] = 0.0
            self._outputs['mode'] = 'DISABLED'
            return

        # 下垂控制
        freq_error = freq - self._parameters['freq_nominal']

        if abs(freq_error) > self._parameters['deadband']:
            # 频率偏低则放电，偏高则充电
            droop_power = -self._parameters['droop_gain'] * freq_error
        else:
            droop_power = 0.0

        # 结合设定值
        target_power = setpoint + droop_power

        # 功率限制
        target_power = max(-self._parameters['rated_power'],
                          min(self._parameters['rated_power'], target_power))

        # SOC限制
        soc = self._states['soc']
        if target_power > 0 and soc <= self._parameters['min_soc']:
            target_power = 0.0  # SOC过低，停止放电
        if target_power < 0 and soc >= self._parameters['max_soc']:
            target_power = 0.0  # SOC过高，停止充电

        # 爬坡限制
        max_change = self._parameters['ramp_rate'] * dt
        power_change = target_power - self._states['power']
        if abs(power_change) > max_change:
            power_change = math.copysign(max_change, power_change)

        new_power = self._states['power'] + power_change

        # 更新SOC
        if new_power > 0:  # 放电
            energy_change = new_power * dt / 3600 / self._parameters['discharge_efficiency']
        else:  # 充电
            energy_change = new_power * dt / 3600 * self._parameters['charge_efficiency']

        new_energy = self._states['energy'] - energy_change
        new_soc = new_energy / self._parameters['rated_energy']
        new_soc = max(0.0, min(1.0, new_soc))

        # 更新状态
        self._states['power'] = new_power
        self._states['soc'] = new_soc
        self._states['energy'] = new_energy
        self._states['mode'] = 'CHARGING' if new_power < 0 else ('DISCHARGING' if new_power > 0 else 'STANDBY')

        # 计算可用功率
        if new_soc <= self._parameters['min_soc']:
            available_discharge = 0.0
        else:
            available_discharge = self._parameters['rated_power']

        if new_soc >= self._parameters['max_soc']:
            available_charge = 0.0
        else:
            available_charge = self._parameters['rated_power']

        self._outputs = {
            'power_output': new_power,
            'soc': new_soc,
            'mode': self._states['mode'],
            'available_power': available_discharge,
            'available_charge': available_charge
        }

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


class BatteryMBDModel(MBDModel):
    """锂电池储能MBD模型

    秒级响应，提供二次调频支撑
    """

    def __init__(self, model_id: str = "BESS_MBD_001"):
        super().__init__(model_id, "锂电池储能模型", ModelType.PLANT)

        self._parameters = {
            'rated_power': 200.0,       # 额定功率 (MW)
            'rated_energy': 400.0,      # 额定能量 (MWh)
            'max_soc': 0.90,
            'min_soc': 0.10,
            'response_time': 0.2,       # 响应时间 (s)
            'ramp_rate': 200.0,         # 爬坡率 (MW/s)
            'filter_time_constant': 1.0,  # 滤波时间常数 (s)
            'charge_efficiency': 0.92,
            'discharge_efficiency': 0.92
        }

        self.artifact.inputs = ['power_setpoint', 'sc_power', 'enable']
        self.artifact.outputs = ['power_output', 'soc', 'mode', 'available_power']
        self.artifact.requirements = ['REQ_BESS_001', 'REQ_BESS_002']

    def initialize(self):
        self._states = {
            'soc': 0.50,
            'power': 0.0,
            'filtered_setpoint': 0.0,
            'mode': 'STANDBY'
        }
        self._outputs = {
            'power_output': 0.0,
            'soc': 0.50,
            'mode': 'STANDBY',
            'available_power': self._parameters['rated_power']
        }

    def update(self, dt: float):
        setpoint = self._inputs.get('power_setpoint', 0.0)
        sc_power = self._inputs.get('sc_power', 0.0)
        enable = self._inputs.get('enable', True)

        if not enable:
            self._outputs['power_output'] = 0.0
            self._outputs['mode'] = 'DISABLED'
            return

        # 低通滤波 - 接管SC的功率
        alpha = dt / (self._parameters['filter_time_constant'] + dt)
        filtered = self._states['filtered_setpoint'] + alpha * (setpoint - self._states['filtered_setpoint'])
        self._states['filtered_setpoint'] = filtered

        # 目标功率
        target_power = filtered

        # 功率和SOC限制
        target_power = max(-self._parameters['rated_power'],
                          min(self._parameters['rated_power'], target_power))

        soc = self._states['soc']
        if target_power > 0 and soc <= self._parameters['min_soc']:
            target_power = 0.0
        if target_power < 0 and soc >= self._parameters['max_soc']:
            target_power = 0.0

        # 爬坡限制
        max_change = self._parameters['ramp_rate'] * dt
        power_change = target_power - self._states['power']
        if abs(power_change) > max_change:
            power_change = math.copysign(max_change, power_change)

        new_power = self._states['power'] + power_change

        # 更新SOC
        if new_power > 0:
            energy_change = new_power * dt / 3600 / self._parameters['discharge_efficiency']
        else:
            energy_change = new_power * dt / 3600 * self._parameters['charge_efficiency']

        new_soc = self._states['soc'] - energy_change / self._parameters['rated_energy']
        new_soc = max(0.0, min(1.0, new_soc))

        self._states['power'] = new_power
        self._states['soc'] = new_soc
        self._states['mode'] = 'CHARGING' if new_power < 0 else ('DISCHARGING' if new_power > 0 else 'STANDBY')

        self._outputs = {
            'power_output': new_power,
            'soc': new_soc,
            'mode': self._states['mode'],
            'available_power': self._parameters['rated_power'] if new_soc > self._parameters['min_soc'] else 0.0
        }

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


class PSHMBDModel(MBDModel):
    """抽水蓄能电站MBD模型

    分钟级响应，提供大容量调节能力
    """

    def __init__(self, model_id: str = "PSH_MBD_001"):
        super().__init__(model_id, "抽水蓄能电站模型", ModelType.PLANT)

        self._parameters = {
            'rated_power_gen': 300.0,   # 发电额定功率 (MW)
            'rated_power_pump': 280.0,  # 抽水额定功率 (MW)
            'upper_reservoir': 10.0,    # 上库容量 (百万m³)
            'lower_reservoir': 12.0,    # 下库容量 (百万m³)
            'max_level': 0.95,          # 最大水位比
            'min_level': 0.15,          # 最小水位比
            'ramp_rate': 5.0,           # 爬坡率 (MW/min)
            'mode_switch_time': 300.0,  # 模式切换时间 (s)
            'min_run_time': 1800.0,     # 最小运行时间 (s)
            'min_stop_time': 900.0,     # 最小停机时间 (s)
            'gen_efficiency': 0.88,
            'pump_efficiency': 0.85
        }

        self.artifact.inputs = ['power_setpoint', 'mode_command', 'enable']
        self.artifact.outputs = ['power_output', 'upper_level', 'lower_level', 'mode', 'available_power']
        self.artifact.requirements = ['REQ_PSH_001', 'REQ_PSH_002', 'REQ_PSH_003']

    def initialize(self):
        self._states = {
            'upper_level': 0.50,
            'lower_level': 0.50,
            'power': 0.0,
            'mode': 'STOPPED',
            'mode_timer': 0.0,
            'run_timer': 0.0,
            'stop_timer': 0.0,
            'transition_target': None
        }
        self._outputs = {
            'power_output': 0.0,
            'upper_level': 0.50,
            'lower_level': 0.50,
            'mode': 'STOPPED',
            'available_power': self._parameters['rated_power_gen']
        }

    def update(self, dt: float):
        setpoint = self._inputs.get('power_setpoint', 0.0)
        mode_cmd = self._inputs.get('mode_command', None)
        enable = self._inputs.get('enable', True)

        if not enable:
            self._outputs['power_output'] = 0.0
            self._outputs['mode'] = 'DISABLED'
            return

        mode = self._states['mode']
        upper_level = self._states['upper_level']
        lower_level = self._states['lower_level']

        # 模式切换逻辑
        if mode_cmd and mode_cmd != mode:
            if self._can_switch_mode(mode, mode_cmd):
                self._states['mode'] = 'TRANSITIONING'
                self._states['transition_target'] = mode_cmd
                self._states['mode_timer'] = 0.0

        # 模式转换中
        if mode == 'TRANSITIONING':
            self._states['mode_timer'] += dt
            if self._states['mode_timer'] >= self._parameters['mode_switch_time']:
                self._states['mode'] = self._states['transition_target']
                self._states['run_timer'] = 0.0
            self._states['power'] = 0.0

        # 发电模式
        elif mode == 'GENERATING':
            self._states['run_timer'] += dt
            if upper_level <= self._parameters['min_level']:
                setpoint = 0.0  # 水位过低

            target = max(0, min(self._parameters['rated_power_gen'], setpoint))
            max_change = self._parameters['ramp_rate'] / 60 * dt
            power_change = target - self._states['power']
            if abs(power_change) > max_change:
                power_change = math.copysign(max_change, power_change)
            self._states['power'] = self._states['power'] + power_change

            # 更新水位
            water_flow = self._states['power'] / self._parameters['gen_efficiency'] * dt / 3600
            self._states['upper_level'] -= water_flow / self._parameters['upper_reservoir']
            self._states['lower_level'] += water_flow / self._parameters['lower_reservoir']

        # 抽水模式
        elif mode == 'PUMPING':
            self._states['run_timer'] += dt
            if lower_level <= self._parameters['min_level']:
                setpoint = 0.0
            if upper_level >= self._parameters['max_level']:
                setpoint = 0.0

            target = max(0, min(self._parameters['rated_power_pump'], abs(setpoint)))
            max_change = self._parameters['ramp_rate'] / 60 * dt
            power_change = target - abs(self._states['power'])
            if abs(power_change) > max_change:
                power_change = math.copysign(max_change, power_change)
            self._states['power'] = -(abs(self._states['power']) + power_change)

            # 更新水位
            water_flow = abs(self._states['power']) * self._parameters['pump_efficiency'] * dt / 3600
            self._states['upper_level'] += water_flow / self._parameters['upper_reservoir']
            self._states['lower_level'] -= water_flow / self._parameters['lower_reservoir']

        # 停机模式
        elif mode == 'STOPPED':
            self._states['stop_timer'] += dt
            self._states['power'] = 0.0

        # 限制水位范围
        self._states['upper_level'] = max(0.0, min(1.0, self._states['upper_level']))
        self._states['lower_level'] = max(0.0, min(1.0, self._states['lower_level']))

        # 计算可用功率
        if upper_level > self._parameters['min_level']:
            available_gen = self._parameters['rated_power_gen']
        else:
            available_gen = 0.0

        if lower_level > self._parameters['min_level'] and upper_level < self._parameters['max_level']:
            available_pump = self._parameters['rated_power_pump']
        else:
            available_pump = 0.0

        self._outputs = {
            'power_output': self._states['power'],
            'upper_level': self._states['upper_level'],
            'lower_level': self._states['lower_level'],
            'mode': self._states['mode'],
            'available_power': available_gen,
            'available_pump': available_pump
        }

    def _can_switch_mode(self, current: str, target: str) -> bool:
        """检查是否可以切换模式"""
        if current == 'TRANSITIONING':
            return False
        if current == 'GENERATING' and self._states['run_timer'] < self._parameters['min_run_time']:
            return False
        if current == 'PUMPING' and self._states['run_timer'] < self._parameters['min_run_time']:
            return False
        if current == 'STOPPED' and self._states['stop_timer'] < self._parameters['min_stop_time']:
            return False
        return True

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


# ============================================================
# 分层控制器MBD模型
# ============================================================

class HierarchicalControllerMBDModel(MBDModel):
    """分层控制器MBD模型

    实现三层响应链:
    - 第一层: SC下垂控制 (毫秒级)
    - 第二层: BESS滤波控制 (秒级)
    - 第三层: PSH/水电MPC协调 (分钟级)
    """

    def __init__(self, model_id: str = "HIER_CTRL_MBD_001"):
        super().__init__(model_id, "分层协调控制器模型", ModelType.CONTROLLER)

        self._parameters = {
            # 频率参数
            'freq_nominal': 50.0,
            'freq_deadband': 0.02,

            # SC下垂参数
            'sc_droop_gain': 25.0,

            # BESS滤波参数
            'bess_filter_tau': 1.0,

            # MPC参数
            'mpc_horizon': 24,
            'mpc_interval': 300.0,  # 5分钟

            # 协调参数
            'power_threshold_sc': 50.0,
            'power_threshold_bess': 200.0
        }

        self.artifact.inputs = [
            'grid_frequency', 'load_demand', 'renewable_power',
            'sc_soc', 'bess_soc', 'psh_level'
        ]
        self.artifact.outputs = [
            'sc_setpoint', 'bess_setpoint', 'psh_setpoint',
            'hydro_setpoint', 'coordination_mode'
        ]
        self.artifact.requirements = [
            'REQ_CTRL_001',  # 响应链无断裂
            'REQ_CTRL_002',  # 频率偏差<=0.5Hz
            'REQ_CTRL_003'   # 储能SOC保持安全范围
        ]

    def initialize(self):
        self._states = {
            'sc_power': 0.0,
            'bess_power': 0.0,
            'psh_power': 0.0,
            'mpc_timer': 0.0,
            'coordination_mode': 'NORMAL'
        }
        self._outputs = {
            'sc_setpoint': 0.0,
            'bess_setpoint': 0.0,
            'psh_setpoint': 0.0,
            'hydro_setpoint': 0.0,
            'coordination_mode': 'NORMAL'
        }

    def update(self, dt: float):
        freq = self._inputs.get('grid_frequency', 50.0)
        load = self._inputs.get('load_demand', 0.0)
        renewable = self._inputs.get('renewable_power', 0.0)
        sc_soc = self._inputs.get('sc_soc', 0.5)
        bess_soc = self._inputs.get('bess_soc', 0.5)
        psh_level = self._inputs.get('psh_level', 0.5)

        # 计算功率不平衡
        imbalance = load - renewable

        # 第一层: SC下垂控制
        freq_error = freq - self._parameters['freq_nominal']
        if abs(freq_error) > self._parameters['freq_deadband']:
            sc_droop = -self._parameters['sc_droop_gain'] * freq_error
        else:
            sc_droop = 0.0

        # SC功率限制
        if sc_soc < 0.25:
            sc_setpoint = min(0, sc_droop)  # 只充电
        elif sc_soc > 0.90:
            sc_setpoint = max(0, sc_droop)  # 只放电
        else:
            sc_setpoint = sc_droop

        sc_setpoint = max(-self._parameters['power_threshold_sc'],
                         min(self._parameters['power_threshold_sc'], sc_setpoint))

        # 第二层: BESS滤波控制
        alpha = dt / (self._parameters['bess_filter_tau'] + dt)
        bess_target = imbalance - sc_setpoint
        bess_setpoint = self._states['bess_power'] + alpha * (bess_target - self._states['bess_power'])

        # BESS功率限制
        if bess_soc < 0.15:
            bess_setpoint = min(0, bess_setpoint)
        elif bess_soc > 0.85:
            bess_setpoint = max(0, bess_setpoint)

        bess_setpoint = max(-self._parameters['power_threshold_bess'],
                           min(self._parameters['power_threshold_bess'], bess_setpoint))

        # 第三层: MPC协调 (简化实现)
        self._states['mpc_timer'] += dt
        if self._states['mpc_timer'] >= self._parameters['mpc_interval']:
            self._states['mpc_timer'] = 0.0
            # MPC优化计算 (简化)
            remaining = imbalance - sc_setpoint - bess_setpoint
            psh_setpoint = remaining * 0.6
            hydro_setpoint = remaining * 0.4
        else:
            psh_setpoint = self._states['psh_power']
            hydro_setpoint = self._outputs.get('hydro_setpoint', 0.0)

        # 确定协调模式
        if abs(freq_error) > 0.3:
            coordination_mode = 'EMERGENCY'
        elif abs(freq_error) > 0.1:
            coordination_mode = 'ACTIVE'
        else:
            coordination_mode = 'NORMAL'

        # 更新状态
        self._states['sc_power'] = sc_setpoint
        self._states['bess_power'] = bess_setpoint
        self._states['psh_power'] = psh_setpoint
        self._states['coordination_mode'] = coordination_mode

        self._outputs = {
            'sc_setpoint': sc_setpoint,
            'bess_setpoint': bess_setpoint,
            'psh_setpoint': psh_setpoint,
            'hydro_setpoint': hydro_setpoint,
            'coordination_mode': coordination_mode
        }

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


# ============================================================
# 多能互补系统ODD定义
# ============================================================

def create_multi_energy_system_odd() -> ODDDefinition:
    """创建多能互补系统完整ODD定义"""
    odd = ODDDefinition(
        odd_id="ODD_MULTI_ENERGY_SYSTEM",
        name="水风光储多能互补系统ODD",
        description="多能互补系统的完整运行设计域定义"
    )

    # 电网频率条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_GRID_FREQ",
        name="电网频率",
        description="电网运行频率范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="grid_frequency",
        unit="Hz",
        min_value=49.0,
        max_value=51.0,
        nominal_value=50.0
    ))

    # 频率偏差条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_FREQ_DEVIATION",
        name="频率偏差",
        description="频率偏离额定值的范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="freq_deviation",
        unit="Hz",
        min_value=-0.5,
        max_value=0.5
    ))

    # 超级电容SOC条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_SC_SOC",
        name="超级电容SOC",
        description="超级电容荷电状态范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="sc_soc",
        unit="%",
        min_value=20.0,
        max_value=95.0,
        nominal_value=50.0
    ))

    # 锂电池SOC条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_BESS_SOC",
        name="锂电池SOC",
        description="锂电池荷电状态范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="bess_soc",
        unit="%",
        min_value=10.0,
        max_value=90.0,
        nominal_value=50.0
    ))

    # 抽水蓄能上库水位条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_PSH_UPPER_LEVEL",
        name="PSH上库水位",
        description="抽水蓄能上库水位范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="psh_upper_level",
        unit="%",
        min_value=15.0,
        max_value=95.0,
        nominal_value=50.0
    ))

    # 功率平衡条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_POWER_IMBALANCE",
        name="功率不平衡",
        description="发电与负荷的功率差",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="power_imbalance",
        unit="MW",
        min_value=-500.0,
        max_value=500.0
    ))

    # 风速条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_WIND_SPEED",
        name="风速",
        description="风电场风速范围",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="wind_speed",
        unit="m/s",
        min_value=0.0,
        max_value=30.0
    ))

    # 太阳辐照度条件
    odd.add_condition(OperatingCondition(
        condition_id="ME_SOLAR_IRRADIANCE",
        name="太阳辐照度",
        description="光伏电站辐照度范围",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="solar_irradiance",
        unit="W/m²",
        min_value=0.0,
        max_value=1200.0
    ))

    # 添加边界
    # 频率硬边界
    freq_boundary = ODDBoundary(
        boundary_id="ME_BOUND_FREQ",
        name="频率安全边界",
        description="电网频率必须保持在安全范围内",
        boundary_type=BoundaryType.HARD,
        violation_severity=ViolationSeverity.CRITICAL,
        response_action="启动所有储能快速响应",
        recovery_procedure="频率恢复后逐步退出调频",
        max_violation_duration=0.0
    )
    freq_boundary.add_condition(odd.conditions["ME_GRID_FREQ"])
    odd.add_boundary(freq_boundary)

    # SOC软边界
    soc_boundary = ODDBoundary(
        boundary_id="ME_BOUND_SOC",
        name="储能SOC边界",
        description="储能SOC应保持在安全范围",
        boundary_type=BoundaryType.SOFT,
        violation_severity=ViolationSeverity.WARNING,
        response_action="调整充放电策略",
        max_violation_duration=300.0
    )
    soc_boundary.add_condition(odd.conditions["ME_SC_SOC"])
    soc_boundary.add_condition(odd.conditions["ME_BESS_SOC"])
    odd.add_boundary(soc_boundary)

    # PSH水位边界
    psh_boundary = ODDBoundary(
        boundary_id="ME_BOUND_PSH_LEVEL",
        name="抽水蓄能水位边界",
        description="上下库水位约束",
        boundary_type=BoundaryType.SOFT,
        violation_severity=ViolationSeverity.WARNING,
        response_action="调整抽发策略",
        max_violation_duration=600.0
    )
    psh_boundary.add_condition(odd.conditions["ME_PSH_UPPER_LEVEL"])
    odd.add_boundary(psh_boundary)

    return odd


# ============================================================
# 多能互补系统安全目标和降级策略
# ============================================================

def create_multi_energy_safety_goals() -> List[SafetyGoal]:
    """创建多能互补系统安全目标"""
    goals = []

    # SG1: 频率稳定
    goals.append(SafetyGoal(
        goal_id="SG_ME_FREQ_STABILITY",
        name="频率稳定性",
        description="保持电网频率在安全范围内运行",
        asil_level=ASILLevel.ASIL_C,
        sil_level=SafetyLevel.SIL_2,
        hazard_id="HAZ_ME_001",
        hazard_description="频率失稳可能导致大面积停电",
        exposure="E4",
        controllability="C2",
        severity="S3",
        safe_state="启动所有可用调频资源",
        fault_tolerant_time=0.5,
        max_response_time=0.1,
        requirements=["REQ_ME_FREQ_001", "REQ_ME_FREQ_002"]
    ))

    # SG2: 响应链完整
    goals.append(SafetyGoal(
        goal_id="SG_ME_RESPONSE_CHAIN",
        name="响应链完整性",
        description="确保SC-BESS-PSH响应链无断裂",
        asil_level=ASILLevel.ASIL_B,
        sil_level=SafetyLevel.SIL_1,
        hazard_id="HAZ_ME_002",
        hazard_description="响应链断裂导致调频失效",
        safe_state="备用储能接管",
        requirements=["REQ_ME_CHAIN_001"]
    ))

    # SG3: 储能保护
    goals.append(SafetyGoal(
        goal_id="SG_ME_STORAGE_PROTECTION",
        name="储能设备保护",
        description="防止储能设备过充过放",
        asil_level=ASILLevel.ASIL_B,
        sil_level=SafetyLevel.SIL_1,
        hazard_id="HAZ_ME_003",
        hazard_description="过充过放损坏储能设备",
        safe_state="停止充放电",
        requirements=["REQ_ME_SOC_001"]
    ))

    return goals


def create_multi_energy_degradation_strategies() -> List[DegradationStrategy]:
    """创建多能互补系统降级策略"""
    strategies = []

    # 策略1: SC故障
    strategies.append(DegradationStrategy(
        strategy_id="ME_DEG_SC_FAULT",
        name="超级电容故障降级",
        description="SC故障时BESS直接接管一次调频",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["ME_FAULT_SC_TRIP", "ME_FAULT_SC_COMM"],
        actions=[
            "BESS切换到下垂控制模式",
            "增加BESS响应增益",
            "降低系统响应时间要求"
        ],
        disabled_features=["毫秒级快速响应"],
        parameter_overrides={
            'bess_droop_enabled': True,
            'bess_droop_gain': 30.0
        }
    ))

    # 策略2: BESS故障
    strategies.append(DegradationStrategy(
        strategy_id="ME_DEG_BESS_FAULT",
        name="锂电池故障降级",
        description="BESS故障时由SC和PSH协同补偿",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["ME_FAULT_BESS_TRIP", "ME_FAULT_BESS_SOC"],
        actions=[
            "增加SC出力",
            "提前启动PSH",
            "请求常规水电支援"
        ],
        disabled_features=["秒级平滑调节"],
        parameter_overrides={
            'sc_power_limit': 60.0,
            'psh_advance_start': True
        }
    ))

    # 策略3: PSH故障
    strategies.append(DegradationStrategy(
        strategy_id="ME_DEG_PSH_FAULT",
        name="抽水蓄能故障降级",
        description="PSH故障时增加其他资源出力",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["ME_FAULT_PSH_TRIP", "ME_FAULT_PSH_LEVEL"],
        actions=[
            "增加常规水电出力",
            "限制新能源波动",
            "请求外部功率支援"
        ]
    ))

    # 策略4: 频率严重偏差
    strategies.append(DegradationStrategy(
        strategy_id="ME_DEG_FREQ_EMERGENCY",
        name="频率紧急响应",
        description="频率严重偏差时的紧急措施",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L3,
        trigger_faults=["ME_FAULT_FREQ_HIGH", "ME_FAULT_FREQ_LOW"],
        trigger_conditions={'freq_deviation': {'min': -0.5, 'max': 0.5}},
        actions=[
            "所有储能全功率响应",
            "PSH紧急投入",
            "切除非关键负荷",
            "启动备用机组"
        ],
        parameter_overrides={
            'sc_power_limit': 1.2,  # 120%过载
            'bess_power_limit': 1.1
        }
    ))

    # 策略5: 多重故障安全状态
    strategies.append(DegradationStrategy(
        strategy_id="ME_DEG_SAFE_STATE",
        name="多重故障安全状态",
        description="多个关键组件故障时进入安全状态",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.SAFE_STATE,
        trigger_faults=["ME_FAULT_MULTIPLE", "ME_FAULT_COMM_TOTAL"],
        actions=[
            "所有储能进入本地控制",
            "维持当前出力",
            "断开自动调度",
            "等待人工干预"
        ],
        recovery_actions=["故障排除", "系统检查", "逐步恢复"]
    ))

    return strategies


# ============================================================
# 完整MBD工作流
# ============================================================

def create_multi_energy_mbd_workflow() -> MBDWorkflow:
    """创建多能互补系统完整MBD工作流"""
    workflow = MBDWorkflow("水风光储多能互补系统")

    # 添加需求
    requirements = [
        # 频率控制需求
        RequirementTrace(
            requirement_id="REQ_ME_FREQ_001",
            requirement_text="系统应能在500ms内将频率偏差控制在±0.5Hz以内",
            source="调度规范 3.1",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_C"
        ),
        RequirementTrace(
            requirement_id="REQ_ME_FREQ_002",
            requirement_text="正常运行时频率偏差应控制在±0.2Hz以内",
            source="调度规范 3.2",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),

        # 响应链需求
        RequirementTrace(
            requirement_id="REQ_ME_CHAIN_001",
            requirement_text="SC-BESS-PSH响应链应无断裂,功率移交平滑",
            source="系统规格书 4.1",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),

        # 储能SOC需求
        RequirementTrace(
            requirement_id="REQ_ME_SOC_001",
            requirement_text="储能SOC应维持在安全范围内运行",
            source="设备规范 5.1",
            priority="MEDIUM",
            safety_related=True,
            asil_level="ASIL_B"
        ),

        # SC需求
        RequirementTrace(
            requirement_id="REQ_SC_001",
            requirement_text="超级电容响应时间应小于10ms",
            source="系统规格书 4.2.1",
            priority="HIGH"
        ),
        RequirementTrace(
            requirement_id="REQ_SC_002",
            requirement_text="超级电容应实现下垂控制,死区0.02Hz",
            source="系统规格书 4.2.2",
            priority="HIGH"
        ),

        # BESS需求
        RequirementTrace(
            requirement_id="REQ_BESS_001",
            requirement_text="锂电池响应时间应小于200ms",
            source="系统规格书 4.3.1",
            priority="HIGH"
        ),
        RequirementTrace(
            requirement_id="REQ_BESS_002",
            requirement_text="锂电池应平滑接管SC功率",
            source="系统规格书 4.3.2",
            priority="HIGH"
        ),

        # PSH需求
        RequirementTrace(
            requirement_id="REQ_PSH_001",
            requirement_text="抽水蓄能启动时间应小于5分钟",
            source="系统规格书 4.4.1",
            priority="MEDIUM"
        ),
        RequirementTrace(
            requirement_id="REQ_PSH_002",
            requirement_text="抽水蓄能模式切换时间应小于5分钟",
            source="系统规格书 4.4.2",
            priority="MEDIUM"
        ),
    ]

    for req in requirements:
        workflow.add_requirement(req)

    # 注册模型
    sc_model = SupercapacitorMBDModel()
    sc_model.initialize()
    workflow.register_model(sc_model)

    bess_model = BatteryMBDModel()
    bess_model.initialize()
    workflow.register_model(bess_model)

    psh_model = PSHMBDModel()
    psh_model.initialize()
    workflow.register_model(psh_model)

    controller_model = HierarchicalControllerMBDModel()
    controller_model.initialize()
    workflow.register_model(controller_model)

    return workflow


def create_multi_energy_safety_monitor() -> SafetyMonitor:
    """创建多能互补系统安全监控器"""
    monitor = SafetyMonitor("MULTI_ENERGY_SAFETY_MONITOR")

    # 添加安全目标
    for goal in create_multi_energy_safety_goals():
        monitor.add_safety_goal(goal)

    # 配置降级状态机
    for strategy in create_multi_energy_degradation_strategies():
        monitor.degradation_sm.add_strategy(strategy)

    return monitor
