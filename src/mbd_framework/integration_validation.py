# -*- coding: utf-8 -*-
"""
Integration Validation - 集成测试与验证模块
Integration Testing and Validation Module

提供完整的集成测试、回归测试、覆盖分析和测试报告生成能力
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Tuple, Set
from datetime import datetime
import json
import copy
import hashlib


class TestLevel(Enum):
    """测试级别"""
    UNIT = auto()               # 单元测试
    INTEGRATION = auto()        # 集成测试
    SYSTEM = auto()             # 系统测试
    ACCEPTANCE = auto()         # 验收测试


class TestStatus(Enum):
    """测试状态"""
    NOT_RUN = auto()            # 未运行
    RUNNING = auto()            # 运行中
    PASSED = auto()             # 通过
    FAILED = auto()             # 失败
    ERROR = auto()              # 错误
    SKIPPED = auto()            # 跳过
    BLOCKED = auto()            # 阻塞


class RequirementStatus(Enum):
    """需求状态"""
    NOT_COVERED = auto()        # 未覆盖
    PARTIALLY_COVERED = auto()  # 部分覆盖
    FULLY_COVERED = auto()      # 完全覆盖
    VERIFIED = auto()           # 已验证


@dataclass
class IntegrationTestCase:
    """集成测试用例"""
    test_id: str                            # 测试ID
    name: str                               # 名称
    description: str                        # 描述
    level: TestLevel = TestLevel.INTEGRATION

    # 关联
    requirements: List[str] = field(default_factory=list)
    safety_goals: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)  # 涉及的组件

    # 前置条件
    preconditions: List[str] = field(default_factory=list)
    setup_steps: List[str] = field(default_factory=list)

    # 测试步骤
    test_steps: List[Dict] = field(default_factory=list)
    # step格式: {'step_id': str, 'action': str, 'expected': str}

    # 验收标准
    acceptance_criteria: List[str] = field(default_factory=list)

    # 清理
    teardown_steps: List[str] = field(default_factory=list)

    # 结果
    status: TestStatus = TestStatus.NOT_RUN
    actual_results: List[Dict] = field(default_factory=list)
    error_message: str = ""
    execution_time: float = 0.0
    executed_at: Optional[datetime] = None

    # 元数据
    priority: int = 2                       # 1(高), 2(中), 3(低)
    automated: bool = True                  # 是否自动化
    tags: List[str] = field(default_factory=list)


class IntegrationTestSuite:
    """集成测试套件"""

    def __init__(self, suite_id: str, name: str):
        self.suite_id = suite_id
        self.name = name
        self.description = ""
        self.test_cases: Dict[str, IntegrationTestCase] = {}
        self.test_order: List[str] = []     # 执行顺序

        # 环境配置
        self.setup_func: Optional[Callable] = None
        self.teardown_func: Optional[Callable] = None
        self.test_environment = None

        # 执行状态
        self.executed = False
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # 结果统计
        self.results: Dict[str, Dict] = {}
        self.passed_count = 0
        self.failed_count = 0
        self.error_count = 0
        self.skipped_count = 0

    def add_test_case(self, test_case: IntegrationTestCase):
        """添加测试用例"""
        self.test_cases[test_case.test_id] = test_case
        if test_case.test_id not in self.test_order:
            self.test_order.append(test_case.test_id)

    def set_test_order(self, order: List[str]):
        """设置执行顺序"""
        self.test_order = order

    def set_environment(self, env: Any):
        """设置测试环境"""
        self.test_environment = env

    def run(self, test_ids: List[str] = None,
           stop_on_failure: bool = False) -> Dict[str, Any]:
        """运行测试套件"""
        self.start_time = datetime.now()
        self.passed_count = 0
        self.failed_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.results = {}

        # 确定要运行的测试
        tests_to_run = test_ids or self.test_order

        # Suite级别setup
        if self.setup_func:
            try:
                self.setup_func()
            except Exception as e:
                return {'error': f'Suite setup failed: {str(e)}'}

        try:
            for test_id in tests_to_run:
                if test_id not in self.test_cases:
                    continue

                test_case = self.test_cases[test_id]
                result = self._run_single_test(test_case)
                self.results[test_id] = result

                # 更新统计
                if result['status'] == TestStatus.PASSED:
                    self.passed_count += 1
                elif result['status'] == TestStatus.FAILED:
                    self.failed_count += 1
                    if stop_on_failure:
                        break
                elif result['status'] == TestStatus.ERROR:
                    self.error_count += 1
                    if stop_on_failure:
                        break
                else:
                    self.skipped_count += 1

        finally:
            # Suite级别teardown
            if self.teardown_func:
                try:
                    self.teardown_func()
                except:
                    pass

        self.end_time = datetime.now()
        self.executed = True

        return self.get_summary()

    def _run_single_test(self, test_case: IntegrationTestCase) -> Dict[str, Any]:
        """运行单个测试"""
        test_case.status = TestStatus.RUNNING
        test_case.actual_results = []
        start_time = datetime.now()

        try:
            # 执行测试步骤
            all_passed = True
            for step in test_case.test_steps:
                step_result = self._execute_step(step)
                test_case.actual_results.append(step_result)
                if not step_result.get('passed', False):
                    all_passed = False

            test_case.status = TestStatus.PASSED if all_passed else TestStatus.FAILED

        except Exception as e:
            test_case.status = TestStatus.ERROR
            test_case.error_message = str(e)

        test_case.execution_time = (datetime.now() - start_time).total_seconds()
        test_case.executed_at = datetime.now()

        return {
            'test_id': test_case.test_id,
            'status': test_case.status,
            'execution_time': test_case.execution_time,
            'error_message': test_case.error_message,
            'results': test_case.actual_results
        }

    def _execute_step(self, step: Dict) -> Dict:
        """执行测试步骤"""
        result = {
            'step_id': step.get('step_id', ''),
            'action': step.get('action', ''),
            'expected': step.get('expected', ''),
            'passed': True,
            'actual': '',
            'timestamp': datetime.now().isoformat()
        }

        # 实际执行逻辑需要根据具体环境实现
        # 这里是示例实现
        if self.test_environment:
            try:
                # 执行动作并获取结果
                if hasattr(self.test_environment, 'execute_step'):
                    actual = self.test_environment.execute_step(step)
                    result['actual'] = str(actual)
                    result['passed'] = str(actual) == step.get('expected', '')
            except Exception as e:
                result['passed'] = False
                result['actual'] = f"Error: {str(e)}"

        return result

    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        total = len(self.results)
        return {
            'suite_id': self.suite_id,
            'suite_name': self.name,
            'executed': self.executed,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0,
            'total': total,
            'passed': self.passed_count,
            'failed': self.failed_count,
            'error': self.error_count,
            'skipped': self.skipped_count,
            'pass_rate': self.passed_count / total * 100 if total > 0 else 0
        }


class SystemValidation:
    """系统验证 - 完整的系统级验证"""

    def __init__(self, system_id: str, name: str):
        self.system_id = system_id
        self.name = name

        # 验证项
        self.validation_items: Dict[str, Dict] = {}
        self.validation_results: Dict[str, Dict] = {}

        # 关联
        self.requirements: Dict[str, Dict] = {}
        self.test_suites: Dict[str, IntegrationTestSuite] = {}

        # 状态
        self.validated = False
        self.validation_date: Optional[datetime] = None

    def add_validation_item(self, item_id: str, description: str,
                           method: str, criteria: List[str]):
        """添加验证项"""
        self.validation_items[item_id] = {
            'description': description,
            'method': method,  # TEST/ANALYSIS/INSPECTION/DEMO
            'criteria': criteria,
            'status': 'NOT_VALIDATED'
        }

    def add_requirement(self, req_id: str, description: str,
                       validation_items: List[str]):
        """添加需求"""
        self.requirements[req_id] = {
            'description': description,
            'validation_items': validation_items,
            'status': RequirementStatus.NOT_COVERED
        }

    def register_test_suite(self, suite: IntegrationTestSuite):
        """注册测试套件"""
        self.test_suites[suite.suite_id] = suite

    def validate(self) -> Dict[str, Any]:
        """执行系统验证"""
        results = {
            'system_id': self.system_id,
            'validation_date': datetime.now().isoformat(),
            'items': {},
            'requirements': {},
            'summary': {}
        }

        # 验证各项
        for item_id, item in self.validation_items.items():
            item_result = self._validate_item(item_id, item)
            results['items'][item_id] = item_result
            self.validation_results[item_id] = item_result

        # 更新需求状态
        for req_id, req in self.requirements.items():
            req_status = self._check_requirement_status(req)
            results['requirements'][req_id] = {
                'description': req['description'],
                'status': req_status.name
            }

        # 汇总
        total_items = len(self.validation_items)
        validated_items = sum(1 for r in results['items'].values()
                             if r.get('validated', False))
        results['summary'] = {
            'total_items': total_items,
            'validated_items': validated_items,
            'validation_rate': validated_items / total_items * 100 if total_items > 0 else 0,
            'overall_status': 'PASSED' if validated_items == total_items else 'INCOMPLETE'
        }

        self.validated = validated_items == total_items
        self.validation_date = datetime.now()

        return results

    def _validate_item(self, item_id: str, item: Dict) -> Dict:
        """验证单个验证项"""
        result = {
            'item_id': item_id,
            'description': item['description'],
            'method': item['method'],
            'validated': False,
            'evidence': []
        }

        # 查找关联的测试结果
        for suite in self.test_suites.values():
            for test_id, test_case in suite.test_cases.items():
                if item_id in test_case.tags or test_id.startswith(item_id):
                    if test_case.status == TestStatus.PASSED:
                        result['evidence'].append({
                            'type': 'TEST',
                            'id': test_id,
                            'status': 'PASSED'
                        })

        # 判断是否验证通过
        if result['evidence']:
            result['validated'] = all(e['status'] == 'PASSED' for e in result['evidence'])

        return result

    def _check_requirement_status(self, req: Dict) -> RequirementStatus:
        """检查需求状态"""
        validation_items = req['validation_items']
        if not validation_items:
            return RequirementStatus.NOT_COVERED

        validated_count = 0
        for item_id in validation_items:
            if item_id in self.validation_results:
                if self.validation_results[item_id].get('validated', False):
                    validated_count += 1

        if validated_count == 0:
            return RequirementStatus.NOT_COVERED
        elif validated_count < len(validation_items):
            return RequirementStatus.PARTIALLY_COVERED
        else:
            return RequirementStatus.VERIFIED


class RegressionTestManager:
    """回归测试管理器"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.test_suites: Dict[str, IntegrationTestSuite] = {}
        self.baseline_results: Dict[str, Dict] = {}
        self.regression_history: List[Dict] = []

        # 变更追踪
        self.changed_components: Set[str] = set()
        self.impact_matrix: Dict[str, List[str]] = {}  # 组件 -> 影响的测试

    def register_suite(self, suite: IntegrationTestSuite):
        """注册测试套件"""
        self.test_suites[suite.suite_id] = suite

    def set_baseline(self, suite_id: str, results: Dict[str, Any]):
        """设置基线结果"""
        self.baseline_results[suite_id] = {
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'checksum': self._compute_checksum(results)
        }

    def register_impact(self, component: str, test_ids: List[str]):
        """注册影响关系"""
        self.impact_matrix[component] = test_ids

    def report_change(self, component: str):
        """报告组件变更"""
        self.changed_components.add(component)

    def get_affected_tests(self) -> List[str]:
        """获取受影响的测试"""
        affected = set()
        for component in self.changed_components:
            if component in self.impact_matrix:
                affected.update(self.impact_matrix[component])
        return list(affected)

    def run_regression(self, full: bool = False) -> Dict[str, Any]:
        """运行回归测试"""
        start_time = datetime.now()

        if full:
            # 完整回归
            tests_to_run = None  # 运行所有
        else:
            # 增量回归 - 只运行受影响的测试
            tests_to_run = self.get_affected_tests()

        results = {
            'type': 'FULL' if full else 'INCREMENTAL',
            'start_time': start_time.isoformat(),
            'changed_components': list(self.changed_components),
            'suites': {}
        }

        for suite_id, suite in self.test_suites.items():
            if tests_to_run is not None:
                # 筛选套件中的测试
                suite_tests = [t for t in tests_to_run if t in suite.test_cases]
                if not suite_tests:
                    continue
                suite_result = suite.run(suite_tests)
            else:
                suite_result = suite.run()

            results['suites'][suite_id] = suite_result

            # 比较基线
            if suite_id in self.baseline_results:
                comparison = self._compare_with_baseline(suite_id, suite_result)
                results['suites'][suite_id]['baseline_comparison'] = comparison

        results['end_time'] = datetime.now().isoformat()

        # 记录历史
        self.regression_history.append(results)

        # 清除变更记录
        self.changed_components.clear()

        return results

    def _compare_with_baseline(self, suite_id: str,
                               current_results: Dict) -> Dict[str, Any]:
        """与基线比较"""
        baseline = self.baseline_results[suite_id]['results']
        comparison = {
            'new_failures': [],
            'new_passes': [],
            'regressions': [],
            'improvements': []
        }

        baseline_tests = baseline.get('results', {})
        current_tests = current_results.get('results', {})

        for test_id in set(baseline_tests.keys()) | set(current_tests.keys()):
            baseline_status = baseline_tests.get(test_id, {}).get('status')
            current_status = current_tests.get(test_id, {}).get('status')

            if baseline_status == TestStatus.PASSED and current_status == TestStatus.FAILED:
                comparison['regressions'].append(test_id)
            elif baseline_status == TestStatus.FAILED and current_status == TestStatus.PASSED:
                comparison['improvements'].append(test_id)
            elif baseline_status is None and current_status == TestStatus.FAILED:
                comparison['new_failures'].append(test_id)
            elif baseline_status is None and current_status == TestStatus.PASSED:
                comparison['new_passes'].append(test_id)

        return comparison

    def _compute_checksum(self, data: Any) -> str:
        """计算数据校验和"""
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()


