# -*- coding: utf-8 -*-
"""
功率分配算法与响应链解耦控制
Power Allocation Algorithm and Response Chain Decoupling

本模块基于"水系统控制论"原理,实现多能互补系统的功率分配算法:

1. PowerAllocationAlgorithm:
   - 基于频率偏差最小化的功率分配
   - 考虑各单元响应特性和约束
   - 优化分配以最小化系统频率偏差

2. ResponseChainDecoupler:
   - 解决风光波动引起的"响应链条断裂"问题
   - 实现SC->BESS->PSH/Hydro的平滑功率移交
   - 确保任意时刻都有足够的功率支撑

3. FrequencyRegulator:
   - 一次调频和二次调频协调
   - 频率偏差Δf最小化控制

理论基础:
=========
水系统控制论核心思想:
- 将能量流动类比为水流
- 功率分配类似于流量分配
- 储能系统类似于水库调节
- 频率稳定类似于水位控制

优化目标:
min J = ∫[w₁·Δf² + w₂·Σ(ΔP_i)² + w₃·Σ(1-η_i)] dt

约束:
- 功率平衡: Σ P_gen = P_load
- 各单元功率限制: P_min ≤ P ≤ P_max
- 爬坡率约束: |dP/dt| ≤ R_max
- SOC约束: SOC_min ≤ SOC ≤ SOC_max
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from enum import Enum, auto
from collections import deque


# ==================== 数据结构 ====================

@dataclass
class UnitCapability:
    """能源单元能力描述"""
    name: str
    rated_power: float              # 额定功率(MW)
    min_power: float = 0.0          # 最小功率(MW)
    ramp_rate_up: float = 0.1       # 上升爬坡率(p.u./s)
    ramp_rate_down: float = 0.1     # 下降爬坡率(p.u./s)
    response_time: float = 1.0      # 响应时间常数(s)
    efficiency: float = 0.95        # 效率
    available: bool = True          # 是否可用
    priority: int = 1               # 调度优先级(1最高)
    current_power: float = 0.0      # 当前功率


@dataclass
class AllocationResult:
    """分配结果"""
    power_commands: Dict[str, float]  # 各单元功率指令
    total_allocated: float            # 总分配功率
    residual: float                   # 未分配残差
    frequency_deviation_expected: float  # 预期频率偏差
    status: str = "success"           # 状态


@dataclass
class ChainState:
    """响应链状态"""
    active_layer: int = 0             # 当前活动层(1=SC, 2=BESS, 3=PSH/Hydro)
    handover_progress: float = 0.0    # 移交进度(0-1)
    sc_contribution: float = 0.0      # SC贡献比例
    bess_contribution: float = 0.0    # BESS贡献比例
    slow_unit_contribution: float = 0.0  # 慢速单元贡献比例


# ==================== 功率分配算法 ====================

class PowerAllocationAlgorithm:
    """
    基于水系统控制论的功率分配算法

    分配策略:
    ========
    1. 按响应速度分层:
       - 快速层: SC (毫秒级)
       - 中速层: BESS (秒级)
       - 慢速层: PSH, Hydro (分钟级)

    2. 功率需求分解:
       P_demand = P_fast + P_medium + P_slow
       使用滤波器分解不同时间尺度的分量

    3. 分配原则:
       - 高频波动 -> SC
       - 中频波动 -> BESS
       - 低频波动 -> PSH/Hydro
       - 稳态偏差 -> 最优经济分配

    4. 频率偏差最小化:
       根据各单元的下垂特性和容量,优化分配
    """

    def __init__(
        self,
        units: List[UnitCapability],
        system_base_power: float = 1000.0,  # 系统基准功率(MW)
        frequency_droop: float = 0.05,       # 系统下垂系数(5%)
        nominal_frequency: float = 50.0
    ):
        self.units = {u.name: u for u in units}
        self.base_power = system_base_power
        self.droop = frequency_droop
        self.f_nom = nominal_frequency

        # 滤波器状态(用于功率分解)
        self._high_freq_filter = 0.0
        self._med_freq_filter = 0.0
        self._low_freq_filter = 0.0

        # 时间常数
        self._tau_high = 0.1    # 高频滤波时间常数(s)
        self._tau_med = 2.0     # 中频滤波时间常数(s)
        self._tau_low = 60.0    # 低频滤波时间常数(s)

    def decompose_power_demand(
        self,
        power_demand: float,
        dt: float
    ) -> Tuple[float, float, float]:
        """
        将功率需求分解为不同时间尺度的分量

        Args:
            power_demand: 总功率需求(MW)
            dt: 时间步长(s)

        Returns:
            (高频分量, 中频分量, 低频分量)
        """
        # 低通滤波提取低频分量
        alpha_low = 1 - np.exp(-dt / self._tau_low)
        self._low_freq_filter += alpha_low * (power_demand - self._low_freq_filter)

        # 中频 = 低频滤波后 - 更低频滤波
        alpha_med = 1 - np.exp(-dt / self._tau_med)
        self._med_freq_filter += alpha_med * (power_demand - self._med_freq_filter)

        # 高频 = 原始 - 低频
        p_low = self._low_freq_filter
        p_med = self._med_freq_filter - self._low_freq_filter
        p_high = power_demand - self._med_freq_filter

        return p_high, p_med, p_low

    def allocate_by_priority(
        self,
        power_demand: float,
        available_units: Optional[List[str]] = None
    ) -> AllocationResult:
        """
        按优先级分配功率

        Args:
            power_demand: 功率需求(MW), 正=需要发电, 负=需要吸收
            available_units: 可用单元列表

        Returns:
            AllocationResult
        """
        if available_units is None:
            available_units = list(self.units.keys())

        # 按优先级排序
        sorted_units = sorted(
            [self.units[n] for n in available_units if n in self.units and self.units[n].available],
            key=lambda u: u.priority
        )

        commands = {}
        remaining = power_demand

        for unit in sorted_units:
            if abs(remaining) < 0.01:
                commands[unit.name] = unit.current_power
                continue

            # 计算可分配的功率
            if remaining > 0:  # 需要发电
                max_available = unit.rated_power - unit.current_power
                allocated = min(remaining, max_available)
            else:  # 需要吸收(充电/抽水)
                max_available = unit.current_power - unit.min_power
                allocated = max(remaining, -max_available)

            commands[unit.name] = unit.current_power + allocated
            remaining -= allocated

        return AllocationResult(
            power_commands=commands,
            total_allocated=power_demand - remaining,
            residual=remaining,
            frequency_deviation_expected=remaining / self.base_power * self.f_nom / self.droop,
            status="success" if abs(remaining) < 0.1 else "partial"
        )

    def allocate_hierarchical(
        self,
        power_demand: float,
        dt: float,
        fast_units: List[str],
        medium_units: List[str],
        slow_units: List[str]
    ) -> AllocationResult:
        """
        分层功率分配

        Args:
            power_demand: 总功率需求
            dt: 时间步长
            fast_units: 快速响应单元(SC)
            medium_units: 中速响应单元(BESS)
            slow_units: 慢速响应单元(PSH, Hydro)

        Returns:
            AllocationResult
        """
        # 分解功率需求
        p_high, p_med, p_low = self.decompose_power_demand(power_demand, dt)

        commands = {}
        residual = 0.0

        # 高频分量 -> 快速单元
        result_fast = self.allocate_by_priority(p_high, fast_units)
        commands.update(result_fast.power_commands)
        residual += result_fast.residual

        # 中频分量 + 快速残差 -> 中速单元
        result_med = self.allocate_by_priority(p_med + result_fast.residual, medium_units)
        commands.update(result_med.power_commands)
        residual = result_med.residual

        # 低频分量 + 中速残差 -> 慢速单元
        result_slow = self.allocate_by_priority(p_low + result_med.residual, slow_units)
        commands.update(result_slow.power_commands)
        residual = result_slow.residual

        total_allocated = power_demand - residual

        return AllocationResult(
            power_commands=commands,
            total_allocated=total_allocated,
            residual=residual,
            frequency_deviation_expected=residual / self.base_power * self.f_nom / self.droop,
            status="success" if abs(residual) < 0.1 else "partial"
        )

    def minimize_frequency_deviation(
        self,
        power_imbalance: float,
        frequency_deviation: float,
        available_units: List[str]
    ) -> AllocationResult:
        """
        最小化频率偏差的功率分配

        基于下垂控制原理:
        Δf = ΔP / (K * P_base)
        各单元按下垂系数反比分配

        Args:
            power_imbalance: 功率不平衡(MW)
            frequency_deviation: 当前频率偏差(Hz)
            available_units: 可用单元

        Returns:
            AllocationResult
        """
        # 需要补偿的功率
        # 频率低 -> 需要增加发电
        # 频率高 -> 需要减少发电
        power_needed = -frequency_deviation * self.droop * self.base_power / self.f_nom

        # 加上当前不平衡
        total_power_needed = power_needed + power_imbalance

        # 按容量加权分配
        total_capacity = sum(
            self.units[n].rated_power
            for n in available_units
            if n in self.units and self.units[n].available
        )

        if total_capacity < 0.1:
            return AllocationResult(
                power_commands={},
                total_allocated=0,
                residual=total_power_needed,
                frequency_deviation_expected=frequency_deviation,
                status="no_capacity"
            )

        commands = {}
        allocated = 0.0

        for name in available_units:
            if name not in self.units or not self.units[name].available:
                continue

            unit = self.units[name]
            # 按容量比例分配
            share = unit.rated_power / total_capacity
            power_target = total_power_needed * share

            # 限幅
            if power_target > 0:
                power_target = min(power_target, unit.rated_power - unit.current_power)
            else:
                power_target = max(power_target, -(unit.current_power - unit.min_power))

            commands[name] = unit.current_power + power_target
            allocated += power_target

        residual = total_power_needed - allocated
        expected_freq_dev = residual / self.base_power * self.f_nom / self.droop

        return AllocationResult(
            power_commands=commands,
            total_allocated=allocated,
            residual=residual,
            frequency_deviation_expected=frequency_deviation + expected_freq_dev,
            status="success" if abs(residual) < 0.1 else "partial"
        )


# ==================== 响应链解耦控制 ====================

class ResponseChainDecoupler:
    """
    响应链解耦控制器

    解决问题:
    ========
    当风光瞬时波动发生时,如果只依赖PSH或水电响应,
    由于它们启动时间长(分钟级),会出现"响应真空期",
    导致频率大幅偏离。

    解决方案:
    ========
    1. SC立即响应(毫秒级) - 填补真空期
    2. BESS逐渐接管SC功率(秒级) - 恢复SC容量
    3. PSH/Hydro启动后接管BESS功率(分钟级) - 恢复BESS容量
    4. 实现无缝功率移交,确保响应链连续

    移交策略:
    ========
    使用S形曲线实现平滑移交:
    handover(t) = 1 / (1 + exp(-k*(t-t_mid)))
    """

    def __init__(
        self,
        sc_capacity: float = 10.0,       # SC容量(MW)
        bess_capacity: float = 20.0,     # BESS容量(MW)
        handover_time_sc_bess: float = 5.0,    # SC到BESS移交时间(s)
        handover_time_bess_slow: float = 60.0  # BESS到慢速单元移交时间(s)
    ):
        self.sc_capacity = sc_capacity
        self.bess_capacity = bess_capacity
        self.t_handover_1 = handover_time_sc_bess
        self.t_handover_2 = handover_time_bess_slow

        # 状态
        self._chain_state = ChainState()
        self._event_start_time: Optional[float] = None
        self._event_power: float = 0.0
        self._slow_unit_ready = False

        # 历史
        self._power_history: deque = deque(maxlen=1000)

    def _sigmoid(self, t: float, t_mid: float, k: float = 0.5) -> float:
        """S形曲线"""
        return 1 / (1 + np.exp(-k * (t - t_mid)))

    def detect_event(
        self,
        power_demand: float,
        power_demand_prev: float,
        threshold: float = 5.0  # MW
    ) -> bool:
        """
        检测功率突变事件

        Args:
            power_demand: 当前功率需求
            power_demand_prev: 上一时刻功率需求
            threshold: 突变阈值

        Returns:
            是否检测到事件
        """
        delta = abs(power_demand - power_demand_prev)
        return delta > threshold

    def start_response_chain(self, power_demand: float, current_time: float):
        """开始响应链"""
        self._event_start_time = current_time
        self._event_power = power_demand
        self._chain_state.active_layer = 1
        self._chain_state.handover_progress = 0.0
        self._slow_unit_ready = False

    def notify_slow_unit_ready(self):
        """通知慢速单元已准备好"""
        self._slow_unit_ready = True

    def step(
        self,
        dt: float,
        current_time: float,
        power_demand: float
    ) -> Dict[str, float]:
        """
        执行一步响应链控制

        Args:
            dt: 时间步长
            current_time: 当前时间
            power_demand: 功率需求

        Returns:
            各层功率分配
        """
        if self._event_start_time is None:
            # 无事件,返回零分配
            return {
                'sc_power': 0.0,
                'bess_power': 0.0,
                'slow_power': 0.0
            }

        elapsed = current_time - self._event_start_time

        # 计算各层贡献比例
        if not self._slow_unit_ready:
            # 阶段1: SC -> BESS
            if elapsed < self.t_handover_1 * 3:
                # SC逐渐减少,BESS逐渐增加
                sc_ratio = 1 - self._sigmoid(elapsed, self.t_handover_1)
                bess_ratio = self._sigmoid(elapsed, self.t_handover_1)
                slow_ratio = 0.0
            else:
                # SC移交完成
                sc_ratio = 0.0
                bess_ratio = 1.0
                slow_ratio = 0.0
        else:
            # 阶段2: BESS -> Slow
            t_since_ready = elapsed - self.t_handover_1 * 2

            if t_since_ready < self.t_handover_2 * 2:
                bess_ratio = 1 - self._sigmoid(t_since_ready, self.t_handover_2)
                slow_ratio = self._sigmoid(t_since_ready, self.t_handover_2)
                sc_ratio = 0.0
            else:
                # 移交完成
                sc_ratio = 0.0
                bess_ratio = 0.0
                slow_ratio = 1.0
                # 重置事件
                self._event_start_time = None

        # 更新状态
        self._chain_state.sc_contribution = sc_ratio
        self._chain_state.bess_contribution = bess_ratio
        self._chain_state.slow_unit_contribution = slow_ratio

        # 计算功率分配
        # 使用当前需求而非事件时需求,以跟踪变化
        return {
            'sc_power': power_demand * sc_ratio,
            'bess_power': power_demand * bess_ratio,
            'slow_power': power_demand * slow_ratio
        }

    def get_chain_state(self) -> ChainState:
        """获取响应链状态"""
        return self._chain_state

    def is_chain_active(self) -> bool:
        """响应链是否活动"""
        return self._event_start_time is not None

    def reset(self):
        """重置状态"""
        self._event_start_time = None
        self._event_power = 0.0
        self._slow_unit_ready = False
        self._chain_state = ChainState()


# ==================== 频率调节器 ====================

class FrequencyRegulator:
    """
    频率调节器

    实现一次调频(Primary Frequency Response, PFR)和
    二次调频(Automatic Generation Control, AGC)

    一次调频:
    =========
    - 响应时间: 毫秒-秒级
    - 控制方式: 下垂控制
    - 目标: 阻止频率继续偏离

    二次调频:
    =========
    - 响应时间: 秒-分钟级
    - 控制方式: PI控制
    - 目标: 将频率恢复到标称值

    频率偏差最小化:
    =============
    综合考虑:
    - 频率偏差权重
    - 调节成本
    - 各单元容量和效率
    """

    def __init__(
        self,
        nominal_frequency: float = 50.0,
        frequency_deadband: float = 0.02,  # 频率死区(Hz)
        droop_coefficient: float = 0.05,    # 下垂系数(5%)
        agc_kp: float = 50.0,               # AGC比例增益(MW/Hz)
        agc_ki: float = 10.0,               # AGC积分增益(MW/Hz/s)
        agc_max_output: float = 100.0       # AGC最大输出(MW)
    ):
        self.f_nom = nominal_frequency
        self.deadband = frequency_deadband
        self.droop = droop_coefficient
        self.agc_kp = agc_kp
        self.agc_ki = agc_ki
        self.agc_max = agc_max_output

        # 状态
        self._integral_error = 0.0
        self._last_freq_dev = 0.0
        self._pfr_output = 0.0
        self._agc_output = 0.0

        # 统计
        self._freq_dev_history: deque = deque(maxlen=10000)
        self._agc_output_history: deque = deque(maxlen=10000)

    def calculate_pfr(
        self,
        frequency_deviation: float,
        participating_units: List[UnitCapability]
    ) -> Dict[str, float]:
        """
        计算一次调频响应

        Args:
            frequency_deviation: 频率偏差(Hz)
            participating_units: 参与调频的单元

        Returns:
            各单元PFR功率调整
        """
        # 死区处理
        if abs(frequency_deviation) < self.deadband:
            return {u.name: 0.0 for u in participating_units}

        effective_dev = frequency_deviation
        if frequency_deviation > 0:
            effective_dev -= self.deadband
        else:
            effective_dev += self.deadband

        # 总PFR需求
        # Δf/f_nom = -Droop * ΔP/P_rated
        # ΔP = -Δf * P_rated / (f_nom * Droop)

        pfr_commands = {}
        for unit in participating_units:
            if not unit.available:
                pfr_commands[unit.name] = 0.0
                continue

            # 按额定容量和下垂系数分配
            delta_p = -effective_dev * unit.rated_power / (self.f_nom * self.droop)

            # 限幅
            max_up = unit.rated_power - unit.current_power
            max_down = unit.current_power - unit.min_power

            delta_p = np.clip(delta_p, -max_down, max_up)
            pfr_commands[unit.name] = delta_p

        self._pfr_output = sum(pfr_commands.values())
        return pfr_commands

    def calculate_agc(
        self,
        frequency_deviation: float,
        area_control_error: float,
        dt: float
    ) -> float:
        """
        计算二次调频(AGC)输出

        ACE = ΔP_tie + B * Δf
        其中B为频率偏差系数

        Args:
            frequency_deviation: 频率偏差(Hz)
            area_control_error: 区域控制偏差(MW)
            dt: 时间步长

        Returns:
            AGC总功率调整(MW)
        """
        # 频率偏差贡献
        freq_error = frequency_deviation

        # PI控制
        p_term = self.agc_kp * freq_error
        self._integral_error += freq_error * dt
        # 积分限幅(防止积分饱和)
        self._integral_error = np.clip(
            self._integral_error,
            -self.agc_max / self.agc_ki,
            self.agc_max / self.agc_ki
        )
        i_term = self.agc_ki * self._integral_error

        # 总AGC输出
        agc_output = -(p_term + i_term)  # 负号: 频率低需要增加出力
        agc_output = np.clip(agc_output, -self.agc_max, self.agc_max)

        self._agc_output = agc_output
        self._freq_dev_history.append(frequency_deviation)
        self._agc_output_history.append(agc_output)

        return agc_output

    def distribute_agc(
        self,
        agc_total: float,
        participating_units: List[UnitCapability]
    ) -> Dict[str, float]:
        """
        分配AGC功率给各单元

        按参与因子分配,考虑:
        - 可用容量
        - 爬坡能力
        - 效率

        Args:
            agc_total: AGC总功率
            participating_units: 参与单元

        Returns:
            各单元AGC分配
        """
        # 计算总可用容量
        if agc_total > 0:  # 需要增加出力
            total_headroom = sum(
                u.rated_power - u.current_power
                for u in participating_units if u.available
            )
        else:  # 需要减少出力
            total_headroom = sum(
                u.current_power - u.min_power
                for u in participating_units if u.available
            )

        if total_headroom < 0.1:
            return {u.name: 0.0 for u in participating_units}

        agc_commands = {}
        for unit in participating_units:
            if not unit.available:
                agc_commands[unit.name] = 0.0
                continue

            if agc_total > 0:
                headroom = unit.rated_power - unit.current_power
            else:
                headroom = -(unit.current_power - unit.min_power)

            # 按容量比例分配
            share = abs(headroom) / total_headroom
            allocated = agc_total * share

            # 效率加权(效率高的多分配)
            allocated *= unit.efficiency

            agc_commands[unit.name] = allocated

        return agc_commands

    def step(
        self,
        dt: float,
        frequency: float,
        area_control_error: float,
        participating_units: List[UnitCapability]
    ) -> Dict:
        """
        执行一步频率调节

        Returns:
            包含PFR和AGC分配的字典
        """
        freq_dev = frequency - self.f_nom

        # 一次调频
        pfr = self.calculate_pfr(freq_dev, participating_units)

        # 二次调频
        agc_total = self.calculate_agc(freq_dev, area_control_error, dt)
        agc = self.distribute_agc(agc_total, participating_units)

        # 合并(PFR和AGC叠加)
        combined = {}
        for unit in participating_units:
            pfr_power = pfr.get(unit.name, 0.0)
            agc_power = agc.get(unit.name, 0.0)
            combined[unit.name] = pfr_power + agc_power

        return {
            'pfr': pfr,
            'agc': agc,
            'combined': combined,
            'pfr_total': self._pfr_output,
            'agc_total': self._agc_output,
            'frequency_deviation': freq_dev
        }

    def get_statistics(self) -> Dict:
        """获取调频统计"""
        if len(self._freq_dev_history) == 0:
            return {}

        freq_array = np.array(self._freq_dev_history)
        return {
            'freq_dev_mean': np.mean(freq_array),
            'freq_dev_std': np.std(freq_array),
            'freq_dev_max': np.max(np.abs(freq_array)),
            'agc_output_mean': np.mean(self._agc_output_history) if self._agc_output_history else 0
        }

    def reset(self):
        """重置状态"""
        self._integral_error = 0.0
        self._pfr_output = 0.0
        self._agc_output = 0.0
        self._freq_dev_history.clear()
        self._agc_output_history.clear()
