#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水利枢纽智能控制柜 HIL 数字验收流程
Digital Factory Acceptance Test (FAT) Workflow

完整的数字验收流程，包括：
1. 设备信息录入
2. 测试工况执行
3. 参数敏感性分析
4. 验收报告生成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.test_cases import MultiValveTestSuite
from src.test_cases.sensitivity_analysis import ParameterSensitivityAnalyzer
from src.report_generator import HILReportGenerator


def run_digital_fat(device_type: str = "IVCU",
                    device_id: str = "TEST-001",
                    quick_mode: bool = True) -> HILReportGenerator:
    """运行数字验收测试

    Args:
        device_type: 设备类型 (IVCU/IPCU/IGCU)
        device_id: 设备编号
        quick_mode: 快速模式（跳过敏感性分析）

    Returns:
        报告生成器实例
    """
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     水利枢纽智能控制柜 HIL 数字验收测试                                     ║
║     Digital Factory Acceptance Test (FAT)                                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # 初始化报告生成器
    generator = HILReportGenerator()

    # 1. 设备信息
    print("【步骤 1/4】录入设备信息")
    print("-" * 60)
    generator.set_device_info(
        device_type=device_type,
        device_id=device_id,
        manufacturer="水利智控科技有限公司",
        model=f"{device_type}-DN2000",
    )
    print(f"  设备类型: {device_type}")
    print(f"  设备编号: {device_id}")

    # 2. 测试环境
    print("\n【步骤 2/4】配置测试环境")
    print("-" * 60)
    generator.set_test_environment(
        test_location="HIL仿真实验室",
    )
    print("  测试环境已配置")

    # 3. 执行测试
    print("\n【步骤 3/4】执行测试工况")
    print("-" * 60)

    # 根据设备类型选择测试套件
    if device_type == "IVCU":
        suite = MultiValveTestSuite()
        suite_name = "阀门控制柜测试"
    else:
        suite = MultiValveTestSuite()  # 使用通用测试
        suite_name = f"{device_type}测试"

    print(f"  运行 {suite_name}...")
    results = suite.run_all()
    summary = suite.get_summary()

    generator.add_test_result(suite_name, summary)

    print(f"\n  测试完成:")
    print(f"    通过: {summary['passed']}/{summary['total']}")
    print(f"    通过率: {summary['pass_rate']*100:.1f}%")

    # 4. 敏感性分析
    if not quick_mode:
        print("\n【步骤 4/4】参数敏感性分析")
        print("-" * 60)

        analyzer = ParameterSensitivityAnalyzer(design_pressure=1.6)
        analyzer.analyze_pipe_length(
            length_range=(5000, 25000),
            step=5000
        )

        safe_range = analyzer.get_safe_range("pipe_length")
        generator.add_sensitivity_data("pipe_length", safe_range)

        print(f"  管长安全范围: {safe_range.get('safe_range', 'N/A')}")
    else:
        print("\n【步骤 4/4】参数敏感性分析 (已跳过 - 快速模式)")

    return generator


def main():
    """主函数"""
    # 解析命令行参数
    device_type = "IVCU"
    device_id = "IVCU-2024-001"
    quick_mode = True

    if len(sys.argv) > 1:
        device_type = sys.argv[1].upper()
    if len(sys.argv) > 2:
        device_id = sys.argv[2]
    if len(sys.argv) > 3 and sys.argv[3] == "--full":
        quick_mode = False

    # 运行验收测试
    generator = run_digital_fat(
        device_type=device_type,
        device_id=device_id,
        quick_mode=quick_mode
    )

    # 生成报告
    print("\n" + "=" * 60)
    print("生成验收报告")
    print("=" * 60)

    report = generator.generate_text_report()
    print(report)

    # 保存报告
    report_file = f"FAT_Report_{device_id}.txt"
    generator.save_report(report_file, format='text')
    print(f"\n报告已保存至: {report_file}")

    json_file = f"FAT_Report_{device_id}.json"
    generator.save_report(json_file, format='json')
    print(f"JSON数据已保存至: {json_file}")


if __name__ == "__main__":
    main()
