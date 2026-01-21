# -*- coding: utf-8 -*-
"""
HIL Enhanced - 增强的硬件在环测试框架
Enhanced Hardware-In-the-Loop Testing Framework

提供完整的硬件在环测试能力
包括硬件接口、信号调理、故障注入和同步机制
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Tuple, Union
from datetime import datetime
import time
import threading
import queue
import copy


class HardwareType(Enum):
    """硬件类型"""
    ANALOG_INPUT = auto()       # 模拟输入
    ANALOG_OUTPUT = auto()      # 模拟输出
    DIGITAL_INPUT = auto()      # 数字输入
    DIGITAL_OUTPUT = auto()     # 数字输出
    PWM_OUTPUT = auto()         # PWM输出
    ENCODER_INPUT = auto()      # 编码器输入
    CAN_BUS = auto()            # CAN总线
    MODBUS = auto()             # Modbus通信
    ETHERNET = auto()           # 以太网
    RS485 = auto()              # RS485串口
    PROFINET = auto()           # PROFINET


class SignalType(Enum):
    """信号类型"""
    VOLTAGE = auto()            # 电压信号
    CURRENT = auto()            # 电流信号 (4-20mA)
    RESISTANCE = auto()         # 电阻信号
    FREQUENCY = auto()          # 频率信号
    PULSE = auto()              # 脉冲信号
    DIGITAL = auto()            # 数字信号


class FaultMode(Enum):
    """故障模式"""
    OPEN_CIRCUIT = auto()       # 开路
    SHORT_CIRCUIT = auto()      # 短路
    STUCK_HIGH = auto()         # 卡高
    STUCK_LOW = auto()          # 卡低
    DRIFT = auto()              # 漂移
    NOISE = auto()              # 噪声
    OFFSET = auto()             # 偏移
    GAIN_ERROR = auto()         # 增益误差
    DELAY = auto()              # 延迟
    INTERMITTENT = auto()       # 间歇故障
    PACKET_LOSS = auto()        # 丢包(通信)
    BIT_ERROR = auto()          # 位错误


class SyncMode(Enum):
    """同步模式"""
    FREE_RUNNING = auto()       # 自由运行
    HARDWARE_SYNC = auto()      # 硬件同步
    SOFTWARE_SYNC = auto()      # 软件同步
    EXTERNAL_TRIGGER = auto()   # 外部触发


@dataclass
class HardwareChannel:
    """硬件通道"""
    channel_id: str                         # 通道ID
    name: str                               # 名称
    hardware_type: HardwareType             # 硬件类型
    signal_type: SignalType                 # 信号类型

    # 信号范围
    min_value: float = 0.0                  # 最小值
    max_value: float = 10.0                 # 最大值
    resolution: int = 16                    # 分辨率(位)

    # 物理量映射
    engineering_unit: str = ""              # 工程单位
    scale_factor: float = 1.0               # 缩放系数
    offset: float = 0.0                     # 偏移量

    # 校准参数
    calibration_date: Optional[str] = None
    calibration_coefficients: List[float] = field(default_factory=list)

    # 状态
    enabled: bool = True
    current_value: float = 0.0
    fault_state: Optional[FaultMode] = None

    def to_engineering(self, raw_value: float) -> float:
        """转换为工程值"""
        return raw_value * self.scale_factor + self.offset

    def to_raw(self, eng_value: float) -> float:
        """转换为原始值"""
        return (eng_value - self.offset) / self.scale_factor


@dataclass
class SignalConditionerConfig:
    """信号调理器配置"""
    filter_type: str = "LOWPASS"            # 滤波器类型
    cutoff_frequency: float = 100.0         # 截止频率(Hz)
    filter_order: int = 2                   # 滤波器阶数
    gain: float = 1.0                       # 增益
    input_impedance: float = 1e6            # 输入阻抗(Ω)
    isolation: bool = True                  # 隔离


class HardwareInterface(ABC):
    """硬件接口基类"""

    def __init__(self, interface_id: str, name: str):
        self.interface_id = interface_id
        self.name = name
        self.channels: Dict[str, HardwareChannel] = {}
        self.connected = False
        self.error_count = 0
        self.last_error: Optional[str] = None

    @abstractmethod
    def connect(self) -> bool:
        """连接硬件"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass

    @abstractmethod
    def read(self, channel_id: str) -> float:
        """读取通道"""
        pass

    @abstractmethod
    def write(self, channel_id: str, value: float) -> bool:
        """写入通道"""
        pass

    def add_channel(self, channel: HardwareChannel):
        """添加通道"""
        self.channels[channel.channel_id] = channel

    def get_status(self) -> Dict[str, Any]:
        """获取接口状态"""
        return {
            'interface_id': self.interface_id,
            'name': self.name,
            'connected': self.connected,
            'channel_count': len(self.channels),
            'error_count': self.error_count,
            'last_error': self.last_error
        }


