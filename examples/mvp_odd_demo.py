#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MVP ODD框架演示
Minimum Viable Product ODD Framework Demonstration

核心原则：
- 先做出可审查、可验收、可定责的最小ODD集
- 再逐步扩展

四条硬边界：
1. 规范硬约束边界 - 从规范与计算书直接抽取
2. 执行硬能力边界 - 从设备参数与工况试验抽取
3. 信息硬条件边界 - 从系统架构与监测质量抽取
4. 组织硬兜底边界 - 能被演练与验收
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from mbd_framework.odd_mvp import (
    # 硬边界类型
    HardBoundaryType, BoundaryLevel, SourceType, SourceReference,
    # 四条硬边界
    RegulatoryBoundary, ExecutionBoundary, InformationBoundary, OrganizationBoundary,
    # MVP ODD
    MVPODDDefinition, MVPODDStatus,
    # 扩展
    SoftBoundaryCategory, SoftBoundary, ExtendedODD,
    # 工厂函数
    create_reservoir_mvp_odd, create_irrigation_mvp_odd,
    create_urban_supply_mvp_odd, create_flood_control_mvp_odd,
    # 验收
    MVPODDAcceptanceChecker,
)


def print_header(title: str, char: str = "="):
    """打印标题"""
    print(f"\n{char * 80}")
    print(f"  {title}")
    print(f"{char * 80}")


def test_hard_boundary_types():
    """测试四条硬边界类型"""
    print_header("四条硬边界类型")

    results = []

    print("\n  MVP ODD的四条硬边界：没有它们就谈不上自主运行\n")

    for bt in HardBoundaryType:
        print(f"  {bt.name}: {bt.value}")

    print("\n  [测试] 硬边界类型完整性")
    expected_types = ["REGULATORY", "EXECUTION", "INFORMATION", "ORGANIZATION"]
    actual_types = [bt.name for bt in HardBoundaryType]

    if set(expected_types) == set(actual_types):
        print(f"    ✓ 四条硬边界类型完整")
        results.append(True)
    else:
        print(f"    ✗ 硬边界类型不完整")
        results.append(False)

    return results


def test_source_traceability():
    """测试来源追溯"""
    print_header("来源追溯机制")

    results = []

    print("\n  每个阈值都能追溯来源是MVP ODD的核心工程特性\n")

    # 测试来源类型
    print("  来源类型：")
    for st in SourceType:
        print(f"    - {st.value}")

    # 测试来源引用
    source = SourceReference(
        source_type=SourceType.REGULATION,
        document_name="XX水库调度规程",
        document_id="SD-2023-001",
        section="4.2.1",
        page="15",
        extract_value="汛限水位145.0m"
    )

    print(f"\n  [测试] 来源引用生成")
    citation = source.to_citation()
    print(f"    引用: {citation}")

    if "XX水库调度规程" in citation and "4.2.1" in citation:
        print(f"    ✓ 来源引用生成正确")
        results.append(True)
    else:
        print(f"    ✗ 来源引用生成错误")
        results.append(False)

    return results


def test_boundary_evaluation():
    """测试边界评估"""
    print_header("边界分级评估")

    results = []

    print("\n  分级明确：正常/受限/禁止\n")

    # 创建一个规范硬约束边界
    boundary = RegulatoryBoundary(
        boundary_id="REG_TEST_001",
        name="水位边界",
        description="测试水位边界",
        boundary_type=HardBoundaryType.REGULATORY,
        parameter_name="water_level",
        unit="m",
        normal_max=145.0,
        normal_min=125.0,
        restricted_max=148.0,
        restricted_min=123.0,
        source=SourceReference(
            source_type=SourceType.REGULATION,
            document_name="调度规程",
            extract_value="汛限145m，死水位125m"
        ),
        normal_strategy="S3",
        restricted_strategy="S1",
        prohibited_action="S0+人工接管"
    )

    # 测试不同值的评估
    test_cases = [
        (135.0, BoundaryLevel.NORMAL, "S3"),      # 正常范围内
        (146.0, BoundaryLevel.RESTRICTED, "S1"),  # 受限范围
        (150.0, BoundaryLevel.PROHIBITED, "S0+人工接管"),  # 禁止范围
        (124.0, BoundaryLevel.RESTRICTED, "S1"),  # 低于正常
        (120.0, BoundaryLevel.PROHIBITED, "S0+人工接管"),  # 低于受限
    ]

    print("  [测试] 边界分级评估")
    all_correct = True
    for value, expected_level, expected_strategy in test_cases:
        level, msg = boundary.evaluate(value)
        strategy = boundary.get_strategy(level)

        status = "✓" if (level == expected_level) else "✗"
        print(f"    {status} 水位={value}m -> {level.value}, 策略={strategy}")

        if level != expected_level:
            all_correct = False

    results.append(all_correct)

    return results


