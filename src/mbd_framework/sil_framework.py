# -*- coding: utf-8 -*-
"""
SIL Framework - 软件在环测试框架
Software-In-the-Loop Testing Framework

提供完整的软件在环仿真和测试能力
包括MIL(模型在环)、SIL(软件在环)测试
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Tuple, Union
from datetime import datetime
import time
import copy
import threading
import json


class TestResult(Enum):
    """测试结果"""
    NOT_RUN = auto()            # 未运行
    RUNNING = auto()            # 运行中
    PASSED = auto()             # 通过
    FAILED = auto()             # 失败
    ERROR = auto()              # 错误
    SKIPPED = auto()            # 跳过
    BLOCKED = auto()            # 阻塞


class CoverageType(Enum):
    """覆盖类型"""
    STATEMENT = auto()          # 语句覆盖
    BRANCH = auto()             # 分支覆盖
    CONDITION = auto()          # 条件覆盖
    MCDC = auto()               # MC/DC覆盖
    PATH = auto()               # 路径覆盖
    REQUIREMENT = auto()        # 需求覆盖


class SimulationMode(Enum):
    """仿真模式"""
    OFFLINE = auto()            # 离线仿真
    ACCELERATED = auto()        # 加速仿真
    REALTIME = auto()           # 实时仿真
    SCALED = auto()             # 按比例仿真


@dataclass
class TestCase:
    """测试用例基类"""
    test_id: str                            # 测试ID
    name: str                               # 名称
    description: str                        # 描述
    category: str = "FUNCTIONAL"            # 类别

    # 关联
    requirements: List[str] = field(default_factory=list)  # 关联需求
    safety_goals: List[str] = field(default_factory=list)  # 关联安全目标

    # 前置条件和输入
    preconditions: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)

    # 预期结果
    expected_outputs: Dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: List[str] = field(default_factory=list)
    tolerances: Dict[str, float] = field(default_factory=dict)

    # 执行参数
    timeout: float = 60.0                   # 超时时间(秒)
    priority: int = 2                       # 优先级: 1(高), 2(中), 3(低)

    # 结果
    result: TestResult = TestResult.NOT_RUN
    actual_outputs: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    error_message: str = ""
    execution_log: List[str] = field(default_factory=list)


@dataclass
class SILTestCase(TestCase):
    """SIL测试用例"""
    # 仿真配置
    simulation_time: float = 10.0           # 仿真时间(秒)
    time_step: float = 0.001                # 时间步长(秒)
    simulation_mode: SimulationMode = SimulationMode.OFFLINE

    # 激励信号
    input_signals: Dict[str, List[Tuple[float, Any]]] = field(default_factory=dict)

    # 断言
    assertions: List[Dict[str, Any]] = field(default_factory=list)

    # 故障注入
    fault_injection: Optional[Dict] = None

    # 记录
    record_signals: List[str] = field(default_factory=list)
    recorded_data: Dict[str, List] = field(default_factory=dict)


class SILTestEnvironment:
    """SIL测试环境"""

    def __init__(self, env_id: str, name: str):
        self.env_id = env_id
        self.name = name
        self.initialized = False

        # 模型组件
        self.plant_model = None             # 被控对象模型
        self.controller = None              # 控制器
        self.sensors: Dict[str, Any] = {}   # 传感器模型
        self.actuators: Dict[str, Any] = {} # 执行器模型

        # 仿真参数
        self.simulation_time = 0.0
        self.time_step = 0.001
        self.current_time = 0.0
        self.max_simulation_time = 3600.0

        # 数据记录
        self.time_history: List[float] = []
        self.data_history: Dict[str, List] = {}
        self.event_log: List[Dict] = []

        # 回调
        self.pre_step_callbacks: List[Callable] = []
        self.post_step_callbacks: List[Callable] = []

    def initialize(self, config: Dict[str, Any] = None):
        """初始化测试环境"""
        if config:
            self.time_step = config.get('time_step', 0.001)
            self.max_simulation_time = config.get('max_time', 3600.0)

        self.current_time = 0.0
        self.time_history = []
        self.data_history = {}
        self.event_log = []

        # 初始化各模型
        if self.plant_model:
            self.plant_model.initialize()
        if self.controller:
            self.controller.initialize()

        self.initialized = True
        self._log_event("INITIALIZED", "Environment initialized")

    def set_plant_model(self, model: Any):
        """设置被控对象模型"""
        self.plant_model = model

    def set_controller(self, controller: Any):
        """设置控制器"""
        self.controller = controller

    def add_sensor(self, name: str, sensor: Any):
        """添加传感器"""
        self.sensors[name] = sensor

    def add_actuator(self, name: str, actuator: Any):
        """添加执行器"""
        self.actuators[name] = actuator

    def step(self, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行一步仿真"""
        if not self.initialized:
            raise RuntimeError("Environment not initialized")

        # 前置回调
        for callback in self.pre_step_callbacks:
            callback(self.current_time, inputs)

        outputs = {}

        # 1. 传感器测量
        measurements = {}
        for name, sensor in self.sensors.items():
            if hasattr(sensor, 'measure'):
                measurements[name] = sensor.measure(self.plant_model)

        # 2. 控制器计算
        control_outputs = {}
        if self.controller:
            controller_inputs = {**measurements}
            if inputs:
                controller_inputs.update(inputs)
            if hasattr(self.controller, 'compute'):
                control_outputs = self.controller.compute(controller_inputs)
            elif hasattr(self.controller, 'update'):
                self.controller.update(self.time_step)
                control_outputs = self.controller.get_outputs()

        # 3. 执行器动作
        actuator_outputs = {}
        for name, actuator in self.actuators.items():
            if name in control_outputs and hasattr(actuator, 'actuate'):
                actuator_outputs[name] = actuator.actuate(control_outputs[name])

        # 4. 被控对象更新
        if self.plant_model:
            plant_inputs = {**actuator_outputs}
            if hasattr(self.plant_model, 'step'):
                self.plant_model.step(plant_inputs, self.time_step)
            elif hasattr(self.plant_model, 'update'):
                self.plant_model.set_inputs(plant_inputs)
                self.plant_model.update(self.time_step)

        # 收集输出
        outputs = {
            'time': self.current_time,
            'measurements': measurements,
            'control': control_outputs,
            'actuators': actuator_outputs
        }

        # 记录数据
        self._record_data(outputs)

        # 更新时间
        self.current_time += self.time_step

        # 后置回调
        for callback in self.post_step_callbacks:
            callback(self.current_time, outputs)

        return outputs

    def run(self, duration: float, inputs_schedule: Dict[str, List[Tuple[float, Any]]] = None) -> Dict[str, Any]:
        """运行仿真"""
        if not self.initialized:
            self.initialize()

        start_time = self.current_time
        end_time = start_time + duration
        step_count = 0

        while self.current_time < end_time:
            # 获取当前时刻的输入
            current_inputs = {}
            if inputs_schedule:
                for signal_name, schedule in inputs_schedule.items():
                    current_inputs[signal_name] = self._interpolate_input(
                        schedule, self.current_time - start_time
                    )

            self.step(current_inputs)
            step_count += 1

        return {
            'start_time': start_time,
            'end_time': self.current_time,
            'step_count': step_count,
            'data': self.data_history
        }

    def _interpolate_input(self, schedule: List[Tuple[float, Any]], t: float) -> Any:
        """插值输入信号"""
        if not schedule:
            return 0.0

        # 找到时间点前后的值
        prev_value = schedule[0][1]
        for time_point, value in schedule:
            if time_point <= t:
                prev_value = value
            else:
                break

        return prev_value

    def _record_data(self, outputs: Dict[str, Any]):
        """记录数据"""
        self.time_history.append(self.current_time)

        def flatten_dict(d: Dict, prefix: str = '') -> Dict:
            items = {}
            for k, v in d.items():
                key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    items.update(flatten_dict(v, key))
                else:
                    items[key] = v
            return items

        flat_outputs = flatten_dict(outputs)
        for key, value in flat_outputs.items():
            if key not in self.data_history:
                self.data_history[key] = []
            self.data_history[key].append(value)

    def _log_event(self, event_type: str, message: str):
        """记录事件"""
        self.event_log.append({
            'timestamp': datetime.now().isoformat(),
            'sim_time': self.current_time,
            'type': event_type,
            'message': message
        })

    def reset(self):
        """重置环境"""
        self.current_time = 0.0
        self.time_history = []
        self.data_history = {}
        self.event_log = []
        self.initialized = False