class SimulatedHardwareInterface(HardwareInterface):
    """模拟硬件接口 - 用于软件仿真"""

    def __init__(self, interface_id: str, name: str):
        super().__init__(interface_id, name)
        self._values: Dict[str, float] = {}

    def connect(self) -> bool:
        self.connected = True
        return True

    def disconnect(self) -> bool:
        self.connected = False
        return True

    def read(self, channel_id: str) -> float:
        if channel_id in self.channels:
            channel = self.channels[channel_id]
            raw_value = self._values.get(channel_id, 0.0)
            return channel.to_engineering(raw_value)
        return 0.0

    def write(self, channel_id: str, value: float) -> bool:
        if channel_id in self.channels:
            channel = self.channels[channel_id]
            self._values[channel_id] = channel.to_raw(value)
            channel.current_value = value
            return True
        return False

    def set_simulated_input(self, channel_id: str, value: float):
        """设置模拟输入值"""
        self._values[channel_id] = value


class SignalConditioner:
    """信号调理器"""

    def __init__(self, config: SignalConditionerConfig = None):
        self.config = config or SignalConditionerConfig()
        self._history: List[float] = []
        self._filter_state = [0.0] * self.config.filter_order

    def process(self, value: float) -> float:
        """处理信号"""
        # 应用增益
        value = value * self.config.gain

        # 简单低通滤波 (一阶IIR)
        if self.config.filter_type == "LOWPASS":
            alpha = 0.1  # 简化的滤波系数
            if self._history:
                value = alpha * value + (1 - alpha) * self._history[-1]

        self._history.append(value)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        return value

    def reset(self):
        """重置状态"""
        self._history = []
        self._filter_state = [0.0] * self.config.filter_order


@dataclass
class FaultInjectionConfig:
    """故障注入配置"""
    fault_id: str                           # 故障ID
    channel_id: str                         # 目标通道
    fault_mode: FaultMode                   # 故障模式
    start_time: float = 0.0                 # 开始时间
    duration: float = -1.0                  # 持续时间(-1表示永久)
    parameters: Dict[str, Any] = field(default_factory=dict)  # 故障参数

    # 故障参数示例:
    # DRIFT: {'rate': 0.01}  # 漂移率
    # NOISE: {'amplitude': 0.1, 'frequency': 50}  # 噪声幅值和频率
    # OFFSET: {'value': 1.0}  # 偏移值
    # DELAY: {'time': 0.1}  # 延迟时间
    # INTERMITTENT: {'probability': 0.1, 'duration': 0.5}  # 间歇概率和持续


