# -*- coding: utf-8 -*-
"""
HIL 测试结果可视化模块
HIL Test Results Visualization Module

提供测试数据的图形化展示功能：
- 时序曲线绘制
- 多变量对比图
- 性能指标图表
- 测试报告图形
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
from dataclasses import dataclass


class PlotStyle(Enum):
    """绘图样式"""
    LINE = "line"
    SCATTER = "scatter"
    BAR = "bar"
    AREA = "area"
    STEP = "step"


@dataclass
class PlotConfig:
    """绘图配置"""
    title: str = ""
    xlabel: str = "时间 (s)"
    ylabel: str = ""
    legend_loc: str = "best"
    grid: bool = True
    figsize: Tuple[int, int] = (10, 6)


class HILPlotter:
    """HIL 测试结果绘图器

    提供各种测试数据的可视化功能
    """

    # 预定义颜色方案
    COLORS = [
        '#1f77b4',  # 蓝色
        '#ff7f0e',  # 橙色
        '#2ca02c',  # 绿色
        '#d62728',  # 红色
        '#9467bd',  # 紫色
        '#8c564b',  # 棕色
        '#e377c2',  # 粉色
        '#7f7f7f',  # 灰色
    ]

    def __init__(self):
        """初始化绘图器"""
        self._matplotlib_available = False
        self._plt = None
        self._fig = None
        self._axes = None

        # 尝试导入 matplotlib
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')  # 使用非交互式后端
            self._plt = plt
            self._matplotlib_available = True
        except ImportError:
            pass

    def is_available(self) -> bool:
        """检查绘图功能是否可用"""
        return self._matplotlib_available

    def plot_time_series(self, time: List[float], data: Dict[str, List[float]],
                         config: Optional[PlotConfig] = None,
                         filename: Optional[str] = None) -> bool:
        """绘制时序曲线

        Args:
            time: 时间序列
            data: 数据字典 {变量名: 数据列表}
            config: 绘图配置
            filename: 保存文件名 (None则不保存)

        Returns:
            是否成功
        """
        if not self._matplotlib_available:
            return False

        config = config or PlotConfig()
        plt = self._plt

        fig, ax = plt.subplots(figsize=config.figsize)

        for i, (name, values) in enumerate(data.items()):
            color = self.COLORS[i % len(self.COLORS)]
            ax.plot(time, values, label=name, color=color, linewidth=1.5)

        ax.set_xlabel(config.xlabel)
        ax.set_ylabel(config.ylabel)
        ax.set_title(config.title)
        ax.legend(loc=config.legend_loc)
        if config.grid:
            ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def plot_valve_response(self, history: List[Dict],
                            filename: Optional[str] = None) -> bool:
        """绘制阀门响应曲线

        Args:
            history: 历史数据列表
            filename: 保存文件名

        Returns:
            是否成功
        """
        if not self._matplotlib_available or not history:
            return False

        plt = self._plt

        time = [h.get('time', i) for i, h in enumerate(history)]
        opening = [h.get('opening', h.get('valve_opening', 0)) for h in history]
        flow = [h.get('flow', h.get('flow_rate', 0)) for h in history]
        pressure_up = [h.get('pressure_upstream', h.get('P_up', 0)) for h in history]
        pressure_down = [h.get('pressure_downstream', h.get('P_down', 0)) for h in history]

        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

        # 开度曲线
        axes[0].plot(time, opening, 'b-', linewidth=1.5, label='阀门开度')
        axes[0].set_ylabel('开度')
        axes[0].set_ylim(-0.1, 1.1)
        axes[0].legend(loc='upper right')
        axes[0].grid(True, alpha=0.3)

        # 流量曲线
        axes[1].plot(time, flow, 'g-', linewidth=1.5, label='流量')
        axes[1].set_ylabel('流量 (m³/s)')
        axes[1].legend(loc='upper right')
        axes[1].grid(True, alpha=0.3)

        # 压力曲线
        axes[2].plot(time, pressure_up, 'r-', linewidth=1.5, label='上游压力')
        axes[2].plot(time, pressure_down, 'r--', linewidth=1.5, label='下游压力')
        axes[2].set_xlabel('时间 (s)')
        axes[2].set_ylabel('压力 (MPa)')
        axes[2].legend(loc='upper right')
        axes[2].grid(True, alpha=0.3)

        plt.suptitle('阀门响应曲线', fontsize=12)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def plot_pump_performance(self, history: List[Dict],
                              filename: Optional[str] = None) -> bool:
        """绘制水泵性能曲线

        Args:
            history: 历史数据列表
            filename: 保存文件名

        Returns:
            是否成功
        """
        if not self._matplotlib_available or not history:
            return False

        plt = self._plt

        time = [h.get('time', i) for i, h in enumerate(history)]
        speed = [h.get('speed', 0) for h in history]
        flow = [h.get('flow', 0) for h in history]
        head = [h.get('head', 0) for h in history]
        efficiency = [h.get('efficiency', 0) for h in history]

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        # 转速曲线
        axes[0, 0].plot(time, speed, 'b-', linewidth=1.5)
        axes[0, 0].set_ylabel('转速 (rpm)')
        axes[0, 0].set_title('转速-时间')
        axes[0, 0].grid(True, alpha=0.3)

        # 流量曲线
        axes[0, 1].plot(time, flow, 'g-', linewidth=1.5)
        axes[0, 1].set_ylabel('流量 (m³/s)')
        axes[0, 1].set_title('流量-时间')
        axes[0, 1].grid(True, alpha=0.3)

        # 扬程曲线
        axes[1, 0].plot(time, head, 'r-', linewidth=1.5)
        axes[1, 0].set_xlabel('时间 (s)')
        axes[1, 0].set_ylabel('扬程 (m)')
        axes[1, 0].set_title('扬程-时间')
        axes[1, 0].grid(True, alpha=0.3)

        # 效率曲线
        axes[1, 1].plot(time, efficiency, 'm-', linewidth=1.5)
        axes[1, 1].set_xlabel('时间 (s)')
        axes[1, 1].set_ylabel('效率')
        axes[1, 1].set_title('效率-时间')
        axes[1, 1].grid(True, alpha=0.3)

        plt.suptitle('水泵性能曲线', fontsize=12)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def plot_gate_operation(self, history: List[Dict],
                            filename: Optional[str] = None) -> bool:
        """绘制闸门运行曲线

        Args:
            history: 历史数据列表
            filename: 保存文件名

        Returns:
            是否成功
        """
        if not self._matplotlib_available or not history:
            return False

        plt = self._plt

        time = [h.get('time', i) for i, h in enumerate(history)]
        opening = [h.get('opening', 0) for h in history]
        level = [h.get('level', h.get('upstream_level', 0)) for h in history]
        flow = [h.get('flow', 0) for h in history]

        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

        # 开度曲线
        axes[0].plot(time, opening, 'b-', linewidth=1.5, label='闸门开度')
        axes[0].set_ylabel('开度 (m)')
        axes[0].legend(loc='upper right')
        axes[0].grid(True, alpha=0.3)

        # 水位曲线
        axes[1].plot(time, level, 'c-', linewidth=1.5, label='上游水位')
        axes[1].set_ylabel('水位 (m)')
        axes[1].legend(loc='upper right')
        axes[1].grid(True, alpha=0.3)

        # 流量曲线
        axes[2].plot(time, flow, 'g-', linewidth=1.5, label='过闸流量')
        axes[2].set_xlabel('时间 (s)')
        axes[2].set_ylabel('流量 (m³/s)')
        axes[2].legend(loc='upper right')
        axes[2].grid(True, alpha=0.3)

        plt.suptitle('闸门运行曲线', fontsize=12)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def plot_water_hammer(self, history: List[Dict],
                          filename: Optional[str] = None) -> bool:
        """绘制水锤分析曲线

        Args:
            history: 历史数据列表
            filename: 保存文件名

        Returns:
            是否成功
        """
        if not self._matplotlib_available or not history:
            return False

        plt = self._plt

        time = [h.get('time', i) for i, h in enumerate(history)]
        pressure = [h.get('pressure', h.get('max_pressure', 0)) for h in history]
        flow = [h.get('flow', h.get('flow_rate', 0)) for h in history]
        valve_opening = [h.get('valve_opening', 1.0) for h in history]

        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

        # 压力曲线
        axes[0].plot(time, pressure, 'r-', linewidth=1.5, label='管道压力')
        axes[0].axhline(y=max(pressure) if pressure else 0, color='r',
                        linestyle='--', alpha=0.5, label=f'最大压力: {max(pressure):.2f} MPa')
        axes[0].set_ylabel('压力 (MPa)')
        axes[0].legend(loc='upper right')
        axes[0].grid(True, alpha=0.3)

        # 流量曲线
        axes[1].plot(time, flow, 'b-', linewidth=1.5, label='流量')
        axes[1].set_ylabel('流量 (m³/s)')
        axes[1].legend(loc='upper right')
        axes[1].grid(True, alpha=0.3)

        # 阀门开度
        axes[2].plot(time, valve_opening, 'g-', linewidth=1.5, label='阀门开度')
        axes[2].set_xlabel('时间 (s)')
        axes[2].set_ylabel('开度')
        axes[2].set_ylim(-0.1, 1.1)
        axes[2].legend(loc='upper right')
        axes[2].grid(True, alpha=0.3)

        plt.suptitle('水锤分析曲线', fontsize=12)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def plot_cascade_pumps(self, history: List[Dict],
                           num_pumps: int = 3,
                           filename: Optional[str] = None) -> bool:
        """绘制级联泵组曲线

        Args:
            history: 历史数据列表
            num_pumps: 泵数量
            filename: 保存文件名

        Returns:
            是否成功
        """
        if not self._matplotlib_available or not history:
            return False

        plt = self._plt

        time = [h.get('time', i) for i, h in enumerate(history)]
        total_flow = [h.get('total_flow', 0) for h in history]

        # 提取各泵流量
        pump_flows = []
        for i in range(num_pumps):
            flows = []
            for h in history:
                pump_flow_list = h.get('flows', [0] * num_pumps)
                flows.append(pump_flow_list[i] if i < len(pump_flow_list) else 0)
            pump_flows.append(flows)

        fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

        # 各泵流量曲线
        for i, flows in enumerate(pump_flows):
            color = self.COLORS[i % len(self.COLORS)]
            axes[0].plot(time, flows, color=color, linewidth=1.5, label=f'泵 {i+1}')
        axes[0].set_ylabel('流量 (m³/s)')
        axes[0].legend(loc='upper right')
        axes[0].grid(True, alpha=0.3)
        axes[0].set_title('各泵流量')

        # 总流量曲线
        axes[1].plot(time, total_flow, 'k-', linewidth=2, label='总流量')
        axes[1].fill_between(time, total_flow, alpha=0.3)
        axes[1].set_xlabel('时间 (s)')
        axes[1].set_ylabel('流量 (m³/s)')
        axes[1].legend(loc='upper right')
        axes[1].grid(True, alpha=0.3)
        axes[1].set_title('总流量')

        plt.suptitle('级联泵组运行曲线', fontsize=12)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def plot_test_summary(self, results: Dict,
                          filename: Optional[str] = None) -> bool:
        """绘制测试结果汇总图

        Args:
            results: 测试结果字典
            filename: 保存文件名

        Returns:
            是否成功
        """
        if not self._matplotlib_available:
            return False

        plt = self._plt

        # 提取数据
        test_names = list(results.keys())
        passed = [1 if r.get('passed', False) else 0 for r in results.values()]
        failed = [0 if r.get('passed', False) else 1 for r in results.values()]

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # 条形图
        x = np.arange(len(test_names))
        width = 0.35
        axes[0].bar(x, passed, width, label='通过', color='#2ca02c')
        axes[0].bar(x, failed, width, bottom=passed, label='失败', color='#d62728')
        axes[0].set_ylabel('测试结果')
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(test_names, rotation=45, ha='right')
        axes[0].legend()
        axes[0].set_title('各测试结果')

        # 饼图
        total_passed = sum(passed)
        total_failed = sum(failed)
        sizes = [total_passed, total_failed]
        labels = [f'通过 ({total_passed})', f'失败 ({total_failed})']
        colors = ['#2ca02c', '#d62728']
        explode = (0.05, 0) if total_failed > 0 else (0, 0)

        if sum(sizes) > 0:
            axes[1].pie(sizes, explode=explode, labels=labels, colors=colors,
                        autopct='%1.1f%%', startangle=90)
        axes[1].set_title('测试通过率')

        plt.suptitle('测试结果汇总', fontsize=12)
        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def plot_sensitivity_analysis(self, param_name: str,
                                  param_values: List[float],
                                  metrics: Dict[str, List[float]],
                                  safe_range: Optional[Tuple[float, float]] = None,
                                  filename: Optional[str] = None) -> bool:
        """绘制敏感性分析图

        Args:
            param_name: 参数名称
            param_values: 参数值列表
            metrics: 性能指标 {指标名: 值列表}
            safe_range: 安全范围 (min, max)
            filename: 保存文件名

        Returns:
            是否成功
        """
        if not self._matplotlib_available:
            return False

        plt = self._plt

        fig, ax = plt.subplots(figsize=(10, 6))

        for i, (name, values) in enumerate(metrics.items()):
            color = self.COLORS[i % len(self.COLORS)]
            ax.plot(param_values, values, 'o-', color=color,
                    linewidth=1.5, markersize=6, label=name)

        # 标注安全范围
        if safe_range:
            ax.axvspan(safe_range[0], safe_range[1], alpha=0.2, color='green',
                       label='安全范围')

        ax.set_xlabel(param_name)
        ax.set_ylabel('指标值')
        ax.set_title(f'{param_name} 敏感性分析')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if filename:
            plt.savefig(filename, dpi=150, bbox_inches='tight')

        plt.close(fig)
        return True

    def create_report_figures(self, test_results: Dict,
                              output_dir: str = ".") -> List[str]:
        """为报告创建所有图形

        Args:
            test_results: 测试结果
            output_dir: 输出目录

        Returns:
            生成的图形文件列表
        """
        if not self._matplotlib_available:
            return []

        import os
        generated_files = []

        # 测试汇总图
        summary_file = os.path.join(output_dir, "test_summary.png")
        if self.plot_test_summary(test_results, summary_file):
            generated_files.append(summary_file)

        # 为每个测试生成详细图
        for test_name, result in test_results.items():
            history = result.get('history', [])
            if not history:
                continue

            # 根据测试类型选择绘图方法
            test_id = result.get('test_id', '')
            detail_file = os.path.join(output_dir, f"{test_id}_detail.png")

            if 'FPV' in test_id or 'WHV' in test_id or 'ESV' in test_id:
                if self.plot_valve_response(history, detail_file):
                    generated_files.append(detail_file)
            elif 'PC' in test_id:
                if self.plot_pump_performance(history, detail_file):
                    generated_files.append(detail_file)
            elif 'GC' in test_id:
                if self.plot_gate_operation(history, detail_file):
                    generated_files.append(detail_file)

        return generated_files
