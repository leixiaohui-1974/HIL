# -*- coding: utf-8 -*-
"""
闸门必测工况集 (Gate Mandatory Cases)

GC-01: 负荷弃用防漫堤
GC-02: 恒定流量伺服
GC-03: 传感器漂移容错
"""

from typing import Dict, List
import numpy as np

from .base_test import HILTestCase, HILTestSuite, TestResult, TestStatus
from ..simulator import ChannelSaintVenantModel, ChannelParameters
from ..controllers import GateController, GateControlMode
from ..sensors import SensorArray, VirtualLevelSensor, VirtualFlowSensor, SensorFaultType


class GateTestCase(HILTestCase):
    """闸门测试用例基类"""

    def __init__(self, test_id: str, test_name: str, description: str = ""):
        super().__init__(test_id, test_name, description)

        # 渠道参数
        self.channel_params = ChannelParameters(
            length=5000,            # 5km
            bottom_width=20.0,      # 20m底宽
            side_slope=1.5,
            bed_slope=0.0001,
            manning_n=0.015,
            design_depth=5.0,       # 5m设计水深
            freeboard=0.5,          # 0.5m安全超高
        )

        # 初始条件
        self.initial_level = 3.0      # 初始水位 (m)
        self.initial_flow = 50.0      # 初始流量 (m³/s)
        self.initial_opening = 1.0    # 初始开度 (m)

    def setup(self) -> None:
        """测试准备"""
        # 创建仿真模型
        self.simulator = ChannelSaintVenantModel(self.channel_params, dt=0.5)
        self.simulator.initialize(
            upstream_level=self.initial_level,
            initial_flow=self.initial_flow,
            gate_opening=self.initial_opening
        )

        # 创建控制器
        self.controller = GateController("IGCU-TEST")
        self.controller.max_opening = 5.0
        self.controller.gate_width = 10.0
        self.controller.initial_level = self.initial_level

        # 创建传感器阵列
        self.sensor_array = SensorArray()
        self.sensor_array.add_sensor(VirtualLevelSensor(10.0))
        self.sensor_array.add_sensor(VirtualFlowSensor(200.0))


class GC01_LoadRejectionOverflow(GateTestCase):
    """GC-01: 负荷弃用防漫堤测试

    仿真工况：模拟下游用水户突然停止取水（流量需求归零），要求闸门关闭
    验收判据：
    1. 控制柜计算出"最优关闭曲线"，而非立即关死
    2. 仿真出的上游明渠最高水位未超过堤顶高程（安全超高内）
    """

    def __init__(self):
        super().__init__(
            test_id="GC-01",
            test_name="负荷弃用防漫堤测试",
            description="模拟下游用水户突然停止取水"
        )
        self.duration = 120.0  # 2分钟

    def run(self) -> TestResult:
        """执行测试"""
        dt = 0.5  # 500ms时间步长
        steps = int(self.duration / dt)

        # 先运行10秒稳态
        for _ in range(int(10.0 / dt)):
            self.simulator.step()

        self.result.add_log("稳态运行完成，模拟负荷弃用")

        # 命令闸门关闭
        self.controller.command_close(soft=True)

        max_level = self.initial_level
        level_history = []
        used_soft_close = False

        for i in range(steps):
            state = self.simulator.step()

            # 获取传感器读数
            sim_state = {
                'time': state.time,
                'level_upstream': state.level_upstream,
                'flow_rate': state.flow_rate,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, dt)

            # 控制器输入
            controller_input = {
                'opening': self.simulator.gate_opening,
                'Z_up': sensor_readings['Z'],
                'Z_down': self.simulator.downstream_level,
                'Q': sensor_readings['Q'],
            }

            ctrl_result = self.controller.run_cycle(controller_input)

            # 更新闸门开度
            self.simulator.set_gate_opening(ctrl_result['output'])

            # 记录数据
            record = {
                'time': state.time,
                'level': state.level_upstream,
                'opening': self.simulator.gate_opening,
                'flow': state.flow_rate,
            }
            level_history.append(record)

            # 更新最高水位
            max_level = max(max_level, state.level_upstream)

            # 检查是否使用柔性关闭
            if self.controller.gate_mode == GateControlMode.SOFT_CLOSE:
                used_soft_close = True

        # 计算安全高程
        safe_level = self.channel_params.design_depth - self.channel_params.freeboard

        self._max_level = max_level
        self._safe_level = safe_level
        self._used_soft_close = used_soft_close
        self._level_history = level_history

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 使用最优关闭曲线（柔性关闭）
        self.result.check_criterion(
            "计算最优关闭曲线",
            self._used_soft_close
        )

        # 判据2: 最高水位在安全超高内
        level_ok = self._max_level <= self._safe_level
        self.result.check_criterion(
            f"最高水位 <= {self._safe_level:.2f}m (安全超高内)",
            level_ok,
            self._max_level
        )

        return self._used_soft_close and level_ok