def test_mvp_odd_creation():
    """测试MVP ODD创建"""
    print_header("MVP ODD创建")

    results = []

    print("\n  创建水库调度MVP ODD\n")

    odd = create_reservoir_mvp_odd()

    print(f"  ODD编号: {odd.odd_id}")
    print(f"  名称: {odd.name}")
    print(f"  版本: {odd.version}")
    print(f"  状态: {odd.status.value}")

    print(f"\n  四条硬边界统计:")
    print(f"    1. 规范硬约束: {len(odd.regulatory_boundaries)}项")
    print(f"    2. 执行硬能力: {len(odd.execution_boundaries)}项")
    print(f"    3. 信息硬条件: {len(odd.information_boundaries)}项")
    print(f"    4. 组织硬兜底: {len(odd.organization_boundaries)}项")

    # 验证完整性
    completeness = odd.validate_completeness()

    print(f"\n  [测试] MVP ODD完整性验证")
    print(f"    完整: {'是' if completeness['is_complete'] else '否'}")
    print(f"    总边界数: {completeness['statistics']['total']}")
    print(f"    已追溯来源: {completeness['statistics']['with_source']}")

    if completeness['is_complete']:
        print(f"    ✓ MVP ODD四条硬边界完整")
        results.append(True)
    else:
        print(f"    ✗ MVP ODD不完整: {completeness['missing']}")
        results.append(False)

    return results


def test_mvp_odd_evaluation():
    """测试MVP ODD运行点评估"""
    print_header("MVP ODD运行点评估")

    results = []

    odd = create_reservoir_mvp_odd()

    # 测试场景1: 正常运行
    print("\n  [场景1] 正常运行状态")
    values_normal = {
        'water_level': 140.0,
        'outflow': 500.0,
        'gate_opening': 50.0,
        'gate_speed': 0.5,
        'level_measurement_error': 1.0,
        'comm_latency': 200.0,
        'takeover_response_time': 3.0,
        'consultation_response_time': 20.0
    }
    result = odd.evaluate(values_normal)
    print(f"    整体等级: {result['overall_level']}")
    print(f"    允许策略: {result['allowed_strategy']}")
    print(f"    违规数: {len(result['violations'])}")
    print(f"    警告数: {len(result['warnings'])}")

    if result['overall_level'] == '正常' and result['allowed_strategy'] == 'S3':
        print(f"    ✓ 正常状态评估正确")
        results.append(True)
    else:
        print(f"    ✗ 正常状态评估错误")
        results.append(False)

    # 测试场景2: 受限状态
    print("\n  [场景2] 受限运行状态")
    values_restricted = {
        'water_level': 146.5,  # 超出正常，在受限内
        'outflow': 500.0,
        'gate_opening': 50.0,
        'gate_speed': 0.5,
        'level_measurement_error': 1.0,
        'comm_latency': 200.0,
        'takeover_response_time': 3.0,
        'consultation_response_time': 20.0
    }
    result = odd.evaluate(values_restricted)
    print(f"    整体等级: {result['overall_level']}")
    print(f"    允许策略: {result['allowed_strategy']}")
    print(f"    警告数: {len(result['warnings'])}")

    if result['overall_level'] == '受限':
        print(f"    ✓ 受限状态评估正确")
        results.append(True)
    else:
        print(f"    ✗ 受限状态评估错误")
        results.append(False)

    # 测试场景3: 禁止状态
    print("\n  [场景3] 禁止运行状态")
    values_prohibited = {
        'water_level': 150.0,  # 超出受限范围
        'outflow': 500.0,
        'gate_opening': 50.0,
        'gate_speed': 0.5,
        'level_measurement_error': 1.0,
        'comm_latency': 200.0,
        'takeover_response_time': 3.0,
        'consultation_response_time': 20.0
    }
    result = odd.evaluate(values_prohibited)
    print(f"    整体等级: {result['overall_level']}")
    print(f"    允许策略: {result['allowed_strategy']}")
    print(f"    违规数: {len(result['violations'])}")

    if result['overall_level'] == '禁止' and result['allowed_strategy'] == 'S0':
        print(f"    ✓ 禁止状态评估正确")
        results.append(True)
    else:
        print(f"    ✗ 禁止状态评估错误")
        results.append(False)

    return results


