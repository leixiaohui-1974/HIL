# -*- coding: utf-8 -*-
"""
智能闸门控制柜 (IGCU - Intelligent Gate Control Unit)
Intelligent Gate Control Unit

实现闸门智能控制功能，包括：
- 流量伺服精度控制
- 波涌抑制控制
- 防冲刷逻辑
- 传感器漂移容错
"""

from enum import Enum
from typing import Dict, Optional, List
import numpy as np

from .base_controller import (
    BaseController, ControllerState, ControlMode, AlarmLevel
)


class GateControlMode(Enum):
    """闸门控制模式"""
    OPENING = "opening"           # 开度控制
    FLOW = "flow"                 # 流量控制
    LEVEL = "level"               # 水位控制
    SURGE_SUPPRESS = "surge"      # 波涌抑制
    SOFT_CLOSE = "soft_close"     # 柔性关闭
    UNIFORM = "uniform"           # 均流控制


class GateController(BaseController):
    """智能闸门控制柜 (IGCU)

    核心功能：
    1. 流量伺服精度 - 实际流量与目标偏差 <= 2%
    2. 波涌抑制 - 上游水位波涌幅度 < 0.3m
    3. 防冲刷逻辑 - 多孔闸门自动均流
    """

    def __init__(self, controller_id: str = "IGCU-001"):
        """初始化

        Args:
            controller_id: 控制器标识
        """
        super().__init__(controller_id)

        # 控制模式
        self.gate_mode = GateControlMode.OPENING

        # 闸门参数
        self.gate_width: float = 10.0          # 闸门宽度 (m)
        self.max_opening: float = 5.0          # 最大开度 (m)
        self.gate_cd: float = 0.6              # 流量系数

        # 当前状态
        self.current_opening: float = 0.0      # 当前开度 (m)
        self.opening_setpoint: float = 0.0     # 目标开度 (m)
        self.current_flow: float = 0.0         # 当前流量 (m³/s)
        self.target_flow: float = 0.0          # 目标流量 (m³/s)

        # 动作速度
        self.normal_speed: float = 0.01        # 正常速度 (m/s)
        self.fast_speed: float = 0.05          # 快速速度 (m/s)
        self.slow_speed: float = 0.002         # 慢速速度 (m/s)

        # 流量控制参数
        self.flow_tolerance: float = 0.02      # 流量容差 (2%)
        self.flow_kp: float = 0.1              # 比例增益
        self.flow_ki: float = 0.01             # 积分增益
        self._flow_integral: float = 0.0

        # 水位参数
        self.upstream_level: float = 3.0       # 上游水位 (m)
        self.downstream_level: float = 2.0     # 下游水位 (m)
        self.max_surge: float = 0.3            # 最大允许波涌 (m)
        self.initial_level: float = 3.0        # 初始水位

        # 波涌抑制参数
        self.surge_threshold: float = 0.2      # 波涌触发阈值 (m)
        self._surge_detected: bool = False
        self._surge_timer: float = 0.0

        # 柔性关闭参数
        self.soft_close_segments: int = 5      # 分段数
        self.segment_pause_time: float = 5.0   # 每段暂停时间 (s)
        self._soft_close_stage: int = 0
        self._segment_timer: float = 0.0
        self._segment_target: float = 0.0

        # 传感器漂移检测
        self.level_change_rate_max: float = 0.5  # 最大水位变化率 (m/s)
        self._last_level: float = 0.0
        self._level_jump_detected: bool = False

        # 多孔均流参数 (模拟多孔闸门)
        self.num_gates: int = 1
        self.gate_openings: List[float] = [0.0]  # 各孔开度
        self.uniform_tolerance: float = 0.1      # 均流容差

        # 配置传感器量程
        self.add_sensor_range('opening', 0.0, 10.0)
        self.add_sensor_range('Z_up', 0.0, 10.0)
        self.add_sensor_range('Z_down', 0.0, 10.0)
        self.add_sensor_range('Q', 0.0, 500.0)

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理传感器输入"""
        self.state.sensor_readings = sensor_data.copy()

        self.current_opening = sensor_data.get('opening', 0.0)
        self.upstream_level = sensor_data.get('Z_up', self.upstream_level)
        self.downstream_level = sensor_data.get('Z_down', self.downstream_level)
        self.current_flow = sensor_data.get('Q', 0.0)

        # 检测水位突变
        dt = 0.01
        level_rate = abs(self.upstream_level - self._last_level) / dt
        if level_rate > self.level_change_rate_max and self._last_level > 0:
            self._level_jump_detected = True
        else:
            self._level_jump_detected = False
        self._last_level = self.upstream_level

        # 计算波涌幅度
        surge = abs(self.upstream_level - self.initial_level)
        if surge > self.surge_threshold:
            self._surge_detected = True
            self._surge_timer += dt
        else:
            self._surge_detected = False
            self._surge_timer = 0.0

        self.state.actual_position = self.current_opening / self.max_opening

    def calculate_output(self) -> float:
        """计算闸门开度控制输出

        Returns:
            开度指令 (m)
        """
        dt = 0.01

        if self.gate_mode == GateControlMode.OPENING:
            return self._opening_control(dt)

        elif self.gate_mode == GateControlMode.FLOW:
            return self._flow_control(dt)

        elif self.gate_mode == GateControlMode.LEVEL:
            return self._level_control(dt)

        elif self.gate_mode == GateControlMode.SURGE_SUPPRESS:
            return self._surge_suppress_control(dt)

        elif self.gate_mode == GateControlMode.SOFT_CLOSE:
            return self._soft_close_control(dt)

        return self.current_opening

    def _opening_control(self, dt: float) -> float:
        """开度控制"""
        error = self.opening_setpoint - self.current_opening
        max_change = self.normal_speed * dt

        if abs(error) < max_change:
            return self.opening_setpoint
        else:
            return self.current_opening + np.sign(error) * max_change

    def _flow_control(self, dt: float) -> float:
        """流量伺服控制

        使用PI控制器，根据水位差自动调整开度
        """
        # 计算流量误差
        flow_error = self.target_flow - self.current_flow
        flow_error_ratio = flow_error / max(self.target_flow, 1.0)

        # 如果误差在容差内，不调整
        if abs(flow_error_ratio) < self.flow_tolerance:
            return self.current_opening

        # PI控制
        self._flow_integral += flow_error * dt
        self._flow_integral = np.clip(self._flow_integral, -10, 10)  # 积分限幅

        adjustment = self.flow_kp * flow_error + self.flow_ki * self._flow_integral

        # 计算需要的开度变化
        # 流量近似正比于开度 (简化)
        required_opening = self.current_opening + adjustment * 0.1

        # 限制变化速率
        max_change = self.normal_speed * dt
        new_opening = self.current_opening + np.clip(
            required_opening - self.current_opening, -max_change, max_change
        )

        return np.clip(new_opening, 0, self.max_opening)

    def _level_control(self, dt: float) -> float:
        """水位控制"""
        level_setpoint = self.state.setpoint
        level_error = level_setpoint - self.upstream_level

        # 水位过高则开大闸门，过低则关小
        adjustment = -level_error * 0.5  # 负反馈
        max_change = self.normal_speed * dt

        new_opening = self.current_opening + np.clip(adjustment * dt, -max_change, max_change)
        return np.clip(new_opening, 0, self.max_opening)

    def _surge_suppress_control(self, dt: float) -> float:
        """波涌抑制控制

        在大幅度调节时使用柔性轨迹
        """
        error = self.opening_setpoint - self.current_opening

        if abs(error) > 0.5:  # 大幅度调节
            # 使用慢速
            speed = self.slow_speed
        else:
            speed = self.normal_speed

        max_change = speed * dt

        # 检测波涌，如果波涌过大则暂停
        if self._surge_detected and self._surge_timer > 0.5:
            return self.current_opening  # 暂停动作

        if abs(error) < max_change:
            return self.opening_setpoint
        else:
            return self.current_opening + np.sign(error) * max_change

    def _soft_close_control(self, dt: float) -> float:
        """柔性关闭控制

        分段关闭，防止上游水位漫堤
        """
        if self._soft_close_stage == 0:
            # 初始化分段目标
            segment_size = self.current_opening / self.soft_close_segments
            self._segment_target = self.current_opening - segment_size
            self._soft_close_stage = 1
            self._segment_timer = 0.0

        if self._soft_close_stage % 2 == 1:
            # 关闭阶段
            if self.current_opening > self._segment_target + 0.01:
                new_opening = self.current_opening - self.slow_speed * dt
                return max(new_opening, self._segment_target)
            else:
                # 进入暂停阶段
                self._soft_close_stage += 1
                self._segment_timer = 0.0
                return self.current_opening

        else:
            # 暂停阶段，等待水位稳定
            self._segment_timer += dt
            if self._segment_timer >= self.segment_pause_time:
                if self._segment_target <= 0.01:
                    # 关闭完成
                    self._soft_close_stage = 0
                    self.gate_mode = GateControlMode.OPENING
                    return 0.0
                else:
                    # 下一段
                    segment_size = self._segment_target / max(
                        1, (self.soft_close_segments - self._soft_close_stage // 2)
                    )
                    self._segment_target = max(0, self._segment_target - segment_size)
                    self._soft_close_stage += 1
            return self.current_opening

    def execute_protection(self) -> bool:
        """执行保护逻辑"""
        protection_triggered = False

        # 1. 波涌抑制
        surge = abs(self.upstream_level - self.initial_level)
        if surge > self.max_surge:
            self._raise_alarm(
                "SURGE_EXCEEDED",
                AlarmLevel.ALARM,
                f"波涌超限: {surge:.2f}m > {self.max_surge}m"
            )
            # 切换到波涌抑制模式
            if self.gate_mode not in [GateControlMode.SURGE_SUPPRESS, GateControlMode.SOFT_CLOSE]:
                self.gate_mode = GateControlMode.SURGE_SUPPRESS
            protection_triggered = True

        # 2. 漫堤风险检查
        design_depth = 5.0  # 假设设计水深
        freeboard = 0.5     # 安全超高
        if self.upstream_level > design_depth - freeboard:
            self._raise_alarm(
                "OVERFLOW_RISK",
                AlarmLevel.CRITICAL,
                f"漫堤风险: 水位 {self.upstream_level:.2f}m"
            )
            # 紧急开大闸门
            self.opening_setpoint = min(self.max_opening, self.current_opening + 0.5)
            protection_triggered = True

        # 3. 传感器漂移容错
        if self._level_jump_detected:
            self._raise_alarm(
                "LEVEL_SENSOR_FAULT",
                AlarmLevel.WARNING,
                "水位计信号跳变，切换至开度控制模式"
            )
            # 保持当前开度，不随错误信号调整
            self.gate_mode = GateControlMode.OPENING
            self.opening_setpoint = self.current_opening
            protection_triggered = True

        # 4. 流量伺服精度检查
        if self.gate_mode == GateControlMode.FLOW:
            flow_error_ratio = abs(self.current_flow - self.target_flow) / max(self.target_flow, 1.0)
            if flow_error_ratio > 0.05:  # 5% 偏差
                self._raise_alarm(
                    "FLOW_DEVIATION",
                    AlarmLevel.WARNING,
                    f"流量偏差超限: {flow_error_ratio*100:.1f}%"
                )

        return protection_triggered

    def command_close(self, soft: bool = True) -> None:
        """关闭闸门

        Args:
            soft: 是否使用柔性关闭
        """
        if soft:
            self.gate_mode = GateControlMode.SOFT_CLOSE
            self._soft_close_stage = 0
        else:
            self.gate_mode = GateControlMode.OPENING
            self.opening_setpoint = 0.0

    def command_open(self, target: float) -> None:
        """开启闸门

        Args:
            target: 目标开度 (m)
        """
        self.gate_mode = GateControlMode.OPENING
        self.opening_setpoint = np.clip(target, 0, self.max_opening)

    def set_flow_target(self, flow: float) -> None:
        """设置目标流量

        Args:
            flow: 目标流量 (m³/s)
        """
        self.target_flow = flow
        self.gate_mode = GateControlMode.FLOW
        self._flow_integral = 0.0

    def calculate_optimal_opening(self, target_flow: float) -> float:
        """计算达到目标流量所需的最优开度

        使用闸孔出流公式反算

        Args:
            target_flow: 目标流量 (m³/s)

        Returns:
            最优开度 (m)
        """
        h = self.upstream_level - self.downstream_level
        if h <= 0:
            return 0.0

        # Q = Cd * B * e * sqrt(2*g*h)
        # e = Q / (Cd * B * sqrt(2*g*h))
        denominator = self.gate_cd * self.gate_width * np.sqrt(2 * 9.81 * h)
        if denominator > 0:
            optimal = target_flow / denominator
        else:
            optimal = 0.0

        return np.clip(optimal, 0, self.max_opening)

    def get_flow_coefficient_curve(self, h: float) -> Dict[float, float]:
        """获取流量系数曲线

        Args:
            h: 水位差 (m)

        Returns:
            开度到流量的映射
        """
        curve = {}
        for e in np.linspace(0, self.max_opening, 20):
            if e > 0:
                Q = self.gate_cd * self.gate_width * e * np.sqrt(2 * 9.81 * h)
                curve[e] = Q
            else:
                curve[e] = 0.0
        return curve

    def check_uniform_flow(self) -> Dict:
        """检查多孔均流状态"""
        if self.num_gates <= 1:
            return {'uniform': True, 'deviation': 0.0}

        mean_opening = np.mean(self.gate_openings)
        if mean_opening <= 0:
            return {'uniform': True, 'deviation': 0.0}

        max_deviation = max(abs(o - mean_opening) / mean_opening for o in self.gate_openings)

        return {
            'uniform': max_deviation <= self.uniform_tolerance,
            'deviation': max_deviation,
            'openings': self.gate_openings.copy(),
            'mean': mean_opening,
        }

    def reset(self) -> None:
        """复位控制器"""
        super().reset()
        self.current_opening = 0.0
        self.opening_setpoint = 0.0
        self._flow_integral = 0.0
        self._surge_detected = False
        self._surge_timer = 0.0
        self._soft_close_stage = 0
        self._level_jump_detected = False
        self.gate_mode = GateControlMode.OPENING
