# -*- coding: utf-8 -*-
"""
水-风-光-储-抽(Hydro-Wind-Solar-HESS-PSH)多能互补系统
Multi-Energy Complementary System for Hydro-Wind-Solar-HESS-PSH

本模块实现了一个完整的多能互补系统联合控制仿真框架，包括:
- 波动电源: 风电(WT)和光伏(PV)
- 常规调峰: 梯级水电站(Conventional Hydro)
- 抽水蓄能: PSH(Pumped Storage Hydropower)
- 混合储能: HESS(超级电容SC + 锂电池BESS)

控制架构采用分布式分层控制:
- 第一层(毫秒级): 超级电容下垂控制
- 第二层(秒级): 锂电池低通滤波控制
- 第三层(分钟级): PSH与常规水电MPC协同控制

Author: HIL Multi-Energy System
Version: 1.0.0
"""

from .energy_models import (
    WindTurbineModel,
    PhotovoltaicModel,
    SupercapacitorModel,
    BatteryStorageModel,
    PumpedStorageModel,
    ConventionalHydroModel,
    GridModel
)

from .psh_state_machine import (
    PSHOperatingMode,
    PSHStateEvent,
    PSHStateMachine,
    PSHConstraints
)

from .hierarchical_control import (
    Layer1_SCDroopController,
    Layer2_BESSFilterController,
    Layer3_MPCCoordinator,
    HierarchicalEnergyController
)

from .power_allocation import (
    PowerAllocationAlgorithm,
    ResponseChainDecoupler,
    FrequencyRegulator
)

from .simulation import (
    MultiEnergySimulator,
    SimulationConfig,
    SimulationResult
)

from .visualization import (
    MultiEnergyVisualizer,
    generate_daily_report
)

from .mpc_optimizer import (
    MPCOptimizer,
    MPCOptimizerConfig,
    MPCState,
    MPCPrediction,
    MPCSolution,
    DynamicProgrammingSolver,
    EconomicDispatcher
)

__all__ = [
    # 能源模型
    'WindTurbineModel',
    'PhotovoltaicModel',
    'SupercapacitorModel',
    'BatteryStorageModel',
    'PumpedStorageModel',
    'ConventionalHydroModel',
    'GridModel',
    # PSH状态机
    'PSHOperatingMode',
    'PSHStateEvent',
    'PSHStateMachine',
    'PSHConstraints',
    # 分层控制
    'Layer1_SCDroopController',
    'Layer2_BESSFilterController',
    'Layer3_MPCCoordinator',
    'HierarchicalEnergyController',
    # 功率分配
    'PowerAllocationAlgorithm',
    'ResponseChainDecoupler',
    'FrequencyRegulator',
    # 仿真
    'MultiEnergySimulator',
    'SimulationConfig',
    'SimulationResult',
    # 可视化
    'MultiEnergyVisualizer',
    'generate_daily_report',
    # MPC优化器
    'MPCOptimizer',
    'MPCOptimizerConfig',
    'MPCState',
    'MPCPrediction',
    'MPCSolution',
    'DynamicProgrammingSolver',
    'EconomicDispatcher'
]
