# -*- coding: utf-8 -*-
"""
多类型阀门控制器
Multi-Type Valve Controllers

支持水利枢纽中不同类型的阀门：
1. 调流调压阀 (Flow/Pressure Regulating Valve) - 连续调节流量和压力
2. 水锤消除阀 (Water Hammer Relief Valve) - 快速释放过压
3. 事故阀 (Emergency Shut-off Valve) - 紧急工况快速关闭
"""

from enum import Enum
from typing import Dict, Optional, Callable, List
import numpy as np

from .base_controller import (
    BaseController, ControllerState, ControlMode, AlarmLevel
)


class ValveType(Enum):
    """阀门类型"""
    FLOW_REGULATING = "flow_regulating"           # 调流阀
    PRESSURE_REGULATING = "pressure_regulating"   # 调压阀
    FLOW_PRESSURE = "flow_pressure"               # 调流调压阀
    WATER_HAMMER_RELIEF = "water_hammer_relief"   # 水锤消除阀
    EMERGENCY_SHUTOFF = "emergency_shutoff"       # 事故阀
    BUTTERFLY = "butterfly"                        # 蝶阀
    BALL = "ball"                                  # 球阀
    CONE = "cone"                                  # 锥形阀


class ValveControlMode(Enum):
    """阀门控制模式"""
    POSITION = "position"              # 位置控制
    FLOW = "flow"                      # 流量控制
    PRESSURE = "pressure"              # 压力控制
    DIFFERENTIAL_PRESSURE = "dp"       # 压差控制
    TWO_STAGE_CLOSE = "two_stage"      # 两阶段关闭
    TIME_BASED = "time_based"          # 时间控制（降级模式）
    EMERGENCY_CLOSE = "emergency"      # 紧急关闭
    RELIEF = "relief"                  # 泄压模式