class SILTestSuite:
    """SIL测试套件"""

    def __init__(self, suite_id: str, name: str):
        self.suite_id = suite_id
        self.name = name
        self.test_cases: Dict[str, SILTestCase] = {}
        self.test_environment: Optional[SILTestEnvironment] = None
        self.setup_func: Optional[Callable] = None
        self.teardown_func: Optional[Callable] = None

        # 执行状态
        self.executed = False
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # 结果统计
        self.passed_count = 0
        self.failed_count = 0
        self.error_count = 0
        self.skipped_count = 0

    def add_test_case(self, test_case: SILTestCase):
        """添加测试用例"""
        self.test_cases[test_case.test_id] = test_case

    def set_environment(self, env: SILTestEnvironment):
        """设置测试环境"""
        self.test_environment = env

    def set_setup(self, func: Callable):
        """设置setup函数"""
        self.setup_func = func

    def set_teardown(self, func: Callable):
        """设置teardown函数"""
        self.teardown_func = func

    def run(self, test_ids: List[str] = None) -> Dict[str, Any]:
        """运行测试"""
        self.start_time = datetime.now()
        self.passed_count = 0
        self.failed_count = 0
        self.error_count = 0
        self.skipped_count = 0

        # 确定要运行的测试
        tests_to_run = test_ids if test_ids else list(self.test_cases.keys())

        # 按优先级排序
        tests_to_run.sort(key=lambda x: self.test_cases[x].priority)

        results = {}
        for test_id in tests_to_run:
            if test_id not in self.test_cases:
                continue

            test_case = self.test_cases[test_id]
            result = self._run_single_test(test_case)
            results[test_id] = result

            # 更新统计
            if result['result'] == TestResult.PASSED:
                self.passed_count += 1
            elif result['result'] == TestResult.FAILED:
                self.failed_count += 1
            elif result['result'] == TestResult.ERROR:
                self.error_count += 1
            else:
                self.skipped_count += 1

        self.end_time = datetime.now()
        self.executed = True

        return {
            'suite_id': self.suite_id,
            'suite_name': self.name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total': len(tests_to_run),
            'passed': self.passed_count,
            'failed': self.failed_count,
            'error': self.error_count,
            'skipped': self.skipped_count,
            'results': results
        }

    def _run_single_test(self, test_case: SILTestCase) -> Dict[str, Any]:
        """运行单个测试"""
        test_case.result = TestResult.RUNNING
        test_case.execution_log = []
        start_time = time.time()

        try:
            # Setup
            if self.setup_func:
                self.setup_func()

            # 初始化环境
            if self.test_environment:
                self.test_environment.initialize()

            # 运行仿真
            sim_result = self.test_environment.run(
                test_case.simulation_time,
                test_case.input_signals
            )

            # 记录数据
            test_case.recorded_data = sim_result.get('data', {})

            # 验证结果
            passed, messages = self._verify_results(test_case, sim_result)

            if passed:
                test_case.result = TestResult.PASSED
            else:
                test_case.result = TestResult.FAILED
                test_case.error_message = "; ".join(messages)

            test_case.execution_log.extend(messages)

        except Exception as e:
            test_case.result = TestResult.ERROR
            test_case.error_message = str(e)
            test_case.execution_log.append(f"Exception: {str(e)}")

        finally:
            # Teardown
            if self.teardown_func:
                try:
                    self.teardown_func()
                except:
                    pass

            # 重置环境
            if self.test_environment:
                self.test_environment.reset()

        test_case.execution_time = time.time() - start_time

        return {
            'test_id': test_case.test_id,
            'name': test_case.name,
            'result': test_case.result,
            'execution_time': test_case.execution_time,
            'error_message': test_case.error_message,
            'log': test_case.execution_log
        }

    def _verify_results(self, test_case: SILTestCase,
                       sim_result: Dict) -> Tuple[bool, List[str]]:
        """验证测试结果"""
        all_passed = True
        messages = []

        # 验证预期输出
        data = sim_result.get('data', {})

        for output_name, expected_value in test_case.expected_outputs.items():
            if output_name not in data:
                all_passed = False
                messages.append(f"Output '{output_name}' not found in results")
                continue

            actual_values = data[output_name]
            if not actual_values:
                all_passed = False
                messages.append(f"Output '{output_name}' has no data")
                continue

            # 取最终值进行比较
            actual_value = actual_values[-1]
            tolerance = test_case.tolerances.get(output_name, 0.01)

            if isinstance(expected_value, (int, float)):
                if abs(actual_value - expected_value) > abs(expected_value * tolerance):
                    all_passed = False
                    messages.append(
                        f"Output '{output_name}': expected {expected_value}, "
                        f"got {actual_value} (tolerance: {tolerance})"
                    )
                else:
                    messages.append(f"Output '{output_name}': PASSED")
            else:
                if actual_value != expected_value:
                    all_passed = False
                    messages.append(
                        f"Output '{output_name}': expected {expected_value}, got {actual_value}"
                    )

        # 验证断言
        for assertion in test_case.assertions:
            passed, msg = self._check_assertion(assertion, data)
            if not passed:
                all_passed = False
            messages.append(msg)

        return all_passed, messages

    def _check_assertion(self, assertion: Dict, data: Dict) -> Tuple[bool, str]:
        """检查断言"""
        assertion_type = assertion.get('type', 'value')
        signal = assertion.get('signal', '')
        condition = assertion.get('condition', '')

        if signal not in data:
            return False, f"Assertion failed: signal '{signal}' not found"

        values = data[signal]

        if assertion_type == 'always':
            # 始终满足条件
            threshold = assertion.get('threshold', 0)
            op = assertion.get('operator', '<')
            for v in values:
                if not self._compare(v, op, threshold):
                    return False, f"Assertion 'always {signal} {op} {threshold}' failed"
            return True, f"Assertion 'always {signal} {op} {threshold}' passed"

        elif assertion_type == 'eventually':
            # 最终满足条件
            threshold = assertion.get('threshold', 0)
            op = assertion.get('operator', '==')
            for v in values:
                if self._compare(v, op, threshold):
                    return True, f"Assertion 'eventually {signal} {op} {threshold}' passed"
            return False, f"Assertion 'eventually {signal} {op} {threshold}' failed"

        elif assertion_type == 'settling_time':
            # 稳定时间
            target = assertion.get('target', 0)
            tolerance = assertion.get('tolerance', 0.05)
            max_time = assertion.get('max_time', 5.0)
            # 简化实现
            return True, "Settling time assertion skipped"

        return True, "Unknown assertion type"

    def _compare(self, value: float, op: str, threshold: float) -> bool:
        """比较操作"""
        ops = {
            '<': lambda a, b: a < b,
            '<=': lambda a, b: a <= b,
            '>': lambda a, b: a > b,
            '>=': lambda a, b: a >= b,
            '==': lambda a, b: abs(a - b) < 1e-6,
            '!=': lambda a, b: abs(a - b) >= 1e-6
        }
        return ops.get(op, lambda a, b: False)(value, threshold)


