# -*- coding: utf-8 -*-
"""
多类型阀门测试工况集
Multi-Type Valve Test Cases

针对不同类型阀门的专项测试：
1. 调流调压阀测试 (FPV-01~03)
2. 水锤消除阀测试 (WHV-01~02)
3. 事故阀测试 (ESV-01~03)
"""

from typing import Dict, List
import numpy as np

from .base_test import HILTestCase, HILTestSuite, TestResult, TestStatus
from ..simulator import PipeMOCModel, PipeParameters
from ..controllers import (
    FlowPressureRegulatingValve,
    WaterHammerReliefValve,
    EmergencyShutoffValve,
    ValveType
)
from ..sensors import SensorArray, VirtualPressureSensor, VirtualFlowSensor


# ============================================================================
# 调流调压阀测试
# ============================================================================

class FPV01_FlowRegulationAccuracy(HILTestCase):
    """FPV-01: 调流精度测试

    验证调流调压阀的流量控制精度：
    1. 阶跃响应 - 流量设定值突变时的响应特性
    2. 稳态精度 - 流量控制偏差 <= 2%
    3. 抗扰动能力 - 上游压力波动时的流量保持能力
    """

    def __init__(self):
        super().__init__(
            test_id="FPV-01",
            test_name="调流精度测试",
            description="验证调流调压阀的流量控制精度"
        )
        self.duration = 60.0
        self.dt = 0.01

    def setup(self) -> None:
        """测试准备"""
        self.pipe_params = PipeParameters(
            length=5000,
            diameter=1.5,
            wave_speed=1000,
            design_pressure=1.6
        )

        self.simulator = PipeMOCModel(self.pipe_params, dt=self.dt)
        self.simulator.initialize(upstream_head=80, initial_flow=8.0, valve_opening=0.5)

        self.controller = FlowPressureRegulatingValve("FPV-TEST")
        self.controller.set_flow_setpoint(10.0)  # 目标流量 10 m³/s

        self.sensor_array = SensorArray()
        self.sensor_array.add_sensor(VirtualPressureSensor("upstream", 2.0))
        self.sensor_array.add_sensor(VirtualPressureSensor("downstream", 2.0))
        self.sensor_array.add_sensor(VirtualFlowSensor(20.0))

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)
        flow_history = []
        setpoint_history = []

        # 阶段1: 初始稳定
        flow_setpoint = 10.0
        self.controller.set_flow_setpoint(flow_setpoint)

        for i in range(steps):
            t = i * self.dt

            # 阶段2: t=20s时流量设定值阶跃变化
            if t >= 20.0 and t < 20.1:
                flow_setpoint = 6.0
                self.controller.set_flow_setpoint(flow_setpoint)
                self.result.add_log(f"t={t:.1f}s: 流量设定值变更为 {flow_setpoint} m³/s")

            # 阶段3: t=40s时模拟上游压力扰动
            if 40.0 <= t < 45.0:
                self.simulator.upstream_head = 80 + 20 * np.sin(2 * np.pi * (t - 40) / 5)
            else:
                self.simulator.upstream_head = 80

            # 仿真步进
            state = self.simulator.step()

            # 传感器读数
            sim_state = {
                'pressure_upstream': state.pressure_upstream,
                'pressure_downstream': state.pressure_downstream,
                'flow_rate': state.flow_rate,
            }
            readings = self.sensor_array.update_all(sim_state, self.dt)

            # 控制器
            ctrl_input = {
                'P1': readings.get('P_upstream', 0),
                'P2': readings.get('P_downstream', 0),
                'Q': readings.get('Q', 0),
                'opening': self.simulator.valve_opening,
            }
            result = self.controller.run_cycle(ctrl_input)
            self.simulator.set_valve_opening(result['output'])

            flow_history.append(state.flow_rate)
            setpoint_history.append(flow_setpoint)

        # 分析结果
        # 稳态精度 (最后10秒)
        steady_flows = flow_history[-int(10/self.dt):]
        steady_setpoint = setpoint_history[-1]
        mean_flow = np.mean(steady_flows)
        flow_error = abs(mean_flow - steady_setpoint) / steady_setpoint

        # 阶跃响应时间 (流量达到新设定值95%的时间)
        step_start = int(20.0 / self.dt)
        step_target = 6.0
        response_time = None
        for i, flow in enumerate(flow_history[step_start:]):
            if abs(flow - step_target) / step_target < 0.05:
                response_time = i * self.dt
                break

        self._flow_error = flow_error
        self._response_time = response_time
        self._flow_history = flow_history

        return self.result

    def evaluate(self) -> bool:
        """评估结果"""
        # 判据1: 稳态精度 <= 2%
        accuracy_ok = self._flow_error <= 0.02
        self.result.check_criterion(
            "稳态流量精度 <= 2%",
            accuracy_ok,
            self._flow_error * 100
        )

        # 判据2: 阶跃响应时间 <= 30s
        response_ok = self._response_time is not None and self._response_time <= 30
        self.result.check_criterion(
            "阶跃响应时间 <= 30s",
            response_ok,
            self._response_time if self._response_time else 999
        )

        return accuracy_ok and response_ok


