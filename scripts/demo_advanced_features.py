#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高级功能演示脚本
Advanced Features Demo Script

演示内容:
1. 多场景对比分析
2. 系统健康监测
3. 增强可视化报告
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from src.multi_energy import (
    # 场景分析
    ScenarioType,
    ScenarioLibrary,
    ScenarioRunner,
    ScenarioComparator,
    # 系统监控
    AlarmLevel,
    ComponentType,
    MonitoringConfig,
    SystemMonitor,
    PerformanceAnalyzer,
    # 仿真
    MultiEnergySimulator,
    SimulationConfig,
    # 可视化
    MultiEnergyVisualizer,
    generate_daily_report
)


def demo_scenario_comparison():
    """
    演示1: 多场景对比分析
    """
    print("\n" + "=" * 70)
    print("演示1: 多场景对比分析")
    print("=" * 70)

    # 获取预定义场景(只选择3个以节省时间)
    scenarios = [
        ScenarioLibrary.get_typical_day(),
        ScenarioLibrary.get_high_renewable(),
        ScenarioLibrary.get_peak_load()
    ]

    # 修改仿真时间为2小时(快速演示)
    for scenario in scenarios:
        scenario.config.duration = 7200.0  # 2小时
        scenario.config.time_step = 10.0

    print(f"\n选择场景: {[s.name for s in scenarios]}")

    # 运行场景
    runner = ScenarioRunner(verbose=True)
    results = runner.run_all_scenarios(scenarios)

    # 对比分析
    comparator = ScenarioComparator(results)
    report = comparator.compare()

    # 打印对比表格
    print("\n" + "-" * 50)
    print("场景对比表格")
    print("-" * 50)
    comparator.print_comparison_table()

    # 打印最佳场景
    print("\n各指标最佳场景:")
    for metric, best in report.best_scenario.items():
        print(f"  {metric}: {best}")

    return results


