# -*- coding: utf-8 -*-
"""
管网MOC（特征线法）水力瞬变模型
Method of Characteristics (MOC) for Water Hammer Analysis

实现基于特征线法的管道水锤分析，用于模拟：
- 阀门启闭引起的水锤
- 水泵启停瞬变过程
- 断电事故工况
"""

import numpy as np
from typing import Optional, Tuple
from .hydraulic_model import (
    HydraulicModel, SimulationState, BoundaryType, PipeParameters
)


class PipeMOCModel(HydraulicModel):
    """管网特征线法(MOC)水锤模型

    基于特征线法求解一维非恒定流方程：
    - 连续性方程: ∂H/∂t + (a²/gA)∂Q/∂x = 0
    - 运动方程: ∂Q/∂t + gA∂H/∂x + fQ|Q|/(2DA) = 0

    其中:
    - H: 压力水头 (m)
    - Q: 流量 (m³/s)
    - a: 水锤波速 (m/s)
    - A: 管道截面积 (m²)
    - f: 达西摩阻系数
    - D: 管径 (m)
    """

    def __init__(self, pipe_params: Optional[PipeParameters] = None, dt: float = 0.01):
        """初始化MOC模型

        Args:
            pipe_params: 管道参数
            dt: 时间步长 (s)
        """
        super().__init__(dt)
        self.pipe = pipe_params or PipeParameters()

        # 计算网格参数
        self.n_nodes = max(int(self.pipe.length / (self.pipe.wave_speed * dt)), 10)
        self.dx = self.pipe.length / (self.n_nodes - 1)
        self.dt = self.dx / self.pipe.wave_speed  # 满足Courant条件

        # 特征线参数
        self.B = self.pipe.wave_speed / (9.81 * self.pipe.area)  # 管道阻抗
        self.R = self.pipe.friction_factor * self.dx / (
            2 * 9.81 * self.pipe.diameter * self.pipe.area ** 2
        )

        # 状态变量
        self.H = np.zeros(self.n_nodes)  # 水头 (m)
        self.Q = np.zeros(self.n_nodes)  # 流量 (m³/s)
        self.H_prev = np.zeros(self.n_nodes)
        self.Q_prev = np.zeros(self.n_nodes)

        # 边界条件
        self.upstream_head: float = 100.0  # 上游水头 (m)
        self.valve_opening: float = 1.0    # 阀门开度 (0-1)
        self.valve_cv: float = 1.0         # 阀门流量系数
        self.downstream_head: float = 0.0  # 下游水头 (m)

        # 水泵参数
        self.pump_speed: float = 0.0       # 水泵转速比 (0-1)
        self.pump_on: bool = False

    def initialize(self, upstream_head: float = 100.0,
                   initial_flow: float = 10.0,
                   valve_opening: float = 1.0) -> None:
        """初始化稳态流动

        Args:
            upstream_head: 上游水头 (m)
            initial_flow: 初始流量 (m³/s)
            valve_opening: 初始阀门开度
        """
        self.upstream_head = upstream_head
        self.valve_opening = valve_opening

        # 计算稳态水头分布 (考虑摩阻损失)
        self.Q[:] = initial_flow
        velocity = initial_flow / self.pipe.area
        head_loss_per_m = self.pipe.friction_factor * velocity ** 2 / (
            2 * 9.81 * self.pipe.diameter
        )

        for i in range(self.n_nodes):
            x = i * self.dx
            self.H[i] = upstream_head - head_loss_per_m * x

        # 保存初始状态
        self.H_prev[:] = self.H
        self.Q_prev[:] = self.Q

        # 更新仿真状态
        self._update_state()

    def step(self) -> SimulationState:
        """执行一个时间步的MOC计算"""
        self.time += self.dt

        # 保存上一时刻状态
        self.H_prev[:] = self.H
        self.Q_prev[:] = self.Q

        # 内部节点计算 (特征线法)
        for i in range(1, self.n_nodes - 1):
            Cp, Bp = self._positive_characteristic(i)
            Cm, Bm = self._negative_characteristic(i)

            # 求解联立方程
            denom = Bp + Bm
            if denom > 0:
                self.H[i] = (Cp + Cm) / denom
                self.Q[i] = Cp - Bp * self.H[i]
            else:
                # 保持上一时刻值
                self.H[i] = self.H_prev[i]
                self.Q[i] = self.Q_prev[i]

            # 数值稳定性：限制结果范围
            self.H[i] = np.clip(self.H[i], -1e6, 1e6)
            self.Q[i] = np.clip(self.Q[i], -1e4, 1e4)

            # 处理NaN
            if not np.isfinite(self.H[i]):
                self.H[i] = self.H_prev[i]
            if not np.isfinite(self.Q[i]):
                self.Q[i] = self.Q_prev[i]

        # 上游边界 (水库或水泵)
        self._upstream_boundary()

        # 下游边界 (阀门或自由出流)
        self._downstream_boundary()

        # 更新仿真状态
        self._update_state()

        return self.state

    def _positive_characteristic(self, i: int) -> Tuple[float, float]:
        """正特征线 (C+)

        从 (i-1, t) 到 (i, t+dt)
        """
        H_p = self.H_prev[i - 1]
        Q_p = self.Q_prev[i - 1]

        # 数值稳定性：限制极值
        H_p = np.clip(H_p, -1e6, 1e6)
        Q_p = np.clip(Q_p, -1e4, 1e4)

        Cp = H_p + self.B * Q_p - self.R * Q_p * abs(Q_p)
        Bp = self.B + 2 * self.R * abs(Q_p)

        # 防止NaN/Inf
        if not np.isfinite(Cp):
            Cp = H_p
        if not np.isfinite(Bp) or Bp < self.B:
            Bp = self.B

        return Cp, Bp

    def _negative_characteristic(self, i: int) -> Tuple[float, float]:
        """负特征线 (C-)

        从 (i+1, t) 到 (i, t+dt)
        """
        H_m = self.H_prev[i + 1]
        Q_m = self.Q_prev[i + 1]

        # 数值稳定性：限制极值
        H_m = np.clip(H_m, -1e6, 1e6)
        Q_m = np.clip(Q_m, -1e4, 1e4)

        Cm = H_m - self.B * Q_m + self.R * Q_m * abs(Q_m)
        Bm = self.B + 2 * self.R * abs(Q_m)

        # 防止NaN/Inf
        if not np.isfinite(Cm):
            Cm = H_m
        if not np.isfinite(Bm) or Bm < self.B:
            Bm = self.B

        return Cm, Bm

    def _upstream_boundary(self) -> None:
        """上游边界条件

        可以是恒定水头水库或水泵边界
        """
        Cm, Bm = self._negative_characteristic(0)

        if self.pump_on:
            # 水泵边界 - 简化处理
            # 实际应使用水泵完整特性曲线
            pump_head = self.upstream_head * (self.pump_speed ** 2)
            self.H[0] = pump_head
            self.Q[0] = (Cm - pump_head) / (-Bm)
        else:
            # 恒定水头水库边界
            self.H[0] = self.upstream_head
            self.Q[0] = (Cm - self.upstream_head) / (-Bm)

    def _downstream_boundary(self) -> None:
        """下游边界条件 - 阀门模型

        使用阀门流量系数和开度计算
        """
        Cp, Bp = self._positive_characteristic(self.n_nodes - 1)
        i = self.n_nodes - 1

        if self.valve_opening <= 0.001:
            # 阀门全关
            self.Q[i] = 0.0
            self.H[i] = Cp
        else:
            # 阀门部分开启 - 使用特征方程和阀门方程联立求解
            # Q = Cv * tau * sqrt(H - H_downstream)
            Cv_tau = self.valve_cv * self.valve_opening

            if Cv_tau > 0:
                # 迭代求解
                H_est = self.H_prev[i]
                for _ in range(10):
                    if H_est > self.downstream_head:
                        Q_valve = Cv_tau * np.sqrt(H_est - self.downstream_head)
                    else:
                        Q_valve = -Cv_tau * np.sqrt(abs(self.downstream_head - H_est))

                    H_new = Cp - Bp * Q_valve
                    if abs(H_new - H_est) < 0.001:
                        break
                    H_est = H_new

                self.H[i] = H_est
                self.Q[i] = Q_valve
            else:
                self.Q[i] = 0.0
                self.H[i] = Cp

    def _update_state(self) -> None:
        """更新仿真状态对象"""
        self.state.time = self.time
        self.state.heads = self.H.copy()
        self.state.flows = self.Q.copy()

        # 监测点数据
        self.state.pressure_upstream = self.H[0] * 9.81 / 1e6  # 转换为MPa
        self.state.pressure_downstream = self.H[-1] * 9.81 / 1e6
        self.state.flow_rate = self.Q[-1]
        self.state.valve_opening = self.valve_opening

        # 计算流速
        self.state.velocities = self.Q / self.pipe.area

        # 更新极值
        max_h = np.max(self.H)
        min_h = np.min(self.H)
        self.state.max_pressure = max(self.state.max_pressure, max_h * 9.81 / 1e6)
        self.state.min_pressure = min(self.state.min_pressure, min_h * 9.81 / 1e6)
        self.state.water_hammer_amplitude = (max_h - min_h) * 9.81 / 1e6

    def set_boundary_condition(self, boundary_type: BoundaryType,
                                value: float, location: str = "upstream") -> None:
        """设置边界条件"""
        if location == "upstream":
            if boundary_type == BoundaryType.CONSTANT_HEAD:
                self.upstream_head = value
            elif boundary_type == BoundaryType.PUMP:
                self.pump_on = True
                self.pump_speed = value
        elif location == "downstream":
            if boundary_type == BoundaryType.VALVE:
                self.valve_opening = value
            elif boundary_type == BoundaryType.CONSTANT_HEAD:
                self.downstream_head = value

    def set_valve_opening(self, opening: float) -> None:
        """设置阀门开度

        Args:
            opening: 阀门开度 (0-1)
        """
        self.valve_opening = max(0.0, min(1.0, opening))

    def simulate_power_failure(self) -> None:
        """模拟断电工况

        上游动力丧失，压力波向下游传播
        """
        self.pump_on = False
        self.pump_speed = 0.0
        # 上游水头按惯性衰减
        self.upstream_head *= 0.95

    def get_water_hammer_risk(self) -> dict:
        """评估水锤风险

        Returns:
            风险评估结果
        """
        design_pressure = self.pipe.design_pressure
        max_allowable = design_pressure * 1.2  # 允许1.2倍超压

        return {
            'max_pressure_mpa': self.state.max_pressure,
            'min_pressure_mpa': self.state.min_pressure,
            'design_pressure_mpa': design_pressure,
            'max_allowable_mpa': max_allowable,
            'overpressure_ratio': self.state.max_pressure / design_pressure,
            'negative_pressure': self.state.min_pressure < 0.05,  # 负压风险
            'risk_level': self._calculate_risk_level(),
        }

    def _calculate_risk_level(self) -> str:
        """计算风险等级"""
        design_pressure = self.pipe.design_pressure
        ratio = self.state.max_pressure / design_pressure

        if ratio > 1.2:
            return "CRITICAL"
        elif ratio > 1.0:
            return "WARNING"
        elif self.state.min_pressure < 0.05:
            return "NEGATIVE_PRESSURE"
        else:
            return "SAFE"
