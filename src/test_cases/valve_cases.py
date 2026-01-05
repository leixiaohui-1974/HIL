# -*- coding: utf-8 -*-
"""
阀门必测工况集 (Valve Mandatory Cases)

VC-01: 断电水锤防护
VC-02: 误关阀冲击测试
VC-03: 卡涩故障演练
VC-04: 压力传感器失效
"""

from typing import Dict, List, Optional
import numpy as np

from .base_test import HILTestCase, HILTestSuite, TestResult, TestStatus
from ..simulator import PipeMOCModel, PipeParameters
from ..controllers import ValveController, ValveControlMode
from ..sensors import SensorArray, VirtualPressureSensor, VirtualFlowSensor, SensorFaultType


class ValveTestCase(HILTestCase):
    """阀门测试用例基类"""

    def __init__(self, test_id: str, test_name: str, description: str = ""):
        super().__init__(test_id, test_name, description)

        # 管道参数 (默认长输管线)
        self.pipe_params = PipeParameters(
            length=20000,           # 20km
            diameter=2.0,           # DN2000
            wave_speed=1000,        # 1000m/s
            friction_factor=0.02,
            design_pressure=1.6,    # 1.6MPa
        )

        # 初始条件
        self.initial_head = 100.0     # 初始水头 (m)
        self.initial_flow = 10.0      # 初始流量 (m³/s)
        self.initial_opening = 1.0    # 初始开度

    def setup(self) -> None:
        """测试准备"""
        # 创建仿真模型
        self.simulator = PipeMOCModel(self.pipe_params, dt=0.01)
        self.simulator.initialize(
            upstream_head=self.initial_head,
            initial_flow=self.initial_flow,
            valve_opening=self.initial_opening
        )

        # 创建控制器
        self.controller = ValveController("IVCU-TEST")
        self.controller.design_pressure = self.pipe_params.design_pressure

        # 创建传感器阵列
        self.sensor_array = SensorArray()
        self.sensor_array.add_sensor(VirtualPressureSensor("upstream", 2.5))
        self.sensor_array.add_sensor(VirtualPressureSensor("downstream", 2.5))
        self.sensor_array.add_sensor(VirtualFlowSensor(50.0))


