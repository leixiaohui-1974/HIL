# -*- coding: utf-8 -*-
"""
分层控制架构
Hierarchical Control Architecture for Multi-Energy System

实现三层分布式控制:
===================

第一层(毫秒级) - Layer1_SCDroopController:
    超级电容(SC)下垂控制
    - 响应时间: 1-10ms
    - 功能: 快速响应频率突变
    - 算法: 下垂控制 ΔP = -Kp * Δf

第二层(秒级) - Layer2_BESSFilterController:
    锂电池(BESS)低通滤波控制
    - 响应时间: 100ms-1s
    - 功能: 承接SC的功率压力,平滑功率波动
    - 算法: 一阶低通滤波 + 功率分配

第三层(分钟级) - Layer3_MPCCoordinator:
    PSH与常规水电MPC协同控制
    - 响应时间: 1-10min
    - 功能: 基于预测的净负荷调度PSH和水电
    - 算法: 滚动时域优化(MPC)

响应链解耦:
==========
当风光瞬时波动发生时:
1. SC立即响应(毫秒级),稳定频率
2. BESS逐渐接管SC的功率(秒级)
3. PSH/水电在MPC调度下启动(分钟级)
4. BESS将功率移交给PSH/水电
5. SC恢复到待命状态

这种分层结构确保了"响应链条"的连续性,避免了PSH/水电启动前的"真空期"。
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum, auto
from abc import ABC, abstractmethod


# ==================== 基础数据结构 ====================

@dataclass
class ControlSignal:
    """控制信号"""
    power_command: float = 0.0      # 功率指令(MW), 正=发电/放电, 负=抽水/充电
    frequency_deviation: float = 0.0  # 频率偏差(Hz)
    power_imbalance: float = 0.0    # 功率不平衡(MW)
    timestamp: float = 0.0          # 时间戳


@dataclass
class LayerOutput:
    """层输出"""
    power_output: float = 0.0       # 本层输出功率(MW)
    power_residual: float = 0.0     # 传递给下层的残差功率(MW)
    soc: float = 0.5                # 荷电状态(如适用)
    status: str = "normal"          # 状态


@dataclass
class SystemState:
    """系统状态汇总"""
    time: float = 0.0
    frequency: float = 50.0
    frequency_deviation: float = 0.0
    total_generation: float = 0.0
    total_load: float = 0.0
    total_renewable: float = 0.0
    net_load: float = 0.0  # 负荷 - 新能源
    power_imbalance: float = 0.0


# ==================== 第一层: 超级电容下垂控制 ====================

class Layer1_SCDroopController:
    """
    第一层控制器: 超级电容下垂控制

    核心方程:
    ΔP_sc = -Kp * Δf - Kd * (dΔf/dt)

    其中:
    - Kp: 下垂系数(MW/Hz)
    - Kd: 阻尼系数(MW·s/Hz)
    - Δf: 频率偏差
    - dΔf/dt: 频率变化率(RoCoF)

    特点:
    - 响应时间: 1-10ms
    - 高功率密度
    - 有限能量容量
    """

    def __init__(
        self,
        rated_power: float = 10.0,      # 额定功率(MW)
        rated_energy: float = 0.5,       # 额定能量(MWh)
        droop_gain: float = 20.0,        # 下垂系数Kp(MW/Hz)
        damping_gain: float = 5.0,       # 阻尼系数Kd(MW·s/Hz)
        time_constant: float = 0.01,     # 响应时间常数(s)
        soc_high_limit: float = 0.95,    # SOC上限
        soc_low_limit: float = 0.05,     # SOC下限
        deadband: float = 0.02           # 频率死区(Hz)
    ):
        self.rated_power = rated_power
        self.rated_energy = rated_energy
        self.droop_gain = droop_gain
        self.damping_gain = damping_gain
        self.time_constant = time_constant
        self.soc_high_limit = soc_high_limit
        self.soc_low_limit = soc_low_limit
        self.deadband = deadband

        # 状态变量
        self._soc = 0.5
        self._power_output = 0.0
        self._last_freq_dev = 0.0
        self._power_integral = 0.0

    def get_soc(self) -> float:
        """获取SOC"""
        return self._soc

    def get_power(self) -> float:
        """获取当前输出功率"""
        return self._power_output

    def calculate_droop_power(
        self,
        frequency_deviation: float,
        rocof: float = 0.0
    ) -> float:
        """
        计算下垂控制功率

        Args:
            frequency_deviation: 频率偏差(Hz)
            rocof: 频率变化率(Hz/s)

        Returns:
            控制功率(MW)
        """
        # 死区处理
        if abs(frequency_deviation) < self.deadband:
            freq_dev_effective = 0.0
        else:
            freq_dev_effective = frequency_deviation - np.sign(frequency_deviation) * self.deadband

        # 下垂控制: P = -Kp * Δf
        power_droop = -self.droop_gain * freq_dev_effective

        # 阻尼控制: P_damp = -Kd * RoCoF
        power_damp = -self.damping_gain * rocof

        return power_droop + power_damp

    def step(
        self,
        dt: float,
        frequency_deviation: float,
        rocof: float = 0.0,
        power_setpoint: Optional[float] = None
    ) -> LayerOutput:
        """
        执行一步控制

        Args:
            dt: 时间步长(s)
            frequency_deviation: 频率偏差(Hz)
            rocof: 频率变化率(Hz/s)
            power_setpoint: 外部功率设定(如果有)

        Returns:
            LayerOutput
        """
        # 计算下垂功率
        power_droop = self.calculate_droop_power(frequency_deviation, rocof)

        # 如果有外部设定,叠加
        if power_setpoint is not None:
            power_target = power_droop + power_setpoint
        else:
            power_target = power_droop

        # SOC保护
        if power_target > 0 and self._soc < self.soc_low_limit:
            # 需要放电但SOC过低
            power_target *= (self._soc / self.soc_low_limit) ** 2
        elif power_target < 0 and self._soc > self.soc_high_limit:
            # 需要充电但SOC过高
            power_target *= ((1 - self._soc) / (1 - self.soc_high_limit)) ** 2

        # 功率限幅
        power_target = np.clip(power_target, -self.rated_power, self.rated_power)

        # 一阶惯性响应(毫秒级)
        alpha = 1 - np.exp(-dt / self.time_constant)
        self._power_output += alpha * (power_target - self._power_output)

        # 更新SOC
        energy_change = self._power_output * dt / 3600  # MWh
        if self._power_output > 0:  # 放电
            energy_change = -energy_change / 0.95  # 放电效率
        else:  # 充电
            energy_change = -energy_change * 0.95  # 充电效率

        self._soc = np.clip(self._soc + energy_change / self.rated_energy, 0.0, 1.0)

        # 计算残差(需要下层承接的功率)
        # 如果SC功率受限,残差较大
        power_residual = power_droop - self._power_output

        return LayerOutput(
            power_output=self._power_output,
            power_residual=power_residual,
            soc=self._soc,
            status="normal" if self.soc_low_limit < self._soc < self.soc_high_limit else "limited"
        )

    def reset(self, soc: float = 0.5):
        """重置状态"""
        self._soc = soc
        self._power_output = 0.0


# ==================== 第二层: 锂电池低通滤波控制 ====================

class Layer2_BESSFilterController:
    """
    第二层控制器: 锂电池低通滤波控制

    核心算法:
    1. 低通滤波: P_bess = LPF(P_residual)
    2. SOC管理: 考虑SOC均衡策略

    滤波器设计:
    H(s) = 1 / (τs + 1)
    τ = 1-5s (平滑高频波动)

    功能:
    - 承接SC传递的残差功率
    - 平滑功率波动
    - 准备将功率移交给PSH/水电
    """

    def __init__(
        self,
        rated_power: float = 20.0,       # 额定功率(MW)
        rated_energy: float = 40.0,       # 额定能量(MWh)
        filter_time_constant: float = 2.0,  # 滤波器时间常数(s)
        response_time_constant: float = 0.5,  # 响应时间常数(s)
        ramp_rate: float = 0.2,           # 爬坡速率(p.u./s)
        soc_high_limit: float = 0.9,
        soc_low_limit: float = 0.1,
        soc_target: float = 0.5           # SOC目标值
    ):
        self.rated_power = rated_power
        self.rated_energy = rated_energy
        self.filter_tau = filter_time_constant
        self.response_tau = response_time_constant
        self.ramp_rate = ramp_rate
        self.soc_high_limit = soc_high_limit
        self.soc_low_limit = soc_low_limit
        self.soc_target = soc_target

        # 状态变量
        self._soc = 0.5
        self._power_output = 0.0
        self._filtered_power = 0.0  # 滤波后的功率
        self._power_history: List[float] = []

    def get_soc(self) -> float:
        return self._soc

    def get_power(self) -> float:
        return self._power_output

    def _apply_lowpass_filter(self, power_input: float, dt: float) -> float:
        """应用低通滤波"""
        alpha = 1 - np.exp(-dt / self.filter_tau)
        self._filtered_power += alpha * (power_input - self._filtered_power)
        return self._filtered_power

    def _calculate_soc_correction(self) -> float:
        """
        计算SOC校正功率
        当SOC偏离目标时,增加小功率进行校正
        """
        soc_error = self._soc - self.soc_target
        # 比例校正
        correction = -soc_error * self.rated_power * 0.1
        return correction

    def step(
        self,
        dt: float,
        power_residual: float,  # 来自Layer1的残差
        power_setpoint: Optional[float] = None,
        layer3_ready: bool = False  # Layer3是否准备好接管
    ) -> LayerOutput:
        """
        执行一步控制

        Args:
            dt: 时间步长
            power_residual: 来自Layer1的残差功率
            power_setpoint: 外部功率设定
            layer3_ready: Layer3是否准备好

        Returns:
            LayerOutput
        """
        # 低通滤波平滑波动
        filtered_power = self._apply_lowpass_filter(power_residual, dt)

        # 添加SOC校正
        soc_correction = self._calculate_soc_correction()

        # 如果有外部设定,使用外部设定
        if power_setpoint is not None:
            power_target = power_setpoint + soc_correction
        else:
            power_target = filtered_power + soc_correction

        # SOC保护
        if power_target > 0 and self._soc <= self.soc_low_limit:
            power_target = 0
        elif power_target < 0 and self._soc >= self.soc_high_limit:
            power_target = 0

        # 爬坡限制
        max_change = self.ramp_rate * self.rated_power * dt
        if abs(power_target - self._power_output) > max_change:
            power_target = self._power_output + np.sign(power_target - self._power_output) * max_change

        # 功率限幅
        power_target = np.clip(power_target, -self.rated_power, self.rated_power)

        # 响应动态
        alpha = 1 - np.exp(-dt / self.response_tau)
        self._power_output += alpha * (power_target - self._power_output)

        # 更新SOC
        energy_change = self._power_output * dt / 3600
        efficiency = 0.95
        if self._power_output > 0:
            energy_change = -energy_change / efficiency
        else:
            energy_change = -energy_change * efficiency

        self._soc = np.clip(self._soc + energy_change / self.rated_energy, 0.0, 1.0)

        # 计算传递给Layer3的残差
        # 如果Layer3准备好了,逐渐减少BESS输出
        if layer3_ready:
            power_residual_to_l3 = self._power_output * 0.5  # 逐步移交
        else:
            power_residual_to_l3 = filtered_power - self._power_output

        return LayerOutput(
            power_output=self._power_output,
            power_residual=power_residual_to_l3,
            soc=self._soc,
            status="normal" if self.soc_low_limit < self._soc < self.soc_high_limit else "limited"
        )

    def reset(self, soc: float = 0.5):
        self._soc = soc
        self._power_output = 0.0
        self._filtered_power = 0.0


# ==================== 第三层: MPC协同控制 ====================

@dataclass
class MPCConfig:
    """MPC配置参数"""
    prediction_horizon: int = 12      # 预测时域步数
    control_horizon: int = 4          # 控制时域步数
    time_step: float = 300.0          # 时间步长(s) = 5min
    frequency_weight: float = 100.0   # 频率偏差权重
    power_weight: float = 1.0         # 功率跟踪权重
    psh_switch_penalty: float = 50.0  # PSH切换惩罚
    efficiency_weight: float = 10.0   # 效率权重


class Layer3_MPCCoordinator:
    """
    第三层控制器: PSH与常规水电MPC协同控制

    MPC优化问题:
    ===========
    目标函数:
    J = Σ[ w_f * Δf² + w_p * (P_gen - P_demand)² + w_η * (1-η) + w_sw * N_switch ]

    约束条件:
    1. 功率平衡: P_gen + P_psh + P_hydro = P_load - P_renewable
    2. PSH约束: 模式切换时间、最短运行时间、水位限制
    3. 水电约束: 爬坡率、最小出力
    4. 频率约束: |Δf| < Δf_max

    决策变量:
    - PSH运行模式(抽水/发电/停机)
    - PSH功率设定
    - 常规水电功率设定
    """

    def __init__(
        self,
        psh_rated_power_gen: float = 100.0,
        psh_rated_power_pump: float = 90.0,
        hydro_rated_power: float = 200.0,
        hydro_min_power: float = 60.0,
        config: Optional[MPCConfig] = None
    ):
        self.psh_rated_gen = psh_rated_power_gen
        self.psh_rated_pump = psh_rated_power_pump
        self.hydro_rated = hydro_rated_power
        self.hydro_min = hydro_min_power
        self.config = config or MPCConfig()

        # 状态
        self._psh_power_setpoint = 0.0
        self._hydro_power_setpoint = 0.0
        self._psh_mode_request = "stopped"  # "stopped", "pumping", "generating"
        self._optimization_result: Optional[Dict] = None

        # 预测器状态
        self._net_load_forecast: List[float] = []
        self._last_optimization_time = 0.0

    def update_forecast(self, net_load_forecast: List[float]):
        """更新净负荷预测"""
        self._net_load_forecast = net_load_forecast

    def _solve_optimization(
        self,
        current_net_load: float,
        reservoir_level: float,
        psh_current_mode: str,
        hydro_current_power: float
    ) -> Dict:
        """
        求解MPC优化问题(简化启发式算法)

        实际应用中可使用更复杂的优化求解器(如CVXPY, Gurobi等)

        Returns:
            优化结果
        """
        # 简化优化:基于净负荷和预测决策
        n_steps = min(self.config.prediction_horizon, len(self._net_load_forecast))

        # 预测未来净负荷趋势
        if n_steps > 0:
            avg_future_net_load = np.mean(self._net_load_forecast[:n_steps])
            max_future_net_load = max(self._net_load_forecast[:n_steps])
            min_future_net_load = min(self._net_load_forecast[:n_steps])
        else:
            avg_future_net_load = current_net_load
            max_future_net_load = current_net_load
            min_future_net_load = current_net_load

        # 决策逻辑
        psh_mode = psh_current_mode
        psh_power = 0.0
        hydro_power = hydro_current_power

        # PSH决策
        if current_net_load > 50 and reservoir_level > 0.25:
            # 高净负荷,需要发电
            psh_mode = "generating"
            psh_power = min(self.psh_rated_gen, current_net_load * 0.5)
        elif current_net_load < -30 and reservoir_level < 0.85:
            # 净负荷为负(新能源过剩),抽水储能
            psh_mode = "pumping"
            psh_power = min(self.psh_rated_pump, abs(current_net_load) * 0.6)
        elif abs(current_net_load) < 20:
            # 净负荷较小,可停机节能
            psh_mode = "stopped"
            psh_power = 0.0

        # 水电决策: 基载 + 调峰
        base_load_ratio = 0.4  # 基载比例
        hydro_base = self.hydro_rated * base_load_ratio

        if psh_mode == "generating":
            # PSH发电时,水电减少出力
            hydro_target = max(self.hydro_min, current_net_load - psh_power)
        elif psh_mode == "pumping":
            # PSH抽水时,水电需要补充
            hydro_target = current_net_load + psh_power
        else:
            # PSH停机,水电承担全部调峰
            hydro_target = current_net_load

        hydro_power = np.clip(hydro_target, self.hydro_min, self.hydro_rated)

        # 计算预测的频率偏差
        total_gen = hydro_power + (psh_power if psh_mode == "generating" else 0)
        power_imbalance = total_gen - current_net_load
        if psh_mode == "pumping":
            power_imbalance -= psh_power

        return {
            'psh_mode': psh_mode,
            'psh_power': psh_power,
            'hydro_power': hydro_power,
            'predicted_imbalance': power_imbalance,
            'optimization_status': 'feasible'
        }

    def step(
        self,
        dt: float,
        current_net_load: float,
        reservoir_level: float,
        psh_current_mode: str,
        hydro_current_power: float,
        power_residual_from_l2: float = 0.0,
        frequency_deviation: float = 0.0
    ) -> Dict:
        """
        执行一步MPC控制

        Args:
            dt: 时间步长
            current_net_load: 当前净负荷
            reservoir_level: PSH水库水位
            psh_current_mode: PSH当前模式
            hydro_current_power: 水电当前功率
            power_residual_from_l2: 来自Layer2的残差
            frequency_deviation: 频率偏差

        Returns:
            控制决策
        """
        # 定期执行优化(每个MPC周期)
        self._optimization_result = self._solve_optimization(
            current_net_load + power_residual_from_l2,  # 考虑残差
            reservoir_level,
            psh_current_mode,
            hydro_current_power
        )

        self._psh_mode_request = self._optimization_result['psh_mode']
        self._psh_power_setpoint = self._optimization_result['psh_power']
        self._hydro_power_setpoint = self._optimization_result['hydro_power']

        # 频率偏差校正(叠加在MPC结果上)
        if abs(frequency_deviation) > 0.1:
            freq_correction = -frequency_deviation * 50  # 50 MW/Hz
            if self._psh_mode_request == "generating":
                self._psh_power_setpoint += freq_correction
                self._psh_power_setpoint = np.clip(
                    self._psh_power_setpoint, 0, self.psh_rated_gen
                )
            else:
                self._hydro_power_setpoint += freq_correction
                self._hydro_power_setpoint = np.clip(
                    self._hydro_power_setpoint, self.hydro_min, self.hydro_rated
                )

        return {
            'psh_mode': self._psh_mode_request,
            'psh_power': self._psh_power_setpoint,
            'hydro_power': self._hydro_power_setpoint,
            'layer3_ready': True  # 表示Layer3已准备好接管
        }

    def get_psh_setpoint(self) -> Tuple[str, float]:
        """获取PSH设定值"""
        return self._psh_mode_request, self._psh_power_setpoint

    def get_hydro_setpoint(self) -> float:
        """获取水电设定值"""
        return self._hydro_power_setpoint


# ==================== 分层控制器总协调 ====================

class HierarchicalEnergyController:
    """
    多能互补系统分层控制器

    协调三层控制器,实现响应链解耦

    控制流程:
    ========
    1. Layer1(SC)响应频率变化
    2. Layer1输出残差传递给Layer2
    3. Layer2(BESS)滤波平滑
    4. Layer2输出残差传递给Layer3
    5. Layer3(MPC)调度PSH和水电
    6. 当Layer3准备好后,Layer2逐步移交功率
    7. Layer2卸载后,Layer1恢复待命

    ```
    频率偏差 -> [Layer1:SC] -> 残差 -> [Layer2:BESS] -> 残差 -> [Layer3:MPC]
                   ↓                       ↓                       ↓
               快速响应              平滑接管              调度决策
    ```
    """

    def __init__(
        self,
        layer1: Optional[Layer1_SCDroopController] = None,
        layer2: Optional[Layer2_BESSFilterController] = None,
        layer3: Optional[Layer3_MPCCoordinator] = None
    ):
        self.layer1 = layer1 or Layer1_SCDroopController()
        self.layer2 = layer2 or Layer2_BESSFilterController()
        self.layer3 = layer3 or Layer3_MPCCoordinator()

        # 协调状态
        self._layer3_ready = False
        self._handover_progress = 0.0  # 功率移交进度

    def step(
        self,
        dt: float,
        system_state: SystemState,
        reservoir_level: float,
        psh_current_mode: str,
        hydro_current_power: float,
        net_load_forecast: Optional[List[float]] = None
    ) -> Dict:
        """
        执行一步分层控制

        Args:
            dt: 时间步长
            system_state: 系统状态
            reservoir_level: PSH水库水位
            psh_current_mode: PSH当前模式
            hydro_current_power: 水电当前功率
            net_load_forecast: 净负荷预测

        Returns:
            控制输出(各层功率指令)
        """
        freq_dev = system_state.frequency_deviation
        rocof = 0.0  # 可从历史计算

        # ===== Layer 1: SC快速响应 =====
        l1_output = self.layer1.step(
            dt=dt,
            frequency_deviation=freq_dev,
            rocof=rocof
        )

        # ===== Layer 2: BESS平滑接管 =====
        l2_output = self.layer2.step(
            dt=dt,
            power_residual=l1_output.power_residual,
            layer3_ready=self._layer3_ready
        )

        # ===== Layer 3: MPC调度 =====
        if net_load_forecast:
            self.layer3.update_forecast(net_load_forecast)

        l3_output = self.layer3.step(
            dt=dt,
            current_net_load=system_state.net_load,
            reservoir_level=reservoir_level,
            psh_current_mode=psh_current_mode,
            hydro_current_power=hydro_current_power,
            power_residual_from_l2=l2_output.power_residual,
            frequency_deviation=freq_dev
        )

        self._layer3_ready = l3_output.get('layer3_ready', False)

        # 计算HESS总功率
        hess_power = l1_output.power_output + l2_output.power_output

        return {
            # Layer1输出
            'sc_power': l1_output.power_output,
            'sc_soc': l1_output.soc,
            'sc_status': l1_output.status,

            # Layer2输出
            'bess_power': l2_output.power_output,
            'bess_soc': l2_output.soc,
            'bess_status': l2_output.status,

            # Layer3输出
            'psh_mode': l3_output['psh_mode'],
            'psh_power': l3_output['psh_power'],
            'hydro_power': l3_output['hydro_power'],

            # 汇总
            'hess_power': hess_power,  # SC + BESS
            'total_controllable_power': hess_power + l3_output['psh_power'] + l3_output['hydro_power'],

            # 状态
            'layer3_ready': self._layer3_ready
        }

    def get_response_chain_status(self) -> Dict:
        """获取响应链状态"""
        return {
            'layer1_active': abs(self.layer1.get_power()) > 0.1,
            'layer2_active': abs(self.layer2.get_power()) > 0.1,
            'layer3_ready': self._layer3_ready,
            'sc_soc': self.layer1.get_soc(),
            'bess_soc': self.layer2.get_soc()
        }

    def reset(self):
        """重置所有控制器"""
        self.layer1.reset()
        self.layer2.reset()
        self._layer3_ready = False
        self._handover_progress = 0.0
