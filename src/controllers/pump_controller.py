# -*- coding: utf-8 -*-
"""
智能泵控柜 (IPCU - Intelligent Pump Control Unit)
Intelligent Pump Control Unit

实现水泵智能控制功能，包括：
- S形曲线软启停
- 运行区间限制
- 倒转保护
- 振动与健康联动
"""

from enum import Enum
from typing import Dict, Optional, List
import numpy as np

from .base_controller import (
    BaseController, ControllerState, ControlMode, AlarmLevel
)


class PumpControlMode(Enum):
    """水泵控制模式"""
    SPEED = "speed"               # 转速控制
    FLOW = "flow"                 # 流量控制
    PRESSURE = "pressure"         # 压力控制
    SOFT_START = "soft_start"     # 软启动
    SOFT_STOP = "soft_stop"       # 软停止
    EMERGENCY_STOP = "emergency"  # 紧急停止
    ANTI_SURGE = "anti_surge"     # 防喘振


class PumpController(BaseController):
    """智能泵控柜 (IPCU)

    核心功能：
    1. 软启停控制 - S形曲线，启停时间 >= 60s
    2. 运行区间限制 - 禁止在马鞍区或汽蚀区运行
    3. 倒转保护 - 最大倒转速 < 1.2倍额定转速，倒转时间 < 120s
    4. 振动与健康联动 - 超标自动降负荷或停机
    """

    def __init__(self, controller_id: str = "IPCU-001"):
        """初始化

        Args:
            controller_id: 控制器标识
        """
        super().__init__(controller_id)

        # 控制模式
        self.pump_mode = PumpControlMode.SPEED

        # 额定参数
        self.rated_speed: float = 1450.0       # 额定转速 (rpm)
        self.rated_flow: float = 10.0          # 额定流量 (m³/s)
        self.rated_head: float = 100.0         # 额定扬程 (m)
        self.rated_power: float = 12000.0      # 额定功率 (kW)

        # 当前状态
        self.current_speed: float = 0.0        # 当前转速 (rpm)
        self.speed_setpoint: float = 0.0       # 目标转速 (rpm)
        self.current_flow: float = 0.0         # 当前流量 (m³/s)
        self.current_head: float = 0.0         # 当前扬程 (m)
        self.current_power: float = 0.0        # 当前功率 (kW)
        self.current_efficiency: float = 0.0  # 当前效率

        # 软启停参数
        self.min_start_time: float = 60.0      # 最小启动时间 (s)
        self.min_stop_time: float = 60.0       # 最小停止时间 (s)
        self._ramp_timer: float = 0.0
        self._ramp_duration: float = 60.0
        self._ramp_start_speed: float = 0.0
        self._ramp_target_speed: float = 0.0

        # 倒转保护参数
        self.max_reverse_ratio: float = 1.2    # 最大倒转速比
        self.max_reverse_time: float = 120.0   # 最大倒转时间 (s)
        self._reverse_timer: float = 0.0
        self._is_reversing: bool = False

        # 运行区边界
        self.efficiency_zone_min: float = 0.6  # 高效区最小流量比
        self.efficiency_zone_max: float = 1.2  # 高效区最大流量比
        self.saddle_zone_max: float = 0.4      # 马鞍区最大流量比
        self.cavitation_flow_ratio: float = 1.3 # 汽蚀区流量比

        # 振动与温度阈值
        self.vibration_warning: float = 4.5    # 振动警告值 (mm/s)
        self.vibration_alarm: float = 7.1      # 振动报警值 (mm/s)
        self.vibration_trip: float = 11.2      # 振动跳闸值 (mm/s)
        self.temperature_warning: float = 65.0 # 轴温警告 (°C)
        self.temperature_alarm: float = 75.0   # 轴温报警 (°C)
        self.temperature_trip: float = 85.0    # 轴温跳闸 (°C)

        # 闷泵保护
        self.deadhead_pressure: float = 1.8    # 闷泵压力 (MPa)
        self.deadhead_time: float = 30.0       # 闷泵时间限制 (s)
        self._deadhead_timer: float = 0.0

        # 传感器读数
        self._pressure_suction: float = 0.0    # 吸入压力
        self._pressure_discharge: float = 0.0  # 排出压力
        self._vibration: float = 0.0           # 振动值
        self._temperature: float = 0.0         # 轴温

        # 配置传感器量程
        self.add_sensor_range('speed', -2000, 2000)
        self.add_sensor_range('flow', 0, 20)
        self.add_sensor_range('P_suction', -0.1, 0.5)
        self.add_sensor_range('P_discharge', 0, 2.5)
        self.add_sensor_range('vibration', 0, 20)
        self.add_sensor_range('temperature', 0, 100)

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理传感器输入

        Args:
            sensor_data: 传感器数据
        """
        self.state.sensor_readings = sensor_data.copy()

        self.current_speed = sensor_data.get('speed', 0.0)
        self.current_flow = sensor_data.get('flow', 0.0)
        self._pressure_suction = sensor_data.get('P_suction', 0.0)
        self._pressure_discharge = sensor_data.get('P_discharge', 0.0)
        self._vibration = sensor_data.get('vibration', 0.0)
        self._temperature = sensor_data.get('temperature', 20.0)

        # 计算扬程
        self.current_head = (self._pressure_discharge - self._pressure_suction) * 1e6 / (1000 * 9.81)

        # 计算效率 (简化)
        if self.current_speed > 0 and self.current_flow > 0:
            speed_ratio = self.current_speed / self.rated_speed
            flow_ratio = self.current_flow / (self.rated_flow * speed_ratio)
            self.current_efficiency = 0.88 * (1 - 0.5 * (flow_ratio - 1) ** 2)
        else:
            self.current_efficiency = 0.0

        # 检测倒转
        self._is_reversing = self.current_speed < -10

        self.state.actual_position = self.current_speed / self.rated_speed

    def calculate_output(self) -> float:
        """计算转速控制输出

        Returns:
            转速指令 (rpm)
        """
        dt = 0.01  # 10ms控制周期

        if self.pump_mode == PumpControlMode.SOFT_START:
            return self._soft_start_control(dt)

        elif self.pump_mode == PumpControlMode.SOFT_STOP:
            return self._soft_stop_control(dt)

        elif self.pump_mode == PumpControlMode.SPEED:
            return self._speed_control(dt)

        elif self.pump_mode == PumpControlMode.EMERGENCY_STOP:
            return 0.0

        elif self.pump_mode == PumpControlMode.ANTI_SURGE:
            return self._anti_surge_control(dt)

        return self.current_speed

    def _soft_start_control(self, dt: float) -> float:
        """S形曲线软启动控制"""
        self._ramp_timer += dt

        if self._ramp_timer >= self._ramp_duration:
            # 启动完成
            self.pump_mode = PumpControlMode.SPEED
            return self._ramp_target_speed

        # S形曲线 (Sigmoid函数)
        progress = self._ramp_timer / self._ramp_duration
        # 使用修改后的S曲线，确保平滑
        s_curve = 1 / (1 + np.exp(-10 * (progress - 0.5)))

        target = self._ramp_start_speed + (self._ramp_target_speed - self._ramp_start_speed) * s_curve

        return target

    def _soft_stop_control(self, dt: float) -> float:
        """S形曲线软停止控制"""
        self._ramp_timer += dt

        if self._ramp_timer >= self._ramp_duration:
            self.pump_mode = PumpControlMode.SPEED
            self.state.is_running = False
            return 0.0

        progress = self._ramp_timer / self._ramp_duration
        # 反向S曲线
        s_curve = 1 - 1 / (1 + np.exp(-10 * (progress - 0.5)))

        target = self._ramp_start_speed * s_curve

        return target

    def _speed_control(self, dt: float) -> float:
        """转速控制"""
        error = self.speed_setpoint - self.current_speed
        max_rate = self.rated_speed / self.min_start_time  # 最大变化率

        if abs(error) < max_rate * dt:
            return self.speed_setpoint
        else:
            return self.current_speed + np.sign(error) * max_rate * dt

    def _anti_surge_control(self, dt: float) -> float:
        """防喘振控制"""
        # 如果在马鞍区，增加转速或减小阀门开度
        flow_ratio = self.current_flow / self.rated_flow
        speed_ratio = self.current_speed / self.rated_speed

        if flow_ratio / max(speed_ratio, 0.1) < self.saddle_zone_max:
            # 降低转速退出马鞍区
            return self.current_speed * 0.95
        else:
            return self.current_speed

    def execute_protection(self) -> bool:
        """执行保护逻辑"""
        protection_triggered = False
        dt = 0.01

        # 1. 倒转保护
        if self._is_reversing:
            self._reverse_timer += dt
            reverse_ratio = abs(self.current_speed) / self.rated_speed

            if reverse_ratio > self.max_reverse_ratio:
                self._raise_alarm(
                    "OVERSPEED_REVERSE",
                    AlarmLevel.CRITICAL,
                    f"倒转超速: {reverse_ratio:.2f} > {self.max_reverse_ratio}"
                )
                protection_triggered = True

            if self._reverse_timer > self.max_reverse_time:
                self._raise_alarm(
                    "REVERSE_TIMEOUT",
                    AlarmLevel.CRITICAL,
                    f"倒转超时: {self._reverse_timer:.0f}s > {self.max_reverse_time}s"
                )
                protection_triggered = True
        else:
            self._reverse_timer = 0.0

        # 2. 运行区间检查
        if self.current_speed > 100:
            zone = self._get_operating_zone()

            if zone == "SADDLE":
                self._raise_alarm(
                    "SADDLE_ZONE",
                    AlarmLevel.WARNING,
                    "运行在不稳定马鞍区"
                )
                self.pump_mode = PumpControlMode.ANTI_SURGE
                protection_triggered = True

            elif zone == "CAVITATION":
                self._raise_alarm(
                    "CAVITATION_RISK",
                    AlarmLevel.ALARM,
                    "存在汽蚀风险，建议降低转速"
                )
                # 自动降速
                self.speed_setpoint = self.current_speed * 0.9
                protection_triggered = True

        # 3. 振动保护
        if self._vibration > self.vibration_trip:
            self._raise_alarm(
                "VIBRATION_TRIP",
                AlarmLevel.CRITICAL,
                f"振动超限跳闸: {self._vibration:.1f} mm/s"
            )
            self.pump_mode = PumpControlMode.EMERGENCY_STOP
            protection_triggered = True
        elif self._vibration > self.vibration_alarm:
            self._raise_alarm(
                "VIBRATION_ALARM",
                AlarmLevel.ALARM,
                f"振动报警: {self._vibration:.1f} mm/s，自动降负荷"
            )
            self.speed_setpoint = self.current_speed * 0.8
            protection_triggered = True
        elif self._vibration > self.vibration_warning:
            self._raise_alarm(
                "VIBRATION_WARNING",
                AlarmLevel.WARNING,
                f"振动警告: {self._vibration:.1f} mm/s"
            )

        # 4. 温度保护
        if self._temperature > self.temperature_trip:
            self._raise_alarm(
                "TEMPERATURE_TRIP",
                AlarmLevel.CRITICAL,
                f"轴温超限跳闸: {self._temperature:.1f}°C"
            )
            self.pump_mode = PumpControlMode.EMERGENCY_STOP
            protection_triggered = True
        elif self._temperature > self.temperature_alarm:
            self._raise_alarm(
                "TEMPERATURE_ALARM",
                AlarmLevel.ALARM,
                f"轴温报警: {self._temperature:.1f}°C"
            )

        # 5. 闷泵保护
        if self._pressure_discharge > self.deadhead_pressure and self.current_flow < 0.5:
            self._deadhead_timer += dt
            if self._deadhead_timer > self.deadhead_time:
                self._raise_alarm(
                    "DEADHEAD",
                    AlarmLevel.CRITICAL,
                    f"闷泵保护触发: 压力={self._pressure_discharge:.2f}MPa, 时间={self._deadhead_timer:.0f}s"
                )
                self.pump_mode = PumpControlMode.EMERGENCY_STOP
                protection_triggered = True
        else:
            self._deadhead_timer = 0.0

        return protection_triggered

    def _get_operating_zone(self) -> str:
        """获取当前运行区域"""
        speed_ratio = self.current_speed / self.rated_speed
        if speed_ratio < 0.1:
            return "STOPPED"

        flow_ratio = self.current_flow / (self.rated_flow * speed_ratio)

        if flow_ratio < self.saddle_zone_max:
            return "SADDLE"
        elif flow_ratio > self.cavitation_flow_ratio:
            return "CAVITATION"
        elif self.efficiency_zone_min <= flow_ratio <= self.efficiency_zone_max:
            return "HIGH_EFFICIENCY"
        else:
            return "NORMAL"

    def command_start(self, target_speed: Optional[float] = None) -> None:
        """启动水泵

        Args:
            target_speed: 目标转速，默认额定转速
        """
        if target_speed is None:
            target_speed = self.rated_speed

        self.pump_mode = PumpControlMode.SOFT_START
        self._ramp_timer = 0.0
        self._ramp_start_speed = self.current_speed
        self._ramp_target_speed = target_speed
        self._ramp_duration = self.min_start_time
        self.speed_setpoint = target_speed
        self.state.is_running = True

    def command_stop(self, emergency: bool = False) -> None:
        """停止水泵

        Args:
            emergency: 是否紧急停止
        """
        if emergency:
            self.pump_mode = PumpControlMode.EMERGENCY_STOP
            self.speed_setpoint = 0.0
        else:
            self.pump_mode = PumpControlMode.SOFT_STOP
            self._ramp_timer = 0.0
            self._ramp_start_speed = self.current_speed
            self._ramp_duration = self.min_stop_time

    def set_speed(self, speed: float) -> None:
        """设置目标转速

        Args:
            speed: 目标转速 (rpm)
        """
        self.speed_setpoint = max(0, min(speed, self.rated_speed * 1.1))

    def get_performance(self) -> Dict:
        """获取当前性能参数"""
        return {
            'speed': self.current_speed,
            'speed_ratio': self.current_speed / self.rated_speed,
            'flow': self.current_flow,
            'head': self.current_head,
            'power': self.current_power,
            'efficiency': self.current_efficiency,
            'operating_zone': self._get_operating_zone(),
            'is_reversing': self._is_reversing,
            'reverse_time': self._reverse_timer if self._is_reversing else 0,
        }

    def reset(self) -> None:
        """复位控制器"""
        super().reset()
        self.current_speed = 0.0
        self.speed_setpoint = 0.0
        self._ramp_timer = 0.0
        self._reverse_timer = 0.0
        self._deadhead_timer = 0.0
        self._is_reversing = False
        self.pump_mode = PumpControlMode.SPEED
