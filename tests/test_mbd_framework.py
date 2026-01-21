# -*- coding: utf-8 -*-
"""
MBD Framework 测试
Test cases for Model-Based Design Framework
"""

import sys
import os
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.mbd_framework.mbd_core import (
    MBDModel, MBDWorkflow, VModelPhase, ModelType,
    RequirementTrace, DesignSpecification, ModelArtifact,
    ModelValidator, CodeGenerator, VerificationStatus,
    create_default_validator
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
    SystemState, create_hydraulic_degradation_strategies
)
from src.mbd_framework.sil_framework import (
    SILTestEnvironment, SILTestCase, SILTestSuite,
    SimulationMode, TestResult, CoverageType,
    create_valve_sil_test_cases
)
from src.mbd_framework.hil_enhanced import (
    HILTestEnvironment, HILTestCase, HILTestSuite,
    HardwareInterface, SimulatedHardwareInterface, HardwareChannel,
    HardwareType, SignalType, FaultInjector, FaultInjectionConfig, FaultMode
)
from src.mbd_framework.hitl_framework import (
    HITLTestEnvironment, HITLScenario, OperatorInterface,
    HumanFactorsModel, WorkloadAssessment, SituationAwareness,
    SituationAwarenessLevel, WorkloadLevel, OperatorRole
)
from src.mbd_framework.integration_validation import (
    IntegrationTestSuite, IntegrationTestCase, SystemValidation,
    CoverageAnalyzer, RequirementCoverage, TestReportGenerator, TestLevel,
    CoverageItem, RequirementStatus
)


# 简单测试模型
class TestModel(MBDModel):
    """测试用简单模型"""

    def __init__(self):
        super().__init__("TEST_MODEL", "Test Model", ModelType.CONTROLLER)
        self._parameters = {'gain': 1.0}
        self.artifact.inputs = ['input1']
        self.artifact.outputs = ['output1']
        self.artifact.parameters = self._parameters
        self.artifact.requirements = ['REQ_001']

    def initialize(self):
        self._states = {'state1': 0.0}
        self._outputs = {'output1': 0.0}

    def update(self, dt: float):
        self._outputs['output1'] = self._inputs.get('input1', 0.0) * self._parameters['gain']

    def get_outputs(self):
        return self._outputs.copy()


class TestMBDCore(unittest.TestCase):
    """MBD核心模块测试"""

    def test_requirement_trace_creation(self):
        """测试需求追溯创建"""
        req = RequirementTrace(
            requirement_id="REQ_001",
            requirement_text="Test requirement",
            source="Test",
            priority="HIGH",
            safety_related=True
        )
        self.assertEqual(req.requirement_id, "REQ_001")
        self.assertTrue(req.safety_related)
        self.assertEqual(req.verification_status, VerificationStatus.NOT_VERIFIED)

    def test_requirement_trace_add_test_case(self):
        """测试添加测试用例到需求"""
        req = RequirementTrace(
            requirement_id="REQ_001",
            requirement_text="Test requirement",
            source="Test"
        )
        req.add_test_case("TC_001")
        req.add_test_case("TC_002")
        self.assertEqual(len(req.test_cases), 2)
        self.assertIn("TC_001", req.test_cases)

    def test_design_specification_creation(self):
        """测试设计规格创建"""
        spec = DesignSpecification(
            spec_id="SPEC_001",
            name="Test Spec",
            description="Test description",
            phase=VModelPhase.DETAILED_DESIGN,
            requirements=["REQ_001"]
        )
        self.assertEqual(spec.spec_id, "SPEC_001")
        self.assertEqual(spec.phase, VModelPhase.DETAILED_DESIGN)

    def test_mbd_workflow_creation(self):
        """测试MBD工作流创建"""
        workflow = MBDWorkflow("Test Project")
        self.assertEqual(workflow.project_name, "Test Project")
        self.assertEqual(workflow.current_phase, VModelPhase.REQUIREMENTS)

    def test_mbd_workflow_add_requirement(self):
        """测试添加需求到工作流"""
        workflow = MBDWorkflow("Test Project")
        req = RequirementTrace(
            requirement_id="REQ_001",
            requirement_text="Test requirement",
            source="Test"
        )
        workflow.add_requirement(req)
        self.assertIn("REQ_001", workflow.requirements)

    def test_mbd_model_basic_operation(self):
        """测试MBD模型基本操作"""
        model = TestModel()
        model.initialize()
        model.set_inputs({'input1': 5.0})
        output = model.step(dt=0.01)
        self.assertEqual(output['output1'], 5.0)

    def test_model_validator(self):
        """测试模型验证器"""
        model = TestModel()
        model.initialize()
        validator = create_default_validator()
        result = validator.validate_model(model)
        self.assertTrue(result['overall_status'])


