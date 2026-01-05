# -*- coding: utf-8 -*-
"""虚拟传感器模块"""

from .virtual_sensors import (
    VirtualSensor,
    VirtualPressureSensor,
    VirtualFlowSensor,
    VirtualLevelSensor,
    VirtualSpeedSensor,
    SensorArray,
    SignalInjector,
    SensorFaultType,
)

__all__ = [
    'VirtualSensor',
    'VirtualPressureSensor',
    'VirtualFlowSensor',
    'VirtualLevelSensor',
    'VirtualSpeedSensor',
    'SensorArray',
    'SignalInjector',
    'SensorFaultType',
]