def demo_system_monitoring():
    """
    演示2: 系统健康监测
    """
    print("\n" + "=" * 70)
    print("演示2: 系统健康监测")
    print("=" * 70)

    # 创建监控器
    config = MonitoringConfig(
        freq_warning_threshold=0.3,
        freq_critical_threshold=0.8,
        soc_low_warning=0.2,
        soc_low_critical=0.1
    )
    monitor = SystemMonitor(config)
    analyzer = PerformanceAnalyzer()

    # 注册组件
    monitor.register_component(ComponentType.WIND_TURBINE, "风电场")
    monitor.register_component(ComponentType.SOLAR_PV, "光伏电站")
    monitor.register_component(ComponentType.BATTERY, "锂电池储能")
    monitor.register_component(ComponentType.HYDRO, "常规水电")
    monitor.register_component(ComponentType.PSH, "抽水蓄能")

    print("\n注册组件:")
    for name in monitor._component_status:
        print(f"  - {name}")

    # 运行短时仿真
    print("\n运行仿真并监测系统状态...")
    sim_config = SimulationConfig(
        duration=3600.0,  # 1小时
        time_step=10.0
    )
    simulator = MultiEnergySimulator(sim_config)
    result = simulator.run()

    # 模拟监测过程
    print("\n模拟监测过程...")
    n_samples = len(result.time)
    sample_interval = max(1, n_samples // 100)  # 采样100个点

    for i in range(0, n_samples, sample_interval):
        t = result.time[i]
        freq = result.frequency[i]
        wind = result.wind_power[i]
        solar = result.solar_power[i]
        hydro = result.hydro_power[i]
        bess_soc = result.bess_soc[i]
        psh_level = result.psh_level[i]

        total_gen = wind + solar + hydro + max(0, result.psh_power[i])
        total_load = result.load[i]

        # 更新电网状态
        monitor.update_grid(
            timestamp=t,
            frequency=freq,
            total_generation=total_gen,
            total_load=total_load
        )

        # 更新组件状态
        monitor.update_component("风电场", wind)
        monitor.update_component("光伏电站", solar)
        monitor.update_component("常规水电", hydro)
        monitor.update_component("锂电池储能", result.bess_power[i], soc=bess_soc)

        # 添加性能样本
        analyzer.add_sample(
            timestamp=t,
            frequency=freq,
            generation=total_gen,
            load=total_load
        )

    # 获取统计信息
    stats = monitor.get_statistics()
    print("\n监测统计:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    # 获取告警
    alarms = monitor.get_alarms()
    print(f"\n告警记录: {len(alarms)}条")
    if alarms:
        # 按级别统计
        level_counts = {}
        for alarm in alarms:
            level = alarm.level.name
            level_counts[level] = level_counts.get(level, 0) + 1
        for level, count in level_counts.items():
            print(f"  {level}: {count}条")

    # 生成健康报告
    report = monitor.generate_health_report()
    print("\n" + "-" * 50)
    print("系统健康报告预览(前30行):")
    print("-" * 50)
    for line in report.split('\n')[:30]:
        print(line)

    # 性能分析
    perf_stats = analyzer.analyze()
    if perf_stats:
        print("\n" + "-" * 50)
        print("性能分析结果:")
        print("-" * 50)
        for key, value in perf_stats.items():
            print(f"  {key}: {value:.4f}")

    return monitor, analyzer


def demo_enhanced_visualization():
    """
    演示3: 增强可视化
    """
    print("\n" + "=" * 70)
    print("演示3: 增强可视化报告")
    print("=" * 70)

    # 运行仿真
    print("\n运行24小时仿真...")
    config = SimulationConfig(
        duration=86400.0,
        time_step=30.0,  # 30秒步长加快仿真
        use_optimized_params=True
    )
    simulator = MultiEnergySimulator(config)
    result = simulator.run()

    print(f"\n仿真完成!")
    print(f"  频率偏差最大: {result.frequency_deviation_max:.4f} Hz")
    print(f"  频率偏差RMS: {result.frequency_deviation_rms:.4f} Hz")
    print(f"  PSH模式切换: {result.psh_mode_switches}次")

    # 生成可视化
    output_dir = 'output/demo_advanced'
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n生成可视化报告到: {output_dir}/")

    try:
        from src.multi_energy.visualization import VisualizationConfig
        viz_config = VisualizationConfig(output_dir=output_dir)
        visualizer = MultiEnergyVisualizer(viz_config)

        # 生成所有图表
        paths = visualizer.plot_all(result, output_dir)
        print(f"\n生成图表 {len(paths)}个:")
        for path in paths:
            if path:
                print(f"  - {os.path.basename(path)}")

    except Exception as e:
        print(f"可视化生成失败(可忽略): {e}")
        print("继续生成文本报告...")

    # 生成日报告
    report_path = generate_daily_report(result, output_dir)
    print(f"\n日报告: {report_path}")

    return result


def main():
    """主函数"""
    print("\n" + "#" * 70)
    print("#" + " " * 20 + "多能互补系统高级功能演示" + " " * 20 + "#")
    print("#" * 70)

    # 演示1: 场景对比
    try:
        scenario_results = demo_scenario_comparison()
    except Exception as e:
        print(f"场景对比演示失败: {e}")
        scenario_results = None

    # 演示2: 系统监测
    try:
        monitor, analyzer = demo_system_monitoring()
    except Exception as e:
        print(f"系统监测演示失败: {e}")
        monitor, analyzer = None, None

    # 演示3: 增强可视化
    try:
        result = demo_enhanced_visualization()
    except Exception as e:
        print(f"可视化演示失败: {e}")
        result = None

    # 总结
    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)
    print("\n功能总结:")
    print("  1. 多场景对比分析 - 支持批量仿真和性能对比")
    print("  2. 系统健康监测 - 实时告警和性能统计")
    print("  3. 增强可视化 - 健康仪表板和效率分析图")
    print("\n输出文件目录: output/demo_advanced/")


if __name__ == '__main__':
    main()
