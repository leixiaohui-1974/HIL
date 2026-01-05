# -*- coding: utf-8 -*-
"""
HIL仿真测试平台
Hardware-in-the-Loop Simulation Platform

实现完整的HIL测试框架，包括：
- 虚实闭环接口
- 实时仿真控制
- 测试执行与报告生成
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import json

from .simulator import (
    HydraulicModel, PipeMOCModel, ChannelSaintVenantModel,
    PumpCharacteristics, PipeParameters, ChannelParameters
)
from .controllers import (
    BaseController, ValveController, PumpController, GateController
)
from .sensors import SensorArray, SignalInjector
from .test_cases import (
    HILTestSuite, ValveTestSuite, PumpTestSuite, GateTestSuite
)


class HILMode(Enum):
    """HIL运行模式"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class HILConfiguration:
    """HIL配置参数"""
    # 仿真参数
    simulation_dt: float = 0.01          # 仿真步长 (s)
    control_cycle: float = 0.01          # 控制周期 (s)
    realtime_factor: float = 1.0         # 实时因子 (1.0=实时)

    # 通信参数
    signal_update_rate: float = 100.0    # 信号刷新率 (Hz)
    io_latency: float = 0.001            # IO延迟 (s)

    # 记录参数
    record_interval: int = 10            # 记录间隔 (步)
    log_level: str = "INFO"

    # 管道参数 (用于阀门测试)
    pipe_length: float = 20000.0         # 管长 (m)
    pipe_diameter: float = 2.0           # 管径 (m)
    pipe_wave_speed: float = 1000.0      # 波速 (m/s)
    design_pressure: float = 1.6         # 设计压力 (MPa)

    # 渠道参数 (用于闸门测试)
    channel_length: float = 5000.0       # 渠长 (m)
    channel_width: float = 20.0          # 底宽 (m)
    channel_depth: float = 5.0           # 设计水深 (m)
    manning_n: float = 0.015             # 糙率


