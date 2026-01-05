# -*- coding: utf-8 -*-
"""
水泵特性曲线模型
Pump Characteristics and Performance Curves

实现水泵的完整特性曲线，包括：
- H-Q 性能曲线
- 效率曲线
- 功率曲线
- 四象限全特性曲线（飞逸工况）
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional
from enum import Enum


class PumpOperatingZone(Enum):
    """水泵运行区域"""
    HIGH_EFFICIENCY = "high_efficiency"    # 高效区
    NORMAL = "normal"                       # 正常区
    SADDLE = "saddle"                       # 马鞍区（不稳定区）
    CAVITATION = "cavitation"               # 汽蚀区
    RUNAWAY = "runaway"                     # 飞逸区
    REVERSE = "reverse"                     # 倒转区


@dataclass
class PumpParameters:
    """水泵参数"""
    rated_flow: float = 10.0              # 额定流量 (m³/s)
    rated_head: float = 100.0             # 额定扬程 (m)
    rated_speed: float = 1450.0           # 额定转速 (rpm)
    rated_power: float = 12000.0          # 额定功率 (kW)
    rated_efficiency: float = 0.88        # 额定效率

    # 曲线系数 (二次多项式 H = a*Q² + b*Q + c)
    curve_a: float = -0.5                 # 二次项系数
    curve_b: float = -2.0                 # 一次项系数
    curve_c: float = 120.0                # 常数项 (关死点扬程)

    # 高效区边界
    efficiency_zone_min: float = 0.6      # 最小流量比
    efficiency_zone_max: float = 1.2      # 最大流量比

    # 汽蚀参数
    npsh_required: float = 8.0            # 必需汽蚀余量 (m)
    suction_head: float = 5.0             # 吸水高度 (m)

    # 飞逸参数
    runaway_speed_ratio: float = 1.8      # 飞逸转速比
    inertia_constant: float = 10.0        # 惯性时间常数 (s)

    # 最大允许倒转
    max_reverse_speed_ratio: float = 1.2  # 最大允许倒转转速比


class PumpCharacteristics:
    """水泵特性曲线模型

    提供水泵性能计算和运行状态评估
    """

    def __init__(self, params: Optional[PumpParameters] = None):
        """初始化

        Args:
            params: 水泵参数
        """
        self.params = params or PumpParameters()
        self.current_speed_ratio: float = 0.0  # 当前转速比 (n/n_rated)
        self.current_flow: float = 0.0
        self.current_head: float = 0.0
        self.current_power: float = 0.0
        self.current_efficiency: float = 0.0
        self.current_torque: float = 0.0
        self.is_running: bool = False
        self.is_reversing: bool = False

    def calculate_head(self, flow: float, speed_ratio: float = 1.0) -> float:
        """计算扬程

        使用相似定律: H = H_rated * (n/n_rated)²

        Args:
            flow: 流量 (m³/s)
            speed_ratio: 转速比 (n/n_rated)

        Returns:
            扬程 (m)
        """
        if speed_ratio <= 0:
            return 0.0

        # 归一化流量
        q_ratio = flow / self.params.rated_flow

        # 使用二次曲线计算扬程 (额定转速下)
        H_rated = (self.params.curve_a * q_ratio ** 2 +
                   self.params.curve_b * q_ratio +
                   self.params.curve_c)

        # 应用相似定律
        return H_rated * (speed_ratio ** 2)

    def calculate_efficiency(self, flow: float, speed_ratio: float = 1.0) -> float:
        """计算效率

        Args:
            flow: 流量 (m³/s)
            speed_ratio: 转速比

        Returns:
            效率 (0-1)
        """
        if speed_ratio <= 0 or flow <= 0:
            return 0.0

        # 归一化流量
        q_ratio = flow / self.params.rated_flow / speed_ratio

        # 效率曲线 (抛物线形状，在额定点达到最大)
        eta_max = self.params.rated_efficiency
        efficiency = eta_max * (1 - 0.5 * (q_ratio - 1) ** 2)

        return max(0.0, min(efficiency, eta_max))

    def calculate_power(self, flow: float, head: float, efficiency: float) -> float:
        """计算轴功率

        P = ρgQH / η

        Args:
            flow: 流量 (m³/s)
            head: 扬程 (m)
            efficiency: 效率

        Returns:
            功率 (kW)
        """
        if efficiency <= 0:
            return 0.0

        rho = 1000  # 水密度 kg/m³
        g = 9.81

        return rho * g * flow * head / efficiency / 1000

    def calculate_torque(self, power: float, speed: float) -> float:
        """计算扭矩

        T = P / ω = P / (2π*n/60)

        Args:
            power: 功率 (kW)
            speed: 转速 (rpm)

        Returns:
            扭矩 (N·m)
        """
        if speed <= 0:
            return 0.0

        omega = 2 * np.pi * speed / 60
        return power * 1000 / omega

    def get_operating_point(self, flow: float, speed_ratio: float = 1.0) -> dict:
        """获取当前运行点参数

        Args:
            flow: 流量 (m³/s)
            speed_ratio: 转速比

        Returns:
            运行点参数字典
        """
        head = self.calculate_head(flow, speed_ratio)
        efficiency = self.calculate_efficiency(flow, speed_ratio)
        power = self.calculate_power(flow, head, efficiency)
        speed = self.params.rated_speed * speed_ratio
        torque = self.calculate_torque(power, speed)

        self.current_speed_ratio = speed_ratio
        self.current_flow = flow
        self.current_head = head
        self.current_power = power
        self.current_efficiency = efficiency
        self.current_torque = torque

        return {
            'flow': flow,
            'head': head,
            'speed': speed,
            'speed_ratio': speed_ratio,
            'power': power,
            'efficiency': efficiency,
            'torque': torque,
            'operating_zone': self.get_operating_zone(flow, speed_ratio),
        }

    def get_operating_zone(self, flow: float, speed_ratio: float = 1.0) -> PumpOperatingZone:
        """判断运行区域

        Args:
            flow: 流量 (m³/s)
            speed_ratio: 转速比

        Returns:
            运行区域枚举
        """
        if speed_ratio < 0:
            return PumpOperatingZone.REVERSE

        if speed_ratio > self.params.runaway_speed_ratio:
            return PumpOperatingZone.RUNAWAY

        q_ratio = flow / self.params.rated_flow / max(speed_ratio, 0.01)

        # 检查汽蚀区
        if q_ratio > 1.3:
            npsh_available = 10.33 - self.params.suction_head  # 大气压减吸程
            if npsh_available < self.params.npsh_required * (q_ratio ** 2):
                return PumpOperatingZone.CAVITATION

        # 检查马鞍区 (低流量不稳定区)
        if q_ratio < 0.4:
            return PumpOperatingZone.SADDLE

        # 检查高效区
        if self.params.efficiency_zone_min <= q_ratio <= self.params.efficiency_zone_max:
            return PumpOperatingZone.HIGH_EFFICIENCY

        return PumpOperatingZone.NORMAL

    def simulate_startup(self, target_speed_ratio: float, duration: float,
                         dt: float = 0.1) -> list:
        """模拟启动过程

        使用S形曲线平滑启动

        Args:
            target_speed_ratio: 目标转速比
            duration: 启动时间 (s)
            dt: 时间步长 (s)

        Returns:
            启动过程记录
        """
        history = []
        t = 0
        n_steps = int(duration / dt)

        for i in range(n_steps):
            t = i * dt

            # S形曲线 (Sigmoid)
            x = 6 * (t / duration - 0.5)  # 映射到 [-3, 3]
            speed_ratio = target_speed_ratio / (1 + np.exp(-x))

            # 计算对应的流量 (假设管路特性)
            # 简化：流量与转速成正比
            flow = self.params.rated_flow * speed_ratio

            # 获取运行点
            point = self.get_operating_point(flow, speed_ratio)
            point['time'] = t

            history.append(point)

        self.is_running = True
        return history

    def simulate_trip(self, initial_speed_ratio: float, initial_flow: float,
                      duration: float, dt: float = 0.1,
                      valve_closing_curve: Optional[callable] = None) -> list:
        """模拟跳闸飞逸过程

        Args:
            initial_speed_ratio: 初始转速比
            initial_flow: 初始流量 (m³/s)
            duration: 仿真时长 (s)
            dt: 时间步长 (s)
            valve_closing_curve: 阀门关闭曲线函数 f(t) -> opening

        Returns:
            飞逸过程记录
        """
        history = []
        t = 0
        n_steps = int(duration / dt)

        speed_ratio = initial_speed_ratio
        flow = initial_flow

        # 转动惯量效应
        J = self.params.inertia_constant
        max_reverse_ratio = -self.params.max_reverse_speed_ratio

        for i in range(n_steps):
            t = i * dt

            # 阀门开度
            if valve_closing_curve:
                valve_opening = valve_closing_curve(t)
            else:
                valve_opening = 1.0

            # 水力力矩 (简化模型)
            # 正转减速 -> 停止 -> 倒转
            if speed_ratio > 0:
                # 正转减速阶段
                decel_rate = 2.0 / J  # 减速率
                speed_ratio -= decel_rate * dt

                # 阀门阻止倒流
                flow = initial_flow * valve_opening * max(speed_ratio, 0)

            else:
                # 倒转阶段
                self.is_reversing = True
                reverse_accel = 1.5 / J  # 倒转加速率

                # 阀门限制倒流
                if valve_opening < 0.3:
                    reverse_accel *= 0.3  # 阀门节流减缓倒转

                speed_ratio -= reverse_accel * dt
                speed_ratio = max(speed_ratio, max_reverse_ratio)

                # 倒流流量
                flow = -abs(speed_ratio) * self.params.rated_flow * valve_opening

            # 记录状态
            point = {
                'time': t,
                'speed_ratio': speed_ratio,
                'speed': speed_ratio * self.params.rated_speed,
                'flow': flow,
                'valve_opening': valve_opening,
                'is_reversing': speed_ratio < 0,
            }

            history.append(point)

            # 检查是否稳定
            if abs(speed_ratio) < 0.01 and valve_opening < 0.1:
                break

        return history

    def check_safety(self, speed_ratio: float, flow: float) -> dict:
        """安全检查

        Args:
            speed_ratio: 转速比
            flow: 流量

        Returns:
            安全状态评估
        """
        zone = self.get_operating_zone(flow, speed_ratio)

        warnings = []
        is_safe = True

        # 飞逸检查
        if abs(speed_ratio) > self.params.max_reverse_speed_ratio:
            warnings.append("OVERSPEED: 转速超过允许倒转速度")
            is_safe = False

        # 汽蚀检查
        if zone == PumpOperatingZone.CAVITATION:
            warnings.append("CAVITATION: 存在汽蚀风险")
            is_safe = False

        # 马鞍区检查
        if zone == PumpOperatingZone.SADDLE:
            warnings.append("UNSTABLE: 运行在不稳定马鞍区")

        return {
            'is_safe': is_safe,
            'zone': zone,
            'speed_ratio': speed_ratio,
            'max_allowed_ratio': self.params.max_reverse_speed_ratio,
            'warnings': warnings,
        }

    def get_hq_curve(self, speed_ratio: float = 1.0, n_points: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        """获取H-Q曲线

        Args:
            speed_ratio: 转速比
            n_points: 曲线点数

        Returns:
            (流量数组, 扬程数组)
        """
        q_max = self.params.rated_flow * 1.5 * speed_ratio
        flows = np.linspace(0, q_max, n_points)
        heads = np.array([self.calculate_head(q, speed_ratio) for q in flows])

        return flows, heads

    def get_efficiency_curve(self, speed_ratio: float = 1.0, n_points: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        """获取效率曲线

        Args:
            speed_ratio: 转速比
            n_points: 曲线点数

        Returns:
            (流量数组, 效率数组)
        """
        q_max = self.params.rated_flow * 1.5 * speed_ratio
        flows = np.linspace(0.1, q_max, n_points)
        efficiencies = np.array([self.calculate_efficiency(q, speed_ratio) for q in flows])

        return flows, efficiencies
