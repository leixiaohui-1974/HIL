# -*- coding: utf-8 -*-
"""
水泵必测工况集 (Pump Mandatory Cases)

PC-01: 软启动平稳性
PC-02: 事故跳闸飞逸
PC-03: 泵阀联动失效
PC-04: 气蚀/低效区运行
"""

from typing import Dict, List
import numpy as np

from .base_test import HILTestCase, HILTestSuite, TestResult, TestStatus
from ..simulator import PumpCharacteristics, PumpParameters, PumpOperatingZone
from ..controllers import PumpController, PumpControlMode
from ..sensors import SensorArray, VirtualPressureSensor, VirtualFlowSensor, VirtualSpeedSensor


class PumpTestCase(HILTestCase):
    """水泵测试用例基类"""

    def __init__(self, test_id: str, test_name: str, description: str = ""):
        super().__init__(test_id, test_name, description)

        # 水泵参数
        self.pump_params = PumpParameters(
            rated_flow=10.0,           # 10 m³/s
            rated_head=100.0,          # 100 m
            rated_speed=1450.0,        # 1450 rpm
            rated_power=12000.0,       # 12 MW
            rated_efficiency=0.88,
            runaway_speed_ratio=1.8,
            max_reverse_speed_ratio=1.2,
        )

    def setup(self) -> None:
        """测试准备"""
        # 创建水泵特性曲线
        self.pump = PumpCharacteristics(self.pump_params)

        # 创建控制器
        self.controller = PumpController("IPCU-TEST")
        self.controller.rated_speed = self.pump_params.rated_speed
        self.controller.rated_flow = self.pump_params.rated_flow
        self.controller.max_reverse_ratio = self.pump_params.max_reverse_speed_ratio

        # 创建传感器阵列
        self.sensor_array = SensorArray()
        self.sensor_array.add_sensor(VirtualPressureSensor("suction", 0.5))
        self.sensor_array.add_sensor(VirtualPressureSensor("discharge", 2.5))
        self.sensor_array.add_sensor(VirtualFlowSensor(20.0))
        self.sensor_array.add_sensor(VirtualSpeedSensor(self.pump_params.rated_speed))


class PC01_SoftStartStability(PumpTestCase):
    """PC-01: 软启动平稳性测试

    仿真工况：模拟水泵按预设曲线启动，加载管路阻力模型
    验收判据：
    1. 启动过程中无压力超调或震荡
    2. 水泵运行点未穿越喘振区（马鞍区）
    3. 启动电流仿真值符合设计要求
    """

    def __init__(self):
        super().__init__(
            test_id="PC-01",
            test_name="软启动平稳性测试",
            description="模拟水泵按S形曲线启动"
        )
        self.duration = 90.0  # 90秒（含60秒启动时间）

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)

        # 启动水泵
        self.controller.command_start(self.pump_params.rated_speed)
        self.result.add_log("开始软启动")

        history = []
        passed_saddle = False
        pressure_oscillation = False
        prev_pressure = 0.0
        oscillation_count = 0

        for i in range(steps):
            t = i * self.dt

            # 模拟水泵运行
            speed_ratio = self.controller.current_speed / self.pump_params.rated_speed
            flow = self.pump_params.rated_flow * speed_ratio  # 简化：流量正比于转速

            # 计算运行点
            point = self.pump.get_operating_point(flow, speed_ratio)

            # 准备传感器数据
            sim_state = {
                'pump_speed': self.controller.current_speed,
                'pressure_upstream': 0.1,  # 吸入压力
                'pressure_downstream': point['head'] * 9.81 / 1e6,  # 排出压力
                'flow_rate': flow,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, self.dt)

            # 控制器输入
            controller_input = {
                'speed': self.controller.current_speed,  # 使用控制器输出作为反馈
                'flow': flow,
                'P_suction': 0.1,
                'P_discharge': point['head'] * 9.81 / 1e6,
                'vibration': 2.0,  # 正常振动
                'temperature': 40.0,  # 正常温度
            }

            # 运行控制器
            ctrl_result = self.controller.run_cycle(controller_input)

            # 更新转速
            self.controller.current_speed = ctrl_result['output']

            # 记录
            record = {
                'time': t,
                'speed': self.controller.current_speed,
                'speed_ratio': self.controller.current_speed / self.pump_params.rated_speed,
                'flow': flow,
                'head': point['head'],
                'efficiency': point['efficiency'],
                'zone': point['operating_zone'].value,
            }
            history.append(record)

            # 检查马鞍区
            if point['operating_zone'] == PumpOperatingZone.SADDLE:
                passed_saddle = True
                self.result.add_log(f"警告: t={t:.1f}s 运行点进入马鞍区")

            # 检查压力震荡
            current_pressure = point['head'] * 9.81 / 1e6
            if abs(current_pressure - prev_pressure) > 0.1:  # 压力变化超过0.1MPa
                oscillation_count += 1
            prev_pressure = current_pressure

        # 评估震荡
        if oscillation_count > 20:  # 允许一定的正常波动
            pressure_oscillation = True

        self._history = history
        self._passed_saddle = passed_saddle
        self._pressure_oscillation = pressure_oscillation
        self._final_speed_ratio = self.controller.current_speed / self.pump_params.rated_speed

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 无压力超调或震荡
        no_oscillation = not self._pressure_oscillation
        self.result.check_criterion(
            "启动过程中无压力超调或震荡",
            no_oscillation
        )

        # 判据2: 未穿越马鞍区
        no_saddle = not self._passed_saddle
        self.result.check_criterion(
            "水泵运行点未穿越马鞍区",
            no_saddle
        )

        # 判据3: 启动完成（达到目标转速）
        startup_complete = self._final_speed_ratio >= 0.95
        self.result.check_criterion(
            "达到目标转速",
            startup_complete,
            self._final_speed_ratio
        )

        return no_oscillation and no_saddle and startup_complete


