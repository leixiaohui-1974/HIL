#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水利枢纽 HIL 仿真测试平台演示
Hardware-in-the-Loop Simulation Platform Demo

本演示展示了针对水利枢纽关键设备的智能控制与数字验收规范的完整实现，
包括阀门(IVCU)、水泵(IPCU)、闸门(IGCU)三类智能控制柜的HIL测试。

运行方式:
    python -m examples.run_demo           # 运行完整演示
    python -m examples.run_demo valve     # 仅运行阀门测试
    python -m examples.run_demo pump      # 仅运行水泵测试
    python -m examples.run_demo gate      # 仅运行闸门测试
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hil_platform import HILPlatform, create_platform
from src.test_cases import ValveTestSuite, PumpTestSuite, GateTestSuite


def print_banner():
    """打印横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     水利枢纽关键设备智能控制与数字验收规范                                  ║
║     HIL (Hardware-in-the-Loop) 仿真测试平台                                 ║
║                                                                              ║
║     版本: 1.0.0                                                              ║
║     适用设备: IVCU (阀门) | IPCU (水泵) | IGCU (闸门)                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def run_valve_demo():
    """运行阀门测试演示"""
    print("\n" + "="*70)
    print("阀门控制柜 (IVCU) HIL 测试")
    print("="*70)

    print("""
测试项目:
  VC-01: 断电水锤防护 - 验证两阶段液压关闭曲线
  VC-02: 误关阀冲击  - 验证高流速锁定保护
  VC-03: 卡涩故障    - 验证卡涩检测与报警
  VC-04: 传感器失效  - 验证降级运行模式
""")

    platform = HILPlatform()
    platform.setup_valve_test()

    print("正在执行阀门测试套件...")
    results = platform.run_test_suite('valve')

    platform.test_suites['valve'].print_report()

    return results


def run_pump_demo():
    """运行水泵测试演示"""
    print("\n" + "="*70)
    print("水泵控制柜 (IPCU) HIL 测试")
    print("="*70)

    print("""
测试项目:
  PC-01: 软启动平稳性 - 验证S形曲线启动
  PC-02: 事故跳闸飞逸 - 验证倒转保护
  PC-03: 泵阀联动失效 - 验证闷泵保护
  PC-04: 气蚀/低效区  - 验证运行区间限制
""")

    platform = HILPlatform()
    platform.setup_pump_test()

    print("正在执行水泵测试套件...")
    results = platform.run_test_suite('pump')

    platform.test_suites['pump'].print_report()

    return results


def run_gate_demo():
    """运行闸门测试演示"""
    print("\n" + "="*70)
    print("闸门控制柜 (IGCU) HIL 测试")
    print("="*70)

    print("""
测试项目:
  GC-01: 负荷弃用防漫堤 - 验证柔性关闭曲线
  GC-02: 恒定流量伺服   - 验证流量控制精度
  GC-03: 传感器漂移容错 - 验证故障容错能力
""")

    platform = HILPlatform()
    platform.setup_gate_test()

    print("正在执行闸门测试套件...")
    results = platform.run_test_suite('gate')

    platform.test_suites['gate'].print_report()

    return results


def run_full_demo():
    """运行完整演示"""
    print_banner()

    print("""
本演示将执行以下内容:
  1. 阀门控制柜 (IVCU) 必测工况集 (VC-01 ~ VC-04)
  2. 水泵控制柜 (IPCU) 必测工况集 (PC-01 ~ PC-04)
  3. 闸门控制柜 (IGCU) 必测工况集 (GC-01 ~ GC-03)

这些测试覆盖了水利枢纽关键设备的核心安全功能验证。
""")

    input("按 Enter 键开始测试...")

    all_results = {}

    # 阀门测试
    all_results['valve'] = run_valve_demo()
    print("\n" + "-"*40)
    input("阀门测试完成，按 Enter 继续水泵测试...")

    # 水泵测试
    all_results['pump'] = run_pump_demo()
    print("\n" + "-"*40)
    input("水泵测试完成，按 Enter 继续闸门测试...")

    # 闸门测试
    all_results['gate'] = run_gate_demo()

    # 生成总报告
    print("\n")
    platform = HILPlatform()
    report = platform.generate_report(all_results)
    print(report)

    # 保存结果
    try:
        platform.export_results(all_results, 'hil_test_results.json')
        print("\n测试结果已保存至: hil_test_results.json")
    except Exception as e:
        print(f"\n保存测试结果时出错: {e}")

    return all_results


def run_quick_demo():
    """快速演示（无交互）"""
    print_banner()
    print("快速模式：自动执行所有测试\n")

    platform = create_platform('all')
    all_results = platform.run_all_tests()

    report = platform.generate_report(all_results)
    print(report)

    return all_results


def demo_single_test():
    """演示单个测试用例"""
    print_banner()

    print("可用的测试用例:")
    print("-" * 40)
    print("阀门测试:")
    print("  VC-01: 断电水锤防护测试")
    print("  VC-02: 误关阀冲击测试")
    print("  VC-03: 卡涩故障演练")
    print("  VC-04: 压力传感器失效测试")
    print("")
    print("水泵测试:")
    print("  PC-01: 软启动平稳性测试")
    print("  PC-02: 事故跳闸飞逸测试")
    print("  PC-03: 泵阀联动失效测试")
    print("  PC-04: 气蚀/低效区运行测试")
    print("")
    print("闸门测试:")
    print("  GC-01: 负荷弃用防漫堤测试")
    print("  GC-02: 恒定流量伺服测试")
    print("  GC-03: 传感器漂移容错测试")
    print("-" * 40)

    # 示例：运行单个测试
    print("\n示例: 运行 VC-01 断电水锤防护测试\n")

    from src.test_cases.valve_cases import VC01_PowerFailureWaterHammer

    test = VC01_PowerFailureWaterHammer()
    result = test.execute()

    print(result.summary())


def main():
    """主函数"""
    if len(sys.argv) < 2:
        run_full_demo()
    else:
        test_type = sys.argv[1].lower()

        if test_type == 'valve':
            run_valve_demo()
        elif test_type == 'pump':
            run_pump_demo()
        elif test_type == 'gate':
            run_gate_demo()
        elif test_type == 'quick':
            run_quick_demo()
        elif test_type == 'single':
            demo_single_test()
        elif test_type == 'help':
            print(__doc__)
        else:
            print(f"未知选项: {test_type}")
            print("可用选项: valve, pump, gate, quick, single, help")
            sys.exit(1)


if __name__ == "__main__":
    main()
