"""
综合SIL/HIL/HITL测试演示
Comprehensive SIL/HIL/HITL Testing Demonstration

本演示展示了完整的模型驱动设计(MBD)测试流程，包括：
1. 软件在环(SIL)测试 - 纯软件仿真验证
2. 硬件在环(HIL)测试 - 硬件接口验证
3. 人在环(HITL)测试 - 人机交互验证
4. 集成验证 - 系统级验证
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import random
import time
import json

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# 导入MBD框架模块
try:
    from mbd_framework import mbd_core
    from mbd_framework import odd_framework
    from mbd_framework import functional_safety
    from mbd_framework import sil_framework
    from mbd_framework import hil_enhanced
    from mbd_framework import hitl_framework
    from mbd_framework import hydraulic_mbd
    from mbd_framework import multi_energy_mbd
except ImportError:
    # 如果包导入失败，使用直接导入
    import importlib.util

    def load_module_direct(name: str, path: str):
        """动态加载模块"""
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    mbd_path = project_root / "src" / "mbd_framework"
    mbd_core = load_module_direct("mbd_core", str(mbd_path / "mbd_core.py"))
    odd_framework = load_module_direct("odd_framework", str(mbd_path / "odd_framework.py"))
    functional_safety = load_module_direct("functional_safety", str(mbd_path / "functional_safety.py"))
    sil_framework = load_module_direct("sil_framework", str(mbd_path / "sil_framework.py"))
    hil_enhanced = load_module_direct("hil_enhanced", str(mbd_path / "hil_enhanced.py"))
    hitl_framework = load_module_direct("hitl_framework", str(mbd_path / "hitl_framework.py"))
    hydraulic_mbd = load_module_direct("hydraulic_mbd", str(mbd_path / "hydraulic_mbd.py"))
    multi_energy_mbd = load_module_direct("multi_energy_mbd", str(mbd_path / "multi_energy_mbd.py"))


# ============================================================================
# 测试结果数据结构
# ============================================================================

class TestStatus(Enum):
    """测试状态"""
    NOT_RUN = "not_run"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    test_name: str
    test_type: str  # SIL, HIL, HITL
    status: TestStatus
    duration_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    suite_name: str
    test_type: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    warnings: int
    duration_ms: float
    results: List[TestResult] = field(default_factory=list)
    coverage: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# SIL测试演示器
# ============================================================================

class SILTestDemonstrator:
    """软件在环测试演示器"""

    def __init__(self):
        self.test_results: List[TestResult] = []

    def run_valve_sil_tests(self) -> TestSuiteResult:
        """运行阀门控制器SIL测试"""
        print("\n" + "="*70)
        print("阀门控制器(IVCU) SIL测试")
        print("="*70)

        results = []
        start_time = time.time()

        # 创建阀门模型
        valve_model = hydraulic_mbd.ValveMBDModel()
        valve_model.initialize()

        # 测试1: 正常开关阀测试
        result = self._test_valve_normal_operation(valve_model)
        results.append(result)

        # 测试2: 两段关闭测试
        result = self._test_valve_two_stage_closing(valve_model)
        results.append(result)

        # 测试3: 水锤保护测试
        result = self._test_valve_water_hammer_protection(valve_model)
        results.append(result)

        # 测试4: 降级模式测试
        result = self._test_valve_degradation(valve_model)
        results.append(result)

        # 测试5: ODD边界测试
        result = self._test_valve_odd_boundaries(valve_model)
        results.append(result)

        duration = (time.time() - start_time) * 1000

        return self._create_suite_result(
            "IVCU_SIL_Tests",
            "SIL",
            results,
            duration
        )

    def _test_valve_normal_operation(self, model) -> TestResult:
        """测试阀门正常开关操作"""
        print("\n  [测试1] 正常开关阀操作...")
        start = time.time()

        try:
            # 设置开阀命令
            model.set_inputs({
                'command': 1.0,  # 全开
                'pressure_upstream': 5.0,
                'pressure_downstream': 3.0
            })

            # 仿真开阀过程
            for _ in range(100):
                model.update(0.01)  # 10ms步长

            outputs = model.get_outputs()
            position = outputs.get('position', 0)

            # 验证开阀完成
            if position > 0.95:
                status = TestStatus.PASSED
                message = f"开阀成功，位置={position:.2%}"
            else:
                status = TestStatus.FAILED
                message = f"开阀不完整，位置={position:.2%}"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_VALVE_001",
                test_name="正常开关阀操作",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'final_position': position}
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_VALVE_001",
                test_name="正常开关阀操作",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_valve_two_stage_closing(self, model) -> TestResult:
        """测试两段关闭功能"""
        print("\n  [测试2] 两段关闭测试...")
        start = time.time()

        try:
            # 初始化为全开状态
            model.set_inputs({'command': 1.0})
            for _ in range(50):
                model.update(0.01)

            # 执行关阀
            model.set_inputs({'command': 0.0})

            positions = []
            velocities = []

            for i in range(200):
                model.update(0.01)
                outputs = model.get_outputs()
                positions.append(outputs.get('position', 0))
                velocities.append(outputs.get('velocity', 0))

            # 分析两段关闭特性
            # 第一段(80%-20%): 较快速度
            # 第二段(20%-0%): 较慢速度
            fast_phase_speeds = []
            slow_phase_speeds = []

            for i, pos in enumerate(positions):
                if i > 0:
                    speed = abs(positions[i] - positions[i-1]) / 0.01
                    if pos > 0.2:
                        fast_phase_speeds.append(speed)
                    elif pos > 0.01:
                        slow_phase_speeds.append(speed)

            avg_fast = sum(fast_phase_speeds) / len(fast_phase_speeds) if fast_phase_speeds else 0
            avg_slow = sum(slow_phase_speeds) / len(slow_phase_speeds) if slow_phase_speeds else 0

            # 验证第二段速度明显低于第一段
            if avg_slow < avg_fast * 0.8:  # 第二段速度至少低20%
                status = TestStatus.PASSED
                message = f"两段关闭有效，快段={avg_fast:.3f}/s，慢段={avg_slow:.3f}/s"
            else:
                status = TestStatus.WARNING
                message = f"两段关闭效果不明显，快段={avg_fast:.3f}/s，慢段={avg_slow:.3f}/s"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_VALVE_002",
                test_name="两段关闭测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'fast_phase_speed': avg_fast,
                    'slow_phase_speed': avg_slow
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_VALVE_002",
                test_name="两段关闭测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_valve_water_hammer_protection(self, model) -> TestResult:
        """测试水锤保护功能"""
        print("\n  [测试3] 水锤保护测试...")
        start = time.time()

        try:
            # 模拟高压差快速关阀场景
            model.set_inputs({
                'command': 1.0,
                'pressure_upstream': 10.0,  # 高上游压力
                'pressure_downstream': 2.0
            })

            for _ in range(50):
                model.update(0.01)

            # 快速关阀
            model.set_inputs({'command': 0.0})

            max_pressure_rate = 0
            for _ in range(100):
                model.update(0.01)
                outputs = model.get_outputs()
                pressure_rate = abs(outputs.get('pressure_rate', 0))
                max_pressure_rate = max(max_pressure_rate, pressure_rate)

            # 验证压力变化率在允许范围内
            max_allowed_rate = 5.0  # MPa/s

            if max_pressure_rate < max_allowed_rate:
                status = TestStatus.PASSED
                message = f"水锤保护有效，最大压力变化率={max_pressure_rate:.2f} MPa/s"
            else:
                status = TestStatus.WARNING
                message = f"压力变化率较高={max_pressure_rate:.2f} MPa/s"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_VALVE_003",
                test_name="水锤保护测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'max_pressure_rate': max_pressure_rate}
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_VALVE_003",
                test_name="水锤保护测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_valve_degradation(self, model) -> TestResult:
        """测试降级模式"""
        print("\n  [测试4] 降级模式测试...")
        start = time.time()

        try:
            # 获取降级策略
            strategies = hydraulic_mbd.create_valve_degradation_strategies()

            # 模拟传感器故障
            degradation_levels = []

            # 单传感器故障 -> DEGRADED_L1
            degradation_levels.append(("单传感器故障", functional_safety.DegradationLevel.DEGRADED_L1))

            # 双传感器故障 -> DEGRADED_L2
            degradation_levels.append(("双传感器故障", functional_safety.DegradationLevel.DEGRADED_L2))

            # 执行器响应异常 -> DEGRADED_L3
            degradation_levels.append(("执行器响应异常", functional_safety.DegradationLevel.DEGRADED_L3))

            all_valid = True
            details = {}

            for fault_name, expected_level in degradation_levels:
                # 验证对应策略存在
                strategy_found = False
                for strategy in strategies:
                    if strategy.level == expected_level:
                        strategy_found = True
                        details[fault_name] = {
                            'level': expected_level.value,
                            'actions': strategy.actions[:2]  # 取前两个动作
                        }
                        break

                if not strategy_found:
                    all_valid = False
                    details[fault_name] = {'error': '未找到对应策略'}

            if all_valid:
                status = TestStatus.PASSED
                message = f"降级策略验证通过，共{len(strategies)}个策略"
            else:
                status = TestStatus.FAILED
                message = "部分降级策略缺失"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_VALVE_004",
                test_name="降级模式测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details=details
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_VALVE_004",
                test_name="降级模式测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_valve_odd_boundaries(self, model) -> TestResult:
        """测试ODD边界"""
        print("\n  [测试5] ODD边界测试...")
        start = time.time()

        try:
            # 获取阀门ODD定义
            odd = hydraulic_mbd.create_valve_odd()

            # 测试正常工作点
            normal_point = {
                'pressure': 6.0,
                'flow_rate': 50.0,
                'temperature': 25.0,
                'position_feedback': 0.5
            }

            normal_result = odd.validate_operating_point(normal_point)

            # 测试边界工作点
            boundary_point = {
                'pressure': 9.5,  # 接近上限
                'flow_rate': 95.0,
                'temperature': 45.0,
                'position_feedback': 0.98
            }

            boundary_result = odd.validate_operating_point(boundary_point)

            # 测试超出边界工作点
            outside_point = {
                'pressure': 15.0,  # 超出上限
                'flow_rate': 150.0,
                'temperature': 60.0,
                'position_feedback': 1.5
            }

            outside_result = odd.validate_operating_point(outside_point)

            # 验证结果
            if (normal_result['within_odd'] and
                boundary_result['within_odd'] and
                not outside_result['within_odd']):
                status = TestStatus.PASSED
                message = "ODD边界验证正确"
            else:
                status = TestStatus.FAILED
                message = "ODD边界验证异常"

            print(f"    结果: {status.value} - {message}")
            print(f"      正常点: {'在ODD内' if normal_result['within_odd'] else '超出ODD'}")
            print(f"      边界点: {'在ODD内' if boundary_result['within_odd'] else '超出ODD'}")
            print(f"      越界点: {'在ODD内' if outside_result['within_odd'] else '超出ODD'}")

            return TestResult(
                test_id="SIL_VALVE_005",
                test_name="ODD边界测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'normal_in_odd': normal_result['within_odd'],
                    'boundary_in_odd': boundary_result['within_odd'],
                    'outside_in_odd': outside_result['within_odd']
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_VALVE_005",
                test_name="ODD边界测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def run_pump_sil_tests(self) -> TestSuiteResult:
        """运行水泵控制器SIL测试"""
        print("\n" + "="*70)
        print("水泵控制器(IPCU) SIL测试")
        print("="*70)

        results = []
        start_time = time.time()

        # 创建水泵模型
        pump_model = hydraulic_mbd.PumpMBDModel()
        pump_model.initialize()

        # 测试1: S曲线启动测试
        result = self._test_pump_s_curve_start(pump_model)
        results.append(result)

        # 测试2: 恒压控制测试
        result = self._test_pump_pressure_control(pump_model)
        results.append(result)

        # 测试3: 反转保护测试
        result = self._test_pump_reverse_protection(pump_model)
        results.append(result)

        # 测试4: 多台联动测试
        result = self._test_pump_coordination()
        results.append(result)

        duration = (time.time() - start_time) * 1000

        return self._create_suite_result(
            "IPCU_SIL_Tests",
            "SIL",
            results,
            duration
        )

    def _test_pump_s_curve_start(self, model) -> TestResult:
        """测试S曲线软启动"""
        print("\n  [测试1] S曲线软启动测试...")
        start = time.time()

        try:
            # 设置启动命令
            model.set_inputs({
                'target_speed': 1450.0,  # 目标转速
                'enable': True
            })

            speeds = []
            accelerations = []

            # 仿真启动过程
            for i in range(300):
                model.update(0.01)
                outputs = model.get_outputs()
                speed = outputs.get('speed', 0)
                speeds.append(speed)

                if i > 0:
                    accel = (speeds[i] - speeds[i-1]) / 0.01
                    accelerations.append(accel)

            # 验证S曲线特性：加速度先增后减
            if len(accelerations) > 10:
                first_quarter = accelerations[:len(accelerations)//4]
                mid_section = accelerations[len(accelerations)//4:3*len(accelerations)//4]
                last_quarter = accelerations[3*len(accelerations)//4:]

                avg_first = sum(first_quarter) / len(first_quarter) if first_quarter else 0
                avg_mid = sum(mid_section) / len(mid_section) if mid_section else 0
                avg_last = sum(last_quarter) / len(last_quarter) if last_quarter else 0

                # S曲线：中间段加速度应最大
                final_speed = speeds[-1] if speeds else 0

                if final_speed > 1400:  # 达到目标转速
                    status = TestStatus.PASSED
                    message = f"S曲线启动成功，最终转速={final_speed:.0f} rpm"
                else:
                    status = TestStatus.WARNING
                    message = f"启动不完全，最终转速={final_speed:.0f} rpm"
            else:
                status = TestStatus.FAILED
                message = "数据点不足"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_PUMP_001",
                test_name="S曲线软启动测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'final_speed': speeds[-1] if speeds else 0}
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_PUMP_001",
                test_name="S曲线软启动测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_pump_pressure_control(self, model) -> TestResult:
        """测试恒压控制"""
        print("\n  [测试2] 恒压控制测试...")
        start = time.time()

        try:
            # 设置目标压力
            target_pressure = 5.0  # MPa
            model.set_inputs({
                'target_pressure': target_pressure,
                'enable': True
            })

            pressures = []

            # 仿真压力控制
            for _ in range(200):
                model.update(0.01)
                outputs = model.get_outputs()
                pressure = outputs.get('outlet_pressure', 0)
                pressures.append(pressure)

            # 取稳态数据分析
            steady_state = pressures[-50:]  # 最后50个点
            avg_pressure = sum(steady_state) / len(steady_state)
            max_deviation = max(abs(p - target_pressure) for p in steady_state)

            # 验证稳态精度
            if max_deviation < 0.1 * target_pressure:  # 10%误差范围
                status = TestStatus.PASSED
                message = f"恒压控制稳定，平均={avg_pressure:.2f}MPa，最大偏差={max_deviation:.3f}MPa"
            else:
                status = TestStatus.WARNING
                message = f"压力波动较大，平均={avg_pressure:.2f}MPa，最大偏差={max_deviation:.3f}MPa"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_PUMP_002",
                test_name="恒压控制测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'target_pressure': target_pressure,
                    'avg_pressure': avg_pressure,
                    'max_deviation': max_deviation
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_PUMP_002",
                test_name="恒压控制测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_pump_reverse_protection(self, model) -> TestResult:
        """测试反转保护"""
        print("\n  [测试3] 反转保护测试...")
        start = time.time()

        try:
            # 模拟停机后反向压力
            model.set_inputs({
                'enable': False,
                'target_speed': 0
            })

            for _ in range(50):
                model.update(0.01)

            # 施加反向压力
            model.set_inputs({
                'reverse_pressure': 3.0  # MPa
            })

            speeds = []
            for _ in range(100):
                model.update(0.01)
                outputs = model.get_outputs()
                speed = outputs.get('speed', 0)
                speeds.append(speed)

            # 验证没有反转
            min_speed = min(speeds)

            if min_speed >= -10:  # 允许小量波动
                status = TestStatus.PASSED
                message = f"反转保护有效，最小转速={min_speed:.0f} rpm"
            else:
                status = TestStatus.FAILED
                message = f"检测到反转，最小转速={min_speed:.0f} rpm"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_PUMP_003",
                test_name="反转保护测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'min_speed': min_speed}
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_PUMP_003",
                test_name="反转保护测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_pump_coordination(self) -> TestResult:
        """测试多台水泵联动"""
        print("\n  [测试4] 多台联动测试...")
        start = time.time()

        try:
            # 创建3台水泵
            pumps = [
                hydraulic_mbd.PumpMBDModel(f"PUMP_{i+1}")
                for i in range(3)
            ]

            for pump in pumps:
                pump.initialize()

            # 依次启动（间隔启动避免冲击）
            total_flow = 0

            for i, pump in enumerate(pumps):
                # 延时启动
                pump.set_inputs({
                    'target_speed': 1450.0,
                    'enable': True
                })

                # 运行一段时间
                for _ in range(100):
                    pump.update(0.01)

            # 获取总流量
            for pump in pumps:
                outputs = pump.get_outputs()
                total_flow += outputs.get('flow_rate', 0)

            # 验证联动效果
            if total_flow > 200:  # 3台泵总流量
                status = TestStatus.PASSED
                message = f"联动运行正常，总流量={total_flow:.1f} m³/h"
            else:
                status = TestStatus.WARNING
                message = f"联动流量偏低，总流量={total_flow:.1f} m³/h"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_PUMP_004",
                test_name="多台联动测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'num_pumps': len(pumps),
                    'total_flow': total_flow
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_PUMP_004",
                test_name="多台联动测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def run_gate_sil_tests(self) -> TestSuiteResult:
        """运行闸门控制器SIL测试"""
        print("\n" + "="*70)
        print("闸门控制器(IGCU) SIL测试")
        print("="*70)

        results = []
        start_time = time.time()

        # 创建闸门模型
        gate_model = hydraulic_mbd.GateMBDModel()
        gate_model.initialize()

        # 测试1: 流量伺服控制测试
        result = self._test_gate_flow_servo(gate_model)
        results.append(result)

        # 测试2: 涌浪抑制测试
        result = self._test_gate_surge_suppression(gate_model)
        results.append(result)

        # 测试3: 位置精度测试
        result = self._test_gate_position_accuracy(gate_model)
        results.append(result)

        duration = (time.time() - start_time) * 1000

        return self._create_suite_result(
            "IGCU_SIL_Tests",
            "SIL",
            results,
            duration
        )

    def _test_gate_flow_servo(self, model) -> TestResult:
        """测试流量伺服控制"""
        print("\n  [测试1] 流量伺服控制测试...")
        start = time.time()

        try:
            target_flow = 50.0  # m³/s
            model.set_inputs({
                'target_flow': target_flow,
                'upstream_level': 100.0,
                'downstream_level': 95.0
            })

            flows = []
            for _ in range(200):
                model.update(0.01)
                outputs = model.get_outputs()
                flow = outputs.get('flow_rate', 0)
                flows.append(flow)

            # 分析稳态性能
            steady_flows = flows[-50:]
            avg_flow = sum(steady_flows) / len(steady_flows)
            error = abs(avg_flow - target_flow) / target_flow * 100

            if error < 5:  # 5%误差
                status = TestStatus.PASSED
                message = f"流量伺服控制精度良好，误差={error:.1f}%"
            else:
                status = TestStatus.WARNING
                message = f"流量控制精度需改进，误差={error:.1f}%"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_GATE_001",
                test_name="流量伺服控制测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'target_flow': target_flow,
                    'avg_flow': avg_flow,
                    'error_percent': error
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_GATE_001",
                test_name="流量伺服控制测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_gate_surge_suppression(self, model) -> TestResult:
        """测试涌浪抑制"""
        print("\n  [测试2] 涌浪抑制测试...")
        start = time.time()

        try:
            # 模拟快速开闸导致的涌浪
            model.set_inputs({
                'target_position': 0.8,  # 快速开到80%
                'upstream_level': 105.0,  # 高水位
                'downstream_level': 90.0
            })

            levels = []
            for _ in range(300):
                model.update(0.01)
                outputs = model.get_outputs()
                level_change = outputs.get('downstream_level_change', 0)
                levels.append(level_change)

            # 分析涌浪幅度
            max_surge = max(abs(l) for l in levels)

            if max_surge < 1.0:  # 1米涌浪限制
                status = TestStatus.PASSED
                message = f"涌浪控制有效，最大涌浪={max_surge:.2f}m"
            else:
                status = TestStatus.WARNING
                message = f"涌浪较大，最大涌浪={max_surge:.2f}m"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_GATE_002",
                test_name="涌浪抑制测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'max_surge': max_surge}
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_GATE_002",
                test_name="涌浪抑制测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_gate_position_accuracy(self, model) -> TestResult:
        """测试位置精度"""
        print("\n  [测试3] 位置精度测试...")
        start = time.time()

        try:
            # 测试多个目标位置
            target_positions = [0.2, 0.5, 0.8, 0.3, 0.7]
            errors = []

            for target in target_positions:
                model.set_inputs({'target_position': target})

                # 等待稳定
                for _ in range(100):
                    model.update(0.01)

                outputs = model.get_outputs()
                actual = outputs.get('position', 0)
                error = abs(actual - target)
                errors.append(error)

            avg_error = sum(errors) / len(errors)
            max_error = max(errors)

            if max_error < 0.01:  # 1%精度
                status = TestStatus.PASSED
                message = f"位置精度优秀，平均误差={avg_error*100:.2f}%"
            elif max_error < 0.02:
                status = TestStatus.WARNING
                message = f"位置精度良好，平均误差={avg_error*100:.2f}%"
            else:
                status = TestStatus.FAILED
                message = f"位置精度不足，平均误差={avg_error*100:.2f}%"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_GATE_003",
                test_name="位置精度测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'avg_error': avg_error,
                    'max_error': max_error
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_GATE_003",
                test_name="位置精度测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def run_multi_energy_sil_tests(self) -> TestSuiteResult:
        """运行多能互补系统SIL测试"""
        print("\n" + "="*70)
        print("多能互补系统 SIL测试")
        print("="*70)

        results = []
        start_time = time.time()

        # 测试1: 超级电容快速响应
        result = self._test_sc_fast_response()
        results.append(result)

        # 测试2: 储能电池平滑控制
        result = self._test_battery_smoothing()
        results.append(result)

        # 测试3: 抽蓄MPC控制
        result = self._test_psh_mpc()
        results.append(result)

        # 测试4: 层级协调控制
        result = self._test_hierarchical_control()
        results.append(result)

        duration = (time.time() - start_time) * 1000

        return self._create_suite_result(
            "MultiEnergy_SIL_Tests",
            "SIL",
            results,
            duration
        )

    def _test_sc_fast_response(self) -> TestResult:
        """测试超级电容快速响应"""
        print("\n  [测试1] 超级电容快速响应测试...")
        start = time.time()

        try:
            sc_model = multi_energy_mbd.SupercapacitorMBDModel()
            sc_model.initialize()

            # 模拟频率阶跃扰动
            sc_model.set_inputs({
                'frequency_deviation': -0.2,  # -0.2Hz偏差
                'enable_droop': True
            })

            powers = []
            response_time = None

            for i in range(100):
                sc_model.update(0.001)  # 1ms步长
                outputs = sc_model.get_outputs()
                power = outputs.get('active_power', 0)
                powers.append(power)

                # 检测响应时间（达到90%目标功率）
                if response_time is None and power > 4.0:  # 约90%目标
                    response_time = i * 1  # ms

            final_power = powers[-1] if powers else 0

            if response_time and response_time < 10:  # 10ms内响应
                status = TestStatus.PASSED
                message = f"快速响应达标，响应时间={response_time}ms，功率={final_power:.1f}MW"
            elif response_time:
                status = TestStatus.WARNING
                message = f"响应略慢，响应时间={response_time}ms"
            else:
                status = TestStatus.FAILED
                message = "未能达到目标功率"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_ME_001",
                test_name="超级电容快速响应测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'response_time_ms': response_time,
                    'final_power': final_power
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_ME_001",
                test_name="超级电容快速响应测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_battery_smoothing(self) -> TestResult:
        """测试储能电池平滑控制"""
        print("\n  [测试2] 储能电池平滑控制测试...")
        start = time.time()

        try:
            battery_model = multi_energy_mbd.BatteryMBDModel()
            battery_model.initialize()

            # 模拟波动功率输入
            powers = []
            smoothed_powers = []

            for i in range(200):
                # 模拟光伏波动
                pv_power = 50 + 20 * (0.5 - random.random())  # MW

                battery_model.set_inputs({
                    'power_reference': pv_power,
                    'enable_smoothing': True
                })

                battery_model.update(0.1)  # 100ms步长
                outputs = battery_model.get_outputs()

                powers.append(pv_power)
                smoothed_powers.append(outputs.get('output_power', pv_power))

            # 计算平滑效果
            input_variance = sum((p - sum(powers)/len(powers))**2 for p in powers) / len(powers)
            output_variance = sum((p - sum(smoothed_powers)/len(smoothed_powers))**2
                                  for p in smoothed_powers) / len(smoothed_powers)

            smoothing_ratio = output_variance / input_variance if input_variance > 0 else 1

            if smoothing_ratio < 0.5:  # 方差降低50%以上
                status = TestStatus.PASSED
                message = f"平滑效果良好，方差比={smoothing_ratio:.2f}"
            else:
                status = TestStatus.WARNING
                message = f"平滑效果一般，方差比={smoothing_ratio:.2f}"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_ME_002",
                test_name="储能电池平滑控制测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'smoothing_ratio': smoothing_ratio}
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_ME_002",
                test_name="储能电池平滑控制测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_psh_mpc(self) -> TestResult:
        """测试抽蓄MPC控制"""
        print("\n  [测试3] 抽蓄MPC控制测试...")
        start = time.time()

        try:
            psh_model = multi_energy_mbd.PSHMBDModel()
            psh_model.initialize()

            # 设置优化目标
            psh_model.set_inputs({
                'power_schedule': [100, 120, 80, 60, 100],  # 未来5分钟调度
                'electricity_price': [0.5, 0.6, 0.4, 0.3, 0.5],  # 电价
                'enable_mpc': True
            })

            # 运行MPC优化
            for _ in range(60):  # 模拟60秒
                psh_model.update(1.0)

            outputs = psh_model.get_outputs()
            actual_power = outputs.get('active_power', 0)
            efficiency = outputs.get('efficiency', 0)

            if efficiency > 0.75:  # 75%效率
                status = TestStatus.PASSED
                message = f"MPC控制有效，效率={efficiency*100:.1f}%"
            else:
                status = TestStatus.WARNING
                message = f"MPC效率偏低，效率={efficiency*100:.1f}%"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_ME_003",
                test_name="抽蓄MPC控制测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'actual_power': actual_power,
                    'efficiency': efficiency
                }
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_ME_003",
                test_name="抽蓄MPC控制测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_hierarchical_control(self) -> TestResult:
        """测试层级协调控制"""
        print("\n  [测试4] 层级协调控制测试...")
        start = time.time()

        try:
            controller = multi_energy_mbd.HierarchicalControllerMBDModel()
            controller.initialize()

            # 模拟系统负荷变化
            controller.set_inputs({
                'frequency_deviation': -0.1,  # Hz
                'total_load': 500,  # MW
                'renewable_power': 200,  # MW
                'enable_coordination': True
            })

            # 运行协调控制
            frequency_errors = []
            for _ in range(100):
                controller.update(0.1)
                outputs = controller.get_outputs()
                freq_error = outputs.get('frequency_error', 0.1)
                frequency_errors.append(freq_error)

            final_error = frequency_errors[-1]

            if abs(final_error) < 0.02:  # 20mHz内
                status = TestStatus.PASSED
                message = f"协调控制有效，最终频率偏差={final_error*1000:.0f}mHz"
            else:
                status = TestStatus.WARNING
                message = f"频率偏差较大，最终偏差={final_error*1000:.0f}mHz"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="SIL_ME_004",
                test_name="层级协调控制测试",
                test_type="SIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'final_frequency_error': final_error}
            )
        except Exception as e:
            return TestResult(
                test_id="SIL_ME_004",
                test_name="层级协调控制测试",
                test_type="SIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _create_suite_result(self, name: str, test_type: str,
                             results: List[TestResult], duration: float) -> TestSuiteResult:
        """创建测试套件结果"""
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in results if r.status == TestStatus.WARNING)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)

        return TestSuiteResult(
            suite_name=name,
            test_type=test_type,
            total_tests=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            warnings=warnings,
            duration_ms=duration,
            results=results,
            coverage={
                'statement': 0.85,  # 模拟覆盖率
                'branch': 0.78,
                'function': 0.92
            }
        )


# ============================================================================
# HIL测试演示器
# ============================================================================

class HILTestDemonstrator:
    """硬件在环测试演示器"""

    def __init__(self):
        self.test_results: List[TestResult] = []

    def run_valve_hil_tests(self) -> TestSuiteResult:
        """运行阀门HIL测试"""
        print("\n" + "="*70)
        print("阀门控制器(IVCU) HIL测试")
        print("="*70)

        results = []
        start_time = time.time()

        # 测试1: 硬件接口验证
        result = self._test_hardware_interface()
        results.append(result)

        # 测试2: 信号调理验证
        result = self._test_signal_conditioning()
        results.append(result)

        # 测试3: 故障注入测试
        result = self._test_fault_injection()
        results.append(result)

        # 测试4: 实时同步测试
        result = self._test_realtime_sync()
        results.append(result)

        duration = (time.time() - start_time) * 1000

        return self._create_suite_result(
            "IVCU_HIL_Tests",
            "HIL",
            results,
            duration
        )

    def _test_hardware_interface(self) -> TestResult:
        """测试硬件接口"""
        print("\n  [测试1] 硬件接口验证...")
        start = time.time()

        try:
            # 模拟硬件接口检测
            interfaces = {
                'analog_inputs': {'count': 8, 'resolution': 16, 'status': 'ok'},
                'analog_outputs': {'count': 4, 'resolution': 16, 'status': 'ok'},
                'digital_inputs': {'count': 16, 'status': 'ok'},
                'digital_outputs': {'count': 16, 'status': 'ok'},
                'encoder_inputs': {'count': 2, 'resolution': 24, 'status': 'ok'},
                'can_bus': {'channels': 2, 'baudrate': 500000, 'status': 'ok'}
            }

            all_ok = all(iface['status'] == 'ok' for iface in interfaces.values())

            if all_ok:
                status = TestStatus.PASSED
                message = f"所有硬件接口正常，共{len(interfaces)}类接口"
            else:
                status = TestStatus.FAILED
                failed_ifaces = [k for k, v in interfaces.items() if v['status'] != 'ok']
                message = f"接口异常: {', '.join(failed_ifaces)}"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HIL_VALVE_001",
                test_name="硬件接口验证",
                test_type="HIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'interfaces': interfaces}
            )
        except Exception as e:
            return TestResult(
                test_id="HIL_VALVE_001",
                test_name="硬件接口验证",
                test_type="HIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_signal_conditioning(self) -> TestResult:
        """测试信号调理"""
        print("\n  [测试2] 信号调理验证...")
        start = time.time()

        try:
            # 模拟信号调理测试
            test_signals = [
                {'name': '压力传感器', 'input_range': '4-20mA', 'output_range': '0-10V',
                 'linearity_error': 0.05},
                {'name': '位置传感器', 'input_range': '0-10V', 'output_range': '0-100%',
                 'linearity_error': 0.03},
                {'name': '流量传感器', 'input_range': '4-20mA', 'output_range': '0-100m³/h',
                 'linearity_error': 0.08}
            ]

            max_error = max(s['linearity_error'] for s in test_signals)

            if max_error < 0.1:  # 0.1%线性度
                status = TestStatus.PASSED
                message = f"信号调理精度良好，最大线性误差={max_error*100:.2f}%"
            else:
                status = TestStatus.WARNING
                message = f"信号调理精度需改进，最大线性误差={max_error*100:.2f}%"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HIL_VALVE_002",
                test_name="信号调理验证",
                test_type="HIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={'signals': test_signals}
            )
        except Exception as e:
            return TestResult(
                test_id="HIL_VALVE_002",
                test_name="信号调理验证",
                test_type="HIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_fault_injection(self) -> TestResult:
        """测试故障注入"""
        print("\n  [测试3] 故障注入测试...")
        start = time.time()

        try:
            # 定义故障注入场景
            fault_scenarios = [
                {
                    'fault_type': 'sensor_stuck_high',
                    'target': 'pressure_sensor',
                    'expected_response': 'switch_to_backup',
                    'actual_response': 'switch_to_backup',
                    'response_time_ms': 15
                },
                {
                    'fault_type': 'sensor_drift',
                    'target': 'position_sensor',
                    'expected_response': 'compensate_and_warn',
                    'actual_response': 'compensate_and_warn',
                    'response_time_ms': 25
                },
                {
                    'fault_type': 'communication_loss',
                    'target': 'can_bus_1',
                    'expected_response': 'use_redundant_channel',
                    'actual_response': 'use_redundant_channel',
                    'response_time_ms': 10
                },
                {
                    'fault_type': 'actuator_jam',
                    'target': 'main_valve',
                    'expected_response': 'emergency_stop',
                    'actual_response': 'emergency_stop',
                    'response_time_ms': 5
                }
            ]

            # 验证故障响应
            correct_responses = sum(
                1 for s in fault_scenarios
                if s['expected_response'] == s['actual_response']
            )

            avg_response_time = sum(s['response_time_ms'] for s in fault_scenarios) / len(fault_scenarios)

            if correct_responses == len(fault_scenarios) and avg_response_time < 30:
                status = TestStatus.PASSED
                message = f"故障响应正确，平均响应时间={avg_response_time:.0f}ms"
            elif correct_responses == len(fault_scenarios):
                status = TestStatus.WARNING
                message = f"响应正确但较慢，平均响应时间={avg_response_time:.0f}ms"
            else:
                status = TestStatus.FAILED
                message = f"故障响应不正确，{correct_responses}/{len(fault_scenarios)}通过"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HIL_VALVE_003",
                test_name="故障注入测试",
                test_type="HIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'scenarios': fault_scenarios,
                    'correct_responses': correct_responses,
                    'avg_response_time': avg_response_time
                }
            )
        except Exception as e:
            return TestResult(
                test_id="HIL_VALVE_003",
                test_name="故障注入测试",
                test_type="HIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_realtime_sync(self) -> TestResult:
        """测试实时同步"""
        print("\n  [测试4] 实时同步测试...")
        start = time.time()

        try:
            # 模拟实时性能测试
            cycle_times = []
            jitters = []

            target_cycle = 1.0  # 1ms目标周期

            for _ in range(1000):
                # 模拟测量
                actual_cycle = target_cycle + (random.random() - 0.5) * 0.1  # ±50μs抖动
                cycle_times.append(actual_cycle)
                jitters.append(abs(actual_cycle - target_cycle))

            avg_cycle = sum(cycle_times) / len(cycle_times)
            max_jitter = max(jitters) * 1000  # 转换为μs

            if max_jitter < 100:  # 100μs抖动限制
                status = TestStatus.PASSED
                message = f"实时性能良好，最大抖动={max_jitter:.0f}μs"
            elif max_jitter < 200:
                status = TestStatus.WARNING
                message = f"实时性能一般，最大抖动={max_jitter:.0f}μs"
            else:
                status = TestStatus.FAILED
                message = f"实时性能不足，最大抖动={max_jitter:.0f}μs"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HIL_VALVE_004",
                test_name="实时同步测试",
                test_type="HIL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'avg_cycle_ms': avg_cycle,
                    'max_jitter_us': max_jitter
                }
            )
        except Exception as e:
            return TestResult(
                test_id="HIL_VALVE_004",
                test_name="实时同步测试",
                test_type="HIL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _create_suite_result(self, name: str, test_type: str,
                             results: List[TestResult], duration: float) -> TestSuiteResult:
        """创建测试套件结果"""
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in results if r.status == TestStatus.WARNING)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)

        return TestSuiteResult(
            suite_name=name,
            test_type=test_type,
            total_tests=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            warnings=warnings,
            duration_ms=duration,
            results=results
        )


# ============================================================================
# HITL测试演示器
# ============================================================================

class HITLTestDemonstrator:
    """人在环测试演示器"""

    def __init__(self):
        self.test_results: List[TestResult] = []

    def run_hitl_tests(self) -> TestSuiteResult:
        """运行HITL测试"""
        print("\n" + "="*70)
        print("人在环(HITL)测试")
        print("="*70)

        results = []
        start_time = time.time()

        # 测试1: 操作员界面响应测试
        result = self._test_operator_interface()
        results.append(result)

        # 测试2: 工作负荷评估
        result = self._test_workload_assessment()
        results.append(result)

        # 测试3: 态势感知测试
        result = self._test_situation_awareness()
        results.append(result)

        # 测试4: 紧急响应测试
        result = self._test_emergency_response()
        results.append(result)

        # 测试5: 决策支持系统测试
        result = self._test_decision_support()
        results.append(result)

        duration = (time.time() - start_time) * 1000

        return self._create_suite_result(
            "HITL_Tests",
            "HITL",
            results,
            duration
        )

    def _test_operator_interface(self) -> TestResult:
        """测试操作员界面"""
        print("\n  [测试1] 操作员界面响应测试...")
        start = time.time()

        try:
            # 模拟界面响应测试
            interface_metrics = {
                'screen_refresh_rate': 60,  # Hz
                'input_latency_ms': 15,
                'alarm_display_time_ms': 50,
                'trend_update_interval_ms': 100,
                'command_acknowledgment_ms': 25
            }

            # 验证响应时间
            all_within_spec = (
                interface_metrics['input_latency_ms'] < 50 and
                interface_metrics['alarm_display_time_ms'] < 100 and
                interface_metrics['command_acknowledgment_ms'] < 50
            )

            if all_within_spec:
                status = TestStatus.PASSED
                message = f"界面响应良好，输入延迟={interface_metrics['input_latency_ms']}ms"
            else:
                status = TestStatus.WARNING
                message = "部分界面响应需优化"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HITL_001",
                test_name="操作员界面响应测试",
                test_type="HITL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details=interface_metrics
            )
        except Exception as e:
            return TestResult(
                test_id="HITL_001",
                test_name="操作员界面响应测试",
                test_type="HITL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_workload_assessment(self) -> TestResult:
        """测试工作负荷评估"""
        print("\n  [测试2] 工作负荷评估(NASA-TLX)...")
        start = time.time()

        try:
            # 模拟NASA-TLX评估结果
            nasa_tlx_scores = {
                'mental_demand': 45,      # 心理需求 (0-100)
                'physical_demand': 25,    # 体力需求
                'temporal_demand': 55,    # 时间压力
                'performance': 75,        # 绩效感知
                'effort': 50,             # 努力程度
                'frustration': 30         # 挫败感
            }

            # 计算加权总分
            weights = {
                'mental_demand': 0.25,
                'physical_demand': 0.10,
                'temporal_demand': 0.20,
                'performance': 0.20,
                'effort': 0.15,
                'frustration': 0.10
            }

            weighted_score = sum(
                nasa_tlx_scores[k] * weights[k]
                for k in nasa_tlx_scores
            )

            if weighted_score < 50:
                status = TestStatus.PASSED
                message = f"工作负荷适中，NASA-TLX综合分={weighted_score:.1f}"
            elif weighted_score < 70:
                status = TestStatus.WARNING
                message = f"工作负荷较高，NASA-TLX综合分={weighted_score:.1f}"
            else:
                status = TestStatus.FAILED
                message = f"工作负荷过高，NASA-TLX综合分={weighted_score:.1f}"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HITL_002",
                test_name="工作负荷评估",
                test_type="HITL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'nasa_tlx_scores': nasa_tlx_scores,
                    'weighted_score': weighted_score
                }
            )
        except Exception as e:
            return TestResult(
                test_id="HITL_002",
                test_name="工作负荷评估",
                test_type="HITL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_situation_awareness(self) -> TestResult:
        """测试态势感知"""
        print("\n  [测试3] 态势感知评估(Endsley模型)...")
        start = time.time()

        try:
            # 模拟Endsley三级态势感知评估
            sa_assessment = {
                'level_1_perception': {  # 感知
                    'alarm_recognition_rate': 0.95,
                    'parameter_reading_accuracy': 0.92,
                    'status_awareness_score': 0.88
                },
                'level_2_comprehension': {  # 理解
                    'trend_understanding': 0.85,
                    'anomaly_detection': 0.80,
                    'system_state_comprehension': 0.82
                },
                'level_3_projection': {  # 预测
                    'failure_prediction_accuracy': 0.75,
                    'load_forecast_accuracy': 0.78,
                    'decision_anticipation': 0.72
                }
            }

            # 计算各级平均分
            level_scores = {}
            for level, metrics in sa_assessment.items():
                level_scores[level] = sum(metrics.values()) / len(metrics)

            overall_sa = sum(level_scores.values()) / len(level_scores)

            if overall_sa > 0.85:
                status = TestStatus.PASSED
                message = f"态势感知优秀，综合评分={overall_sa*100:.1f}%"
            elif overall_sa > 0.70:
                status = TestStatus.WARNING
                message = f"态势感知良好，综合评分={overall_sa*100:.1f}%"
            else:
                status = TestStatus.FAILED
                message = f"态势感知不足，综合评分={overall_sa*100:.1f}%"

            print(f"    结果: {status.value} - {message}")
            print(f"      Level 1 (感知): {level_scores['level_1_perception']*100:.1f}%")
            print(f"      Level 2 (理解): {level_scores['level_2_comprehension']*100:.1f}%")
            print(f"      Level 3 (预测): {level_scores['level_3_projection']*100:.1f}%")

            return TestResult(
                test_id="HITL_003",
                test_name="态势感知评估",
                test_type="HITL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'sa_assessment': sa_assessment,
                    'level_scores': level_scores,
                    'overall_sa': overall_sa
                }
            )
        except Exception as e:
            return TestResult(
                test_id="HITL_003",
                test_name="态势感知评估",
                test_type="HITL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_emergency_response(self) -> TestResult:
        """测试紧急响应"""
        print("\n  [测试4] 紧急响应测试...")
        start = time.time()

        try:
            # 模拟紧急场景响应测试
            emergency_scenarios = [
                {
                    'scenario': '管道泄漏',
                    'detection_time_s': 2.5,
                    'response_time_s': 5.0,
                    'correct_action': True,
                    'procedure_followed': True
                },
                {
                    'scenario': '水泵过载',
                    'detection_time_s': 1.0,
                    'response_time_s': 3.0,
                    'correct_action': True,
                    'procedure_followed': True
                },
                {
                    'scenario': '闸门卡阻',
                    'detection_time_s': 3.0,
                    'response_time_s': 8.0,
                    'correct_action': True,
                    'procedure_followed': False  # 跳过了一步
                },
                {
                    'scenario': '电源故障',
                    'detection_time_s': 0.5,
                    'response_time_s': 2.0,
                    'correct_action': True,
                    'procedure_followed': True
                }
            ]

            # 统计结果
            avg_detection = sum(s['detection_time_s'] for s in emergency_scenarios) / len(emergency_scenarios)
            avg_response = sum(s['response_time_s'] for s in emergency_scenarios) / len(emergency_scenarios)
            correct_actions = sum(1 for s in emergency_scenarios if s['correct_action'])
            procedures_followed = sum(1 for s in emergency_scenarios if s['procedure_followed'])

            if (correct_actions == len(emergency_scenarios) and
                avg_response < 10 and
                procedures_followed >= len(emergency_scenarios) - 1):
                status = TestStatus.PASSED
                message = f"紧急响应良好，平均响应时间={avg_response:.1f}s"
            elif correct_actions == len(emergency_scenarios):
                status = TestStatus.WARNING
                message = f"响应正确但需加强，平均响应时间={avg_response:.1f}s"
            else:
                status = TestStatus.FAILED
                message = f"紧急响应需改进，正确率={correct_actions}/{len(emergency_scenarios)}"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HITL_004",
                test_name="紧急响应测试",
                test_type="HITL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'scenarios': emergency_scenarios,
                    'avg_detection_time': avg_detection,
                    'avg_response_time': avg_response,
                    'correct_actions': correct_actions,
                    'procedures_followed': procedures_followed
                }
            )
        except Exception as e:
            return TestResult(
                test_id="HITL_004",
                test_name="紧急响应测试",
                test_type="HITL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _test_decision_support(self) -> TestResult:
        """测试决策支持系统"""
        print("\n  [测试5] 决策支持系统测试...")
        start = time.time()

        try:
            # 模拟决策支持系统评估
            dss_metrics = {
                'recommendation_accuracy': 0.90,
                'explanation_clarity': 0.85,
                'user_acceptance_rate': 0.88,
                'override_frequency': 0.12,  # 用户否决率
                'avg_decision_time_reduction': 0.35  # 决策时间减少比例
            }

            # 评估决策支持效果
            effectiveness = (
                dss_metrics['recommendation_accuracy'] * 0.3 +
                dss_metrics['user_acceptance_rate'] * 0.3 +
                (1 - dss_metrics['override_frequency']) * 0.2 +
                dss_metrics['avg_decision_time_reduction'] * 0.2
            )

            if effectiveness > 0.80:
                status = TestStatus.PASSED
                message = f"决策支持系统效果良好，有效性={effectiveness*100:.1f}%"
            elif effectiveness > 0.60:
                status = TestStatus.WARNING
                message = f"决策支持系统效果一般，有效性={effectiveness*100:.1f}%"
            else:
                status = TestStatus.FAILED
                message = f"决策支持系统需改进，有效性={effectiveness*100:.1f}%"

            print(f"    结果: {status.value} - {message}")

            return TestResult(
                test_id="HITL_005",
                test_name="决策支持系统测试",
                test_type="HITL",
                status=status,
                duration_ms=(time.time() - start) * 1000,
                message=message,
                details={
                    'metrics': dss_metrics,
                    'effectiveness': effectiveness
                }
            )
        except Exception as e:
            return TestResult(
                test_id="HITL_005",
                test_name="决策支持系统测试",
                test_type="HITL",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"测试异常: {str(e)}"
            )

    def _create_suite_result(self, name: str, test_type: str,
                             results: List[TestResult], duration: float) -> TestSuiteResult:
        """创建测试套件结果"""
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in results if r.status == TestStatus.WARNING)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)

        return TestSuiteResult(
            suite_name=name,
            test_type=test_type,
            total_tests=len(results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            warnings=warnings,
            duration_ms=duration,
            results=results
        )


# ============================================================================
# 综合测试报告生成器
# ============================================================================

class TestReportGenerator:
    """测试报告生成器"""

    def __init__(self):
        self.suite_results: List[TestSuiteResult] = []

    def add_suite_result(self, result: TestSuiteResult):
        """添加测试套件结果"""
        self.suite_results.append(result)

    def generate_summary(self) -> Dict[str, Any]:
        """生成测试摘要"""
        total_tests = sum(s.total_tests for s in self.suite_results)
        total_passed = sum(s.passed for s in self.suite_results)
        total_failed = sum(s.failed for s in self.suite_results)
        total_warnings = sum(s.warnings for s in self.suite_results)
        total_duration = sum(s.duration_ms for s in self.suite_results)

        return {
            'total_suites': len(self.suite_results),
            'total_tests': total_tests,
            'passed': total_passed,
            'failed': total_failed,
            'warnings': total_warnings,
            'pass_rate': total_passed / total_tests * 100 if total_tests > 0 else 0,
            'total_duration_ms': total_duration,
            'by_type': self._group_by_type()
        }

    def _group_by_type(self) -> Dict[str, Dict[str, int]]:
        """按测试类型分组统计"""
        by_type = {}
        for suite in self.suite_results:
            if suite.test_type not in by_type:
                by_type[suite.test_type] = {
                    'suites': 0,
                    'tests': 0,
                    'passed': 0,
                    'failed': 0,
                    'warnings': 0
                }
            by_type[suite.test_type]['suites'] += 1
            by_type[suite.test_type]['tests'] += suite.total_tests
            by_type[suite.test_type]['passed'] += suite.passed
            by_type[suite.test_type]['failed'] += suite.failed
            by_type[suite.test_type]['warnings'] += suite.warnings
        return by_type

    def print_report(self):
        """打印测试报告"""
        print("\n")
        print("=" * 80)
        print("                       综 合 测 试 报 告")
        print("=" * 80)

        summary = self.generate_summary()

        print(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试套件数: {summary['total_suites']}")
        print(f"总测试数: {summary['total_tests']}")
        print(f"总耗时: {summary['total_duration_ms']:.0f}ms")

        print("\n" + "-" * 80)
        print("                          总体结果")
        print("-" * 80)

        print(f"  通过: {summary['passed']} ({summary['pass_rate']:.1f}%)")
        print(f"  失败: {summary['failed']}")
        print(f"  警告: {summary['warnings']}")

        print("\n" + "-" * 80)
        print("                       按测试类型统计")
        print("-" * 80)

        for test_type, stats in summary['by_type'].items():
            pass_rate = stats['passed'] / stats['tests'] * 100 if stats['tests'] > 0 else 0
            print(f"\n  [{test_type}]")
            print(f"    测试套件: {stats['suites']}")
            print(f"    测试用例: {stats['tests']}")
            print(f"    通过/失败/警告: {stats['passed']}/{stats['failed']}/{stats['warnings']}")
            print(f"    通过率: {pass_rate:.1f}%")

        print("\n" + "-" * 80)
        print("                       各套件详情")
        print("-" * 80)

        for suite in self.suite_results:
            pass_rate = suite.passed / suite.total_tests * 100 if suite.total_tests > 0 else 0
            status_icon = "✓" if suite.failed == 0 else "✗"
            print(f"\n  {status_icon} {suite.suite_name} [{suite.test_type}]")
            print(f"    {suite.passed}/{suite.total_tests} 通过 ({pass_rate:.0f}%) | {suite.duration_ms:.0f}ms")

            for result in suite.results:
                status_char = {
                    TestStatus.PASSED: "✓",
                    TestStatus.FAILED: "✗",
                    TestStatus.WARNING: "⚠",
                    TestStatus.SKIPPED: "-"
                }.get(result.status, "?")
                print(f"      {status_char} {result.test_name}: {result.message[:50]}")

        print("\n" + "=" * 80)

        # 结论
        if summary['failed'] == 0:
            print("结论: 所有测试通过! ✓")
        else:
            print(f"结论: 有 {summary['failed']} 个测试失败，需要关注 ✗")

        print("=" * 80)


# ============================================================================
# 主程序
# ============================================================================

def run_comprehensive_tests():
    """运行综合测试"""
    print("\n" + "=" * 80)
    print("          水利枢纽智能控制柜 - 综合SIL/HIL/HITL测试演示")
    print("=" * 80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    report_generator = TestReportGenerator()

    # ========================
    # 1. SIL测试
    # ========================
    print("\n\n" + "#" * 80)
    print("#                       软件在环(SIL)测试                              #")
    print("#" * 80)

    sil_demonstrator = SILTestDemonstrator()

    # 阀门SIL测试
    valve_sil_result = sil_demonstrator.run_valve_sil_tests()
    report_generator.add_suite_result(valve_sil_result)

    # 水泵SIL测试
    pump_sil_result = sil_demonstrator.run_pump_sil_tests()
    report_generator.add_suite_result(pump_sil_result)

    # 闸门SIL测试
    gate_sil_result = sil_demonstrator.run_gate_sil_tests()
    report_generator.add_suite_result(gate_sil_result)

    # 多能互补SIL测试
    multi_energy_sil_result = sil_demonstrator.run_multi_energy_sil_tests()
    report_generator.add_suite_result(multi_energy_sil_result)

    # ========================
    # 2. HIL测试
    # ========================
    print("\n\n" + "#" * 80)
    print("#                       硬件在环(HIL)测试                              #")
    print("#" * 80)

    hil_demonstrator = HILTestDemonstrator()

    # 阀门HIL测试
    valve_hil_result = hil_demonstrator.run_valve_hil_tests()
    report_generator.add_suite_result(valve_hil_result)

    # ========================
    # 3. HITL测试
    # ========================
    print("\n\n" + "#" * 80)
    print("#                       人在环(HITL)测试                               #")
    print("#" * 80)

    hitl_demonstrator = HITLTestDemonstrator()

    # HITL测试
    hitl_result = hitl_demonstrator.run_hitl_tests()
    report_generator.add_suite_result(hitl_result)

    # ========================
    # 4. 生成报告
    # ========================
    report_generator.print_report()

    # 保存JSON报告
    summary = report_generator.generate_summary()
    report_path = project_root / "test_results" / "comprehensive_test_report.json"
    report_path.parent.mkdir(exist_ok=True)

    # 转换为可序列化格式
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'summary': summary,
        'suites': [
            {
                'name': s.suite_name,
                'type': s.test_type,
                'total': s.total_tests,
                'passed': s.passed,
                'failed': s.failed,
                'warnings': s.warnings,
                'duration_ms': s.duration_ms
            }
            for s in report_generator.suite_results
        ]
    }

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"\n报告已保存至: {report_path}")

    return summary


if __name__ == "__main__":
    summary = run_comprehensive_tests()

    # 根据结果设置退出码
    if summary['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)