class PC02_TripRunaway(PumpTestCase):
    """PC-02: 事故跳闸飞逸测试

    仿真工况：模拟水泵满载运行时突然断电，失去动力矩
    验收判据：
    1. 控制系统能准确监测到转速下降
    2. 配合阀门动作后，仿真出的最大反转转速 < 1.2倍额定转速
    """

    def __init__(self):
        super().__init__(
            test_id="PC-02",
            test_name="事故跳闸飞逸测试",
            description="模拟水泵满载运行时突然断电"
        )
        self.duration = 180.0  # 3分钟

    def run(self) -> TestResult:
        """执行测试"""
        # 初始化满载运行
        self.controller.current_speed = self.pump_params.rated_speed
        self.controller.state.is_running = True
        initial_flow = self.pump_params.rated_flow

        self.result.add_log("水泵满载运行中")

        # 先运行5秒稳态
        for _ in range(int(5.0 / self.dt)):
            pass

        self.result.add_log("模拟断电跳闸")

        # 模拟跳闸飞逸过程
        def valve_closing_curve(t):
            # 两阶段关阀曲线
            if t < 10:
                return max(0.3, 1.0 - t * 0.07)  # 快关到30%
            else:
                return max(0.0, 0.3 - (t - 10) * 0.015)  # 慢关到0

        trip_history = self.pump.simulate_trip(
            initial_speed_ratio=1.0,
            initial_flow=initial_flow,
            duration=self.duration,
            dt=self.dt,
            valve_closing_curve=valve_closing_curve
        )

        # 分析结果
        speed_drop_detected = False
        max_reverse_speed = 0.0
        reverse_time = 0.0

        for point in trip_history:
            # 检测转速下降
            if point['speed_ratio'] < 0.9 and not speed_drop_detected:
                speed_drop_detected = True
                self.result.add_log(f"检测到转速下降: {point['speed_ratio']*100:.1f}%")

            # 记录最大反转速
            if point['is_reversing']:
                reverse_speed = abs(point['speed_ratio'])
                if reverse_speed > max_reverse_speed:
                    max_reverse_speed = reverse_speed

                reverse_time = point['time']

        self._speed_drop_detected = speed_drop_detected
        self._max_reverse_ratio = max_reverse_speed
        self._reverse_time = reverse_time

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 准确监测转速下降
        self.result.check_criterion(
            "准确监测到转速下降",
            self._speed_drop_detected
        )

        # 判据2: 最大反转速 < 1.2倍额定
        reverse_ok = self._max_reverse_ratio < self.pump_params.max_reverse_speed_ratio
        self.result.check_criterion(
            f"最大反转速比 < {self.pump_params.max_reverse_speed_ratio}",
            reverse_ok,
            self._max_reverse_ratio
        )

        # 判据3: 反转时间 < 120s
        time_ok = self._reverse_time < 120
        self.result.check_criterion(
            "反转持续时间 < 120s",
            time_ok,
            self._reverse_time
        )

        return self._speed_drop_detected and reverse_ok and time_ok


