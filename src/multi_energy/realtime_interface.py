# -*- coding: utf-8 -*-
"""
实时仿真接口模块
Real-Time Simulation Interface Module

提供硬件在环(HIL)实时仿真接口:
1. 实时步进控制
2. 外部数据输入接口
3. 实时状态输出
4. HIL通信协议支持
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable, Any
from enum import Enum, auto
import threading
import queue
import time
from collections import deque


class SimulationMode(Enum):
    """仿真模式"""
    OFFLINE = auto()      # 离线仿真(尽快执行)
    REALTIME = auto()     # 实时仿真(按真实时间)
    SCALED = auto()       # 缩放时间仿真
    STEP = auto()         # 单步仿真


class DataType(Enum):
    """数据类型"""
    FREQUENCY = "frequency"
    POWER = "power"
    SOC = "soc"
    LEVEL = "level"
    MODE = "mode"
    SETPOINT = "setpoint"


@dataclass
class ExternalInput:
    """外部输入数据"""
    timestamp: float
    data_type: str
    source: str
    value: float
    unit: str = ""
    quality: float = 1.0  # 数据质量 0-1


@dataclass
class OutputData:
    """输出数据"""
    timestamp: float
    data_type: str
    target: str
    value: float
    unit: str = ""


@dataclass
class RealTimeConfig:
    """实时仿真配置"""
    mode: SimulationMode = SimulationMode.REALTIME
    time_scale: float = 1.0          # 时间缩放因子
    step_size: float = 0.1           # 步长(s)
    input_buffer_size: int = 100     # 输入缓冲区大小
    output_buffer_size: int = 100    # 输出缓冲区大小
    sync_interval: float = 1.0       # 同步间隔(s)
    enable_logging: bool = True


class RealTimeSimulator:
    """
    实时仿真器

    支持HIL硬件在环仿真的实时接口
    """

    def __init__(self, config: Optional[RealTimeConfig] = None):
        self.config = config or RealTimeConfig()

        # 状态
        self._running = False
        self._paused = False
        self._current_time = 0.0
        self._wall_time_start = 0.0

        # 缓冲区
        self._input_queue = queue.Queue(maxsize=self.config.input_buffer_size)
        self._output_queue = queue.Queue(maxsize=self.config.output_buffer_size)
        self._pending_inputs: Dict[str, ExternalInput] = {}

        # 回调函数
        self._step_callbacks: List[Callable] = []
        self._output_callbacks: List[Callable] = []

        # 线程
        self._sim_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 历史数据
        self._history = deque(maxlen=1000)

        # 组件状态
        self._component_states: Dict[str, Dict[str, float]] = {}

        # 初始化仿真器
        self._simulator = None

    def initialize(
        self,
        simulation_config: 'SimulationConfig',
        warm_up: bool = True
    ) -> None:
        """
        初始化仿真器

        Args:
            simulation_config: 仿真配置
            warm_up: 是否预热
        """
        from .simulation import MultiEnergySimulator

        self._simulator = MultiEnergySimulator(simulation_config)

        if warm_up:
            self._simulator._warmup()

        self._current_time = 0.0
        self._component_states.clear()

        print(f"实时仿真器初始化完成")
        print(f"  模式: {self.config.mode.name}")
        print(f"  步长: {self.config.step_size}s")
        if self.config.mode == SimulationMode.SCALED:
            print(f"  时间缩放: {self.config.time_scale}x")

    def register_step_callback(self, callback: Callable) -> None:
        """注册步进回调函数"""
        self._step_callbacks.append(callback)

    def register_output_callback(self, callback: Callable) -> None:
        """注册输出回调函数"""
        self._output_callbacks.append(callback)

    def push_input(self, data: ExternalInput) -> bool:
        """
        推送外部输入数据

        Args:
            data: 外部输入数据

        Returns:
            是否成功
        """
        try:
            self._input_queue.put_nowait(data)
            return True
        except queue.Full:
            return False

    def pull_output(self, timeout: float = 0.0) -> Optional[OutputData]:
        """
        拉取输出数据

        Args:
            timeout: 超时时间

        Returns:
            输出数据或None
        """
        try:
            return self._output_queue.get(timeout=timeout if timeout > 0 else None)
        except queue.Empty:
            return None

    def step(self, dt: Optional[float] = None) -> Dict[str, Any]:
        """
        执行单步仿真

        Args:
            dt: 时间步长(可选)

        Returns:
            当前状态字典
        """
        if self._simulator is None:
            raise RuntimeError("仿真器未初始化")

        dt = dt or self.config.step_size

        # 处理外部输入
        self._process_inputs()

        # 执行仿真步进
        state = self._execute_step(dt)

        # 更新时间
        self._current_time += dt

        # 生成输出
        self._generate_outputs(state)

        # 触发回调
        for callback in self._step_callbacks:
            try:
                callback(self._current_time, state)
            except Exception as e:
                print(f"步进回调异常: {e}")

        # 记录历史
        self._history.append({
            'time': self._current_time,
            'state': state.copy()
        })

        return state

    def _process_inputs(self) -> None:
        """处理外部输入"""
        while not self._input_queue.empty():
            try:
                data = self._input_queue.get_nowait()
                key = f"{data.source}_{data.data_type}"
                self._pending_inputs[key] = data
            except queue.Empty:
                break

        # 应用输入到仿真器
        for key, data in self._pending_inputs.items():
            self._apply_input(data)

        self._pending_inputs.clear()

    def _apply_input(self, data: ExternalInput) -> None:
        """应用外部输入到仿真器"""
        if self._simulator is None:
            return

        # 根据数据类型和源应用输入
        # 这里可以扩展支持更多输入类型
        if data.data_type == "wind_power_setpoint":
            pass  # 可以设置风电设定值
        elif data.data_type == "load_actual":
            pass  # 可以更新实际负荷

    def _execute_step(self, dt: float) -> Dict[str, Any]:
        """执行仿真步进并返回状态"""
        if self._simulator is None:
            return {}

        # 获取当前小时
        hour = (self._current_time / 3600) % 24

        # 获取当前条件
        cfg = self._simulator.config

        # 简化的步进逻辑
        state = {
            'time': self._current_time,
            'frequency': self._simulator.grid.get_frequency(),
            'wind_power': self._simulator.wind_turbine.get_power(),
            'solar_power': self._simulator.photovoltaic.get_power(),
            'hydro_power': self._simulator.hydro.get_power(),
            'psh_power': self._simulator.psh.get_power(),
            'sc_power': self._simulator.supercapacitor.get_power(),
            'bess_power': self._simulator.battery.get_power(),
            'sc_soc': self._simulator.supercapacitor.get_soc(),
            'bess_soc': self._simulator.battery.get_soc(),
            'psh_level': self._simulator.psh.get_reservoir_level(),
            'psh_mode': self._simulator.psh.get_mode()
        }

        return state

    def _generate_outputs(self, state: Dict[str, Any]) -> None:
        """生成输出数据"""
        # 频率输出
        try:
            self._output_queue.put_nowait(OutputData(
                timestamp=self._current_time,
                data_type="frequency",
                target="grid",
                value=state.get('frequency', 50.0),
                unit="Hz"
            ))
        except queue.Full:
            pass

        # 触发输出回调
        for callback in self._output_callbacks:
            try:
                callback(self._current_time, state)
            except Exception as e:
                print(f"输出回调异常: {e}")

    def start(self) -> None:
        """启动实时仿真"""
        if self._running:
            return

        self._running = True
        self._paused = False
        self._wall_time_start = time.time()

        if self.config.mode in [SimulationMode.REALTIME, SimulationMode.SCALED]:
            self._sim_thread = threading.Thread(target=self._run_loop)
            self._sim_thread.daemon = True
            self._sim_thread.start()
            print("实时仿真已启动")

    def stop(self) -> None:
        """停止仿真"""
        self._running = False
        if self._sim_thread:
            self._sim_thread.join(timeout=2.0)
        print("仿真已停止")

    def pause(self) -> None:
        """暂停仿真"""
        self._paused = True
        print("仿真已暂停")

    def resume(self) -> None:
        """恢复仿真"""
        self._paused = False
        print("仿真已恢复")

    def _run_loop(self) -> None:
        """仿真循环"""
        next_step_time = time.time()

        while self._running:
            if self._paused:
                time.sleep(0.01)
                continue

            current_wall_time = time.time()

            # 计算下一步时间
            if self.config.mode == SimulationMode.REALTIME:
                step_interval = self.config.step_size
            else:  # SCALED
                step_interval = self.config.step_size / self.config.time_scale

            if current_wall_time >= next_step_time:
                # 执行步进
                with self._lock:
                    self.step()

                next_step_time = current_wall_time + step_interval
            else:
                # 等待
                sleep_time = min(next_step_time - current_wall_time, 0.001)
                time.sleep(sleep_time)

    def get_current_time(self) -> float:
        """获取当前仿真时间"""
        return self._current_time

    def get_current_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        with self._lock:
            if self._history:
                return self._history[-1]['state'].copy()
            return {}

    def get_history(self, n: int = 100) -> List[Dict]:
        """获取历史数据"""
        with self._lock:
            return list(self._history)[-n:]


class HILInterface:
    """
    HIL硬件在环接口

    提供与外部硬件通信的接口
    """

    def __init__(self, realtime_sim: RealTimeSimulator):
        self.simulator = realtime_sim
        self._connected = False
        self._protocol = "internal"

        # 通信参数
        self._input_mappings: Dict[str, str] = {}
        self._output_mappings: Dict[str, str] = {}

    def connect(self, protocol: str = "internal", **kwargs) -> bool:
        """
        连接硬件接口

        Args:
            protocol: 通信协议 ("internal", "modbus", "opc-ua")
            **kwargs: 协议特定参数

        Returns:
            是否连接成功
        """
        self._protocol = protocol

        if protocol == "internal":
            # 内部模拟模式
            self._connected = True
            print("HIL接口已连接(内部模式)")
            return True

        elif protocol == "modbus":
            # Modbus协议(示例)
            host = kwargs.get('host', 'localhost')
            port = kwargs.get('port', 502)
            print(f"Modbus连接: {host}:{port}")
            # 实际实现需要pymodbus库
            self._connected = True
            return True

        elif protocol == "opc-ua":
            # OPC-UA协议(示例)
            endpoint = kwargs.get('endpoint', 'opc.tcp://localhost:4840')
            print(f"OPC-UA连接: {endpoint}")
            # 实际实现需要opcua库
            self._connected = True
            return True

        return False

    def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        print("HIL接口已断开")

    def map_input(self, external_tag: str, internal_var: str) -> None:
        """
        映射外部输入到内部变量

        Args:
            external_tag: 外部标签名
            internal_var: 内部变量名
        """
        self._input_mappings[external_tag] = internal_var

    def map_output(self, internal_var: str, external_tag: str) -> None:
        """
        映射内部变量到外部输出

        Args:
            internal_var: 内部变量名
            external_tag: 外部标签名
        """
        self._output_mappings[internal_var] = external_tag

    def read_inputs(self) -> Dict[str, float]:
        """读取所有映射的输入"""
        if not self._connected:
            return {}

        # 内部模式返回模拟值
        if self._protocol == "internal":
            return {tag: 0.0 for tag in self._input_mappings}

        return {}

    def write_outputs(self, values: Dict[str, float]) -> bool:
        """
        写入输出值

        Args:
            values: {内部变量名: 值}

        Returns:
            是否成功
        """
        if not self._connected:
            return False

        # 内部模式只记录
        if self._protocol == "internal":
            return True

        return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected


# 便捷函数
def create_realtime_simulator(
    simulation_config: 'SimulationConfig',
    mode: SimulationMode = SimulationMode.REALTIME,
    time_scale: float = 1.0
) -> RealTimeSimulator:
    """
    创建实时仿真器

    Args:
        simulation_config: 仿真配置
        mode: 仿真模式
        time_scale: 时间缩放因子

    Returns:
        实时仿真器实例
    """
    rt_config = RealTimeConfig(
        mode=mode,
        time_scale=time_scale
    )

    simulator = RealTimeSimulator(rt_config)
    simulator.initialize(simulation_config)

    return simulator
