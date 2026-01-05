# -*- coding: utf-8 -*-
"""
明渠圣维南方程模型
Saint-Venant Equations for Open Channel Flow

实现一维非恒定明渠流动计算，用于模拟：
- 闸门调节引起的波涌
- 渠道水位变化
- 流量调度过程
"""

import numpy as np
from typing import Optional
from .hydraulic_model import (
    HydraulicModel, SimulationState, BoundaryType, ChannelParameters
)


class ChannelSaintVenantModel(HydraulicModel):
    """明渠圣维南方程模型

    求解一维圣维南方程组：
    - 连续性方程: ∂A/∂t + ∂Q/∂x = 0
    - 动量方程: ∂Q/∂t + ∂(Q²/A)/∂x + gA∂h/∂x = gA(S₀ - Sf)

    其中:
    - A: 过水断面积 (m²)
    - Q: 流量 (m³/s)
    - h: 水深 (m)
    - S₀: 底坡
    - Sf: 摩阻坡度 (曼宁公式)
    """

    def __init__(self, channel_params: Optional[ChannelParameters] = None,
                 dt: float = 0.5):
        """初始化圣维南模型

        Args:
            channel_params: 渠道参数
            dt: 时间步长 (s)
        """
        super().__init__(dt)
        self.channel = channel_params or ChannelParameters()

        # 计算网格参数
        self.n_nodes = 101
        self.dx = self.channel.length / (self.n_nodes - 1)

        # 状态变量
        self.h = np.zeros(self.n_nodes)    # 水深 (m)
        self.Q = np.zeros(self.n_nodes)    # 流量 (m³/s)
        self.A = np.zeros(self.n_nodes)    # 断面积 (m²)
        self.V = np.zeros(self.n_nodes)    # 流速 (m/s)

        # 上一时刻状态
        self.h_prev = np.zeros(self.n_nodes)
        self.Q_prev = np.zeros(self.n_nodes)

        # 边界条件
        self.upstream_level: float = 3.0   # 上游水位 (m)
        self.downstream_level: float = 2.5 # 下游水位 (m)
        self.gate_opening: float = 0.0     # 闸门开度 (m)
        self.target_flow: float = 50.0     # 目标流量 (m³/s)

        # 闸门参数
        self.gate_width: float = 10.0      # 闸门宽度 (m)
        self.gate_cd: float = 0.6          # 流量系数

        # 记录初始水位用于波涌计算
        self.initial_level: float = 3.0
        self.max_surge: float = 0.0

    def initialize(self, upstream_level: float = 3.0,
                   initial_flow: float = 50.0,
                   gate_opening: float = 1.0) -> None:
        """初始化稳态流动

        Args:
            upstream_level: 上游水位 (m)
            initial_flow: 初始流量 (m³/s)
            gate_opening: 初始闸门开度 (m)
        """
        self.upstream_level = upstream_level
        self.initial_level = upstream_level
        self.gate_opening = gate_opening
        self.target_flow = initial_flow

        # 初始化均匀流条件
        # 使用曼宁公式反算正常水深
        normal_depth = self._calculate_normal_depth(initial_flow)

        self.h[:] = normal_depth
        self.Q[:] = initial_flow

        # 计算断面积和流速
        for i in range(self.n_nodes):
            self.A[i] = self.channel.wetted_area(self.h[i])
            self.V[i] = self.Q[i] / self.A[i] if self.A[i] > 0 else 0

        # 设置水位分布 (考虑壅水曲线)
        self._calculate_backwater_curve()

        # 保存初始状态
        self.h_prev[:] = self.h
        self.Q_prev[:] = self.Q

        # 更新仿真状态
        self._update_state()

    def _calculate_normal_depth(self, Q: float) -> float:
        """使用曼宁公式计算正常水深

        Args:
            Q: 流量 (m³/s)

        Returns:
            正常水深 (m)
        """
        n = self.channel.manning_n
        S0 = self.channel.bed_slope
        B = self.channel.bottom_width
        m = self.channel.side_slope

        # 迭代求解
        h = 2.0  # 初始猜测
        for _ in range(50):
            A = (B + m * h) * h
            P = B + 2 * h * np.sqrt(1 + m ** 2)
            R = A / P
            Q_calc = A * (R ** (2/3)) * np.sqrt(S0) / n

            if abs(Q_calc - Q) < 0.01:
                break

            # 牛顿迭代
            dA_dh = B + 2 * m * h
            dP_dh = 2 * np.sqrt(1 + m ** 2)
            dR_dh = (dA_dh * P - A * dP_dh) / (P ** 2)
            dQ_dh = (dA_dh * R ** (2/3) + A * (2/3) * R ** (-1/3) * dR_dh) * np.sqrt(S0) / n

            h = h - (Q_calc - Q) / dQ_dh
            h = max(0.1, h)

        return h

    def _calculate_backwater_curve(self) -> None:
        """计算壅水曲线"""
        # 从下游向上游计算
        # 简化处理：线性插值
        h_up = self.upstream_level
        h_down = self.h[-1]

        for i in range(self.n_nodes):
            x = i * self.dx
            self.h[i] = h_up - (h_up - h_down) * x / self.channel.length

    def step(self) -> SimulationState:
        """执行一个时间步的圣维南方程求解

        使用Preissmann隐式格式
        """
        self.time += self.dt

        # 保存上一时刻状态
        self.h_prev[:] = self.h
        self.Q_prev[:] = self.Q

        # 使用简化的显式格式 (演示用)
        # 实际应用中应使用Preissmann四点隐式格式

        h_new = np.zeros(self.n_nodes)
        Q_new = np.zeros(self.n_nodes)

        # 内部节点
        for i in range(1, self.n_nodes - 1):
            # 连续性方程
            dQ_dx = (self.Q[i+1] - self.Q[i-1]) / (2 * self.dx)
            dA_dt = -dQ_dx

            # 计算新的断面积
            A_new = self.A[i] + dA_dt * self.dt
            A_new = max(A_new, 0.1)  # 防止负值

            # 反算水深
            h_new[i] = self._depth_from_area(A_new)

            # 动量方程
            Sf = self._friction_slope(i)
            S0 = self.channel.bed_slope

            dQ_dt = 9.81 * self.A[i] * (S0 - Sf) - \
                    self.Q[i] * (self.Q[i+1] - self.Q[i-1]) / (self.A[i] * 2 * self.dx) - \
                    9.81 * self.A[i] * (self.h[i+1] - self.h[i-1]) / (2 * self.dx)

            Q_new[i] = self.Q[i] + dQ_dt * self.dt

        # 上游边界
        h_new[0] = self.upstream_level
        Q_new[0] = self._upstream_flow()

        # 下游边界 (闸门)
        h_new[-1] = self.h[-1]  # 保持水深
        Q_new[-1] = self._gate_flow()

        # 更新状态
        self.h = h_new
        self.Q = Q_new

        # 更新断面积和流速
        for i in range(self.n_nodes):
            self.A[i] = self.channel.wetted_area(self.h[i])
            self.V[i] = self.Q[i] / self.A[i] if self.A[i] > 0 else 0

        # 计算波涌
        current_max_level = np.max(self.h)
        self.max_surge = max(self.max_surge, current_max_level - self.initial_level)

        # 更新仿真状态
        self._update_state()

        return self.state

    def _depth_from_area(self, A: float) -> float:
        """从断面积反算水深"""
        B = self.channel.bottom_width
        m = self.channel.side_slope

        # 解二次方程: A = (B + m*h)*h => m*h² + B*h - A = 0
        if m == 0:
            return A / B
        else:
            discriminant = B ** 2 + 4 * m * A
            return (-B + np.sqrt(discriminant)) / (2 * m)

    def _friction_slope(self, i: int) -> float:
        """计算摩阻坡度 (曼宁公式)"""
        n = self.channel.manning_n
        R = self.channel.hydraulic_radius(self.h[i])
        V = self.V[i]

        return (n ** 2) * (V ** 2) / (R ** (4/3))

    def _upstream_flow(self) -> float:
        """上游入流边界"""
        # 简化处理：保持稳定入流
        return self.target_flow

    def _gate_flow(self) -> float:
        """计算过闸流量

        使用闸孔出流公式
        """
        if self.gate_opening <= 0.001:
            return 0.0

        # 闸前水位
        h_up = self.h[-2] if len(self.h) > 1 else self.h[-1]
        h_down = self.downstream_level

        # 判断出流类型
        if self.gate_opening < 0.67 * h_up:
            # 孔流 (淹没或自由)
            if h_down < self.gate_opening:
                # 自由孔流
                Q = self.gate_cd * self.gate_width * self.gate_opening * \
                    np.sqrt(2 * 9.81 * h_up)
            else:
                # 淹没孔流
                dh = h_up - h_down
                if dh > 0:
                    Q = self.gate_cd * self.gate_width * self.gate_opening * \
                        np.sqrt(2 * 9.81 * dh)
                else:
                    Q = 0.0
        else:
            # 堰流
            Q = 0.385 * self.gate_width * np.sqrt(2 * 9.81) * (h_up ** 1.5)

        return Q

    def _update_state(self) -> None:
        """更新仿真状态"""
        self.state.time = self.time
        self.state.water_levels = self.h.copy()
        self.state.flows = self.Q.copy()
        self.state.velocities = self.V.copy()

        # 监测点数据
        self.state.level_upstream = self.h[0]
        self.state.level_downstream = self.h[-1]
        self.state.flow_rate = self.Q[-1]
        self.state.gate_opening = self.gate_opening
        self.state.gate_flow = self._gate_flow()
        self.state.surge_amplitude = self.max_surge

    def set_boundary_condition(self, boundary_type: BoundaryType,
                                value: float, location: str = "upstream") -> None:
        """设置边界条件"""
        if location == "upstream":
            if boundary_type == BoundaryType.CONSTANT_HEAD:
                self.upstream_level = value
            elif boundary_type == BoundaryType.CONSTANT_FLOW:
                self.target_flow = value
        elif location == "downstream":
            if boundary_type == BoundaryType.GATE:
                self.gate_opening = value
            elif boundary_type == BoundaryType.CONSTANT_HEAD:
                self.downstream_level = value

    def set_gate_opening(self, opening: float) -> None:
        """设置闸门开度

        Args:
            opening: 闸门开度 (m)
        """
        self.gate_opening = max(0.0, opening)

    def set_target_flow(self, flow: float) -> None:
        """设置目标流量

        Args:
            flow: 目标流量 (m³/s)
        """
        self.target_flow = flow

    def calculate_optimal_gate_opening(self, target_flow: float) -> float:
        """计算达到目标流量所需的闸门开度

        Args:
            target_flow: 目标流量 (m³/s)

        Returns:
            最优闸门开度 (m)
        """
        h_up = self.h[-2] if len(self.h) > 1 else self.upstream_level
        h_down = self.downstream_level

        # 反算闸门开度 (自由孔流公式)
        # Q = Cd * B * e * sqrt(2*g*h)
        # e = Q / (Cd * B * sqrt(2*g*h))

        denominator = self.gate_cd * self.gate_width * np.sqrt(2 * 9.81 * h_up)
        if denominator > 0:
            opening = target_flow / denominator
        else:
            opening = 0.0

        return max(0.0, min(opening, self.channel.design_depth))

    def check_overflow_risk(self) -> dict:
        """检查漫堤风险

        Returns:
            风险评估结果
        """
        max_level = np.max(self.h)
        safe_level = self.channel.design_depth - self.channel.freeboard

        return {
            'max_water_level': max_level,
            'safe_level': safe_level,
            'freeboard': self.channel.freeboard,
            'surge_amplitude': self.max_surge,
            'overflow_risk': max_level > safe_level,
            'risk_level': self._calculate_overflow_risk_level(max_level, safe_level),
        }

    def _calculate_overflow_risk_level(self, max_level: float, safe_level: float) -> str:
        """计算漫堤风险等级"""
        if max_level > self.channel.design_depth:
            return "CRITICAL"
        elif max_level > safe_level:
            return "WARNING"
        elif max_level > safe_level - 0.2:
            return "CAUTION"
        else:
            return "SAFE"