def test_acceptance_check():
    """测试验收检查"""
    print_header("MVP ODD验收检查")

    results = []

    print('\n  验收检查确保ODD"能验收、能定责、能复用"\n')

    checker = MVPODDAcceptanceChecker()

    # 测试完整的ODD
    odd = create_reservoir_mvp_odd()
    result = checker.check(odd)

    print(f"  ODD编号: {result['odd_id']}")
    print(f"  验收通过: {'是' if result['passed'] else '否'}")

    print(f"\n  检查项目:")
    for check in result['checks']:
        status = "✓" if check['passed'] else "✗"
        print(f"    {status} {check['name']}")
        for detail in check['details']:
            print(f"        {detail}")

    print(f"\n  汇总:")
    print(f"    检查总数: {result['summary']['total_checks']}")
    print(f"    通过数: {result['summary']['passed_checks']}")
    print(f"    边界总数: {result['summary']['total_boundaries']}")
    print(f"    验收就绪: {'是' if result['summary']['acceptance_ready'] else '否'}")

    if result['passed']:
        print(f"\n    ✓ MVP ODD通过验收检查")
        results.append(True)
    else:
        print(f"\n    ✗ MVP ODD未通过验收检查")
        results.append(False)

    return results


def test_audit_document():
    """测试审计文档生成"""
    print_header("审计文档生成")

    results = []

    odd = create_reservoir_mvp_odd()

    print("\n  生成审计文档（用于验收和定责）\n")

    doc = odd.generate_audit_document()

    # 检查文档包含关键部分
    required_sections = [
        "规范硬约束边界",
        "执行硬能力边界",
        "信息硬条件边界",
        "组织硬兜底边界",
        "完整性验证",
        "签署"
    ]

    print("  [测试] 文档结构完整性")
    all_found = True
    for section in required_sections:
        if section in doc:
            print(f"    ✓ 包含: {section}")
        else:
            print(f"    ✗ 缺少: {section}")
            all_found = False

    results.append(all_found)

    # 打印文档片段
    print("\n  [文档预览]")
    lines = doc.split('\n')[:25]
    for line in lines:
        print(f"    {line}")
    print("    ...")

    return results


def test_progressive_extension():
    """测试渐进扩展"""
    print_header("渐进扩展机制")

    results = []

    print("\n  MVP ODD跑通后，再逐步扩展软边界\n")

    # 创建MVP ODD
    mvp_odd = create_reservoir_mvp_odd()

    # 创建扩展ODD
    extended = ExtendedODD(mvp_odd=mvp_odd)

    print(f"  初始成熟度: {extended.get_maturity_level()}")

    # 添加软边界
    extended.add_soft_boundary(SoftBoundary(
        boundary_id="SOFT_001",
        name="预报误差统计",
        description="按季节、年景分型的预报误差",
        category=SoftBoundaryCategory.FORECAST_UNCERTAINTY,
        parameter_name="forecast_error_distribution",
        levels={"汛期": (0, 25), "枯期": (0, 15)},
        strategy_modifier="汛期采用更保守策略"
    ))

    print(f"  添加预报误差统计后: {extended.get_maturity_level()}")

    extended.add_soft_boundary(SoftBoundary(
        boundary_id="SOFT_002",
        name="多水源联动工况",
        description="多水源切换时的工况组合",
        category=SoftBoundaryCategory.SCENARIO_COMBINATION,
        parameter_name="multi_source_scenario",
        strategy_modifier="多源切换时降为S2"
    ))

    print(f"  添加工况组合后: {extended.get_maturity_level()}")

    extended.add_soft_boundary(SoftBoundary(
        boundary_id="SOFT_003",
        name="组织成熟度",
        description="根据接管能力确定策略上限",
        category=SoftBoundaryCategory.ORG_MATURITY,
        parameter_name="org_maturity_level",
        levels={"初级": (0, 1), "中级": (1, 2), "高级": (2, 3)},
        strategy_modifier="初级限制为S1"
    ))

    print(f"  添加组织成熟度后: {extended.get_maturity_level()}")

    # 验证渐进扩展
    if extended.get_maturity_level() == "L3-完整":
        print(f"\n    ✓ 渐进扩展正常工作")
        results.append(True)
    else:
        print(f"\n    ✗ 渐进扩展异常")
        results.append(False)

    return results