class PC03_ValveInterlock(PumpTestCase):
    """PC-03: 泵阀联动失效测试

    仿真工况：模拟启泵后，出口阀门拒动（卡在全关位）
    验收判据：
    1. 控制柜在检测到出口压力异常升高后触发保护
    2. 或达到"闷泵"时间极限（30秒）后自动触发紧急停泵保护
    """

    def __init__(self):
        super().__init__(
            test_id="PC-03",
            test_name="泵阀联动失效测试",
            description="模拟启泵后出口阀门拒动"
        )
        self.duration = 60.0

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)

        # 启动水泵
        self.controller.command_start(self.pump_params.rated_speed)
        self.result.add_log("启动水泵（出口阀门卡死在全关位）")

        # 模拟阀门卡死，流量为0
        valve_stuck = True

        deadhead_detected = False
        emergency_stop_triggered = False
        deadhead_pressure = 0.0

        for i in range(steps):
            t = i * self.dt

            # 计算转速
            speed_ratio = self.controller.current_speed / self.pump_params.rated_speed

            if valve_stuck:
                # 闷泵：流量为0，压力升高到关死点扬程
                flow = 0.0
                # 关死点扬程（假设为额定扬程的1.2倍）
                deadhead_head = self.pump_params.rated_head * 1.2 * (speed_ratio ** 2)
                discharge_pressure = deadhead_head * 9.81 / 1e6
            else:
                flow = self.pump_params.rated_flow * speed_ratio
                discharge_pressure = self.pump_params.rated_head * speed_ratio * 9.81 / 1e6

            deadhead_pressure = max(deadhead_pressure, discharge_pressure)

            # 控制器输入
            controller_input = {
                'speed': self.controller.current_speed,
                'flow': flow,
                'P_suction': 0.1,
                'P_discharge': discharge_pressure,
                'vibration': 3.0 + speed_ratio * 2,  # 闷泵时振动增加
                'temperature': 40 + t * 0.5,  # 温度上升
            }

            ctrl_result = self.controller.run_cycle(controller_input)
            self.controller.current_speed = ctrl_result['output']

            # 检查保护触发
            if ctrl_result['protection_triggered']:
                if self.controller.pump_mode == PumpControlMode.EMERGENCY_STOP:
                    emergency_stop_triggered = True
                    self.result.add_log(f"紧急停泵保护触发 @ t={t:.1f}s")
                    break

            # 检查闷泵检测
            if self.controller._deadhead_timer > 0:
                deadhead_detected = True

        self._deadhead_detected = deadhead_detected
        self._emergency_stop = emergency_stop_triggered
        self._max_pressure = deadhead_pressure
        self._trigger_time = t if emergency_stop_triggered else self.duration

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 检测到闷泵或压力异常
        detection_ok = self._deadhead_detected or self._max_pressure > 1.5
        self.result.check_criterion(
            "检测到出口压力异常或闷泵",
            detection_ok,
            self._max_pressure
        )

        # 判据2: 触发紧急停泵保护
        self.result.check_criterion(
            "自动触发紧急停泵保护",
            self._emergency_stop
        )

        # 判据3: 在时间限制内响应
        time_ok = self._trigger_time <= 35  # 30秒限制 + 5秒余量
        self.result.check_criterion(
            "闷泵时间限制内响应 (<=35s)",
            time_ok,
            self._trigger_time
        )

        return detection_ok and self._emergency_stop