class FPV02_PressureRegulation(HILTestCase):
    """FPV-02: 调压性能测试

    验证调流调压阀的压力控制能力：
    1. 下游压力稳定性
    2. 压差控制能力
    """

    def __init__(self):
        super().__init__(
            test_id="FPV-02",
            test_name="调压性能测试",
            description="验证调流调压阀的压力控制能力"
        )
        self.duration = 40.0
        self.dt = 0.01

    def setup(self) -> None:
        self.pipe_params = PipeParameters(length=5000, diameter=1.5, design_pressure=1.6)
        self.simulator = PipeMOCModel(self.pipe_params, dt=self.dt)
        self.simulator.initialize(upstream_head=100, initial_flow=8.0, valve_opening=0.5)

        self.controller = FlowPressureRegulatingValve("FPV-TEST")
        self.controller.set_pressure_setpoint(0.6)  # 目标下游压力 0.6 MPa

        self.sensor_array = SensorArray()
        self.sensor_array.add_sensor(VirtualPressureSensor("upstream", 2.0))
        self.sensor_array.add_sensor(VirtualPressureSensor("downstream", 2.0))
        self.sensor_array.add_sensor(VirtualFlowSensor(20.0))

    def run(self) -> TestResult:
        steps = int(self.duration / self.dt)
        pressure_history = []

        for i in range(steps):
            t = i * self.dt

            # 模拟上游压力波动
            if 15.0 <= t < 25.0:
                self.simulator.upstream_head = 100 + 30 * np.sin(2 * np.pi * (t - 15) / 10)
            else:
                self.simulator.upstream_head = 100

            state = self.simulator.step()

            sim_state = {
                'pressure_upstream': state.pressure_upstream,
                'pressure_downstream': state.pressure_downstream,
                'flow_rate': state.flow_rate,
            }
            readings = self.sensor_array.update_all(sim_state, self.dt)

            ctrl_input = {
                'P1': readings.get('P_upstream', 0),
                'P2': readings.get('P_downstream', 0),
                'Q': readings.get('Q', 0),
                'opening': self.simulator.valve_opening,
            }
            result = self.controller.run_cycle(ctrl_input)
            self.simulator.set_valve_opening(result['output'])

            pressure_history.append(state.pressure_downstream)

        # 分析压力波动
        setpoint = self.controller.pressure_setpoint
        max_deviation = max(abs(p - setpoint) for p in pressure_history) / setpoint

        self._max_deviation = max_deviation
        self._pressure_history = pressure_history

        return self.result

    def evaluate(self) -> bool:
        # 判据: 压力偏差 <= 10%
        deviation_ok = self._max_deviation <= 0.10
        self.result.check_criterion(
            "下游压力偏差 <= 10%",
            deviation_ok,
            self._max_deviation * 100
        )
        return deviation_ok


# ============================================================================
# 水锤消除阀测试
# ============================================================================

