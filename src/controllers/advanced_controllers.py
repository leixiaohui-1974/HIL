# -*- coding: utf-8 -*-
"""
高级控制器模块
Advanced Controllers Module

实现复杂的协调控制策略：
- 级联泵组控制器 (CascadePumpController)
- 泵阀联动控制器 (PumpValveController)
- 流量前馈控制器 (FlowFeedforwardController)
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np

from .base_controller import (
    BaseController, ControllerState, ControlMode, AlarmLevel
)
from .pump_controller import PumpController, PumpControlMode
from .multi_valve_controller import FlowPressureRegulatingValve


class CascadeStrategy(Enum):
    """级联控制策略"""
    SEQUENTIAL = "sequential"      # 顺序启停
    LOAD_BALANCE = "load_balance"  # 负荷均衡
    EFFICIENCY = "efficiency"      # 效率优先
    RUNTIME_BALANCE = "runtime"    # 运行时间均衡


class CascadePumpController(BaseController):
    """级联泵组控制器

    实现多台泵的协调控制：
    1. 级联启停控制 - 按需启停泵组
    2. 负荷均衡 - 各泵负荷均匀分配
    3. 效率优化 - 选择最优泵组合
    4. 运行时间均衡 - 轮换运行减少磨损
    """

    def __init__(self, controller_id: str = "CASCADE-001", num_pumps: int = 3):
        """初始化

        Args:
            controller_id: 控制器标识
            num_pumps: 泵数量
        """
        super().__init__(controller_id)

        self.num_pumps = num_pumps
        self.strategy = CascadeStrategy.SEQUENTIAL

        # 创建子控制器
        self.pump_controllers: List[PumpController] = []
        for i in range(num_pumps):
            ctrl = PumpController(f"{controller_id}-P{i+1}")
            self.pump_controllers.append(ctrl)

        # 泵参数
        self.rated_flow_per_pump: float = 10.0  # 单泵额定流量 m³/s
        self.rated_speed: float = 1450.0        # 额定转速 rpm
        self.min_speed_ratio: float = 0.3       # 最小转速比

        # 级联参数
        self.min_start_interval: float = 5.0    # 最小启动间隔 (s)
        self.min_stop_interval: float = 3.0     # 最小停机间隔 (s)
        self.flow_deadband: float = 0.5         # 流量死区 m³/s
        self.load_balance_tolerance: float = 0.1  # 负荷均衡容差

        # 目标值
        self.target_flow: float = 0.0           # 目标总流量

        # 状态
        self._last_start_time: float = -10.0
        self._last_stop_time: float = -10.0
        self._pump_runtimes: List[float] = [0.0] * num_pumps
        self._current_time: float = 0.0

        # 配置传感器量程
        self.add_sensor_range('total_flow', 0.0, num_pumps * 20.0)
        self.add_sensor_range('discharge_pressure', 0.0, 2.0)

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理传感器输入"""
        self.state.sensor_readings = sensor_data.copy()

        # 更新各泵状态
        for i, ctrl in enumerate(self.pump_controllers):
            pump_data = {
                'speed': sensor_data.get(f'pump_{i}_speed', ctrl.current_speed),
                'flow': sensor_data.get(f'pump_{i}_flow', 0.0),
                'P_suction': sensor_data.get('suction_pressure', 0.1),
                'P_discharge': sensor_data.get('discharge_pressure', 1.0),
                'vibration': sensor_data.get(f'pump_{i}_vibration', 2.0),
                'temperature': sensor_data.get(f'pump_{i}_temp', 40.0),
            }
            ctrl.process_inputs(pump_data)

            # 更新运行时间
            if ctrl.state.is_running:
                self._pump_runtimes[i] += 0.01  # 假设10ms周期

    def calculate_output(self) -> float:
        """计算控制输出

        Returns:
            总流量指令
        """
        dt = 0.01
        self._current_time += dt

        # 计算当前总流量
        current_total_flow = self._get_total_flow()
        flow_error = self.target_flow - current_total_flow

        # 根据策略执行控制
        if self.strategy == CascadeStrategy.SEQUENTIAL:
            self._sequential_control(flow_error)
        elif self.strategy == CascadeStrategy.LOAD_BALANCE:
            self._load_balance_control(flow_error)
        elif self.strategy == CascadeStrategy.EFFICIENCY:
            self._efficiency_control(flow_error)
        elif self.strategy == CascadeStrategy.RUNTIME_BALANCE:
            self._runtime_balance_control(flow_error)

        # 更新各泵输出
        total_output = 0.0
        for ctrl in self.pump_controllers:
            output = ctrl.calculate_output()
            ctrl.current_speed = output
            if ctrl.state.is_running:
                flow = self.rated_flow_per_pump * (output / self.rated_speed)
                total_output += flow

        return total_output

    def _sequential_control(self, flow_error: float) -> None:
        """顺序启停控制"""
        # 需要增加流量
        if flow_error > self.flow_deadband:
            if self._current_time - self._last_start_time >= self.min_start_interval:
                # 启动下一台泵
                for ctrl in self.pump_controllers:
                    if not ctrl.state.is_running:
                        ctrl.command_start(self.rated_speed)
                        self._last_start_time = self._current_time
                        break

        # 需要减少流量
        elif flow_error < -self.flow_deadband:
            if self._current_time - self._last_stop_time >= self.min_stop_interval:
                # 停止最后一台运行的泵
                for ctrl in reversed(self.pump_controllers):
                    if ctrl.state.is_running:
                        running_count = sum(1 for c in self.pump_controllers if c.state.is_running)
                        if running_count > 1:  # 保留至少一台
                            ctrl.command_stop()
                            self._last_stop_time = self._current_time
                            break

    def _load_balance_control(self, flow_error: float) -> None:
        """负荷均衡控制"""
        self._sequential_control(flow_error)  # 先处理启停

        # 均衡各泵负荷
        running_pumps = [c for c in self.pump_controllers if c.state.is_running]
        if len(running_pumps) > 1:
            target_speed = sum(c.speed_setpoint for c in running_pumps) / len(running_pumps)
            for ctrl in running_pumps:
                # 逐渐调整到目标转速
                speed_error = target_speed - ctrl.speed_setpoint
                ctrl.speed_setpoint += np.clip(speed_error * 0.1, -10, 10)

    def _efficiency_control(self, flow_error: float) -> None:
        """效率优先控制

        选择最优泵数量和转速组合
        """
        # 计算不同泵数量的效率
        best_config = self._find_optimal_config()

        target_pump_count = best_config['pump_count']
        target_speed = best_config['speed']

        # 调整泵数量
        running_count = sum(1 for c in self.pump_controllers if c.state.is_running)

        if target_pump_count > running_count:
            if self._current_time - self._last_start_time >= self.min_start_interval:
                for ctrl in self.pump_controllers:
                    if not ctrl.state.is_running:
                        ctrl.command_start(target_speed)
                        self._last_start_time = self._current_time
                        break
        elif target_pump_count < running_count:
            if self._current_time - self._last_stop_time >= self.min_stop_interval:
                for ctrl in reversed(self.pump_controllers):
                    if ctrl.state.is_running and running_count > 1:
                        ctrl.command_stop()
                        self._last_stop_time = self._current_time
                        break

        # 调整转速
        for ctrl in self.pump_controllers:
            if ctrl.state.is_running:
                ctrl.speed_setpoint = target_speed

    def _runtime_balance_control(self, flow_error: float) -> None:
        """运行时间均衡控制"""
        self._sequential_control(flow_error)

        # 检查是否需要轮换
        running_pumps = [(i, c) for i, c in enumerate(self.pump_controllers) if c.state.is_running]
        stopped_pumps = [(i, c) for i, c in enumerate(self.pump_controllers) if not c.state.is_running]

        if running_pumps and stopped_pumps:
            # 找运行时间最长的运行泵和最短的停止泵
            max_runtime_idx = max(running_pumps, key=lambda x: self._pump_runtimes[x[0]])[0]
            min_runtime_idx = min(stopped_pumps, key=lambda x: self._pump_runtimes[x[0]])[0]

            # 如果差异超过阈值，进行轮换
            runtime_diff = self._pump_runtimes[max_runtime_idx] - self._pump_runtimes[min_runtime_idx]
            if runtime_diff > 3600:  # 1小时差异
                if self._current_time - self._last_start_time >= self.min_start_interval:
                    self.pump_controllers[min_runtime_idx].command_start(self.rated_speed)
                    self._last_start_time = self._current_time

                    if self._current_time - self._last_stop_time >= self.min_stop_interval:
                        self.pump_controllers[max_runtime_idx].command_stop()
                        self._last_stop_time = self._current_time

    def _find_optimal_config(self) -> Dict:
        """找到最优泵配置"""
        if self.target_flow <= 0:
            return {'pump_count': 0, 'speed': 0, 'efficiency': 0}

        best_efficiency = 0
        best_config = {'pump_count': 1, 'speed': self.rated_speed, 'efficiency': 0}

        for n in range(1, self.num_pumps + 1):
            # 计算每台泵需要的流量
            flow_per_pump = self.target_flow / n

            if flow_per_pump > self.rated_flow_per_pump:
                continue  # 超过单泵能力

            # 计算需要的转速比
            speed_ratio = flow_per_pump / self.rated_flow_per_pump

            if speed_ratio < self.min_speed_ratio:
                continue  # 低于最小转速

            # 简化效率模型：效率在额定点附近最高
            efficiency = 0.88 * (1 - 0.5 * (1 - speed_ratio) ** 2)

            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_config = {
                    'pump_count': n,
                    'speed': speed_ratio * self.rated_speed,
                    'efficiency': efficiency
                }

        return best_config

    def _get_total_flow(self) -> float:
        """获取当前总流量"""
        total = 0.0
        for ctrl in self.pump_controllers:
            if ctrl.state.is_running:
                speed_ratio = ctrl.current_speed / self.rated_speed
                total += self.rated_flow_per_pump * speed_ratio
        return total

    def execute_protection(self) -> bool:
        """执行保护逻辑"""
        protection_triggered = False

        # 检查各泵保护
        for i, ctrl in enumerate(self.pump_controllers):
            if ctrl.execute_protection():
                self._raise_alarm(
                    f"PUMP_{i+1}_PROTECTION",
                    AlarmLevel.ALARM,
                    f"泵 {i+1} 触发保护"
                )
                protection_triggered = True

        return protection_triggered

    def set_target_flow(self, flow: float) -> None:
        """设置目标流量"""
        self.target_flow = max(0, flow)

    def set_strategy(self, strategy: CascadeStrategy) -> None:
        """设置级联策略"""
        self.strategy = strategy

    def get_pump_status(self) -> List[Dict]:
        """获取各泵状态"""
        status = []
        for i, ctrl in enumerate(self.pump_controllers):
            status.append({
                'id': ctrl.controller_id,
                'running': ctrl.state.is_running,
                'speed': ctrl.current_speed,
                'speed_ratio': ctrl.current_speed / self.rated_speed,
                'runtime': self._pump_runtimes[i],
                'mode': ctrl.pump_mode.value,
            })
        return status


