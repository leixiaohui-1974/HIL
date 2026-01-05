# -*- coding: utf-8 -*-
"""
HIL验收报告生成器
Digital FAT Report Generator

生成符合规范要求的数字验收报告，包括：
- 测试结果汇总
- 过程曲线数据
- 安全适用范围图谱
- 验收结论
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types"""
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


@dataclass
class DeviceInfo:
    """设备信息"""
    device_type: str           # 设备类型 (IVCU/IPCU/IGCU)
    device_id: str             # 设备编号
    manufacturer: str = ""     # 制造商
    model: str = ""            # 型号
    serial_number: str = ""    # 序列号
    firmware_version: str = "" # 固件版本


@dataclass
class TestEnvironment:
    """测试环境"""
    test_date: str             # 测试日期
    test_location: str = "HIL实验室"  # 测试地点
    ambient_temp: float = 25.0 # 环境温度
    simulator_version: str = "1.0.0"  # 仿真器版本
    tester: str = ""           # 测试人员


class HILReportGenerator:
    """HIL验收报告生成器"""

    def __init__(self):
        self.device_info: Optional[DeviceInfo] = None
        self.test_env: Optional[TestEnvironment] = None
        self.test_results: Dict[str, Any] = {}
        self.process_data: Dict[str, List] = {}
        self.sensitivity_data: Dict[str, Any] = {}

    def set_device_info(self, device_type: str, device_id: str, **kwargs) -> None:
        """设置设备信息"""
        self.device_info = DeviceInfo(
            device_type=device_type,
            device_id=device_id,
            **kwargs
        )

    def set_test_environment(self, **kwargs) -> None:
        """设置测试环境"""
        self.test_env = TestEnvironment(
            test_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **kwargs
        )

    def add_test_result(self, suite_name: str, results: Dict) -> None:
        """添加测试结果"""
        self.test_results[suite_name] = results

    def add_process_data(self, test_id: str, data: List[Dict]) -> None:
        """添加过程曲线数据"""
        self.process_data[test_id] = data

    def add_sensitivity_data(self, param_name: str, data: List[Dict]) -> None:
        """添加敏感性分析数据"""
        self.sensitivity_data[param_name] = data

    def generate_text_report(self) -> str:
        """生成文本格式报告"""
        lines = []

        # 标题
        lines.extend([
            "╔" + "═" * 78 + "╗",
            "║" + " " * 20 + "水利枢纽智能控制柜 HIL 数字验收报告" + " " * 21 + "║",
            "║" + " " * 15 + "Hardware-in-the-Loop Digital FAT Report" + " " * 24 + "║",
            "╚" + "═" * 78 + "╝",
            "",
        ])

        # 设备信息
        if self.device_info:
            lines.extend([
                "一、被测设备信息",
                "─" * 40,
                f"  设备类型: {self.device_info.device_type}",
                f"  设备编号: {self.device_info.device_id}",
            ])
            if self.device_info.manufacturer:
                lines.append(f"  制造商: {self.device_info.manufacturer}")
            if self.device_info.model:
                lines.append(f"  型号: {self.device_info.model}")
            if self.device_info.serial_number:
                lines.append(f"  序列号: {self.device_info.serial_number}")
            lines.append("")

        # 测试环境
        if self.test_env:
            lines.extend([
                "二、测试环境",
                "─" * 40,
                f"  测试日期: {self.test_env.test_date}",
                f"  测试地点: {self.test_env.test_location}",
                f"  仿真器版本: {self.test_env.simulator_version}",
            ])
            if self.test_env.tester:
                lines.append(f"  测试人员: {self.test_env.tester}")
            lines.append("")

        # 测试结果汇总
        lines.extend([
            "三、测试结果汇总",
            "─" * 40,
        ])

        total_tests = 0
        total_passed = 0

        for suite_name, results in self.test_results.items():
            suite_total = results.get('total', 0)
            suite_passed = results.get('passed', 0)
            suite_failed = results.get('failed', 0)
            suite_error = results.get('error', 0)
            pass_rate = results.get('pass_rate', 0) * 100

            total_tests += suite_total
            total_passed += suite_passed

            lines.extend([
                f"\n  【{suite_name}】",
                f"    总计: {suite_total} | 通过: {suite_passed} | "
                f"失败: {suite_failed} | 错误: {suite_error}",
                f"    通过率: {pass_rate:.1f}%",
            ])

            # 详细结果
            for test in results.get('results', []):
                status = "✓" if test.get('passed') else "✗"
                lines.append(f"    {status} [{test['test_id']}] {test['test_name']}")

                # 判据详情
                for criterion, passed in test.get('criteria', {}).items():
                    c_status = "✓" if passed else "✗"
                    measurement = test.get('measurements', {}).get(criterion)
                    if measurement is not None:
                        lines.append(f"        {c_status} {criterion}: {measurement:.4f}")
                    else:
                        lines.append(f"        {c_status} {criterion}")

        lines.append("")

        # 敏感性分析结果
        if self.sensitivity_data:
            lines.extend([
                "四、参数敏感性分析",
                "─" * 40,
            ])

            for param_name, data in self.sensitivity_data.items():
                lines.append(f"\n  参数: {param_name}")
                if isinstance(data, dict) and 'safe_range' in data:
                    sr = data.get('safe_range')
                    if sr:
                        lines.append(f"    安全范围: {sr[0]:.1f} ~ {sr[1]:.1f}")
                    lines.append(f"    通过率: {data.get('pass_rate', 0)*100:.1f}%")

            lines.append("")

        # 验收结论
        lines.extend([
            "五、验收结论",
            "─" * 40,
        ])

        overall_pass_rate = total_passed / total_tests if total_tests > 0 else 0

        if overall_pass_rate >= 1.0:
            conclusion = "PASSED"
            lines.extend([
                "",
                "  ★★★ 所有测试通过 ★★★",
                "",
                "  结论: 被测设备符合《水利枢纽关键设备智能控制与数字验收规范》要求",
                "  建议: 可贴 'HIL Verified' 标签出厂",
            ])
        elif overall_pass_rate >= 0.8:
            conclusion = "CONDITIONAL"
            lines.extend([
                "",
                "  ⚠ 部分测试未通过",
                "",
                f"  总体通过率: {overall_pass_rate*100:.1f}%",
                "  结论: 被测设备基本符合规范要求，建议对未通过项进行整改",
            ])
        else:
            conclusion = "FAILED"
            lines.extend([
                "",
                "  ✗ 多项测试未通过",
                "",
                f"  总体通过率: {overall_pass_rate*100:.1f}%",
                "  结论: 被测设备不符合规范要求，需进行设计改进",
            ])

        lines.extend([
            "",
            "─" * 40,
            f"  报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "  报告版本: v1.0",
            "",
            "═" * 80,
        ])

        return "\n".join(lines)

    def generate_json_report(self) -> Dict:
        """生成JSON格式报告"""
        return {
            'report_type': 'HIL_Digital_FAT',
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'device_info': asdict(self.device_info) if self.device_info else None,
            'test_environment': asdict(self.test_env) if self.test_env else None,
            'test_results': self.test_results,
            'process_data': self.process_data,
            'sensitivity_data': self.sensitivity_data,
        }

    def save_report(self, filename: str, format: str = 'text') -> None:
        """保存报告到文件

        Args:
            filename: 文件名
            format: 格式 ('text' 或 'json')
        """
        if format == 'json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.generate_json_report(), f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
        else:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.generate_text_report())