class GC02_ConstantFlowServo(GateTestCase):
    """GC-02: 恒定流量伺服测试

    仿真工况：模拟上游水位发生大幅波动（如从3m涨至5m）
    验收判据：
    1. 控制柜能根据水位上涨自动关小闸门
    2. 仿真出的过闸流量波动幅度控制在目标值的 +/- 5% 以内
    """

    def __init__(self):
        super().__init__(
            test_id="GC-02",
            test_name="恒定流量伺服测试",
            description="模拟上游水位大幅波动，验证流量伺服精度"
        )
        self.duration = 120.0
        self.target_flow = 50.0  # 目标流量

    def run(self) -> TestResult:
        """执行测试"""
        dt = 0.5
        steps = int(self.duration / dt)

        # 设置流量控制模式
        self.controller.set_flow_target(self.target_flow)
        self.result.add_log(f"目标流量: {self.target_flow} m³/s")

        flow_history = []
        gate_adjusted = False

        for i in range(steps):
            t = i * dt

            # 模拟上游水位变化 (从3m涨至5m)
            if t < 20:
                upstream_level = self.initial_level
            elif t < 60:
                # 线性上涨
                progress = (t - 20) / 40
                upstream_level = self.initial_level + 2.0 * progress
            else:
                upstream_level = 5.0

            # 更新仿真器水位
            self.simulator.upstream_level = upstream_level

            state = self.simulator.step()

            # 传感器读数
            sim_state = {
                'time': state.time,
                'level_upstream': upstream_level,
                'flow_rate': state.flow_rate,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, dt)

            # 控制器输入
            controller_input = {
                'opening': self.simulator.gate_opening,
                'Z_up': sensor_readings['Z'],
                'Z_down': self.simulator.downstream_level,
                'Q': sensor_readings['Q'],
            }

            ctrl_result = self.controller.run_cycle(controller_input)
            new_opening = ctrl_result['output']

            # 检查是否调节闸门
            if abs(new_opening - self.simulator.gate_opening) > 0.01:
                gate_adjusted = True

            self.simulator.set_gate_opening(new_opening)

            # 记录流量
            flow_history.append({
                'time': t,
                'upstream_level': upstream_level,
                'flow': state.flow_rate,
                'opening': new_opening,
            })

        # 分析流量偏差
        flows = [r['flow'] for r in flow_history[int(20/dt):]]  # 排除初始稳态
        if flows:
            mean_flow = np.mean(flows)
            max_deviation = max(abs(f - self.target_flow) / self.target_flow for f in flows)
        else:
            mean_flow = 0
            max_deviation = 1.0

        self._gate_adjusted = gate_adjusted
        self._max_flow_deviation = max_deviation
        self._mean_flow = mean_flow
        self._flow_history = flow_history

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 根据水位上涨自动调节闸门
        self.result.check_criterion(
            "根据水位上涨自动关小闸门",
            self._gate_adjusted
        )

        # 判据2: 流量波动在 +/- 5% 以内
        flow_stable = self._max_flow_deviation <= 0.05
        self.result.check_criterion(
            "流量波动幅度 <= +/- 5%",
            flow_stable,
            self._max_flow_deviation * 100
        )

        return self._gate_adjusted and flow_stable