def test_all_water_networks():
    """测试所有水网类型的MVP ODD"""
    print_header("四类水网MVP ODD")

    results = []

    factories = [
        ("水库调度", create_reservoir_mvp_odd),
        ("灌区水网", create_irrigation_mvp_odd),
        ("城市供水", create_urban_supply_mvp_odd),
        ("防洪调度", create_flood_control_mvp_odd),
    ]

    checker = MVPODDAcceptanceChecker()

    for name, factory in factories:
        print(f"\n  [{name}]")
        odd = factory()

        # 验收检查
        result = checker.check(odd)

        print(f"    规范硬约束: {len(odd.regulatory_boundaries)}项")
        print(f"    执行硬能力: {len(odd.execution_boundaries)}项")
        print(f"    信息硬条件: {len(odd.information_boundaries)}项")
        print(f"    组织硬兜底: {len(odd.organization_boundaries)}项")
        print(f"    验收通过: {'✓' if result['passed'] else '✗'}")

        results.append(result['passed'])

    return results


def main():
    """主函数"""
    print_header("MVP ODD框架演示", "=")
    print("  核心原则：先做出可审查、可验收、可定责的最小ODD集")
    print('  ODD落地的关键不是"写得全"，而是"能验收、能定责、能复用"')

    all_results = []

    # 运行所有测试
    all_results.extend(test_hard_boundary_types())
    all_results.extend(test_source_traceability())
    all_results.extend(test_boundary_evaluation())
    all_results.extend(test_mvp_odd_creation())
    all_results.extend(test_mvp_odd_evaluation())
    all_results.extend(test_acceptance_check())
    all_results.extend(test_audit_document())
    all_results.extend(test_progressive_extension())
    all_results.extend(test_all_water_networks())

    # 统计结果
    passed = sum(all_results)
    total = len(all_results)

    print_header("测试结果汇总", "=")
    print(f"\n  总计: {total} 项测试")
    print(f"  通过: {passed} 项 ({100*passed/total:.1f}%)")
    print(f"  失败: {total-passed} 项")

    if passed == total:
        print("\n  结论: 所有测试通过! ✓")
    else:
        print(f"\n  结论: 有 {total-passed} 项测试需要关注")

    print_header("MVP ODD核心要点", "-")
    print('''
  1. 四条硬边界（没有它们就谈不上自主运行）
     - 规范硬约束：水位红线、流量压力边界、生态下泄等
     - 执行硬能力：闸门速度、泵站容量、备用冗余等
     - 信息硬条件：测量误差、通信延迟、预测精度等
     - 组织硬兜底：接管时间、权限链路、演练验收等

  2. 三个工程特性
     - 分级明确（正常/受限/禁止）
     - 每个阈值都能追溯来源（规范、设备、系统、预案）
     - 每个等级都映射到策略等级与退化动作

  3. 渐进扩展原则
     - MVP阶段：四条硬边界，可审查、可验收、可定责
     - L1扩展：加入预测误差统计
     - L2扩展：加入工况组合细化
     - L3扩展：加入风险偏好和组织成熟度

  4. 核心结论
     ODD落地的关键不是"写得全"，而是"能验收、能定责、能复用"
''')

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
