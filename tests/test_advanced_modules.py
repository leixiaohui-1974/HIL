# -*- coding: utf-8 -*-
"""
高级模块单元测试
Unit Tests for Advanced Modules (Scenario Analysis & System Monitor)

测试覆盖:
1. 场景分析模块测试
2. 系统监控模块测试
"""

import sys
import os
import unittest
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.multi_energy.scenario_analysis import (
    ScenarioType,
    ScenarioDefinition,
    ScenarioResult,
    ComparisonReport,
    ScenarioLibrary,
    ScenarioRunner,
    ScenarioComparator
)

from src.multi_energy.system_monitor import (
    AlarmLevel,
    ComponentType,
    Alarm,
    ComponentStatus,
    SystemSnapshot,
    MonitoringConfig,
    SystemMonitor,
    PerformanceAnalyzer
)

from src.multi_energy.simulation import SimulationConfig, SimulationResult


# ==================== 场景分析模块测试 ====================

class TestScenarioType(unittest.TestCase):
    """场景类型枚举测试"""

    def test_scenario_types_exist(self):
        """测试场景类型存在"""
        self.assertEqual(ScenarioType.TYPICAL_DAY.value, 1)
        self.assertEqual(ScenarioType.HIGH_RENEWABLE.value, 2)
        self.assertEqual(ScenarioType.LOW_RENEWABLE.value, 3)
        self.assertEqual(ScenarioType.PEAK_LOAD.value, 4)

    def test_all_scenario_types(self):
        """测试所有场景类型"""
        types = list(ScenarioType)
        self.assertGreaterEqual(len(types), 6)


class TestScenarioLibrary(unittest.TestCase):
    """场景库测试"""

    def test_get_typical_day(self):
        """测试获取典型日场景"""
        scenario = ScenarioLibrary.get_typical_day()
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.name, "typical_day")
        self.assertEqual(scenario.scenario_type, ScenarioType.TYPICAL_DAY)
        self.assertIsInstance(scenario.config, SimulationConfig)

    def test_get_high_renewable(self):
        """测试获取高新能源场景"""
        scenario = ScenarioLibrary.get_high_renewable()
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.name, "high_renewable")
        # 高新能源场景应该有更大的装机容量
        self.assertGreater(scenario.config.wind_capacity, 50)

    def test_get_low_renewable(self):
        """测试获取低新能源场景"""
        scenario = ScenarioLibrary.get_low_renewable()
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.name, "low_renewable")

    def test_get_peak_load(self):
        """测试获取高负荷场景"""
        scenario = ScenarioLibrary.get_peak_load()
        self.assertIsNotNone(scenario)
        # 高负荷场景应该有更高的基础负荷
        self.assertGreater(scenario.config.base_load, 250)

    def test_get_all_scenarios(self):
        """测试获取所有场景"""
        scenarios = ScenarioLibrary.get_all_scenarios()
        self.assertGreaterEqual(len(scenarios), 6)
        # 验证每个场景都有名称和配置
        for scenario in scenarios:
            self.assertIsNotNone(scenario.name)
            self.assertIsNotNone(scenario.config)
            self.assertIsNotNone(scenario.description)


class TestScenarioDefinition(unittest.TestCase):
    """场景定义测试"""

    def test_create_custom_scenario(self):
        """测试创建自定义场景"""
        config = SimulationConfig(
            duration=3600.0,
            time_step=10.0,
            base_load=200.0
        )
        scenario = ScenarioDefinition(
            name="custom_test",
            description="测试用自定义场景",
            config=config,
            scenario_type=ScenarioType.TYPICAL_DAY,
            tags=["test", "custom"]
        )
        self.assertEqual(scenario.name, "custom_test")
        self.assertEqual(len(scenario.tags), 2)


class TestScenarioRunner(unittest.TestCase):
    """场景运行器测试"""

    def test_runner_initialization(self):
        """测试运行器初始化"""
        runner = ScenarioRunner(verbose=False)
        self.assertIsNotNone(runner)
        self.assertEqual(len(runner.results), 0)