class TestODDFramework(unittest.TestCase):
    """ODD框架测试"""

    def test_operating_condition_creation(self):
        """测试运行条件创建"""
        condition = OperatingCondition(
            condition_id="COND_001",
            name="Test Condition",
            description="Test",
            category=ODDCategory.OPERATIONAL,
            condition_type=ConditionType.DYNAMIC,
            parameter_name="pressure",
            unit="MPa",
            min_value=0.0,
            max_value=10.0
        )
        self.assertEqual(condition.condition_id, "COND_001")
        self.assertEqual(condition.min_value, 0.0)
        self.assertEqual(condition.max_value, 10.0)

    def test_operating_condition_check_value(self):
        """测试运行条件值检查"""
        condition = OperatingCondition(
            condition_id="COND_001",
            name="Pressure",
            description="System pressure",
            category=ODDCategory.OPERATIONAL,
            condition_type=ConditionType.DYNAMIC,
            parameter_name="pressure",
            min_value=0.0,
            max_value=10.0
        )
        passed, _ = condition.check_value(5.0)
        self.assertTrue(passed)
        passed, _ = condition.check_value(15.0)
        self.assertFalse(passed)
        passed, _ = condition.check_value(-1.0)
        self.assertFalse(passed)

    def test_odd_definition_creation(self):
        """测试ODD定义创建"""
        odd = ODDDefinition("ODD_001", "Test ODD", "Test description")
        self.assertEqual(odd.odd_id, "ODD_001")
        self.assertEqual(len(odd.conditions), 0)

    def test_odd_add_condition(self):
        """测试添加运行条件到ODD"""
        odd = ODDDefinition("ODD_001", "Test ODD")
        condition = OperatingCondition(
            condition_id="COND_001",
            name="Pressure",
            description="System pressure",
            category=ODDCategory.OPERATIONAL,
            condition_type=ConditionType.DYNAMIC,
            parameter_name="pressure",
            min_value=0.0,
            max_value=10.0
        )
        odd.add_condition(condition)
        self.assertEqual(len(odd.conditions), 1)

    def test_hydraulic_system_odd_template(self):
        """测试水利系统ODD模板"""
        odd = create_hydraulic_system_odd()
        self.assertIsNotNone(odd)
        self.assertTrue(len(odd.conditions) > 0)
        self.assertTrue(len(odd.boundaries) > 0)

    def test_multi_energy_odd_template(self):
        """测试多能互补系统ODD模板"""
        odd = create_multi_energy_odd()
        self.assertIsNotNone(odd)
        self.assertIn("GRID_FREQ", odd.conditions)

    def test_odd_validate_operating_point(self):
        """测试ODD运行点验证"""
        odd = create_hydraulic_system_odd()
        # 正常运行点
        result = odd.validate_operating_point({
            'system_pressure': 2.5,
            'flow_rate': 50.0
        })
        self.assertTrue(result['in_odd'])

    def test_odd_monitor(self):
        """测试ODD监控器"""
        odd = create_hydraulic_system_odd()
        monitor = ODDMonitor(odd)
        monitor.start_monitoring()
        self.assertTrue(monitor.monitoring)
        result = monitor.update({'system_pressure': 2.5, 'flow_rate': 50.0})
        self.assertIn('in_odd', result)