class FaultInjector:
    """故障注入器"""

    def __init__(self):
        self.active_faults: Dict[str, FaultInjectionConfig] = {}
        self.fault_history: List[Dict] = []
        self._start_time: float = 0.0
        self._current_time: float = 0.0

    def start(self):
        """开始故障注入会话"""
        self._start_time = time.time()
        self._current_time = 0.0

    def add_fault(self, config: FaultInjectionConfig):
        """添加故障"""
        self.active_faults[config.fault_id] = config
        self._log_event('FAULT_ADDED', config)

    def remove_fault(self, fault_id: str) -> bool:
        """移除故障"""
        if fault_id in self.active_faults:
            config = self.active_faults.pop(fault_id)
            self._log_event('FAULT_REMOVED', config)
            return True
        return False

    def update_time(self, sim_time: float):
        """更新仿真时间"""
        self._current_time = sim_time

    def apply_fault(self, channel_id: str, value: float) -> float:
        """应用故障到信号"""
        for fault_id, config in self.active_faults.items():
            if config.channel_id != channel_id:
                continue

            # 检查故障是否激活
            if self._current_time < config.start_time:
                continue

            if config.duration > 0 and self._current_time > config.start_time + config.duration:
                continue

            # 应用故障
            value = self._apply_fault_mode(value, config)

        return value

    def _apply_fault_mode(self, value: float, config: FaultInjectionConfig) -> float:
        """应用故障模式"""
        mode = config.fault_mode
        params = config.parameters

        if mode == FaultMode.STUCK_HIGH:
            return params.get('high_value', 10.0)

        elif mode == FaultMode.STUCK_LOW:
            return params.get('low_value', 0.0)

        elif mode == FaultMode.OPEN_CIRCUIT:
            return float('nan')

        elif mode == FaultMode.SHORT_CIRCUIT:
            return 0.0

        elif mode == FaultMode.DRIFT:
            rate = params.get('rate', 0.01)
            elapsed = self._current_time - config.start_time
            return value + rate * elapsed

        elif mode == FaultMode.NOISE:
            import random
            amplitude = params.get('amplitude', 0.1)
            return value + random.uniform(-amplitude, amplitude)

        elif mode == FaultMode.OFFSET:
            offset = params.get('value', 0.0)
            return value + offset

        elif mode == FaultMode.GAIN_ERROR:
            gain = params.get('gain', 1.1)
            return value * gain

        elif mode == FaultMode.DELAY:
            # 简化实现 - 实际需要缓冲区
            return value

        elif mode == FaultMode.INTERMITTENT:
            import random
            probability = params.get('probability', 0.1)
            if random.random() < probability:
                return float('nan')
            return value

        return value

    def _log_event(self, event_type: str, config: FaultInjectionConfig):
        """记录事件"""
        self.fault_history.append({
            'timestamp': datetime.now().isoformat(),
            'sim_time': self._current_time,
            'event': event_type,
            'fault_id': config.fault_id,
            'channel': config.channel_id,
            'mode': config.fault_mode.name
        })

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            'active_faults': len(self.active_faults),
            'faults': {fid: {
                'channel': cfg.channel_id,
                'mode': cfg.fault_mode.name,
                'start': cfg.start_time,
                'duration': cfg.duration
            } for fid, cfg in self.active_faults.items()}
        }


class HILSynchronizer:
    """HIL同步器 - 管理实时同步"""

    def __init__(self, target_rate: float = 1000.0):
        self.target_rate = target_rate      # 目标采样率(Hz)
        self.target_period = 1.0 / target_rate
        self.sync_mode = SyncMode.SOFTWARE_SYNC
        self._running = False
        self._lock = threading.Lock()

        # 统计信息
        self.cycle_count = 0
        self.overrun_count = 0
        self.max_jitter = 0.0
        self.avg_jitter = 0.0
        self._jitter_sum = 0.0
        self._last_cycle_time = 0.0

    def start(self):
        """启动同步"""
        self._running = True
        self._last_cycle_time = time.time()
        self.cycle_count = 0
        self.overrun_count = 0

    def stop(self):
        """停止同步"""
        self._running = False

    def wait_for_next_cycle(self) -> float:
        """等待下一个周期"""
        if not self._running:
            return 0.0

        current_time = time.time()
        elapsed = current_time - self._last_cycle_time
        remaining = self.target_period - elapsed

        if remaining > 0:
            time.sleep(remaining)
        else:
            self.overrun_count += 1

        # 计算抖动
        actual_period = time.time() - self._last_cycle_time
        jitter = abs(actual_period - self.target_period)
        self._jitter_sum += jitter
        self.cycle_count += 1

        if jitter > self.max_jitter:
            self.max_jitter = jitter
        self.avg_jitter = self._jitter_sum / self.cycle_count

        self._last_cycle_time = time.time()
        return actual_period

    def get_timing_stats(self) -> Dict[str, Any]:
        """获取时序统计"""
        return {
            'target_rate': self.target_rate,
            'cycle_count': self.cycle_count,
            'overrun_count': self.overrun_count,
            'overrun_rate': self.overrun_count / max(1, self.cycle_count) * 100,
            'max_jitter_us': self.max_jitter * 1e6,
            'avg_jitter_us': self.avg_jitter * 1e6
        }


