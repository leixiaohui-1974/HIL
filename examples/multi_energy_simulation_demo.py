#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多能互补系统联合仿真演示
Multi-Energy Complementary System Joint Simulation Demo

本脚本演示如何使用多能互补系统模块进行全天候仿真:
1. 创建仿真配置
2. 运行联合仿真
3. 生成可视化报告
4. 分析PSH调峰填谷策略

Usage:
    python examples/multi_energy_simulation_demo.py

Author: HIL Multi-Energy System
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np

# 导入多能互补系统模块
from src.multi_energy.simulation import (
    MultiEnergySimulator,
    SimulationConfig,
    run_quick_simulation
)
from src.multi_energy.visualization import (
    MultiEnergyVisualizer,
    generate_daily_report
)
from src.multi_energy.psh_state_machine import (
    PSHStateMachine,
    PSHConstraints,
    PSHDispatcher,
    PSHOperatingMode
)


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def demo_basic_simulation():
    """
    演示1: 基础仿真
    使用默认配置运行24小时仿真
    """
    print_header("演示1: 基础仿真 (24小时典型日)")

    # 创建仿真配置
    config = SimulationConfig(
        duration=86400.0,      # 24小时
        time_step=10.0,        # 10秒步长(加速仿真)
        base_load=300.0,       # 基础负荷300MW
        wind_capacity=50.0,    # 风电50MW
        solar_capacity=30.0,   # 光伏30MW
        psh_power_gen=100.0,   # PSH发电100MW
        psh_power_pump=90.0,   # PSH抽水90MW
        hydro_power=200.0,     # 常规水电200MW
        sc_power=10.0,         # 超级电容10MW
        bess_power=20.0,       # 锂电池20MW
    )

    print(f"系统配置:")
    print(f"  - 基础负荷: {config.base_load} MW")
    print(f"  - 风电装机: {config.wind_capacity} MW")
    print(f"  - 光伏装机: {config.solar_capacity} MW")
    print(f"  - PSH容量: {config.psh_power_gen}/{config.psh_power_pump} MW (发电/抽水)")
    print(f"  - 常规水电: {config.hydro_power} MW")
    print(f"  - 储能: SC {config.sc_power}MW + BESS {config.bess_power}MW")

    # 创建仿真器
    simulator = MultiEnergySimulator(config)

    # 运行仿真
    print("\n开始仿真...")
    result = simulator.run()

    # 打印结果
    print(f"\n仿真结果:")
    print(f"  - 频率偏差最大值: {result.frequency_deviation_max:.4f} Hz")
    print(f"  - 频率偏差RMS: {result.frequency_deviation_rms:.4f} Hz")
    print(f"  - PSH模式切换次数: {result.psh_mode_switches}")

    return result


def demo_visualization(result):
    """
    演示2: 可视化结果
    """
    print_header("演示2: 生成可视化图表")

    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output', 'multi_energy')
    os.makedirs(output_dir, exist_ok=True)

    visualizer = MultiEnergyVisualizer()
    visualizer.config.output_dir = output_dir

    # 生成各类图表
    print("生成功率平衡图...")
    path1 = visualizer.plot_power_balance(result)
    print(f"  -> {path1}")

    print("生成频率响应图...")
    path2 = visualizer.plot_frequency_response(result)
    print(f"  -> {path2}")

    print("生成储能状态图...")
    path3 = visualizer.plot_storage_status(result)
    print(f"  -> {path3}")

    print("生成PSH运行图...")
    path4 = visualizer.plot_psh_operation(result)
    print(f"  -> {path4}")

    print("生成综合仪表板...")
    path5 = visualizer.plot_comprehensive_dashboard(result)
    print(f"  -> {path5}")

    # 生成日报告
    print("生成日运行报告...")
    report_path = generate_daily_report(result, output_dir)
    print(f"  -> {report_path}")