class WHV01_ReliefResponse(HILTestCase):
    """WHV-01: 泄压响应测试

    验证水锤消除阀的快速响应能力：
    1. 响应时间 <= 50ms
    2. 自动泄压启动
    3. 压力峰值抑制
    """

    def __init__(self):
        super().__init__(
            test_id="WHV-01",
            test_name="泄压响应测试",
            description="验证水锤消除阀的快速响应能力"
        )
        self.duration = 10.0
        self.dt = 0.001  # 1ms精度

    def setup(self) -> None:
        self.controller = WaterHammerReliefValve("WHV-TEST")
        self.controller.trigger_pressure = 1.5  # 触发压力 1.5 MPa
        self.controller.reset_pressure = 1.2

        self.sensor_array = SensorArray()
        self.sensor_array.add_sensor(VirtualPressureSensor("main", 3.0))

    def run(self) -> TestResult:
        steps = int(self.duration / self.dt)

        relief_triggered_time = None
        max_pressure = 0.0
        pressure_at_trigger = 0.0

        for i in range(steps):
            t = i * self.dt

            # 模拟压力升高（水锤波）
            if t < 2.0:
                pressure = 1.0  # 正常压力
            elif t < 2.5:
                # 快速升压 (模拟水锤波)
                pressure = 1.0 + 1.0 * (t - 2.0) / 0.5  # 0.5秒内升高1MPa
            else:
                if self.controller.is_relieving:
                    # 泄压后压力下降
                    pressure = max(1.0, pressure - 0.5 * self.dt)
                else:
                    pressure = 2.0

            max_pressure = max(max_pressure, pressure)

            # 控制器
            ctrl_input = {'P': pressure, 'opening': self.controller.valve_opening}
            result = self.controller.run_cycle(ctrl_input)

            # 记录触发时刻
            if self.controller.is_relieving and relief_triggered_time is None:
                relief_triggered_time = t
                pressure_at_trigger = pressure
                self.result.add_log(f"泄压阀触发 @ t={t*1000:.1f}ms, P={pressure:.2f}MPa")

        # 计算响应时间 (从超过触发压力到阀门动作)
        trigger_time = 2.0 + 0.5 * (1.5 - 1.0) / 1.0  # 压力达到1.5MPa的时刻
        if relief_triggered_time:
            response_time_ms = (relief_triggered_time - trigger_time) * 1000
        else:
            response_time_ms = None

        self._response_time_ms = response_time_ms
        self._max_pressure = max_pressure
        self._relief_triggered = self.controller.is_relieving or relief_triggered_time is not None

        return self.result

    def evaluate(self) -> bool:
        # 判据1: 响应时间 <= 50ms
        response_ok = self._response_time_ms is not None and self._response_time_ms <= 50
        self.result.check_criterion(
            "响应时间 <= 50ms",
            response_ok,
            self._response_time_ms if self._response_time_ms else 999
        )

        # 判据2: 泄压阀启动
        self.result.check_criterion(
            "泄压阀自动启动",
            self._relief_triggered
        )

        return response_ok and self._relief_triggered