class TestScenarioComparator(unittest.TestCase):
    """场景对比器测试"""

    def test_comparator_with_empty_results(self):
        """测试空结果对比"""
        comparator = ScenarioComparator([])
        report = comparator.compare()
        self.assertIsNotNone(report)
        self.assertEqual(len(report.scenarios), 0)

    def test_create_mock_scenario_result(self):
        """测试创建模拟场景结果"""
        time = np.linspace(0, 3600, 100)
        sim_result = SimulationResult(
            time=time,
            frequency=50.0 + 0.1 * np.sin(time / 100),
            wind_power=np.ones(100) * 20,
            solar_power=np.ones(100) * 15,
            hydro_power=np.ones(100) * 100,
            psh_power=np.zeros(100),
            sc_power=np.zeros(100),
            bess_power=np.zeros(100),
            load=np.ones(100) * 135,
            net_load=np.ones(100) * 100,
            sc_soc=np.ones(100) * 0.5,
            bess_soc=np.ones(100) * 0.6,
            psh_level=np.ones(100) * 0.5,
            psh_mode=['stopped'] * 100
        )

        scenario_result = ScenarioResult(
            scenario_name="test_scenario",
            simulation_result=sim_result,
            execution_time=1.0,
            metrics={'freq_dev_max': 0.1, 'freq_dev_rms': 0.05}
        )

        self.assertEqual(scenario_result.scenario_name, "test_scenario")
        self.assertEqual(scenario_result.metrics['freq_dev_max'], 0.1)


# ==================== 系统监控模块测试 ====================

class TestAlarmLevel(unittest.TestCase):
    """告警级别测试"""

    def test_alarm_levels(self):
        """测试告警级别枚举"""
        self.assertEqual(AlarmLevel.INFO.value, 1)
        self.assertEqual(AlarmLevel.WARNING.value, 2)
        self.assertEqual(AlarmLevel.CRITICAL.value, 3)
        self.assertEqual(AlarmLevel.EMERGENCY.value, 4)

    def test_alarm_level_comparison(self):
        """测试告警级别比较"""
        self.assertLess(AlarmLevel.INFO.value, AlarmLevel.WARNING.value)
        self.assertLess(AlarmLevel.WARNING.value, AlarmLevel.CRITICAL.value)
        self.assertLess(AlarmLevel.CRITICAL.value, AlarmLevel.EMERGENCY.value)


class TestComponentType(unittest.TestCase):
    """组件类型测试"""

    def test_component_types(self):
        """测试组件类型枚举"""
        types = list(ComponentType)
        self.assertGreater(len(types), 5)

    def test_component_type_values(self):
        """测试组件类型值"""
        self.assertEqual(ComponentType.WIND_TURBINE.value, "风电")
        self.assertEqual(ComponentType.SOLAR_PV.value, "光伏")
        self.assertEqual(ComponentType.BATTERY.value, "锂电池")


class TestAlarm(unittest.TestCase):
    """告警对象测试"""

    def test_create_alarm(self):
        """测试创建告警"""
        alarm = Alarm(
            timestamp=100.0,
            level=AlarmLevel.WARNING,
            component=ComponentType.GRID,
            message="频率偏差超限",
            value=0.3,
            threshold=0.2
        )
        self.assertEqual(alarm.level, AlarmLevel.WARNING)
        self.assertEqual(alarm.component, ComponentType.GRID)
        self.assertEqual(alarm.value, 0.3)
        self.assertEqual(alarm.timestamp, 100.0)

    def test_alarm_severity(self):
        """测试告警严重程度"""
        info_alarm = Alarm(
            timestamp=0.0,
            level=AlarmLevel.INFO,
            component=ComponentType.BATTERY,
            message="SOC正常",
            value=0.5,
            threshold=0.2
        )
        critical_alarm = Alarm(
            timestamp=0.0,
            level=AlarmLevel.CRITICAL,
            component=ComponentType.GRID,
            message="频率严重偏差",
            value=1.0,
            threshold=0.5
        )
        self.assertLess(info_alarm.level.value, critical_alarm.level.value)


class TestComponentStatus(unittest.TestCase):
    """组件状态测试"""

    def test_create_component_status(self):
        """测试创建组件状态"""
        status = ComponentStatus(
            component_type=ComponentType.HYDRO,
            name="常规水电",
            power=150.0,
            status="normal",
            soc=None,
            efficiency=0.92,
            available=True
        )
        self.assertTrue(status.available)
        self.assertEqual(status.power, 150.0)
        self.assertEqual(status.efficiency, 0.92)


