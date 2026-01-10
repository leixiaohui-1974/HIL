# -*- coding: utf-8 -*-
"""
控制器参数优化模块
Controller Parameter Tuning Module

本模块提供:
1. 参数优化策略
2. 参数敏感性分析
3. 自动参数整定工具
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum, auto


@dataclass
class OptimizedControllerParams:
    """
    优化后的控制器参数

    基于以下分析确定:
    1. 系统基础功率1000MW
    2. 频率偏差目标: ±0.5Hz以内
    3. 频率恢复时间: <60s
    4. 平衡响应速度与稳定性
    """

    # ===== 第一层: 超级电容下垂控制 =====
    sc_rated_power: float = 15.0        # 额定功率(MW) - 增加容量
    sc_rated_energy: float = 0.75       # 额定能量(MWh) - 3分钟满功率
    sc_droop_gain: float = 30.0         # 下垂系数(MW/Hz) - 适中响应(避免过冲)
    sc_damping_gain: float = 8.0        # 阻尼系数(MW·s/Hz) - 抑制RoCoF
    sc_time_constant: float = 0.01      # 响应时间(s) - 10ms
    sc_deadband: float = 0.02           # 频率死区(Hz) - 适中死区

    # ===== 第二层: 锂电池滤波控制 =====
    bess_rated_power: float = 25.0      # 额定功率(MW) - 适度增加
    bess_rated_energy: float = 50.0     # 额定能量(MWh)
    bess_filter_tau: float = 1.0        # 滤波时间常数(s) - 中等速度
    bess_response_tau: float = 0.3      # 响应时间常数(s)
    bess_ramp_rate: float = 0.4         # 爬坡速率(p.u./s)

    # ===== 第三层: MPC协同控制 =====
    mpc_freq_weight: float = 150.0      # 频率权重
    mpc_power_weight: float = 1.0       # 功率权重
    mpc_freq_correction: float = 80.0   # 频率校正增益(MW/Hz) - 降低
    mpc_freq_threshold: float = 0.08    # 频率校正阈值(Hz)

    # ===== 电网参数 =====
    grid_inertia: float = 7.0           # 惯量常数H(s)
    grid_damping: float = 1.5           # 阻尼系数D(p.u.)
    grid_base_power: float = 1000.0     # 基准功率(MW)

    # ===== 调频参数 =====
    agc_kp: float = 80.0                # AGC比例增益
    agc_ki: float = 15.0                # AGC积分增益
    pfr_droop: float = 0.045            # 一次调频下垂


@dataclass
class DefaultControllerParams:
    """默认控制器参数(未优化)"""

    # SC参数
    sc_rated_power: float = 10.0
    sc_rated_energy: float = 0.5
    sc_droop_gain: float = 20.0
    sc_damping_gain: float = 5.0
    sc_time_constant: float = 0.01
    sc_deadband: float = 0.02

    # BESS参数
    bess_rated_power: float = 20.0
    bess_rated_energy: float = 40.0
    bess_filter_tau: float = 2.0
    bess_response_tau: float = 0.5
    bess_ramp_rate: float = 0.2

    # MPC参数
    mpc_freq_weight: float = 100.0
    mpc_power_weight: float = 1.0
    mpc_freq_correction: float = 50.0
    mpc_freq_threshold: float = 0.1

    # 电网参数
    grid_inertia: float = 6.0
    grid_damping: float = 1.0
    grid_base_power: float = 1000.0

    # 调频参数
    agc_kp: float = 50.0
    agc_ki: float = 10.0
    pfr_droop: float = 0.05


class ParameterSensitivityAnalyzer:
    """
    参数敏感性分析器

    分析各控制器参数对频率稳定性的影响
    """

    def __init__(self):
        self.base_params = DefaultControllerParams()
        self.sensitivity_results: Dict[str, List[Dict]] = {}

    def analyze_parameter(
        self,
        param_name: str,
        param_range: List[float],
        simulation_func: Callable,
        metric_func: Callable
    ) -> List[Dict]:
        """
        分析单个参数的敏感性

        Args:
            param_name: 参数名称
            param_range: 参数取值范围
            simulation_func: 仿真函数
            metric_func: 性能指标计算函数

        Returns:
            敏感性分析结果列表
        """
        results = []

        for value in param_range:
            # 设置参数
            params = DefaultControllerParams()
            setattr(params, param_name, value)

            # 运行仿真
            sim_result = simulation_func(params)

            # 计算指标
            metrics = metric_func(sim_result)

            results.append({
                'param_value': value,
                'freq_dev_max': metrics.get('freq_dev_max', 0),
                'freq_dev_rms': metrics.get('freq_dev_rms', 0),
                'settling_time': metrics.get('settling_time', 0),
                'overshoot': metrics.get('overshoot', 0)
            })

        self.sensitivity_results[param_name] = results
        return results

    def compute_sensitivity_coefficient(
        self,
        param_name: str,
        metric_name: str = 'freq_dev_rms'
    ) -> float:
        """
        计算敏感性系数

        敏感性系数 = Δ指标% / Δ参数%

        Args:
            param_name: 参数名称
            metric_name: 性能指标名称

        Returns:
            敏感性系数
        """
        if param_name not in self.sensitivity_results:
            return 0.0

        results = self.sensitivity_results[param_name]
        if len(results) < 2:
            return 0.0

        # 取首尾计算变化率
        first = results[0]
        last = results[-1]

        param_change = (last['param_value'] - first['param_value']) / first['param_value']
        metric_change = (last[metric_name] - first[metric_name]) / first[metric_name]

        if abs(param_change) < 1e-6:
            return 0.0

        return metric_change / param_change

    def get_critical_parameters(self, threshold: float = 0.5) -> List[str]:
        """
        获取关键参数(敏感性系数超过阈值)

        Args:
            threshold: 敏感性系数阈值

        Returns:
            关键参数名称列表
        """
        critical = []

        for param_name in self.sensitivity_results:
            sensitivity = abs(self.compute_sensitivity_coefficient(param_name))
            if sensitivity > threshold:
                critical.append(param_name)

        return critical


class AdaptiveParameterTuner:
    """
    自适应参数整定器

    基于运行数据动态调整控制器参数
    """

    def __init__(
        self,
        initial_params: Optional[OptimizedControllerParams] = None
    ):
        self.params = initial_params or OptimizedControllerParams()

        # 性能目标
        self.target_freq_dev_max: float = 0.2  # Hz
        self.target_freq_dev_rms: float = 0.1  # Hz
        self.target_settling_time: float = 30.0  # s

        # 学习率
        self.learning_rate: float = 0.1

        # 历史性能
        self.performance_history: List[Dict] = []

    def evaluate_performance(
        self,
        freq_deviation: np.ndarray,
        time_array: np.ndarray
    ) -> Dict:
        """
        评估频率性能

        Args:
            freq_deviation: 频率偏差序列
            time_array: 时间序列

        Returns:
            性能指标字典
        """
        freq_dev_max = np.max(np.abs(freq_deviation))
        freq_dev_rms = np.sqrt(np.mean(freq_deviation ** 2))
        freq_dev_mean = np.mean(freq_deviation)

        # 计算稳定时间(频率回到±0.1Hz)
        settling_idx = len(freq_deviation)
        for i in range(len(freq_deviation) - 1, -1, -1):
            if abs(freq_deviation[i]) > 0.1:
                settling_idx = i
                break
        settling_time = time_array[settling_idx] if settling_idx < len(time_array) else time_array[-1]

        # 计算正常频率时间占比
        normal_mask = np.abs(freq_deviation) < 0.5
        normal_ratio = np.sum(normal_mask) / len(freq_deviation)

        return {
            'freq_dev_max': freq_dev_max,
            'freq_dev_rms': freq_dev_rms,
            'freq_dev_mean': freq_dev_mean,
            'settling_time': settling_time,
            'normal_ratio': normal_ratio
        }

    def update_parameters(self, performance: Dict) -> bool:
        """
        根据性能反馈更新参数

        Args:
            performance: 当前性能指标

        Returns:
            是否更新了参数
        """
        updated = False

        # 记录历史
        self.performance_history.append(performance)

        # 如果频率偏差过大,增加下垂增益
        if performance['freq_dev_max'] > self.target_freq_dev_max:
            ratio = performance['freq_dev_max'] / self.target_freq_dev_max

            # 增加SC下垂增益
            self.params.sc_droop_gain *= (1 + self.learning_rate * (ratio - 1))
            self.params.sc_droop_gain = min(self.params.sc_droop_gain, 100.0)

            # 增加BESS响应速度
            self.params.bess_filter_tau *= (1 - self.learning_rate * (ratio - 1) * 0.5)
            self.params.bess_filter_tau = max(self.params.bess_filter_tau, 0.1)

            # 增加MPC频率校正
            self.params.mpc_freq_correction *= (1 + self.learning_rate * (ratio - 1))
            self.params.mpc_freq_correction = min(self.params.mpc_freq_correction, 200.0)

            updated = True

        # 如果稳定时间过长,增加阻尼
        if performance['settling_time'] > self.target_settling_time:
            ratio = performance['settling_time'] / self.target_settling_time

            # 增加SC阻尼
            self.params.sc_damping_gain *= (1 + self.learning_rate * (ratio - 1))
            self.params.sc_damping_gain = min(self.params.sc_damping_gain, 20.0)

            # 增加电网阻尼
            self.params.grid_damping *= (1 + self.learning_rate * (ratio - 1) * 0.5)
            self.params.grid_damping = min(self.params.grid_damping, 5.0)

            updated = True

        return updated

    def get_optimized_params(self) -> OptimizedControllerParams:
        """获取当前优化后的参数"""
        return self.params


def calculate_droop_requirements(
    base_power_mw: float,
    max_freq_deviation_hz: float = 0.5,
    max_power_imbalance_ratio: float = 0.1
) -> Dict[str, float]:
    """
    计算满足频率要求的下垂参数

    基于下垂控制方程:
    Δf/f_nom = -R * ΔP/P_rated

    Args:
        base_power_mw: 系统基准功率(MW)
        max_freq_deviation_hz: 最大允许频率偏差(Hz)
        max_power_imbalance_ratio: 最大功率不平衡比例

    Returns:
        推荐参数字典
    """
    f_nom = 50.0

    # 所需的总下垂响应
    # Δf = ΔP / K_total
    # K_total = ΔP / Δf
    max_power_imbalance = base_power_mw * max_power_imbalance_ratio
    required_droop_gain = max_power_imbalance / max_freq_deviation_hz  # MW/Hz

    # 分配给各层
    # 快速层(SC): 30% - 快速响应小功率
    # 中速层(BESS): 40% - 主力响应
    # 慢速层(Hydro+PSH): 30% - 持续支撑

    sc_droop = required_droop_gain * 0.3
    bess_droop = required_droop_gain * 0.4
    slow_droop = required_droop_gain * 0.3

    # 确保各层功率容量足够
    # SC需要覆盖2秒内的响应
    sc_energy_requirement = (sc_droop * max_freq_deviation_hz * 2) / 3600  # MWh

    # BESS需要覆盖60秒内的响应
    bess_energy_requirement = (bess_droop * max_freq_deviation_hz * 60) / 3600  # MWh

    return {
        'total_droop_gain': required_droop_gain,
        'sc_droop_gain': sc_droop,
        'bess_droop_gain': bess_droop,
        'slow_droop_gain': slow_droop,
        'sc_rated_power': sc_droop * 0.5,  # 假设最大0.5Hz偏差时的功率
        'sc_rated_energy': max(0.5, sc_energy_requirement * 2),
        'bess_rated_power': bess_droop * 0.5,
        'bess_rated_energy': max(20, bess_energy_requirement * 2)
    }


def get_recommended_params_for_system(
    system_capacity_mw: float,
    renewable_ratio: float = 0.3,
    freq_quality: str = "standard"
) -> OptimizedControllerParams:
    """
    根据系统配置获取推荐参数

    Args:
        system_capacity_mw: 系统装机容量(MW)
        renewable_ratio: 新能源占比
        freq_quality: 频率质量要求 ("relaxed", "standard", "strict")

    Returns:
        推荐的优化参数
    """
    # 频率质量对应的偏差限制
    freq_limits = {
        "relaxed": 1.0,      # ±1.0 Hz
        "standard": 0.5,     # ±0.5 Hz
        "strict": 0.2        # ±0.2 Hz
    }

    max_freq_dev = freq_limits.get(freq_quality, 0.5)

    # 新能源占比越高,需要更强的调频能力
    capacity_factor = 1.0 + renewable_ratio

    # 计算基础要求
    reqs = calculate_droop_requirements(
        system_capacity_mw,
        max_freq_dev,
        0.1 * capacity_factor
    )

    # 创建优化参数
    params = OptimizedControllerParams()

    # SC参数
    params.sc_rated_power = max(15.0, reqs['sc_rated_power'])
    params.sc_rated_energy = max(0.75, reqs['sc_rated_energy'])
    params.sc_droop_gain = reqs['sc_droop_gain']

    # 严格质量要求时,减小死区
    if freq_quality == "strict":
        params.sc_deadband = 0.005
        params.sc_damping_gain = 15.0
    elif freq_quality == "relaxed":
        params.sc_deadband = 0.02
        params.sc_damping_gain = 5.0

    # BESS参数
    params.bess_rated_power = max(30.0, reqs['bess_rated_power'])
    params.bess_rated_energy = max(60.0, reqs['bess_rated_energy'])

    # 高新能源占比时,加快BESS响应
    if renewable_ratio > 0.4:
        params.bess_filter_tau = 0.3
        params.bess_ramp_rate = 0.8

    # MPC参数
    params.mpc_freq_correction = reqs['slow_droop_gain'] * 2
    if freq_quality == "strict":
        params.mpc_freq_weight = 300.0
        params.mpc_freq_threshold = 0.02

    # 电网参数
    # 新能源占比高时,等效惯量降低,需要更多阻尼
    params.grid_damping = 2.0 + renewable_ratio * 2

    return params


# 预设参数配置
PARAM_PRESETS = {
    "default": DefaultControllerParams(),
    "optimized": OptimizedControllerParams(),
    "high_renewable": get_recommended_params_for_system(1000, 0.5, "standard"),
    "strict_frequency": get_recommended_params_for_system(1000, 0.3, "strict"),
    "relaxed": get_recommended_params_for_system(1000, 0.2, "relaxed")
}
