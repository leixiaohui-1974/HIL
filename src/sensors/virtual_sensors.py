# -*- coding: utf-8 -*-
"""
虚拟传感器系统
Virtual Sensor System

实现HIL测试中的虚拟传感器，包括：
- 虚拟压力变送器
- 虚拟电磁流量计
- 虚拟超声波水位计
- 虚拟转速传感器

虚拟传感器运行在仿真机内存中，通过DA卡输出信号"欺骗"控制柜
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
import numpy as np
from enum import Enum


class SensorFaultType(Enum):
    """传感器故障类型"""
    NONE = "none"                    # 无故障
    SIGNAL_LOST = "signal_lost"      # 信号丢失
    DRIFT = "drift"                  # 漂移
    STUCK = "stuck"                  # 卡死
    NOISE = "noise"                  # 噪声过大
    FULL_SCALE = "full_scale"        # 满量程
    ZERO = "zero"                    # 零点


@dataclass
class SensorConfig:
    """传感器配置"""
    name: str                        # 传感器名称
    unit: str                        # 单位
    range_min: float                 # 量程下限
    range_max: float                 # 量程上限
    resolution: float = 0.001        # 分辨率
    response_time: float = 0.01      # 响应时间 (s)
    noise_level: float = 0.001       # 噪声水平 (相对值)
    sample_rate: float = 100.0       # 采样率 (Hz)


class VirtualSensor(ABC):
    """虚拟传感器基类"""

    def __init__(self, config: SensorConfig):
        """初始化

        Args:
            config: 传感器配置
        """
        self.config = config
        self.current_value: float = 0.0
        self.output_signal: float = 0.0  # 4-20mA 信号 (mA)
        self.fault_type = SensorFaultType.NONE
        self._fault_value: float = 0.0
        self._drift_rate: float = 0.0
        self._stuck_value: float = 0.0
        self._noise_amplitude: float = 0.0

        # 一阶滤波器状态
        self._filter_state: float = 0.0

    @abstractmethod
    def calculate_value(self, simulation_state: Dict) -> float:
        """从仿真状态计算传感器值

        Args:
            simulation_state: 仿真状态数据

        Returns:
            传感器物理量值
        """
        pass

    def update(self, simulation_state: Dict, dt: float = 0.01) -> float:
        """更新传感器读数

        Args:
            simulation_state: 仿真状态
            dt: 时间步长

        Returns:
            传感器输出值
        """
        # 计算物理量值
        raw_value = self.calculate_value(simulation_state)

        # 应用一阶滤波 (模拟响应时间)
        alpha = dt / (self.config.response_time + dt)
        self._filter_state = alpha * raw_value + (1 - alpha) * self._filter_state

        # 添加噪声
        noise = np.random.normal(0, self.config.noise_level * (self.config.range_max - self.config.range_min))
        self.current_value = self._filter_state + noise

        # 应用故障模式
        self.current_value = self._apply_fault(self.current_value, dt)

        # 限幅
        self.current_value = np.clip(self.current_value, self.config.range_min, self.config.range_max)

        # 转换为4-20mA信号
        self.output_signal = self._to_ma_signal(self.current_value)

        return self.current_value

    def _apply_fault(self, value: float, dt: float) -> float:
        """应用故障模式"""
        if self.fault_type == SensorFaultType.NONE:
            return value

        elif self.fault_type == SensorFaultType.SIGNAL_LOST:
            return 0.0  # 信号丢失返回0

        elif self.fault_type == SensorFaultType.DRIFT:
            self._fault_value += self._drift_rate * dt
            return value + self._fault_value

        elif self.fault_type == SensorFaultType.STUCK:
            return self._stuck_value  # 卡在某个值

        elif self.fault_type == SensorFaultType.NOISE:
            extra_noise = np.random.normal(0, self._noise_amplitude)
            return value + extra_noise

        elif self.fault_type == SensorFaultType.FULL_SCALE:
            return self.config.range_max

        elif self.fault_type == SensorFaultType.ZERO:
            return self.config.range_min

        return value

    def _to_ma_signal(self, value: float) -> float:
        """转换为4-20mA信号

        Args:
            value: 物理量值

        Returns:
            电流信号 (mA)
        """
        # 线性映射: range -> 4-20mA
        ratio = (value - self.config.range_min) / (self.config.range_max - self.config.range_min)
        return 4.0 + ratio * 16.0

    def inject_fault(self, fault_type: SensorFaultType, **kwargs) -> None:
        """注入故障

        Args:
            fault_type: 故障类型
            **kwargs: 故障参数
        """
        self.fault_type = fault_type

        if fault_type == SensorFaultType.DRIFT:
            self._drift_rate = kwargs.get('drift_rate', 0.01)
            self._fault_value = 0.0

        elif fault_type == SensorFaultType.STUCK:
            self._stuck_value = kwargs.get('stuck_value', self.current_value)

        elif fault_type == SensorFaultType.NOISE:
            self._noise_amplitude = kwargs.get('amplitude', 0.1)

    def clear_fault(self) -> None:
        """清除故障"""
        self.fault_type = SensorFaultType.NONE
        self._fault_value = 0.0

    def get_status(self) -> Dict:
        """获取传感器状态"""
        return {
            'name': self.config.name,
            'value': self.current_value,
            'unit': self.config.unit,
            'signal_ma': self.output_signal,
            'fault': self.fault_type.value,
            'in_range': self.config.range_min <= self.current_value <= self.config.range_max,
        }


class VirtualPressureSensor(VirtualSensor):
    """虚拟压力变送器

    模拟安装在阀门前后的压力传感器
    响应频率 1kHz，能复现水锤波的高频震荡
    """

    def __init__(self, location: str = "upstream", range_max: float = 2.5):
        """初始化

        Args:
            location: 安装位置 ("upstream" 或 "downstream")
            range_max: 量程上限 (MPa)
        """
        config = SensorConfig(
            name=f"P_{location}",
            unit="MPa",
            range_min=0.0,
            range_max=range_max,
            resolution=0.001,
            response_time=0.001,  # 1ms响应
            noise_level=0.002,
            sample_rate=1000.0,   # 1kHz采样
        )
        super().__init__(config)
        self.location = location

    def calculate_value(self, simulation_state: Dict) -> float:
        """计算压力值"""
        if self.location == "upstream":
            return simulation_state.get('pressure_upstream', 0.0)
        else:
            return simulation_state.get('pressure_downstream', 0.0)


class VirtualFlowSensor(VirtualSensor):
    """虚拟电磁流量计

    模拟安装在主管道上的流量计
    可模拟"气穴干扰"导致的信号波动
    """

    def __init__(self, range_max: float = 50.0):
        """初始化

        Args:
            range_max: 量程上限 (m³/s)
        """
        config = SensorConfig(
            name="Q",
            unit="m³/s",
            range_min=0.0,
            range_max=range_max,
            resolution=0.01,
            response_time=0.1,   # 100ms响应
            noise_level=0.005,
            sample_rate=100.0,
        )
        super().__init__(config)
        self._cavitation_active = False

    def calculate_value(self, simulation_state: Dict) -> float:
        """计算流量值"""
        flow = simulation_state.get('flow_rate', 0.0)

        # 模拟气穴干扰
        if self._cavitation_active:
            # 气穴时流量信号波动
            noise = np.random.uniform(-0.1, 0.1) * flow
            flow += noise

        return max(0.0, flow)

    def enable_cavitation_effect(self, enabled: bool = True) -> None:
        """启用气穴效果"""
        self._cavitation_active = enabled


class VirtualLevelSensor(VirtualSensor):
    """虚拟超声波水位计

    模拟安装在闸门上游的液位计
    支持注入"波浪噪声"干扰信号
    """

    def __init__(self, range_max: float = 10.0):
        """初始化

        Args:
            range_max: 量程上限 (m)
        """
        config = SensorConfig(
            name="Z",
            unit="m",
            range_min=0.0,
            range_max=range_max,
            resolution=0.001,
            response_time=0.5,   # 500ms响应
            noise_level=0.01,
            sample_rate=10.0,    # 10Hz采样
        )
        super().__init__(config)
        self._wave_amplitude = 0.0
        self._wave_period = 5.0

    def calculate_value(self, simulation_state: Dict) -> float:
        """计算水位值"""
        level = simulation_state.get('level_upstream', 0.0)

        # 添加波浪噪声
        if self._wave_amplitude > 0:
            t = simulation_state.get('time', 0.0)
            wave = self._wave_amplitude * np.sin(2 * np.pi * t / self._wave_period)
            level += wave

        return max(0.0, level)

    def set_wave_noise(self, amplitude: float, period: float = 5.0) -> None:
        """设置波浪噪声

        Args:
            amplitude: 波浪幅度 (m)
            period: 波浪周期 (s)
        """
        self._wave_amplitude = amplitude
        self._wave_period = period


class VirtualSpeedSensor(VirtualSensor):
    """虚拟转速传感器

    模拟水泵转速传感器
    可测量正转和倒转
    """

    def __init__(self, rated_speed: float = 1450.0):
        """初始化

        Args:
            rated_speed: 额定转速 (rpm)
        """
        config = SensorConfig(
            name="N",
            unit="rpm",
            range_min=-rated_speed * 2,
            range_max=rated_speed * 2,
            resolution=1.0,
            response_time=0.05,   # 50ms响应
            noise_level=0.005,
            sample_rate=100.0,
        )
        super().__init__(config)
        self.rated_speed = rated_speed

    def calculate_value(self, simulation_state: Dict) -> float:
        """计算转速值"""
        return simulation_state.get('pump_speed', 0.0)


class SensorArray:
    """传感器阵列

    管理一组虚拟传感器
    """

    def __init__(self):
        self.sensors: Dict[str, VirtualSensor] = {}

    def add_sensor(self, sensor: VirtualSensor) -> None:
        """添加传感器"""
        self.sensors[sensor.config.name] = sensor

    def update_all(self, simulation_state: Dict, dt: float = 0.01) -> Dict[str, float]:
        """更新所有传感器

        Returns:
            传感器读数字典
        """
        readings = {}
        for name, sensor in self.sensors.items():
            readings[name] = sensor.update(simulation_state, dt)
        return readings

    def get_ma_signals(self) -> Dict[str, float]:
        """获取所有传感器的4-20mA信号"""
        return {name: sensor.output_signal for name, sensor in self.sensors.items()}

    def inject_fault(self, sensor_name: str, fault_type: SensorFaultType, **kwargs) -> bool:
        """注入传感器故障

        Returns:
            是否成功
        """
        if sensor_name in self.sensors:
            self.sensors[sensor_name].inject_fault(fault_type, **kwargs)
            return True
        return False

    def clear_all_faults(self) -> None:
        """清除所有故障"""
        for sensor in self.sensors.values():
            sensor.clear_fault()

    def get_status(self) -> Dict[str, Dict]:
        """获取所有传感器状态"""
        return {name: sensor.get_status() for name, sensor in self.sensors.items()}


class SignalInjector:
    """信号注入器

    用于向控制柜注入虚拟传感器信号
    """

    def __init__(self, sensor_array: SensorArray):
        """初始化

        Args:
            sensor_array: 传感器阵列
        """
        self.sensor_array = sensor_array
        self._signal_mapping: Dict[str, str] = {}
        self._signal_processors: Dict[str, Callable] = {}

    def map_signal(self, sensor_name: str, controller_input: str) -> None:
        """映射传感器信号到控制器输入

        Args:
            sensor_name: 传感器名称
            controller_input: 控制器输入名称
        """
        self._signal_mapping[sensor_name] = controller_input

    def add_processor(self, sensor_name: str, processor: Callable[[float], float]) -> None:
        """添加信号处理器

        Args:
            sensor_name: 传感器名称
            processor: 处理函数
        """
        self._signal_processors[sensor_name] = processor

    def get_controller_inputs(self) -> Dict[str, float]:
        """获取控制器输入信号

        Returns:
            控制器输入字典
        """
        inputs = {}
        for sensor_name, input_name in self._signal_mapping.items():
            if sensor_name in self.sensor_array.sensors:
                value = self.sensor_array.sensors[sensor_name].current_value

                # 应用处理器
                if sensor_name in self._signal_processors:
                    value = self._signal_processors[sensor_name](value)

                inputs[input_name] = value

        return inputs

    @staticmethod
    def create_standard_valve_array() -> SensorArray:
        """创建标准阀门传感器阵列"""
        array = SensorArray()
        array.add_sensor(VirtualPressureSensor("upstream", 2.5))
        array.add_sensor(VirtualPressureSensor("downstream", 2.5))
        array.add_sensor(VirtualFlowSensor(50.0))
        return array

    @staticmethod
    def create_standard_pump_array() -> SensorArray:
        """创建标准水泵传感器阵列"""
        array = SensorArray()
        array.add_sensor(VirtualPressureSensor("suction", 0.5))
        array.add_sensor(VirtualPressureSensor("discharge", 2.5))
        array.add_sensor(VirtualFlowSensor(20.0))
        array.add_sensor(VirtualSpeedSensor(1450.0))
        return array

    @staticmethod
    def create_standard_gate_array() -> SensorArray:
        """创建标准闸门传感器阵列"""
        array = SensorArray()
        array.add_sensor(VirtualLevelSensor(10.0))
        array.add_sensor(VirtualFlowSensor(200.0))
        return array
