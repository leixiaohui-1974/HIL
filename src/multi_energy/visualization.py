# -*- coding: utf-8 -*-
"""
多能互补系统可视化模块
Visualization Module for Multi-Energy Complementary System

生成仿真结果的可视化图表:
1. 功率平衡图 - 各能源单元出力曲线
2. 频率响应图 - 系统频率动态
3. 储能状态图 - SOC和水库水位
4. PSH运行图 - 抽蓄运行模式
5. 日报告生成 - 综合分析报告
"""

import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import os

# 尝试导入matplotlib,如果不可用则提供替代方案
try:
    import matplotlib
    matplotlib.use('Agg')  # 使用非交互式后端
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.gridspec import GridSpec
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Visualization will generate text reports only.")


@dataclass
class VisualizationConfig:
    """可视化配置"""
    figure_width: float = 14.0
    figure_height: float = 10.0
    dpi: int = 150
    font_size: int = 10
    line_width: float = 1.0
    output_dir: str = "./output"
    show_grid: bool = True
    use_chinese: bool = True


class MultiEnergyVisualizer:
    """
    多能互补系统可视化器

    提供多种可视化方法展示仿真结果
    """

    # 颜色方案
    COLORS = {
        'wind': '#2E86AB',      # 蓝色
        'solar': '#F6AE2D',     # 橙色
        'hydro': '#33658A',     # 深蓝
        'psh_gen': '#86BBD8',   # 浅蓝
        'psh_pump': '#758E4F',  # 绿色
        'sc': '#F26419',        # 橙红
        'bess': '#9B2915',      # 红棕
        'load': '#2F4858',      # 深灰蓝
        'frequency': '#E94F37', # 红色
        'soc': '#1B998B',       # 青色
    }

    def __init__(self, config: Optional[VisualizationConfig] = None):
        self.config = config or VisualizationConfig()

        # 确保输出目录存在
        os.makedirs(self.config.output_dir, exist_ok=True)

        # 设置中文字体(如果需要)
        if MATPLOTLIB_AVAILABLE and self.config.use_chinese:
            try:
                plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial']
                plt.rcParams['axes.unicode_minus'] = False
            except Exception:
                pass

    def plot_power_balance(
        self,
        result,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制功率平衡图

        显示各能源单元的出力曲线和负荷曲线

        Args:
            result: SimulationResult对象
            save_path: 保存路径
            show: 是否显示

        Returns:
            保存的文件路径
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._generate_text_report(result, "power_balance")

        hours = result.time / 3600

        fig, axes = plt.subplots(3, 1, figsize=(self.config.figure_width, self.config.figure_height))

        # ===== 子图1: 可再生能源和负荷 =====
        ax1 = axes[0]
        ax1.fill_between(hours, 0, result.wind_power,
                        alpha=0.7, color=self.COLORS['wind'], label='风电 (Wind)')
        ax1.fill_between(hours, result.wind_power, result.wind_power + result.solar_power,
                        alpha=0.7, color=self.COLORS['solar'], label='光伏 (Solar)')
        ax1.plot(hours, result.load, color=self.COLORS['load'],
                linewidth=2, label='负荷 (Load)')
        ax1.plot(hours, result.net_load, color='gray',
                linewidth=1.5, linestyle='--', label='净负荷 (Net Load)')

        ax1.set_ylabel('功率 (MW)', fontsize=self.config.font_size)
        ax1.set_title('可再生能源出力与负荷 (Renewable Generation and Load)',
                     fontsize=self.config.font_size + 2)
        ax1.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax1.grid(self.config.show_grid, alpha=0.3)
        ax1.set_xlim(0, 24)

        # ===== 子图2: 可调度电源 =====
        ax2 = axes[1]
        ax2.plot(hours, result.hydro_power, color=self.COLORS['hydro'],
                linewidth=1.5, label='常规水电 (Hydro)')

        # PSH功率(发电为正,抽水为负)
        psh_gen = np.maximum(result.psh_power, 0)
        psh_pump = np.minimum(result.psh_power, 0)

        ax2.fill_between(hours, 0, psh_gen,
                        alpha=0.6, color=self.COLORS['psh_gen'], label='PSH发电 (PSH Gen)')
        ax2.fill_between(hours, 0, psh_pump,
                        alpha=0.6, color=self.COLORS['psh_pump'], label='PSH抽水 (PSH Pump)')

        ax2.axhline(y=0, color='black', linewidth=0.5)
        ax2.set_ylabel('功率 (MW)', fontsize=self.config.font_size)
        ax2.set_title('可调度电源 (Dispatchable Generation)',
                     fontsize=self.config.font_size + 2)
        ax2.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax2.grid(self.config.show_grid, alpha=0.3)
        ax2.set_xlim(0, 24)

        # ===== 子图3: 储能系统 =====
        ax3 = axes[2]
        ax3.plot(hours, result.sc_power, color=self.COLORS['sc'],
                linewidth=1.5, label='超级电容 (SC)')
        ax3.plot(hours, result.bess_power, color=self.COLORS['bess'],
                linewidth=1.5, label='锂电池 (BESS)')
        ax3.plot(hours, result.sc_power + result.bess_power, color='purple',
                linewidth=1, linestyle='--', label='HESS总计')

        ax3.axhline(y=0, color='black', linewidth=0.5)
        ax3.set_xlabel('时间 (小时)', fontsize=self.config.font_size)
        ax3.set_ylabel('功率 (MW)', fontsize=self.config.font_size)
        ax3.set_title('混合储能系统 (Hybrid Energy Storage System)',
                     fontsize=self.config.font_size + 2)
        ax3.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax3.grid(self.config.show_grid, alpha=0.3)
        ax3.set_xlim(0, 24)

        plt.tight_layout()

        # 保存
        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'power_balance.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def plot_frequency_response(
        self,
        result,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制频率响应图
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._generate_text_report(result, "frequency")

        hours = result.time / 3600
        freq_dev = result.frequency - 50.0

        fig, axes = plt.subplots(2, 1, figsize=(self.config.figure_width, 6))

        # ===== 子图1: 频率 =====
        ax1 = axes[0]
        ax1.plot(hours, result.frequency, color=self.COLORS['frequency'], linewidth=1)
        ax1.axhline(y=50.0, color='gray', linestyle='--', linewidth=0.5)
        ax1.axhline(y=49.8, color='red', linestyle=':', linewidth=0.5, alpha=0.7)
        ax1.axhline(y=50.2, color='red', linestyle=':', linewidth=0.5, alpha=0.7)

        ax1.fill_between(hours, 49.8, 50.2, alpha=0.1, color='green', label='正常范围')

        ax1.set_ylabel('频率 (Hz)', fontsize=self.config.font_size)
        ax1.set_title('系统频率 (System Frequency)', fontsize=self.config.font_size + 2)
        ax1.set_xlim(0, 24)
        ax1.set_ylim(49.5, 50.5)
        ax1.grid(self.config.show_grid, alpha=0.3)

        # ===== 子图2: 频率偏差直方图 =====
        ax2 = axes[1]
        ax2.hist(freq_dev, bins=50, color=self.COLORS['frequency'],
                alpha=0.7, edgecolor='black', linewidth=0.5)
        ax2.axvline(x=0, color='gray', linestyle='--', linewidth=1)
        ax2.axvline(x=np.mean(freq_dev), color='blue', linestyle='-',
                   linewidth=1.5, label=f'均值: {np.mean(freq_dev):.4f} Hz')
        ax2.axvline(x=np.std(freq_dev), color='orange', linestyle='--',
                   linewidth=1, label=f'标准差: {np.std(freq_dev):.4f} Hz')
        ax2.axvline(x=-np.std(freq_dev), color='orange', linestyle='--', linewidth=1)

        ax2.set_xlabel('频率偏差 (Hz)', fontsize=self.config.font_size)
        ax2.set_ylabel('频次', fontsize=self.config.font_size)
        ax2.set_title('频率偏差分布 (Frequency Deviation Distribution)',
                     fontsize=self.config.font_size + 2)
        ax2.legend(fontsize=self.config.font_size - 1)
        ax2.grid(self.config.show_grid, alpha=0.3)

        plt.tight_layout()

        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'frequency_response.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def plot_storage_status(
        self,
        result,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制储能状态图
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._generate_text_report(result, "storage")

        hours = result.time / 3600

        fig, axes = plt.subplots(2, 1, figsize=(self.config.figure_width, 6))

        # ===== 子图1: HESS SOC =====
        ax1 = axes[0]
        ax1.plot(hours, result.sc_soc * 100, color=self.COLORS['sc'],
                linewidth=1.5, label='超级电容 SOC')
        ax1.plot(hours, result.bess_soc * 100, color=self.COLORS['bess'],
                linewidth=1.5, label='锂电池 SOC')

        # SOC限制线
        ax1.axhline(y=10, color='red', linestyle=':', linewidth=0.5, alpha=0.7)
        ax1.axhline(y=90, color='red', linestyle=':', linewidth=0.5, alpha=0.7)
        ax1.fill_between(hours, 10, 90, alpha=0.1, color='green')

        ax1.set_ylabel('SOC (%)', fontsize=self.config.font_size)
        ax1.set_title('储能系统荷电状态 (Energy Storage SOC)',
                     fontsize=self.config.font_size + 2)
        ax1.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax1.set_xlim(0, 24)
        ax1.set_ylim(0, 100)
        ax1.grid(self.config.show_grid, alpha=0.3)

        # ===== 子图2: PSH水库水位 =====
        ax2 = axes[1]
        ax2.fill_between(hours, 0, result.psh_level * 100,
                        alpha=0.6, color=self.COLORS['hydro'])
        ax2.plot(hours, result.psh_level * 100, color=self.COLORS['hydro'],
                linewidth=1.5, label='水库水位')

        # 水位限制
        ax2.axhline(y=15, color='red', linestyle=':', linewidth=1, label='最低水位 (15%)')
        ax2.axhline(y=95, color='red', linestyle=':', linewidth=1, label='最高水位 (95%)')

        ax2.set_xlabel('时间 (小时)', fontsize=self.config.font_size)
        ax2.set_ylabel('水位 (%)', fontsize=self.config.font_size)
        ax2.set_title('抽水蓄能水库水位 (PSH Reservoir Level)',
                     fontsize=self.config.font_size + 2)
        ax2.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax2.set_xlim(0, 24)
        ax2.set_ylim(0, 100)
        ax2.grid(self.config.show_grid, alpha=0.3)

        plt.tight_layout()

        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'storage_status.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def plot_psh_operation(
        self,
        result,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制PSH运行模式图
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._generate_text_report(result, "psh")

        hours = result.time / 3600

        fig, axes = plt.subplots(3, 1, figsize=(self.config.figure_width, 8))

        # ===== 子图1: PSH功率 =====
        ax1 = axes[0]
        psh_gen = np.maximum(result.psh_power, 0)
        psh_pump = np.minimum(result.psh_power, 0)

        ax1.fill_between(hours, 0, psh_gen, alpha=0.7,
                        color=self.COLORS['psh_gen'], label='发电 (Generation)')
        ax1.fill_between(hours, 0, psh_pump, alpha=0.7,
                        color=self.COLORS['psh_pump'], label='抽水 (Pumping)')
        ax1.axhline(y=0, color='black', linewidth=0.5)

        ax1.set_ylabel('功率 (MW)', fontsize=self.config.font_size)
        ax1.set_title('抽水蓄能电站功率 (PSH Power)', fontsize=self.config.font_size + 2)
        ax1.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax1.grid(self.config.show_grid, alpha=0.3)
        ax1.set_xlim(0, 24)

        # ===== 子图2: 运行模式 =====
        ax2 = axes[1]

        # 将模式转换为数值
        mode_map = {'stopped': 0, 'pumping': -1, 'generating': 1,
                   'pump_starting': -0.5, 'gen_starting': 0.5,
                   'pump_stopping': -0.5, 'gen_stopping': 0.5,
                   'mode_switching': 0}
        mode_values = [mode_map.get(m, 0) for m in result.psh_mode]

        # 绘制模式带
        ax2.fill_between(hours, 0, mode_values, where=np.array(mode_values) > 0,
                        alpha=0.7, color=self.COLORS['psh_gen'], label='发电')
        ax2.fill_between(hours, 0, mode_values, where=np.array(mode_values) < 0,
                        alpha=0.7, color=self.COLORS['psh_pump'], label='抽水')
        ax2.axhline(y=0, color='black', linewidth=0.5)

        ax2.set_ylabel('运行模式', fontsize=self.config.font_size)
        ax2.set_title('PSH运行模式 (PSH Operating Mode)', fontsize=self.config.font_size + 2)
        ax2.set_yticks([-1, 0, 1])
        ax2.set_yticklabels(['抽水', '停机', '发电'])
        ax2.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax2.grid(self.config.show_grid, alpha=0.3)
        ax2.set_xlim(0, 24)

        # ===== 子图3: 净负荷与PSH响应 =====
        ax3 = axes[2]
        ax3.plot(hours, result.net_load, color='gray',
                linewidth=1.5, label='净负荷 (Net Load)')
        ax3.plot(hours, result.psh_power, color=self.COLORS['hydro'],
                linewidth=1.5, label='PSH功率')

        ax3.axhline(y=0, color='black', linewidth=0.5)
        ax3.set_xlabel('时间 (小时)', fontsize=self.config.font_size)
        ax3.set_ylabel('功率 (MW)', fontsize=self.config.font_size)
        ax3.set_title('净负荷与PSH响应 (Net Load and PSH Response)',
                     fontsize=self.config.font_size + 2)
        ax3.legend(loc='upper right', fontsize=self.config.font_size - 1)
        ax3.grid(self.config.show_grid, alpha=0.3)
        ax3.set_xlim(0, 24)

        plt.tight_layout()

        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'psh_operation.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def plot_comprehensive_dashboard(
        self,
        result,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制综合仪表板
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._generate_text_report(result, "dashboard")

        hours = result.time / 3600
        freq_dev = result.frequency - 50.0

        fig = plt.figure(figsize=(16, 12))
        gs = GridSpec(4, 3, figure=fig, hspace=0.3, wspace=0.25)

        # ===== 1. 功率堆叠图 (占2列) =====
        ax1 = fig.add_subplot(gs[0, :2])
        ax1.stackplot(hours,
                     result.wind_power,
                     result.solar_power,
                     result.hydro_power,
                     np.maximum(result.psh_power, 0),
                     np.maximum(result.sc_power + result.bess_power, 0),
                     labels=['风电', '光伏', '水电', 'PSH发电', 'HESS放电'],
                     colors=[self.COLORS['wind'], self.COLORS['solar'],
                            self.COLORS['hydro'], self.COLORS['psh_gen'],
                            self.COLORS['sc']],
                     alpha=0.7)
        ax1.plot(hours, result.load, 'k-', linewidth=2, label='负荷')
        ax1.set_title('发电与负荷平衡', fontsize=12)
        ax1.set_ylabel('功率 (MW)')
        ax1.legend(loc='upper right', fontsize=8)
        ax1.set_xlim(0, 24)
        ax1.grid(True, alpha=0.3)

        # ===== 2. 频率指标饼图 =====
        ax2 = fig.add_subplot(gs[0, 2])
        # 计算频率在各范围的时间占比
        in_normal = np.sum(np.abs(freq_dev) <= 0.2) / len(freq_dev) * 100
        in_warning = np.sum((np.abs(freq_dev) > 0.2) & (np.abs(freq_dev) <= 0.5)) / len(freq_dev) * 100
        in_critical = np.sum(np.abs(freq_dev) > 0.5) / len(freq_dev) * 100

        sizes = [in_normal, in_warning, in_critical]
        labels = [f'正常\n{in_normal:.1f}%', f'警告\n{in_warning:.1f}%', f'临界\n{in_critical:.1f}%']
        colors = ['green', 'yellow', 'red']
        explode = (0.05, 0.05, 0.1)

        ax2.pie(sizes, explode=explode, labels=labels, colors=colors,
               autopct='', startangle=90, shadow=True)
        ax2.set_title('频率质量分布', fontsize=12)

        # ===== 3. 频率曲线 =====
        ax3 = fig.add_subplot(gs[1, :2])
        ax3.plot(hours, result.frequency, color=self.COLORS['frequency'], linewidth=0.8)
        ax3.axhline(y=50.0, color='gray', linestyle='--', linewidth=0.5)
        ax3.fill_between(hours, 49.8, 50.2, alpha=0.2, color='green')
        ax3.set_ylabel('频率 (Hz)')
        ax3.set_title('系统频率', fontsize=12)
        ax3.set_xlim(0, 24)
        ax3.set_ylim(49.5, 50.5)
        ax3.grid(True, alpha=0.3)

        # ===== 4. 关键指标卡片 =====
        ax4 = fig.add_subplot(gs[1, 2])
        ax4.axis('off')
        metrics_text = (
            f"━━━ 关键性能指标 ━━━\n\n"
            f"频率偏差最大值: {result.frequency_deviation_max:.4f} Hz\n"
            f"频率偏差RMS: {result.frequency_deviation_rms:.4f} Hz\n"
            f"PSH模式切换: {result.psh_mode_switches} 次\n\n"
            f"风电利用率: {np.mean(result.wind_power)/50*100:.1f}%\n"
            f"光伏利用率: {np.mean(result.solar_power)/30*100:.1f}%\n\n"
            f"BESS最终SOC: {result.bess_soc[-1]*100:.1f}%\n"
            f"PSH最终水位: {result.psh_level[-1]*100:.1f}%"
        )
        ax4.text(0.1, 0.9, metrics_text, transform=ax4.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

        # ===== 5. 储能SOC =====
        ax5 = fig.add_subplot(gs[2, 0])
        ax5.plot(hours, result.sc_soc * 100, color=self.COLORS['sc'],
                linewidth=1.5, label='SC')
        ax5.plot(hours, result.bess_soc * 100, color=self.COLORS['bess'],
                linewidth=1.5, label='BESS')
        ax5.set_ylabel('SOC (%)')
        ax5.set_title('储能SOC', fontsize=12)
        ax5.legend(fontsize=8)
        ax5.set_xlim(0, 24)
        ax5.set_ylim(0, 100)
        ax5.grid(True, alpha=0.3)

        # ===== 6. PSH水位 =====
        ax6 = fig.add_subplot(gs[2, 1])
        ax6.fill_between(hours, 0, result.psh_level * 100,
                        alpha=0.6, color=self.COLORS['hydro'])
        ax6.axhline(y=15, color='red', linestyle=':', linewidth=1)
        ax6.axhline(y=95, color='red', linestyle=':', linewidth=1)
        ax6.set_ylabel('水位 (%)')
        ax6.set_title('PSH水库水位', fontsize=12)
        ax6.set_xlim(0, 24)
        ax6.set_ylim(0, 100)
        ax6.grid(True, alpha=0.3)

        # ===== 7. PSH功率 =====
        ax7 = fig.add_subplot(gs[2, 2])
        ax7.fill_between(hours, 0, np.maximum(result.psh_power, 0),
                        alpha=0.7, color=self.COLORS['psh_gen'], label='发电')
        ax7.fill_between(hours, 0, np.minimum(result.psh_power, 0),
                        alpha=0.7, color=self.COLORS['psh_pump'], label='抽水')
        ax7.axhline(y=0, color='black', linewidth=0.5)
        ax7.set_ylabel('功率 (MW)')
        ax7.set_title('PSH功率', fontsize=12)
        ax7.legend(fontsize=8)
        ax7.set_xlim(0, 24)
        ax7.grid(True, alpha=0.3)

        # ===== 8. 净负荷与调度 =====
        ax8 = fig.add_subplot(gs[3, :])
        ax8.plot(hours, result.net_load, 'k-', linewidth=1.5, label='净负荷', alpha=0.8)
        ax8.plot(hours, result.psh_power, color=self.COLORS['psh_gen'],
                linewidth=1.5, label='PSH功率')
        ax8.plot(hours, result.hydro_power, color=self.COLORS['hydro'],
                linewidth=1.5, label='水电功率')
        ax8.axhline(y=0, color='black', linewidth=0.5)
        ax8.set_xlabel('时间 (小时)')
        ax8.set_ylabel('功率 (MW)')
        ax8.set_title('净负荷与可调度电源协同', fontsize=12)
        ax8.legend(loc='upper right', fontsize=9)
        ax8.set_xlim(0, 24)
        ax8.grid(True, alpha=0.3)

        # 添加时段标注
        ax8.axvspan(11, 15, alpha=0.1, color='yellow', label='午间光伏高峰')
        ax8.axvspan(17, 21, alpha=0.1, color='red', label='晚间负荷高峰')

        plt.suptitle('多能互补系统全天候运行综合仪表板\n(Hydro-Wind-Solar-HESS-PSH Multi-Energy Complementary System)',
                    fontsize=14, fontweight='bold', y=0.98)

        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'comprehensive_dashboard.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def _generate_text_report(self, result, report_type: str) -> str:
        """生成文本报告(matplotlib不可用时)"""
        report_path = os.path.join(self.config.output_dir, f'{report_type}_report.txt')

        freq_dev = result.frequency - 50.0

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("多能互补系统仿真报告\n")
            f.write("=" * 60 + "\n\n")

            f.write("【频率性能】\n")
            f.write(f"  频率偏差最大值: {result.frequency_deviation_max:.4f} Hz\n")
            f.write(f"  频率偏差RMS: {result.frequency_deviation_rms:.4f} Hz\n")
            f.write(f"  频率偏差均值: {np.mean(freq_dev):.4f} Hz\n\n")

            f.write("【能源出力统计】\n")
            f.write(f"  风电平均出力: {np.mean(result.wind_power):.2f} MW\n")
            f.write(f"  光伏平均出力: {np.mean(result.solar_power):.2f} MW\n")
            f.write(f"  水电平均出力: {np.mean(result.hydro_power):.2f} MW\n")
            f.write(f"  PSH平均功率: {np.mean(result.psh_power):.2f} MW\n\n")

            f.write("【储能状态】\n")
            f.write(f"  SC最终SOC: {result.sc_soc[-1]*100:.1f}%\n")
            f.write(f"  BESS最终SOC: {result.bess_soc[-1]*100:.1f}%\n")
            f.write(f"  PSH最终水位: {result.psh_level[-1]*100:.1f}%\n\n")

            f.write("【PSH运行统计】\n")
            f.write(f"  模式切换次数: {result.psh_mode_switches} 次\n")

        return report_path

    def generate_all_plots(self, result) -> List[str]:
        """生成所有图表"""
        paths = []

        paths.append(self.plot_power_balance(result))
        paths.append(self.plot_frequency_response(result))
        paths.append(self.plot_storage_status(result))
        paths.append(self.plot_psh_operation(result))
        paths.append(self.plot_comprehensive_dashboard(result))

        return paths


def generate_daily_report(result, output_dir: str = "./output") -> str:
    """
    生成日运行报告

    Args:
        result: SimulationResult
        output_dir: 输出目录

    Returns:
        报告文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "daily_report.txt")

    freq_dev = result.frequency - 50.0

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("╔" + "═" * 58 + "╗\n")
        f.write("║" + " " * 10 + "多能互补系统日运行报告" + " " * 10 + "║\n")
        f.write("║" + " " * 5 + "Hydro-Wind-Solar-HESS-PSH Daily Report" + " " * 5 + "║\n")
        f.write("╚" + "═" * 58 + "╝\n\n")

        f.write("1. 频率性能指标\n")
        f.write("─" * 40 + "\n")
        f.write(f"  • 频率偏差最大值: {result.frequency_deviation_max:.4f} Hz\n")
        f.write(f"  • 频率偏差均方根: {result.frequency_deviation_rms:.4f} Hz\n")
        f.write(f"  • 频率偏差均值:   {np.mean(freq_dev):.4f} Hz\n")

        in_normal = np.sum(np.abs(freq_dev) <= 0.2) / len(freq_dev) * 100
        f.write(f"  • 频率正常时间占比: {in_normal:.1f}%\n\n")

        f.write("2. 能源出力统计\n")
        f.write("─" * 40 + "\n")
        f.write(f"  • 风电:  平均 {np.mean(result.wind_power):6.2f} MW, "
               f"最大 {np.max(result.wind_power):6.2f} MW\n")
        f.write(f"  • 光伏:  平均 {np.mean(result.solar_power):6.2f} MW, "
               f"最大 {np.max(result.solar_power):6.2f} MW\n")
        f.write(f"  • 水电:  平均 {np.mean(result.hydro_power):6.2f} MW, "
               f"最大 {np.max(result.hydro_power):6.2f} MW\n")
        f.write(f"  • PSH:   平均 {np.mean(result.psh_power):6.2f} MW, "
               f"范围 [{np.min(result.psh_power):6.2f}, {np.max(result.psh_power):6.2f}] MW\n")
        f.write(f"  • 负荷:  平均 {np.mean(result.load):6.2f} MW, "
               f"峰值 {np.max(result.load):6.2f} MW\n\n")

        f.write("3. 储能系统状态\n")
        f.write("─" * 40 + "\n")
        f.write(f"  • SC (超级电容):\n")
        f.write(f"      SOC范围: [{np.min(result.sc_soc)*100:.1f}%, {np.max(result.sc_soc)*100:.1f}%]\n")
        f.write(f"      最终SOC: {result.sc_soc[-1]*100:.1f}%\n")
        f.write(f"  • BESS (锂电池):\n")
        f.write(f"      SOC范围: [{np.min(result.bess_soc)*100:.1f}%, {np.max(result.bess_soc)*100:.1f}%]\n")
        f.write(f"      最终SOC: {result.bess_soc[-1]*100:.1f}%\n\n")

        f.write("4. 抽水蓄能电站(PSH)运行\n")
        f.write("─" * 40 + "\n")
        f.write(f"  • 模式切换次数: {result.psh_mode_switches} 次\n")
        f.write(f"  • 水库水位范围: [{np.min(result.psh_level)*100:.1f}%, {np.max(result.psh_level)*100:.1f}%]\n")
        f.write(f"  • 最终水位: {result.psh_level[-1]*100:.1f}%\n")

        # 统计各模式运行时间
        mode_counts = {}
        for m in result.psh_mode:
            mode_counts[m] = mode_counts.get(m, 0) + 1
        total_steps = len(result.psh_mode)

        f.write(f"  • 运行模式时间占比:\n")
        for mode, count in sorted(mode_counts.items()):
            pct = count / total_steps * 100
            f.write(f"      {mode:15s}: {pct:5.1f}%\n")

        f.write("\n5. 调峰填谷效果分析\n")
        f.write("─" * 40 + "\n")
        # 计算净负荷峰谷差
        net_load_peak = np.max(result.net_load)
        net_load_valley = np.min(result.net_load)
        f.write(f"  • 净负荷峰值: {net_load_peak:.2f} MW\n")
        f.write(f"  • 净负荷谷值: {net_load_valley:.2f} MW\n")
        f.write(f"  • 净负荷峰谷差: {net_load_peak - net_load_valley:.2f} MW\n")

        # 计算实际输出的峰谷差
        total_output = result.hydro_power + np.maximum(result.psh_power, 0)
        output_peak = np.max(total_output)
        output_valley = np.min(total_output)
        f.write(f"  • 调度输出峰值: {output_peak:.2f} MW\n")
        f.write(f"  • 调度输出谷值: {output_valley:.2f} MW\n")

        f.write("\n" + "═" * 60 + "\n")
        f.write("报告生成完毕\n")

    return report_path
