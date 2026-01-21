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

# 水网类型MBD模型 - 差异化ODD设计
from .water_network_mbd import (
    # 灌区水网 - 长期公平性与连续调配
    IrrigationNetworkMBDModel,
    IrrigationFairnessLevel,
    create_irrigation_network_odd,
    create_irrigation_degradation_strategies,
    # 调水工程 - 长时滞与多工程联动
    WaterTransferMBDModel,
    create_water_transfer_odd,
    create_water_transfer_degradation_strategies,
    # 城市供水 - 压力稳定性与服务连续性
    UrbanWaterSupplyMBDModel,
    PressureZone,
    create_urban_water_supply_odd,
    create_urban_supply_degradation_strategies,
    # 防洪调度 - 不确定性管理与越界控制
    FloodControlMBDModel,
    FloodRiskLevel,
    DecisionAuthority,
    create_flood_control_odd,
    create_flood_control_degradation_strategies,
)

__version__ = '1.2.0'
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
    'create_multi_energy_degradation_strategies',

    # Water Network Types MBD - 差异化ODD设计
    # 灌区水网
    'IrrigationNetworkMBDModel', 'IrrigationFairnessLevel',
    'create_irrigation_network_odd', 'create_irrigation_degradation_strategies',
    # 调水工程
    'WaterTransferMBDModel',
    'create_water_transfer_odd', 'create_water_transfer_degradation_strategies',
    # 城市供水
    'UrbanWaterSupplyMBDModel', 'PressureZone',
    'create_urban_water_supply_odd', 'create_urban_supply_degradation_strategies',
    # 防洪调度
    'FloodControlMBDModel', 'FloodRiskLevel', 'DecisionAuthority',
    'create_flood_control_odd', 'create_flood_control_degradation_strategies',
]