class FlowPressureRegulatingValve(BaseController):
    """调流调压阀控制器

    功能特点：
    1. 精确的流量/压力PID控制
    2. 无级调节，响应平滑
    3. 防水锤慢关曲线
    4. 上下游压差保护
    """

    def __init__(self, controller_id: str = "FPV-001"):
        super().__init__(controller_id)
        self.valve_type = ValveType.FLOW_PRESSURE

        # 控制模式
        self.control_mode = ValveControlMode.FLOW

        # 阀门参数
        self.valve_opening: float = 0.5          # 当前开度 (0-1)
        self.valve_cv: float = 500.0             # 阀门流量系数 Cv
        self.max_velocity: float = 0.02          # 最大动作速度 (%/s)

        # 流量控制参数
        self.flow_setpoint: float = 10.0         # 流量设定值 (m³/s)
        self.flow_kp: float = 0.05               # 比例增益
        self.flow_ki: float = 0.01               # 积分增益
        self.flow_kd: float = 0.001              # 微分增益
        self._flow_integral: float = 0.0
        self._flow_error_prev: float = 0.0

        # 压力控制参数
        self.pressure_setpoint: float = 0.8      # 压力设定值 (MPa)
        self.pressure_kp: float = 0.1
        self.pressure_ki: float = 0.02
        self._pressure_integral: float = 0.0

        # 压差保护参数
        self.max_dp: float = 0.5                 # 最大允许压差 (MPa)
        self.min_dp: float = 0.05                # 最小压差 (MPa)
        self.dp_warning: float = 0.4             # 压差警告阈值

        # 防水锤参数
        self.anti_hammer_enabled: bool = True
        self.close_time_min: float = 60.0        # 最小关闭时间 (s)
        self.close_curve: str = "two_stage"      # 关闭曲线类型

        # 状态
        self._pressure_upstream: float = 0.0
        self._pressure_downstream: float = 0.0
        self._flow_rate: float = 0.0
        self._dp: float = 0.0

        # 传感器量程
        self.add_sensor_range('P1', 0.0, 2.5)
        self.add_sensor_range('P2', 0.0, 2.5)
        self.add_sensor_range('Q', 0.0, 50.0)

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理输入"""
        self.state.sensor_readings = sensor_data.copy()

        self._pressure_upstream = sensor_data.get('P1', 0.0)
        self._pressure_downstream = sensor_data.get('P2', 0.0)
        self._flow_rate = sensor_data.get('Q', 0.0)
        self.valve_opening = sensor_data.get('opening', self.valve_opening)

        self._dp = self._pressure_upstream - self._pressure_downstream

        self.state.actual_position = self.valve_opening

    def calculate_output(self) -> float:
        """计算控制输出"""
        dt = 0.01

        if self.control_mode == ValveControlMode.FLOW:
            return self._flow_control(dt)
        elif self.control_mode == ValveControlMode.PRESSURE:
            return self._pressure_control(dt)
        elif self.control_mode == ValveControlMode.DIFFERENTIAL_PRESSURE:
            return self._dp_control(dt)
        elif self.control_mode == ValveControlMode.POSITION:
            return self._position_control(dt)

        return self.valve_opening

    def _flow_control(self, dt: float) -> float:
        """流量PID控制"""
        error = self.flow_setpoint - self._flow_rate

        # PID
        self._flow_integral += error * dt
        self._flow_integral = np.clip(self._flow_integral, -10, 10)

        derivative = (error - self._flow_error_prev) / dt
        self._flow_error_prev = error

        output = (self.flow_kp * error +
                  self.flow_ki * self._flow_integral +
                  self.flow_kd * derivative)

        # 转换为开度变化
        new_opening = self.valve_opening + output * 0.01

        # 限速
        max_change = self.max_velocity * dt
        new_opening = self.valve_opening + np.clip(
            new_opening - self.valve_opening, -max_change, max_change
        )

        return np.clip(new_opening, 0, 1)

    def _pressure_control(self, dt: float) -> float:
        """下游压力控制"""
        error = self.pressure_setpoint - self._pressure_downstream

        self._pressure_integral += error * dt
        self._pressure_integral = np.clip(self._pressure_integral, -5, 5)

        output = self.pressure_kp * error + self.pressure_ki * self._pressure_integral

        new_opening = self.valve_opening + output * 0.01
        max_change = self.max_velocity * dt
        new_opening = self.valve_opening + np.clip(
            new_opening - self.valve_opening, -max_change, max_change
        )

        return np.clip(new_opening, 0, 1)

    def _dp_control(self, dt: float) -> float:
        """压差控制"""
        dp_setpoint = 0.3  # 目标压差
        error = dp_setpoint - self._dp

        output = 0.1 * error
        new_opening = self.valve_opening - output * 0.01  # 注意：压差大则需要开大阀门

        max_change = self.max_velocity * dt
        new_opening = self.valve_opening + np.clip(
            new_opening - self.valve_opening, -max_change, max_change
        )

        return np.clip(new_opening, 0, 1)

    def _position_control(self, dt: float) -> float:
        """位置控制"""
        target = self.state.setpoint
        error = target - self.valve_opening
        max_change = self.max_velocity * dt

        if abs(error) < max_change:
            return target
        return self.valve_opening + np.sign(error) * max_change

    def execute_protection(self) -> bool:
        """保护逻辑"""
        protection_triggered = False

        # 压差过大保护
        if self._dp > self.max_dp:
            self._raise_alarm(
                "DP_HIGH",
                AlarmLevel.ALARM,
                f"压差过大: {self._dp:.2f} MPa"
            )
            # 开大阀门降低压差
            self.state.output_command = min(1.0, self.valve_opening + 0.1)
            protection_triggered = True

        # 压差警告
        elif self._dp > self.dp_warning:
            self._raise_alarm(
                "DP_WARNING",
                AlarmLevel.WARNING,
                f"压差接近限值: {self._dp:.2f} MPa"
            )

        return protection_triggered

    def set_flow_setpoint(self, flow: float) -> None:
        """设置流量设定值"""
        self.flow_setpoint = flow
        self.control_mode = ValveControlMode.FLOW
        self._flow_integral = 0.0

    def set_pressure_setpoint(self, pressure: float) -> None:
        """设置压力设定值"""
        self.pressure_setpoint = pressure
        self.control_mode = ValveControlMode.PRESSURE
        self._pressure_integral = 0.0


class WaterHammerReliefValve(BaseController):
    """水锤消除阀控制器

    功能特点：
    1. 快速响应过压（<50ms）
    2. 自动泄压保护
    3. 压力波监测
    4. 智能复位控制
    """

    def __init__(self, controller_id: str = "WHV-001"):
        super().__init__(controller_id)
        self.valve_type = ValveType.WATER_HAMMER_RELIEF

        # 阀门状态
        self.valve_opening: float = 0.0          # 常闭阀
        self.is_relieving: bool = False

        # 触发参数
        self.trigger_pressure: float = 1.5       # 触发压力 (MPa)
        self.reset_pressure: float = 1.2         # 复位压力 (MPa)
        self.response_time: float = 0.05         # 响应时间 (s)

        # 泄压参数
        self.relief_opening: float = 0.8         # 泄压开度
        self.relief_duration_min: float = 2.0    # 最小泄压持续时间 (s)
        self._relief_timer: float = 0.0

        # 压力波监测
        self.pressure_rate_threshold: float = 0.5  # 压力变化率阈值 (MPa/s)
        self._pressure_history: List[float] = []
        self._max_history_len: int = 100

        # 当前状态
        self._pressure: float = 0.0
        self._pressure_rate: float = 0.0
        self._peak_pressure: float = 0.0

        self.add_sensor_range('P', 0.0, 3.0)

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理输入"""
        self.state.sensor_readings = sensor_data.copy()

        new_pressure = sensor_data.get('P', 0.0)

        # 计算压力变化率
        if len(self._pressure_history) > 0:
            self._pressure_rate = (new_pressure - self._pressure_history[-1]) / 0.01

        self._pressure = new_pressure
        self._pressure_history.append(new_pressure)
        if len(self._pressure_history) > self._max_history_len:
            self._pressure_history.pop(0)

        # 更新峰值
        self._peak_pressure = max(self._peak_pressure, new_pressure)

        self.valve_opening = sensor_data.get('opening', self.valve_opening)
        self.state.actual_position = self.valve_opening

    def calculate_output(self) -> float:
        """计算输出"""
        dt = 0.01

        # 检测过压条件
        overpressure = self._pressure > self.trigger_pressure
        rapid_rise = self._pressure_rate > self.pressure_rate_threshold

        if overpressure or (rapid_rise and self._pressure > self.reset_pressure):
            # 触发泄压
            if not self.is_relieving:
                self.is_relieving = True
                self._relief_timer = 0.0
                self._raise_alarm(
                    "RELIEF_ACTIVATED",
                    AlarmLevel.WARNING,
                    f"水锤消除阀开启，压力: {self._pressure:.2f} MPa"
                )

            self._relief_timer += dt
            return self.relief_opening

        elif self.is_relieving:
            # 检查是否可以复位
            if self._pressure < self.reset_pressure and \
               self._relief_timer >= self.relief_duration_min:
                self.is_relieving = False
                self._raise_alarm(
                    "RELIEF_RESET",
                    AlarmLevel.INFO,
                    "水锤消除阀复位"
                )
                return 0.0
            else:
                self._relief_timer += dt
                return self.relief_opening

        return 0.0  # 常闭

    def execute_protection(self) -> bool:
        """保护逻辑"""
        # 水锤消除阀本身就是保护设备
        if self._peak_pressure > self.trigger_pressure * 1.2:
            self._raise_alarm(
                "EXTREME_PRESSURE",
                AlarmLevel.CRITICAL,
                f"极端过压: {self._peak_pressure:.2f} MPa"
            )
            return True
        return False

    def reset_peak(self) -> None:
        """复位峰值记录"""
        self._peak_pressure = self._pressure

    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'is_relieving': self.is_relieving,
            'pressure': self._pressure,
            'pressure_rate': self._pressure_rate,
            'peak_pressure': self._peak_pressure,
            'relief_timer': self._relief_timer,
            'opening': self.valve_opening,
        }