class WHV02_AutoReset(HILTestCase):
    """WHV-02: 自动复位测试

    验证水锤消除阀的自动复位功能：
    1. 压力恢复正常后自动关闭
    2. 最小泄压持续时间保障
    """

    def __init__(self):
        super().__init__(
            test_id="WHV-02",
            test_name="自动复位测试",
            description="验证水锤消除阀的自动复位功能"
        )
        self.duration = 20.0
        self.dt = 0.01

    def setup(self) -> None:
        self.controller = WaterHammerReliefValve("WHV-TEST")
        self.controller.trigger_pressure = 1.5
        self.controller.reset_pressure = 1.2
        self.controller.relief_duration_min = 2.0

    def run(self) -> TestResult:
        steps = int(self.duration / self.dt)

        reset_occurred = False
        relief_started = False
        relief_duration = 0.0

        for i in range(steps):
            t = i * self.dt

            # 压力曲线：升压->保持->降压
            if t < 2.0:
                pressure = 1.0
            elif t < 3.0:
                pressure = 1.0 + 0.8 * (t - 2.0)  # 升压到1.8
            elif t < 6.0:
                pressure = 1.8  # 保持高压
            elif t < 8.0:
                pressure = 1.8 - 0.4 * (t - 6.0)  # 降压到1.0
            else:
                pressure = 1.0  # 正常压力

            ctrl_input = {'P': pressure}
            self.controller.run_cycle(ctrl_input)

            if self.controller.is_relieving:
                if not relief_started:
                    relief_started = True
                    self.result.add_log(f"泄压开始 @ t={t:.1f}s")
                relief_duration = self.controller._relief_timer
            elif relief_started and not reset_occurred:
                reset_occurred = True
                self.result.add_log(f"泄压阀复位 @ t={t:.1f}s, 持续时间={relief_duration:.1f}s")

        self._reset_occurred = reset_occurred
        self._relief_duration = relief_duration

        return self.result

    def evaluate(self) -> bool:
        # 判据1: 自动复位
        self.result.check_criterion(
            "泄压后自动复位",
            self._reset_occurred
        )

        # 判据2: 最小持续时间
        duration_ok = self._relief_duration >= 2.0
        self.result.check_criterion(
            "最小泄压持续时间 >= 2s",
            duration_ok,
            self._relief_duration
        )

        return self._reset_occurred and duration_ok


# ============================================================================
# 事故阀测试
# ============================================================================

class ESV01_PowerFailTrip(HILTestCase):
    """ESV-01: 断电触发测试

    验证事故阀的失电关闭功能：
    1. 断电后自动触发关闭
    2. 两阶段关闭曲线
    3. 关闭时间符合设计要求
    """

    def __init__(self):
        super().__init__(
            test_id="ESV-01",
            test_name="断电触发测试",
            description="验证事故阀的失电关闭功能"
        )
        self.duration = 40.0
        self.dt = 0.01

    def setup(self) -> None:
        self.controller = EmergencyShutoffValve("ESV-TEST")
        self.controller.trip_on_power_fail = True
        self.controller.full_close_time = 30.0
        self.controller.stage1_time = 5.0
        self.controller.stage2_time = 25.0

    def run(self) -> TestResult:
        steps = int(self.duration / self.dt)
        opening_history = []

        for i in range(steps):
            t = i * self.dt

            # t=5s时模拟断电
            power_fail = t >= 5.0

            ctrl_input = {
                'P': 0.8,
                'Q': 8.0,
                'power_fail': power_fail,
                'opening': self.controller.valve_opening,
            }
            result = self.controller.run_cycle(ctrl_input)

            # 更新开度
            self.controller.valve_opening = result['output']
            opening_history.append(result['output'])

            if power_fail and self.controller.is_tripped and self.controller._close_stage == 1:
                if i == int(5.0 / self.dt):
                    self.result.add_log(f"断电触发 @ t={t:.1f}s")

        # 分析关闭曲线
        trip_start = int(5.0 / self.dt)
        stage1_end = int(10.0 / self.dt)  # 5s + 5s

        # 第一阶段结束时的开度应该接近 stage1_opening (0.2)
        stage1_final = opening_history[stage1_end] if stage1_end < len(opening_history) else 0
        final_opening = opening_history[-1]

        self._tripped = self.controller.is_tripped
        self._stage1_final = stage1_final
        self._final_opening = final_opening
        self._opening_history = opening_history

        return self.result

    def evaluate(self) -> bool:
        # 判据1: 触发关闭
        self.result.check_criterion(
            "断电自动触发关闭",
            self._tripped
        )

        # 判据2: 两阶段关闭 (第一阶段结束在20%左右)
        stage1_ok = abs(self._stage1_final - 0.2) < 0.1
        self.result.check_criterion(
            "第一阶段关闭到20%",
            stage1_ok,
            self._stage1_final * 100
        )

        # 判据3: 最终全关
        final_ok = self._final_opening < 0.05
        self.result.check_criterion(
            "最终全关",
            final_ok,
            self._final_opening * 100
        )

        return self._tripped and stage1_ok and final_ok