class TestMonitoringConfig(unittest.TestCase):
    """监控配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = MonitoringConfig()
        self.assertGreater(config.freq_warning_threshold, 0)
        self.assertGreater(config.freq_critical_threshold,
                          config.freq_warning_threshold)

    def test_custom_config(self):
        """测试自定义配置"""
        config = MonitoringConfig(
            freq_warning_threshold=0.3,
            freq_critical_threshold=0.6,
            soc_low_warning=0.15,
            soc_high_warning=0.90
        )
        self.assertEqual(config.freq_warning_threshold, 0.3)
        self.assertEqual(config.soc_low_warning, 0.15)


class TestSystemMonitor(unittest.TestCase):
    """系统监控器测试"""

    def setUp(self):
        self.config = MonitoringConfig()
        self.monitor = SystemMonitor(self.config)

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.monitor)

    def test_register_component(self):
        """测试注册组件"""
        self.monitor.register_component(ComponentType.HYDRO, "水电站1")
        # 验证注册成功
        self.assertIn("水电站1", self.monitor._component_status)

    def test_update_grid_normal(self):
        """测试正常电网状态更新"""
        self.monitor.update_grid(
            timestamp=100.0,
            frequency=50.0,
            total_generation=200.0,
            total_load=195.0
        )
        snapshot = self.monitor.get_system_snapshot()
        self.assertEqual(snapshot.frequency, 50.0)
        self.assertEqual(snapshot.total_generation, 200.0)

    def test_update_grid_frequency_warning(self):
        """测试频率告警"""
        # 设置较大的频率偏差
        self.monitor.update_grid(
            timestamp=100.0,
            frequency=50.6,  # 偏差0.6Hz > warning阈值0.5Hz
            total_generation=200.0,
            total_load=195.0
        )
        alarms = self.monitor.get_alarms()
        # 应该有告警
        self.assertGreater(len(alarms), 0)

    def test_update_component_soc(self):
        """测试组件SOC更新"""
        self.monitor.register_component(ComponentType.BATTERY, "锂电池1")
        self.monitor.update_component(
            name="锂电池1",
            power=10.0,
            status="normal",
            soc=0.5,
            efficiency=0.95
        )
        # 验证更新成功
        status = self.monitor._component_status.get("锂电池1")
        self.assertIsNotNone(status)
        self.assertEqual(status.soc, 0.5)

    def test_low_soc_alarm(self):
        """测试低SOC告警"""
        self.monitor.register_component(ComponentType.BATTERY, "锂电池1")
        self.monitor.update_component(
            name="锂电池1",
            power=10.0,
            status="normal",
            soc=0.03,  # 低于critical阈值0.05
            efficiency=0.95
        )
        alarms = self.monitor.get_alarms()
        # 应该有SOC相关告警
        battery_alarms = [a for a in alarms if a.component == ComponentType.BATTERY]
        self.assertGreater(len(battery_alarms), 0)

    def test_get_system_snapshot(self):
        """测试获取系统快照"""
        self.monitor.update_grid(
            timestamp=100.0,
            frequency=50.1,
            total_generation=200.0,
            total_load=195.0
        )
        snapshot = self.monitor.get_system_snapshot()
        self.assertIsInstance(snapshot, SystemSnapshot)
        self.assertEqual(snapshot.timestamp, 100.0)

    def test_get_statistics(self):
        """测试获取统计信息"""
        # 添加多个样本
        for i in range(100):
            self.monitor.update_grid(
                timestamp=float(i),
                frequency=50.0 + 0.1 * np.sin(i / 10),
                total_generation=200.0,
                total_load=195.0
            )
        stats = self.monitor.get_statistics()
        self.assertIn('freq_dev_max', stats)
        self.assertIn('freq_dev_rms', stats)

    def test_generate_health_report(self):
        """测试生成健康报告"""
        self.monitor.update_grid(
            timestamp=100.0,
            frequency=50.1,
            total_generation=200.0,
            total_load=195.0
        )
        report = self.monitor.generate_health_report()
        self.assertIsInstance(report, str)
        self.assertIn("系统健康状态报告", report)

    def test_reset(self):
        """测试重置"""
        self.monitor.update_grid(
            timestamp=100.0,
            frequency=50.6,
            total_generation=200.0,
            total_load=195.0
        )
        self.monitor.reset()
        self.assertEqual(len(self.monitor._alarms), 0)


class TestPerformanceAnalyzer(unittest.TestCase):
    """性能分析器测试"""

    def setUp(self):
        self.analyzer = PerformanceAnalyzer()

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNotNone(self.analyzer)

    def test_add_sample(self):
        """测试添加样本"""
        self.analyzer.add_sample(
            timestamp=0.0,
            frequency=50.0,
            generation=200.0,
            load=195.0
        )
        self.assertEqual(len(self.analyzer._data['time']), 1)

    def test_analyze_insufficient_data(self):
        """测试数据不足时的分析"""
        # 只添加少量样本
        for i in range(5):
            self.analyzer.add_sample(
                timestamp=float(i),
                frequency=50.0,
                generation=200.0,
                load=195.0
            )
        result = self.analyzer.analyze()
        # 数据不足应返回空
        self.assertEqual(len(result), 0)

    def test_analyze_sufficient_data(self):
        """测试充足数据时的分析"""
        # 添加足够样本
        for i in range(100):
            self.analyzer.add_sample(
                timestamp=float(i),
                frequency=50.0 + 0.1 * np.sin(i / 10),
                generation=200.0 + 10 * np.sin(i / 20),
                load=195.0
            )
        result = self.analyzer.analyze()
        self.assertIn('freq_dev_max', result)
        self.assertIn('freq_dev_rms', result)
        self.assertIn('gen_mean', result)
        self.assertIn('load_mean', result)

    def test_get_time_series(self):
        """测试获取时间序列"""
        for i in range(10):
            self.analyzer.add_sample(
                timestamp=float(i),
                frequency=50.0,
                generation=200.0,
                load=195.0
            )
        ts = self.analyzer.get_time_series()
        self.assertIn('time', ts)
        self.assertIn('frequency', ts)
        self.assertEqual(len(ts['time']), 10)

    def test_reset(self):
        """测试重置"""
        for i in range(10):
            self.analyzer.add_sample(
                timestamp=float(i),
                frequency=50.0,
                generation=200.0,
                load=195.0
            )
        self.analyzer.reset()
        self.assertEqual(len(self.analyzer._data['time']), 0)


# ==================== 集成测试 ====================

class TestMonitorIntegration(unittest.TestCase):
    """监控器集成测试"""

    def test_full_monitoring_cycle(self):
        """测试完整监控周期"""
        config = MonitoringConfig()
        monitor = SystemMonitor(config)
        analyzer = PerformanceAnalyzer()

        # 注册组件
        monitor.register_component(ComponentType.BATTERY, "BESS")
        monitor.register_component(ComponentType.HYDRO, "水电站")

        # 模拟24小时运行(每小时一个样本)
        for hour in range(24):
            # 模拟频率变化
            freq = 50.0 + 0.1 * np.sin(hour * np.pi / 12)
            generation = 200.0 + 20 * np.sin(hour * np.pi / 12)
            load = 195.0

            monitor.update_grid(
                timestamp=hour * 3600.0,
                frequency=freq,
                total_generation=generation,
                total_load=load
            )

            # 模拟储能SOC变化
            bess_soc = 0.5 + 0.3 * np.sin(hour * np.pi / 12)
            monitor.update_component(
                name="BESS",
                power=10.0,
                soc=np.clip(bess_soc, 0.1, 0.9)
            )

            # 添加性能样本
            analyzer.add_sample(
                timestamp=hour * 3600.0,
                frequency=freq,
                generation=generation,
                load=load
            )

        # 验证分析结果
        stats = analyzer.analyze()
        self.assertIn('freq_dev_max', stats)
        self.assertIn('freq_dev_rms', stats)

        # 获取最终快照
        snapshot = monitor.get_system_snapshot()
        self.assertIsNotNone(snapshot)

        # 获取健康报告
        report = monitor.generate_health_report()
        self.assertIn("系统健康状态报告", report)


if __name__ == '__main__':
    unittest.main()