class GC03_SensorDriftTolerance(GateTestCase):
    """GC-03: 传感器漂移容错测试

    仿真工况：模拟水位计读数突然跳变或卡死
    验收判据：
    1. 系统通过流量与开度的逻辑校验识别出水位异常
    2. 保持当前开度或切换至"开度控制模式"，不发生误调节
    """

    def __init__(self):
        super().__init__(
            test_id="GC-03",
            test_name="传感器漂移容错测试",
            description="模拟水位计读数突然跳变或卡死"
        )
        self.duration = 60.0

    def run(self) -> TestResult:
        """执行测试"""
        dt = 0.5
        steps = int(self.duration / dt)

        # 设置流量控制模式
        self.controller.set_flow_target(self.target_flow if hasattr(self, 'target_flow') else 50.0)

        # 正常运行20秒
        for _ in range(int(20.0 / dt)):
            self.simulator.step()

        self.result.add_log("正常运行完成，注入水位传感器故障")

        # 记录注入故障前的开度
        pre_fault_opening = self.simulator.gate_opening

        # 注入水位计故障：突然跳变到满量程
        self.sensor_array.inject_fault('Z', SensorFaultType.FULL_SCALE)

        fault_detected = False
        switched_to_opening_mode = False
        wrong_adjustment = False

        for i in range(int(40.0 / dt)):
            state = self.simulator.step()

            # 传感器读数（水位计已故障）
            sim_state = {
                'time': state.time,
                'level_upstream': state.level_upstream,  # 真实值
                'flow_rate': state.flow_rate,
            }
            sensor_readings = self.sensor_array.update_all(sim_state, dt)

            controller_input = {
                'opening': self.simulator.gate_opening,
                'Z_up': sensor_readings['Z'],  # 故障值（满量程）
                'Z_down': self.simulator.downstream_level,
                'Q': sensor_readings['Q'],
            }

            ctrl_result = self.controller.run_cycle(controller_input)

            # 检查是否切换到开度控制模式
            if self.controller.gate_mode == GateControlMode.OPENING:
                switched_to_opening_mode = True

            # 检查是否检测到水位异常
            if self.controller._level_jump_detected:
                fault_detected = True
                self.result.add_log("检测到水位计信号异常")

            # 检查是否发生误调节
            opening_change = abs(ctrl_result['output'] - pre_fault_opening)
            if opening_change > 0.5:  # 开度变化超过0.5m
                wrong_adjustment = True

            # 不实际更新闸门开度（避免误调节）
            # self.simulator.set_gate_opening(ctrl_result['output'])

        self._fault_detected = fault_detected
        self._switched_to_opening_mode = switched_to_opening_mode
        self._wrong_adjustment = wrong_adjustment

        return self.result

    def evaluate(self) -> bool:
        """评估测试结果"""
        # 判据1: 识别水位异常
        self.result.check_criterion(
            "通过逻辑校验识别水位异常",
            self._fault_detected
        )

        # 判据2: 切换到开度控制模式或保持当前开度
        proper_response = self._switched_to_opening_mode or not self._wrong_adjustment
        self.result.check_criterion(
            "保持当前开度或切换至开度控制模式",
            proper_response
        )

        # 判据3: 不发生误调节
        no_wrong_adjustment = not self._wrong_adjustment
        self.result.check_criterion(
            "不发生误调节",
            no_wrong_adjustment
        )

        return self._fault_detected and proper_response


class GateTestSuite(HILTestSuite):
    """闸门测试套件"""

    def __init__(self):
        super().__init__("闸门必测工况集")

        self.add_test(GC01_LoadRejectionOverflow())
        self.add_test(GC02_ConstantFlowServo())
        self.add_test(GC03_SensorDriftTolerance())