class ESV02_OverpressureTrip(HILTestCase):
    """ESV-02: 过压触发测试

    验证事故阀的过压保护功能
    """

    def __init__(self):
        super().__init__(
            test_id="ESV-02",
            test_name="过压触发测试",
            description="验证事故阀的过压保护功能"
        )
        self.duration = 20.0
        self.dt = 0.01

    def setup(self) -> None:
        self.controller = EmergencyShutoffValve("ESV-TEST")
        self.controller.trip_on_high_pressure = True
        self.controller.trip_pressure_high = 1.8

    def run(self) -> TestResult:
        steps = int(self.duration / self.dt)

        for i in range(steps):
            t = i * self.dt

            # 模拟压力升高
            if t < 3.0:
                pressure = 1.0
            elif t < 5.0:
                pressure = 1.0 + 0.5 * (t - 3.0)  # 升压到2.0
            else:
                pressure = 2.0

            ctrl_input = {
                'P': pressure,
                'Q': 8.0,
                'power_fail': False,
                'opening': self.controller.valve_opening,
            }
            result = self.controller.run_cycle(ctrl_input)
            self.controller.valve_opening = result['output']

            if self.controller.is_tripped and self.controller._close_timer < 0.02:
                self.result.add_log(f"过压触发 @ t={t:.1f}s, P={pressure:.2f}MPa")

        self._tripped = self.controller.is_tripped
        self._trip_source = self.controller.trip_source

        return self.result

    def evaluate(self) -> bool:
        # 判据1: 过压触发
        self.result.check_criterion(
            "过压自动触发关闭",
            self._tripped
        )

        # 判据2: 触发源正确
        source_ok = "HIGH_PRESSURE" in self._trip_source
        self.result.check_criterion(
            "触发源为过压",
            source_ok
        )

        return self._tripped and source_ok


class ESV03_InterlockTrip(HILTestCase):
    """ESV-03: 联锁触发测试

    验证事故阀的联锁保护功能
    """

    def __init__(self):
        super().__init__(
            test_id="ESV-03",
            test_name="联锁触发测试",
            description="验证事故阀的联锁保护功能"
        )
        self.duration = 15.0
        self.dt = 0.01

    def setup(self) -> None:
        self.controller = EmergencyShutoffValve("ESV-TEST")

    def run(self) -> TestResult:
        steps = int(self.duration / self.dt)

        for i in range(steps):
            t = i * self.dt

            # t=5s时触发联锁信号
            interlock_active = t >= 5.0

            ctrl_input = {
                'P': 0.8,
                'Q': 8.0,
                'power_fail': False,
                'interlock_pump_trip': interlock_active,  # 水泵跳闸联锁
                'opening': self.controller.valve_opening,
            }
            result = self.controller.run_cycle(ctrl_input)
            self.controller.valve_opening = result['output']

            if self.controller.is_tripped and self.controller._close_timer < 0.02:
                self.result.add_log(f"联锁触发 @ t={t:.1f}s")

        self._tripped = self.controller.is_tripped
        self._trip_source = self.controller.trip_source

        return self.result

    def evaluate(self) -> bool:
        # 判据: 联锁触发
        self.result.check_criterion(
            "联锁自动触发关闭",
            self._tripped
        )

        source_ok = "INTERLOCK" in self._trip_source
        self.result.check_criterion(
            "触发源为联锁",
            source_ok
        )

        return self._tripped and source_ok


# ============================================================================
# 测试套件
# ============================================================================

class MultiValveTestSuite(HILTestSuite):
    """多类型阀门测试套件"""

    def __init__(self):
        super().__init__("多类型阀门测试套件")

        # 调流调压阀测试
        self.add_test(FPV01_FlowRegulationAccuracy())
        self.add_test(FPV02_PressureRegulation())

        # 水锤消除阀测试
        self.add_test(WHV01_ReliefResponse())
        self.add_test(WHV02_AutoReset())

        # 事故阀测试
        self.add_test(ESV01_PowerFailTrip())
        self.add_test(ESV02_OverpressureTrip())
        self.add_test(ESV03_InterlockTrip())
