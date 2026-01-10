# -*- coding: utf-8 -*-
"""
系统健康监测模块
System Health Monitoring Module

本模块提供:
1. 实时系统状态监测
2. 告警检测与记录
3. 性能指标统计
4. 运行日志生成
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum, auto
from collections import deque
from datetime import datetime


class AlarmLevel(Enum):
    """告警级别"""
    INFO = auto()       # 信息
    WARNING = auto()    # 警告
    CRITICAL = auto()   # 严重
    EMERGENCY = auto()  # 紧急


class ComponentType(Enum):
    """组件类型"""
    WIND_TURBINE = "风电"
    SOLAR_PV = "光伏"
    SUPERCAPACITOR = "超级电容"
    BATTERY = "锂电池"
    PSH = "抽水蓄能"
    HYDRO = "常规水电"
    GRID = "电网"


@dataclass
class Alarm:
    """告警记录"""
    timestamp: float                # 时间戳
    level: AlarmLevel              # 告警级别
    component: ComponentType       # 组件类型
    message: str                   # 告警信息
    value: float = 0.0             # 相关数值
    threshold: float = 0.0         # 阈值


@dataclass
class ComponentStatus:
    """组件状态"""
    component_type: ComponentType
    name: str
    power: float = 0.0
    status: str = "normal"
    soc: Optional[float] = None    # 储能SOC
    efficiency: float = 1.0
    available: bool = True
    last_update: float = 0.0


@dataclass
class SystemSnapshot:
    """系统快照"""
    timestamp: float
    frequency: float
    frequency_deviation: float
    total_generation: float
    total_load: float
    power_imbalance: float
    components: List[ComponentStatus]
    active_alarms: List[Alarm]


@dataclass
class MonitoringConfig:
    """监测配置"""
    # 频率阈值
    freq_warning_threshold: float = 0.5     # Hz
    freq_critical_threshold: float = 1.0    # Hz
    freq_emergency_threshold: float = 2.0   # Hz

    # SOC阈值
    soc_low_warning: float = 0.15           # 15%
    soc_low_critical: float = 0.05          # 5%
    soc_high_warning: float = 0.95          # 95%

    # 功率阈值
    power_imbalance_warning: float = 0.05   # 5% of base power
    power_imbalance_critical: float = 0.10  # 10%

    # 历史记录长度
    history_length: int = 1000


class SystemMonitor:
    """
    系统健康监测器

    实时监测多能互补系统的运行状态
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()

        # 组件状态
        self._component_status: Dict[str, ComponentStatus] = {}

        # 告警历史
        self._alarms: List[Alarm] = []
        self._active_alarms: List[Alarm] = []

        # 性能历史
        self._frequency_history: deque = deque(maxlen=self.config.history_length)
        self._power_history: deque = deque(maxlen=self.config.history_length)

        # 统计信息
        self._statistics: Dict[str, float] = {}

        # 当前时间
        self._current_time: float = 0.0

    def register_component(
        self,
        component_type: ComponentType,
        name: str
    ) -> None:
        """注册组件"""
        self._component_status[name] = ComponentStatus(
            component_type=component_type,
            name=name
        )

    def update_component(
        self,
        name: str,
        power: float,
        status: str = "normal",
        soc: Optional[float] = None,
        efficiency: float = 1.0,
        available: bool = True
    ) -> None:
        """更新组件状态"""
        if name not in self._component_status:
            return

        cs = self._component_status[name]
        cs.power = power
        cs.status = status
        cs.soc = soc
        cs.efficiency = efficiency
        cs.available = available
        cs.last_update = self._current_time

        # 检查SOC告警
        if soc is not None:
            self._check_soc_alarm(name, cs.component_type, soc)

    def update_grid(
        self,
        timestamp: float,
        frequency: float,
        total_generation: float,
        total_load: float
    ) -> None:
        """更新电网状态"""
        self._current_time = timestamp
        freq_dev = frequency - 50.0
        power_imbalance = total_generation - total_load

        # 记录历史
        self._frequency_history.append((timestamp, frequency, freq_dev))
        self._power_history.append((timestamp, total_generation, total_load, power_imbalance))

        # 检查频率告警
        self._check_frequency_alarm(freq_dev)

        # 检查功率平衡告警
        self._check_power_balance_alarm(power_imbalance, total_load)

        # 更新统计
        self._update_statistics()

    def _check_frequency_alarm(self, freq_dev: float) -> None:
        """检查频率告警"""
        abs_dev = abs(freq_dev)

        if abs_dev > self.config.freq_emergency_threshold:
            self._add_alarm(
                AlarmLevel.EMERGENCY,
                ComponentType.GRID,
                f"频率严重偏离: {freq_dev:+.3f} Hz",
                freq_dev,
                self.config.freq_emergency_threshold
            )
        elif abs_dev > self.config.freq_critical_threshold:
            self._add_alarm(
                AlarmLevel.CRITICAL,
                ComponentType.GRID,
                f"频率大幅偏离: {freq_dev:+.3f} Hz",
                freq_dev,
                self.config.freq_critical_threshold
            )
        elif abs_dev > self.config.freq_warning_threshold:
            self._add_alarm(
                AlarmLevel.WARNING,
                ComponentType.GRID,
                f"频率偏离警告: {freq_dev:+.3f} Hz",
                freq_dev,
                self.config.freq_warning_threshold
            )

    def _check_soc_alarm(
        self,
        name: str,
        component_type: ComponentType,
        soc: float
    ) -> None:
        """检查SOC告警"""
        if soc < self.config.soc_low_critical:
            self._add_alarm(
                AlarmLevel.CRITICAL,
                component_type,
                f"{name} SOC过低: {soc*100:.1f}%",
                soc,
                self.config.soc_low_critical
            )
        elif soc < self.config.soc_low_warning:
            self._add_alarm(
                AlarmLevel.WARNING,
                component_type,
                f"{name} SOC偏低: {soc*100:.1f}%",
                soc,
                self.config.soc_low_warning
            )
        elif soc > self.config.soc_high_warning:
            self._add_alarm(
                AlarmLevel.WARNING,
                component_type,
                f"{name} SOC过高: {soc*100:.1f}%",
                soc,
                self.config.soc_high_warning
            )

    def _check_power_balance_alarm(
        self,
        power_imbalance: float,
        base_power: float
    ) -> None:
        """检查功率平衡告警"""
        if base_power < 1:
            return

        imbalance_ratio = abs(power_imbalance) / base_power

        if imbalance_ratio > self.config.power_imbalance_critical:
            self._add_alarm(
                AlarmLevel.CRITICAL,
                ComponentType.GRID,
                f"功率严重不平衡: {power_imbalance:+.1f} MW ({imbalance_ratio*100:.1f}%)",
                power_imbalance,
                self.config.power_imbalance_critical * base_power
            )
        elif imbalance_ratio > self.config.power_imbalance_warning:
            self._add_alarm(
                AlarmLevel.WARNING,
                ComponentType.GRID,
                f"功率不平衡警告: {power_imbalance:+.1f} MW",
                power_imbalance,
                self.config.power_imbalance_warning * base_power
            )

    def _add_alarm(
        self,
        level: AlarmLevel,
        component: ComponentType,
        message: str,
        value: float,
        threshold: float
    ) -> None:
        """添加告警"""
        alarm = Alarm(
            timestamp=self._current_time,
            level=level,
            component=component,
            message=message,
            value=value,
            threshold=threshold
        )

        self._alarms.append(alarm)

        # 更新活动告警(保留最近的同类告警)
        self._active_alarms = [a for a in self._active_alarms
                              if not (a.component == component and a.level == level)]
        self._active_alarms.append(alarm)

    def _update_statistics(self) -> None:
        """更新统计信息"""
        if len(self._frequency_history) < 2:
            return

        freq_devs = [h[2] for h in self._frequency_history]
        freq_array = np.array(freq_devs)

        self._statistics = {
            'freq_dev_max': np.max(np.abs(freq_array)),
            'freq_dev_rms': np.sqrt(np.mean(freq_array ** 2)),
            'freq_dev_mean': np.mean(freq_array),
            'freq_dev_std': np.std(freq_array),
            'freq_normal_ratio': np.sum(np.abs(freq_array) < 0.5) / len(freq_array) * 100,
            'total_alarms': len(self._alarms),
            'active_alarms': len(self._active_alarms)
        }

    def get_system_snapshot(self) -> SystemSnapshot:
        """获取系统快照"""
        if not self._frequency_history:
            freq = 50.0
            freq_dev = 0.0
        else:
            freq = self._frequency_history[-1][1]
            freq_dev = self._frequency_history[-1][2]

        if not self._power_history:
            total_gen = 0.0
            total_load = 0.0
            power_imbalance = 0.0
        else:
            total_gen = self._power_history[-1][1]
            total_load = self._power_history[-1][2]
            power_imbalance = self._power_history[-1][3]

        return SystemSnapshot(
            timestamp=self._current_time,
            frequency=freq,
            frequency_deviation=freq_dev,
            total_generation=total_gen,
            total_load=total_load,
            power_imbalance=power_imbalance,
            components=list(self._component_status.values()),
            active_alarms=self._active_alarms.copy()
        )

    def get_statistics(self) -> Dict[str, float]:
        """获取统计信息"""
        return self._statistics.copy()

    def get_alarms(
        self,
        level: Optional[AlarmLevel] = None,
        component: Optional[ComponentType] = None,
        limit: int = 100
    ) -> List[Alarm]:
        """
        获取告警记录

        Args:
            level: 告警级别过滤
            component: 组件类型过滤
            limit: 返回数量限制

        Returns:
            告警列表
        """
        alarms = self._alarms

        if level is not None:
            alarms = [a for a in alarms if a.level == level]

        if component is not None:
            alarms = [a for a in alarms if a.component == component]

        return alarms[-limit:]

    def generate_health_report(self) -> str:
        """生成健康报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("系统健康状态报告")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)

        # 系统概况
        snapshot = self.get_system_snapshot()
        lines.append("\n1. 系统概况")
        lines.append("-" * 40)
        lines.append(f"  当前频率: {snapshot.frequency:.4f} Hz")
        lines.append(f"  频率偏差: {snapshot.frequency_deviation:+.4f} Hz")
        lines.append(f"  总发电: {snapshot.total_generation:.1f} MW")
        lines.append(f"  总负荷: {snapshot.total_load:.1f} MW")
        lines.append(f"  功率平衡: {snapshot.power_imbalance:+.1f} MW")

        # 性能统计
        stats = self.get_statistics()
        if stats:
            lines.append("\n2. 性能统计")
            lines.append("-" * 40)
            lines.append(f"  频率偏差最大: {stats.get('freq_dev_max', 0):.4f} Hz")
            lines.append(f"  频率偏差RMS: {stats.get('freq_dev_rms', 0):.4f} Hz")
            lines.append(f"  频率正常占比: {stats.get('freq_normal_ratio', 0):.1f}%")

        # 组件状态
        lines.append("\n3. 组件状态")
        lines.append("-" * 40)
        for cs in snapshot.components:
            status_icon = "OK" if cs.status == "normal" and cs.available else "!!"
            soc_str = f", SOC:{cs.soc*100:.1f}%" if cs.soc is not None else ""
            lines.append(f"  [{status_icon}] {cs.name}: {cs.power:.1f}MW{soc_str}")

        # 告警统计
        lines.append("\n4. 告警统计")
        lines.append("-" * 40)
        lines.append(f"  总告警数: {len(self._alarms)}")
        lines.append(f"  活动告警: {len(self._active_alarms)}")

        # 按级别统计
        for level in AlarmLevel:
            count = len([a for a in self._alarms if a.level == level])
            if count > 0:
                lines.append(f"    {level.name}: {count}")

        # 最近告警
        recent_alarms = self._alarms[-5:] if self._alarms else []
        if recent_alarms:
            lines.append("\n5. 最近告警")
            lines.append("-" * 40)
            for alarm in reversed(recent_alarms):
                lines.append(f"  [{alarm.level.name}] {alarm.message}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    def print_status(self) -> None:
        """打印当前状态"""
        snapshot = self.get_system_snapshot()

        # 状态颜色(文本模式)
        if abs(snapshot.frequency_deviation) < 0.2:
            freq_status = "[OK]"
        elif abs(snapshot.frequency_deviation) < 0.5:
            freq_status = "[!!]"
        else:
            freq_status = "[XX]"

        print(f"\n{freq_status} 频率: {snapshot.frequency:.3f}Hz "
              f"(偏差: {snapshot.frequency_deviation:+.3f}Hz)")
        print(f"    发电: {snapshot.total_generation:.1f}MW | "
              f"负荷: {snapshot.total_load:.1f}MW | "
              f"平衡: {snapshot.power_imbalance:+.1f}MW")

        if self._active_alarms:
            print(f"    活动告警: {len(self._active_alarms)}个")

    def reset(self) -> None:
        """重置监测器"""
        self._component_status.clear()
        self._alarms.clear()
        self._active_alarms.clear()
        self._frequency_history.clear()
        self._power_history.clear()
        self._statistics.clear()
        self._current_time = 0.0


class PerformanceAnalyzer:
    """
    性能分析器

    分析系统长期运行性能
    """

    def __init__(self):
        self._data: Dict[str, List[float]] = {
            'time': [],
            'frequency': [],
            'generation': [],
            'load': []
        }

    def add_sample(
        self,
        timestamp: float,
        frequency: float,
        generation: float,
        load: float
    ) -> None:
        """添加采样数据"""
        self._data['time'].append(timestamp)
        self._data['frequency'].append(frequency)
        self._data['generation'].append(generation)
        self._data['load'].append(load)

    def analyze(self) -> Dict[str, float]:
        """执行性能分析"""
        if len(self._data['time']) < 10:
            return {}

        freq_array = np.array(self._data['frequency'])
        freq_dev = freq_array - 50.0
        gen_array = np.array(self._data['generation'])
        load_array = np.array(self._data['load'])

        return {
            # 频率指标
            'freq_dev_max': np.max(np.abs(freq_dev)),
            'freq_dev_min': np.min(freq_dev),
            'freq_dev_rms': np.sqrt(np.mean(freq_dev ** 2)),
            'freq_dev_std': np.std(freq_dev),
            'freq_normal_time_ratio': np.sum(np.abs(freq_dev) < 0.5) / len(freq_dev),

            # 功率指标
            'gen_mean': np.mean(gen_array),
            'gen_max': np.max(gen_array),
            'gen_min': np.min(gen_array),
            'load_mean': np.mean(load_array),
            'load_max': np.max(load_array),
            'load_min': np.min(load_array),

            # 跟踪能力
            'power_balance_mean': np.mean(gen_array - load_array),
            'power_balance_std': np.std(gen_array - load_array)
        }

    def get_time_series(self) -> Dict[str, np.ndarray]:
        """获取时间序列数据"""
        return {k: np.array(v) for k, v in self._data.items()}

    def reset(self) -> None:
        """重置分析器"""
        for key in self._data:
            self._data[key] = []
