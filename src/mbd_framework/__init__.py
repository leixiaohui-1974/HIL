# -*- coding: utf-8 -*-
"""
MBD Framework - 模型驱动设计框架
Model-Based Design Framework for HIL Testing Platform

包含:
- MBD核心框架和V模型开发流程
- ODD运行设计域定义
- 功能安全和降级策略
- SIL/HIL/HITL测试体系
"""

from .mbd_core import (
    MBDModel,
    MBDWorkflow,
    VModelPhase,
    ModelArtifact,
    RequirementTrace,
    DesignSpecification,
    CodeGenerator,
    ModelValidator
)

from .odd_framework import (
    ODDDefinition,
    ODDBoundary,
    OperatingCondition,
    ODDMonitor,
    ODDValidator,
    ODDViolationHandler
)

from .functional_safety import (
    SafetyLevel,
    ASILLevel,
    SafetyGoal,
    SafetyRequirement,
    DegradationStrategy,
    DegradationStateMachine,
    FaultHandler,
    SafetyMonitor
)

from .sil_framework import (
    SILTestEnvironment,
    SILTestCase,
    SILTestSuite,
    ModelInLoopTest,
    SoftwareInLoopTest,
    SILCoverage
)

from .hil_enhanced import (
    HILTestEnvironment,
    HILTestCase,
    HILTestSuite,
    HardwareInterface,
    SignalConditioner,
    FaultInjector,
    HILSynchronizer
)

from .hitl_framework import (
    HITLTestEnvironment,
    HITLScenario,
    OperatorInterface,
    HumanFactorsModel,
    WorkloadAssessment,
    SituationAwareness,
    DecisionSupport,
    TrainingScenario
)

from .integration_validation import (
    IntegrationTestSuite,
    SystemValidation,
    RegressionTestManager,
    CoverageAnalyzer,
    RequirementCoverage,
    TestReportGenerator
)

# 水利控制器MBD模型
from .hydraulic_mbd import (
    ValveMBDModel,
    PumpMBDModel,
    GateMBDModel,
    create_valve_odd,
    create_pump_odd,
    create_gate_odd,
    create_valve_safety_goals,
    create_valve_degradation_strategies,
    create_hydraulic_mbd_workflow,
    create_hydraulic_safety_monitor
)

# 多能互补系统MBD模型
from .multi_energy_mbd import (
    SupercapacitorMBDModel,
    BatteryMBDModel,
    PSHMBDModel,
    HierarchicalControllerMBDModel,
    create_multi_energy_system_odd,
    create_multi_energy_safety_goals,
    create_multi_energy_degradation_strategies
)

__version__ = '1.1.0'
__all__ = [
    # MBD Core
    'MBDModel', 'MBDWorkflow', 'VModelPhase', 'ModelArtifact',
    'RequirementTrace', 'DesignSpecification', 'CodeGenerator', 'ModelValidator',

    # ODD Framework
    'ODDDefinition', 'ODDBoundary', 'OperatingCondition',
    'ODDMonitor', 'ODDValidator', 'ODDViolationHandler',

    # Functional Safety
    'SafetyLevel', 'ASILLevel', 'SafetyGoal', 'SafetyRequirement',
    'DegradationStrategy', 'DegradationStateMachine', 'FaultHandler', 'SafetyMonitor',

    # SIL Framework
    'SILTestEnvironment', 'SILTestCase', 'SILTestSuite',
    'ModelInLoopTest', 'SoftwareInLoopTest', 'SILCoverage',

    # HIL Enhanced
    'HILTestEnvironment', 'HILTestCase', 'HILTestSuite',
    'HardwareInterface', 'SignalConditioner', 'FaultInjector', 'HILSynchronizer',

    # HITL Framework
    'HITLTestEnvironment', 'HITLScenario', 'OperatorInterface',
    'HumanFactorsModel', 'WorkloadAssessment', 'SituationAwareness',
    'DecisionSupport', 'TrainingScenario',

    # Integration & Validation
    'IntegrationTestSuite', 'SystemValidation', 'RegressionTestManager',
    'CoverageAnalyzer', 'RequirementCoverage', 'TestReportGenerator',

    # Hydraulic Controllers MBD
    'ValveMBDModel', 'PumpMBDModel', 'GateMBDModel',
    'create_valve_odd', 'create_pump_odd', 'create_gate_odd',
    'create_valve_safety_goals', 'create_valve_degradation_strategies',
    'create_hydraulic_mbd_workflow', 'create_hydraulic_safety_monitor',

    # Multi-Energy System MBD
    'SupercapacitorMBDModel', 'BatteryMBDModel', 'PSHMBDModel',
    'HierarchicalControllerMBDModel',
    'create_multi_energy_system_odd', 'create_multi_energy_safety_goals',
    'create_multi_energy_degradation_strategies'
]
