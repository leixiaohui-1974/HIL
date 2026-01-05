# -*- coding: utf-8 -*-
"""测试工况模块"""

from .base_test import HILTestCase, HILTestSuite, TestResult, TestStatus
from .valve_cases import ValveTestCase, ValveTestSuite
from .pump_cases import PumpTestCase, PumpTestSuite
from .gate_cases import GateTestCase, GateTestSuite
from .multi_valve_cases import (
    MultiValveTestSuite,
    FPV01_FlowRegulationAccuracy,
    FPV02_PressureRegulation,
    WHV01_ReliefResponse,
    WHV02_AutoReset,
    ESV01_PowerFailTrip,
    ESV02_OverpressureTrip,
    ESV03_InterlockTrip,
)

__all__ = [
    'HILTestCase',
    'HILTestSuite',
    'TestResult',
    'TestStatus',
    'ValveTestCase',
    'ValveTestSuite',
    'PumpTestCase',
    'PumpTestSuite',
    'GateTestCase',
    'GateTestSuite',
    'MultiValveTestSuite',
]