@dataclass
class HILTestCase:
    """HIL测试用例"""
    test_id: str                            # 测试ID
    name: str                               # 名称
    description: str                        # 描述
    category: str = "FUNCTIONAL"            # 类别

    # 关联
    requirements: List[str] = field(default_factory=list)
    safety_goals: List[str] = field(default_factory=list)

    # 硬件配置
    required_interfaces: List[str] = field(default_factory=list)
    input_channels: List[str] = field(default_factory=list)
    output_channels: List[str] = field(default_factory=list)

    # 测试参数
    duration: float = 60.0                  # 测试持续时间(秒)
    sample_rate: float = 1000.0             # 采样率(Hz)
    real_time: bool = True                  # 是否实时测试

    # 激励和预期
    stimuli: Dict[str, List[Tuple[float, Any]]] = field(default_factory=dict)
    expected_responses: Dict[str, Any] = field(default_factory=dict)
    tolerances: Dict[str, float] = field(default_factory=dict)

    # 故障注入
    fault_injections: List[FaultInjectionConfig] = field(default_factory=list)

    # 结果
    result: str = "NOT_RUN"
    actual_responses: Dict[str, Any] = field(default_factory=dict)
    recorded_data: Dict[str, List] = field(default_factory=dict)
    timing_stats: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