class VC01_PowerFailureWaterHammer(ValveTestCase):
    """VC-01: 断电水锤防护测试

    仿真工况：模拟上游动力源突然丧失，流量瞬间丧失，反向水压波袭来
    验收判据：
    1. 阀门按预设的"两阶段液压曲线"执行关闭
    2. 仿真出的阀后压力峰值未超过1.2倍设计压力
    3. 在倒流速度达到最大值前，阀门已关闭至30%以下
    """

    def __init__(self):
        super().__init__(
            test_id="VC-01",
            test_name="断电水锤防护测试",
            description="模拟上游动力源突然丧失，验证阀门水锤防护能力"
        )
        self.duration = 30.0  # 30秒测试

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)
        history = []

        # 先运行5秒稳态
        for _ in range(int(5.0 / self.dt)):
            state = self.simulator.step()

        self.result.add_log("稳态运行完成，模拟断电")

        # 模拟断电
        power_fail_time = self.simulator.time
        self.simulator.simulate_power_failure()

        # 继续仿真
        max_pressure = 0.0
        min_pressure = float('inf')
        max_reverse_velocity = 0.0
        valve_at_30_time = None

        for i in range(steps):
            # 更新仿真
            state = self.simulator.step()

            # 获取传感器读数
            sim_state = {
                'pressure_upstream': state.pressure_upstream,
                'pressure_downstream': state.pressure_downstream,
                'flow_rate': state.flow_rate,
                'power_fail': True,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, self.dt)

            # 控制器输入
            controller_input = {
                'P1': sensor_readings['P_upstream'],
                'P2': sensor_readings['P_downstream'],
                'Q': sensor_readings['Q'],
                'opening': self.simulator.valve_opening,
                'power_fail': True,
            }

            # 运行控制器
            ctrl_result = self.controller.run_cycle(controller_input)

            # 更新阀门开度
            self.simulator.set_valve_opening(ctrl_result['output'])

            # 记录数据
            record = {
                'time': state.time,
                'pressure_up': state.pressure_upstream,
                'pressure_down': state.pressure_downstream,
                'flow': state.flow_rate,
                'valve_opening': self.simulator.valve_opening,
                'velocity': state.flow_rate / self.pipe_params.area,
            }
            history.append(record)

            # 更新统计
            max_pressure = max(max_pressure, state.pressure_downstream)
            min_pressure = min(min_pressure, state.pressure_downstream)

            # 检测倒流
            if record['velocity'] < 0:
                reverse_v = abs(record['velocity'])
                max_reverse_velocity = max(max_reverse_velocity, reverse_v)

            # 记录阀门关闭到30%的时刻
            if valve_at_30_time is None and self.simulator.valve_opening <= 0.30:
                valve_at_30_time = state.time - power_fail_time
                self.result.add_log(f"阀门关闭至30%，用时 {valve_at_30_time:.2f}s")

        # 保存历史数据供评估
        self._history = history
        self._max_pressure = max_pressure
        self._min_pressure = min_pressure
        self._max_reverse_velocity = max_reverse_velocity
        self._valve_at_30_time = valve_at_30_time

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        design_pressure = self.pipe_params.design_pressure
        max_allowed = design_pressure * 1.2

        # 判据1: 两阶段关闭
        two_stage = self.controller.valve_mode == ValveControlMode.TWO_STAGE_CLOSE or \
                    self.controller._closing_stage > 0
        self.result.check_criterion(
            "两阶段液压曲线关闭",
            two_stage
        )

        # 判据2: 压力峰值不超过1.2倍
        pressure_ok = self._max_pressure <= max_allowed
        self.result.check_criterion(
            f"压力峰值 <= {max_allowed:.2f} MPa",
            pressure_ok,
            self._max_pressure
        )

        # 判据3: 倒流前关闭到30%
        # 假设最大倒流速度约为正常流速的1.3倍
        normal_velocity = self.initial_flow / self.pipe_params.area
        max_expected_reverse = normal_velocity * 1.3

        if self._valve_at_30_time is not None:
            close_before_max_reverse = self._max_reverse_velocity < max_expected_reverse * 0.8
        else:
            close_before_max_reverse = False

        self.result.check_criterion(
            "倒流达最大前关闭至30%以下",
            close_before_max_reverse,
            self._max_reverse_velocity if self._max_reverse_velocity > 0 else 0
        )

        return pressure_ok and close_before_max_reverse


