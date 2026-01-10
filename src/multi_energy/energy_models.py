# -*- coding: utf-8 -*-
"""
多能互补系统能源组件模型
Energy Component Models for Multi-Energy Complementary System

包含以下能源组件的物理模型:
1. WindTurbineModel - 风力发电机模型
2. PhotovoltaicModel - 光伏发电模型
3. SupercapacitorModel - 超级电容模型
4. BatteryStorageModel - 锂电池储能模型
5. PumpedStorageModel - 抽水蓄能电站模型(非线性)
6. ConventionalHydroModel - 常规梯级水电站模型
7. GridModel - 电网模型(频率动态)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
from enum import Enum, auto
from abc import ABC, abstractmethod


# ==================== 基础数据结构 ====================

@dataclass
class EnergyState:
    """能源组件通用状态"""
    time: float = 0.0  # 当前时间(s)
    power_output: float = 0.0  # 输出功率(MW)
    power_setpoint: float = 0.0  # 功率设定值(MW)
    available: bool = True  # 是否可用
    efficiency: float = 1.0  # 当前效率


@dataclass
class WindCondition:
    """风况参数"""
    wind_speed: float = 8.0  # 风速(m/s)
    air_density: float = 1.225  # 空气密度(kg/m³)
    turbulence_intensity: float = 0.1  # 湍流强度


@dataclass
class SolarCondition:
    """光照条件"""
    irradiance: float = 800.0  # 辐照度(W/m²)
    temperature: float = 25.0  # 环境温度(°C)
    cloud_factor: float = 1.0  # 云遮系数(0-1)


@dataclass
class HydraulicHead:
    """水力水头参数"""
    gross_head: float = 100.0  # 总水头(m)
    head_loss: float = 5.0  # 水头损失(m)

    @property
    def net_head(self) -> float:
        """有效水头"""
        return self.gross_head - self.head_loss


# ==================== 抽象基类 ====================

class EnergyComponent(ABC):
    """能源组件抽象基类"""

    def __init__(self, name: str, rated_power: float):
        """
        Args:
            name: 组件名称
            rated_power: 额定功率(MW)
        """
        self.name = name
        self.rated_power = rated_power
        self.state = EnergyState()
        self._enabled = True

    @abstractmethod
    def step(self, dt: float, **kwargs) -> EnergyState:
        """
        执行一步仿真

        Args:
            dt: 时间步长(s)
            **kwargs: 额外参数

        Returns:
            更新后的状态
        """
        pass

    @abstractmethod
    def set_power_setpoint(self, power: float) -> bool:
        """设置功率目标值"""
        pass

    def enable(self):
        """启用组件"""
        self._enabled = True
        self.state.available = True

    def disable(self):
        """禁用组件"""
        self._enabled = False
        self.state.available = False

    def get_power(self) -> float:
        """获取当前输出功率"""
        return self.state.power_output


# ==================== 风力发电模型 ====================

class WindTurbineModel(EnergyComponent):
    """
    风力发电机模型

    采用简化的功率曲线模型:
    - 切入风速: v_in
    - 额定风速: v_rated
    - 切出风速: v_out

    功率计算: P = 0.5 * ρ * A * Cp * v³
    其中Cp为风能利用系数(Betz极限~0.593)
    """

    def __init__(
        self,
        name: str = "WT",
        rated_power: float = 50.0,  # MW
        rotor_diameter: float = 126.0,  # m
        v_cut_in: float = 3.0,  # m/s
        v_rated: float = 12.0,  # m/s
        v_cut_out: float = 25.0,  # m/s
        cp_max: float = 0.45,  # 最大风能利用系数
        time_constant: float = 2.0  # 响应时间常数(s)
    ):
        super().__init__(name, rated_power)
        self.rotor_diameter = rotor_diameter
        self.rotor_area = np.pi * (rotor_diameter / 2) ** 2
        self.v_cut_in = v_cut_in
        self.v_rated = v_rated
        self.v_cut_out = v_cut_out
        self.cp_max = cp_max
        self.time_constant = time_constant

        # 内部状态
        self._current_wind_speed = 0.0
        self._power_available = 0.0

    def _calculate_power_curve(self, wind_speed: float, air_density: float) -> float:
        """
        计算给定风速下的可用功率

        Args:
            wind_speed: 风速(m/s)
            air_density: 空气密度(kg/m³)

        Returns:
            可用功率(MW)
        """
        if wind_speed < self.v_cut_in or wind_speed > self.v_cut_out:
            return 0.0

        if wind_speed >= self.v_rated:
            return self.rated_power

        # 立方关系区间
        # 考虑贝茨极限的风能转换
        power_theoretical = 0.5 * air_density * self.rotor_area * self.cp_max * (wind_speed ** 3)
        power_mw = power_theoretical / 1e6  # 转换为MW

        return min(power_mw, self.rated_power)

    def set_power_setpoint(self, power: float) -> bool:
        """
        设置功率目标(风机通常不接受功率设定，除非curtailment)
        """
        self.state.power_setpoint = min(power, self._power_available)
        return True

    def step(self, dt: float, wind_condition: Optional[WindCondition] = None) -> EnergyState:
        """
        执行一步仿真

        Args:
            dt: 时间步长(s)
            wind_condition: 风况参数
        """
        if not self._enabled:
            self.state.power_output = 0.0
            return self.state

        if wind_condition is None:
            wind_condition = WindCondition()

        self._current_wind_speed = wind_condition.wind_speed

        # 计算可用功率
        self._power_available = self._calculate_power_curve(
            wind_condition.wind_speed,
            wind_condition.air_density
        )

        # 添加湍流引起的功率波动
        turbulence_effect = 1.0 + wind_condition.turbulence_intensity * np.random.normal(0, 0.1)
        self._power_available *= max(0, turbulence_effect)

        # 一阶惯性响应
        target_power = min(self.state.power_setpoint, self._power_available)
        alpha = 1 - np.exp(-dt / self.time_constant)
        self.state.power_output += alpha * (target_power - self.state.power_output)

        # 更新效率(简化模型)
        if self._power_available > 0:
            self.state.efficiency = self.state.power_output / self._power_available

        self.state.time += dt
        return self.state

    def get_available_power(self) -> float:
        """获取当前风况下的可用功率"""
        return self._power_available


# ==================== 光伏发电模型 ====================

class PhotovoltaicModel(EnergyComponent):
    """
    光伏发电模型

    基于单二极管等效电路模型简化:
    P = η * A * G * (1 - β*(T - T_ref))

    其中:
    - η: 组件效率
    - A: 总面积
    - G: 辐照度
    - β: 温度系数
    - T_ref: 参考温度(25°C)
    """

    def __init__(
        self,
        name: str = "PV",
        rated_power: float = 30.0,  # MW (峰值功率)
        efficiency: float = 0.20,  # 组件效率
        temp_coefficient: float = -0.004,  # 温度系数(/°C)
        area: float = 150000.0,  # 光伏阵列总面积(m²)
        time_constant: float = 0.1  # 响应时间常数(s)
    ):
        super().__init__(name, rated_power)
        self.efficiency = efficiency
        self.temp_coefficient = temp_coefficient
        self.area = area
        self.time_constant = time_constant
        self.temp_ref = 25.0  # 参考温度(°C)

        # 内部状态
        self._power_available = 0.0
        self._current_irradiance = 0.0

    def _calculate_power(self, solar_condition: SolarCondition) -> float:
        """
        计算当前光照条件下的可用功率

        Args:
            solar_condition: 光照条件

        Returns:
            可用功率(MW)
        """
        # 温度修正系数
        temp_factor = 1 + self.temp_coefficient * (solar_condition.temperature - self.temp_ref)
        temp_factor = max(0.7, min(1.1, temp_factor))  # 限幅

        # 功率计算
        power_w = (self.efficiency * self.area *
                   solar_condition.irradiance *
                   solar_condition.cloud_factor *
                   temp_factor)

        power_mw = power_w / 1e6
        return min(power_mw, self.rated_power)

    def set_power_setpoint(self, power: float) -> bool:
        """设置功率目标(光伏curtailment)"""
        self.state.power_setpoint = min(power, self._power_available)
        return True

    def step(self, dt: float, solar_condition: Optional[SolarCondition] = None) -> EnergyState:
        """执行一步仿真"""
        if not self._enabled:
            self.state.power_output = 0.0
            return self.state

        if solar_condition is None:
            solar_condition = SolarCondition()

        self._current_irradiance = solar_condition.irradiance
        self._power_available = self._calculate_power(solar_condition)

        # 快速响应(MPPT控制器)
        target_power = min(self.state.power_setpoint, self._power_available)
        alpha = 1 - np.exp(-dt / self.time_constant)
        self.state.power_output += alpha * (target_power - self.state.power_output)

        # 更新效率
        if self._power_available > 0:
            self.state.efficiency = self.state.power_output / self._power_available

        self.state.time += dt
        return self.state

    def get_available_power(self) -> float:
        """获取当前光照条件下的可用功率"""
        return self._power_available


# ==================== 超级电容模型 ====================

class SupercapacitorModel(EnergyComponent):
    """
    超级电容(SC)储能模型

    特点:
    - 高功率密度，低能量密度
    - 快速响应(毫秒级)
    - 高循环寿命

    模型:
    - 等效电路: RC串联模型
    - 能量: E = 0.5 * C * V²
    - SOC = (V - V_min) / (V_max - V_min)
    """

    def __init__(
        self,
        name: str = "SC",
        rated_power: float = 10.0,  # MW
        rated_energy: float = 0.5,  # MWh
        efficiency: float = 0.95,  # 充放电效率
        voltage_max: float = 800.0,  # V
        voltage_min: float = 400.0,  # V (最低工作电压)
        time_constant: float = 0.01,  # 响应时间常数(s) - 毫秒级
        self_discharge_rate: float = 0.02  # 自放电率(/day)
    ):
        super().__init__(name, rated_power)
        self.rated_energy = rated_energy
        self.efficiency = efficiency
        self.voltage_max = voltage_max
        self.voltage_min = voltage_min
        self.time_constant = time_constant
        self.self_discharge_rate = self_discharge_rate

        # 计算等效电容
        # E = 0.5 * C * (Vmax² - Vmin²)
        self.capacitance = 2 * rated_energy * 1e6 / (voltage_max**2 - voltage_min**2)  # F

        # 状态变量
        self._soc = 0.5  # 初始SOC 50%
        self._voltage = self._soc_to_voltage(self._soc)
        self._power_command = 0.0

    def _soc_to_voltage(self, soc: float) -> float:
        """SOC转电压"""
        return self.voltage_min + soc * (self.voltage_max - self.voltage_min)

    def _voltage_to_soc(self, voltage: float) -> float:
        """电压转SOC"""
        return (voltage - self.voltage_min) / (self.voltage_max - self.voltage_min)

    def get_soc(self) -> float:
        """获取当前SOC"""
        return self._soc

    def set_power_setpoint(self, power: float) -> bool:
        """
        设置功率指令

        Args:
            power: 功率指令(MW), 正值放电, 负值充电
        """
        # 检查SOC限制
        if power > 0 and self._soc < 0.05:  # 放电但SOC过低
            power = 0
        elif power < 0 and self._soc > 0.95:  # 充电但SOC过高
            power = 0

        # 功率限幅
        power = np.clip(power, -self.rated_power, self.rated_power)
        self._power_command = power
        self.state.power_setpoint = power
        return True

    def step(self, dt: float, **kwargs) -> EnergyState:
        """
        执行一步仿真

        Args:
            dt: 时间步长(s)
        """
        if not self._enabled:
            self.state.power_output = 0.0
            return self.state

        # 快速功率响应(一阶惯性)
        alpha = 1 - np.exp(-dt / self.time_constant)
        self.state.power_output += alpha * (self._power_command - self.state.power_output)

        # 计算能量变化
        # 正功率=放电, 负功率=充电
        power_actual = self.state.power_output
        if power_actual > 0:  # 放电
            energy_change = -power_actual * dt / 3600 / self.efficiency  # MWh
        else:  # 充电
            energy_change = -power_actual * dt / 3600 * self.efficiency  # MWh

        # 更新SOC
        soc_change = energy_change / self.rated_energy
        self._soc = np.clip(self._soc + soc_change, 0.0, 1.0)

        # 自放电
        self._soc *= (1 - self.self_discharge_rate * dt / 86400)

        # 更新电压
        self._voltage = self._soc_to_voltage(self._soc)

        # 更新效率
        self.state.efficiency = self.efficiency
        self.state.time += dt

        return self.state

    def get_available_power_range(self) -> Tuple[float, float]:
        """
        获取当前可用功率范围

        Returns:
            (最大充电功率(负值), 最大放电功率(正值))
        """
        # 根据SOC限制可用功率
        max_discharge = self.rated_power * min(1.0, self._soc / 0.1)
        max_charge = -self.rated_power * min(1.0, (1 - self._soc) / 0.1)
        return (max_charge, max_discharge)


# ==================== 锂电池储能模型 ====================

class BatteryStorageModel(EnergyComponent):
    """
    锂电池储能系统(BESS)模型

    特点:
    - 中等功率密度和能量密度
    - 秒级响应
    - 需考虑温度和老化

    模型:
    - 等效电路: 二阶RC模型简化
    - SOC动态: dSOC/dt = -I/(C_bat)
    - 效率随SOC变化
    """

    def __init__(
        self,
        name: str = "BESS",
        rated_power: float = 20.0,  # MW
        rated_energy: float = 40.0,  # MWh (2h容量)
        efficiency_charge: float = 0.95,
        efficiency_discharge: float = 0.95,
        soc_min: float = 0.1,  # 最低SOC
        soc_max: float = 0.9,  # 最高SOC
        time_constant: float = 0.5,  # 响应时间常数(s)
        ramp_rate: float = 0.2  # 爬坡速率(p.u./s)
    ):
        super().__init__(name, rated_power)
        self.rated_energy = rated_energy
        self.efficiency_charge = efficiency_charge
        self.efficiency_discharge = efficiency_discharge
        self.soc_min = soc_min
        self.soc_max = soc_max
        self.time_constant = time_constant
        self.ramp_rate = ramp_rate

        # 状态变量
        self._soc = 0.5  # 初始SOC 50%
        self._temperature = 25.0  # 电池温度(°C)
        self._power_command = 0.0
        self._cycle_count = 0  # 循环计数

    def get_soc(self) -> float:
        """获取当前SOC"""
        return self._soc

    def get_temperature(self) -> float:
        """获取电池温度"""
        return self._temperature

    def _get_efficiency(self, power: float) -> float:
        """
        获取当前效率(考虑SOC影响)
        """
        base_eff = self.efficiency_discharge if power > 0 else self.efficiency_charge

        # SOC影响: 在极端SOC时效率下降
        soc_factor = 1.0
        if self._soc < 0.2:
            soc_factor = 0.9 + 0.5 * self._soc
        elif self._soc > 0.8:
            soc_factor = 0.9 + 0.5 * (1 - self._soc)

        return base_eff * soc_factor

    def set_power_setpoint(self, power: float) -> bool:
        """
        设置功率指令

        Args:
            power: 功率指令(MW), 正值放电, 负值充电
        """
        # SOC保护
        if power > 0 and self._soc <= self.soc_min:
            power = 0
        elif power < 0 and self._soc >= self.soc_max:
            power = 0

        # 功率限幅
        power = np.clip(power, -self.rated_power, self.rated_power)
        self._power_command = power
        self.state.power_setpoint = power
        return True

    def step(self, dt: float, **kwargs) -> EnergyState:
        """执行一步仿真"""
        if not self._enabled:
            self.state.power_output = 0.0
            return self.state

        # 爬坡率限制
        max_change = self.ramp_rate * self.rated_power * dt
        target_power = self._power_command

        if abs(target_power - self.state.power_output) > max_change:
            if target_power > self.state.power_output:
                target_power = self.state.power_output + max_change
            else:
                target_power = self.state.power_output - max_change

        # 一阶惯性响应
        alpha = 1 - np.exp(-dt / self.time_constant)
        self.state.power_output += alpha * (target_power - self.state.power_output)

        # 计算能量变化
        power_actual = self.state.power_output
        efficiency = self._get_efficiency(power_actual)

        if power_actual > 0:  # 放电
            energy_change = -power_actual * dt / 3600 / efficiency
        else:  # 充电
            energy_change = -power_actual * dt / 3600 * efficiency

        # 更新SOC
        soc_change = energy_change / self.rated_energy
        old_soc = self._soc
        self._soc = np.clip(self._soc + soc_change, 0.0, 1.0)

        # 循环计数(简化)
        if abs(soc_change) > 0.001:
            self._cycle_count += abs(soc_change) / 2

        # 温度模型(简化)
        heat_generation = abs(power_actual) * (1 - efficiency) * dt / 3600  # MWh
        cooling_rate = 0.01  # 冷却速率
        self._temperature += heat_generation * 10 - cooling_rate * (self._temperature - 25) * dt

        # 更新效率
        self.state.efficiency = efficiency
        self.state.time += dt

        return self.state

    def get_available_power_range(self) -> Tuple[float, float]:
        """获取当前可用功率范围"""
        # 根据SOC计算可用功率
        discharge_headroom = (self._soc - self.soc_min) / (1 - self.soc_min)
        charge_headroom = (self.soc_max - self._soc) / self.soc_max

        max_discharge = self.rated_power * min(1.0, discharge_headroom * 2)
        max_charge = -self.rated_power * min(1.0, charge_headroom * 2)

        return (max_charge, max_discharge)


# ==================== 抽水蓄能电站模型 ====================

class PSHOperatingState(Enum):
    """抽水蓄能运行状态"""
    STOPPED = auto()       # 停机
    PUMP_STARTING = auto()  # 泵启动中
    PUMPING = auto()       # 抽水运行
    PUMP_STOPPING = auto()  # 泵停止中
    GEN_STARTING = auto()   # 发电启动中
    GENERATING = auto()    # 发电运行
    GEN_STOPPING = auto()   # 发电停止中
    MODE_SWITCHING = auto() # 模式切换中


@dataclass
class PSHParameters:
    """抽水蓄能电站参数"""
    # 额定参数
    rated_power_gen: float = 100.0  # 发电额定功率(MW)
    rated_power_pump: float = 90.0  # 抽水额定功率(MW)
    rated_head: float = 300.0  # 额定水头(m)
    rated_flow_gen: float = 40.0  # 发电额定流量(m³/s)
    rated_flow_pump: float = 35.0  # 抽水额定流量(m³/s)

    # 效率参数
    efficiency_gen: float = 0.92  # 发电效率
    efficiency_pump: float = 0.88  # 抽水效率
    efficiency_motor: float = 0.98  # 电机效率

    # 水库参数
    reservoir_volume: float = 5e6  # 上水库容量(m³)
    reservoir_level_max: float = 0.95  # 最高水位(相对)
    reservoir_level_min: float = 0.15  # 最低水位(相对)

    # 时间约束
    startup_time_gen: float = 90.0  # 发电启动时间(s)
    startup_time_pump: float = 120.0  # 抽水启动时间(s)
    shutdown_time: float = 60.0  # 停机时间(s)
    mode_switch_time: float = 180.0  # 模式切换时间(s)
    min_run_time: float = 600.0  # 最短运行时间(s)
    min_stop_time: float = 300.0  # 最短停机时间(s)

    # 水力惯性
    water_starting_time: float = 2.0  # 水流启动时间常数(s)
    mechanical_time_constant: float = 8.0  # 机械时间常数(s)


class PumpedStorageModel(EnergyComponent):
    """
    抽水蓄能电站(PSH)非线性模型

    核心方程:
    发电模式: P_gen = η_gen * η_motor * ρ * g * H * Q
    抽水模式: P_pump = ρ * g * H * Q / (η_pump * η_motor)

    考虑因素:
    1. 有效水头H随水库水位变化
    2. 流量Q与水头的非线性关系
    3. 效率随运行点变化
    4. 水力惯性和机械惯性
    5. 模式切换约束
    """

    RHO = 1000.0  # 水密度(kg/m³)
    G = 9.81  # 重力加速度(m/s²)

    def __init__(
        self,
        name: str = "PSH",
        params: Optional[PSHParameters] = None
    ):
        self.params = params or PSHParameters()
        super().__init__(name, self.params.rated_power_gen)

        # 运行状态
        self._operating_state = PSHOperatingState.STOPPED
        self._state_timer = 0.0  # 状态持续时间

        # 物理状态
        self._reservoir_level = 0.5  # 上水库水位(相对值)
        self._flow = 0.0  # 当前流量(m³/s)
        self._head = self.params.rated_head  # 当前水头(m)
        self._speed = 0.0  # 转速(p.u.)

        # 功率状态
        self._power_command = 0.0
        self._power_actual = 0.0

        # 目标模式
        self._target_mode: Optional[PSHOperatingState] = None

    def get_operating_state(self) -> PSHOperatingState:
        """获取当前运行状态"""
        return self._operating_state

    def get_reservoir_level(self) -> float:
        """获取上水库水位"""
        return self._reservoir_level

    def _calculate_effective_head(self) -> float:
        """
        计算有效水头
        考虑水库水位和水头损失
        """
        # 水位对水头的影响
        level_effect = 0.8 + 0.4 * self._reservoir_level

        # 流量相关的水头损失 (Darcy-Weisbach简化)
        head_loss = 0.002 * self._flow ** 2

        effective_head = self.params.rated_head * level_effect - head_loss
        return max(effective_head, 0.0)

    def _calculate_efficiency(self, flow: float, is_generating: bool) -> float:
        """
        计算效率(非线性)
        效率随偏离最佳运行点下降
        """
        if is_generating:
            optimal_flow = self.params.rated_flow_gen
            base_efficiency = self.params.efficiency_gen
        else:
            optimal_flow = self.params.rated_flow_pump
            base_efficiency = self.params.efficiency_pump

        # 偏离最佳点的效率损失
        deviation = abs(flow - optimal_flow) / optimal_flow
        efficiency_factor = 1 - 0.3 * deviation ** 2

        return base_efficiency * max(0.7, efficiency_factor) * self.params.efficiency_motor

    def _calculate_power_from_flow(self, flow: float, head: float, is_generating: bool) -> float:
        """
        从流量和水头计算功率

        Args:
            flow: 流量(m³/s)
            head: 水头(m)
            is_generating: 是否发电模式

        Returns:
            功率(MW), 发电为正,抽水为负
        """
        if flow <= 0:
            return 0.0

        efficiency = self._calculate_efficiency(flow, is_generating)

        # P = ρ * g * H * Q * η (发电)
        # P = ρ * g * H * Q / η (抽水)
        hydraulic_power = self.RHO * self.G * head * flow / 1e6  # MW

        if is_generating:
            return hydraulic_power * efficiency
        else:
            return -hydraulic_power / efficiency

    def _calculate_flow_from_power(self, power: float, head: float, is_generating: bool) -> float:
        """
        从功率和水头计算所需流量
        """
        if abs(power) < 0.01:
            return 0.0

        # 迭代求解(简化)
        if is_generating:
            # 估算效率
            est_efficiency = self.params.efficiency_gen * self.params.efficiency_motor
            flow = abs(power) * 1e6 / (self.RHO * self.G * head * est_efficiency)
        else:
            est_efficiency = self.params.efficiency_pump * self.params.efficiency_motor
            flow = abs(power) * 1e6 * est_efficiency / (self.RHO * self.G * head)

        return flow

    def request_mode(self, target_state: PSHOperatingState) -> bool:
        """
        请求切换到目标运行模式

        Args:
            target_state: 目标状态

        Returns:
            是否接受请求
        """
        current = self._operating_state

        # 检查是否可以切换
        if current == target_state:
            return True

        # 检查最短运行时间约束
        if current in [PSHOperatingState.PUMPING, PSHOperatingState.GENERATING]:
            if self._state_timer < self.params.min_run_time:
                return False

        # 检查最短停机时间约束
        if current == PSHOperatingState.STOPPED:
            if self._state_timer < self.params.min_stop_time:
                return False

        # 不能在过渡状态时请求新模式
        if current in [PSHOperatingState.PUMP_STARTING, PSHOperatingState.PUMP_STOPPING,
                       PSHOperatingState.GEN_STARTING, PSHOperatingState.GEN_STOPPING,
                       PSHOperatingState.MODE_SWITCHING]:
            return False

        # 检查水库水位约束
        if target_state == PSHOperatingState.GENERATING:
            if self._reservoir_level < self.params.reservoir_level_min + 0.1:
                return False
        elif target_state == PSHOperatingState.PUMPING:
            if self._reservoir_level > self.params.reservoir_level_max - 0.1:
                return False

        self._target_mode = target_state
        return True

    def set_power_setpoint(self, power: float) -> bool:
        """
        设置功率指令

        Args:
            power: 功率指令(MW), 正值发电, 负值抽水
        """
        # 限幅
        if power > 0:
            power = min(power, self.params.rated_power_gen)
        else:
            power = max(power, -self.params.rated_power_pump)

        self._power_command = power
        self.state.power_setpoint = power
        return True

    def _update_state_machine(self, dt: float):
        """更新状态机"""
        self._state_timer += dt
        current = self._operating_state

        # 处理模式切换请求
        if self._target_mode is not None and self._target_mode != current:
            if current == PSHOperatingState.STOPPED:
                if self._target_mode == PSHOperatingState.GENERATING:
                    self._operating_state = PSHOperatingState.GEN_STARTING
                    self._state_timer = 0
                elif self._target_mode == PSHOperatingState.PUMPING:
                    self._operating_state = PSHOperatingState.PUMP_STARTING
                    self._state_timer = 0
            elif current == PSHOperatingState.GENERATING:
                if self._target_mode == PSHOperatingState.STOPPED:
                    self._operating_state = PSHOperatingState.GEN_STOPPING
                    self._state_timer = 0
                elif self._target_mode == PSHOperatingState.PUMPING:
                    self._operating_state = PSHOperatingState.GEN_STOPPING
                    self._state_timer = 0
            elif current == PSHOperatingState.PUMPING:
                if self._target_mode == PSHOperatingState.STOPPED:
                    self._operating_state = PSHOperatingState.PUMP_STOPPING
                    self._state_timer = 0
                elif self._target_mode == PSHOperatingState.GENERATING:
                    self._operating_state = PSHOperatingState.PUMP_STOPPING
                    self._state_timer = 0

        # 处理过渡状态
        current = self._operating_state

        if current == PSHOperatingState.GEN_STARTING:
            if self._state_timer >= self.params.startup_time_gen:
                self._operating_state = PSHOperatingState.GENERATING
                self._state_timer = 0
                self._target_mode = None

        elif current == PSHOperatingState.PUMP_STARTING:
            if self._state_timer >= self.params.startup_time_pump:
                self._operating_state = PSHOperatingState.PUMPING
                self._state_timer = 0
                self._target_mode = None

        elif current == PSHOperatingState.GEN_STOPPING:
            if self._state_timer >= self.params.shutdown_time:
                if self._target_mode == PSHOperatingState.PUMPING:
                    self._operating_state = PSHOperatingState.MODE_SWITCHING
                else:
                    self._operating_state = PSHOperatingState.STOPPED
                self._state_timer = 0

        elif current == PSHOperatingState.PUMP_STOPPING:
            if self._state_timer >= self.params.shutdown_time:
                if self._target_mode == PSHOperatingState.GENERATING:
                    self._operating_state = PSHOperatingState.MODE_SWITCHING
                else:
                    self._operating_state = PSHOperatingState.STOPPED
                self._state_timer = 0

        elif current == PSHOperatingState.MODE_SWITCHING:
            if self._state_timer >= self.params.mode_switch_time:
                if self._target_mode == PSHOperatingState.GENERATING:
                    self._operating_state = PSHOperatingState.GEN_STARTING
                elif self._target_mode == PSHOperatingState.PUMPING:
                    self._operating_state = PSHOperatingState.PUMP_STARTING
                else:
                    self._operating_state = PSHOperatingState.STOPPED
                self._state_timer = 0

    def step(self, dt: float, **kwargs) -> EnergyState:
        """执行一步仿真"""
        if not self._enabled:
            self.state.power_output = 0.0
            return self.state

        # 更新状态机
        self._update_state_machine(dt)

        # 更新有效水头
        self._head = self._calculate_effective_head()

        # 根据运行状态计算功率
        current = self._operating_state
        target_power = 0.0

        if current == PSHOperatingState.GENERATING:
            target_power = max(0, self._power_command)
        elif current == PSHOperatingState.PUMPING:
            target_power = min(0, self._power_command)
        elif current == PSHOperatingState.GEN_STARTING:
            # 启动过程中功率逐渐增加
            progress = self._state_timer / self.params.startup_time_gen
            target_power = max(0, self._power_command) * progress
        elif current == PSHOperatingState.PUMP_STARTING:
            progress = self._state_timer / self.params.startup_time_pump
            target_power = min(0, self._power_command) * progress
        elif current == PSHOperatingState.GEN_STOPPING:
            progress = 1 - self._state_timer / self.params.shutdown_time
            target_power = self._power_actual * progress
        elif current == PSHOperatingState.PUMP_STOPPING:
            progress = 1 - self._state_timer / self.params.shutdown_time
            target_power = self._power_actual * progress

        # 水力惯性响应
        alpha = 1 - np.exp(-dt / self.params.water_starting_time)
        target_flow = self._calculate_flow_from_power(
            target_power,
            self._head,
            current in [PSHOperatingState.GENERATING, PSHOperatingState.GEN_STARTING]
        )
        self._flow += alpha * (target_flow - self._flow)

        # 计算实际功率
        is_generating = current in [PSHOperatingState.GENERATING, PSHOperatingState.GEN_STARTING,
                                     PSHOperatingState.GEN_STOPPING]
        self._power_actual = self._calculate_power_from_flow(self._flow, self._head, is_generating)

        # 机械惯性
        alpha_mech = 1 - np.exp(-dt / self.params.mechanical_time_constant)
        self.state.power_output += alpha_mech * (self._power_actual - self.state.power_output)

        # 更新水库水位
        volume_change = self._flow * dt  # m³
        if is_generating:
            volume_change = -volume_change  # 发电消耗水
        level_change = volume_change / self.params.reservoir_volume
        self._reservoir_level = np.clip(
            self._reservoir_level + level_change,
            self.params.reservoir_level_min,
            self.params.reservoir_level_max
        )

        # 更新效率
        if abs(self._flow) > 0.1:
            self.state.efficiency = self._calculate_efficiency(self._flow, is_generating)

        self.state.time += dt
        return self.state

    def get_mode_switch_time_remaining(self) -> float:
        """获取模式切换剩余时间"""
        current = self._operating_state
        if current == PSHOperatingState.GEN_STARTING:
            return max(0, self.params.startup_time_gen - self._state_timer)
        elif current == PSHOperatingState.PUMP_STARTING:
            return max(0, self.params.startup_time_pump - self._state_timer)
        elif current == PSHOperatingState.GEN_STOPPING:
            return max(0, self.params.shutdown_time - self._state_timer)
        elif current == PSHOperatingState.PUMP_STOPPING:
            return max(0, self.params.shutdown_time - self._state_timer)
        elif current == PSHOperatingState.MODE_SWITCHING:
            return max(0, self.params.mode_switch_time - self._state_timer)
        return 0.0

    def is_available_for_dispatch(self) -> bool:
        """是否可被调度"""
        return self._operating_state in [
            PSHOperatingState.STOPPED,
            PSHOperatingState.GENERATING,
            PSHOperatingState.PUMPING
        ]


# ==================== 常规水电站模型 ====================

@dataclass
class HydroPlantParameters:
    """常规水电站参数"""
    rated_power: float = 200.0  # 额定功率(MW)
    rated_head: float = 80.0  # 额定水头(m)
    rated_flow: float = 300.0  # 额定流量(m³/s)
    efficiency: float = 0.90  # 综合效率
    min_power: float = 0.3  # 最小技术出力(p.u.)
    ramp_rate: float = 0.02  # 爬坡速率(p.u./s)
    governor_time_constant: float = 0.5  # 调速器时间常数(s)
    water_time_constant: float = 1.5  # 水流时间常数(s)


class ConventionalHydroModel(EnergyComponent):
    """
    常规梯级水电站模型

    包含:
    - 调速器模型
    - 水轮机非线性特性
    - 水流惯性
    - 调频响应
    """

    RHO = 1000.0
    G = 9.81

    def __init__(
        self,
        name: str = "Hydro",
        params: Optional[HydroPlantParameters] = None
    ):
        self.params = params or HydroPlantParameters()
        super().__init__(name, self.params.rated_power)

        # 状态变量
        self._head = self.params.rated_head
        self._flow = 0.0
        self._guide_vane_position = 0.0  # 导叶开度(0-1)
        self._power_command = 0.0
        self._running = False

    def start(self) -> bool:
        """启动机组"""
        self._running = True
        return True

    def stop(self) -> bool:
        """停止机组"""
        self._running = False
        self._power_command = 0
        return True

    def is_running(self) -> bool:
        """是否运行中"""
        return self._running

    def set_power_setpoint(self, power: float) -> bool:
        """设置功率指令"""
        if not self._running:
            return False

        # 限幅
        min_power = self.params.rated_power * self.params.min_power
        power = np.clip(power, min_power, self.params.rated_power)

        self._power_command = power
        self.state.power_setpoint = power
        return True

    def _calculate_flow_from_gate(self, gate_position: float, head: float) -> float:
        """从导叶开度计算流量"""
        # Q = Cv * A * sqrt(2gH) 简化
        flow_coeff = gate_position ** 0.8  # 非线性特性
        return self.params.rated_flow * flow_coeff * np.sqrt(head / self.params.rated_head)

    def _calculate_power_from_flow(self, flow: float, head: float) -> float:
        """从流量计算功率"""
        hydraulic_power = self.RHO * self.G * head * flow / 1e6
        return hydraulic_power * self.params.efficiency

    def step(self, dt: float, head: Optional[float] = None, **kwargs) -> EnergyState:
        """执行一步仿真"""
        if not self._enabled or not self._running:
            self.state.power_output = 0.0
            return self.state

        if head is not None:
            self._head = head

        # 目标导叶开度
        # 反算: P_target = η * ρ * g * H * Q
        target_flow = self._power_command * 1e6 / (self.params.efficiency * self.RHO * self.G * self._head)
        target_gate = (target_flow / self.params.rated_flow) ** 1.25
        target_gate = np.clip(target_gate, 0, 1)

        # 导叶开度爬坡限制
        max_gate_change = self.params.ramp_rate * dt
        gate_error = target_gate - self._guide_vane_position
        if abs(gate_error) > max_gate_change:
            gate_error = np.sign(gate_error) * max_gate_change

        # 调速器响应
        alpha = 1 - np.exp(-dt / self.params.governor_time_constant)
        self._guide_vane_position += alpha * gate_error
        self._guide_vane_position = np.clip(self._guide_vane_position, 0, 1)

        # 水流响应
        target_flow = self._calculate_flow_from_gate(self._guide_vane_position, self._head)
        alpha_water = 1 - np.exp(-dt / self.params.water_time_constant)
        self._flow += alpha_water * (target_flow - self._flow)

        # 计算功率
        power = self._calculate_power_from_flow(self._flow, self._head)
        self.state.power_output = power

        self.state.efficiency = self.params.efficiency
        self.state.time += dt

        return self.state

    def get_available_power_range(self) -> Tuple[float, float]:
        """获取可用功率范围"""
        if not self._running:
            return (0, 0)
        min_power = self.params.rated_power * self.params.min_power
        return (min_power, self.params.rated_power)


# ==================== 电网频率模型 ====================

@dataclass
class GridParameters:
    """电网参数"""
    nominal_frequency: float = 50.0  # 额定频率(Hz)
    system_inertia: float = 6.0  # 系统惯量常数H(s)
    damping_coefficient: float = 1.0  # 阻尼系数D(p.u.)
    base_power: float = 1000.0  # 系统基准功率(MW)
    frequency_deadband: float = 0.02  # 频率死区(Hz)


class GridModel:
    """
    电网频率动态模型

    基于摇摆方程:
    2H * df/dt = P_m - P_e - D * Δf

    其中:
    - H: 系统惯量常数
    - P_m: 机械功率(发电)
    - P_e: 电气功率(负荷)
    - D: 阻尼系数
    - Δf: 频率偏差
    """

    def __init__(self, params: Optional[GridParameters] = None):
        self.params = params or GridParameters()

        # 状态变量
        self._frequency = self.params.nominal_frequency
        self._frequency_derivative = 0.0
        self._power_imbalance = 0.0

        # 历史记录
        self._frequency_history: List[float] = []
        self._time_history: List[float] = []

    def get_frequency(self) -> float:
        """获取当前频率"""
        return self._frequency

    def get_frequency_deviation(self) -> float:
        """获取频率偏差"""
        return self._frequency - self.params.nominal_frequency

    def get_rocof(self) -> float:
        """获取频率变化率(RoCoF)"""
        return self._frequency_derivative

    def step(
        self,
        dt: float,
        total_generation: float,
        total_load: float
    ) -> float:
        """
        执行一步仿真

        Args:
            dt: 时间步长(s)
            total_generation: 总发电功率(MW)
            total_load: 总负荷功率(MW)

        Returns:
            当前频率(Hz)
        """
        # 功率不平衡(标幺值)
        self._power_imbalance = (total_generation - total_load) / self.params.base_power

        # 频率偏差
        delta_f = self._frequency - self.params.nominal_frequency

        # 摇摆方程: 2H * df/dt = ΔP - D * Δf
        # df/dt = (ΔP - D * Δf) / (2H)
        self._frequency_derivative = (
            self._power_imbalance - self.params.damping_coefficient * delta_f / self.params.nominal_frequency
        ) / (2 * self.params.system_inertia) * self.params.nominal_frequency

        # 更新频率
        self._frequency += self._frequency_derivative * dt

        # 频率限幅(防止仿真发散)
        self._frequency = np.clip(self._frequency, 47.0, 53.0)

        # 记录历史
        self._frequency_history.append(self._frequency)

        return self._frequency

    def get_frequency_history(self) -> List[float]:
        """获取频率历史"""
        return self._frequency_history.copy()

    def reset(self):
        """重置到标称状态"""
        self._frequency = self.params.nominal_frequency
        self._frequency_derivative = 0.0
        self._power_imbalance = 0.0
        self._frequency_history.clear()
