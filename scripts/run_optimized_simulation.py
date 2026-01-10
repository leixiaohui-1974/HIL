#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行优化参数仿真并对比效果
Compare optimized vs default parameter simulation results
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from src.multi_energy import (
    MultiEnergySimulator,
    SimulationConfig,
    MultiEnergyVisualizer,
    generate_daily_report,
    OptimizedControllerParams,
    DefaultControllerParams
)


def run_comparison_simulation():
    """运行对比仿真"""

    print("=" * 60)
    print("多能互补系统参数优化效果对比仿真")
    print("=" * 60)

    # ===== 1. 运行优化参数仿真 =====
    print("\n[1] 运行优化参数仿真...")

    config_optimized = SimulationConfig(
        duration=86400.0,  # 24小时
        time_step=10.0,    # 10秒步长(加快仿真)
        use_optimized_params=True
    )

    simulator_opt = MultiEnergySimulator(config_optimized)
    result_opt = simulator_opt.run()

    # ===== 2. 运行默认参数仿真 =====
    print("\n[2] 运行默认参数仿真...")

    config_default = SimulationConfig(
        duration=86400.0,
        time_step=10.0,
        use_optimized_params=False
    )

    simulator_def = MultiEnergySimulator(config_default)
    result_def = simulator_def.run()

    # ===== 3. 对比结果 =====
    print("\n" + "=" * 60)
    print("仿真结果对比")
    print("=" * 60)

    print(f"\n{'指标':<30} {'默认参数':>15} {'优化参数':>15} {'改善':>10}")
    print("-" * 70)

    # 频率偏差最大值
    improvement = (result_def.frequency_deviation_max - result_opt.frequency_deviation_max) / result_def.frequency_deviation_max * 100
    print(f"{'频率偏差最大值 (Hz)':<30} {result_def.frequency_deviation_max:>15.4f} {result_opt.frequency_deviation_max:>15.4f} {improvement:>9.1f}%")

    # 频率偏差RMS
    improvement = (result_def.frequency_deviation_rms - result_opt.frequency_deviation_rms) / result_def.frequency_deviation_rms * 100
    print(f"{'频率偏差RMS (Hz)':<30} {result_def.frequency_deviation_rms:>15.4f} {result_opt.frequency_deviation_rms:>15.4f} {improvement:>9.1f}%")

    # 频率正常时间占比
    freq_dev_opt = result_opt.frequency - 50.0
    freq_dev_def = result_def.frequency - 50.0
    normal_ratio_opt = np.sum(np.abs(freq_dev_opt) < 0.5) / len(freq_dev_opt) * 100
    normal_ratio_def = np.sum(np.abs(freq_dev_def) < 0.5) / len(freq_dev_def) * 100
    improvement = normal_ratio_opt - normal_ratio_def
    print(f"{'频率正常时间占比 (%)':<30} {normal_ratio_def:>15.1f} {normal_ratio_opt:>15.1f} {improvement:>+9.1f}%")

    # 频率偏差均值
    mean_dev_opt = np.mean(freq_dev_opt)
    mean_dev_def = np.mean(freq_dev_def)
    print(f"{'频率偏差均值 (Hz)':<30} {mean_dev_def:>15.4f} {mean_dev_opt:>15.4f}")

    # PSH模式切换次数
    print(f"{'PSH模式切换次数':<30} {result_def.psh_mode_switches:>15} {result_opt.psh_mode_switches:>15}")

    print("\n" + "=" * 60)

    # ===== 4. 生成对比报告 =====
    print("\n生成优化效果报告...")

    output_dir = 'output/multi_energy'
    os.makedirs(output_dir, exist_ok=True)

    # 写入对比报告
    with open(f'{output_dir}/optimization_comparison.txt', 'w', encoding='utf-8') as f:
        f.write("╔══════════════════════════════════════════════════════════╗\n")
        f.write("║          参数优化效果对比报告                              ║\n")
        f.write("║     Controller Parameter Optimization Report              ║\n")
        f.write("╚══════════════════════════════════════════════════════════╝\n\n")

        f.write("1. 优化参数设置\n")
        f.write("────────────────────────────────────────\n")
        opt_params = OptimizedControllerParams()
        f.write(f"  • SC下垂增益: 20.0 → {opt_params.sc_droop_gain} MW/Hz\n")
        f.write(f"  • SC阻尼增益: 5.0 → {opt_params.sc_damping_gain} MW·s/Hz\n")
        f.write(f"  • SC额定功率: 10.0 → {opt_params.sc_rated_power} MW\n")
        f.write(f"  • BESS滤波时间: 2.0 → {opt_params.bess_filter_tau} s\n")
        f.write(f"  • BESS额定功率: 20.0 → {opt_params.bess_rated_power} MW\n")
        f.write(f"  • MPC频率校正: 50 → {opt_params.mpc_freq_correction} MW/Hz\n")
        f.write(f"  • 电网阻尼系数: 1.0 → {opt_params.grid_damping} p.u.\n")
        f.write("\n")

        f.write("2. 频率性能对比\n")
        f.write("────────────────────────────────────────\n")
        f.write(f"  │ {'指标':<25} │ {'默认':>10} │ {'优化':>10} │ {'改善':>8} │\n")
        f.write("  ├" + "─" * 27 + "┼" + "─" * 12 + "┼" + "─" * 12 + "┼" + "─" * 10 + "┤\n")

        improvement_max = (result_def.frequency_deviation_max - result_opt.frequency_deviation_max) / result_def.frequency_deviation_max * 100
        f.write(f"  │ {'最大偏差 (Hz)':<25} │ {result_def.frequency_deviation_max:>10.4f} │ {result_opt.frequency_deviation_max:>10.4f} │ {improvement_max:>+7.1f}% │\n")

        improvement_rms = (result_def.frequency_deviation_rms - result_opt.frequency_deviation_rms) / result_def.frequency_deviation_rms * 100
        f.write(f"  │ {'RMS偏差 (Hz)':<25} │ {result_def.frequency_deviation_rms:>10.4f} │ {result_opt.frequency_deviation_rms:>10.4f} │ {improvement_rms:>+7.1f}% │\n")

        f.write(f"  │ {'正常时间占比 (%)':<25} │ {normal_ratio_def:>10.1f} │ {normal_ratio_opt:>10.1f} │ {(normal_ratio_opt-normal_ratio_def):>+7.1f}% │\n")
        f.write("\n")

        f.write("3. 结论\n")
        f.write("────────────────────────────────────────\n")
        if result_opt.frequency_deviation_max < result_def.frequency_deviation_max:
            f.write("  ✓ 优化参数显著降低了频率偏差\n")
        if result_opt.frequency_deviation_rms < result_def.frequency_deviation_rms:
            f.write("  ✓ 频率波动RMS明显改善\n")
        if normal_ratio_opt > normal_ratio_def:
            f.write("  ✓ 频率正常运行时间大幅提升\n")
        f.write("\n═══════════════════════════════════════════════════════════\n")

    print(f"对比报告已保存至: {output_dir}/optimization_comparison.txt")

    # ===== 5. 生成优化后的日报告 =====
    print("\n生成优化后日报告...")
    generate_daily_report(result_opt, output_dir)

    # ===== 6. 生成可视化 =====
    print("\n生成可视化图表...")
    try:
        from src.multi_energy.visualization import VisualizationConfig
        viz_config = VisualizationConfig(output_dir=output_dir)
        visualizer = MultiEnergyVisualizer(viz_config)
        visualizer.plot_all(result_opt, output_dir)
    except Exception as e:
        print(f"可视化生成失败(可忽略): {e}")

    print("\n" + "=" * 60)
    print("仿真完成!")
    print("=" * 60)

    return result_opt, result_def


if __name__ == '__main__':
    run_comparison_simulation()