class TestFunctionalSafety(unittest.TestCase):
    """功能安全模块测试"""

    def test_safety_goal_creation(self):
        """测试安全目标创建"""
        goal = SafetyGoal(
            goal_id="SG_001",
            name="Test Safety Goal",
            description="Test",
            asil_level=ASILLevel.ASIL_B,
            sil_level=SafetyLevel.SIL_2
        )
        self.assertEqual(goal.goal_id, "SG_001")
        self.assertEqual(goal.asil_level, ASILLevel.ASIL_B)

    def test_degradation_state_machine_creation(self):
        """测试降级状态机创建"""
        sm = DegradationStateMachine("TEST_SYSTEM")
        self.assertEqual(sm.current_level, DegradationLevel.NORMAL)
        self.assertEqual(sm.current_state, SystemState.INITIALIZING)

    def test_degradation_state_machine_transition(self):
        """测试降级状态机转换"""
        sm = DegradationStateMachine("TEST_SYSTEM")
        # 正常 -> 一级降级
        result = sm.transition_to(DegradationLevel.DEGRADED_L1, "Test transition")
        self.assertTrue(result)
        self.assertEqual(sm.current_level, DegradationLevel.DEGRADED_L1)

    def test_degradation_state_machine_invalid_transition(self):
        """测试无效的降级转换"""
        sm = DegradationStateMachine("TEST_SYSTEM")
        # 不能直接从紧急停机恢复到正常
        sm.current_level = DegradationLevel.EMERGENCY_STOP
        result = sm.transition_to(DegradationLevel.NORMAL, "Invalid")
        self.assertFalse(result)

    def test_fault_report_and_degradation(self):
        """测试故障报告和降级"""
        sm = DegradationStateMachine("TEST_SYSTEM")
        fault = Fault(
            fault_id="FAULT_001",
            name="Test Fault",
            description="Test fault",
            fault_type=FaultType.SENSOR_FAULT,
            category=FaultCategory.TRANSIENT,
            severity=FaultSeverity.MARGINAL
        )
        sm.report_fault(fault)
        self.assertIn("FAULT_001", sm.active_faults)
        self.assertNotEqual(sm.current_level, DegradationLevel.NORMAL)

    def test_fault_clear(self):
        """测试故障清除"""
        sm = DegradationStateMachine("TEST_SYSTEM")
        fault = Fault(
            fault_id="FAULT_001",
            name="Test Fault",
            description="Test fault",
            fault_type=FaultType.SENSOR_FAULT,
            category=FaultCategory.TRANSIENT,
            severity=FaultSeverity.NEGLIGIBLE
        )
        sm.report_fault(fault)
        result = sm.clear_fault("FAULT_001")
        self.assertTrue(result)
        self.assertEqual(len(sm.active_faults), 0)

    def test_hydraulic_degradation_strategies(self):
        """测试水利系统降级策略"""
        strategies = create_hydraulic_degradation_strategies()
        self.assertTrue(len(strategies) > 0)


class TestSILFramework(unittest.TestCase):
    """SIL测试框架测试"""

    def test_sil_test_environment_creation(self):
        """测试SIL测试环境创建"""
        env = SILTestEnvironment("SIL_ENV_001", "Test Environment")
        self.assertEqual(env.env_id, "SIL_ENV_001")
        self.assertFalse(env.initialized)

    def test_sil_test_environment_initialization(self):
        """测试SIL测试环境初始化"""
        env = SILTestEnvironment("SIL_ENV_001", "Test Environment")
        env.initialize()
        self.assertTrue(env.initialized)
        self.assertEqual(env.current_time, 0.0)

    def test_sil_test_case_creation(self):
        """测试SIL测试用例创建"""
        tc = SILTestCase(
            test_id="SIL_TC_001",
            name="Test Case",
            description="Test",
            simulation_time=10.0,
            time_step=0.001
        )
        self.assertEqual(tc.test_id, "SIL_TC_001")
        self.assertEqual(tc.simulation_time, 10.0)
        self.assertEqual(tc.result, TestResult.NOT_RUN)

    def test_sil_test_suite_creation(self):
        """测试SIL测试套件创建"""
        suite = SILTestSuite("SIL_SUITE_001", "Test Suite")
        self.assertEqual(suite.suite_id, "SIL_SUITE_001")
        self.assertEqual(len(suite.test_cases), 0)

    def test_sil_test_suite_add_test_case(self):
        """测试添加测试用例到套件"""
        suite = SILTestSuite("SIL_SUITE_001", "Test Suite")
        tc = SILTestCase(
            test_id="SIL_TC_001",
            name="Test Case",
            description="Test"
        )
        suite.add_test_case(tc)
        self.assertEqual(len(suite.test_cases), 1)

    def test_valve_sil_test_cases(self):
        """测试阀门SIL测试用例模板"""
        test_cases = create_valve_sil_test_cases()
        self.assertTrue(len(test_cases) > 0)


class TestHILFramework(unittest.TestCase):
    """HIL测试框架测试"""

    def test_hardware_channel_creation(self):
        """测试硬件通道创建"""
        channel = HardwareChannel(
            channel_id="CH_001",
            name="Test Channel",
            hardware_type=HardwareType.ANALOG_INPUT,
            signal_type=SignalType.VOLTAGE,
            min_value=0.0,
            max_value=10.0
        )
        self.assertEqual(channel.channel_id, "CH_001")
        self.assertEqual(channel.hardware_type, HardwareType.ANALOG_INPUT)

    def test_simulated_hardware_interface(self):
        """测试模拟硬件接口"""
        interface = SimulatedHardwareInterface("IF_001", "Test Interface")
        channel = HardwareChannel(
            channel_id="CH_001",
            name="Test Channel",
            hardware_type=HardwareType.ANALOG_INPUT,
            signal_type=SignalType.VOLTAGE
        )
        interface.add_channel(channel)
        self.assertTrue(interface.connect())
        self.assertTrue(interface.connected)

    def test_fault_injector(self):
        """测试故障注入器"""
        injector = FaultInjector()
        config = FaultInjectionConfig(
            fault_id="FI_001",
            channel_id="CH_001",
            fault_mode=FaultMode.STUCK_HIGH,
            parameters={'high_value': 10.0}
        )
        injector.start()
        injector.add_fault(config)
        self.assertIn("FI_001", injector.active_faults)

    def test_fault_injector_apply_fault(self):
        """测试故障注入应用"""
        injector = FaultInjector()
        config = FaultInjectionConfig(
            fault_id="FI_001",
            channel_id="CH_001",
            fault_mode=FaultMode.OFFSET,
            start_time=0.0,
            parameters={'value': 1.0}
        )
        injector.start()
        injector.add_fault(config)
        injector.update_time(1.0)
        result = injector.apply_fault("CH_001", 5.0)
        self.assertEqual(result, 6.0)

    def test_hil_test_environment_creation(self):
        """测试HIL测试环境创建"""
        env = HILTestEnvironment("HIL_ENV_001", "Test Environment")
        self.assertEqual(env.env_id, "HIL_ENV_001")
        self.assertFalse(env.initialized)


