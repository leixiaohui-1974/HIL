# -*- coding: utf-8 -*-
"""
模型预测控制(MPC)优化求解器
Model Predictive Control Optimizer for Multi-Energy System

实现基于滚动时域优化的多能源协调调度:

优化问题:
=========
目标函数:
  min J = Σ[w_f·Δf² + w_p·(P_gen - P_demand)² + w_η·(1-η) + w_sw·N_switch + w_e·E_cost]

决策变量:
  - PSH运行模式序列: u_psh[k] ∈ {pump, gen, stop}
  - PSH功率序列: P_psh[k]
  - 水电功率序列: P_hydro[k]

约束条件:
  - 功率平衡: P_gen + P_psh + P_hydro + P_hess = P_load - P_renewable
  - PSH约束: 模式切换时间、最短运行时间、水位限制
  - 水电约束: P_min ≤ P_hydro ≤ P_max, 爬坡率限制
  - 储能约束: SOC_min ≤ SOC ≤ SOC_max

求解方法:
  1. 简化启发式求解(默认)
  2. 动态规划(可选)
  3. 二次规划QP(需要额外依赖)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from enum import Enum


# ==================== 配置参数 ====================

@dataclass
class MPCOptimizerConfig:
    """MPC优化器配置"""
    # 时域参数
    prediction_horizon: int = 24        # 预测时域步数
    control_horizon: int = 6            # 控制时域步数
    time_step: float = 300.0            # 时间步长(s) = 5min

    # 权重系数
    weight_frequency: float = 100.0     # 频率偏差权重
    weight_power_balance: float = 10.0  # 功率平衡权重
    weight_efficiency: float = 5.0      # 效率权重
    weight_mode_switch: float = 50.0    # 模式切换惩罚
    weight_energy_cost: float = 1.0     # 能量成本权重
    weight_soc_deviation: float = 20.0  # SOC偏离目标权重

    # SOC目标
    sc_soc_target: float = 0.5
    bess_soc_target: float = 0.5
    psh_level_target: float = 0.5

    # 约束参数
    frequency_max_deviation: float = 0.5  # 最大允许频率偏差(Hz)
    psh_min_run_time: int = 6            # PSH最短运行步数(对应30min)
    psh_mode_switch_dead_time: int = 2   # PSH切换死区步数


@dataclass
class MPCState:
    """MPC状态"""
    # 当前状态
    current_time: float = 0.0
    frequency: float = 50.0
    net_load: float = 0.0

    # PSH状态
    psh_mode: str = "stopped"     # "stopped", "pumping", "generating"
    psh_power: float = 0.0
    psh_level: float = 0.5
    psh_mode_time: int = 0        # 当前模式持续步数

    # 水电状态
    hydro_power: float = 100.0

    # 储能状态
    sc_soc: float = 0.5
    bess_soc: float = 0.5


@dataclass
class MPCPrediction:
    """MPC预测信息"""
    net_load_forecast: np.ndarray = field(default_factory=lambda: np.zeros(24))
    price_forecast: np.ndarray = field(default_factory=lambda: np.ones(24))
    renewable_forecast: np.ndarray = field(default_factory=lambda: np.zeros(24))


@dataclass
class MPCSolution:
    """MPC求解结果"""
    # 控制序列
    psh_mode_sequence: List[str] = field(default_factory=list)
    psh_power_sequence: np.ndarray = field(default_factory=lambda: np.array([]))
    hydro_power_sequence: np.ndarray = field(default_factory=lambda: np.array([]))
    hess_power_sequence: np.ndarray = field(default_factory=lambda: np.array([]))

    # 状态预测
    frequency_prediction: np.ndarray = field(default_factory=lambda: np.array([]))
    psh_level_prediction: np.ndarray = field(default_factory=lambda: np.array([]))

    # 优化指标
    objective_value: float = 0.0
    solve_time: float = 0.0
    feasible: bool = True
    status: str = "optimal"


# ==================== MPC优化器 ====================

class MPCOptimizer:
    """
    多能源系统MPC优化器

    实现滚动时域优化,为PSH和水电提供最优调度策略
    """

    def __init__(
        self,
        psh_power_gen: float = 100.0,
        psh_power_pump: float = 90.0,
        hydro_power_max: float = 200.0,
        hydro_power_min: float = 60.0,
        config: Optional[MPCOptimizerConfig] = None
    ):
        self.psh_gen = psh_power_gen
        self.psh_pump = psh_power_pump
        self.hydro_max = hydro_power_max
        self.hydro_min = hydro_power_min
        self.config = config or MPCOptimizerConfig()

        # 预计算参数
        self._precompute_parameters()

    def _precompute_parameters(self):
        """预计算优化参数"""
        cfg = self.config

        # 创建权重矩阵
        n = cfg.prediction_horizon
        self.Q_freq = cfg.weight_frequency * np.eye(n)
        self.Q_power = cfg.weight_power_balance * np.eye(n)
        self.Q_eff = cfg.weight_efficiency * np.eye(n)

    def _simulate_psh_dynamics(
        self,
        mode_sequence: List[str],
        power_sequence: np.ndarray,
        initial_level: float
    ) -> Tuple[np.ndarray, bool]:
        """
        模拟PSH动态

        Args:
            mode_sequence: 模式序列
            power_sequence: 功率序列
            initial_level: 初始水位

        Returns:
            (水位预测, 是否可行)
        """
        n = len(mode_sequence)
        level = np.zeros(n + 1)
        level[0] = initial_level

        dt = self.config.time_step / 3600  # 转换为小时

        for k in range(n):
            mode = mode_sequence[k]
            power = power_sequence[k]

            if mode == "generating":
                # 发电消耗水(简化: 水位变化 ∝ 功率 × 时间)
                level[k+1] = level[k] - power * dt / 1000
            elif mode == "pumping":
                # 抽水增加水位
                level[k+1] = level[k] + abs(power) * dt / 1000
            else:
                level[k+1] = level[k]

            # 检查水位约束
            if level[k+1] < 0.15 or level[k+1] > 0.95:
                return level[:n], False

        return level[:n], True

    def _evaluate_objective(
        self,
        state: MPCState,
        prediction: MPCPrediction,
        psh_mode_seq: List[str],
        psh_power_seq: np.ndarray,
        hydro_power_seq: np.ndarray
    ) -> float:
        """
        评估目标函数值

        Args:
            state: 当前状态
            prediction: 预测信息
            psh_mode_seq: PSH模式序列
            psh_power_seq: PSH功率序列
            hydro_power_seq: 水电功率序列

        Returns:
            目标函数值
        """
        cfg = self.config
        n = len(psh_mode_seq)
        J = 0.0

        # 模拟PSH水位
        level_seq, feasible = self._simulate_psh_dynamics(
            psh_mode_seq, psh_power_seq, state.psh_level
        )
        if not feasible:
            return 1e10  # 不可行解

        for k in range(n):
            net_load = prediction.net_load_forecast[k]
            mode = psh_mode_seq[k]
            psh_power = psh_power_seq[k]
            hydro_power = hydro_power_seq[k]

            # 功率平衡
            if mode == "generating":
                total_gen = hydro_power + psh_power
            elif mode == "pumping":
                total_gen = hydro_power - abs(psh_power)
            else:
                total_gen = hydro_power

            power_imbalance = total_gen - net_load
            J += cfg.weight_power_balance * power_imbalance ** 2

            # 效率惩罚(低效运行)
            if mode == "generating" and psh_power < 0.3 * self.psh_gen:
                J += cfg.weight_efficiency * (0.3 * self.psh_gen - psh_power) ** 2
            if hydro_power < 0.4 * self.hydro_max:
                J += cfg.weight_efficiency * (0.4 * self.hydro_max - hydro_power) ** 2

            # 水位偏离目标
            level_dev = level_seq[k] - cfg.psh_level_target
            J += cfg.weight_soc_deviation * level_dev ** 2

        # 模式切换惩罚
        mode_switches = 0
        for k in range(1, n):
            if psh_mode_seq[k] != psh_mode_seq[k-1]:
                mode_switches += 1
        J += cfg.weight_mode_switch * mode_switches

        return J

    def _generate_candidate_solutions(
        self,
        state: MPCState,
        prediction: MPCPrediction
    ) -> List[Tuple[List[str], np.ndarray, np.ndarray]]:
        """
        生成候选解集合

        使用启发式规则生成多个候选解
        """
        n = self.config.prediction_horizon
        candidates = []

        net_load = prediction.net_load_forecast

        # 策略1: 保持当前模式
        mode_seq = [state.psh_mode] * n
        psh_power = np.zeros(n)
        hydro_power = np.clip(net_load, self.hydro_min, self.hydro_max)
        candidates.append((mode_seq.copy(), psh_power.copy(), hydro_power.copy()))

        # 策略2: 基于净负荷的简单规则
        mode_seq = []
        psh_power = np.zeros(n)
        for k in range(n):
            if net_load[k] > 80:  # 高负荷,发电
                mode_seq.append("generating")
                psh_power[k] = min(self.psh_gen, net_load[k] - 80)
            elif net_load[k] < -30:  # 负净负荷(过剩),抽水
                mode_seq.append("pumping")
                psh_power[k] = min(self.psh_pump, abs(net_load[k] + 30))
            else:
                mode_seq.append("stopped")
                psh_power[k] = 0

        hydro_power = np.clip(net_load - psh_power, self.hydro_min, self.hydro_max)
        candidates.append((mode_seq.copy(), psh_power.copy(), hydro_power.copy()))

        # 策略3: 只使用发电模式
        mode_seq = []
        psh_power = np.zeros(n)
        for k in range(n):
            if net_load[k] > 50 and state.psh_level > 0.3:
                mode_seq.append("generating")
                psh_power[k] = min(self.psh_gen, net_load[k] * 0.3)
            else:
                mode_seq.append("stopped")
        hydro_power = np.clip(net_load - psh_power, self.hydro_min, self.hydro_max)
        candidates.append((mode_seq.copy(), psh_power.copy(), hydro_power.copy()))

        # 策略4: 只使用抽水模式
        mode_seq = []
        psh_power = np.zeros(n)
        for k in range(n):
            if net_load[k] < 20 and state.psh_level < 0.8:
                mode_seq.append("pumping")
                psh_power[k] = min(self.psh_pump, 50)
            else:
                mode_seq.append("stopped")
        hydro_power = np.clip(net_load + psh_power, self.hydro_min, self.hydro_max)
        candidates.append((mode_seq.copy(), psh_power.copy(), hydro_power.copy()))

        # 策略5: 峰谷优化(上午抽水,下午发电)
        mode_seq = []
        psh_power = np.zeros(n)
        for k in range(n):
            hour = (state.current_time / 3600 + k * self.config.time_step / 3600) % 24

            if 10 <= hour < 15 and state.psh_level < 0.8:  # 午间抽水
                mode_seq.append("pumping")
                psh_power[k] = self.psh_pump * 0.7
            elif 17 <= hour < 22 and state.psh_level > 0.3:  # 晚间发电
                mode_seq.append("generating")
                psh_power[k] = self.psh_gen * 0.8
            else:
                mode_seq.append("stopped")
                psh_power[k] = 0

        hydro_power = np.clip(net_load - psh_power, self.hydro_min, self.hydro_max)
        candidates.append((mode_seq.copy(), psh_power.copy(), hydro_power.copy()))

        return candidates

    def solve(
        self,
        state: MPCState,
        prediction: MPCPrediction
    ) -> MPCSolution:
        """
        求解MPC优化问题

        Args:
            state: 当前系统状态
            prediction: 预测信息

        Returns:
            MPCSolution
        """
        import time
        start_time = time.time()

        # 生成候选解
        candidates = self._generate_candidate_solutions(state, prediction)

        # 评估每个候选解
        best_J = float('inf')
        best_solution = None

        for mode_seq, psh_seq, hydro_seq in candidates:
            J = self._evaluate_objective(
                state, prediction,
                mode_seq, psh_seq, hydro_seq
            )

            if J < best_J:
                best_J = J
                best_solution = (mode_seq, psh_seq, hydro_seq)

        solve_time = time.time() - start_time

        if best_solution is None:
            return MPCSolution(
                feasible=False,
                status="infeasible",
                solve_time=solve_time
            )

        mode_seq, psh_seq, hydro_seq = best_solution

        # 计算状态预测
        level_pred, _ = self._simulate_psh_dynamics(
            mode_seq, psh_seq, state.psh_level
        )

        return MPCSolution(
            psh_mode_sequence=mode_seq,
            psh_power_sequence=psh_seq,
            hydro_power_sequence=hydro_seq,
            psh_level_prediction=level_pred,
            objective_value=best_J,
            solve_time=solve_time,
            feasible=True,
            status="optimal"
        )

    def get_next_control(
        self,
        state: MPCState,
        prediction: MPCPrediction
    ) -> Tuple[str, float, float]:
        """
        获取下一步控制动作(滚动时域)

        Returns:
            (PSH模式, PSH功率, 水电功率)
        """
        solution = self.solve(state, prediction)

        if not solution.feasible:
            # 返回保守控制
            return "stopped", 0.0, self.hydro_min

        # 返回第一步控制
        return (
            solution.psh_mode_sequence[0],
            solution.psh_power_sequence[0],
            solution.hydro_power_sequence[0]
        )


# ==================== 动态规划求解器 ====================

class DynamicProgrammingSolver:
    """
    动态规划求解器

    用于求解具有离散决策的最优控制问题
    """

    def __init__(
        self,
        psh_power_gen: float = 100.0,
        psh_power_pump: float = 90.0,
        hydro_power_max: float = 200.0,
        hydro_power_min: float = 60.0,
        n_psh_levels: int = 20,  # PSH水位离散化数量
        n_power_levels: int = 10  # 功率离散化数量
    ):
        self.psh_gen = psh_power_gen
        self.psh_pump = psh_power_pump
        self.hydro_max = hydro_power_max
        self.hydro_min = hydro_power_min

        # 离散化
        self.n_levels = n_psh_levels
        self.n_powers = n_power_levels

        # 状态空间
        self.level_grid = np.linspace(0.15, 0.95, n_psh_levels)
        self.psh_power_grid = np.linspace(0, psh_power_gen, n_power_levels)
        self.hydro_power_grid = np.linspace(hydro_power_min, hydro_power_max, n_power_levels)

        # 模式集合
        self.modes = ["stopped", "pumping", "generating"]

    def _get_level_index(self, level: float) -> int:
        """获取水位在网格中的索引"""
        return np.argmin(np.abs(self.level_grid - level))

    def _stage_cost(
        self,
        level: float,
        mode: str,
        psh_power: float,
        hydro_power: float,
        net_load: float,
        prev_mode: str
    ) -> float:
        """阶段成本函数"""
        # 功率平衡误差
        if mode == "generating":
            balance_error = (hydro_power + psh_power - net_load) ** 2
        elif mode == "pumping":
            balance_error = (hydro_power - psh_power - net_load) ** 2
        else:
            balance_error = (hydro_power - net_load) ** 2

        cost = 10 * balance_error

        # 模式切换惩罚
        if mode != prev_mode:
            cost += 50

        # 水位偏离中间值惩罚
        cost += 20 * (level - 0.5) ** 2

        # 低效运行惩罚
        if mode == "generating" and psh_power < 0.3 * self.psh_gen:
            cost += 5 * (0.3 * self.psh_gen - psh_power) ** 2

        return cost

    def solve_dp(
        self,
        initial_level: float,
        initial_mode: str,
        net_load_forecast: np.ndarray,
        dt: float = 300.0
    ) -> Tuple[List[str], np.ndarray, np.ndarray]:
        """
        使用动态规划求解

        Args:
            initial_level: 初始水位
            initial_mode: 初始模式
            net_load_forecast: 净负荷预测
            dt: 时间步长(s)

        Returns:
            (模式序列, PSH功率序列, 水电功率序列)
        """
        N = len(net_load_forecast)
        n_levels = self.n_levels
        n_modes = len(self.modes)

        # 值函数 V[k, i, m] = 从第k步状态(level_i, mode_m)到终点的最优成本
        V = np.full((N + 1, n_levels, n_modes), np.inf)

        # 终端成本
        for i in range(n_levels):
            for m in range(n_modes):
                V[N, i, m] = 20 * (self.level_grid[i] - 0.5) ** 2

        # 策略存储
        policy_mode = np.zeros((N, n_levels, n_modes), dtype=int)
        policy_psh = np.zeros((N, n_levels, n_modes))
        policy_hydro = np.zeros((N, n_levels, n_modes))

        # 后向递推
        dt_hours = dt / 3600

        for k in range(N - 1, -1, -1):
            net_load = net_load_forecast[k]

            for i in range(n_levels):
                level = self.level_grid[i]

                for m in range(n_modes):
                    current_mode = self.modes[m]
                    best_cost = np.inf
                    best_action = (0, 0, 0)  # (next_mode, psh_power, hydro_power)

                    # 遍历所有可能的动作
                    for next_m in range(n_modes):
                        next_mode = self.modes[next_m]

                        # 根据模式确定功率范围
                        if next_mode == "generating":
                            psh_range = self.psh_power_grid
                        elif next_mode == "pumping":
                            psh_range = self.psh_power_grid[:self.n_powers//2]  # 抽水功率较小
                        else:
                            psh_range = [0.0]

                        for psh_power in psh_range:
                            for hydro_power in self.hydro_power_grid:
                                # 计算下一步水位
                                if next_mode == "generating":
                                    next_level = level - psh_power * dt_hours / 1000
                                elif next_mode == "pumping":
                                    next_level = level + psh_power * dt_hours / 1000
                                else:
                                    next_level = level

                                # 检查水位约束
                                if next_level < 0.15 or next_level > 0.95:
                                    continue

                                next_i = self._get_level_index(next_level)

                                # 阶段成本 + 未来成本
                                stage = self._stage_cost(
                                    level, next_mode, psh_power,
                                    hydro_power, net_load, current_mode
                                )
                                future = V[k + 1, next_i, next_m]
                                total = stage + future

                                if total < best_cost:
                                    best_cost = total
                                    best_action = (next_m, psh_power, hydro_power)

                    V[k, i, m] = best_cost
                    policy_mode[k, i, m] = best_action[0]
                    policy_psh[k, i, m] = best_action[1]
                    policy_hydro[k, i, m] = best_action[2]

        # 前向仿真提取最优轨迹
        mode_sequence = []
        psh_sequence = []
        hydro_sequence = []

        level = initial_level
        level_idx = self._get_level_index(level)
        mode_idx = self.modes.index(initial_mode)

        for k in range(N):
            next_mode_idx = policy_mode[k, level_idx, mode_idx]
            psh_power = policy_psh[k, level_idx, mode_idx]
            hydro_power = policy_hydro[k, level_idx, mode_idx]

            mode_sequence.append(self.modes[next_mode_idx])
            psh_sequence.append(psh_power)
            hydro_sequence.append(hydro_power)

            # 更新状态
            mode_idx = next_mode_idx
            if mode_sequence[-1] == "generating":
                level -= psh_power * dt_hours / 1000
            elif mode_sequence[-1] == "pumping":
                level += psh_power * dt_hours / 1000

            level_idx = self._get_level_index(level)

        return mode_sequence, np.array(psh_sequence), np.array(hydro_sequence)


# ==================== 经济调度优化器 ====================

class EconomicDispatcher:
    """
    经济调度优化器

    考虑分时电价的经济优化调度
    """

    def __init__(
        self,
        psh_efficiency_gen: float = 0.85,
        psh_efficiency_pump: float = 0.80
    ):
        self.eta_gen = psh_efficiency_gen
        self.eta_pump = psh_efficiency_pump

        # 典型分时电价(元/kWh)
        self.price_profile = self._create_price_profile()

    def _create_price_profile(self) -> np.ndarray:
        """创建分时电价曲线"""
        # 24小时电价(峰谷平)
        prices = np.zeros(24)

        # 谷时段: 23:00-07:00 (低价)
        prices[23:24] = 0.3
        prices[0:7] = 0.3

        # 平时段: 07:00-10:00, 15:00-18:00, 21:00-23:00
        prices[7:10] = 0.6
        prices[15:18] = 0.6
        prices[21:23] = 0.6

        # 峰时段: 10:00-15:00, 18:00-21:00 (高价)
        prices[10:15] = 1.0
        prices[18:21] = 1.0

        return prices

    def get_price(self, hour: float) -> float:
        """获取指定时刻的电价"""
        hour_idx = int(hour) % 24
        return self.price_profile[hour_idx]

    def calculate_arbitrage_profit(
        self,
        pump_hours: List[int],
        gen_hours: List[int],
        psh_power: float
    ) -> float:
        """
        计算套利收益

        Args:
            pump_hours: 抽水时段
            gen_hours: 发电时段
            psh_power: PSH功率(MW)

        Returns:
            收益(元/h)
        """
        # 抽水成本
        pump_cost = sum(self.price_profile[h] for h in pump_hours) * psh_power / self.eta_pump

        # 发电收益
        gen_revenue = sum(self.price_profile[h] for h in gen_hours) * psh_power * self.eta_gen

        return gen_revenue - pump_cost

    def optimize_schedule(
        self,
        available_hours: int = 24,
        psh_capacity_hours: float = 6.0
    ) -> Tuple[List[int], List[int]]:
        """
        优化抽水/发电调度

        Args:
            available_hours: 可调度小时数
            psh_capacity_hours: PSH等效满发小时数

        Returns:
            (最优抽水时段, 最优发电时段)
        """
        # 按电价排序
        price_with_hour = [(self.price_profile[h], h) for h in range(24)]
        price_with_hour.sort()

        # 选择最低电价时段抽水
        n_pump_hours = int(psh_capacity_hours / self.eta_pump)
        pump_hours = [h for _, h in price_with_hour[:n_pump_hours]]

        # 选择最高电价时段发电
        n_gen_hours = int(psh_capacity_hours * self.eta_gen)
        gen_hours = [h for _, h in price_with_hour[-n_gen_hours:]]

        return sorted(pump_hours), sorted(gen_hours)