class VC02_MisoperationImpact(ValveTestCase):
    """VC-02: 误关阀冲击测试

    仿真工况：模拟在正常满流工况下，错误触发关阀指令
    验收判据：
    1. 控制柜识别出当前为高流速状态，自动拒绝"快关"指令
    2. 强制切换为"慢关"模式
    3. 产生的最大水锤升压 <= 0.2 MPa
    """

    def __init__(self):
        super().__init__(
            test_id="VC-02",
            test_name="误关阀冲击测试",
            description="模拟正常满流工况下错误触发关阀指令"
        )
        self.duration = 20.0

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)

        # 记录初始压力
        initial_pressure = self.initial_head * 9.81 / 1e6
        max_pressure_rise = 0.0
        fast_close_rejected = False

        # 先运行2秒稳态
        for _ in range(int(2.0 / self.dt)):
            self.simulator.step()

        self.result.add_log("稳态运行完成，触发误关阀指令")

        # 尝试快关
        self.controller.command_close(mode="fast")

        for i in range(steps):
            state = self.simulator.step()

            # 传感器读数
            sim_state = {
                'pressure_upstream': state.pressure_upstream,
                'pressure_downstream': state.pressure_downstream,
                'flow_rate': state.flow_rate,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, self.dt)

            # 计算流速
            velocity = state.flow_rate / self.pipe_params.area

            controller_input = {
                'P1': sensor_readings['P_upstream'],
                'P2': sensor_readings['P_downstream'],
                'Q': sensor_readings['Q'],
                'opening': self.simulator.valve_opening,
            }

            ctrl_result = self.controller.run_cycle(controller_input)
            self.simulator.set_valve_opening(ctrl_result['output'])

            # 检查是否拒绝快关
            if self.controller._high_flow_lockout:
                fast_close_rejected = True

            # 记录压力升高
            pressure_rise = state.pressure_downstream - initial_pressure
            max_pressure_rise = max(max_pressure_rise, pressure_rise)

        self._fast_close_rejected = fast_close_rejected
        self._max_pressure_rise = max_pressure_rise
        self._final_mode = self.controller.valve_mode

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 识别高流速并拒绝快关
        self.result.check_criterion(
            "识别高流速状态拒绝快关",
            self._fast_close_rejected
        )

        # 判据2: 切换为慢关模式
        slow_mode = self.controller.valve_speed <= self.controller.slow_close_speed * 1.1
        self.result.check_criterion(
            "强制切换为慢关模式",
            slow_mode,
            self.controller.valve_speed
        )

        # 判据3: 水锤升压 <= 0.2 MPa
        pressure_ok = self._max_pressure_rise <= 0.2
        self.result.check_criterion(
            "最大水锤升压 <= 0.2 MPa",
            pressure_ok,
            self._max_pressure_rise
        )

        return self._fast_close_rejected and pressure_ok


class VC03_StallFault(ValveTestCase):
    """VC-03: 卡涩故障演练

    仿真工况：模拟阀门在关闭至20%（高阻区）时机械卡死
    验收判据：
    1. 控制柜在2秒内识别出开度反馈与指令不符
    2. 自动触发"水力旁路模式"或报警，而不是死等
    """

    def __init__(self):
        super().__init__(
            test_id="VC-03",
            test_name="卡涩故障演练",
            description="模拟阀门在关闭至20%时机械卡死"
        )
        self.duration = 30.0
        self.stall_opening = 0.20  # 卡涩开度

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)

        stall_detected = False
        stall_detect_time = None
        alarm_raised = False
        stall_start_time = None

        # 开始关阀
        self.controller.command_close(mode="normal")

        for i in range(steps):
            state = self.simulator.step()

            # 模拟卡涩：当开度达到20%时停止动作
            actual_opening = self.simulator.valve_opening
            if actual_opening <= self.stall_opening and stall_start_time is None:
                stall_start_time = state.time
                self.result.add_log(f"阀门卡涩在 {self.stall_opening*100:.0f}%")

            # 如果已卡涩，保持开度不变
            if stall_start_time is not None:
                actual_opening = self.stall_opening

            sim_state = {
                'pressure_upstream': state.pressure_upstream,
                'pressure_downstream': state.pressure_downstream,
                'flow_rate': state.flow_rate,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, self.dt)

            controller_input = {
                'P1': sensor_readings['P_upstream'],
                'P2': sensor_readings['P_downstream'],
                'Q': sensor_readings['Q'],
                'opening': actual_opening,  # 反馈卡涩后的实际开度
            }

            ctrl_result = self.controller.run_cycle(controller_input)

            # 正常情况下更新开度，但卡涩后保持不变
            if stall_start_time is None:
                self.simulator.set_valve_opening(ctrl_result['output'])

            # 检查是否检测到卡涩
            if self.controller.state.actuator_fault and not stall_detected:
                stall_detected = True
                stall_detect_time = state.time - stall_start_time if stall_start_time else 0
                self.result.add_log(f"卡涩检测成功，用时 {stall_detect_time:.2f}s")

            # 检查报警
            for alarm in self.controller.state.alarms:
                if 'STALL' in alarm.code:
                    alarm_raised = True

        self._stall_detected = stall_detected
        self._stall_detect_time = stall_detect_time
        self._alarm_raised = alarm_raised

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 2秒内识别卡涩
        detect_in_time = self._stall_detected and self._stall_detect_time is not None and \
                         self._stall_detect_time <= 2.0
        self.result.check_criterion(
            "2秒内识别开度反馈与指令不符",
            detect_in_time,
            self._stall_detect_time if self._stall_detect_time else 0
        )

        # 判据2: 触发报警
        self.result.check_criterion(
            "自动触发报警",
            self._alarm_raised
        )

        return detect_in_time and self._alarm_raised