class TestHITLFramework(unittest.TestCase):
    """HITL测试框架测试"""

    def test_human_factors_model_creation(self):
        """测试人因模型创建"""
        hf_model = HumanFactorsModel("OP_001")
        self.assertEqual(hf_model.operator_id, "OP_001")
        self.assertEqual(hf_model.current_workload, WorkloadLevel.OPTIMAL)

    def test_workload_assessment(self):
        """测试工作负荷评估"""
        hf_model = HumanFactorsModel("OP_001")
        hf_model.metrics.mental_demand = 70
        hf_model.metrics.temporal_demand = 60
        hf_model.metrics.effort = 50

        assessment = WorkloadAssessment()
        result = assessment.assess(hf_model.metrics)
        self.assertIn('overall_score', result)
        self.assertIn('level', result)

    def test_situation_awareness(self):
        """测试情景意识评估"""
        sa = SituationAwareness()
        sa.add_probe(
            SituationAwarenessLevel.PERCEPTION,
            "Test question",
            "Correct answer"
        )
        self.assertEqual(len(sa.probes), 1)

        result = sa.evaluate_response(sa.probes[0]['id'], "Correct answer", 5.0)
        self.assertTrue(result['correct'])

    def test_operator_interface(self):
        """测试操作员界面"""
        interface = OperatorInterface("OP_IF_001")
        interface.add_control("CTRL_001", "SLIDER", {'min': 0, 'max': 100})
        self.assertIn("CTRL_001", interface.controls)

    def test_hitl_scenario_creation(self):
        """测试HITL场景创建"""
        scenario = HITLScenario(
            scenario_id="HITL_001",
            name="Test Scenario",
            description="Test",
            category="NORMAL",
            duration=3600.0
        )
        self.assertEqual(scenario.scenario_id, "HITL_001")
        self.assertEqual(scenario.duration, 3600.0)


class TestIntegrationValidation(unittest.TestCase):
    """集成验证模块测试"""

    def test_integration_test_case_creation(self):
        """测试集成测试用例创建"""
        tc = IntegrationTestCase(
            test_id="INT_TC_001",
            name="Test Case",
            description="Test",
            level=TestLevel.INTEGRATION
        )
        self.assertEqual(tc.test_id, "INT_TC_001")
        self.assertEqual(tc.level, TestLevel.INTEGRATION)

    def test_integration_test_suite_creation(self):
        """测试集成测试套件创建"""
        suite = IntegrationTestSuite("INT_SUITE_001", "Test Suite")
        self.assertEqual(suite.suite_id, "INT_SUITE_001")

    def test_coverage_analyzer(self):
        """测试覆盖分析器"""
        coverage = CoverageAnalyzer()
        coverage.add_item(CoverageItem("REQ_001", "REQUIREMENT", "Test req 1"))
        coverage.add_item(CoverageItem("REQ_002", "REQUIREMENT", "Test req 2"))
        coverage.record_coverage("TC_001", ["REQ_001"])

        report = coverage.generate_report()
        self.assertEqual(report['summary']['total_items'], 2)
        self.assertEqual(report['summary']['covered_items'], 1)

    def test_requirement_coverage(self):
        """测试需求覆盖追溯"""
        req_cov = RequirementCoverage()
        req_cov.add_requirement("REQ_001", "Test requirement", "HIGH", True)
        req_cov.link_test("REQ_001", "TC_001")

        summary = req_cov.get_coverage_summary()
        self.assertEqual(summary['total_requirements'], 1)

    def test_test_report_generator(self):
        """测试报告生成器"""
        report_gen = TestReportGenerator("Test Project")
        report = report_gen.generate_summary_report()
        self.assertEqual(report['project'], "Test Project")
        self.assertIn('overall_status', report)


if __name__ == '__main__':
    unittest.main(verbosity=2)
