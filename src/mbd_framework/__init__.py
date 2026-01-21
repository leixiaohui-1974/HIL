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

__version__ = '1.0.0'
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
    'CoverageAnalyzer', 'RequirementCoverage', 'TestReportGenerator'
]