class HILTestEnvironment:
    """HIL测试环境"""

    def __init__(self, env_id: str, name: str):
        self.env_id = env_id
        self.name = name

        # 组件
        self.hardware_interfaces: Dict[str, HardwareInterface] = {}
        self.signal_conditioners: Dict[str, SignalConditioner] = {}
        self.fault_injector = FaultInjector()
        self.synchronizer = HILSynchronizer()

        # 被测系统 (UUT - Unit Under Test)
        self.plant_model = None
        self.uut_interface: Optional[HardwareInterface] = None

        # 状态
        self.initialized = False
        self.running = False
        self.current_time = 0.0

        # 数据记录
        self.data_recorder: Dict[str, List] = {}
        self.event_log: List[Dict] = []

    def add_hardware_interface(self, interface: HardwareInterface):
        """添加硬件接口"""
        self.hardware_interfaces[interface.interface_id] = interface

    def add_signal_conditioner(self, channel_id: str, conditioner: SignalConditioner):
        """添加信号调理器"""
        self.signal_conditioners[channel_id] = conditioner

    def set_plant_model(self, model: Any):
        """设置被控对象模型"""
        self.plant_model = model

    def set_uut_interface(self, interface: HardwareInterface):
        """设置被测单元接口"""
        self.uut_interface = interface

    def initialize(self) -> bool:
        """初始化环境"""
        try:
            # 连接所有硬件接口
            for interface in self.hardware_interfaces.values():
                if not interface.connect():
                    self._log_event("ERROR", f"Failed to connect interface {interface.interface_id}")
                    return False

            if self.uut_interface and not self.uut_interface.connected:
                if not self.uut_interface.connect():
                    self._log_event("ERROR", "Failed to connect UUT interface")
                    return False

            # 初始化被控对象模型
            if self.plant_model and hasattr(self.plant_model, 'initialize'):
                self.plant_model.initialize()

            # 初始化故障注入器
            self.fault_injector.start()

            self.initialized = True
            self.current_time = 0.0
            self._log_event("INITIALIZED", "HIL environment initialized")
            return True

        except Exception as e:
            self._log_event("ERROR", f"Initialization failed: {str(e)}")
            return False

    def run_test(self, test_case: HILTestCase) -> Dict[str, Any]:
        """运行HIL测试"""
        if not self.initialized:
            return {'result': 'ERROR', 'message': 'Environment not initialized'}

        test_case.result = "RUNNING"
        self.running = True
        start_time = time.time()

        # 设置同步器
        self.synchronizer.target_rate = test_case.sample_rate
        self.synchronizer.start()

        # 配置故障注入
        for fault_config in test_case.fault_injections:
            self.fault_injector.add_fault(fault_config)

        # 初始化数据记录
        self.data_recorder = {ch: [] for ch in test_case.input_channels + test_case.output_channels}
        self.data_recorder['time'] = []

        try:
            dt = 1.0 / test_case.sample_rate
            while self.current_time < test_case.duration and self.running:
                # 同步等待
                if test_case.real_time:
                    self.synchronizer.wait_for_next_cycle()

                # 获取当前激励
                current_stimuli = {}
                for signal, schedule in test_case.stimuli.items():
                    current_stimuli[signal] = self._get_scheduled_value(schedule, self.current_time)

                # 执行一步
                outputs = self._execute_step(current_stimuli, dt)

                # 记录数据
                self._record_step(outputs)

                # 更新时间
                self.current_time += dt
                self.fault_injector.update_time(self.current_time)

            # 停止同步
            self.synchronizer.stop()

            # 验证结果
            test_case.recorded_data = self.data_recorder
            test_case.timing_stats = self.synchronizer.get_timing_stats()
            passed, message = self._verify_results(test_case)

            test_case.result = "PASSED" if passed else "FAILED"
            test_case.error_message = message

        except Exception as e:
            test_case.result = "ERROR"
            test_case.error_message = str(e)

        finally:
            self.running = False
            # 清理故障注入
            for fault_config in test_case.fault_injections:
                self.fault_injector.remove_fault(fault_config.fault_id)

        return {
            'test_id': test_case.test_id,
            'result': test_case.result,
            'error_message': test_case.error_message,
            'timing_stats': test_case.timing_stats,
            'execution_time': time.time() - start_time
        }

    def _execute_step(self, stimuli: Dict[str, Any], dt: float) -> Dict[str, Any]:
        """执行一步仿真/测试"""
        outputs = {}

        # 1. 写入激励到输出通道
        for channel_id, value in stimuli.items():
            # 应用故障注入
            value = self.fault_injector.apply_fault(channel_id, value)
            # 写入硬件
            for interface in self.hardware_interfaces.values():
                if channel_id in interface.channels:
                    interface.write(channel_id, value)

        # 2. 更新被控对象模型
        if self.plant_model:
            if hasattr(self.plant_model, 'step'):
                self.plant_model.step(stimuli, dt)
            elif hasattr(self.plant_model, 'update'):
                self.plant_model.update(dt)

        # 3. 读取响应
        for interface in self.hardware_interfaces.values():
            for channel_id, channel in interface.channels.items():
                if channel.hardware_type in [HardwareType.ANALOG_INPUT, HardwareType.DIGITAL_INPUT]:
                    value = interface.read(channel_id)
                    # 信号调理
                    if channel_id in self.signal_conditioners:
                        value = self.signal_conditioners[channel_id].process(value)
                    # 应用故障
                    value = self.fault_injector.apply_fault(channel_id, value)
                    outputs[channel_id] = value

        return outputs

    def _get_scheduled_value(self, schedule: List[Tuple[float, Any]], t: float) -> Any:
        """获取计划值"""
        if not schedule:
            return 0.0

        prev_value = schedule[0][1]
        for time_point, value in schedule:
            if time_point <= t:
                prev_value = value
            else:
                break
        return prev_value

    def _record_step(self, outputs: Dict[str, Any]):
        """记录数据"""
        self.data_recorder['time'].append(self.current_time)
        for channel_id, value in outputs.items():
            if channel_id in self.data_recorder:
                self.data_recorder[channel_id].append(value)

    def _verify_results(self, test_case: HILTestCase) -> Tuple[bool, str]:
        """验证测试结果"""
        all_passed = True
        messages = []

        for channel_id, expected in test_case.expected_responses.items():
            if channel_id not in self.data_recorder:
                messages.append(f"Channel {channel_id} not recorded")
                all_passed = False
                continue

            data = self.data_recorder[channel_id]
            if not data:
                messages.append(f"Channel {channel_id} has no data")
                all_passed = False
                continue

            # 取最终值
            actual = data[-1]
            tolerance = test_case.tolerances.get(channel_id, 0.05)

            if isinstance(expected, (int, float)):
                if abs(actual - expected) > abs(expected * tolerance):
                    all_passed = False
                    messages.append(f"{channel_id}: expected {expected}, got {actual}")
                else:
                    messages.append(f"{channel_id}: PASSED")

        return all_passed, "; ".join(messages)

    def _log_event(self, event_type: str, message: str):
        """记录事件"""
        self.event_log.append({
            'timestamp': datetime.now().isoformat(),
            'sim_time': self.current_time,
            'type': event_type,
            'message': message
        })

    def shutdown(self):
        """关闭环境"""
        self.running = False
        for interface in self.hardware_interfaces.values():
            interface.disconnect()
        if self.uut_interface:
            self.uut_interface.disconnect()
        self.initialized = False
        self._log_event("SHUTDOWN", "HIL environment shutdown")