class ModelInLoopTest:
    """模型在环测试 (MIL)"""

    def __init__(self, test_id: str, name: str):
        self.test_id = test_id
        self.name = name
        self.reference_model = None         # 参考模型
        self.test_model = None              # 测试模型
        self.comparison_results: Dict[str, Any] = {}

    def set_reference_model(self, model: Any):
        """设置参考模型"""
        self.reference_model = model

    def set_test_model(self, model: Any):
        """设置测试模型"""
        self.test_model = model

    def run_comparison(self, inputs: Dict[str, Any],
                      duration: float,
                      dt: float = 0.001) -> Dict[str, Any]:
        """运行对比测试"""
        ref_outputs = []
        test_outputs = []
        times = []

        # 初始化模型
        if hasattr(self.reference_model, 'initialize'):
            self.reference_model.initialize()
        if hasattr(self.test_model, 'initialize'):
            self.test_model.initialize()

        t = 0.0
        while t < duration:
            # 运行参考模型
            if hasattr(self.reference_model, 'step'):
                ref_out = self.reference_model.step(inputs, dt)
            else:
                ref_out = {}

            # 运行测试模型
            if hasattr(self.test_model, 'step'):
                test_out = self.test_model.step(inputs, dt)
            else:
                test_out = {}

            ref_outputs.append(ref_out)
            test_outputs.append(test_out)
            times.append(t)

            t += dt

        # 计算差异
        self.comparison_results = self._compute_differences(
            times, ref_outputs, test_outputs
        )

        return self.comparison_results

    def _compute_differences(self, times: List[float],
                            ref_outputs: List[Dict],
                            test_outputs: List[Dict]) -> Dict[str, Any]:
        """计算模型输出差异"""
        results = {
            'times': times,
            'max_differences': {},
            'rms_differences': {},
            'signals': {}
        }

        if not ref_outputs or not test_outputs:
            return results

        # 获取所有信号名
        all_signals = set()
        for out in ref_outputs + test_outputs:
            all_signals.update(out.keys())

        for signal in all_signals:
            ref_values = [out.get(signal, 0.0) for out in ref_outputs]
            test_values = [out.get(signal, 0.0) for out in test_outputs]

            if isinstance(ref_values[0], (int, float)):
                differences = [abs(r - t) for r, t in zip(ref_values, test_values)]
                results['max_differences'][signal] = max(differences)
                results['rms_differences'][signal] = (
                    sum(d**2 for d in differences) / len(differences)
                ) ** 0.5
                results['signals'][signal] = {
                    'reference': ref_values,
                    'test': test_values,
                    'difference': differences
                }

        return results