class HILPlatform:
    """HIL测试平台

    实现虚实结合的闭环测试：
    - 物理域：被测控制柜、执行机构
    - 数字域：水力仿真模型、虚拟传感器
    """

    def __init__(self, config: Optional[HILConfiguration] = None):
        """初始化

        Args:
            config: 平台配置
        """
        self.config = config or HILConfiguration()
        self.mode = HILMode.IDLE

        # 组件
        self.simulator: Optional[HydraulicModel] = None
        self.controller: Optional[BaseController] = None
        self.sensor_array: Optional[SensorArray] = None
        self.signal_injector: Optional[SignalInjector] = None

        # 测试套件
        self.test_suites: Dict[str, HILTestSuite] = {}

        # 运行状态
        self.current_time: float = 0.0
        self.step_count: int = 0
        self.history: List[Dict] = []

        # 回调
        self._callbacks: Dict[str, List[Callable]] = {
            'on_step': [],
            'on_test_start': [],
            'on_test_end': [],
            'on_error': [],
        }

    def setup_valve_test(self, pipe_params: Optional[PipeParameters] = None) -> None:
        """设置阀门测试环境

        Args:
            pipe_params: 管道参数
        """
        if pipe_params is None:
            pipe_params = PipeParameters(
                length=self.config.pipe_length,
                diameter=self.config.pipe_diameter,
                wave_speed=self.config.pipe_wave_speed,
                design_pressure=self.config.design_pressure,
            )

        self.simulator = PipeMOCModel(pipe_params, dt=self.config.simulation_dt)
        self.controller = ValveController("IVCU-001")
        self.sensor_array = SignalInjector.create_standard_valve_array()
        self.signal_injector = SignalInjector(self.sensor_array)

        # 信号映射
        self.signal_injector.map_signal('P_upstream', 'P1')
        self.signal_injector.map_signal('P_downstream', 'P2')
        self.signal_injector.map_signal('Q', 'Q')

        self.test_suites['valve'] = ValveTestSuite()

    def setup_pump_test(self) -> None:
        """设置水泵测试环境"""
        self.controller = PumpController("IPCU-001")
        self.sensor_array = SignalInjector.create_standard_pump_array()
        self.signal_injector = SignalInjector(self.sensor_array)

        self.signal_injector.map_signal('P_suction', 'P_suction')
        self.signal_injector.map_signal('P_discharge', 'P_discharge')
        self.signal_injector.map_signal('Q', 'flow')
        self.signal_injector.map_signal('N', 'speed')

        self.test_suites['pump'] = PumpTestSuite()

    def setup_gate_test(self, channel_params: Optional[ChannelParameters] = None) -> None:
        """设置闸门测试环境

        Args:
            channel_params: 渠道参数
        """
        if channel_params is None:
            channel_params = ChannelParameters(
                length=self.config.channel_length,
                bottom_width=self.config.channel_width,
                design_depth=self.config.channel_depth,
                manning_n=self.config.manning_n,
            )

        self.simulator = ChannelSaintVenantModel(channel_params, dt=self.config.simulation_dt)
        self.controller = GateController("IGCU-001")
        self.sensor_array = SignalInjector.create_standard_gate_array()
        self.signal_injector = SignalInjector(self.sensor_array)

        self.signal_injector.map_signal('Z', 'Z_up')
        self.signal_injector.map_signal('Q', 'Q')

        self.test_suites['gate'] = GateTestSuite()

    def run_test_suite(self, suite_name: str) -> Dict:
        """运行测试套件

        Args:
            suite_name: 套件名称 ('valve', 'pump', 'gate')

        Returns:
            测试结果摘要
        """
        if suite_name not in self.test_suites:
            raise ValueError(f"未知测试套件: {suite_name}")

        suite = self.test_suites[suite_name]
        self.mode = HILMode.RUNNING

        # 触发测试开始回调
        for callback in self._callbacks['on_test_start']:
            callback(suite_name)

        try:
            results = suite.run_all()
            self.mode = HILMode.COMPLETED
        except Exception as e:
            self.mode = HILMode.ERROR
            for callback in self._callbacks['on_error']:
                callback(e)
            raise

        # 触发测试结束回调
        for callback in self._callbacks['on_test_end']:
            callback(suite_name, results)

        return suite.get_summary()

    def run_single_test(self, suite_name: str, test_id: str) -> Dict:
        """运行单个测试

        Args:
            suite_name: 套件名称
            test_id: 测试编号

        Returns:
            测试结果
        """
        if suite_name not in self.test_suites:
            raise ValueError(f"未知测试套件: {suite_name}")

        suite = self.test_suites[suite_name]
        result = suite.run_by_id(test_id)

        if result is None:
            raise ValueError(f"未找到测试: {test_id}")

        return result.to_dict()

    def run_all_tests(self) -> Dict[str, Dict]:
        """运行所有测试套件

        Returns:
            所有套件的测试结果
        """
        results = {}

        for suite_name in self.test_suites:
            print(f"\n运行测试套件: {suite_name}")
            results[suite_name] = self.run_test_suite(suite_name)

        return results

    def step(self) -> Dict:
        """执行一个仿真步

        Returns:
            当前步的状态数据
        """
        if self.mode != HILMode.RUNNING:
            return {}

        dt = self.config.simulation_dt

        # 1. 仿真步进
        if self.simulator:
            sim_state = self.simulator.step()
        else:
            sim_state = None

        # 2. 更新虚拟传感器
        if self.sensor_array and sim_state:
            state_dict = sim_state.to_dict() if hasattr(sim_state, 'to_dict') else {}
            sensor_readings = self.sensor_array.update_all(state_dict, dt)
        else:
            sensor_readings = {}

        # 3. 获取控制器输入
        if self.signal_injector:
            controller_inputs = self.signal_injector.get_controller_inputs()
        else:
            controller_inputs = sensor_readings

        # 4. 运行控制器
        if self.controller:
            ctrl_result = self.controller.run_cycle(controller_inputs)
        else:
            ctrl_result = {}

        # 5. 更新执行机构
        if self.simulator and ctrl_result:
            output = ctrl_result.get('output', 0)
            if hasattr(self.simulator, 'set_valve_opening'):
                self.simulator.set_valve_opening(output)
            elif hasattr(self.simulator, 'set_gate_opening'):
                self.simulator.set_gate_opening(output)

        # 更新计数
        self.current_time += dt
        self.step_count += 1

        # 记录
        record = {
            'time': self.current_time,
            'step': self.step_count,
            'sensors': sensor_readings,
            'control': ctrl_result,
        }

        if self.step_count % self.config.record_interval == 0:
            self.history.append(record)

        # 触发回调
        for callback in self._callbacks['on_step']:
            callback(record)

        return record

    def reset(self) -> None:
        """重置平台状态"""
        self.current_time = 0.0
        self.step_count = 0
        self.history = []
        self.mode = HILMode.IDLE

        if self.simulator:
            self.simulator.reset()
        if self.controller:
            self.controller.reset()
        if self.sensor_array:
            self.sensor_array.clear_all_faults()

    def add_callback(self, event: str, callback: Callable) -> None:
        """添加事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def get_status(self) -> Dict:
        """获取平台状态"""
        return {
            'mode': self.mode.value,
            'time': self.current_time,
            'step_count': self.step_count,
            'simulator': type(self.simulator).__name__ if self.simulator else None,
            'controller': type(self.controller).__name__ if self.controller else None,
            'available_suites': list(self.test_suites.keys()),
        }

    def generate_report(self, results: Dict) -> str:
        """生成测试报告

        Args:
            results: 测试结果

        Returns:
            报告文本
        """
        lines = [
            "=" * 70,
            "水利枢纽智能控制柜 HIL 数字验收报告",
            "Hardware-in-the-Loop Digital FAT Report",
            "=" * 70,
            "",
            f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"平台版本: 1.0.0",
            "",
        ]

        total_tests = 0
        total_passed = 0

        for suite_name, summary in results.items():
            lines.append("-" * 70)
            lines.append(f"测试套件: {summary.get('suite_name', suite_name)}")
            lines.append("-" * 70)

            suite_total = summary.get('total', 0)
            suite_passed = summary.get('passed', 0)
            suite_failed = summary.get('failed', 0)
            suite_error = summary.get('error', 0)

            total_tests += suite_total
            total_passed += suite_passed

            lines.append(f"  总计: {suite_total} | 通过: {suite_passed} | "
                        f"失败: {suite_failed} | 错误: {suite_error}")
            lines.append(f"  通过率: {summary.get('pass_rate', 0)*100:.1f}%")
            lines.append("")

            for result in summary.get('results', []):
                status_icon = "✓" if result.get('passed') else "✗"
                lines.append(f"  {status_icon} [{result['test_id']}] {result['test_name']}")
                lines.append(f"      状态: {result['status']} | 耗时: {result['duration']:.2f}s")

                for criterion, passed in result.get('criteria', {}).items():
                    c_icon = "✓" if passed else "✗"
                    measurement = result.get('measurements', {}).get(criterion, '')
                    if measurement:
                        lines.append(f"        {c_icon} {criterion}: {measurement}")
                    else:
                        lines.append(f"        {c_icon} {criterion}")
                lines.append("")

        lines.append("=" * 70)
        lines.append("总体结果")
        lines.append("=" * 70)
        lines.append(f"  测试总数: {total_tests}")
        lines.append(f"  通过数量: {total_passed}")
        lines.append(f"  总体通过率: {total_passed/total_tests*100:.1f}%" if total_tests > 0 else "  N/A")

        if total_passed == total_tests and total_tests > 0:
            lines.append("")
            lines.append("  ★★★ 所有测试通过，设备符合 HIL 数字验收标准 ★★★")
            lines.append("  建议: 可贴 'HIL Verified' 标签出厂")
        else:
            lines.append("")
            lines.append("  ⚠ 部分测试未通过，需进一步检查和调试")

        lines.append("=" * 70)

        return "\n".join(lines)

    def export_results(self, results: Dict, filename: str) -> None:
        """导出测试结果到JSON文件

        Args:
            results: 测试结果
            filename: 文件名
        """
        export_data = {
            'platform': 'HIL Water Control System',
            'version': '1.0.0',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'configuration': {
                'simulation_dt': self.config.simulation_dt,
                'control_cycle': self.config.control_cycle,
            },
            'results': results,
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)


def create_platform(test_type: str = 'all') -> HILPlatform:
    """创建预配置的HIL平台

    Args:
        test_type: 测试类型 ('valve', 'pump', 'gate', 'all')

    Returns:
        配置好的HIL平台
    """
    platform = HILPlatform()

    if test_type in ('valve', 'all'):
        platform.setup_valve_test()

    if test_type in ('pump', 'all'):
        platform.setup_pump_test()

    if test_type in ('gate', 'all'):
        platform.setup_gate_test()

    return platform
