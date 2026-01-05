#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水利枢纽 HIL 仿真测试平台 - 综合演示
Comprehensive Demo for HIL Simulation Platform

本演示包含：
1. 所有类型阀门的控制测试
2. 水泵和闸门的控制测试
3. 参数敏感性分析
4. 完整的验收报告生成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hil_platform import HILPlatform
from src.test_cases import MultiValveTestSuite, ValveTestSuite, PumpTestSuite, GateTestSuite
from src.test_cases.sensitivity_analysis import ParameterSensitivityAnalyzer
from src.controllers import (
    FlowPressureRegulatingValve,
    WaterHammerReliefValve,
    EmergencyShutoffValve,
)


def demo_flow_pressure_valve():
    """演示调流调压阀控制"""
    print("\n" + "="*60)
    print("调流调压阀 (FPV) 控制演示")
    print("="*60)

    controller = FlowPressureRegulatingValve("FPV-DEMO")

    print("\n1. 流量控制模式")
    controller.set_flow_setpoint(10.0)
    print(f"   目标流量: {controller.flow_setpoint} m³/s")
    print(f"   控制模式: {controller.control_mode.value}")

    # 模拟几个控制周期
    for i in range(5):
        sensor_data = {
            'P1': 1.0 + i * 0.1,
            'P2': 0.6,
            'Q': 8.0 + i * 0.5,
            'opening': controller.valve_opening,
        }
        result = controller.run_cycle(sensor_data)
        controller.valve_opening = result['output']
        print(f"   周期{i+1}: 开度={controller.valve_opening:.3f}, "
              f"流量={sensor_data['Q']:.1f}m³/s")

    print("\n2. 压力控制模式")
    controller.set_pressure_setpoint(0.7)
    print(f"   目标压力: {controller.pressure_setpoint} MPa")

    for i in range(5):
        sensor_data = {
            'P1': 1.0,
            'P2': 0.65 + i * 0.02,
            'Q': 9.0,
            'opening': controller.valve_opening,
        }
        result = controller.run_cycle(sensor_data)
        controller.valve_opening = result['output']
        print(f"   周期{i+1}: 开度={controller.valve_opening:.3f}, "
              f"下游压力={sensor_data['P2']:.2f}MPa")


def demo_water_hammer_valve():
    """演示水锤消除阀控制"""
    print("\n" + "="*60)
    print("水锤消除阀 (WHV) 控制演示")
    print("="*60)

    controller = WaterHammerReliefValve("WHV-DEMO")
    controller.trigger_pressure = 1.5
    controller.reset_pressure = 1.2

    print(f"\n触发压力: {controller.trigger_pressure} MPa")
    print(f"复位压力: {controller.reset_pressure} MPa")

    print("\n模拟压力变化过程:")
    pressures = [1.0, 1.2, 1.4, 1.6, 1.8, 1.6, 1.4, 1.2, 1.0, 0.9]

    for i, p in enumerate(pressures):
        sensor_data = {'P': p}
        result = controller.run_cycle(sensor_data)
        status = "泄压中" if controller.is_relieving else "待命"
        print(f"   t={i}: P={p:.1f}MPa, 开度={result['output']:.1f}, 状态={status}")


def demo_emergency_valve():
    """演示事故阀控制"""
    print("\n" + "="*60)
    print("事故阀 (ESV) 控制演示")
    print("="*60)

    controller = EmergencyShutoffValve("ESV-DEMO")
    controller.full_close_time = 10.0
    controller.stage1_time = 2.0
    controller.stage2_time = 8.0

    print(f"\n关闭时间: {controller.full_close_time}s")
    print(f"第一阶段: {controller.stage1_time}s (快关到20%)")
    print(f"第二阶段: {controller.stage2_time}s (慢关到全关)")

    print("\n1. 模拟断电触发:")
    for i in range(15):
        t = i * 0.5
        power_fail = t >= 2.0

        sensor_data = {
            'P': 0.8,
            'Q': 8.0,
            'power_fail': power_fail,
            'opening': controller.valve_opening,
        }
        result = controller.run_cycle(sensor_data)
        controller.valve_opening = result['output']

        if power_fail:
            print(f"   t={t:.1f}s: 开度={controller.valve_opening*100:.1f}%, "
                  f"阶段={controller._close_stage}")


def demo_sensitivity_analysis():
    """演示参数敏感性分析"""
    print("\n" + "="*60)
    print("参数敏感性分析演示")
    print("="*60)

    analyzer = ParameterSensitivityAnalyzer(design_pressure=1.6)

    print("\n管长敏感性分析 (5km ~ 25km):\n")
    results = analyzer.analyze_pipe_length(
        length_range=(5000, 25000),
        step=5000
    )

    # 获取安全范围
    safe_range = analyzer.get_safe_range("pipe_length")
    print(f"\n安全范围: {safe_range}")


def run_all_test_suites():
    """运行所有测试套件"""
    print("\n" + "="*60)
    print("运行完整测试套件")
    print("="*60)

    suites = [
        ("多类型阀门", MultiValveTestSuite()),
    ]

    all_results = {}

    for name, suite in suites:
        print(f"\n运行 {name} 测试...")
        results = suite.run_all()
        suite.print_report()
        all_results[name] = suite.get_summary()

    return all_results


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     水利枢纽关键设备智能控制与数字验收规范                                  ║
║     HIL (Hardware-in-the-Loop) 仿真测试平台 - 综合演示                      ║
║                                                                              ║
║     版本: 1.0.0                                                              ║
║                                                                              ║
║     包含设备:                                                                ║
║       - 调流调压阀 (Flow/Pressure Regulating Valve)                         ║
║       - 水锤消除阀 (Water Hammer Relief Valve)                              ║
║       - 事故阀 (Emergency Shut-off Valve)                                   ║
║       - 智能泵控柜 (IPCU)                                                    ║
║       - 智能闸门控制柜 (IGCU)                                               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    demos = [
        ("1", "调流调压阀演示", demo_flow_pressure_valve),
        ("2", "水锤消除阀演示", demo_water_hammer_valve),
        ("3", "事故阀演示", demo_emergency_valve),
        ("4", "参数敏感性分析", demo_sensitivity_analysis),
        ("5", "完整测试套件", run_all_test_suites),
        ("0", "运行全部", None),
    ]

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        print("请选择演示内容:")
        for code, name, _ in demos:
            print(f"  {code}. {name}")
        print()
        choice = input("请输入选项 (0-5): ").strip()

    if choice == "0":
        # 运行全部
        for code, name, func in demos[:-1]:
            if func:
                func()
    else:
        # 运行选定的演示
        for code, name, func in demos:
            if code == choice and func:
                func()
                break
        else:
            print(f"未知选项: {choice}")

    print("\n" + "="*60)
    print("演示完成")
    print("="*60)


if __name__ == "__main__":
    main()