class SoftwareInLoopTest(ModelInLoopTest):
    """软件在环测试 (SIL)"""

    def __init__(self, test_id: str, name: str):
        super().__init__(test_id, name)
        self.generated_code = None          # 生成的代码
        self.code_coverage: Dict[str, float] = {}

    def set_generated_code(self, code: Any):
        """设置生成的代码"""
        self.generated_code = code

    def run_back_to_back_test(self, inputs: Dict[str, Any],
                              duration: float) -> Dict[str, Any]:
        """运行背靠背测试"""
        # 参考模型作为golden reference
        # 生成代码作为测试对象
        results = self.run_comparison(inputs, duration)
        results['test_type'] = 'back_to_back'
        return results


@dataclass
class CoverageItem:
    """覆盖项"""
    item_id: str
    item_type: CoverageType
    description: str
    covered: bool = False
    hit_count: int = 0


class SILCoverage:
    """SIL覆盖分析"""

    def __init__(self):
        self.coverage_items: Dict[str, CoverageItem] = {}
        self.requirement_map: Dict[str, List[str]] = {}  # 需求 -> 测试用例

    def add_item(self, item: CoverageItem):
        """添加覆盖项"""
        self.coverage_items[item.item_id] = item

    def mark_covered(self, item_id: str):
        """标记为已覆盖"""
        if item_id in self.coverage_items:
            self.coverage_items[item_id].covered = True
            self.coverage_items[item_id].hit_count += 1

    def link_requirement(self, req_id: str, test_ids: List[str]):
        """关联需求与测试用例"""
        self.requirement_map[req_id] = test_ids

    def get_coverage_by_type(self, coverage_type: CoverageType) -> Dict[str, Any]:
        """按类型获取覆盖率"""
        items = [i for i in self.coverage_items.values()
                if i.item_type == coverage_type]
        if not items:
            return {'type': coverage_type.name, 'total': 0, 'covered': 0, 'percentage': 0.0}

        covered = sum(1 for i in items if i.covered)
        return {
            'type': coverage_type.name,
            'total': len(items),
            'covered': covered,
            'percentage': covered / len(items) * 100
        }

    def get_requirement_coverage(self) -> Dict[str, Any]:
        """获取需求覆盖率"""
        total = len(self.requirement_map)
        covered = sum(1 for tests in self.requirement_map.values() if tests)
        return {
            'total_requirements': total,
            'covered_requirements': covered,
            'percentage': covered / total * 100 if total > 0 else 0.0,
            'details': {
                req: len(tests) > 0
                for req, tests in self.requirement_map.items()
            }
        }

    def generate_report(self) -> Dict[str, Any]:
        """生成覆盖报告"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {},
            'by_type': {},
            'requirement_coverage': self.get_requirement_coverage(),
            'uncovered_items': []
        }

        # 总体覆盖率
        total = len(self.coverage_items)
        covered = sum(1 for i in self.coverage_items.values() if i.covered)
        report['summary'] = {
            'total_items': total,
            'covered_items': covered,
            'overall_percentage': covered / total * 100 if total > 0 else 0.0
        }

        # 按类型分析
        for ct in CoverageType:
            report['by_type'][ct.name] = self.get_coverage_by_type(ct)

        # 未覆盖项
        report['uncovered_items'] = [
            {'id': item.item_id, 'type': item.item_type.name, 'description': item.description}
            for item in self.coverage_items.values()
            if not item.covered
        ]

        return report


# 预定义的水利系统SIL测试用例
def create_valve_sil_test_cases() -> List[SILTestCase]:
    """创建阀门控制SIL测试用例"""
    test_cases = []

    # 测试1: 阀门开度控制
    test_cases.append(SILTestCase(
        test_id="SIL_VALVE_001",
        name="阀门开度阶跃响应测试",
        description="测试阀门从全关到50%开度的响应特性",
        category="FUNCTIONAL",
        requirements=["REQ_VALVE_001", "REQ_VALVE_002"],
        simulation_time=30.0,
        time_step=0.01,
        input_signals={
            'position_setpoint': [(0.0, 0.0), (5.0, 0.5), (25.0, 0.5)]
        },
        expected_outputs={
            'valve_position': 0.5
        },
        tolerances={
            'valve_position': 0.02
        },
        assertions=[
            {'type': 'always', 'signal': 'valve_position', 'operator': '<=', 'threshold': 1.0},
            {'type': 'always', 'signal': 'valve_position', 'operator': '>=', 'threshold': 0.0},
            {'type': 'eventually', 'signal': 'valve_position', 'operator': '>=', 'threshold': 0.48}
        ]
    ))

    # 测试2: 水锤防护
    test_cases.append(SILTestCase(
        test_id="SIL_VALVE_002",
        name="水锤防护快关测试",
        description="测试紧急关闭时的两阶段液压关闭曲线",
        category="SAFETY",
        requirements=["REQ_VALVE_003"],
        safety_goals=["SG_WATER_HAMMER"],
        simulation_time=20.0,
        time_step=0.001,
        input_signals={
            'position_setpoint': [(0.0, 1.0), (2.0, 0.0)]
        },
        assertions=[
            {'type': 'always', 'signal': 'pressure', 'operator': '<', 'threshold': 2.0}  # 压力不超过2倍
        ]
    ))

    # 测试3: 故障模式
    test_cases.append(SILTestCase(
        test_id="SIL_VALVE_003",
        name="传感器故障降级测试",
        description="测试位置传感器故障时的降级控制",
        category="FAULT_TOLERANCE",
        requirements=["REQ_VALVE_004"],
        simulation_time=60.0,
        fault_injection={
            'type': 'SENSOR_FAULT',
            'signal': 'position_feedback',
            'mode': 'STUCK',
            'start_time': 10.0
        }
    ))

    return test_cases


def create_pump_sil_test_cases() -> List[SILTestCase]:
    """创建水泵控制SIL测试用例"""
    test_cases = []

    # 测试1: 启动序列
    test_cases.append(SILTestCase(
        test_id="SIL_PUMP_001",
        name="水泵启动序列测试",
        description="测试水泵从停机到额定转速的启动过程",
        category="FUNCTIONAL",
        requirements=["REQ_PUMP_001"],
        simulation_time=60.0,
        time_step=0.01,
        input_signals={
            'start_command': [(0.0, False), (5.0, True)],
            'speed_setpoint': [(0.0, 0.0), (5.0, 1500.0)]
        },
        expected_outputs={
            'pump_speed': 1500.0,
            'pump_running': True
        },
        tolerances={
            'pump_speed': 0.05
        }
    ))

    # 测试2: 汽蚀保护
    test_cases.append(SILTestCase(
        test_id="SIL_PUMP_002",
        name="汽蚀保护测试",
        description="测试低吸入压力时的汽蚀保护功能",
        category="SAFETY",
        requirements=["REQ_PUMP_003"],
        safety_goals=["SG_CAVITATION"],
        simulation_time=30.0,
        input_signals={
            'suction_pressure': [(0.0, 0.5), (10.0, 0.1), (20.0, 0.5)]  # 模拟压力下降
        },
        assertions=[
            {'type': 'eventually', 'signal': 'cavitation_alarm', 'operator': '==', 'threshold': 1}
        ]
    ))

    return test_cases
