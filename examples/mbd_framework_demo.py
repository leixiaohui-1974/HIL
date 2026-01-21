# -*- coding: utf-8 -*-
"""
MBD Framework 综合演示
Model-Based Design Framework Comprehensive Demo

演示MBD框架的完整功能:
1. 模型驱动设计流程
2. ODD运行设计域定义和监控
3. 功能安全和降级策略
4. SIL/HIL/HITL测试体系
5. 集成测试和验证
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from typing import Dict, Any

# 导入MBD框架模块
from src.mbd_framework.mbd_core import (
    MBDModel, MBDWorkflow, VModelPhase, ModelType,
    RequirementTrace, DesignSpecification, ModelArtifact,
    ModelValidator, CodeGenerator, create_default_validator
)
from src.mbd_framework.odd_framework import (
    ODDDefinition, ODDBoundary, OperatingCondition, ODDMonitor,
    ODDValidator, ODDViolationHandler, ODDCategory, ConditionType,
    BoundaryType, ViolationSeverity,
    create_hydraulic_system_odd, create_multi_energy_odd
)
from src.mbd_framework.functional_safety import (
    SafetyLevel, ASILLevel, SafetyGoal, SafetyRequirement,
    DegradationStrategy, DegradationStateMachine, DegradationLevel,
    FaultHandler, SafetyMonitor, Fault, FaultType, FaultSeverity, FaultCategory,
    create_hydraulic_degradation_strategies, create_multi_energy_degradation_strategies
)
from src.mbd_framework.sil_framework import (
    SILTestEnvironment, SILTestCase, SILTestSuite,
    SimulationMode, create_valve_sil_test_cases, create_pump_sil_test_cases
)
from src.mbd_framework.hil_enhanced import (
    HILTestEnvironment, HILTestCase, HILTestSuite,
    HardwareInterface, SimulatedHardwareInterface, HardwareChannel,
    HardwareType, SignalType, FaultInjector, FaultInjectionConfig, FaultMode,
    create_hydraulic_hil_test_cases
)
from src.mbd_framework.hitl_framework import (
    HITLTestEnvironment, HITLScenario, OperatorInterface,
    HumanFactorsModel, WorkloadAssessment, SituationAwareness, DecisionSupport,
    OperatorRole, OperatorAction, ActionType, AlarmInfo,
    create_hydraulic_hitl_scenarios, create_multi_energy_hitl_scenarios
)
from src.mbd_framework.integration_validation import (
    IntegrationTestSuite, IntegrationTestCase, SystemValidation,
    RegressionTestManager, CoverageAnalyzer, RequirementCoverage,
    TestReportGenerator, TestLevel,
    create_hydraulic_integration_tests, create_multi_energy_integration_tests
)


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_subsection(title: str):
    """打印子节标题"""
    print(f"\n--- {title} ---")


# ============================================================
# 示例模型实现
# ============================================================

class SimpleValveModel(MBDModel):
    """简单阀门模型 - 用于演示"""

    def __init__(self):
        super().__init__("VALVE_001", "Simple Valve Model", ModelType.ACTUATOR)
        self._parameters = {
            'max_opening': 1.0,
            'opening_rate': 0.1,
            'closing_rate': 0.15
        }
        self.artifact.inputs = ['position_setpoint', 'enable']
        self.artifact.outputs = ['position', 'flow', 'fully_open', 'fully_closed']
        self.artifact.parameters = self._parameters
        self.artifact.requirements = ['REQ_VALVE_001', 'REQ_VALVE_002']

    def initialize(self):
        self._states = {
            'position': 0.0,
            'velocity': 0.0
        }
        self._outputs = {
            'position': 0.0,
            'flow': 0.0,
            'fully_open': False,
            'fully_closed': True
        }

    def update(self, dt: float):
        setpoint = self._inputs.get('position_setpoint', 0.0)
        enable = self._inputs.get('enable', True)

        if not enable:
            return

        position = self._states['position']
        error = setpoint - position

        # 简单的位置控制
        if error > 0:
            rate = min(self._parameters['opening_rate'], abs(error) / dt)
            position += rate * dt
        elif error < 0:
            rate = min(self._parameters['closing_rate'], abs(error) / dt)
            position -= rate * dt

        position = max(0.0, min(self._parameters['max_opening'], position))
        self._states['position'] = position

        # 更新输出
        self._outputs['position'] = position
        self._outputs['flow'] = position * 10.0  # 简化流量计算
        self._outputs['fully_open'] = position >= 0.99
        self._outputs['fully_closed'] = position <= 0.01

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


class SimplePumpModel(MBDModel):
    """简单水泵模型 - 用于演示"""

    def __init__(self):
        super().__init__("PUMP_001", "Simple Pump Model", ModelType.ACTUATOR)
        self._parameters = {
            'rated_speed': 1500,
            'rated_flow': 100,
            'rated_head': 50
        }
        self.artifact.inputs = ['speed_setpoint', 'start_command']
        self.artifact.outputs = ['speed', 'flow', 'head', 'running']
        self.artifact.parameters = self._parameters

    def initialize(self):
        self._states = {
            'speed': 0.0,
            'running': False
        }
        self._outputs = {
            'speed': 0.0,
            'flow': 0.0,
            'head': 0.0,
            'running': False
        }

    def update(self, dt: float):
        start_cmd = self._inputs.get('start_command', False)
        speed_setpoint = self._inputs.get('speed_setpoint', 0.0)

        if start_cmd and not self._states['running']:
            self._states['running'] = True

        if not start_cmd and self._states['running']:
            self._states['running'] = False

        if self._states['running']:
            # 简单的转速跟踪
            current_speed = self._states['speed']
            error = speed_setpoint - current_speed
            self._states['speed'] += 0.1 * error * dt * 100
            self._states['speed'] = max(0, min(self._parameters['rated_speed'], self._states['speed']))
        else:
            self._states['speed'] = max(0, self._states['speed'] - 50 * dt)

        # 计算输出
        speed_ratio = self._states['speed'] / self._parameters['rated_speed']
        self._outputs['speed'] = self._states['speed']
        self._outputs['flow'] = self._parameters['rated_flow'] * speed_ratio
        self._outputs['head'] = self._parameters['rated_head'] * speed_ratio ** 2
        self._outputs['running'] = self._states['running']

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


# ============================================================
# 演示函数
# ============================================================

def demo_mbd_workflow():
    """演示1: MBD工作流程"""
    print_section("1. MBD工作流程演示")

    # 创建项目工作流
    workflow = MBDWorkflow("水利枢纽智能控制系统")

    # 添加需求
    print_subsection("1.1 添加需求")
    requirements = [
        RequirementTrace(
            requirement_id="REQ_VALVE_001",
            requirement_text="阀门控制器应能在50ms内响应位置指令",
            source="系统规格书",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_B"
        ),
        RequirementTrace(
            requirement_id="REQ_VALVE_002",
            requirement_text="阀门快关时应采用两阶段关闭曲线以防止水锤",
            source="安全分析报告",
            priority="HIGH",
            safety_related=True,
            asil_level="ASIL_C"
        ),
        RequirementTrace(
            requirement_id="REQ_PUMP_001",
            requirement_text="水泵启动过程应平滑,避免电流冲击",
            source="电气规范",
            priority="MEDIUM"
        )
    ]

    for req in requirements:
        workflow.add_requirement(req)
        print(f"  添加需求: {req.requirement_id} - {req.requirement_text[:30]}...")

    # 添加设计规格
    print_subsection("1.2 添加设计规格")
    spec = DesignSpecification(
        spec_id="SPEC_VALVE_CTRL",
        name="阀门控制器设计规格",
        description="智能阀门控制柜IVCU的详细设计规格",
        phase=VModelPhase.DETAILED_DESIGN,
        requirements=["REQ_VALVE_001", "REQ_VALVE_002"],
        inputs={'position_setpoint': 'float', 'enable': 'bool'},
        outputs={'position': 'float', 'status': 'int'}
    )
    workflow.add_specification(spec)
    print(f"  添加规格: {spec.spec_id} - {spec.name}")

    # 注册模型
    print_subsection("1.3 注册模型")
    valve_model = SimpleValveModel()
    valve_model.initialize()
    workflow.register_model(valve_model)
    print(f"  注册模型: {valve_model.model_id} - {valve_model.name}")

    # 模型验证
    print_subsection("1.4 模型验证")
    validator = create_default_validator()
    validation_result = validator.validate_model(valve_model)
    print(f"  验证状态: {'通过' if validation_result['overall_status'] else '失败'}")
    for rule in validation_result['rules_passed']:
        print(f"    [PASS] {rule['rule']}: {rule['message']}")

    # 生成追溯报告
    print_subsection("1.5 追溯报告")
    trace_report = workflow.generate_traceability_report()
    print(f"  需求覆盖情况:")
    for req_id, coverage in trace_report['requirements_coverage'].items():
        status = "已覆盖" if coverage['is_covered'] else "未覆盖"
        print(f"    {req_id}: {status}")

    return workflow, valve_model


def demo_odd_framework():
    """演示2: ODD运行设计域"""
    print_section("2. ODD运行设计域演示")

    # 创建水利系统ODD
    print_subsection("2.1 创建水利系统ODD")
    hydraulic_odd = create_hydraulic_system_odd()
    print(f"  ODD ID: {hydraulic_odd.odd_id}")
    print(f"  名称: {hydraulic_odd.name}")
    print(f"  条件数量: {len(hydraulic_odd.conditions)}")
    print(f"  边界数量: {len(hydraulic_odd.boundaries)}")

    # 显示运行条件
    print_subsection("2.2 运行条件")
    for cond_id, condition in hydraulic_odd.conditions.items():
        print(f"  {condition.name}: {condition.min_value} ~ {condition.max_value} {condition.unit}")

    # 验证运行点
    print_subsection("2.3 验证运行点")
    test_points = [
        {'system_pressure': 2.5, 'flow_rate': 50.0, 'water_level': 100.0, 'ambient_temperature': 25.0},
        {'system_pressure': 12.0, 'flow_rate': 50.0, 'water_level': 100.0, 'ambient_temperature': 25.0},  # 压力超限
        {'system_pressure': 2.5, 'flow_rate': 150.0, 'water_level': 100.0, 'ambient_temperature': 60.0},  # 温度超限
    ]

    for i, point in enumerate(test_points, 1):
        result = hydraulic_odd.validate_operating_point(point)
        status = "在ODD内" if result['in_odd'] else "ODD外"
        print(f"  测试点{i}: {status}")
        if result['boundary_violations']:
            for v in result['boundary_violations']:
                print(f"    违规: {v['boundary_id']} - {v['messages']}")

    # ODD监控
    print_subsection("2.4 ODD监控")
    monitor = ODDMonitor(hydraulic_odd)
    monitor.start_monitoring()

    # 注册违规处理器
    def critical_violation_handler(violation):
        print(f"    [CRITICAL] 检测到严重违规: {violation.boundary_id}")

    monitor.register_handler(ViolationSeverity.CRITICAL, critical_violation_handler)

    # 模拟监控
    print("  开始监控...")
    monitor.update({'system_pressure': 2.5, 'flow_rate': 50.0})
    print(f"    状态: 正常")
    monitor.update({'system_pressure': 11.0, 'flow_rate': 50.0})  # 触发违规
    print(f"    活动违规数: {len(monitor._active_violations)}")

    return hydraulic_odd


def demo_functional_safety():
    """演示3: 功能安全和降级策略"""
    print_section("3. 功能安全和降级策略演示")

    # 创建安全监控器
    print_subsection("3.1 创建安全监控系统")
    safety_monitor = SafetyMonitor("SAFETY_MONITOR_001")

    # 添加安全目标
    safety_goal = SafetyGoal(
        goal_id="SG_WATER_HAMMER",
        name="水锤防护",
        description="防止管道压力超过设计值的150%",
        asil_level=ASILLevel.ASIL_C,
        sil_level=SafetyLevel.SIL_2,
        hazard_description="快速关阀导致的水锤可能造成管道破裂",
        exposure="E3",
        controllability="C2",
        severity="S3",
        safe_state="阀门保持当前位置,启动泄压",
        fault_tolerant_time=0.5
    )
    safety_monitor.add_safety_goal(safety_goal)
    print(f"  添加安全目标: {safety_goal.name} (ASIL-{safety_goal.asil_level.name})")

    # 创建降级状态机
    print_subsection("3.2 降级状态机")
    degradation_sm = DegradationStateMachine("HYDRAULIC_SYSTEM")

    # 添加降级策略
    strategies = create_hydraulic_degradation_strategies()
    for strategy in strategies:
        degradation_sm.add_strategy(strategy)
        print(f"  添加策略: {strategy.name}")

    # 注册转换回调
    def on_degradation_change(from_level, to_level, reason):
        print(f"    降级转换: {from_level.name} -> {to_level.name} (原因: {reason})")

    degradation_sm.register_transition_callback(on_degradation_change)

    # 模拟故障
    print_subsection("3.3 故障模拟")
    print(f"  当前状态: {degradation_sm.current_level.name}")

    # 报告传感器故障
    sensor_fault = Fault(
        fault_id="FAULT_001",
        name="位置传感器故障",
        description="阀门位置传感器信号丢失",
        fault_type=FaultType.SENSOR_FAULT,
        category=FaultCategory.TRANSIENT,
        severity=FaultSeverity.MARGINAL
    )
    degradation_sm.report_fault(sensor_fault)

    # 显示可用功能
    print_subsection("3.4 当前可用功能")
    features = degradation_sm.get_available_features()
    for feature, available in features.items():
        status = "可用" if available else "禁用"
        print(f"  {feature}: {status}")

    # 清除故障
    print_subsection("3.5 故障恢复")
    degradation_sm.clear_fault("FAULT_001")
    print(f"  当前状态: {degradation_sm.current_level.name}")

    return safety_monitor, degradation_sm


def demo_sil_testing():
    """演示4: SIL软件在环测试"""
    print_section("4. SIL软件在环测试演示")

    # 创建测试环境
    print_subsection("4.1 创建SIL测试环境")
    sil_env = SILTestEnvironment("SIL_ENV_001", "阀门控制SIL测试环境")

    # 设置模型
    valve_model = SimpleValveModel()
    sil_env.set_plant_model(valve_model)
    print(f"  测试环境: {sil_env.name}")

    # 创建测试用例
    print_subsection("4.2 创建测试用例")
    test_cases = create_valve_sil_test_cases()
    print(f"  加载 {len(test_cases)} 个阀门测试用例")

    # 创建测试套件
    print_subsection("4.3 创建测试套件")
    sil_suite = SILTestSuite("SIL_VALVE_SUITE", "阀门控制SIL测试套件")
    sil_suite.set_environment(sil_env)
    for tc in test_cases[:2]:  # 只运行前2个用例演示
        sil_suite.add_test_case(tc)
        print(f"  添加测试: {tc.test_id} - {tc.name}")

    # 运行测试
    print_subsection("4.4 运行测试")
    results = sil_suite.run()
    print(f"  总测试数: {results['total']}")
    print(f"  通过: {results['passed']}")
    print(f"  失败: {results['failed']}")
    print(f"  错误: {results['error']}")

    return sil_suite


def demo_hil_testing():
    """演示5: HIL硬件在环测试"""
    print_section("5. HIL硬件在环测试演示")

    # 创建HIL测试环境
    print_subsection("5.1 创建HIL测试环境")
    hil_env = HILTestEnvironment("HIL_ENV_001", "水利系统HIL测试环境")

    # 添加模拟硬件接口
    sim_interface = SimulatedHardwareInterface("VALVE_IO", "阀门控制IO接口")
    sim_interface.add_channel(HardwareChannel(
        channel_id="valve_cmd",
        name="阀门指令",
        hardware_type=HardwareType.ANALOG_OUTPUT,
        signal_type=SignalType.VOLTAGE,
        min_value=0.0,
        max_value=10.0,
        engineering_unit="%",
        scale_factor=10.0
    ))
    sim_interface.add_channel(HardwareChannel(
        channel_id="valve_position",
        name="阀门位置反馈",
        hardware_type=HardwareType.ANALOG_INPUT,
        signal_type=SignalType.CURRENT,
        min_value=4.0,
        max_value=20.0,
        engineering_unit="%",
        scale_factor=6.25,
        offset=-25.0
    ))

    hil_env.add_hardware_interface(sim_interface)
    print(f"  HIL环境: {hil_env.name}")
    print(f"  硬件接口: {sim_interface.name}")

    # 创建测试用例
    print_subsection("5.2 创建HIL测试用例")
    hil_test_cases = create_hydraulic_hil_test_cases()
    print(f"  加载 {len(hil_test_cases)} 个HIL测试用例")

    # 故障注入演示
    print_subsection("5.3 故障注入配置")
    fault_injector = hil_env.fault_injector
    fault_config = FaultInjectionConfig(
        fault_id="FI_001",
        channel_id="valve_position",
        fault_mode=FaultMode.NOISE,
        start_time=10.0,
        duration=5.0,
        parameters={'amplitude': 0.5}
    )
    fault_injector.add_fault(fault_config)
    print(f"  故障注入: {fault_config.fault_mode.name} @ {fault_config.channel_id}")
    print(f"  开始时间: {fault_config.start_time}s, 持续: {fault_config.duration}s")

    # 创建测试套件
    print_subsection("5.4 创建HIL测试套件")
    hil_suite = HILTestSuite("HIL_HYDRAULIC_SUITE", "水利系统HIL测试套件")
    hil_suite.set_environment(hil_env)
    for tc in hil_test_cases[:1]:  # 只运行1个用例演示
        hil_suite.add_test_case(tc)
        print(f"  添加测试: {tc.test_id} - {tc.name}")

    return hil_suite


def demo_hitl_testing():
    """演示6: HITL人在环测试"""
    print_section("6. HITL人在环测试演示")

    # 创建HITL测试环境
    print_subsection("6.1 创建HITL测试环境")
    hitl_env = HITLTestEnvironment("HITL_ENV_001", "水利系统HITL测试环境")

    # 创建操作员界面
    operator_interface = OperatorInterface("OP_INTERFACE_001")
    operator_interface.add_control("valve_setpoint", "SLIDER", {
        'min': 0, 'max': 100, 'default': 0, 'unit': '%'
    })
    operator_interface.add_control("pump_start", "BUTTON", {
        'label': '启动泵', 'type': 'momentary'
    })
    hitl_env.add_operator_interface(operator_interface)
    print(f"  HITL环境: {hitl_env.name}")

    # 注册操作员
    print_subsection("6.2 注册操作员")
    hitl_env.register_operator("OP_001", OperatorRole.CONTROL_ROOM_OPERATOR)
    print(f"  操作员: OP_001 (控制室操作员)")

    # 加载场景
    print_subsection("6.3 加载测试场景")
    scenarios = create_hydraulic_hitl_scenarios()
    print(f"  加载 {len(scenarios)} 个HITL场景")
    for scenario in scenarios:
        print(f"    {scenario.scenario_id}: {scenario.name} ({scenario.category})")

    # 工作负荷评估
    print_subsection("6.4 工作负荷评估 (NASA-TLX)")
    workload_assessment = WorkloadAssessment()
    hf_model = HumanFactorsModel("OP_001")
    hf_model.metrics.mental_demand = 60
    hf_model.metrics.temporal_demand = 70
    hf_model.metrics.effort = 55
    hf_model.metrics.frustration = 30

    assessment = workload_assessment.assess(hf_model.metrics)
    print(f"  综合工作负荷: {assessment['overall_score']:.1f}")
    print(f"  负荷等级: {assessment['level']}")
    if assessment['recommendations']:
        print("  建议:")
        for rec in assessment['recommendations']:
            print(f"    - {rec}")

    # 情景意识评估
    print_subsection("6.5 情景意识评估")
    sa_assessment = SituationAwareness()
    from src.mbd_framework.hitl_framework import SituationAwarenessLevel
    sa_assessment.add_probe(
        SituationAwarenessLevel.PERCEPTION,
        "当前系统压力是多少?",
        "2.5 MPa"
    )
    sa_assessment.add_probe(
        SituationAwarenessLevel.COMPREHENSION,
        "压力升高的原因是什么?",
        "下游阀门关闭"
    )
    print(f"  SA探测题数: {len(sa_assessment.probes)}")

    # 决策支持
    print_subsection("6.6 决策支持系统")
    decision_support = DecisionSupport()
    decision_support.add_rule(
        "RULE_HIGH_PRESSURE",
        conditions={'pressure': {'min': 3.0}},
        actions=["打开泄压阀", "降低泵转速"],
        priority=1
    )
    decision_support.add_rule(
        "RULE_LOW_FLOW",
        conditions={'flow': {'max': 10.0}},
        actions=["检查阀门开度", "增加泵转速"],
        priority=2
    )
    print(f"  决策规则数: {len(decision_support.rules)}")

    # 测试状态评估
    recommendations = decision_support.evaluate({
        'pressure': 3.5,
        'flow': 8.0
    })
    if recommendations:
        print("  当前建议:")
        for rec in recommendations:
            print(f"    [{rec['priority']}] {', '.join(rec['actions'])}")

    return hitl_env


def demo_integration_validation():
    """演示7: 集成测试和验证"""
    print_section("7. 集成测试和验证演示")

    # 创建集成测试套件
    print_subsection("7.1 创建集成测试套件")
    int_suite = IntegrationTestSuite("INT_HYDRAULIC", "水利系统集成测试套件")

    # 添加测试用例
    test_cases = create_hydraulic_integration_tests()
    for tc in test_cases:
        int_suite.add_test_case(tc)
        print(f"  添加测试: {tc.test_id} - {tc.name}")

    # 系统验证
    print_subsection("7.2 系统验证配置")
    sys_validation = SystemValidation("SYS_HYDRAULIC", "水利系统")
    sys_validation.add_validation_item(
        "VAL_001",
        "阀门响应时间验证",
        "TEST",
        ["响应时间<50ms", "无超调"]
    )
    sys_validation.add_validation_item(
        "VAL_002",
        "水锤防护验证",
        "TEST",
        ["压力峰值<150%额定值"]
    )
    sys_validation.add_requirement(
        "REQ_VALVE_001",
        "阀门快速响应",
        ["VAL_001"]
    )
    sys_validation.register_test_suite(int_suite)
    print(f"  验证项数: {len(sys_validation.validation_items)}")

    # 覆盖分析
    print_subsection("7.3 覆盖分析")
    coverage = CoverageAnalyzer()
    from src.mbd_framework.integration_validation import CoverageItem
    coverage.add_item(CoverageItem("REQ_001", "REQUIREMENT", "阀门响应需求"))
    coverage.add_item(CoverageItem("REQ_002", "REQUIREMENT", "水锤防护需求"))
    coverage.add_item(CoverageItem("REQ_003", "REQUIREMENT", "泵站控制需求"))
    coverage.record_coverage("TEST_001", ["REQ_001", "REQ_002"])

    coverage_report = coverage.generate_report()
    print(f"  总覆盖率: {coverage_report['summary']['overall_percentage']:.1f}%")
    print(f"  未覆盖项: {len(coverage_report['uncovered'])}")

    # 需求追溯
    print_subsection("7.4 需求追溯")
    req_coverage = RequirementCoverage()
    req_coverage.add_requirement("REQ_VALVE_001", "阀门响应时间<50ms", "HIGH", True)
    req_coverage.add_requirement("REQ_VALVE_002", "水锤防护", "HIGH", True)
    req_coverage.add_requirement("REQ_PUMP_001", "泵启动平滑", "MEDIUM", False)

    req_coverage.link_test("REQ_VALVE_001", "SIL_VALVE_001")
    req_coverage.link_test("REQ_VALVE_002", "INT_VALVE_PIPE_001")

    matrix = req_coverage.get_traceability_matrix()
    print("  追溯矩阵:")
    for req_id, info in matrix.items():
        tests = info['linked_tests']
        print(f"    {req_id}: {len(tests)} 个测试关联, 状态: {info['status']}")

    # 测试报告生成
    print_subsection("7.5 测试报告生成")
    report_gen = TestReportGenerator("水利枢纽智能控制系统")
    report_gen.set_coverage_data(coverage_report)

    summary = report_gen.generate_summary_report()
    print(f"  项目: {summary['project']}")
    print(f"  生成时间: {summary['generated_at']}")
    print(f"  整体状态: {summary['overall_status']}")

    return int_suite, sys_validation


def main():
    """主函数 - 运行所有演示"""
    print("\n" + "=" * 60)
    print("  MBD Framework 综合演示")
    print("  Model-Based Design Framework Comprehensive Demo")
    print("=" * 60)
    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 运行各演示
    workflow, valve_model = demo_mbd_workflow()
    hydraulic_odd = demo_odd_framework()
    safety_monitor, degradation_sm = demo_functional_safety()
    sil_suite = demo_sil_testing()
    hil_suite = demo_hil_testing()
    hitl_env = demo_hitl_testing()
    int_suite, sys_validation = demo_integration_validation()

    # 总结
    print_section("演示总结")
    print("""
本演示展示了MBD框架的完整功能:

1. MBD工作流程 - V模型开发流程、需求追溯、模型验证
2. ODD运行设计域 - 运行边界定义、实时监控、违规处理
3. 功能安全 - ASIL等级、降级策略、故障处理
4. SIL测试 - 软件在环仿真、自动化测试
5. HIL测试 - 硬件接口、故障注入、同步控制
6. HITL测试 - 人因评估、工作负荷、情景意识
7. 集成验证 - 覆盖分析、需求追溯、报告生成

框架支持的应用场景:
- 水利枢纽智能控制系统
- 多能互补系统 (水风光储)
- 工业控制系统

更多信息请参考 src/mbd_framework/ 目录下的各模块文档。
""")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
