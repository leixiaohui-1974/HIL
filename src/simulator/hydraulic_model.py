# -*- coding: utf-8 -*-
"""
水力模型基类
Hydraulic Model Base Classes

提供水力仿真的基础框架，包括：
- 仿真状态管理
- 时间步进控制
- 边界条件处理
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from abc import ABC, abstractmethod
import numpy as np
from enum import Enum


class BoundaryType(Enum):
    """边界条件类型"""
    CONSTANT_HEAD = "constant_head"       # 恒定水位/压头
    CONSTANT_FLOW = "constant_flow"       # 恒定流量
    VALVE = "valve"                       # 阀门边界
    PUMP = "pump"                         # 水泵边界
    GATE = "gate"                         # 闸门边界
    FREE_OUTFLOW = "free_outflow"         # 自由出流
    RESERVOIR = "reservoir"               # 水库边界


@dataclass
class SimulationState:
    """仿真状态数据类

    存储当前仿真时刻的所有状态变量
    """
    time: float = 0.0                     # 当前时间 (s)
    dt: float = 0.01                      # 时间步长 (s)

    # 压力/水头状态
    pressures: np.ndarray = field(default_factory=lambda: np.array([]))      # 压力场 (MPa)
    heads: np.ndarray = field(default_factory=lambda: np.array([]))          # 水头场 (m)

    # 流量/流速状态
    flows: np.ndarray = field(default_factory=lambda: np.array([]))          # 流量场 (m³/s)
    velocities: np.ndarray = field(default_factory=lambda: np.array([]))     # 流速场 (m/s)

    # 水位状态 (明渠)
    water_levels: np.ndarray = field(default_factory=lambda: np.array([]))   # 水位 (m)

    # 设备状态
    valve_opening: float = 1.0            # 阀门开度 (0-1)
    pump_speed: float = 0.0               # 水泵转速 (rpm)
    gate_opening: float = 0.0             # 闸门开度 (m)

    # 监测点数据
    pressure_upstream: float = 0.0        # 上游压力 (MPa)
    pressure_downstream: float = 0.0      # 下游压力 (MPa)
    flow_rate: float = 0.0                # 流量 (m³/s)
    level_upstream: float = 0.0           # 上游水位 (m)
    level_downstream: float = 0.0         # 下游水位 (m)

    # 水锤/瞬态参数
    max_pressure: float = 0.0             # 最大压力峰值 (MPa)
    min_pressure: float = 0.0             # 最小压力谷值 (MPa)
    water_hammer_amplitude: float = 0.0   # 水锤幅值 (MPa)

    # 水泵状态
    pump_head: float = 0.0                # 水泵扬程 (m)
    pump_flow: float = 0.0                # 水泵流量 (m³/s)
    pump_efficiency: float = 0.0          # 水泵效率
    pump_power: float = 0.0               # 水泵功率 (kW)
    pump_torque: float = 0.0              # 水泵力矩 (N·m)
    reverse_speed: float = 0.0            # 倒转转速 (rpm)

    # 闸门状态
    gate_flow: float = 0.0                # 过闸流量 (m³/s)
    surge_amplitude: float = 0.0          # 波涌幅度 (m)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'time': self.time,
            'pressure_upstream': self.pressure_upstream,
            'pressure_downstream': self.pressure_downstream,
            'flow_rate': self.flow_rate,
            'valve_opening': self.valve_opening,
            'pump_speed': self.pump_speed,
            'gate_opening': self.gate_opening,
            'max_pressure': self.max_pressure,
            'min_pressure': self.min_pressure,
        }


@dataclass
class PipeParameters:
    """管道参数"""
    length: float = 1000.0          # 管长 (m)
    diameter: float = 2.0           # 管径 (m)
    wave_speed: float = 1000.0      # 波速 (m/s)
    friction_factor: float = 0.02  # 摩阻系数
    wall_thickness: float = 0.02    # 壁厚 (m)
    elastic_modulus: float = 2.1e11 # 弹性模量 (Pa)
    design_pressure: float = 1.6    # 设计压力 (MPa)

    @property
    def area(self) -> float:
        """管道截面积 (m²)"""
        return np.pi * (self.diameter / 2) ** 2

    @property
    def characteristic_time(self) -> float:
        """特征时间 - 水锤波往返时间 (s)"""
        return 2 * self.length / self.wave_speed


@dataclass
class ChannelParameters:
    """明渠参数"""
    length: float = 5000.0          # 渠长 (m)
    bottom_width: float = 20.0      # 底宽 (m)
    side_slope: float = 1.5         # 边坡系数
    bed_slope: float = 0.0001       # 底坡
    manning_n: float = 0.015        # 糙率系数
    design_depth: float = 5.0       # 设计水深 (m)
    freeboard: float = 0.5          # 安全超高 (m)

    def wetted_area(self, depth: float) -> float:
        """过水断面积"""
        return (self.bottom_width + self.side_slope * depth) * depth

    def wetted_perimeter(self, depth: float) -> float:
        """湿周"""
        return self.bottom_width + 2 * depth * np.sqrt(1 + self.side_slope ** 2)

    def hydraulic_radius(self, depth: float) -> float:
        """水力半径"""
        return self.wetted_area(depth) / self.wetted_perimeter(depth)


class HydraulicModel(ABC):
    """水力模型抽象基类

    定义水力仿真模型的通用接口
    """

    def __init__(self, dt: float = 0.01):
        """初始化

        Args:
            dt: 仿真时间步长 (s), 默认10ms
        """
        self.dt = dt
        self.state = SimulationState(dt=dt)
        self.time = 0.0
        self.history: List[SimulationState] = []
        self._callbacks: List[Callable] = []

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """初始化模型参数和初始条件"""
        pass

    @abstractmethod
    def step(self) -> SimulationState:
        """执行一个时间步的计算

        Returns:
            更新后的仿真状态
        """
        pass

    @abstractmethod
    def set_boundary_condition(self, boundary_type: BoundaryType,
                                value: float, location: str = "upstream") -> None:
        """设置边界条件

        Args:
            boundary_type: 边界类型
            value: 边界值
            location: 位置 ("upstream" 或 "downstream")
        """
        pass

    def run(self, duration: float, record_interval: int = 10) -> List[SimulationState]:
        """运行仿真

        Args:
            duration: 仿真时长 (s)
            record_interval: 记录间隔 (步数)

        Returns:
            仿真历史记录
        """
        steps = int(duration / self.dt)
        self.history = []

        for i in range(steps):
            state = self.step()

            if i % record_interval == 0:
                # 深拷贝状态
                import copy
                self.history.append(copy.deepcopy(state))

            # 执行回调
            for callback in self._callbacks:
                callback(state)

        return self.history

    def add_callback(self, callback: Callable[[SimulationState], None]) -> None:
        """添加步进回调函数"""
        self._callbacks.append(callback)

    def reset(self) -> None:
        """重置仿真状态"""
        self.time = 0.0
        self.state = SimulationState(dt=self.dt)
        self.history = []

    def get_sensor_readings(self) -> Dict[str, float]:
        """获取虚拟传感器读数

        Returns:
            传感器名称到读数的映射
        """
        return {
            'P1': self.state.pressure_upstream,      # 上游压力 (MPa)
            'P2': self.state.pressure_downstream,    # 下游压力 (MPa)
            'Q': self.state.flow_rate,               # 流量 (m³/s)
            'Z_up': self.state.level_upstream,       # 上游水位 (m)
            'Z_down': self.state.level_downstream,   # 下游水位 (m)
            'N': self.state.pump_speed,              # 转速 (rpm)
        }