class HILTestSuite:
    """HIL测试套件"""

    def __init__(self, suite_id: str, name: str):
        self.suite_id = suite_id
        self.name = name
        self.test_cases: Dict[str, HILTestCase] = {}
        self.environment: Optional[HILTestEnvironment] = None
        self.results: Dict[str, Dict] = {}

        # 统计
        self.executed = False
        self.passed_count = 0
        self.failed_count = 0
        self.error_count = 0

    def add_test_case(self, test_case: HILTestCase):
        """添加测试用例"""
        self.test_cases[test_case.test_id] = test_case

    def set_environment(self, env: HILTestEnvironment):
        """设置测试环境"""
        self.environment = env

    def run(self, test_ids: List[str] = None) -> Dict[str, Any]:
        """运行测试套件"""
        if not self.environment:
            return {'error': 'No environment set'}

        if not self.environment.initialized:
            if not self.environment.initialize():
                return {'error': 'Environment initialization failed'}

        tests_to_run = test_ids or list(self.test_cases.keys())
        self.passed_count = 0
        self.failed_count = 0
        self.error_count = 0

        for test_id in tests_to_run:
            if test_id not in self.test_cases:
                continue

            test_case = self.test_cases[test_id]
            result = self.environment.run_test(test_case)
            self.results[test_id] = result

            if result['result'] == 'PASSED':
                self.passed_count += 1
            elif result['result'] == 'FAILED':
                self.failed_count += 1
            else:
                self.error_count += 1

        self.executed = True

        return {
            'suite_id': self.suite_id,
            'total': len(tests_to_run),
            'passed': self.passed_count,
            'failed': self.failed_count,
            'error': self.error_count,
            'results': self.results
        }


# 预定义的水利系统HIL测试用例
def create_hydraulic_hil_test_cases() -> List[HILTestCase]:
    """创建水利系统HIL测试用例"""
    test_cases = []

    # 测试1: 阀门控制柜闭环测试
    test_cases.append(HILTestCase(
        test_id="HIL_VALVE_001",
        name="阀门控制柜闭环响应测试",
        description="测试实际控制柜与仿真模型的闭环性能",
        category="INTEGRATION",
        requirements=["REQ_IVCU_001"],
        required_interfaces=["VALVE_CTRL_IO"],
        input_channels=["valve_cmd", "valve_enable"],
        output_channels=["valve_position", "valve_current", "valve_limit_sw"],
        duration=120.0,
        sample_rate=100.0,
        stimuli={
            'valve_enable': [(0.0, True)],
            'valve_cmd': [(0.0, 0.0), (10.0, 0.5), (60.0, 1.0), (90.0, 0.0)]
        },
        expected_responses={
            'valve_position': 0.0  # 最终位置
        },
        tolerances={
            'valve_position': 0.05
        }
    ))

    # 测试2: 传感器故障注入测试
    test_cases.append(HILTestCase(
        test_id="HIL_VALVE_002",
        name="位置传感器故障测试",
        description="测试位置传感器故障时的系统响应",
        category="FAULT_TOLERANCE",
        requirements=["REQ_IVCU_002"],
        safety_goals=["SG_SENSOR_FAULT"],
        duration=60.0,
        sample_rate=100.0,
        input_channels=["valve_position_fb"],
        output_channels=["fault_flag", "degradation_level"],
        fault_injections=[
            FaultInjectionConfig(
                fault_id="FAULT_POS_SENSOR",
                channel_id="valve_position_fb",
                fault_mode=FaultMode.STUCK_HIGH,
                start_time=20.0,
                duration=10.0,
                parameters={'high_value': 10.0}
            )
        ],
        expected_responses={
            'fault_flag': True
        }
    ))

    # 测试3: 水泵启停测试
    test_cases.append(HILTestCase(
        test_id="HIL_PUMP_001",
        name="水泵启停时序测试",
        description="测试水泵启动和停止的完整时序",
        category="FUNCTIONAL",
        requirements=["REQ_IPCU_001"],
        duration=180.0,
        sample_rate=50.0,
        stimuli={
            'pump_start_cmd': [(0.0, False), (10.0, True), (120.0, False)],
            'pump_speed_setpoint': [(0.0, 0), (10.0, 1500)]
        },
        expected_responses={
            'pump_running': False
        }
    ))

    return test_cases
