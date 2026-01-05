# -*- coding: utf-8 -*-
"""
智能控制器基类
Base Smart Controller Class

定义智能控制柜的通用接口和功能，包括：
- 状态机管理
- 报警处理
- 控制模式切换
- 传感器信号处理
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum, IntEnum
import time


class ControlMode(Enum):
    """控制模式"""
    AUTO = "auto"               # 自动模式
    MANUAL = "manual"           # 手动模式
    REMOTE = "remote"           # 远程模式
    EMERGENCY = "emergency"     # 紧急模式
    DEGRADED = "degraded"       # 降级模式
    MAINTENANCE = "maintenance" # 维护模式


class AlarmLevel(IntEnum):
    """报警等级 (使用IntEnum支持比较)"""
    INFO = 0          # 信息
    WARNING = 1       # 警告
    ALARM = 2         # 报警
    CRITICAL = 3      # 严重
    EMERGENCY = 4     # 紧急


@dataclass
class Alarm:
    """报警信息"""
    code: str                    # 报警代码
    level: AlarmLevel           # 报警等级
    message: str                # 报警消息
    timestamp: float            # 时间戳
    acknowledged: bool = False  # 是否已确认
    source: str = ""            # 报警来源


@dataclass
class ControllerState:
    """控制器状态"""
    mode: ControlMode = ControlMode.AUTO
    is_running: bool = False
    is_fault: bool = False
    output_command: float = 0.0      # 输出指令值
    actual_position: float = 0.0     # 实际位置/状态
    setpoint: float = 0.0            # 设定值
    error: float = 0.0               # 偏差
    alarms: List[Alarm] = field(default_factory=list)
    last_update: float = 0.0

    # 传感器读数
    sensor_readings: Dict[str, float] = field(default_factory=dict)

    # 状态标志
    sensor_fault: bool = False
    communication_fault: bool = False
    actuator_fault: bool = False

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'mode': self.mode.value,
            'is_running': self.is_running,
            'is_fault': self.is_fault,
            'output_command': self.output_command,
            'actual_position': self.actual_position,
            'setpoint': self.setpoint,
            'error': self.error,
            'alarm_count': len(self.alarms),
            'sensor_readings': self.sensor_readings,
        }


class BaseController(ABC):
    """智能控制器抽象基类

    实现控制器的通用功能框架
    """

    # 控制周期 (ms)
    CONTROL_CYCLE_MS: int = 10
    # 最大响应延迟 (ms)
    MAX_RESPONSE_DELAY_MS: int = 50

    def __init__(self, controller_id: str):
        """初始化

        Args:
            controller_id: 控制器标识
        """
        self.controller_id = controller_id
        self.state = ControllerState()
        self._callbacks: Dict[str, List[Callable]] = {
            'on_alarm': [],
            'on_mode_change': [],
            'on_fault': [],
            'on_command': [],
        }

        # 传感器配置
        self._sensor_ranges: Dict[str, tuple] = {}
        self._sensor_validity: Dict[str, bool] = {}

        # 时间记录
        self._last_cycle_time: float = 0
        self._cycle_count: int = 0

        # 保护参数
        self._protection_enabled: bool = True
        self._interlock_conditions: List[Callable] = []

    @abstractmethod
    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理输入信号

        Args:
            sensor_data: 传感器数据字典
        """
        pass

    @abstractmethod
    def calculate_output(self) -> float:
        """计算控制输出

        Returns:
            输出指令值
        """
        pass

    @abstractmethod
    def execute_protection(self) -> bool:
        """执行保护逻辑

        Returns:
            是否触发保护动作
        """
        pass

    def run_cycle(self, sensor_data: Dict[str, float]) -> Dict:
        """执行一个控制周期

        Args:
            sensor_data: 传感器数据

        Returns:
            控制周期结果
        """
        cycle_start = time.time()
        self._cycle_count += 1

        # 1. 处理输入信号
        self.process_inputs(sensor_data)

        # 2. 检查传感器有效性
        self._validate_sensors(sensor_data)

        # 3. 执行保护逻辑
        protection_triggered = False
        if self._protection_enabled:
            protection_triggered = self.execute_protection()

        # 4. 计算控制输出
        if not protection_triggered and not self.state.is_fault:
            self.state.output_command = self.calculate_output()
        elif protection_triggered:
            # 保护动作已在 execute_protection 中设置输出

            pass

        # 5. 检查联锁条件
        self._check_interlocks()

        # 6. 更新状态
        cycle_time = (time.time() - cycle_start) * 1000  # ms
        self.state.last_update = time.time()

        # 检查周期时间
        if cycle_time > self.MAX_RESPONSE_DELAY_MS:
            self._raise_alarm(
                "CYCLE_OVERRUN",
                AlarmLevel.WARNING,
                f"控制周期超时: {cycle_time:.1f}ms"
            )

        return {
            'output': self.state.output_command,
            'cycle_time_ms': cycle_time,
            'protection_triggered': protection_triggered,
            'state': self.state.to_dict(),
        }

    def _validate_sensors(self, sensor_data: Dict[str, float]) -> None:
        """验证传感器数据有效性"""
        for name, value in sensor_data.items():
            if name in self._sensor_ranges:
                min_val, max_val = self._sensor_ranges[name]
                is_valid = min_val <= value <= max_val

                if not is_valid and self._sensor_validity.get(name, True):
                    # 传感器刚变为无效
                    self._raise_alarm(
                        f"SENSOR_{name.upper()}_FAULT",
                        AlarmLevel.ALARM,
                        f"传感器 {name} 读数异常: {value}"
                    )
                    self.state.sensor_fault = True

                self._sensor_validity[name] = is_valid

    def _check_interlocks(self) -> None:
        """检查联锁条件"""
        for condition in self._interlock_conditions:
            if not condition(self.state):
                self._raise_alarm(
                    "INTERLOCK",
                    AlarmLevel.CRITICAL,
                    "联锁条件不满足"
                )
                self.state.is_fault = True
                break

    def _raise_alarm(self, code: str, level: AlarmLevel, message: str) -> None:
        """触发报警

        Args:
            code: 报警代码
            level: 报警等级
            message: 报警消息
        """
        alarm = Alarm(
            code=code,
            level=level,
            message=message,
            timestamp=time.time(),
            source=self.controller_id
        )
        self.state.alarms.append(alarm)

        # 触发回调
        for callback in self._callbacks['on_alarm']:
            callback(alarm)

        # 高级别报警触发故障状态
        if level >= AlarmLevel.CRITICAL:
            self.state.is_fault = True
            for callback in self._callbacks['on_fault']:
                callback(self.state)

    def set_mode(self, mode: ControlMode) -> bool:
        """设置控制模式

        Args:
            mode: 目标模式

        Returns:
            是否成功切换
        """
        old_mode = self.state.mode

        # 检查模式切换条件
        if self.state.is_fault and mode != ControlMode.MAINTENANCE:
            return False

        self.state.mode = mode

        # 触发回调
        for callback in self._callbacks['on_mode_change']:
            callback(old_mode, mode)

        return True

    def set_setpoint(self, value: float) -> None:
        """设置目标值

        Args:
            value: 目标值
        """
        self.state.setpoint = value

    def acknowledge_alarms(self) -> int:
        """确认所有报警

        Returns:
            确认的报警数量
        """
        count = 0
        for alarm in self.state.alarms:
            if not alarm.acknowledged:
                alarm.acknowledged = True
                count += 1
        return count

    def clear_alarms(self, level: Optional[AlarmLevel] = None) -> int:
        """清除报警

        Args:
            level: 指定等级，None表示清除所有

        Returns:
            清除的报警数量
        """
        if level is None:
            count = len(self.state.alarms)
            self.state.alarms = []
        else:
            original = len(self.state.alarms)
            self.state.alarms = [a for a in self.state.alarms if a.level != level]
            count = original - len(self.state.alarms)

        # 检查是否可以清除故障状态
        if not any(a.level >= AlarmLevel.CRITICAL for a in self.state.alarms):
            self.state.is_fault = False

        return count

    def reset(self) -> None:
        """复位控制器"""
        self.state = ControllerState()
        self._sensor_validity = {}
        self._cycle_count = 0

    def add_callback(self, event: str, callback: Callable) -> None:
        """添加事件回调

        Args:
            event: 事件名称
            callback: 回调函数
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def add_sensor_range(self, name: str, min_val: float, max_val: float) -> None:
        """添加传感器量程

        Args:
            name: 传感器名称
            min_val: 最小值
            max_val: 最大值
        """
        self._sensor_ranges[name] = (min_val, max_val)

    def add_interlock(self, condition: Callable[[ControllerState], bool]) -> None:
        """添加联锁条件

        Args:
            condition: 联锁检查函数
        """
        self._interlock_conditions.append(condition)

    def get_diagnostics(self) -> Dict:
        """获取诊断信息

        Returns:
            诊断数据字典
        """
        return {
            'controller_id': self.controller_id,
            'mode': self.state.mode.value,
            'cycle_count': self._cycle_count,
            'is_running': self.state.is_running,
            'is_fault': self.state.is_fault,
            'active_alarms': len([a for a in self.state.alarms if not a.acknowledged]),
            'sensor_status': self._sensor_validity,
            'last_update': self.state.last_update,
        }
