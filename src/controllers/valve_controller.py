# -*- coding: utf-8 -*-
"""
智能阀门控制柜 (IVCU - Intelligent Valve Control Unit)
Intelligent Valve Control Unit

实现阀门智能控制功能，包括：
- 两阶段液压关闭曲线
- 水锤防护逻辑
- 卡涩检测
- 断电保护
"""

from enum import Enum
from typing import Dict, Optional, Callable
import numpy as np

from .base_controller import (
    BaseController, ControllerState, ControlMode, AlarmLevel
)


class ValveControlMode(Enum):
    """阀门控制模式"""
    POSITION = "position"          # 位置控制
    FLOW = "flow"                  # 流量控制
    PRESSURE = "pressure"          # 压力控制
    TWO_STAGE_CLOSE = "two_stage"  # 两阶段关闭
    TIME_BASED = "time_based"      # 时间控制（降级模式）
    EMERGENCY_CLOSE = "emergency"  # 紧急关闭


class ValveController(BaseController):
    """智能阀门控制柜 (IVCU)

    核心功能：
    1. 最高压力限制 - 瞬态压力峰值不超过管道设计压力的1.2倍
    2. 防断流弥合 - 控制阀后不出现负压
    3. 倒流截断 - 断电工况下在倒流达到最大前关闭至30%以下
    4. 快速响应 - 信号到指令延迟 <= 50ms
    """

    def __init__(self, controller_id: str = "IVCU-001"):
        """初始化

        Args:
            controller_id: 控制器标识
        """
        super().__init__(controller_id)

        # 阀门控制模式
        self.valve_mode = ValveControlMode.POSITION

        # 设计参数
        self.design_pressure: float = 1.6      # 设计压力 (MPa)
        self.max_pressure_ratio: float = 1.2   # 最大允许压力比
        self.min_pressure: float = 0.05        # 最小允许压力 (MPa)
        self.reversal_cutoff: float = 0.30     # 倒流截断开度

        # 阀门参数
        self.valve_opening: float = 1.0        # 当前开度 (0-1)
        self.valve_setpoint: float = 1.0       # 目标开度
        self.valve_speed: float = 0.1          # 正常动作速度 (%/s)
        self.fast_close_speed: float = 0.5     # 快关速度 (%/s)
        self.slow_close_speed: float = 0.02    # 慢关速度 (%/s)

        # 两阶段关闭参数
        self.stage1_target: float = 0.3        # 第一阶段目标开度
        self.stage1_speed: float = 0.3         # 第一阶段速度
        self.stage2_speed: float = 0.05        # 第二阶段速度
        self.stage_pause_time: float = 2.0     # 阶段间暂停时间 (s)

        # 卡涩检测参数
        self.stall_detect_time: float = 2.0    # 卡涩检测时间 (s)
        self.stall_threshold: float = 0.01     # 卡涩阈值 (开度变化)

        # 状态跟踪
        self._closing_stage: int = 0           # 关闭阶段 (0=未开始, 1=快关, 2=暂停, 3=慢关)
        self._stage_timer: float = 0.0
        self._last_position: float = 1.0
        self._stall_timer: float = 0.0
        self._power_fail_detected: bool = False
        self._high_flow_lockout: bool = False

        # 传感器读数
        self._pressure_upstream: float = 0.0
        self._pressure_downstream: float = 0.0
        self._flow_rate: float = 0.0
        self._velocity: float = 0.0

        # 配置传感器量程
        self.add_sensor_range('P1', 0.0, 2.5)      # 上游压力 MPa
        self.add_sensor_range('P2', 0.0, 2.5)      # 下游压力 MPa
        self.add_sensor_range('Q', 0.0, 50.0)      # 流量 m³/s
        self.add_sensor_range('opening', 0.0, 1.0) # 开度

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理传感器输入

        Args:
            sensor_data: 传感器数据
        """
        self.state.sensor_readings = sensor_data.copy()

        # 提取关键传感器值
        self._pressure_upstream = sensor_data.get('P1', 0.0)
        self._pressure_downstream = sensor_data.get('P2', 0.0)
        self._flow_rate = sensor_data.get('Q', 0.0)
        self.valve_opening = sensor_data.get('opening', self.valve_opening)

        # 计算流速 (假设DN2000管道)
        pipe_area = np.pi * 1.0 ** 2  # 2m直径
        self._velocity = self._flow_rate / pipe_area if pipe_area > 0 else 0

        # 检测断电信号
        if sensor_data.get('power_fail', False):
            self._power_fail_detected = True

        self.state.actual_position = self.valve_opening

    def calculate_output(self) -> float:
        """计算阀门控制输出

        Returns:
            开度指令 (0-1)
        """
        dt = 0.01  # 控制周期 10ms

        if self.valve_mode == ValveControlMode.POSITION:
            # 位置控制模式
            return self._position_control(dt)

        elif self.valve_mode == ValveControlMode.TWO_STAGE_CLOSE:
            # 两阶段关闭模式
            return self._two_stage_close(dt)

        elif self.valve_mode == ValveControlMode.EMERGENCY_CLOSE:
            # 紧急关闭
            return self._emergency_close(dt)

        elif self.valve_mode == ValveControlMode.TIME_BASED:
            # 时间控制模式（传感器故障降级）
            return self._time_based_control(dt)

        return self.valve_opening

    def _position_control(self, dt: float) -> float:
        """位置控制模式"""
        error = self.valve_setpoint - self.valve_opening
        max_change = self.valve_speed * dt

        if abs(error) < max_change:
            return self.valve_setpoint
        else:
            return self.valve_opening + np.sign(error) * max_change

    def _two_stage_close(self, dt: float) -> float:
        """两阶段关闭控制

        第一阶段：快速关闭到30%
        暂停：等待压力波稳定
        第二阶段：缓慢关闭到全关
        """
        if self._closing_stage == 0:
            # 启动第一阶段
            self._closing_stage = 1
            self._stage_timer = 0.0

        if self._closing_stage == 1:
            # 第一阶段：快关到30%
            if self.valve_opening > self.stage1_target:
                new_opening = self.valve_opening - self.stage1_speed * dt
                return max(new_opening, self.stage1_target)
            else:
                # 进入暂停阶段
                self._closing_stage = 2
                self._stage_timer = 0.0
                return self.valve_opening

        elif self._closing_stage == 2:
            # 暂停阶段
            self._stage_timer += dt
            if self._stage_timer >= self.stage_pause_time:
                self._closing_stage = 3
            return self.valve_opening

        elif self._closing_stage == 3:
            # 第二阶段：慢关到全关
            if self.valve_opening > 0.01:
                new_opening = self.valve_opening - self.stage2_speed * dt
                return max(new_opening, 0.0)
            else:
                # 关闭完成
                self._closing_stage = 0
                self.valve_mode = ValveControlMode.POSITION
                return 0.0

        return self.valve_opening

    def _emergency_close(self, dt: float) -> float:
        """紧急关闭"""
        if self.valve_opening > 0.01:
            new_opening = self.valve_opening - self.fast_close_speed * dt
            return max(new_opening, 0.0)
        return 0.0

    def _time_based_control(self, dt: float) -> float:
        """时间控制模式（降级模式）

        当传感器失效时，使用预设时间曲线控制
        """
        # 按预设速度关闭
        target = self.valve_setpoint
        error = target - self.valve_opening
        max_change = self.slow_close_speed * dt

        if abs(error) < max_change:
            return target
        else:
            return self.valve_opening + np.sign(error) * max_change

    def execute_protection(self) -> bool:
        """执行保护逻辑

        Returns:
            是否触发保护
        """
        protection_triggered = False

        # 1. 最高压力保护
        max_allowed = self.design_pressure * self.max_pressure_ratio
        if self._pressure_upstream > max_allowed or self._pressure_downstream > max_allowed:
            self._raise_alarm(
                "OVERPRESSURE",
                AlarmLevel.CRITICAL,
                f"压力超限: P1={self._pressure_upstream:.2f}, P2={self._pressure_downstream:.2f}"
            )
            # 触发两阶段关闭
            if self.valve_mode != ValveControlMode.TWO_STAGE_CLOSE:
                self.valve_mode = ValveControlMode.TWO_STAGE_CLOSE
            protection_triggered = True

        # 2. 负压保护（防断流弥合）
        if self._pressure_downstream < self.min_pressure:
            self._raise_alarm(
                "NEGATIVE_PRESSURE",
                AlarmLevel.ALARM,
                f"下游负压风险: P2={self._pressure_downstream:.2f} MPa"
            )
            # 减缓关闭速度
            self.stage2_speed = 0.01
            protection_triggered = True

        # 3. 断电保护（倒流截断）
        if self._power_fail_detected:
            self._raise_alarm(
                "POWER_FAILURE",
                AlarmLevel.CRITICAL,
                "检测到断电信号，启动倒流截断"
            )
            self.valve_mode = ValveControlMode.TWO_STAGE_CLOSE
            self.valve_setpoint = 0.0
            protection_triggered = True

        # 4. 误关阀保护（高流速锁定）
        if self._velocity > 3.0 and self.valve_setpoint < 0.5:
            if not self._high_flow_lockout:
                self._raise_alarm(
                    "HIGH_FLOW_LOCKOUT",
                    AlarmLevel.WARNING,
                    f"高流速状态拒绝快关指令: V={self._velocity:.2f} m/s"
                )
                self._high_flow_lockout = True
            # 强制切换为慢关模式
            self.valve_mode = ValveControlMode.POSITION
            self.valve_speed = self.slow_close_speed
            protection_triggered = True
        else:
            self._high_flow_lockout = False

        # 5. 卡涩检测
        if self._detect_stall():
            self._raise_alarm(
                "VALVE_STALL",
                AlarmLevel.ALARM,
                f"阀门卡涩: 开度停止在 {self.valve_opening*100:.1f}%"
            )
            self.state.actuator_fault = True
            protection_triggered = True

        # 6. 传感器故障降级
        if self.state.sensor_fault:
            self._raise_alarm(
                "SENSOR_DEGRADED",
                AlarmLevel.WARNING,
                "传感器故障，切换至时间控制模式"
            )
            self.valve_mode = ValveControlMode.TIME_BASED
            protection_triggered = True

        return protection_triggered

    def _detect_stall(self) -> bool:
        """检测阀门卡涩

        Returns:
            是否检测到卡涩
        """
        # 如果阀门应该在动作但位置不变
        position_change = abs(self.valve_opening - self._last_position)
        command_moving = abs(self.state.output_command - self.valve_opening) > 0.01

        if command_moving and position_change < self.stall_threshold:
            self._stall_timer += 0.01  # 累加检测时间
            if self._stall_timer >= self.stall_detect_time:
                return True
        else:
            self._stall_timer = 0.0

        self._last_position = self.valve_opening
        return False

    def command_close(self, mode: str = "normal") -> None:
        """发送关阀指令

        Args:
            mode: "normal", "fast", "two_stage"
        """
        if mode == "two_stage":
            self.valve_mode = ValveControlMode.TWO_STAGE_CLOSE
            self._closing_stage = 0
        elif mode == "fast":
            self.valve_mode = ValveControlMode.EMERGENCY_CLOSE
        else:
            self.valve_mode = ValveControlMode.POSITION

        self.valve_setpoint = 0.0

    def command_open(self, target: float = 1.0) -> None:
        """发送开阀指令

        Args:
            target: 目标开度 (0-1)
        """
        self.valve_mode = ValveControlMode.POSITION
        self.valve_setpoint = max(0.0, min(1.0, target))

    def get_water_hammer_risk(self) -> Dict:
        """评估水锤风险

        Returns:
            风险评估结果
        """
        # 估算关阀可能产生的水锤压力
        # 简化公式: ΔH = a*V/g
        wave_speed = 1000  # m/s (假设)
        potential_hammer = wave_speed * self._velocity / 9.81  # m
        potential_pressure = potential_hammer * 9.81 / 1e6  # MPa

        return {
            'current_velocity': self._velocity,
            'potential_hammer_mpa': potential_pressure,
            'max_allowed_mpa': self.design_pressure * self.max_pressure_ratio,
            'risk_level': self._assess_risk_level(potential_pressure),
            'recommended_close_mode': self._recommend_close_mode(),
        }

    def _assess_risk_level(self, potential_pressure: float) -> str:
        """评估风险等级"""
        max_allowed = self.design_pressure * self.max_pressure_ratio
        current_total = self._pressure_upstream + potential_pressure

        if current_total > max_allowed:
            return "HIGH"
        elif current_total > self.design_pressure:
            return "MEDIUM"
        else:
            return "LOW"

    def _recommend_close_mode(self) -> str:
        """推荐关闭模式"""
        if self._velocity > 3.0:
            return "two_stage"
        elif self._velocity > 1.5:
            return "slow"
        else:
            return "normal"

    def reset(self) -> None:
        """复位控制器"""
        super().reset()
        self._closing_stage = 0
        self._stage_timer = 0.0
        self._stall_timer = 0.0
        self._power_fail_detected = False
        self._high_flow_lockout = False
        self.valve_mode = ValveControlMode.POSITION
