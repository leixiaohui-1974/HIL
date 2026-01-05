# -*- coding: utf-8 -*-
"""
HIL 实时监控仪表盘
HIL Real-time Monitoring Dashboard

提供测试过程的实时监控显示：
- 状态指示器
- 实时数据显示
- 报警信息
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StatusIndicator:
    """状态指示器"""
    name: str
    value: float
    unit: str
    status: str  # normal, warning, alarm
    min_val: float = 0.0
    max_val: float = 100.0


class HILDashboard:
    """HIL 监控仪表盘

    提供测试过程的状态监控和数据显示
    """

    def __init__(self, title: str = "HIL 测试监控"):
        """初始化

        Args:
            title: 仪表盘标题
        """
        self.title = title
        self.indicators: Dict[str, StatusIndicator] = {}
        self.alarms: List[Dict] = []
        self.history: List[Dict] = []
        self._max_history = 1000

        # 初始化默认指示器
        self._init_default_indicators()

    def _init_default_indicators(self) -> None:
        """初始化默认指示器"""
        defaults = [
            ("pressure", "压力", "MPa", 0.0, 2.0),
            ("flow", "流量", "m³/s", 0.0, 50.0),
            ("level", "水位", "m", 0.0, 10.0),
            ("opening", "开度", "%", 0.0, 100.0),
            ("speed", "转速", "rpm", 0.0, 2000.0),
        ]

        for key, name, unit, min_v, max_v in defaults:
            self.indicators[key] = StatusIndicator(
                name=name,
                value=0.0,
                unit=unit,
                status="normal",
                min_val=min_v,
                max_val=max_v
            )

    def update(self, data: Dict[str, float]) -> None:
        """更新仪表盘数据

        Args:
            data: 数据字典
        """
        timestamp = datetime.now()

        for key, value in data.items():
            if key in self.indicators:
                indicator = self.indicators[key]
                indicator.value = value

                # 判断状态
                if value < indicator.min_val or value > indicator.max_val:
                    indicator.status = "alarm"
                elif value < indicator.min_val * 1.1 or value > indicator.max_val * 0.9:
                    indicator.status = "warning"
                else:
                    indicator.status = "normal"

        # 记录历史
        record = {"timestamp": timestamp, **data}
        self.history.append(record)

        # 限制历史记录长度
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history:]

    def add_alarm(self, level: str, message: str, source: str = "") -> None:
        """添加报警

        Args:
            level: 报警等级 (info, warning, alarm, critical)
            message: 报警消息
            source: 报警来源
        """
        alarm = {
            "timestamp": datetime.now(),
            "level": level,
            "message": message,
            "source": source,
            "acknowledged": False
        }
        self.alarms.append(alarm)

    def acknowledge_alarms(self) -> int:
        """确认所有报警

        Returns:
            确认的报警数量
        """
        count = 0
        for alarm in self.alarms:
            if not alarm["acknowledged"]:
                alarm["acknowledged"] = True
                count += 1
        return count

    def clear_alarms(self) -> None:
        """清除所有已确认的报警"""
        self.alarms = [a for a in self.alarms if not a["acknowledged"]]

    def get_display(self) -> str:
        """获取文本显示

        Returns:
            仪表盘文本显示
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"  {self.title}")
        lines.append("=" * 60)
        lines.append("")

        # 状态指示器
        lines.append("【实时数据】")
        lines.append("-" * 40)

        for key, ind in self.indicators.items():
            status_symbol = {
                "normal": "●",
                "warning": "◐",
                "alarm": "○"
            }.get(ind.status, "?")

            bar_width = 20
            if ind.max_val > ind.min_val:
                progress = (ind.value - ind.min_val) / (ind.max_val - ind.min_val)
                progress = max(0, min(1, progress))
                filled = int(progress * bar_width)
                bar = "█" * filled + "░" * (bar_width - filled)
            else:
                bar = "░" * bar_width

            lines.append(f"  {status_symbol} {ind.name:8s}: {ind.value:8.2f} {ind.unit:6s} [{bar}]")

        lines.append("")

        # 报警信息
        active_alarms = [a for a in self.alarms if not a["acknowledged"]]
        if active_alarms:
            lines.append("【活动报警】")
            lines.append("-" * 40)
            for alarm in active_alarms[-5:]:  # 显示最近5条
                level_symbol = {
                    "info": "ℹ",
                    "warning": "⚠",
                    "alarm": "⚡",
                    "critical": "🔥"
                }.get(alarm["level"], "?")
                time_str = alarm["timestamp"].strftime("%H:%M:%S")
                lines.append(f"  {level_symbol} [{time_str}] {alarm['message']}")
            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    def get_summary(self) -> Dict:
        """获取状态摘要

        Returns:
            状态摘要字典
        """
        return {
            "title": self.title,
            "indicators": {
                k: {
                    "name": v.name,
                    "value": v.value,
                    "unit": v.unit,
                    "status": v.status
                }
                for k, v in self.indicators.items()
            },
            "active_alarms": len([a for a in self.alarms if not a["acknowledged"]]),
            "history_length": len(self.history)
        }

    def print_display(self) -> None:
        """打印仪表盘显示"""
        print(self.get_display())


class TestProgressMonitor:
    """测试进度监控器"""

    def __init__(self, total_tests: int):
        """初始化

        Args:
            total_tests: 总测试数
        """
        self.total_tests = total_tests
        self.completed_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.current_test: Optional[str] = None
        self.test_results: Dict[str, bool] = {}

    def start_test(self, test_name: str) -> None:
        """开始测试

        Args:
            test_name: 测试名称
        """
        self.current_test = test_name

    def complete_test(self, test_name: str, passed: bool) -> None:
        """完成测试

        Args:
            test_name: 测试名称
            passed: 是否通过
        """
        self.test_results[test_name] = passed
        self.completed_tests += 1
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
        self.current_test = None

    def get_progress(self) -> float:
        """获取进度百分比

        Returns:
            进度 (0-100)
        """
        if self.total_tests == 0:
            return 100.0
        return (self.completed_tests / self.total_tests) * 100

    def get_pass_rate(self) -> float:
        """获取通过率

        Returns:
            通过率 (0-1)
        """
        if self.completed_tests == 0:
            return 0.0
        return self.passed_tests / self.completed_tests

    def get_display(self) -> str:
        """获取进度显示

        Returns:
            进度文本
        """
        progress = self.get_progress()
        pass_rate = self.get_pass_rate()

        bar_width = 30
        filled = int(progress / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        lines = [
            "【测试进度】",
            f"  进度: [{bar}] {progress:.1f}%",
            f"  完成: {self.completed_tests}/{self.total_tests}",
            f"  通过: {self.passed_tests}  失败: {self.failed_tests}",
            f"  通过率: {pass_rate*100:.1f}%",
        ]

        if self.current_test:
            lines.append(f"  当前: {self.current_test}")

        return "\n".join(lines)