class EmergencyShutoffValve(BaseController):
    """事故阀控制器

    功能特点：
    1. 快速关闭能力（可配置关闭时间）
    2. 蓄能器/重锤驱动（失电关闭）
    3. 两阶段关闭防水锤
    4. 联锁保护逻辑
    """

    def __init__(self, controller_id: str = "ESV-001"):
        super().__init__(controller_id)
        self.valve_type = ValveType.EMERGENCY_SHUTOFF

        # 阀门状态
        self.valve_opening: float = 1.0          # 常开阀
        self.is_tripped: bool = False
        self.trip_source: str = ""

        # 关闭参数
        self.full_close_time: float = 30.0       # 全关时间 (s) - 快速型
        self.stage1_opening: float = 0.2         # 第一阶段目标开度
        self.stage1_time: float = 5.0            # 第一阶段时间 (s)
        self.stage2_time: float = 25.0           # 第二阶段时间 (s)

        # 当前关闭阶段
        self._close_stage: int = 0               # 0=未触发, 1=快关, 2=慢关
        self._close_timer: float = 0.0

        # 触发条件
        self.trip_on_power_fail: bool = True     # 断电触发
        self.trip_on_high_pressure: bool = True  # 过压触发
        self.trip_on_low_pressure: bool = True   # 失压触发
        self.trip_pressure_high: float = 1.8     # 过压阈值 (MPa)
        self.trip_pressure_low: float = 0.1      # 失压阈值 (MPa)
        self.trip_on_high_flow: bool = True      # 过流触发
        self.trip_flow_high: float = 15.0        # 过流阈值 (m³/s)

        # 联锁信号
        self._interlock_signals: Dict[str, bool] = {}

        # 当前状态
        self._pressure: float = 0.0
        self._flow: float = 0.0
        self._power_ok: bool = True

        self.add_sensor_range('P', 0.0, 3.0)
        self.add_sensor_range('Q', 0.0, 30.0)

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理输入"""
        self.state.sensor_readings = sensor_data.copy()

        self._pressure = sensor_data.get('P', 0.0)
        self._flow = sensor_data.get('Q', 0.0)
        self._power_ok = not sensor_data.get('power_fail', False)
        self.valve_opening = sensor_data.get('opening', self.valve_opening)

        # 更新联锁信号
        for signal_name, value in sensor_data.items():
            if signal_name.startswith('interlock_'):
                self._interlock_signals[signal_name] = bool(value)

        self.state.actual_position = self.valve_opening

    def calculate_output(self) -> float:
        """计算输出"""
        dt = 0.01

        if self.is_tripped:
            return self._execute_close(dt)
        else:
            # 检查触发条件
            self._check_trip_conditions()
            return self.valve_opening

    def _check_trip_conditions(self) -> None:
        """检查触发条件"""
        # 断电触发
        if self.trip_on_power_fail and not self._power_ok:
            self._trigger_trip("POWER_FAIL")

        # 过压触发
        if self.trip_on_high_pressure and self._pressure > self.trip_pressure_high:
            self._trigger_trip("HIGH_PRESSURE")

        # 失压触发
        if self.trip_on_low_pressure and self._pressure < self.trip_pressure_low:
            self._trigger_trip("LOW_PRESSURE")

        # 过流触发
        if self.trip_on_high_flow and self._flow > self.trip_flow_high:
            self._trigger_trip("HIGH_FLOW")

        # 联锁触发
        for signal, active in self._interlock_signals.items():
            if active:
                self._trigger_trip(f"INTERLOCK:{signal}")

    def _trigger_trip(self, source: str) -> None:
        """触发关闭"""
        if not self.is_tripped:
            self.is_tripped = True
            self.trip_source = source
            self._close_stage = 1
            self._close_timer = 0.0
            self._raise_alarm(
                "EMERGENCY_TRIP",
                AlarmLevel.CRITICAL,
                f"事故阀触发关闭: {source}"
            )

    def _execute_close(self, dt: float) -> float:
        """执行关闭动作"""
        self._close_timer += dt

        if self._close_stage == 1:
            # 第一阶段：快速关闭到stage1_opening
            if self._close_timer < self.stage1_time:
                progress = self._close_timer / self.stage1_time
                target = 1.0 - (1.0 - self.stage1_opening) * progress
                return target
            else:
                self._close_stage = 2
                self._close_timer = 0.0
                return self.stage1_opening

        elif self._close_stage == 2:
            # 第二阶段：缓慢关闭到全关
            if self._close_timer < self.stage2_time:
                progress = self._close_timer / self.stage2_time
                target = self.stage1_opening * (1 - progress)
                return max(0.0, target)
            else:
                return 0.0

        return 0.0

    def execute_protection(self) -> bool:
        """保护逻辑"""
        # 事故阀本身是保护设备，不需要额外保护
        return self.is_tripped

    def manual_trip(self) -> None:
        """手动触发"""
        self._trigger_trip("MANUAL")

    def reset(self) -> None:
        """复位"""
        super().reset()
        self.is_tripped = False
        self.trip_source = ""
        self._close_stage = 0
        self._close_timer = 0.0
        self.valve_opening = 1.0  # 恢复全开

    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'is_tripped': self.is_tripped,
            'trip_source': self.trip_source,
            'close_stage': self._close_stage,
            'close_timer': self._close_timer,
            'opening': self.valve_opening,
            'pressure': self._pressure,
            'flow': self._flow,
            'power_ok': self._power_ok,
        }


# 保持与原有ValveController的兼容性
from .valve_controller import ValveController