class PumpValveController(BaseController):
    """泵阀联动控制器

    实现泵和阀门的协调控制：
    1. 启泵前阀门预开
    2. 停泵后阀门延时关闭
    3. 压力/流量联动控制
    4. 防水锤保护
    """

    def __init__(self, controller_id: str = "PV-001"):
        """初始化"""
        super().__init__(controller_id)

        # 子控制器
        self.pump_controller = PumpController(f"{controller_id}-PUMP")
        self.valve_controller = FlowPressureRegulatingValve(f"{controller_id}-VALVE")

        # 联动参数
        self.valve_pre_open: float = 0.3        # 启泵前阀门预开度
        self.valve_close_delay: float = 5.0      # 停泵后阀门关闭延时 (s)
        self.min_valve_opening: float = 0.1      # 最小阀门开度

        # 状态
        self._startup_phase: int = 0             # 启动阶段
        self._shutdown_phase: int = 0            # 停机阶段
        self._phase_timer: float = 0.0

        # 控制目标
        self.target_flow: float = 0.0
        self.target_pressure: float = 0.0

        # 配置传感器量程
        self.add_sensor_range('pump_speed', 0.0, 2000.0)
        self.add_sensor_range('valve_opening', 0.0, 1.0)
        self.add_sensor_range('flow', 0.0, 50.0)
        self.add_sensor_range('pressure', 0.0, 2.0)

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理传感器输入"""
        self.state.sensor_readings = sensor_data.copy()

        # 分发数据到子控制器
        pump_data = {
            'speed': sensor_data.get('pump_speed', 0.0),
            'flow': sensor_data.get('flow', 0.0),
            'P_suction': sensor_data.get('suction_pressure', 0.1),
            'P_discharge': sensor_data.get('discharge_pressure', 1.0),
            'vibration': sensor_data.get('vibration', 2.0),
            'temperature': sensor_data.get('temperature', 40.0),
        }
        self.pump_controller.process_inputs(pump_data)

        valve_data = {
            'opening': sensor_data.get('valve_opening', 0.0),
            'P_up': sensor_data.get('discharge_pressure', 1.0),
            'P_down': sensor_data.get('downstream_pressure', 0.1),
            'flow': sensor_data.get('flow', 0.0),
        }
        self.valve_controller.process_inputs(valve_data)

    def calculate_output(self) -> float:
        """计算控制输出

        Returns:
            流量输出
        """
        dt = 0.01
        self._phase_timer += dt

        # 联动状态机
        if self._startup_phase > 0:
            return self._startup_sequence(dt)
        elif self._shutdown_phase > 0:
            return self._shutdown_sequence(dt)
        else:
            return self._normal_control(dt)

    def _startup_sequence(self, dt: float) -> float:
        """启动序列"""
        if self._startup_phase == 1:
            # 阶段1: 预开阀门
            self.valve_controller.valve_opening = min(
                self.valve_controller.valve_opening + 0.1 * dt,
                self.valve_pre_open
            )
            if self.valve_controller.valve_opening >= self.valve_pre_open:
                self._startup_phase = 2
                self._phase_timer = 0.0
                self.pump_controller.command_start(self.pump_controller.rated_speed)

        elif self._startup_phase == 2:
            # 阶段2: 启动泵
            self.pump_controller.calculate_output()
            if self.pump_controller.current_speed >= self.pump_controller.rated_speed * 0.9:
                self._startup_phase = 3
                self._phase_timer = 0.0

        elif self._startup_phase == 3:
            # 阶段3: 同步开阀
            self.pump_controller.calculate_output()
            self.valve_controller.calculate_output()
            if self._phase_timer > 2.0:
                self._startup_phase = 0  # 启动完成

        # 返回当前流量
        return self._calculate_flow()

    def _shutdown_sequence(self, dt: float) -> float:
        """停机序列"""
        if self._shutdown_phase == 1:
            # 阶段1: 缓慢关阀
            target_opening = self.min_valve_opening
            self.valve_controller.valve_opening = max(
                self.valve_controller.valve_opening - 0.05 * dt,
                target_opening
            )
            if self.valve_controller.valve_opening <= target_opening:
                self._shutdown_phase = 2
                self._phase_timer = 0.0

        elif self._shutdown_phase == 2:
            # 阶段2: 延时
            if self._phase_timer >= self.valve_close_delay:
                self._shutdown_phase = 3
                self._phase_timer = 0.0
                self.pump_controller.command_stop()

        elif self._shutdown_phase == 3:
            # 阶段3: 停泵
            self.pump_controller.calculate_output()
            if self.pump_controller.current_speed <= 0.01:
                self._shutdown_phase = 4
                self._phase_timer = 0.0

        elif self._shutdown_phase == 4:
            # 阶段4: 全关阀门
            self.valve_controller.valve_opening = max(
                self.valve_controller.valve_opening - 0.02 * dt,
                0.0
            )
            if self.valve_controller.valve_opening <= 0.001:
                self._shutdown_phase = 0  # 停机完成

        return self._calculate_flow()

    def _normal_control(self, dt: float) -> float:
        """正常运行控制"""
        # 泵控制
        pump_output = self.pump_controller.calculate_output()

        # 阀门控制
        valve_output = self.valve_controller.calculate_output()

        return self._calculate_flow()

    def _calculate_flow(self) -> float:
        """计算当前流量"""
        if not self.pump_controller.state.is_running:
            return 0.0

        # 简化模型：流量 = 泵流量 * 阀门开度
        pump_flow = self.pump_controller.rated_flow * (
            self.pump_controller.current_speed / self.pump_controller.rated_speed
        )
        valve_factor = np.sqrt(self.valve_controller.valve_opening)

        return pump_flow * valve_factor

    def execute_protection(self) -> bool:
        """执行保护逻辑"""
        protection_triggered = False

        # 泵保护
        if self.pump_controller.execute_protection():
            protection_triggered = True

        # 阀门保护
        if self.valve_controller.execute_protection():
            protection_triggered = True

        # 联动保护：泵故障时关阀
        if self.pump_controller.state.is_fault:
            self._raise_alarm(
                "PUMP_FAULT_VALVE_CLOSE",
                AlarmLevel.ALARM,
                "泵故障，关闭阀门"
            )
            self.valve_controller.valve_opening = 0.0
            protection_triggered = True

        return protection_triggered

    def command_start(self) -> None:
        """启动命令"""
        if self._startup_phase == 0 and self._shutdown_phase == 0:
            self._startup_phase = 1
            self._phase_timer = 0.0

    def command_stop(self) -> None:
        """停机命令"""
        if self._startup_phase == 0 and self._shutdown_phase == 0:
            self._shutdown_phase = 1
            self._phase_timer = 0.0

    def set_target_flow(self, flow: float) -> None:
        """设置目标流量"""
        self.target_flow = flow
        self.valve_controller.set_flow_setpoint(flow)

    def set_target_pressure(self, pressure: float) -> None:
        """设置目标压力"""
        self.target_pressure = pressure
        self.valve_controller.set_pressure_setpoint(pressure)

    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'pump_running': self.pump_controller.state.is_running,
            'pump_speed': self.pump_controller.current_speed,
            'valve_opening': self.valve_controller.valve_opening,
            'flow': self._calculate_flow(),
            'startup_phase': self._startup_phase,
            'shutdown_phase': self._shutdown_phase,
        }


class FlowFeedforwardController(BaseController):
    """流量前馈控制器

    使用前馈+反馈的复合控制策略
    """

    def __init__(self, controller_id: str = "FF-001"):
        """初始化"""
        super().__init__(controller_id)

        # 前馈参数
        self.feedforward_gain: float = 1.0
        self.feedforward_lag: float = 0.5  # 前馈滞后时间

        # 反馈PID参数
        self.kp: float = 1.0
        self.ki: float = 0.1
        self.kd: float = 0.05

        # 状态
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._feedforward_buffer: List[float] = []

        # 目标
        self.setpoint: float = 0.0
        self.measured: float = 0.0
        self.disturbance: float = 0.0

    def process_inputs(self, sensor_data: Dict[str, float]) -> None:
        """处理输入"""
        self.state.sensor_readings = sensor_data.copy()
        self.measured = sensor_data.get('measured', 0.0)
        self.disturbance = sensor_data.get('disturbance', 0.0)

    def calculate_output(self) -> float:
        """计算输出"""
        dt = 0.01

        # 前馈项
        ff_output = self.feedforward_gain * self.disturbance

        # 反馈项
        error = self.setpoint - self.measured

        # PID
        p_term = self.kp * error
        self._integral += error * dt
        self._integral = np.clip(self._integral, -10, 10)
        i_term = self.ki * self._integral

        derivative = (error - self._prev_error) / dt if dt > 0 else 0
        d_term = self.kd * derivative
        self._prev_error = error

        fb_output = p_term + i_term + d_term

        # 组合输出
        total_output = ff_output + fb_output

        return total_output

    def execute_protection(self) -> bool:
        """保护逻辑"""
        return False

    def set_setpoint(self, value: float) -> None:
        """设置目标值"""
        self.setpoint = value
