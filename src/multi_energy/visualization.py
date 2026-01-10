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


    def plot_scenario_comparison(
        self,
        scenarios: dict,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制多场景对比图

        Args:
            scenarios: 字典格式 {scenario_name: SimulationResult}
            save_path: 保存路径
            show: 是否显示

        Returns:
            保存的文件路径
        """
        if not MATPLOTLIB_AVAILABLE or len(scenarios) == 0:
            return None

        scenario_names = list(scenarios.keys())
        n_scenarios = len(scenario_names)

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # ===== 1. 频率偏差对比 =====
        ax1 = axes[0, 0]
        freq_max = [scenarios[name].frequency_deviation_max for name in scenario_names]
        freq_rms = [scenarios[name].frequency_deviation_rms for name in scenario_names]

        x = np.arange(n_scenarios)
        width = 0.35
        bars1 = ax1.bar(x - width/2, freq_max, width, label='最大偏差', color=self.COLORS['frequency'])
        bars2 = ax1.bar(x + width/2, freq_rms, width, label='RMS偏差', color=self.COLORS['bess'])

        ax1.set_ylabel('频率偏差 (Hz)')
        ax1.set_title('各场景频率性能对比')
        ax1.set_xticks(x)
        ax1.set_xticklabels(scenario_names, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 添加数值标签
        for bar in bars1:
            height = bar.get_height()
            ax1.annotate(f'{height:.3f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=8)

        # ===== 2. PSH模式切换次数对比 =====
        ax2 = axes[0, 1]
        psh_switches = [scenarios[name].psh_mode_switches for name in scenario_names]
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, n_scenarios))
        bars = ax2.bar(scenario_names, psh_switches, color=colors)

        ax2.set_ylabel('模式切换次数')
        ax2.set_title('PSH运行稳定性对比')
        ax2.set_xticklabels(scenario_names, rotation=45, ha='right')
        ax2.grid(True, alpha=0.3)

        for bar, val in zip(bars, psh_switches):
            ax2.annotate(f'{val}',
                        xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=10)

        # ===== 3. 频率曲线叠加对比 =====
        ax3 = axes[1, 0]
        colors_line = plt.cm.tab10(np.linspace(0, 1, n_scenarios))

        for i, name in enumerate(scenario_names):
            result = scenarios[name]
            hours = result.time / 3600
            ax3.plot(hours, result.frequency, color=colors_line[i],
                    linewidth=1, label=name, alpha=0.8)

        ax3.axhline(y=50.0, color='gray', linestyle='--', linewidth=0.5)
        ax3.fill_between([0, 24], 49.8, 50.2, alpha=0.1, color='green')
        ax3.set_xlabel('时间 (小时)')
        ax3.set_ylabel('频率 (Hz)')
        ax3.set_title('频率曲线对比')
        ax3.set_xlim(0, 24)
        ax3.set_ylim(49.0, 51.0)
        ax3.legend(fontsize=8, loc='upper right')
        ax3.grid(True, alpha=0.3)

        # ===== 4. 储能利用率对比 =====
        ax4 = axes[1, 1]

        # 计算储能利用率(功率变化范围/额定容量)
        sc_util = []
        bess_util = []
        for name in scenario_names:
            result = scenarios[name]
            sc_range = np.max(result.sc_power) - np.min(result.sc_power)
            bess_range = np.max(result.bess_power) - np.min(result.bess_power)
            sc_util.append(sc_range / 15.0 * 100)  # 假设SC额定15MW
            bess_util.append(bess_range / 25.0 * 100)  # 假设BESS额定25MW

        x = np.arange(n_scenarios)
        bars1 = ax4.bar(x - width/2, sc_util, width, label='超级电容', color=self.COLORS['sc'])
        bars2 = ax4.bar(x + width/2, bess_util, width, label='锂电池', color=self.COLORS['bess'])

        ax4.set_ylabel('功率利用率 (%)')
        ax4.set_title('储能系统利用率对比')
        ax4.set_xticks(x)
        ax4.set_xticklabels(scenario_names, rotation=45, ha='right')
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'scenario_comparison.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def plot_system_health_dashboard(
        self,
        result,
        alarms: List[dict] = None,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制系统健康状态仪表板

        Args:
            result: SimulationResult对象
            alarms: 告警列表
            save_path: 保存路径
            show: 是否显示

        Returns:
            保存的文件路径
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        hours = result.time / 3600
        freq_dev = result.frequency - 50.0

        fig = plt.figure(figsize=(16, 12))
        gs = GridSpec(4, 4, figure=fig, hspace=0.35, wspace=0.3)

        # ===== 1. 系统健康评分仪表盘 =====
        ax1 = fig.add_subplot(gs[0, 0])

        # 计算健康评分
        freq_score = max(0, 100 - result.frequency_deviation_max * 50)
        stability_score = max(0, 100 - result.psh_mode_switches * 2)
        soc_score = 100 - abs(result.bess_soc[-1] - 0.5) * 100
        overall_score = (freq_score + stability_score + soc_score) / 3

        # 绘制仪表盘
        theta = np.linspace(0, np.pi, 100)
        r = 1
        ax1.fill_between(theta, 0, r, alpha=0.3, color='lightgray')

        # 评分指针
        score_angle = np.pi * (1 - overall_score / 100)
        ax1.plot([0, np.cos(score_angle)], [0, np.sin(score_angle)],
                'k-', linewidth=3)
        ax1.plot(np.cos(score_angle), np.sin(score_angle), 'ko', markersize=10)

        # 颜色区域
        for i, (start, end, color) in enumerate([
            (0, np.pi/3, 'red'),
            (np.pi/3, 2*np.pi/3, 'yellow'),
            (2*np.pi/3, np.pi, 'green')
        ]):
            theta_seg = np.linspace(start, end, 30)
            ax1.fill_between(theta_seg, 0.8, 1.0, alpha=0.5, color=color)

        ax1.set_xlim(-1.2, 1.2)
        ax1.set_ylim(-0.2, 1.2)
        ax1.set_aspect('equal')
        ax1.axis('off')
        ax1.set_title(f'系统健康评分: {overall_score:.1f}', fontsize=12, fontweight='bold')

        # ===== 2. 子系统健康状态 =====
        ax2 = fig.add_subplot(gs[0, 1])

        components = ['频率控制', 'PSH运行', 'HESS储能', '水电调度']
        scores = [freq_score, stability_score, soc_score, min(100, np.mean(result.hydro_power)/200*100)]
        colors = ['green' if s > 70 else 'yellow' if s > 40 else 'red' for s in scores]

        bars = ax2.barh(components, scores, color=colors, alpha=0.7)
        ax2.set_xlim(0, 100)
        ax2.set_xlabel('健康评分')
        ax2.set_title('子系统健康状态')
        ax2.grid(True, alpha=0.3, axis='x')

        for bar, score in zip(bars, scores):
            ax2.text(score + 2, bar.get_y() + bar.get_height()/2,
                    f'{score:.0f}', va='center', fontsize=10)

        # ===== 3. 频率偏差热力图 =====
        ax3 = fig.add_subplot(gs[0, 2:])

        # 将频率偏差按小时重采样
        n_hours = 24
        samples_per_hour = len(freq_dev) // n_hours
        freq_hourly = freq_dev[:n_hours * samples_per_hour].reshape(n_hours, samples_per_hour)

        im = ax3.imshow(np.abs(freq_hourly.T), aspect='auto', cmap='RdYlGn_r',
                       extent=[0, 24, 0, samples_per_hour], vmin=0, vmax=1)
        ax3.set_xlabel('小时')
        ax3.set_ylabel('时段内采样点')
        ax3.set_title('频率偏差热力图 (深色=偏差大)')
        plt.colorbar(im, ax=ax3, label='|Δf| (Hz)')

        # ===== 4. 功率平衡趋势 =====
        ax4 = fig.add_subplot(gs[1, :2])

        total_gen = result.wind_power + result.solar_power + result.hydro_power + np.maximum(result.psh_power, 0)
        power_balance = total_gen - result.load

        ax4.fill_between(hours, 0, power_balance, where=power_balance > 0,
                        alpha=0.5, color='green', label='发电盈余')
        ax4.fill_between(hours, 0, power_balance, where=power_balance < 0,
                        alpha=0.5, color='red', label='发电不足')
        ax4.axhline(y=0, color='black', linewidth=0.5)
        ax4.set_xlabel('时间 (小时)')
        ax4.set_ylabel('功率差额 (MW)')
        ax4.set_title('系统功率平衡状态')
        ax4.legend()
        ax4.set_xlim(0, 24)
        ax4.grid(True, alpha=0.3)

        # ===== 5. 储能SOC走廊 =====
        ax5 = fig.add_subplot(gs[1, 2:])

        ax5.fill_between(hours, result.bess_soc * 100, 50,
                        where=result.bess_soc * 100 > 50, alpha=0.3, color='blue', label='充电状态')
        ax5.fill_between(hours, result.bess_soc * 100, 50,
                        where=result.bess_soc * 100 < 50, alpha=0.3, color='orange', label='放电状态')
        ax5.plot(hours, result.bess_soc * 100, 'k-', linewidth=1)
        ax5.axhline(y=20, color='red', linestyle='--', alpha=0.5, label='低SOC警戒')
        ax5.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='高SOC警戒')
        ax5.set_xlabel('时间 (小时)')
        ax5.set_ylabel('BESS SOC (%)')
        ax5.set_title('储能SOC运行走廊')
        ax5.set_xlim(0, 24)
        ax5.set_ylim(0, 100)
        ax5.legend(fontsize=8)
        ax5.grid(True, alpha=0.3)

        # ===== 6. 频率质量时段分析 =====
        ax6 = fig.add_subplot(gs[2, :2])

        # 按4小时时段统计
        n_periods = 6
        period_labels = ['0-4h', '4-8h', '8-12h', '12-16h', '16-20h', '20-24h']
        samples_per_period = len(freq_dev) // n_periods

        normal_pct = []
        warning_pct = []
        critical_pct = []

        for i in range(n_periods):
            start = i * samples_per_period
            end = (i + 1) * samples_per_period
            period_freq = freq_dev[start:end]

            normal = np.sum(np.abs(period_freq) <= 0.2) / len(period_freq) * 100
            warning = np.sum((np.abs(period_freq) > 0.2) & (np.abs(period_freq) <= 0.5)) / len(period_freq) * 100
            critical = np.sum(np.abs(period_freq) > 0.5) / len(period_freq) * 100

            normal_pct.append(normal)
            warning_pct.append(warning)
            critical_pct.append(critical)

        x = np.arange(n_periods)
        ax6.bar(x, normal_pct, label='正常 (±0.2Hz)', color='green', alpha=0.7)
        ax6.bar(x, warning_pct, bottom=normal_pct, label='警告 (±0.5Hz)', color='yellow', alpha=0.7)
        ax6.bar(x, critical_pct, bottom=np.array(normal_pct)+np.array(warning_pct),
               label='临界 (>0.5Hz)', color='red', alpha=0.7)

        ax6.set_xticks(x)
        ax6.set_xticklabels(period_labels)
        ax6.set_ylabel('时间占比 (%)')
        ax6.set_title('频率质量时段分析')
        ax6.legend(fontsize=8)
        ax6.grid(True, alpha=0.3, axis='y')

        # ===== 7. 告警统计 =====
        ax7 = fig.add_subplot(gs[2, 2:])

        if alarms and len(alarms) > 0:
            # 统计各级别告警数量
            alarm_counts = {'info': 0, 'warning': 0, 'critical': 0, 'emergency': 0}
            for alarm in alarms:
                level = alarm.get('level', 'info')
                alarm_counts[level] = alarm_counts.get(level, 0) + 1

            levels = list(alarm_counts.keys())
            counts = list(alarm_counts.values())
            colors = ['lightblue', 'yellow', 'orange', 'red']

            ax7.pie(counts, labels=[f'{l}\n({c})' for l, c in zip(levels, counts)],
                   colors=colors, autopct='%1.1f%%', startangle=90)
        else:
            # 无告警时显示绿色
            ax7.pie([1], colors=['lightgreen'], labels=['系统正常\n无告警'])

        ax7.set_title('告警级别分布')

        # ===== 8. 系统运行摘要 =====
        ax8 = fig.add_subplot(gs[3, :])
        ax8.axis('off')

        # 构建摘要文本
        in_normal = np.sum(np.abs(freq_dev) <= 0.2) / len(freq_dev) * 100
        energy_wind = np.sum(result.wind_power) * (result.time[1] - result.time[0]) / 3600 / 1000  # MWh -> GWh
        energy_solar = np.sum(result.solar_power) * (result.time[1] - result.time[0]) / 3600 / 1000

        summary_text = (
            f"╔═══════════════════════════════════════════════════════════════════════════════════════╗\n"
            f"║                              系统运行健康摘要                                          ║\n"
            f"╠═══════════════════════════════════════════════════════════════════════════════════════╣\n"
            f"║  综合健康评分: {overall_score:5.1f}/100    频率正常时间: {in_normal:5.1f}%    PSH切换: {result.psh_mode_switches:3d}次           ║\n"
            f"║  频率偏差最大: {result.frequency_deviation_max:5.3f}Hz   频率偏差RMS: {result.frequency_deviation_rms:5.3f}Hz                         ║\n"
            f"║  新能源发电量: 风电{energy_wind*1000:.1f}MWh + 光伏{energy_solar*1000:.1f}MWh                                    ║\n"
            f"║  储能最终状态: SC-SOC={result.sc_soc[-1]*100:4.1f}%  BESS-SOC={result.bess_soc[-1]*100:4.1f}%  PSH水位={result.psh_level[-1]*100:4.1f}%    ║\n"
            f"╚═══════════════════════════════════════════════════════════════════════════════════════╝"
        )

        ax8.text(0.5, 0.5, summary_text, transform=ax8.transAxes,
                fontsize=10, family='monospace',
                verticalalignment='center', horizontalalignment='center',
                bbox=dict(boxstyle='round', facecolor='lightcyan', alpha=0.5))

        plt.suptitle('多能互补系统健康状态监控仪表板', fontsize=14, fontweight='bold', y=0.98)

        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'system_health_dashboard.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def plot_energy_efficiency_analysis(
        self,
        result,
        save_path: Optional[str] = None,
        show: bool = False
    ) -> Optional[str]:
        """
        绘制能源效率分析图

        Args:
            result: SimulationResult对象
            save_path: 保存路径
            show: 是否显示

        Returns:
            保存的文件路径
        """
        if not MATPLOTLIB_AVAILABLE:
            return None

        hours = result.time / 3600
        dt = result.time[1] - result.time[0]  # 时间步长(秒)

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # ===== 1. 新能源消纳率 =====
        ax1 = axes[0, 0]

        # 计算每小时的新能源出力和消纳
        renewable_total = result.wind_power + result.solar_power
        curtailment = np.maximum(renewable_total - result.net_load - 50, 0)  # 假设弃电阈值

        ax1.fill_between(hours, 0, renewable_total, alpha=0.5, color=self.COLORS['wind'], label='新能源出力')
        ax1.fill_between(hours, renewable_total - curtailment, renewable_total,
                        alpha=0.7, color='red', label='弃风弃光')
        ax1.plot(hours, result.load, 'k--', linewidth=1, label='负荷')

        ax1.set_xlabel('时间 (小时)')
        ax1.set_ylabel('功率 (MW)')
        ax1.set_title('新能源消纳情况')
        ax1.legend()
        ax1.set_xlim(0, 24)
        ax1.grid(True, alpha=0.3)

        # ===== 2. 储能效率分析 =====
        ax2 = axes[0, 1]

        # 计算储能充放电量
        sc_charge = np.sum(np.maximum(result.sc_power, 0)) * dt / 3600  # MWh
        sc_discharge = np.sum(np.maximum(-result.sc_power, 0)) * dt / 3600
        bess_charge = np.sum(np.maximum(result.bess_power, 0)) * dt / 3600
        bess_discharge = np.sum(np.maximum(-result.bess_power, 0)) * dt / 3600

        categories = ['SC充电', 'SC放电', 'BESS充电', 'BESS放电']
        values = [sc_charge, sc_discharge, bess_charge, bess_discharge]
        colors = [self.COLORS['sc'], self.COLORS['sc'], self.COLORS['bess'], self.COLORS['bess']]
        alphas = [0.5, 1.0, 0.5, 1.0]

        bars = ax2.bar(categories, values, color=colors)
        for bar, alpha in zip(bars, alphas):
            bar.set_alpha(alpha)

        ax2.set_ylabel('电量 (MWh)')
        ax2.set_title('储能充放电量统计')
        ax2.grid(True, alpha=0.3, axis='y')

        # 添加数值标签
        for bar in bars:
            height = bar.get_height()
            ax2.annotate(f'{height:.1f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=10)

        # ===== 3. 各电源贡献度 =====
        ax3 = axes[1, 0]

        # 计算各电源发电量
        energy_wind = np.sum(result.wind_power) * dt / 3600
        energy_solar = np.sum(result.solar_power) * dt / 3600
        energy_hydro = np.sum(result.hydro_power) * dt / 3600
        energy_psh_gen = np.sum(np.maximum(result.psh_power, 0)) * dt / 3600
        energy_hess = np.sum(np.maximum(-result.sc_power - result.bess_power, 0)) * dt / 3600

        sources = ['风电', '光伏', '水电', 'PSH发电', 'HESS放电']
        energies = [energy_wind, energy_solar, energy_hydro, energy_psh_gen, energy_hess]
        colors = [self.COLORS['wind'], self.COLORS['solar'], self.COLORS['hydro'],
                 self.COLORS['psh_gen'], self.COLORS['sc']]

        wedges, texts, autotexts = ax3.pie(energies, labels=sources, colors=colors,
                                           autopct='%1.1f%%', startangle=90)
        ax3.set_title('各电源发电量占比')

        # ===== 4. 系统运行效率曲线 =====
        ax4 = axes[1, 1]

        # 计算效率指标(发电量/负荷的匹配程度)
        total_gen = result.wind_power + result.solar_power + result.hydro_power + np.maximum(result.psh_power, 0)
        efficiency = np.minimum(total_gen / (result.load + 0.1), 1.5) * 100  # 限制在150%以内

        ax4.plot(hours, efficiency, color='green', linewidth=1.5)
        ax4.axhline(y=100, color='blue', linestyle='--', linewidth=1, label='完美匹配')
        ax4.fill_between(hours, 95, 105, alpha=0.2, color='green', label='目标区间')

        ax4.set_xlabel('时间 (小时)')
        ax4.set_ylabel('发电/负荷比 (%)')
        ax4.set_title('系统供需匹配效率')
        ax4.legend()
        ax4.set_xlim(0, 24)
        ax4.set_ylim(50, 150)
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path is None:
            save_path = os.path.join(self.config.output_dir, 'energy_efficiency_analysis.png')
        plt.savefig(save_path, dpi=self.config.dpi, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return save_path

    def plot_all(self, result, output_dir: str = None) -> List[str]:
        """生成所有图表(增强版)"""
        if output_dir:
            self.config.output_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)

        paths = self.generate_all_plots(result)

        # 添加增强图表
        try:
            paths.append(self.plot_system_health_dashboard(result))
            paths.append(self.plot_energy_efficiency_analysis(result))
        except Exception as e:
            print(f"增强图表生成失败: {e}")

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