class PC04_CavitationZone(PumpTestCase):
    """PC-04: 气蚀/低效区运行测试

    仿真工况：模拟进水水位降低或流量调节不当，使工况点进入气蚀区
    验收判据：
    1. 系统能根据H-Q曲线识别出气蚀风险
    2. 自动发出调节指令（如降低转速或关小阀门）将工况点拉回安全区
    """

    def __init__(self):
        super().__init__(
            test_id="PC-04",
            test_name="气蚀/低效区运行测试",
            description="模拟工况点进入气蚀区"
        )
        self.duration = 60.0

    def run(self) -> TestResult:
        """执行测试"""
        steps = int(self.duration / self.dt)

        # 初始正常运行
        self.controller.current_speed = self.pump_params.rated_speed
        self.controller.speed_setpoint = self.pump_params.rated_speed
        self.controller.state.is_running = True

        cavitation_detected = False
        auto_adjustment = False
        zone_history = []

        self.result.add_log("水泵正常运行中")

        for i in range(steps):
            t = i * self.dt
            speed_ratio = self.controller.current_speed / self.pump_params.rated_speed

            # 模拟流量逐渐增大（阀门开大或下游需求增加）
            # 导致运行点向右移动，进入气蚀区
            flow_ratio = 1.0 + t / self.duration * 0.5  # 从100%增加到150%
            flow = self.pump_params.rated_flow * flow_ratio * speed_ratio

            # 获取运行点
            point = self.pump.get_operating_point(flow, speed_ratio)
            zone = point['operating_zone']
            zone_history.append(zone)

            # 控制器输入
            controller_input = {
                'speed': self.controller.current_speed,
                'flow': flow,
                'P_suction': 0.08,  # 模拟吸入压力降低
                'P_discharge': point['head'] * 9.81 / 1e6,
                'vibration': 3.0 if zone != PumpOperatingZone.CAVITATION else 8.0,
                'temperature': 45.0,
            }

            ctrl_result = self.controller.run_cycle(controller_input)

            # 检测气蚀区
            if zone == PumpOperatingZone.CAVITATION and not cavitation_detected:
                cavitation_detected = True
                self.result.add_log(f"检测到气蚀风险 @ t={t:.1f}s")

            # 检查是否自动调节
            if cavitation_detected:
                original_setpoint = self.pump_params.rated_speed
                if self.controller.speed_setpoint < original_setpoint * 0.95:
                    auto_adjustment = True
                    self.result.add_log(f"自动降速至 {self.controller.speed_setpoint:.0f} rpm")

            # 更新转速
            self.controller.current_speed = ctrl_result['output']

        # 检查最终是否回到安全区
        final_zone = zone_history[-1] if zone_history else PumpOperatingZone.NORMAL
        returned_to_safe = final_zone not in [PumpOperatingZone.CAVITATION, PumpOperatingZone.SADDLE]

        self._cavitation_detected = cavitation_detected
        self._auto_adjustment = auto_adjustment
        self._returned_to_safe = returned_to_safe

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 识别气蚀风险
        self.result.check_criterion(
            "根据H-Q曲线识别气蚀风险",
            self._cavitation_detected
        )

        # 判据2: 自动调节
        self.result.check_criterion(
            "自动发出调节指令（降低转速）",
            self._auto_adjustment
        )

        # 判据3: 工况点拉回安全区
        self.result.check_criterion(
            "工况点拉回安全区",
            self._returned_to_safe
        )

        return self._cavitation_detected and self._auto_adjustment


class PumpTestSuite(HILTestSuite):
    """水泵测试套件"""

    def __init__(self):
        super().__init__("水泵必测工况集")

        self.add_test(PC01_SoftStartStability())
        self.add_test(PC02_TripRunaway())
        self.add_test(PC03_ValveInterlock())
        self.add_test(PC04_CavitationZone())