def demo_psh_strategy():
    """
    演示3: PSH调峰填谷策略分析
    """
    print_header("演示3: PSH调峰填谷策略分析")

    print("""
PSH调峰填谷策略说明:
====================

1. 午间光伏过剩期 (11:00-15:00)
   ─────────────────────────────
   • 新能源出力高峰,负荷相对平稳
   • PSH切换至"抽水"模式
   • 吸收过剩电力,将电能转化为势能储存

2. 晚高峰用电期 (17:00-21:00)
   ─────────────────────────────
   • 光伏出力骤降,负荷达到峰值
   • PSH切换至"发电"模式
   • 释放储存能量,填补新能源出力缺口

3. 夜间低谷期 (23:00-06:00)
   ─────────────────────────────
   • 负荷处于低谷,风电出力较好
   • PSH进行"抽水"储能
   • 为次日高峰做准备

4. 模式切换决策逻辑
   ─────────────────────────────
   • 基于净负荷(负荷-新能源)预测
   • 考虑水库水位约束
   • 遵守最短运行时间/停机时间约束
   • 采用模型预测控制(MPC)优化调度
    """)

    # 演示PSH状态机
    print("\nPSH状态机约束参数:")
    constraints = PSHConstraints()
    print(f"  - 抽水最短运行时间: {constraints.min_run_time_pump/60:.1f} 分钟")
    print(f"  - 发电最短运行时间: {constraints.min_run_time_gen/60:.1f} 分钟")
    print(f"  - 最短停机时间: {constraints.min_stop_time/60:.1f} 分钟")
    print(f"  - 模式切换死区: {constraints.mode_switch_deadband/60:.1f} 分钟")
    print(f"  - 抽水启动时间: {constraints.startup_time_pump/60:.1f} 分钟")
    print(f"  - 发电启动时间: {constraints.startup_time_gen/60:.1f} 分钟")
    print(f"  - 每日最大切换次数: {constraints.max_mode_switches_per_day} 次")

    # 演示调度决策
    print("\n演示PSH调度决策...")
    dispatcher = PSHDispatcher(
        rated_power_gen=100.0,
        rated_power_pump=90.0
    )

    # 模拟几个典型时段的决策
    test_cases = [
        {"hour": 3, "net_load": -20, "level": 0.4, "desc": "夜间低谷,风电过剩"},
        {"hour": 12, "net_load": -50, "level": 0.5, "desc": "午间,光伏过剩"},
        {"hour": 19, "net_load": 100, "level": 0.6, "desc": "晚高峰,负荷缺口"},
        {"hour": 22, "net_load": 30, "level": 0.35, "desc": "晚间,负荷下降"},
    ]

    print("\n调度决策示例:")
    print("-" * 70)

    from src.multi_energy.psh_state_machine import DispatchContext

    for case in test_cases:
        context = DispatchContext(
            current_time=case["hour"] * 3600,
            hour_of_day=case["hour"],
            net_load=case["net_load"],
            net_load_forecast=[case["net_load"]] * 12,
            reservoir_level=case["level"],
            current_mode=PSHOperatingMode.STOPPED
        )
        decision, power, reason = dispatcher.decide(context)
        print(f"  时间: {case['hour']:02d}:00 | {case['desc']}")
        print(f"    净负荷: {case['net_load']:+6.1f}MW | 水位: {case['level']*100:.0f}%")
        print(f"    决策: {decision.value} | 功率: {power:.1f}MW")
        print(f"    原因: {reason}")
        print()


def demo_hierarchical_control():
    """
    演示4: 分层控制架构
    """
    print_header("演示4: 分层控制架构")

    print("""
分层控制架构说明:
=================

┌─────────────────────────────────────────────────────────────┐
│                    功率不平衡 / 频率偏差                      │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │  第一层: 超级电容(SC)下垂控制    │
         │  • 响应时间: 1-10ms            │
         │  • 功能: 快速响应频率突变        │
         │  • 算法: ΔP = -Kp·Δf - Kd·RoCoF │
         └───────────────┬───────────────┘
                         │ 残差功率
         ┌───────────────┴───────────────┐
         │  第二层: 锂电池(BESS)滤波控制    │
         │  • 响应时间: 100ms-1s          │
         │  • 功能: 平滑功率波动,接管SC     │
         │  • 算法: 一阶低通滤波            │
         └───────────────┬───────────────┘
                         │ 残差功率
         ┌───────────────┴───────────────┐
         │  第三层: MPC协同控制            │
         │  • 响应时间: 1-10min           │
         │  • 功能: 调度PSH和常规水电       │
         │  • 算法: 滚动时域优化           │
         └───────────────┬───────────────┘
                         │
         ┌───────────────┴───────────────┐
         │     PSH + 常规水电出力调整      │
         └───────────────────────────────┘

响应链解耦:
==========
当风光瞬时波动发生时:
1. SC立即响应(毫秒级),稳定频率    ←─ 填补真空期
2. BESS逐渐接管SC的功率(秒级)    ←─ 恢复SC容量
3. PSH/水电在MPC调度下启动(分钟级)←─ 主力调节
4. BESS将功率移交给PSH/水电      ←─ 恢复BESS容量
5. SC恢复到待命状态              ←─ 准备下次响应

这种分层结构确保了"响应链条"的连续性!
    """)


def demo_quick_simulation():
    """
    演示5: 快速仿真
    """
    print_header("演示5: 快速仿真(1小时)")

    print("运行1小时快速仿真...")
    result = run_quick_simulation(
        duration_hours=1.0,
        time_step=1.0,
        base_load=300.0
    )

    print(f"\n快速仿真结果:")
    print(f"  - 仿真步数: {len(result.time)}")
    print(f"  - 频率偏差最大值: {result.frequency_deviation_max:.4f} Hz")
    print(f"  - 平均风电出力: {np.mean(result.wind_power):.2f} MW")
    print(f"  - 平均光伏出力: {np.mean(result.solar_power):.2f} MW")


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    水-风-光-储-抽 多能互补系统联合仿真演示                    ║
║    Hydro-Wind-Solar-HESS-PSH Multi-Energy Simulation Demo    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # 演示1: 基础仿真
    result = demo_basic_simulation()

    # 演示2: 可视化
    demo_visualization(result)

    # 演示3: PSH策略
    demo_psh_strategy()

    # 演示4: 分层控制
    demo_hierarchical_control()

    # 演示5: 快速仿真
    demo_quick_simulation()

    print_header("演示完成!")
    print("""
所有演示已完成。请查看以下输出:
  - output/multi_energy/  包含生成的图表和报告

如需更详细的分析,可以:
  1. 调整SimulationConfig参数
  2. 使用不同的场景(run_scenario_simulation)
  3. 自定义可视化配置
    """)


if __name__ == "__main__":
    main()