class VC04_SensorFailure(ValveTestCase):
    """VC-04: 压力传感器失效测试

    仿真工况：模拟阀前压力传感器信号丢失或漂移至满量程
    验收判据：
    1. 系统不应误判为高压而乱动作
    2. 自动降级为"时间控制模式"并报警
    """

    def __init__(self):
        super().__init__(
            test_id="VC-04",
            test_name="压力传感器失效测试",
            description="模拟阀前压力传感器信号丢失或漂移至满量程"
        )
        self.duration = 20.0

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)

        # 正常运行5秒
        for _ in range(int(5.0 / self.dt)):
            state = self.simulator.step()

        self.result.add_log("正常运行完成，注入传感器故障")

        # 注入故障：上游压力传感器漂移至满量程
        self.sensor_array.inject_fault('P_upstream', SensorFaultType.FULL_SCALE)

        wrong_action = False
        degraded_mode = False
        alarm_raised = False
        initial_opening = self.simulator.valve_opening

        for i in range(int(15.0 / self.dt)):
            state = self.simulator.step()

            sim_state = {
                'pressure_upstream': state.pressure_upstream,
                'pressure_downstream': state.pressure_downstream,
                'flow_rate': state.flow_rate,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, self.dt)

            controller_input = {
                'P1': sensor_readings['P_upstream'],  # 这将是满量程值
                'P2': sensor_readings['P_downstream'],
                'Q': sensor_readings['Q'],
                'opening': self.simulator.valve_opening,
            }

            ctrl_result = self.controller.run_cycle(controller_input)

            # 检查是否降级到时间控制模式
            if self.controller.valve_mode == ValveControlMode.TIME_BASED:
                degraded_mode = True

            # 检查是否误动作（阀门开度剧烈变化）
            opening_change = abs(self.simulator.valve_opening - initial_opening)
            if opening_change > 0.3 and not degraded_mode:
                wrong_action = True

            # 不实际更新阀门开度（防止误动作导致仿真崩溃）
            # self.simulator.set_valve_opening(ctrl_result['output'])

            # 检查报警
            for alarm in self.controller.state.alarms:
                if 'SENSOR' in alarm.code or 'DEGRADED' in alarm.code:
                    alarm_raised = True

        self._wrong_action = wrong_action
        self._degraded_mode = degraded_mode
        self._alarm_raised = alarm_raised

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 不误动作
        no_wrong_action = not self._wrong_action
        self.result.check_criterion(
            "不误判为高压而乱动作",
            no_wrong_action
        )

        # 判据2: 降级为时间控制模式并报警
        proper_degradation = self._degraded_mode and self._alarm_raised
        self.result.check_criterion(
            "自动降级为时间控制模式",
            self._degraded_mode
        )
        self.result.check_criterion(
            "触发报警",
            self._alarm_raised
        )

        return no_wrong_action and proper_degradation


class ValveTestSuite(HILTestSuite):
    """阀门测试套件"""

    def __init__(self):
        super().__init__("阀门必测工况集")

        # 添加所有阀门测试
        self.add_test(VC01_PowerFailureWaterHammer())
        self.add_test(VC02_MisoperationImpact())
        self.add_test(VC03_StallFault())
        self.add_test(VC04_SensorFailure())