@dataclass
class CoverageItem:
    """覆盖项"""
    item_id: str
    item_type: str                          # REQUIREMENT/CODE/BRANCH/CONDITION
    description: str
    covered: bool = False
    coverage_evidence: List[str] = field(default_factory=list)


class CoverageAnalyzer:
    """覆盖分析器"""

    def __init__(self):
        self.coverage_items: Dict[str, CoverageItem] = {}
        self.test_coverage_map: Dict[str, Set[str]] = {}  # 测试ID -> 覆盖项集合

    def add_item(self, item: CoverageItem):
        """添加覆盖项"""
        self.coverage_items[item.item_id] = item

    def record_coverage(self, test_id: str, covered_items: List[str]):
        """记录测试覆盖"""
        if test_id not in self.test_coverage_map:
            self.test_coverage_map[test_id] = set()

        for item_id in covered_items:
            self.test_coverage_map[test_id].add(item_id)
            if item_id in self.coverage_items:
                self.coverage_items[item_id].covered = True
                self.coverage_items[item_id].coverage_evidence.append(test_id)

    def get_coverage_by_type(self, item_type: str) -> Dict[str, Any]:
        """按类型获取覆盖率"""
        items = [i for i in self.coverage_items.values() if i.item_type == item_type]
        if not items:
            return {'type': item_type, 'total': 0, 'covered': 0, 'percentage': 0.0}

        covered = sum(1 for i in items if i.covered)
        return {
            'type': item_type,
            'total': len(items),
            'covered': covered,
            'percentage': covered / len(items) * 100
        }

    def get_uncovered_items(self) -> List[CoverageItem]:
        """获取未覆盖项"""
        return [i for i in self.coverage_items.values() if not i.covered]

    def generate_report(self) -> Dict[str, Any]:
        """生成覆盖报告"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {},
            'by_type': {},
            'uncovered': [],
            'test_coverage': {}
        }

        # 总体统计
        total = len(self.coverage_items)
        covered = sum(1 for i in self.coverage_items.values() if i.covered)
        report['summary'] = {
            'total_items': total,
            'covered_items': covered,
            'overall_percentage': covered / total * 100 if total > 0 else 0
        }

        # 按类型统计
        types = set(i.item_type for i in self.coverage_items.values())
        for item_type in types:
            report['by_type'][item_type] = self.get_coverage_by_type(item_type)

        # 未覆盖项
        report['uncovered'] = [
            {'id': i.item_id, 'type': i.item_type, 'description': i.description}
            for i in self.get_uncovered_items()
        ]

        # 测试覆盖贡献
        for test_id, items in self.test_coverage_map.items():
            report['test_coverage'][test_id] = {
                'items_covered': len(items),
                'items': list(items)
            }

        return report


class RequirementCoverage:
    """需求覆盖追溯"""

    def __init__(self):
        self.requirements: Dict[str, Dict] = {}
        self.test_links: Dict[str, List[str]] = {}  # 需求ID -> 测试ID列表
        self.verification_status: Dict[str, RequirementStatus] = {}

    def add_requirement(self, req_id: str, description: str,
                       priority: str = "MEDIUM", safety_related: bool = False):
        """添加需求"""
        self.requirements[req_id] = {
            'description': description,
            'priority': priority,
            'safety_related': safety_related,
            'created': datetime.now().isoformat()
        }
        self.test_links[req_id] = []
        self.verification_status[req_id] = RequirementStatus.NOT_COVERED

    def link_test(self, req_id: str, test_id: str):
        """关联测试"""
        if req_id in self.test_links:
            if test_id not in self.test_links[req_id]:
                self.test_links[req_id].append(test_id)
            self._update_status(req_id)

    def update_test_result(self, test_id: str, passed: bool):
        """更新测试结果"""
        for req_id, tests in self.test_links.items():
            if test_id in tests:
                self._update_status(req_id)

    def _update_status(self, req_id: str):
        """更新需求状态"""
        tests = self.test_links.get(req_id, [])
        if not tests:
            self.verification_status[req_id] = RequirementStatus.NOT_COVERED
        else:
            # 简化: 有测试链接即视为部分覆盖
            self.verification_status[req_id] = RequirementStatus.PARTIALLY_COVERED

    def get_coverage_summary(self) -> Dict[str, Any]:
        """获取覆盖摘要"""
        total = len(self.requirements)
        status_counts = {}
        for status in RequirementStatus:
            count = sum(1 for s in self.verification_status.values() if s == status)
            status_counts[status.name] = count

        return {
            'total_requirements': total,
            'status_distribution': status_counts,
            'coverage_percentage': status_counts.get('VERIFIED', 0) / total * 100 if total > 0 else 0
        }

    def get_traceability_matrix(self) -> Dict[str, Any]:
        """获取追溯矩阵"""
        matrix = {}
        for req_id, req in self.requirements.items():
            matrix[req_id] = {
                'description': req['description'],
                'priority': req['priority'],
                'safety_related': req['safety_related'],
                'linked_tests': self.test_links.get(req_id, []),
                'status': self.verification_status.get(req_id, RequirementStatus.NOT_COVERED).name
            }
        return matrix


class TestReportGenerator:
    """测试报告生成器"""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.test_results: List[Dict] = []
        self.coverage_data: Optional[Dict] = None
        self.requirement_data: Optional[Dict] = None

    def add_test_results(self, results: Dict[str, Any]):
        """添加测试结果"""
        self.test_results.append({
            'timestamp': datetime.now().isoformat(),
            'results': results
        })

    def set_coverage_data(self, coverage: Dict[str, Any]):
        """设置覆盖数据"""
        self.coverage_data = coverage

    def set_requirement_data(self, requirements: Dict[str, Any]):
        """设置需求数据"""
        self.requirement_data = requirements

    def generate_summary_report(self) -> Dict[str, Any]:
        """生成摘要报告"""
        report = {
            'project': self.project_name,
            'generated_at': datetime.now().isoformat(),
            'test_summary': self._summarize_tests(),
            'coverage_summary': self.coverage_data.get('summary', {}) if self.coverage_data else {},
            'requirement_summary': self.requirement_data.get('summary', {}) if self.requirement_data else {},
            'overall_status': 'UNKNOWN'
        }

        # 确定整体状态
        test_pass_rate = report['test_summary'].get('pass_rate', 0)
        coverage_rate = report['coverage_summary'].get('overall_percentage', 0)

        if test_pass_rate >= 95 and coverage_rate >= 80:
            report['overall_status'] = 'READY_FOR_RELEASE'
        elif test_pass_rate >= 80 and coverage_rate >= 60:
            report['overall_status'] = 'ACCEPTABLE'
        elif test_pass_rate >= 50:
            report['overall_status'] = 'NEEDS_IMPROVEMENT'
        else:
            report['overall_status'] = 'CRITICAL_ISSUES'

        return report

    def _summarize_tests(self) -> Dict[str, Any]:
        """汇总测试结果"""
        if not self.test_results:
            return {}

        latest = self.test_results[-1]['results']

        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_errors = 0

        if 'suites' in latest:
            for suite_result in latest['suites'].values():
                total_tests += suite_result.get('total', 0)
                total_passed += suite_result.get('passed', 0)
                total_failed += suite_result.get('failed', 0)
                total_errors += suite_result.get('error', 0)
        else:
            total_tests = latest.get('total', 0)
            total_passed = latest.get('passed', 0)
            total_failed = latest.get('failed', 0)
            total_errors = latest.get('error', 0)

        return {
            'total_tests': total_tests,
            'passed': total_passed,
            'failed': total_failed,
            'errors': total_errors,
            'pass_rate': total_passed / total_tests * 100 if total_tests > 0 else 0
        }

    def generate_detailed_report(self) -> Dict[str, Any]:
        """生成详细报告"""
        report = self.generate_summary_report()

        # 添加详细信息
        report['test_details'] = self.test_results
        report['coverage_details'] = self.coverage_data
        report['requirement_details'] = self.requirement_data

        # 添加问题清单
        report['issues'] = self._collect_issues()

        # 添加建议
        report['recommendations'] = self._generate_recommendations(report)

        return report

    def _collect_issues(self) -> List[Dict]:
        """收集问题"""
        issues = []

        # 从测试结果收集失败
        if self.test_results:
            latest = self.test_results[-1]['results']
            if 'suites' in latest:
                for suite_id, suite_result in latest['suites'].items():
                    if 'results' in suite_result:
                        for test_id, test_result in suite_result['results'].items():
                            if test_result.get('status') in [TestStatus.FAILED, TestStatus.ERROR]:
                                issues.append({
                                    'type': 'TEST_FAILURE',
                                    'id': test_id,
                                    'suite': suite_id,
                                    'message': test_result.get('error_message', '')
                                })

        # 从覆盖数据收集未覆盖项
        if self.coverage_data and 'uncovered' in self.coverage_data:
            for item in self.coverage_data['uncovered']:
                issues.append({
                    'type': 'COVERAGE_GAP',
                    'id': item.get('id', ''),
                    'description': item.get('description', '')
                })

        return issues

    def _generate_recommendations(self, report: Dict) -> List[str]:
        """生成建议"""
        recommendations = []

        summary = report.get('test_summary', {})
        pass_rate = summary.get('pass_rate', 0)
        failed = summary.get('failed', 0)

        if pass_rate < 80:
            recommendations.append("测试通过率低于80%,需要优先修复失败的测试用例")

        if failed > 0:
            recommendations.append(f"有{failed}个测试失败,建议分析根本原因并修复")

        coverage = report.get('coverage_summary', {})
        coverage_rate = coverage.get('overall_percentage', 0)

        if coverage_rate < 70:
            recommendations.append("覆盖率低于70%,需要增加测试用例以提高覆盖")

        if not recommendations:
            recommendations.append("测试状态良好,可以考虑进行发布准备")

        return recommendations

    def export_html(self, filepath: str):
        """导出HTML报告"""
        report = self.generate_detailed_report()

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>测试报告 - {self.project_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>测试报告 - {self.project_name}</h1>
    <p>生成时间: {report['generated_at']}</p>

    <div class="summary">
        <h2>测试摘要</h2>
        <p>总测试数: {report['test_summary'].get('total_tests', 0)}</p>
        <p class="passed">通过: {report['test_summary'].get('passed', 0)}</p>
        <p class="failed">失败: {report['test_summary'].get('failed', 0)}</p>
        <p>通过率: {report['test_summary'].get('pass_rate', 0):.1f}%</p>
    </div>

    <div class="summary">
        <h2>覆盖摘要</h2>
        <p>覆盖率: {report['coverage_summary'].get('overall_percentage', 0):.1f}%</p>
    </div>

    <h2>问题清单</h2>
    <table>
        <tr><th>类型</th><th>ID</th><th>描述</th></tr>
        {''.join(f"<tr><td>{i['type']}</td><td>{i.get('id', '')}</td><td>{i.get('message', i.get('description', ''))}</td></tr>" for i in report.get('issues', []))}
    </table>

    <h2>建议</h2>
    <ul>
        {''.join(f"<li>{r}</li>" for r in report.get('recommendations', []))}
    </ul>

    <p>整体状态: <strong>{report['overall_status']}</strong></p>
</body>
</html>
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)


# 预定义的集成测试用例
def create_hydraulic_integration_tests() -> List[IntegrationTestCase]:
    """创建水利系统集成测试用例"""
    test_cases = []

    # 测试1: 阀门-管道系统集成
    test_cases.append(IntegrationTestCase(
        test_id="INT_VALVE_PIPE_001",
        name="阀门-管道水锤联合测试",
        description="测试阀门快关时管道系统的水锤响应",
        level=TestLevel.INTEGRATION,
        requirements=["REQ_INT_001", "REQ_SAFETY_001"],
        safety_goals=["SG_WATER_HAMMER"],
        components=["VALVE_CONTROLLER", "PIPE_MODEL", "PRESSURE_SENSOR"],
        preconditions=[
            "系统处于稳态运行",
            "流量为额定值",
            "所有传感器正常"
        ],
        test_steps=[
            {'step_id': 'S1', 'action': '记录初始压力', 'expected': '压力在正常范围'},
            {'step_id': 'S2', 'action': '发送阀门快关命令', 'expected': '阀门开始关闭'},
            {'step_id': 'S3', 'action': '监测压力峰值', 'expected': '压力不超过1.5倍额定值'},
            {'step_id': 'S4', 'action': '检查水锤防护', 'expected': '两阶段关闭曲线生效'}
        ],
        acceptance_criteria=[
            "压力峰值不超过设计值的150%",
            "无负压出现",
            "阀门完成关闭"
        ],
        priority=1,
        tags=["SAFETY", "WATER_HAMMER"]
    ))

    # 测试2: 泵站系统集成
    test_cases.append(IntegrationTestCase(
        test_id="INT_PUMP_STATION_001",
        name="泵站启停集成测试",
        description="测试多台泵的协调启停和负荷分配",
        components=["PUMP_CONTROLLER", "VALVE_CONTROLLER", "PRESSURE_SENSOR", "FLOW_SENSOR"],
        test_steps=[
            {'step_id': 'S1', 'action': '启动1号泵', 'expected': '1号泵正常启动'},
            {'step_id': 'S2', 'action': '等待稳定', 'expected': '流量达到设定值'},
            {'step_id': 'S3', 'action': '启动2号泵', 'expected': '负荷自动分配'},
            {'step_id': 'S4', 'action': '停止1号泵', 'expected': '2号泵接管全部负荷'}
        ],
        priority=2
    ))

    return test_cases


def create_multi_energy_integration_tests() -> List[IntegrationTestCase]:
    """创建多能互补系统集成测试用例"""
    test_cases = []

    # 测试1: 储能响应链集成
    test_cases.append(IntegrationTestCase(
        test_id="INT_STORAGE_CHAIN_001",
        name="储能响应链集成测试",
        description="测试SC-BESS-PSH三级储能响应链的协调",
        components=["SC", "BESS", "PSH", "GRID_MODEL"],
        test_steps=[
            {'step_id': 'S1', 'action': '注入频率扰动', 'expected': 'SC立即响应'},
            {'step_id': 'S2', 'action': '监测功率转移', 'expected': 'BESS逐步接管'},
            {'step_id': 'S3', 'action': '验证PSH响应', 'expected': 'PSH在预定时间内响应'},
            {'step_id': 'S4', 'action': '检查频率恢复', 'expected': '频率恢复到50±0.1Hz'}
        ],
        acceptance_criteria=[
            "响应链无断裂",
            "频率偏差不超过0.5Hz",
            "各储能SOC保持在安全范围"
        ],
        priority=1
    ))

    return test_cases
