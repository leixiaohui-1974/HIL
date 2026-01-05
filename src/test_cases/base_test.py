# -*- coding: utf-8 -*-
"""
HIL测试用例基类
HIL Test Case Base Classes
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time


class TestStatus(Enum):
    """测试状态"""
    NOT_RUN = "not_run"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    test_name: str
    status: TestStatus = TestStatus.NOT_RUN
    duration: float = 0.0
    criteria: Dict[str, bool] = field(default_factory=dict)
    measurements: Dict[str, float] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    error_message: str = ""

    def passed(self) -> bool:
        """是否通过"""
        return self.status == TestStatus.PASSED

    def add_log(self, message: str) -> None:
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")

    def check_criterion(self, name: str, condition: bool, measurement: Optional[float] = None) -> bool:
        """检查判据

        Args:
            name: 判据名称
            condition: 是否满足
            measurement: 测量值

        Returns:
            是否满足
        """
        self.criteria[name] = condition
        if measurement is not None:
            self.measurements[name] = measurement
        return condition

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'test_id': self.test_id,
            'test_name': self.test_name,
            'status': self.status.value,
            'duration': self.duration,
            'criteria': self.criteria,
            'measurements': self.measurements,
            'passed': self.passed(),
            'error': self.error_message,
        }

    def summary(self) -> str:
        """生成摘要"""
        lines = [
            f"测试: {self.test_id} - {self.test_name}",
            f"状态: {self.status.value}",
            f"耗时: {self.duration:.2f}s",
            "判据结果:",
        ]
        for name, passed in self.criteria.items():
            status = "✓" if passed else "✗"
            if name in self.measurements:
                lines.append(f"  {status} {name}: {self.measurements[name]:.4f}")
            else:
                lines.append(f"  {status} {name}")

        if self.error_message:
            lines.append(f"错误: {self.error_message}")

        return "\n".join(lines)


class HILTestCase(ABC):
    """HIL测试用例抽象基类"""

    def __init__(self, test_id: str, test_name: str, description: str = ""):
        """初始化

        Args:
            test_id: 测试编号
            test_name: 测试名称
            description: 测试描述
        """
        self.test_id = test_id
        self.test_name = test_name
        self.description = description
        self.result = TestResult(test_id, test_name)

        # 测试配置
        self.duration: float = 60.0       # 测试时长 (s)
        self.dt: float = 0.01             # 时间步长 (s)
        self.timeout: float = 120.0       # 超时时间 (s)

        # 仿真和控制器引用
        self.simulator = None
        self.controller = None
        self.sensor_array = None

    @abstractmethod
    def setup(self) -> None:
        """测试准备

        初始化仿真模型、控制器和传感器
        """
        pass

    @abstractmethod
    def run(self) -> TestResult:
        """执行测试

        Returns:
            测试结果
        """
        pass

    @abstractmethod
    def evaluate(self) -> bool:
        """评估测试结果

        Returns:
            是否通过
        """
        pass

    def teardown(self) -> None:
        """测试清理"""
        pass

    def execute(self) -> TestResult:
        """执行完整测试流程

        Returns:
            测试结果
        """
        self.result.status = TestStatus.RUNNING
        start_time = time.time()

        try:
            # 准备
            self.result.add_log(f"开始测试: {self.test_id}")
            self.setup()
            self.result.add_log("测试准备完成")

            # 执行
            self.run()
            self.result.add_log("测试执行完成")

            # 评估
            passed = self.evaluate()
            self.result.status = TestStatus.PASSED if passed else TestStatus.FAILED
            self.result.add_log(f"测试{'通过' if passed else '未通过'}")

        except Exception as e:
            self.result.status = TestStatus.ERROR
            self.result.error_message = str(e)
            self.result.add_log(f"测试异常: {e}")

        finally:
            self.teardown()
            self.result.duration = time.time() - start_time

        return self.result


class HILTestSuite:
    """HIL测试套件"""

    def __init__(self, suite_name: str):
        """初始化

        Args:
            suite_name: 套件名称
        """
        self.suite_name = suite_name
        self.test_cases: List[HILTestCase] = []
        self.results: List[TestResult] = []

    def add_test(self, test_case: HILTestCase) -> None:
        """添加测试用例"""
        self.test_cases.append(test_case)

    def run_all(self) -> List[TestResult]:
        """运行所有测试"""
        self.results = []
        for test_case in self.test_cases:
            result = test_case.execute()
            self.results.append(result)
        return self.results

    def run_by_id(self, test_id: str) -> Optional[TestResult]:
        """运行指定测试"""
        for test_case in self.test_cases:
            if test_case.test_id == test_id:
                result = test_case.execute()
                self.results.append(result)
                return result
        return None

    def get_summary(self) -> Dict:
        """获取测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        error = sum(1 for r in self.results if r.status == TestStatus.ERROR)

        return {
            'suite_name': self.suite_name,
            'total': total,
            'passed': passed,
            'failed': failed,
            'error': error,
            'pass_rate': passed / total if total > 0 else 0,
            'results': [r.to_dict() for r in self.results],
        }

    def print_report(self) -> None:
        """打印测试报告"""
        summary = self.get_summary()

        print("=" * 60)
        print(f"测试套件: {self.suite_name}")
        print("=" * 60)
        print(f"总计: {summary['total']} | 通过: {summary['passed']} | "
              f"失败: {summary['failed']} | 错误: {summary['error']}")
        print(f"通过率: {summary['pass_rate']*100:.1f}%")
        print("-" * 60)

        for result in self.results:
            status_icon = {
                TestStatus.PASSED: "✓",
                TestStatus.FAILED: "✗",
                TestStatus.ERROR: "!",
            }.get(result.status, "?")

            print(f"{status_icon} [{result.test_id}] {result.test_name} - "
                  f"{result.status.value} ({result.duration:.2f}s)")

        print("=" * 60)
