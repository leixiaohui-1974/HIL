# -*- coding: utf-8 -*-
"""
水网类型MBD模型
Water Network Type MBD Models

针对不同类型水网的ODD差异化设计:
1. 灌区水网 - 长期公平性与连续调配能力
2. 调水工程 - 长时滞与多工程联动
3. 城市供水 - 压力稳定性与服务连续性
4. 防洪调度 - 不确定性管理与越界控制
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import math

from .mbd_core import MBDModel, ModelType, ModelArtifact
from .odd_framework import (
    ODDDefinition, ODDBoundary, OperatingCondition,
    ODDCategory, ConditionType, BoundaryType, ViolationSeverity
)
from .functional_safety import (
    SafetyLevel, ASILLevel, SafetyGoal, SafetyRequirement,
    DegradationStrategy, DegradationLevel
)


# ============================================================================
# 1. 灌区水网模型 - 以长期公平性与连续调配能力为核心
# ============================================================================

class IrrigationFairnessLevel(Enum):
    """灌溉公平性等级"""
    EXCELLENT = "excellent"     # 偏差<5%
    GOOD = "good"               # 偏差5-10%
    ACCEPTABLE = "acceptable"   # 偏差10-15%
    POOR = "poor"               # 偏差>15%


class IrrigationNetworkMBDModel(MBDModel):
    """
    灌区水网MBD模型 - 最简案例: 单干渠-三分水口

    核心关注:
    - 来水年景的不确定性 (丰/平/枯水年)
    - 作物需水预测误差
    - 渠道输配水损失变化
    - 分水口执行一致性 (公平性)
    """

    def __init__(self, model_id: str = "IRRIGATION_MBD_001"):
        super().__init__(model_id, "灌区水网控制模型", ModelType.CONTROLLER)

        self._parameters = {
            # 渠道参数
            'main_canal_capacity': 10.0,     # 干渠设计流量 (m³/s)
            'canal_loss_rate': 0.15,          # 渠道输水损失率 (15%)
            'num_outlets': 3,                 # 分水口数量

            # 分水口设计流量配比 (总和=1.0)
            'outlet_ratios': [0.4, 0.35, 0.25],  # 各分水口设计配比

            # 公平性参数
            'fairness_tolerance': 0.10,       # 公平性容差 (10%)
            'min_flow_ratio': 0.3,            # 最小供水保证率

            # 时间参数
            'allocation_period': 86400.0,     # 配水周期 (秒, 1天)
            'adjustment_interval': 3600.0,    # 调整间隔 (秒, 1小时)
        }

        self.artifact.inputs = [
            'inflow',           # 干渠来水量 (m³/s)
            'crop_demands',     # 各分水口作物需水 [list]
            'water_year_type',  # 来水年景 (丰/平/枯)
        ]

        self.artifact.outputs = [
            'outlet_flows',     # 各分水口实际分配流量 [list]
            'fairness_index',   # 公平性指数 (0-1)
            'supply_ratio',     # 总供水保证率
            'loss_actual',      # 实际输水损失
        ]

        self.artifact.requirements = [
            'REQ_IRR_001',  # 长期公平性偏差<10%
            'REQ_IRR_002',  # 最小供水保证率>30%
            'REQ_IRR_003',  # 连续调配能力
        ]

    def initialize(self):
        self._inputs = {}
        self._states = {
            'cumulative_allocations': [0.0] * 3,  # 累计分配量
            'cumulative_demands': [0.0] * 3,      # 累计需求量
            'current_period': 0,
            'loss_history': [],
        }

        self._outputs = {
            'outlet_flows': [0.0, 0.0, 0.0],
            'fairness_index': 1.0,
            'supply_ratio': 1.0,
            'loss_actual': self._parameters['canal_loss_rate'],
        }

    def update(self, dt: float):
        # 获取输入
        inflow = self._inputs.get('inflow', self._parameters['main_canal_capacity'])
        crop_demands = self._inputs.get('crop_demands', [1.0, 0.875, 0.625])  # 默认按配比
        water_year = self._inputs.get('water_year_type', 'normal')

        # 根据年景调整损失率
        loss_rate = self._adjust_loss_rate(water_year)
        available_water = inflow * (1 - loss_rate)

        # 计算各分水口分配
        total_demand = sum(crop_demands)
        outlet_flows = []

        if total_demand > 0 and available_water > 0:
            # 按比例公平分配
            supply_ratio = min(1.0, available_water / total_demand)
            for i, demand in enumerate(crop_demands):
                allocated = demand * supply_ratio
                outlet_flows.append(allocated)
                # 累计统计
                self._states['cumulative_allocations'][i] += allocated * dt
                self._states['cumulative_demands'][i] += demand * dt
        else:
            outlet_flows = [0.0] * len(crop_demands)
            supply_ratio = 0.0

        # 计算公平性指数 (Gini系数的补数)
        fairness_index = self._calculate_fairness()

        self._outputs = {
            'outlet_flows': outlet_flows,
            'fairness_index': fairness_index,
            'supply_ratio': supply_ratio,
            'loss_actual': loss_rate,
        }

    def _adjust_loss_rate(self, water_year: str) -> float:
        """根据年景调整损失率"""
        base_loss = self._parameters['canal_loss_rate']
        if water_year == 'wet':      # 丰水年
            return base_loss * 0.9   # 损失略低
        elif water_year == 'dry':    # 枯水年
            return base_loss * 1.2   # 损失偏高
        return base_loss             # 平水年

    def _calculate_fairness(self) -> float:
        """计算公平性指数 (基于累计配水与累计需求的比值一致性)"""
        ratios = []
        for i in range(len(self._states['cumulative_demands'])):
            demand = self._states['cumulative_demands'][i]
            if demand > 0:
                ratio = self._states['cumulative_allocations'][i] / demand
                ratios.append(ratio)

        if len(ratios) < 2:
            return 1.0

        # 公平性 = 1 - 变异系数
        mean_ratio = sum(ratios) / len(ratios)
        if mean_ratio == 0:
            return 1.0
        variance = sum((r - mean_ratio) ** 2 for r in ratios) / len(ratios)
        cv = math.sqrt(variance) / mean_ratio
        return max(0.0, 1.0 - cv)

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


# ============================================================================
# 2. 调水工程模型 - 以长时滞与多工程联动为核心
# ============================================================================

class WaterTransferMBDModel(MBDModel):
    """
    调水工程MBD模型 - 最简案例: 单水源-单渠道-双受水区

    核心关注:
    - 上下游时滞的不确定性
    - 多水源、多受水区的协调约束
    - 调度调整的最小时间尺度
    - 避免"调度修正来不及生效"的系统性风险
    """

    def __init__(self, model_id: str = "TRANSFER_MBD_001"):
        super().__init__(model_id, "调水工程控制模型", ModelType.CONTROLLER)

        self._parameters = {
            # 渠道参数
            'channel_length': 100.0,         # 渠道长度 (km)
            'flow_velocity': 2.0,            # 流速 (m/s)
            'max_flow': 50.0,                # 最大流量 (m³/s)

            # 时滞参数
            'base_delay': 14.0,              # 基础时滞 (小时) = 100km / 2m/s / 3600
            'delay_uncertainty': 0.2,         # 时滞不确定性 (±20%)

            # 受水区参数
            'num_recipients': 2,
            'recipient_demands': [20.0, 15.0],  # 各受水区需求 (m³/s)
            'recipient_distances': [60.0, 100.0],  # 距水源距离 (km)

            # 调度参数
            'min_adjustment_interval': 4.0,   # 最小调度间隔 (小时)
            'forecast_horizon': 24.0,         # 预报时域 (小时)
        }

        self.artifact.inputs = [
            'source_release',      # 水源下泄流量 (m³/s)
            'recipient_requests',  # 各受水区请求 [list]
            'forecast_inflow',     # 预报来水
        ]

        self.artifact.outputs = [
            'channel_flow',        # 渠道当前流量
            'arrival_times',       # 到达各受水区的预计时间 [list]
            'delivery_flows',      # 各受水区实际到达流量 [list]
            'coordination_status', # 协调状态
            'delay_margin',        # 时滞裕度
        ]

        self.artifact.requirements = [
            'REQ_TRF_001',  # 时滞预测误差<20%
            'REQ_TRF_002',  # 调度响应时间>时滞
            'REQ_TRF_003',  # 多受水区协调一致性
        ]

    def initialize(self):
        self._inputs = {}
        self._states = {
            'flow_history': [],           # 流量历史 (用于时滞模拟)
            'current_time': 0.0,
            'last_adjustment_time': 0.0,
            'pending_releases': [],       # 待到达的水量 [(time, flow, recipient)]
        }

        self._outputs = {
            'channel_flow': 0.0,
            'arrival_times': [0.0, 0.0],
            'delivery_flows': [0.0, 0.0],
            'coordination_status': 'IDLE',
            'delay_margin': 1.0,
        }

    def update(self, dt: float):
        # 获取输入
        source_release = self._inputs.get('source_release', 0.0)
        recipient_requests = self._inputs.get('recipient_requests',
                                               self._parameters['recipient_demands'])

        # 更新时间
        self._states['current_time'] += dt / 3600.0  # 转换为小时

        # 计算到达时间
        arrival_times = self._calculate_arrival_times(source_release)

        # 处理到达的水量
        delivery_flows = self._process_arrivals()

        # 添加新的释放到待处理队列
        if source_release > 0:
            for i, dist in enumerate(self._parameters['recipient_distances']):
                delay = self._calculate_delay(dist)
                arrival_time = self._states['current_time'] + delay
                self._states['pending_releases'].append({
                    'arrival_time': arrival_time,
                    'flow': source_release * (recipient_requests[i] / sum(recipient_requests)),
                    'recipient': i
                })

        # 计算协调状态
        coordination_status = self._evaluate_coordination(recipient_requests, delivery_flows)

        # 计算时滞裕度
        delay_margin = self._calculate_delay_margin()

        self._outputs = {
            'channel_flow': source_release,
            'arrival_times': arrival_times,
            'delivery_flows': delivery_flows,
            'coordination_status': coordination_status,
            'delay_margin': delay_margin,
        }

    def _calculate_delay(self, distance_km: float) -> float:
        """计算时滞 (小时)"""
        base_delay = distance_km * 1000 / self._parameters['flow_velocity'] / 3600
        return base_delay

    def _calculate_arrival_times(self, flow: float) -> List[float]:
        """计算预计到达时间"""
        times = []
        for dist in self._parameters['recipient_distances']:
            delay = self._calculate_delay(dist)
            times.append(self._states['current_time'] + delay)
        return times

    def _process_arrivals(self) -> List[float]:
        """处理到达的水量"""
        delivery_flows = [0.0] * self._parameters['num_recipients']
        current_time = self._states['current_time']

        # 处理已到达的释放
        remaining = []
        for release in self._states['pending_releases']:
            if release['arrival_time'] <= current_time:
                delivery_flows[release['recipient']] += release['flow']
            else:
                remaining.append(release)
        self._states['pending_releases'] = remaining

        return delivery_flows

    def _evaluate_coordination(self, requests: List[float], deliveries: List[float]) -> str:
        """评估协调状态"""
        if sum(deliveries) == 0:
            return 'IDLE'

        # 检查各受水区满足率
        satisfaction_rates = []
        for i in range(len(requests)):
            if requests[i] > 0:
                rate = deliveries[i] / requests[i]
                satisfaction_rates.append(rate)

        if not satisfaction_rates:
            return 'IDLE'

        avg_rate = sum(satisfaction_rates) / len(satisfaction_rates)
        variance = sum((r - avg_rate) ** 2 for r in satisfaction_rates) / len(satisfaction_rates)

        if avg_rate >= 0.9 and variance < 0.01:
            return 'COORDINATED'
        elif avg_rate >= 0.7:
            return 'PARTIAL'
        else:
            return 'UNCOORDINATED'

    def _calculate_delay_margin(self) -> float:
        """计算时滞裕度 (调度间隔/时滞)"""
        max_delay = max(self._calculate_delay(d)
                       for d in self._parameters['recipient_distances'])
        if max_delay == 0:
            return 1.0
        return self._parameters['min_adjustment_interval'] / max_delay

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


# ============================================================================
# 3. 城市供水模型 - 以压力稳定性与服务连续性为核心
# ============================================================================

class PressureZone(Enum):
    """压力区域状态"""
    LOW = "low"           # 压力过低
    NORMAL = "normal"     # 正常
    HIGH = "high"         # 压力过高
    CRITICAL = "critical" # 临界


class UrbanWaterSupplyMBDModel(MBDModel):
    """
    城市供水MBD模型 - 最简案例: 单泵站-单管网-变负荷

    核心关注:
    - 负荷波动范围 (日变化系数)
    - 允许的压力波动区间
    - 泵站切换与阀门调整的安全策略
    - 在绝大多数运行场景下保持服务质量一致性
    """

    def __init__(self, model_id: str = "URBAN_WS_MBD_001"):
        super().__init__(model_id, "城市供水控制模型", ModelType.CONTROLLER)

        self._parameters = {
            # 压力参数
            'target_pressure': 0.35,          # 目标压力 (MPa)
            'pressure_tolerance': 0.05,        # 压力容差 (±0.05 MPa)
            'min_pressure': 0.20,              # 最低服务压力
            'max_pressure': 0.50,              # 最高安全压力

            # 负荷参数
            'base_demand': 1000.0,             # 基础需求 (m³/h)
            'peak_factor': 1.5,                # 高峰系数
            'valley_factor': 0.6,              # 低谷系数

            # 泵站参数
            'num_pumps': 3,
            'pump_capacity': 500.0,            # 单泵容量 (m³/h)
            'pump_switch_delay': 30.0,         # 泵切换延迟 (秒)

            # 控制参数
            'pressure_kp': 0.5,                # 压力控制比例增益
            'pressure_ki': 0.1,                # 压力控制积分增益
        }

        self.artifact.inputs = [
            'demand',              # 当前需求 (m³/h)
            'outlet_pressure',     # 出口压力 (MPa)
            'time_of_day',         # 时刻 (0-24)
        ]

        self.artifact.outputs = [
            'pump_status',         # 各泵状态 [list of bool]
            'total_flow',          # 总供水量 (m³/h)
            'pressure',            # 管网压力 (MPa)
            'pressure_zone',       # 压力区域状态
            'service_continuity',  # 服务连续性 (0-1)
        ]

        self.artifact.requirements = [
            'REQ_UWS_001',  # 压力波动<±0.05 MPa
            'REQ_UWS_002',  # 服务连续性>99%
            'REQ_UWS_003',  # 泵站切换平稳
        ]

    def initialize(self):
        self._inputs = {}
        self._states = {
            'pump_running': [True, False, False],  # 初始1台运行
            'pump_switch_timer': [0.0, 0.0, 0.0],
            'pressure_integral': 0.0,
            'service_time': 0.0,
            'adequate_service_time': 0.0,
        }

        self._outputs = {
            'pump_status': [True, False, False],
            'total_flow': 500.0,
            'pressure': 0.35,
            'pressure_zone': 'NORMAL',
            'service_continuity': 1.0,
        }

    def update(self, dt: float):
        # 获取输入
        demand = self._inputs.get('demand', self._parameters['base_demand'])
        measured_pressure = self._inputs.get('outlet_pressure', 0.35)
        time_of_day = self._inputs.get('time_of_day', 12.0)

        # 预测需求 (基于日变化曲线)
        predicted_demand = self._predict_demand(time_of_day)
        actual_demand = demand if demand > 0 else predicted_demand

        # 压力控制
        pressure_error = self._parameters['target_pressure'] - measured_pressure
        self._states['pressure_integral'] += pressure_error * dt
        self._states['pressure_integral'] = max(-1.0, min(1.0, self._states['pressure_integral']))

        # 确定所需泵数
        required_flow = actual_demand * 1.1  # 留10%裕量
        required_pumps = math.ceil(required_flow / self._parameters['pump_capacity'])
        required_pumps = max(1, min(self._parameters['num_pumps'], required_pumps))

        # 泵切换逻辑 (带延迟保护)
        self._update_pumps(required_pumps, dt)

        # 计算实际供水量
        running_pumps = sum(self._states['pump_running'])
        total_flow = running_pumps * self._parameters['pump_capacity']

        # 计算压力 (简化的压力-流量关系)
        if total_flow >= actual_demand:
            pressure = self._parameters['target_pressure']
        else:
            # 供不应求时压力下降
            pressure = self._parameters['target_pressure'] * (total_flow / actual_demand)

        # 确定压力区域
        pressure_zone = self._evaluate_pressure_zone(pressure)

        # 更新服务连续性统计
        self._states['service_time'] += dt
        if pressure >= self._parameters['min_pressure']:
            self._states['adequate_service_time'] += dt

        service_continuity = (self._states['adequate_service_time'] /
                             max(1.0, self._states['service_time']))

        self._outputs = {
            'pump_status': self._states['pump_running'].copy(),
            'total_flow': total_flow,
            'pressure': pressure,
            'pressure_zone': pressure_zone,
            'service_continuity': service_continuity,
        }

    def _predict_demand(self, hour: float) -> float:
        """基于日变化曲线预测需求"""
        base = self._parameters['base_demand']
        # 简化的日变化: 早高峰(7-9), 晚高峰(18-20), 夜间低谷(0-6)
        if 7 <= hour <= 9 or 18 <= hour <= 20:
            return base * self._parameters['peak_factor']
        elif 0 <= hour <= 6:
            return base * self._parameters['valley_factor']
        return base

    def _update_pumps(self, required: int, dt: float):
        """更新泵运行状态"""
        current = sum(self._states['pump_running'])

        if required > current:
            # 需要启动更多泵
            for i in range(len(self._states['pump_running'])):
                if not self._states['pump_running'][i]:
                    self._states['pump_switch_timer'][i] += dt
                    if self._states['pump_switch_timer'][i] >= self._parameters['pump_switch_delay']:
                        self._states['pump_running'][i] = True
                        self._states['pump_switch_timer'][i] = 0.0
                        if sum(self._states['pump_running']) >= required:
                            break
        elif required < current:
            # 需要停止部分泵
            for i in range(len(self._states['pump_running']) - 1, -1, -1):
                if self._states['pump_running'][i] and sum(self._states['pump_running']) > required:
                    self._states['pump_switch_timer'][i] += dt
                    if self._states['pump_switch_timer'][i] >= self._parameters['pump_switch_delay']:
                        self._states['pump_running'][i] = False
                        self._states['pump_switch_timer'][i] = 0.0

    def _evaluate_pressure_zone(self, pressure: float) -> str:
        """评估压力区域"""
        target = self._parameters['target_pressure']
        tolerance = self._parameters['pressure_tolerance']

        if pressure < self._parameters['min_pressure']:
            return 'CRITICAL'
        elif pressure < target - tolerance:
            return 'LOW'
        elif pressure > self._parameters['max_pressure']:
            return 'CRITICAL'
        elif pressure > target + tolerance:
            return 'HIGH'
        return 'NORMAL'

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


# ============================================================================
# 4. 防洪调度模型 - 以不确定性管理与越界控制为核心
# ============================================================================

class FloodRiskLevel(Enum):
    """洪水风险等级"""
    GREEN = "green"       # 安全
    BLUE = "blue"         # 一般
    YELLOW = "yellow"     # 较重
    ORANGE = "orange"     # 严重
    RED = "red"           # 特别严重


class DecisionAuthority(Enum):
    """决策权限"""
    AUTONOMOUS = "autonomous"           # 自主决策
    SUPERVISED = "supervised"           # 监督下决策
    HUMAN_APPROVAL = "human_approval"   # 需人工批准
    HUMAN_ONLY = "human_only"           # 仅人工决策


class FloodControlMBDModel(MBDModel):
    """
    防洪调度MBD模型 - 最简案例: 单水库防洪调度

    核心关注:
    - 预报误差放大的风险
    - 多场洪水叠加
    - 极端情形下的保守退化策略
    - 明确哪些情形可以自主决策，哪些情形必须强制人工介入
    """

    def __init__(self, model_id: str = "FLOOD_CTRL_MBD_001"):
        super().__init__(model_id, "防洪调度控制模型", ModelType.CONTROLLER)

        self._parameters = {
            # 水库参数
            'flood_limit_level': 145.0,       # 汛限水位 (m)
            'design_flood_level': 150.0,      # 设计洪水位 (m)
            'check_flood_level': 152.0,       # 校核洪水位 (m)
            'dam_crest_level': 155.0,         # 坝顶高程 (m)

            # 泄洪能力
            'max_discharge': 5000.0,          # 最大泄量 (m³/s)
            'safe_discharge': 3000.0,         # 安全下泄 (m³/s)

            # 预报参数
            'forecast_horizon': 24.0,         # 预报时域 (小时)
            'forecast_error_ratio': 0.2,      # 预报误差率 (±20%)

            # 决策阈值
            'autonomous_threshold': 0.7,      # 自主决策阈值 (风险指数<0.7)
            'human_required_threshold': 0.9,  # 强制人工阈值 (风险指数>0.9)
        }

        self.artifact.inputs = [
            'current_level',       # 当前水位 (m)
            'inflow',              # 入库流量 (m³/s)
            'forecast_inflow',     # 预报入流 [list]
            'downstream_safe',     # 下游安全泄量 (m³/s)
        ]

        self.artifact.outputs = [
            'discharge',           # 下泄流量 (m³/s)
            'risk_level',          # 风险等级
            'decision_authority',  # 决策权限
            'forecast_confidence', # 预报置信度
            'safety_margin',       # 安全裕度
        ]

        self.artifact.requirements = [
            'REQ_FLD_001',  # 水位不超校核洪水位
            'REQ_FLD_002',  # 高风险时强制人工介入
            'REQ_FLD_003',  # 预报误差风险识别
        ]

    def initialize(self):
        self._inputs = {}
        self._states = {
            'consecutive_high_inflows': 0,    # 连续高来水次数
            'peak_level_reached': 0.0,        # 历史最高水位
            'decision_mode': 'AUTONOMOUS',
            'forecast_history': [],           # 预报历史 (用于评估准确性)
            'actual_history': [],             # 实际历史
        }

        self._outputs = {
            'discharge': 0.0,
            'risk_level': 'GREEN',
            'decision_authority': 'AUTONOMOUS',
            'forecast_confidence': 1.0,
            'safety_margin': 1.0,
        }

    def update(self, dt: float):
        # 获取输入
        level = self._inputs.get('current_level', self._parameters['flood_limit_level'])
        inflow = self._inputs.get('inflow', 0.0)
        forecast = self._inputs.get('forecast_inflow', [inflow])
        downstream_safe = self._inputs.get('downstream_safe', self._parameters['safe_discharge'])

        # 更新历史
        self._update_forecast_history(inflow)

        # 评估风险等级
        risk_level, risk_index = self._evaluate_risk(level, inflow, forecast)

        # 计算预报置信度
        forecast_confidence = self._calculate_forecast_confidence()

        # 确定决策权限
        decision_authority = self._determine_authority(risk_index, forecast_confidence)

        # 计算安全裕度
        safety_margin = self._calculate_safety_margin(level)

        # 计算下泄流量 (根据决策权限采用不同策略)
        discharge = self._calculate_discharge(
            level, inflow, forecast, downstream_safe,
            decision_authority, risk_level
        )

        # 更新峰值记录
        if level > self._states['peak_level_reached']:
            self._states['peak_level_reached'] = level

        self._outputs = {
            'discharge': discharge,
            'risk_level': risk_level,
            'decision_authority': decision_authority,
            'forecast_confidence': forecast_confidence,
            'safety_margin': safety_margin,
        }

    def _evaluate_risk(self, level: float, inflow: float, forecast: List[float]) -> Tuple[str, float]:
        """评估风险等级"""
        flood_limit = self._parameters['flood_limit_level']
        design_level = self._parameters['design_flood_level']
        check_level = self._parameters['check_flood_level']

        # 计算水位风险指数
        if level <= flood_limit:
            level_risk = 0.0
        elif level <= design_level:
            level_risk = (level - flood_limit) / (design_level - flood_limit) * 0.5
        elif level <= check_level:
            level_risk = 0.5 + (level - design_level) / (check_level - design_level) * 0.3
        else:
            level_risk = 0.8 + (level - check_level) / (self._parameters['dam_crest_level'] - check_level) * 0.2

        # 计算来水风险
        max_forecast = max(forecast) if forecast else inflow
        inflow_risk = min(1.0, max_forecast / self._parameters['max_discharge'])

        # 综合风险指数
        risk_index = 0.6 * level_risk + 0.4 * inflow_risk

        # 确定风险等级
        if risk_index < 0.2:
            return 'GREEN', risk_index
        elif risk_index < 0.4:
            return 'BLUE', risk_index
        elif risk_index < 0.6:
            return 'YELLOW', risk_index
        elif risk_index < 0.8:
            return 'ORANGE', risk_index
        else:
            return 'RED', risk_index

    def _calculate_forecast_confidence(self) -> float:
        """计算预报置信度"""
        if len(self._states['forecast_history']) < 2:
            return 0.8  # 默认置信度

        # 比较历史预报与实际值
        errors = []
        for f, a in zip(self._states['forecast_history'], self._states['actual_history']):
            if a > 0:
                error = abs(f - a) / a
                errors.append(error)

        if not errors:
            return 0.8

        avg_error = sum(errors) / len(errors)
        confidence = max(0.0, 1.0 - avg_error / self._parameters['forecast_error_ratio'])
        return confidence

    def _update_forecast_history(self, actual_inflow: float):
        """更新预报历史"""
        forecast = self._inputs.get('forecast_inflow', [actual_inflow])
        if forecast:
            self._states['forecast_history'].append(forecast[0])
            self._states['actual_history'].append(actual_inflow)
            # 保留最近24个记录
            if len(self._states['forecast_history']) > 24:
                self._states['forecast_history'] = self._states['forecast_history'][-24:]
                self._states['actual_history'] = self._states['actual_history'][-24:]

    def _determine_authority(self, risk_index: float, confidence: float) -> str:
        """确定决策权限"""
        # 考虑预报不确定性放大风险
        adjusted_risk = risk_index * (2 - confidence)

        if adjusted_risk < self._parameters['autonomous_threshold']:
            return 'AUTONOMOUS'
        elif adjusted_risk < self._parameters['human_required_threshold']:
            if confidence > 0.7:
                return 'SUPERVISED'
            else:
                return 'HUMAN_APPROVAL'
        else:
            return 'HUMAN_ONLY'

    def _calculate_safety_margin(self, level: float) -> float:
        """计算安全裕度"""
        check_level = self._parameters['check_flood_level']
        if level >= check_level:
            return 0.0
        return (check_level - level) / (check_level - self._parameters['flood_limit_level'])

    def _calculate_discharge(self, level: float, inflow: float, forecast: List[float],
                            downstream_safe: float, authority: str, risk: str) -> float:
        """计算下泄流量"""
        flood_limit = self._parameters['flood_limit_level']
        max_discharge = self._parameters['max_discharge']

        # 基础策略: 维持汛限水位
        if level <= flood_limit:
            base_discharge = min(inflow, downstream_safe)
        else:
            # 超汛限: 加大泄量
            excess = level - flood_limit
            urgency = min(1.0, excess / 5.0)  # 每超5m加大到最大
            base_discharge = downstream_safe + urgency * (max_discharge - downstream_safe)

        # 根据决策权限调整策略
        if authority == 'AUTONOMOUS':
            # 自主决策: 正常执行
            discharge = base_discharge
        elif authority == 'SUPERVISED':
            # 监督决策: 保守10%
            discharge = base_discharge * 0.9
        elif authority == 'HUMAN_APPROVAL':
            # 需批准: 保守20%, 限制在安全泄量
            discharge = min(base_discharge * 0.8, downstream_safe)
        else:  # HUMAN_ONLY
            # 仅人工: 极保守, 仅维持最小泄量
            discharge = min(inflow * 0.5, downstream_safe * 0.5)

        # 限制在能力范围内
        return max(0.0, min(max_discharge, discharge))

    def get_outputs(self) -> Dict[str, Any]:
        return self._outputs.copy()


# ============================================================================
# ODD定义函数 - 各类型水网的差异化ODD
# ============================================================================

def create_irrigation_network_odd() -> ODDDefinition:
    """创建灌区水网ODD - 关注长期公平性"""
    odd = ODDDefinition(
        odd_id="ODD_IRRIGATION_001",
        name="灌区水网ODD",
        description="以长期公平性与连续调配能力为核心"
    )

    # 来水年景条件
    odd.add_condition(OperatingCondition(
        condition_id="IRR_WATER_YEAR",
        name="来水年景",
        description="年度来水情况分类",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.STATIC,
        parameter_name="water_year_type",
        allowed_values=["wet", "normal", "dry"]
    ))

    # 渠道损失率条件
    odd.add_condition(OperatingCondition(
        condition_id="IRR_LOSS_RATE",
        name="渠道损失率",
        description="输配水损失率范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="loss_rate",
        unit="%",
        min_value=10.0,
        max_value=25.0,
        nominal_value=15.0
    ))

    # 公平性指数条件
    odd.add_condition(OperatingCondition(
        condition_id="IRR_FAIRNESS",
        name="公平性指数",
        description="分水公平性指标",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="fairness_index",
        unit="",
        min_value=0.85,
        max_value=1.0,
        nominal_value=0.95
    ))

    # 需求预测误差
    odd.add_condition(OperatingCondition(
        condition_id="IRR_DEMAND_ERROR",
        name="需水预测误差",
        description="作物需水预测相对误差",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="demand_prediction_error",
        unit="%",
        min_value=0.0,
        max_value=30.0,
        nominal_value=10.0
    ))

    return odd


def create_water_transfer_odd() -> ODDDefinition:
    """创建调水工程ODD - 关注时滞与协调"""
    odd = ODDDefinition(
        odd_id="ODD_TRANSFER_001",
        name="调水工程ODD",
        description="以长时滞与多工程联动为核心"
    )

    # 时滞裕度条件 (调度间隔/时滞比)
    odd.add_condition(OperatingCondition(
        condition_id="TRF_DELAY_MARGIN",
        name="时滞裕度",
        description="调度调整间隔与传输时滞的比值",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="delay_margin",
        unit="",
        min_value=0.3,  # 调度间隔至少为时滞的30%
        max_value=2.0,
        nominal_value=0.5
    ))

    # 协调状态条件
    odd.add_condition(OperatingCondition(
        condition_id="TRF_COORDINATION",
        name="协调状态",
        description="多受水区协调程度",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="coordination_status",
        allowed_values=["COORDINATED", "PARTIAL", "UNCOORDINATED", "IDLE"]
    ))

    # 预报准确度
    odd.add_condition(OperatingCondition(
        condition_id="TRF_FORECAST_ACC",
        name="预报准确度",
        description="来水预报准确度",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="forecast_accuracy",
        unit="%",
        min_value=70.0,
        max_value=100.0,
        nominal_value=85.0
    ))

    return odd


def create_urban_water_supply_odd() -> ODDDefinition:
    """创建城市供水ODD - 关注压力稳定性"""
    odd = ODDDefinition(
        odd_id="ODD_URBAN_WS_001",
        name="城市供水ODD",
        description="以压力稳定性与服务连续性为核心"
    )

    # 压力范围条件
    odd.add_condition(OperatingCondition(
        condition_id="UWS_PRESSURE",
        name="管网压力",
        description="供水管网压力范围",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="pressure",
        unit="MPa",
        min_value=0.20,
        max_value=0.50,
        nominal_value=0.35
    ))

    # 负荷波动条件
    odd.add_condition(OperatingCondition(
        condition_id="UWS_LOAD_FACTOR",
        name="负荷系数",
        description="当前负荷与基础负荷的比值",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="load_factor",
        unit="",
        min_value=0.5,
        max_value=1.8,
        nominal_value=1.0
    ))

    # 服务连续性条件
    odd.add_condition(OperatingCondition(
        condition_id="UWS_CONTINUITY",
        name="服务连续性",
        description="供水服务连续性指标",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="service_continuity",
        unit="%",
        min_value=95.0,
        max_value=100.0,
        nominal_value=99.0
    ))

    # 泵站状态条件
    odd.add_condition(OperatingCondition(
        condition_id="UWS_PUMP_STATUS",
        name="泵站可用率",
        description="可用泵数量比例",
        category=ODDCategory.INFRASTRUCTURE,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="pump_availability",
        unit="%",
        min_value=50.0,
        max_value=100.0,
        nominal_value=100.0
    ))

    return odd


def create_flood_control_odd() -> ODDDefinition:
    """创建防洪调度ODD - 关注不确定性与越界控制"""
    odd = ODDDefinition(
        odd_id="ODD_FLOOD_CTRL_001",
        name="防洪调度ODD",
        description="以不确定性管理与越界控制为核心"
    )

    # 风险等级条件
    odd.add_condition(OperatingCondition(
        condition_id="FLD_RISK_LEVEL",
        name="风险等级",
        description="洪水风险分级",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="risk_level",
        allowed_values=["GREEN", "BLUE", "YELLOW", "ORANGE", "RED"]
    ))

    # 决策权限条件
    odd.add_condition(OperatingCondition(
        condition_id="FLD_DECISION_AUTH",
        name="决策权限",
        description="当前决策权限级别",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="decision_authority",
        allowed_values=["AUTONOMOUS", "SUPERVISED", "HUMAN_APPROVAL", "HUMAN_ONLY"]
    ))

    # 预报置信度条件
    odd.add_condition(OperatingCondition(
        condition_id="FLD_FORECAST_CONF",
        name="预报置信度",
        description="洪水预报置信水平",
        category=ODDCategory.ENVIRONMENTAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="forecast_confidence",
        unit="%",
        min_value=50.0,
        max_value=100.0,
        nominal_value=80.0
    ))

    # 安全裕度条件
    odd.add_condition(OperatingCondition(
        condition_id="FLD_SAFETY_MARGIN",
        name="安全裕度",
        description="距校核洪水位的相对裕度",
        category=ODDCategory.OPERATIONAL,
        condition_type=ConditionType.DYNAMIC,
        parameter_name="safety_margin",
        unit="",
        min_value=0.0,
        max_value=1.0,
        nominal_value=0.5
    ))

    return odd


# ============================================================================
# 降级策略定义 - 各类型水网的差异化降级
# ============================================================================

def create_irrigation_degradation_strategies() -> List[DegradationStrategy]:
    """创建灌区水网降级策略"""
    strategies = []

    # 枯水年降级
    strategies.append(DegradationStrategy(
        strategy_id="IRR_DEG_DRY_YEAR",
        name="枯水年配水降级",
        description="枯水年份按比例削减配水",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["WATER_SHORTAGE_MODERATE"],
        actions=[
            "按原配比削减30%配水",
            "优先保证粮食作物",
            "启用应急水源",
        ],
        parameter_overrides={'supply_ratio': 0.7}
    ))

    # 严重缺水降级
    strategies.append(DegradationStrategy(
        strategy_id="IRR_DEG_SEVERE",
        name="严重缺水降级",
        description="严重缺水时保基本需求",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["WATER_SHORTAGE_SEVERE"],
        actions=[
            "仅保证生活用水",
            "农业轮灌",
            "申请上级调水",
        ],
        parameter_overrides={'supply_ratio': 0.4}
    ))

    return strategies


def create_water_transfer_degradation_strategies() -> List[DegradationStrategy]:
    """创建调水工程降级策略"""
    strategies = []

    # 时滞失控降级
    strategies.append(DegradationStrategy(
        strategy_id="TRF_DEG_DELAY_LOSS",
        name="时滞失控降级",
        description="调度修正来不及生效时的保守策略",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["DELAY_MARGIN_LOW"],
        actions=[
            "增大调度间隔",
            "采用预测控制",
            "减小调度幅度",
        ],
        parameter_overrides={'min_adjustment_interval': 8.0}
    ))

    # 协调失败降级
    strategies.append(DegradationStrategy(
        strategy_id="TRF_DEG_COORD_FAIL",
        name="协调失败降级",
        description="多受水区协调失败时的独立控制",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["COORDINATION_FAILURE"],
        actions=[
            "切换为独立控制模式",
            "按预设配比分配",
            "通知人工介入",
        ]
    ))

    return strategies


def create_urban_supply_degradation_strategies() -> List[DegradationStrategy]:
    """创建城市供水降级策略"""
    strategies = []

    # 低压降级
    strategies.append(DegradationStrategy(
        strategy_id="UWS_DEG_LOW_PRESSURE",
        name="低压运行降级",
        description="压力偏低时的保障措施",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["PRESSURE_LOW"],
        actions=[
            "启动备用泵",
            "关闭非核心用户",
            "提高泵站转速",
        ],
        parameter_overrides={'target_pressure': 0.30}
    ))

    # 泵站故障降级
    strategies.append(DegradationStrategy(
        strategy_id="UWS_DEG_PUMP_FAIL",
        name="泵站故障降级",
        description="部分泵故障时的运行策略",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L2,
        trigger_faults=["PUMP_FAILURE"],
        actions=[
            "隔离故障泵",
            "调整运行泵组合",
            "请求相邻泵站支援",
        ]
    ))

    return strategies


def create_flood_control_degradation_strategies() -> List[DegradationStrategy]:
    """创建防洪调度降级策略 - 保守退化策略"""
    strategies = []

    # 预报不确定性高时降级
    strategies.append(DegradationStrategy(
        strategy_id="FLD_DEG_UNCERTAINTY",
        name="高不确定性降级",
        description="预报置信度低时采用保守策略",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L1,
        trigger_faults=["FORECAST_UNCERTAINTY_HIGH"],
        actions=[
            "采用最不利预报情景",
            "预留更大安全裕度",
            "提前预泄腾库",
        ],
        parameter_overrides={'safety_factor': 1.3}
    ))

    # 高风险强制人工介入
    strategies.append(DegradationStrategy(
        strategy_id="FLD_DEG_HIGH_RISK",
        name="高风险人工接管",
        description="风险超阈值时强制人工决策",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.DEGRADED_L3,
        trigger_faults=["RISK_LEVEL_HIGH", "MULTI_FLOOD_OVERLAP"],
        actions=[
            "锁定自动调度",
            "报警通知值班人员",
            "提供决策建议方案",
            "等待人工确认执行",
        ]
    ))

    # 极端情况安全状态
    strategies.append(DegradationStrategy(
        strategy_id="FLD_DEG_EXTREME",
        name="极端情况安全模式",
        description="校核洪水级别时的最保守策略",
        current_level=DegradationLevel.NORMAL,
        target_level=DegradationLevel.SAFE_STATE,
        trigger_faults=["CHECK_FLOOD_EXCEEDED"],
        actions=[
            "全开泄洪设施",
            "启动应急预案",
            "通知下游转移",
            "请求上级指挥",
        ]
    ))

    return strategies