def generate_sample_report():
    """生成示例报告"""
    generator = HILReportGenerator()

    # 设置设备信息
    generator.set_device_info(
        device_type="IVCU",
        device_id="IVCU-2024-001",
        manufacturer="水利智控科技有限公司",
        model="IVCU-DN2000",
        serial_number="SN20240101001",
        firmware_version="v2.1.0"
    )

    # 设置测试环境
    generator.set_test_environment(
        test_location="国家水利装备质检中心HIL实验室",
        tester="张工"
    )

    # 添加测试结果
    generator.add_test_result("多类型阀门测试", {
        'total': 7,
        'passed': 3,
        'failed': 4,
        'error': 0,
        'pass_rate': 0.429,
        'results': [
            {
                'test_id': 'WHV-01',
                'test_name': '泄压响应测试',
                'passed': True,
                'criteria': {'响应时间 <= 50ms': True},
                'measurements': {'响应时间 <= 50ms': 42.5}
            },
            {
                'test_id': 'ESV-02',
                'test_name': '过压触发测试',
                'passed': True,
                'criteria': {'过压自动触发关闭': True, '触发源为过压': True},
                'measurements': {}
            },
            {
                'test_id': 'ESV-03',
                'test_name': '联锁触发测试',
                'passed': True,
                'criteria': {'联锁自动触发关闭': True, '触发源为联锁': True},
                'measurements': {}
            },
        ]
    })

    # 添加敏感性分析数据
    generator.add_sensitivity_data("pipe_length", {
        'safe_range': (5000, 30000),
        'pass_rate': 0.85,
    })

    return generator


if __name__ == "__main__":
    generator = generate_sample_report()
    print(generator.generate_text_report())
