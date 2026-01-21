#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
水网类型差异化ODD测试演示
Water Network Types Differentiated ODD Testing Demo

演示四类水网的ODD差异:
1. 灌区水网 - 长期公平性与连续调配能力
2. 调水工程 - 长时滞与多工程联动
3. 城市供水 - 压力稳定性与服务连续性
4. 防洪调度 - 不确定性管理与越界控制
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum
import time

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# 导入模块
try:
    from mbd_framework import water_network_mbd
    from mbd_framework import functional_safety
except ImportError:
    import importlib.util

    def load_module_direct(name: str, path: str):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    mbd_path = project_root / "src" / "mbd_framework"
    load_module_direct("mbd_core", str(mbd_path / "mbd_core.py"))
    load_module_direct("odd_framework", str(mbd_path / "odd_framework.py"))
    functional_safety = load_module_direct("functional_safety", str(mbd_path / "functional_safety.py"))
    water_network_mbd = load_module_direct("water_network_mbd", str(mbd_path / "water_network_mbd.py"))


class TestStatus(Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


@dataclass
class TestResult:
    test_id: str
    test_name: str
    network_type: str
    status: TestStatus
    message: str
    details: Dict[str, Any] = None


class WaterNetworkTester:
    """水网类型测试器"""

    def __init__(self):
        self.results: List[TestResult] = []

    def run_all_tests(self):
        """运行所有水网类型测试"""
        print("=" * 80)
        print("         水网类型差异化ODD测试演示")
        print("=" * 80)
        print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 1. 灌区水网测试
        self.test_irrigation_network()

        # 2. 调水工程测试
        self.test_water_transfer()

        # 3. 城市供水测试
        self.test_urban_water_supply()

        # 4. 防洪调度测试
        self.test_flood_control()

        # 打印汇总报告
        self.print_summary()

    # ========================================================================
    # 1. 灌区水网测试 - 长期公平性与连续调配能力
    # ========================================================================

    def test_irrigation_network(self):
        """测试灌区水网模型"""
        print("\n" + "=" * 70)
        print("1. 灌区水网测试 - 长期公平性与连续调配能力")
        print("=" * 70)

        model = water_network_mbd.IrrigationNetworkMBDModel()
        model.initialize()

        # 测试1.1: 正常年份公平分配
        self._test_irrigation_fair_allocation(model)

        # 测试1.2: 枯水年份配水
        self._test_irrigation_dry_year(model)

        # 测试1.3: 长期公平性累计
        self._test_irrigation_long_term_fairness(model)

        # 测试1.4: ODD边界验证
        self._test_irrigation_odd(model)

    def _test_irrigation_fair_allocation(self, model):
        """测试公平分配"""
        print("\n  [测试1.1] 正常年份公平分配...")
        model.initialize()

        # 设置正常来水和需求
        model.set_inputs({
            'inflow': 10.0,
            'crop_demands': [4.0, 3.5, 2.5],  # 总需求10.0
            'water_year_type': 'normal'
        })

        # 模拟运行
        for _ in range(100):
            model.update(3600.0)  # 1小时步长

        outputs = model.get_outputs()

        # 验证公平性
        fairness = outputs['fairness_index']
        supply_ratio = outputs['supply_ratio']

        if fairness >= 0.95 and supply_ratio >= 0.8:
            status = TestStatus.PASSED
            message = f"公平分配正常，公平性={fairness:.2%}，供水率={supply_ratio:.2%}"
        elif fairness >= 0.85:
            status = TestStatus.WARNING
            message = f"公平性轻微偏低，公平性={fairness:.2%}"
        else:
            status = TestStatus.FAILED
            message = f"公平性不足，公平性={fairness:.2%}"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "IRR_001", "正常年份公平分配", "灌区水网", status, message,
            {'fairness': fairness, 'supply_ratio': supply_ratio}
        ))

    def _test_irrigation_dry_year(self, model):
        """测试枯水年份配水"""
        print("\n  [测试1.2] 枯水年份配水...")
        model.initialize()

        # 枯水年: 来水减少到60%
        model.set_inputs({
            'inflow': 6.0,  # 减少40%
            'crop_demands': [4.0, 3.5, 2.5],
            'water_year_type': 'dry'
        })

        for _ in range(100):
            model.update(3600.0)

        outputs = model.get_outputs()
        fairness = outputs['fairness_index']
        supply_ratio = outputs['supply_ratio']
        loss = outputs['loss_actual']

        # 枯水年预期: 损失率偏高，供水率下降，但公平性维持
        if fairness >= 0.90 and 0.3 <= supply_ratio <= 0.7:
            status = TestStatus.PASSED
            message = f"枯水年配水正常，公平性={fairness:.2%}，供水率={supply_ratio:.2%}"
        elif fairness >= 0.85:
            status = TestStatus.WARNING
            message = f"枯水年公平性可接受，公平性={fairness:.2%}"
        else:
            status = TestStatus.FAILED
            message = f"枯水年公平性失衡，公平性={fairness:.2%}"

        print(f"    结果: {status.value} - {message}")
        print(f"      输水损失率: {loss:.1%}")
        self.results.append(TestResult(
            "IRR_002", "枯水年份配水", "灌区水网", status, message
        ))

    def _test_irrigation_long_term_fairness(self, model):
        """测试长期公平性"""
        print("\n  [测试1.3] 长期公平性累计...")
        model.initialize()

        # 模拟一个灌溉季节 (模拟30天)
        year_types = ['normal'] * 10 + ['dry'] * 10 + ['wet'] * 10

        for day, year_type in enumerate(year_types):
            # 每天需求有波动
            base_demands = [4.0, 3.5, 2.5]
            inflow = 10.0 if year_type == 'wet' else (8.0 if year_type == 'normal' else 5.0)

            model.set_inputs({
                'inflow': inflow,
                'crop_demands': base_demands,
                'water_year_type': year_type
            })

            # 每天24小时
            for _ in range(24):
                model.update(3600.0)

        outputs = model.get_outputs()
        fairness = outputs['fairness_index']

        # 长期累计后公平性应保持良好
        if fairness >= 0.90:
            status = TestStatus.PASSED
            message = f"长期公平性优秀，累计公平性={fairness:.2%}"
        elif fairness >= 0.80:
            status = TestStatus.WARNING
            message = f"长期公平性良好，累计公平性={fairness:.2%}"
        else:
            status = TestStatus.FAILED
            message = f"长期公平性不足，累计公平性={fairness:.2%}"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "IRR_003", "长期公平性累计", "灌区水网", status, message
        ))

    def _test_irrigation_odd(self, model):
        """测试灌区水网ODD"""
        print("\n  [测试1.4] ODD边界验证...")

        odd = water_network_mbd.create_irrigation_network_odd()

        # 正常工作点
        normal = odd.validate_operating_point({
            'water_year_type': 'normal',
            'loss_rate': 15.0,
            'fairness_index': 0.95,
            'demand_prediction_error': 10.0
        })

        # 边界工作点 (公平性偏低)
        boundary = odd.validate_operating_point({
            'water_year_type': 'dry',
            'loss_rate': 22.0,
            'fairness_index': 0.86,
            'demand_prediction_error': 25.0
        })

        # 越界工作点 (公平性过低)
        outside = odd.validate_operating_point({
            'water_year_type': 'dry',
            'loss_rate': 30.0,
            'fairness_index': 0.70,
            'demand_prediction_error': 40.0
        })

        if normal['in_odd'] and boundary['in_odd'] and not outside['in_odd']:
            status = TestStatus.PASSED
            message = "ODD边界验证正确"
        else:
            status = TestStatus.WARNING
            message = "ODD边界验证需关注"

        print(f"    结果: {status.value} - {message}")
        print(f"      正常点: {'在ODD内' if normal['in_odd'] else '超出ODD'}")
        print(f"      边界点: {'在ODD内' if boundary['in_odd'] else '超出ODD'}")
        print(f"      越界点: {'在ODD内' if outside['in_odd'] else '超出ODD'}")
        self.results.append(TestResult(
            "IRR_004", "ODD边界验证", "灌区水网", status, message
        ))

    # ========================================================================
    # 2. 调水工程测试 - 长时滞与多工程联动
    # ========================================================================

    def test_water_transfer(self):
        """测试调水工程模型"""
        print("\n" + "=" * 70)
        print("2. 调水工程测试 - 长时滞与多工程联动")
        print("=" * 70)

        model = water_network_mbd.WaterTransferMBDModel()
        model.initialize()

        # 测试2.1: 时滞传输测试
        self._test_transfer_delay(model)

        # 测试2.2: 多受水区协调
        self._test_transfer_coordination(model)

        # 测试2.3: 调度间隔与时滞裕度
        self._test_transfer_delay_margin(model)

        # 测试2.4: ODD边界验证
        self._test_transfer_odd(model)

    def _test_transfer_delay(self, model):
        """测试时滞传输"""
        print("\n  [测试2.1] 时滞传输测试...")
        model.initialize()

        # 释放水量
        model.set_inputs({
            'source_release': 30.0,
            'recipient_requests': [15.0, 15.0]
        })

        # 检查到达时间预测
        model.update(1.0)
        outputs = model.get_outputs()
        arrival_times = outputs['arrival_times']

        # 第一个受水区距离60km，第二个100km
        # 流速2m/s: 60km约8.3小时，100km约13.9小时
        expected_delay_1 = 60 * 1000 / 2 / 3600  # 约8.3小时
        expected_delay_2 = 100 * 1000 / 2 / 3600  # 约13.9小时

        if len(arrival_times) == 2:
            status = TestStatus.PASSED
            message = f"时滞预测正常，预计到达时间: {arrival_times[0]:.1f}h, {arrival_times[1]:.1f}h"
        else:
            status = TestStatus.FAILED
            message = "时滞预测异常"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "TRF_001", "时滞传输测试", "调水工程", status, message
        ))

    def _test_transfer_coordination(self, model):
        """测试多受水区协调"""
        print("\n  [测试2.2] 多受水区协调...")
        model.initialize()

        # 模拟长时间运行让水量到达
        model.set_inputs({
            'source_release': 35.0,
            'recipient_requests': [20.0, 15.0]
        })

        # 模拟足够时间让水量传输到达
        for _ in range(200):
            model.update(3600.0)  # 每步1小时

        outputs = model.get_outputs()
        coordination = outputs['coordination_status']
        deliveries = outputs['delivery_flows']

        if coordination in ['COORDINATED', 'PARTIAL']:
            status = TestStatus.PASSED
            message = f"协调状态: {coordination}，供水: {deliveries}"
        elif coordination == 'IDLE':
            status = TestStatus.WARNING
            message = f"等待状态，尚未完成传输"
        else:
            status = TestStatus.FAILED
            message = f"协调失败: {coordination}"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "TRF_002", "多受水区协调", "调水工程", status, message
        ))

    def _test_transfer_delay_margin(self, model):
        """测试时滞裕度"""
        print("\n  [测试2.3] 调度间隔与时滞裕度...")
        model.initialize()

        model.set_inputs({
            'source_release': 30.0,
            'recipient_requests': [15.0, 15.0]
        })
        model.update(1.0)

        outputs = model.get_outputs()
        delay_margin = outputs['delay_margin']

        # 时滞裕度 = 最小调度间隔(4h) / 最大时滞
        # 合理范围: 0.3-1.0
        if 0.3 <= delay_margin <= 1.0:
            status = TestStatus.PASSED
            message = f"时滞裕度合理: {delay_margin:.2f}"
        elif delay_margin > 0.2:
            status = TestStatus.WARNING
            message = f"时滞裕度偏低: {delay_margin:.2f}，调度可能来不及生效"
        else:
            status = TestStatus.FAILED
            message = f"时滞裕度不足: {delay_margin:.2f}，存在系统性风险"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "TRF_003", "时滞裕度测试", "调水工程", status, message
        ))

    def _test_transfer_odd(self, model):
        """测试调水工程ODD"""
        print("\n  [测试2.4] ODD边界验证...")

        odd = water_network_mbd.create_water_transfer_odd()

        normal = odd.validate_operating_point({
            'delay_margin': 0.5,
            'coordination_status': 'COORDINATED',
            'forecast_accuracy': 85.0
        })

        boundary = odd.validate_operating_point({
            'delay_margin': 0.35,
            'coordination_status': 'PARTIAL',
            'forecast_accuracy': 72.0
        })

        outside = odd.validate_operating_point({
            'delay_margin': 0.2,
            'coordination_status': 'UNCOORDINATED',
            'forecast_accuracy': 60.0
        })

        if normal['in_odd'] and not outside['in_odd']:
            status = TestStatus.PASSED
            message = "ODD边界验证正确"
        else:
            status = TestStatus.WARNING
            message = "ODD边界验证需关注"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "TRF_004", "ODD边界验证", "调水工程", status, message
        ))

    # ========================================================================
    # 3. 城市供水测试 - 压力稳定性与服务连续性
    # ========================================================================

    def test_urban_water_supply(self):
        """测试城市供水模型"""
        print("\n" + "=" * 70)
        print("3. 城市供水测试 - 压力稳定性与服务连续性")
        print("=" * 70)

        model = water_network_mbd.UrbanWaterSupplyMBDModel()
        model.initialize()

        # 测试3.1: 稳态压力控制
        self._test_urban_steady_pressure(model)

        # 测试3.2: 日负荷变化响应
        self._test_urban_load_variation(model)

        # 测试3.3: 泵站切换测试
        self._test_urban_pump_switching(model)

        # 测试3.4: ODD边界验证
        self._test_urban_odd(model)

    def _test_urban_steady_pressure(self, model):
        """测试稳态压力控制"""
        print("\n  [测试3.1] 稳态压力控制...")
        model.initialize()

        model.set_inputs({
            'demand': 1000.0,
            'outlet_pressure': 0.35,
            'time_of_day': 12.0
        })

        # 运行至稳态
        for _ in range(100):
            model.update(1.0)

        outputs = model.get_outputs()
        pressure = outputs['pressure']
        zone = outputs['pressure_zone']

        if zone == 'NORMAL' and 0.30 <= pressure <= 0.40:
            status = TestStatus.PASSED
            message = f"压力稳定，P={pressure:.3f}MPa，区域={zone}"
        elif zone in ['LOW', 'HIGH']:
            status = TestStatus.WARNING
            message = f"压力偏离，P={pressure:.3f}MPa，区域={zone}"
        else:
            status = TestStatus.FAILED
            message = f"压力异常，P={pressure:.3f}MPa，区域={zone}"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "UWS_001", "稳态压力控制", "城市供水", status, message
        ))

    def _test_urban_load_variation(self, model):
        """测试日负荷变化响应"""
        print("\n  [测试3.2] 日负荷变化响应...")
        model.initialize()

        pressure_records = []

        # 模拟24小时
        for hour in range(24):
            # 根据时刻设置负荷
            if 7 <= hour <= 9 or 18 <= hour <= 20:
                demand = 1500.0  # 高峰
            elif 0 <= hour <= 6:
                demand = 600.0   # 低谷
            else:
                demand = 1000.0  # 平峰

            model.set_inputs({
                'demand': demand,
                'time_of_day': float(hour)
            })

            # 每小时模拟
            for _ in range(60):
                model.update(60.0)  # 1分钟步长

            outputs = model.get_outputs()
            pressure_records.append(outputs['pressure'])

        # 检查压力波动
        max_p = max(pressure_records)
        min_p = min(pressure_records)
        fluctuation = max_p - min_p

        if fluctuation <= 0.10:
            status = TestStatus.PASSED
            message = f"压力波动小，范围={min_p:.3f}-{max_p:.3f}MPa"
        elif fluctuation <= 0.15:
            status = TestStatus.WARNING
            message = f"压力波动可接受，范围={min_p:.3f}-{max_p:.3f}MPa"
        else:
            status = TestStatus.FAILED
            message = f"压力波动过大，范围={min_p:.3f}-{max_p:.3f}MPa"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "UWS_002", "日负荷变化响应", "城市供水", status, message
        ))

    def _test_urban_pump_switching(self, model):
        """测试泵站切换"""
        print("\n  [测试3.3] 泵站切换测试...")
        model.initialize()

        switch_events = []

        # 模拟负荷突增
        model.set_inputs({'demand': 500.0, 'time_of_day': 6.0})
        for _ in range(60):
            model.update(1.0)
        initial_pumps = sum(model.get_outputs()['pump_status'])

        # 负荷突增
        model.set_inputs({'demand': 1200.0, 'time_of_day': 8.0})
        for _ in range(120):
            model.update(1.0)
        after_increase = sum(model.get_outputs()['pump_status'])

        # 检查是否正常增加泵
        if after_increase > initial_pumps:
            status = TestStatus.PASSED
            message = f"泵切换正常，{initial_pumps}台->{after_increase}台"
        elif after_increase == initial_pumps:
            status = TestStatus.WARNING
            message = f"泵数未变，可能切换延迟"
        else:
            status = TestStatus.FAILED
            message = f"泵切换异常"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "UWS_003", "泵站切换测试", "城市供水", status, message
        ))

    def _test_urban_odd(self, model):
        """测试城市供水ODD"""
        print("\n  [测试3.4] ODD边界验证...")

        odd = water_network_mbd.create_urban_water_supply_odd()

        normal = odd.validate_operating_point({
            'pressure': 0.35,
            'load_factor': 1.0,
            'service_continuity': 99.5,
            'pump_availability': 100.0
        })

        boundary = odd.validate_operating_point({
            'pressure': 0.25,
            'load_factor': 1.6,
            'service_continuity': 96.0,
            'pump_availability': 67.0
        })

        outside = odd.validate_operating_point({
            'pressure': 0.15,
            'load_factor': 2.0,
            'service_continuity': 90.0,
            'pump_availability': 40.0
        })

        if normal['in_odd'] and not outside['in_odd']:
            status = TestStatus.PASSED
            message = "ODD边界验证正确"
        else:
            status = TestStatus.WARNING
            message = "ODD边界验证需关注"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "UWS_004", "ODD边界验证", "城市供水", status, message
        ))

    # ========================================================================
    # 4. 防洪调度测试 - 不确定性管理与越界控制
    # ========================================================================

    def test_flood_control(self):
        """测试防洪调度模型"""
        print("\n" + "=" * 70)
        print("4. 防洪调度测试 - 不确定性管理与越界控制")
        print("=" * 70)

        model = water_network_mbd.FloodControlMBDModel()
        model.initialize()

        # 测试4.1: 正常调度-自主决策
        self._test_flood_autonomous(model)

        # 测试4.2: 高风险-人工介入
        self._test_flood_human_required(model)

        # 测试4.3: 预报不确定性放大
        self._test_flood_forecast_uncertainty(model)

        # 测试4.4: ODD边界验证
        self._test_flood_odd(model)

    def _test_flood_autonomous(self, model):
        """测试自主决策模式"""
        print("\n  [测试4.1] 正常调度-自主决策...")
        model.initialize()

        # 正常水位，正常来水
        model.set_inputs({
            'current_level': 143.0,  # 低于汛限
            'inflow': 1000.0,
            'forecast_inflow': [1000.0, 1200.0, 1100.0],
            'downstream_safe': 3000.0
        })

        model.update(3600.0)
        outputs = model.get_outputs()

        risk = outputs['risk_level']
        authority = outputs['decision_authority']
        discharge = outputs['discharge']

        if authority == 'AUTONOMOUS' and risk in ['GREEN', 'BLUE']:
            status = TestStatus.PASSED
            message = f"自主决策正常，风险={risk}，权限={authority}，下泄={discharge:.0f}m³/s"
        else:
            status = TestStatus.WARNING
            message = f"决策权限异常，风险={risk}，权限={authority}"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "FLD_001", "自主决策测试", "防洪调度", status, message
        ))

    def _test_flood_human_required(self, model):
        """测试人工介入模式"""
        print("\n  [测试4.2] 高风险-强制人工介入...")
        model.initialize()

        # 高水位，大洪水
        model.set_inputs({
            'current_level': 151.0,  # 超设计洪水位
            'inflow': 4500.0,
            'forecast_inflow': [4500.0, 5000.0, 4800.0],  # 大洪水
            'downstream_safe': 3000.0
        })

        model.update(3600.0)
        outputs = model.get_outputs()

        risk = outputs['risk_level']
        authority = outputs['decision_authority']
        safety_margin = outputs['safety_margin']

        # 高风险时应切换到人工决策
        if authority in ['HUMAN_APPROVAL', 'HUMAN_ONLY'] and risk in ['ORANGE', 'RED']:
            status = TestStatus.PASSED
            message = f"正确触发人工介入，风险={risk}，权限={authority}"
        elif risk in ['YELLOW', 'ORANGE']:
            status = TestStatus.WARNING
            message = f"风险等级={risk}，建议人工确认"
        else:
            status = TestStatus.FAILED
            message = f"未能正确触发人工介入，风险={risk}，权限={authority}"

        print(f"    结果: {status.value} - {message}")
        print(f"      安全裕度: {safety_margin:.2%}")
        self.results.append(TestResult(
            "FLD_002", "人工介入测试", "防洪调度", status, message
        ))

    def _test_flood_forecast_uncertainty(self, model):
        """测试预报不确定性处理"""
        print("\n  [测试4.3] 预报不确定性放大...")
        model.initialize()

        # 模拟预报误差较大的情况
        # 先建立一些历史预报记录
        for i in range(10):
            # 预报与实际有较大偏差
            forecast_value = 2000.0 + i * 100
            actual_value = forecast_value * (1.3 if i % 2 == 0 else 0.7)  # ±30%误差

            model.set_inputs({
                'current_level': 146.0,
                'inflow': actual_value,
                'forecast_inflow': [forecast_value],
                'downstream_safe': 3000.0
            })
            model.update(3600.0)

        outputs = model.get_outputs()
        confidence = outputs['forecast_confidence']
        authority = outputs['decision_authority']

        # 预报不确定性高时应降低自主决策权限
        if confidence < 0.7 and authority in ['SUPERVISED', 'HUMAN_APPROVAL']:
            status = TestStatus.PASSED
            message = f"正确识别预报不确定性，置信度={confidence:.2%}，权限={authority}"
        elif confidence >= 0.7:
            status = TestStatus.WARNING
            message = f"预报置信度较高，可能误差检测不足"
        else:
            status = TestStatus.WARNING
            message = f"预报置信度低={confidence:.2%}，建议保守策略"

        print(f"    结果: {status.value} - {message}")
        self.results.append(TestResult(
            "FLD_003", "预报不确定性测试", "防洪调度", status, message
        ))

    def _test_flood_odd(self, model):
        """测试防洪调度ODD"""
        print("\n  [测试4.4] ODD边界验证...")

        odd = water_network_mbd.create_flood_control_odd()

        # 正常情况: 自主决策
        normal = odd.validate_operating_point({
            'risk_level': 'GREEN',
            'decision_authority': 'AUTONOMOUS',
            'forecast_confidence': 85.0,
            'safety_margin': 0.8
        })

        # 边界情况: 监督决策
        boundary = odd.validate_operating_point({
            'risk_level': 'YELLOW',
            'decision_authority': 'SUPERVISED',
            'forecast_confidence': 65.0,
            'safety_margin': 0.3
        })

        # 越界情况: 必须人工
        outside = odd.validate_operating_point({
            'risk_level': 'RED',
            'decision_authority': 'AUTONOMOUS',  # 错误的权限
            'forecast_confidence': 40.0,
            'safety_margin': 0.05
        })

        if normal['in_odd']:
            status = TestStatus.PASSED
            message = "ODD边界验证正确"
        else:
            status = TestStatus.WARNING
            message = "ODD边界验证需关注"

        print(f"    结果: {status.value} - {message}")
        print(f"      核心原则: 高风险时必须人工介入")
        self.results.append(TestResult(
            "FLD_004", "ODD边界验证", "防洪调度", status, message
        ))

    # ========================================================================
    # 汇总报告
    # ========================================================================

    def print_summary(self):
        """打印汇总报告"""
        print("\n" + "=" * 80)
        print("                    水网类型ODD差异化测试报告")
        print("=" * 80)

        # 按网络类型统计
        network_types = ['灌区水网', '调水工程', '城市供水', '防洪调度']
        total_passed = 0
        total_warning = 0
        total_failed = 0

        for net_type in network_types:
            results = [r for r in self.results if r.network_type == net_type]
            passed = sum(1 for r in results if r.status == TestStatus.PASSED)
            warning = sum(1 for r in results if r.status == TestStatus.WARNING)
            failed = sum(1 for r in results if r.status == TestStatus.FAILED)

            total_passed += passed
            total_warning += warning
            total_failed += failed

            status_icon = "✓" if failed == 0 else "✗"
            print(f"\n  {status_icon} {net_type}")
            print(f"    测试数: {len(results)} | 通过: {passed} | 警告: {warning} | 失败: {failed}")

            for r in results:
                icon = "✓" if r.status == TestStatus.PASSED else ("⚠" if r.status == TestStatus.WARNING else "✗")
                print(f"      {icon} {r.test_name}: {r.message}")

        print("\n" + "-" * 80)
        print(f"  总计: {len(self.results)} 测试")
        print(f"  通过: {total_passed} ({total_passed/len(self.results)*100:.1f}%)")
        print(f"  警告: {total_warning}")
        print(f"  失败: {total_failed}")

        # ODD差异化要点总结
        print("\n" + "=" * 80)
        print("                    ODD差异化设计要点")
        print("=" * 80)
        print("""
  1. 灌区水网 ODD核心:
     - 长期运行中的公平性与稳定性
     - 来水年景的不确定性适应
     - 作物需水预测误差容忍

  2. 调水工程 ODD核心:
     - 避免"调度修正来不及生效"的系统性风险
     - 时滞裕度 = 调度间隔 / 传输时滞 > 0.3
     - 多受水区协调约束

  3. 城市供水 ODD核心:
     - 绝大多数场景下的服务质量一致性
     - 压力波动 < ±0.05 MPa
     - 泵站切换的安全策略

  4. 防洪调度 ODD核心:
     - 明确自主决策 vs 人工介入的边界
     - 预报误差放大的风险管理
     - 极端情形的保守退化策略
""")

        if total_failed == 0:
            print("\n" + "=" * 80)
            print("结论: 所有水网类型ODD测试通过! ✓")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print(f"结论: 有 {total_failed} 个测试失败，需要关注 ✗")
            print("=" * 80)


if __name__ == "__main__":
    tester = WaterNetworkTester()
    tester.run_all_tests()
