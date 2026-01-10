# -*- coding: utf-8 -*-
"""
多场景对比分析模块
Multi-Scenario Comparison Analysis Module

本模块提供:
1. 预定义典型场景
2. 场景批量仿真
3. 对比分析报告生成
4. 敏感性分析
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum, auto
import time

from .simulation import SimulationConfig, SimulationResult, MultiEnergySimulator
from .parameter_tuning import OptimizedControllerParams, DefaultControllerParams


class ScenarioType(Enum):
    """场景类型枚举"""
    TYPICAL_DAY = auto()           # 典型日
    HIGH_RENEWABLE = auto()        # 高新能源出力
    LOW_RENEWABLE = auto()         # 低新能源出力
    PEAK_LOAD = auto()             # 高负荷日
    VALLEY_LOAD = auto()           # 低负荷日
    EXTREME_WEATHER = auto()       # 极端天气
    FREQUENCY_EVENT = auto()       # 频率事件
    PSH_MAINTENANCE = auto()       # PSH检修
    GRID_FAULT = auto()            # 电网故障


@dataclass
class ScenarioDefinition:
    """场景定义"""
    name: str                       # 场景名称
    description: str                # 场景描述
    config: SimulationConfig        # 仿真配置
    scenario_type: ScenarioType     # 场景类型
    tags: List[str] = field(default_factory=list)  # 标签


@dataclass
class ScenarioResult:
    """场景仿真结果"""
    scenario_name: str
    simulation_result: SimulationResult
    execution_time: float           # 执行时间(s)
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ComparisonReport:
    """对比分析报告"""
    scenarios: List[str]
    metrics_table: Dict[str, Dict[str, float]]  # {metric: {scenario: value}}
    best_scenario: Dict[str, str]   # {metric: scenario_name}
    ranking: Dict[str, List[str]]   # {metric: [ranked scenarios]}
    summary: str


class ScenarioLibrary:
    """
    场景库

    提供预定义的典型场景配置
    """

    @staticmethod
    def get_typical_day() -> ScenarioDefinition:
        """典型日场景"""
        return ScenarioDefinition(
            name="typical_day",
            description="典型日运行场景,代表平均负荷和新能源条件",
            config=SimulationConfig(
                duration=86400.0,
                time_step=10.0,
                base_load=250.0,
                load_peak_ratio=1.3,
                load_valley_ratio=0.7,
                wind_capacity=50.0,
                solar_capacity=30.0
            ),
            scenario_type=ScenarioType.TYPICAL_DAY,
            tags=["baseline", "reference"]
        )

    @staticmethod
    def get_high_renewable() -> ScenarioDefinition:
        """高新能源出力场景"""
        return ScenarioDefinition(
            name="high_renewable",
            description="高新能源出力日,风光资源丰富",
            config=SimulationConfig(
                duration=86400.0,
                time_step=10.0,
                base_load=250.0,
                load_peak_ratio=1.3,
                wind_capacity=80.0,      # 增加风电
                solar_capacity=50.0,     # 增加光伏
                wind_turbulence=0.05     # 低湍流(稳定风况)
            ),
            scenario_type=ScenarioType.HIGH_RENEWABLE,
            tags=["renewable", "high_penetration"]
        )

    @staticmethod
    def get_low_renewable() -> ScenarioDefinition:
        """低新能源出力场景"""
        return ScenarioDefinition(
            name="low_renewable",
            description="低新能源出力日,风光资源匮乏",
            config=SimulationConfig(
                duration=86400.0,
                time_step=10.0,
                base_load=250.0,
                load_peak_ratio=1.3,
                wind_capacity=50.0,
                solar_capacity=30.0,
                wind_turbulence=0.25     # 高湍流(不稳定)
            ),
            scenario_type=ScenarioType.LOW_RENEWABLE,
            tags=["renewable", "low_output"]
        )

    @staticmethod
    def get_peak_load() -> ScenarioDefinition:
        """高负荷场景"""
        return ScenarioDefinition(
            name="peak_load",
            description="高负荷日,考验系统调峰能力",
            config=SimulationConfig(
                duration=86400.0,
                time_step=10.0,
                base_load=280.0,         # 提高基础负荷
                load_peak_ratio=1.4,     # 提高峰值比
                load_valley_ratio=0.6,
                hydro_power=280.0,       # 增加水电容量
                psh_power_gen=120.0      # 增加PSH容量
            ),
            scenario_type=ScenarioType.PEAK_LOAD,
            tags=["stress_test", "peak_shaving"]
        )

    @staticmethod
    def get_valley_load() -> ScenarioDefinition:
        """低负荷场景"""
        return ScenarioDefinition(
            name="valley_load",
            description="低负荷日,考验系统吸纳能力",
            config=SimulationConfig(
                duration=86400.0,
                time_step=10.0,
                base_load=200.0,         # 降低基础负荷
                load_peak_ratio=1.2,
                load_valley_ratio=0.8,   # 提高谷值
                wind_capacity=60.0,      # 增加可再生能源
                solar_capacity=40.0
            ),
            scenario_type=ScenarioType.VALLEY_LOAD,
            tags=["curtailment_risk", "valley_filling"]
        )

    @staticmethod
    def get_extreme_weather() -> ScenarioDefinition:
        """极端天气场景"""
        return ScenarioDefinition(
            name="extreme_weather",
            description="极端天气日,新能源波动剧烈",
            config=SimulationConfig(
                duration=86400.0,
                time_step=10.0,
                base_load=250.0,
                wind_turbulence=0.3,     # 高湍流
                load_noise=0.05          # 高负荷噪声
            ),
            scenario_type=ScenarioType.EXTREME_WEATHER,
            tags=["extreme", "resilience"]
        )

    @staticmethod
    def get_all_scenarios() -> List[ScenarioDefinition]:
        """获取所有预定义场景"""
        return [
            ScenarioLibrary.get_typical_day(),
            ScenarioLibrary.get_high_renewable(),
            ScenarioLibrary.get_low_renewable(),
            ScenarioLibrary.get_peak_load(),
            ScenarioLibrary.get_valley_load(),
            ScenarioLibrary.get_extreme_weather()
        ]


class ScenarioRunner:
    """
    场景仿真运行器

    批量运行多个场景并收集结果
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.results: List[ScenarioResult] = []

    def run_scenario(self, scenario: ScenarioDefinition) -> ScenarioResult:
        """
        运行单个场景

        Args:
            scenario: 场景定义

        Returns:
            场景结果
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"运行场景: {scenario.name}")
            print(f"描述: {scenario.description}")
            print(f"{'='*60}")

        start_time = time.time()

        # 创建仿真器并运行
        simulator = MultiEnergySimulator(scenario.config)
        sim_result = simulator.run()

        execution_time = time.time() - start_time

        # 计算指标
        metrics = self._calculate_metrics(sim_result)

        result = ScenarioResult(
            scenario_name=scenario.name,
            simulation_result=sim_result,
            execution_time=execution_time,
            metrics=metrics
        )

        self.results.append(result)

        if self.verbose:
            print(f"\n场景 '{scenario.name}' 完成, 耗时: {execution_time:.1f}s")
            self._print_metrics(metrics)

        return result

    def run_all_scenarios(
        self,
        scenarios: Optional[List[ScenarioDefinition]] = None
    ) -> List[ScenarioResult]:
        """
        运行所有场景

        Args:
            scenarios: 场景列表,默认使用全部预定义场景

        Returns:
            结果列表
        """
        if scenarios is None:
            scenarios = ScenarioLibrary.get_all_scenarios()

        self.results = []

        if self.verbose:
            print(f"\n{'#'*60}")
            print(f"# 多场景批量仿真")
            print(f"# 场景数量: {len(scenarios)}")
            print(f"{'#'*60}")

        for i, scenario in enumerate(scenarios):
            if self.verbose:
                print(f"\n[{i+1}/{len(scenarios)}] ", end="")
            self.run_scenario(scenario)

        return self.results

    def _calculate_metrics(self, result: SimulationResult) -> Dict[str, float]:
        """计算性能指标"""
        freq_dev = result.frequency - 50.0

        # 基础频率指标
        freq_dev_max = np.max(np.abs(freq_dev))
        freq_dev_rms = np.sqrt(np.mean(freq_dev ** 2))
        freq_dev_mean = np.mean(freq_dev)

        # 频率质量指标
        normal_ratio = np.sum(np.abs(freq_dev) < 0.5) / len(freq_dev) * 100
        good_ratio = np.sum(np.abs(freq_dev) < 0.2) / len(freq_dev) * 100

        # 新能源利用率
        wind_total = np.sum(result.wind_power) * (result.time[1] - result.time[0]) / 3600
        solar_total = np.sum(result.solar_power) * (result.time[1] - result.time[0]) / 3600
        renewable_total = wind_total + solar_total

        # 储能利用
        sc_cycles = self._estimate_cycles(result.sc_soc)
        bess_cycles = self._estimate_cycles(result.bess_soc)

        # PSH运行统计
        psh_gen_time = np.sum(result.psh_power > 10) / len(result.psh_power) * 100
        psh_pump_time = np.sum(result.psh_power < -10) / len(result.psh_power) * 100

        # 调峰效果
        net_load = result.load - result.wind_power - result.solar_power
        peak_valley_diff = np.max(net_load) - np.min(net_load)

        return {
            'freq_dev_max': freq_dev_max,
            'freq_dev_rms': freq_dev_rms,
            'freq_dev_mean': freq_dev_mean,
            'freq_normal_ratio': normal_ratio,
            'freq_good_ratio': good_ratio,
            'renewable_energy_mwh': renewable_total,
            'sc_cycles': sc_cycles,
            'bess_cycles': bess_cycles,
            'psh_gen_ratio': psh_gen_time,
            'psh_pump_ratio': psh_pump_time,
            'peak_valley_diff': peak_valley_diff,
            'psh_mode_switches': result.psh_mode_switches
        }

    def _estimate_cycles(self, soc_array: np.ndarray) -> float:
        """估算储能循环次数"""
        if len(soc_array) < 2:
            return 0.0

        # 简化估算: 统计SOC变化的绝对值之和
        soc_changes = np.abs(np.diff(soc_array))
        total_change = np.sum(soc_changes)

        # 一个完整循环 = SOC从0到1再到0 = 变化量2.0
        cycles = total_change / 2.0

        return cycles

    def _print_metrics(self, metrics: Dict[str, float]):
        """打印指标"""
        print("\n性能指标:")
        print(f"  频率偏差最大: {metrics['freq_dev_max']:.4f} Hz")
        print(f"  频率偏差RMS:  {metrics['freq_dev_rms']:.4f} Hz")
        print(f"  频率正常占比: {metrics['freq_normal_ratio']:.1f}%")
        print(f"  新能源发电量: {metrics['renewable_energy_mwh']:.1f} MWh")
        print(f"  PSH发电占比:  {metrics['psh_gen_ratio']:.1f}%")


class ScenarioComparator:
    """
    场景对比分析器

    对多个场景结果进行对比分析
    """

    def __init__(self, results: List[ScenarioResult]):
        self.results = results
        self.scenario_names = [r.scenario_name for r in results]

    def compare(self) -> ComparisonReport:
        """
        执行对比分析

        Returns:
            对比报告
        """
        # 收集所有指标
        metrics_table = self._build_metrics_table()

        # 找出各指标最佳场景
        best_scenario = self._find_best_scenarios(metrics_table)

        # 综合排名
        ranking = self._calculate_ranking(metrics_table)

        # 生成摘要
        summary = self._generate_summary(metrics_table, best_scenario, ranking)

        return ComparisonReport(
            scenarios=self.scenario_names,
            metrics_table=metrics_table,
            best_scenario=best_scenario,
            ranking=ranking,
            summary=summary
        )

    def _build_metrics_table(self) -> Dict[str, Dict[str, float]]:
        """构建指标表"""
        table = {}

        if not self.results:
            return table

        # 获取所有指标名称
        metric_names = list(self.results[0].metrics.keys())

        for metric in metric_names:
            table[metric] = {}
            for result in self.results:
                table[metric][result.scenario_name] = result.metrics.get(metric, 0)

        return table

    def _find_best_scenarios(
        self,
        metrics_table: Dict[str, Dict[str, float]]
    ) -> Dict[str, str]:
        """找出各指标最佳场景"""
        best = {}

        # 定义每个指标的优化方向(True=越小越好)
        minimize = {
            'freq_dev_max': True,
            'freq_dev_rms': True,
            'freq_dev_mean': False,  # 接近0最好,特殊处理
            'freq_normal_ratio': False,  # 越大越好
            'freq_good_ratio': False,
            'renewable_energy_mwh': False,
            'sc_cycles': False,  # 合理利用
            'bess_cycles': False,
            'psh_gen_ratio': False,
            'psh_pump_ratio': False,
            'peak_valley_diff': True,  # 越小表示调峰效果越好
            'psh_mode_switches': True
        }

        for metric, values in metrics_table.items():
            if not values:
                continue

            should_minimize = minimize.get(metric, True)

            if metric == 'freq_dev_mean':
                # 特殊处理: 接近0最好
                best_name = min(values.keys(), key=lambda k: abs(values[k]))
            elif should_minimize:
                best_name = min(values.keys(), key=lambda k: values[k])
            else:
                best_name = max(values.keys(), key=lambda k: values[k])

            best[metric] = best_name

        return best

    def _calculate_ranking(
        self,
        metrics_table: Dict[str, Dict[str, float]]
    ) -> Dict[str, List[str]]:
        """计算各指标的场景排名"""
        ranking = {}

        minimize = {
            'freq_dev_max': True,
            'freq_dev_rms': True,
            'freq_normal_ratio': False,
            'renewable_energy_mwh': False
        }

        for metric, values in metrics_table.items():
            if metric not in minimize:
                continue

            should_minimize = minimize[metric]
            sorted_names = sorted(
                values.keys(),
                key=lambda k: values[k],
                reverse=not should_minimize
            )
            ranking[metric] = sorted_names

        return ranking

    def _generate_summary(
        self,
        metrics_table: Dict[str, Dict[str, float]],
        best_scenario: Dict[str, str],
        ranking: Dict[str, List[str]]
    ) -> str:
        """生成摘要报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("多场景对比分析摘要")
        lines.append("=" * 60)
        lines.append("")

        # 最佳场景统计
        best_count = {}
        for metric, name in best_scenario.items():
            best_count[name] = best_count.get(name, 0) + 1

        lines.append("1. 综合表现最佳场景:")
        for name, count in sorted(best_count.items(), key=lambda x: -x[1]):
            lines.append(f"   {name}: {count}项指标最优")
        lines.append("")

        # 关键指标对比
        lines.append("2. 关键指标对比:")
        key_metrics = ['freq_dev_rms', 'freq_normal_ratio', 'renewable_energy_mwh']
        for metric in key_metrics:
            if metric in metrics_table:
                lines.append(f"\n   {metric}:")
                for name, value in sorted(
                    metrics_table[metric].items(),
                    key=lambda x: x[1]
                ):
                    lines.append(f"     {name}: {value:.4f}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def print_comparison_table(self):
        """打印对比表格"""
        if not self.results:
            print("无结果可对比")
            return

        # 表头
        headers = ["指标"] + self.scenario_names

        # 选择要显示的指标
        display_metrics = [
            ('freq_dev_max', '频率偏差最大(Hz)'),
            ('freq_dev_rms', '频率偏差RMS(Hz)'),
            ('freq_normal_ratio', '频率正常占比(%)'),
            ('renewable_energy_mwh', '新能源发电(MWh)'),
            ('psh_gen_ratio', 'PSH发电占比(%)'),
            ('psh_pump_ratio', 'PSH抽水占比(%)')
        ]

        # 计算列宽
        col_width = max(20, max(len(n) for n in self.scenario_names) + 2)

        # 打印表头
        print("\n" + "=" * (20 + col_width * len(self.scenario_names)))
        print(f"{'指标':<20}", end="")
        for name in self.scenario_names:
            print(f"{name:>{col_width}}", end="")
        print()
        print("-" * (20 + col_width * len(self.scenario_names)))

        # 打印数据行
        for metric_key, metric_name in display_metrics:
            print(f"{metric_name:<20}", end="")
            for result in self.results:
                value = result.metrics.get(metric_key, 0)
                if 'ratio' in metric_key or 'mwh' in metric_key.lower():
                    print(f"{value:>{col_width}.1f}", end="")
                else:
                    print(f"{value:>{col_width}.4f}", end="")
            print()

        print("=" * (20 + col_width * len(self.scenario_names)))


def run_scenario_comparison(
    scenarios: Optional[List[ScenarioDefinition]] = None,
    output_file: Optional[str] = None
) -> ComparisonReport:
    """
    运行场景对比分析

    Args:
        scenarios: 场景列表,默认使用预定义场景
        output_file: 输出文件路径

    Returns:
        对比报告
    """
    # 运行所有场景
    runner = ScenarioRunner(verbose=True)
    results = runner.run_all_scenarios(scenarios)

    # 执行对比分析
    comparator = ScenarioComparator(results)
    report = comparator.compare()

    # 打印对比表格
    comparator.print_comparison_table()

    # 打印摘要
    print(report.summary)

    # 保存到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report.summary)
            f.write("\n\n详细数据:\n")
            for metric, values in report.metrics_table.items():
                f.write(f"\n{metric}:\n")
                for name, value in values.items():
                    f.write(f"  {name}: {value}\n")
        print(f"\n报告已保存至: {output_file}")

    return report
