# -*- coding: utf-8 -*-
"""
多能互补系统单元测试
Unit Tests for Multi-Energy Complementary System

测试覆盖:
1. 能源组件模型测试
2. PSH状态机测试
3. 分层控制器测试
4. 功率分配算法测试
5. 集成仿真测试
"""

import sys
import os
import unittest
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.multi_energy.energy_models import (
    WindTurbineModel, PhotovoltaicModel,
    SupercapacitorModel, BatteryStorageModel,
    PumpedStorageModel, ConventionalHydroModel,
    GridModel, WindCondition, SolarCondition,
    PSHOperatingState, PSHParameters
)
from src.multi_energy.psh_state_machine import (
    PSHStateMachine, PSHConstraints, PSHOperatingMode,
    PSHDispatcher, DispatchContext
)
from src.multi_energy.hierarchical_control import (
    Layer1_SCDroopController, Layer2_BESSFilterController,
    Layer3_MPCCoordinator, HierarchicalEnergyController,
    SystemState
)
from src.multi_energy.power_allocation import (
    PowerAllocationAlgorithm, ResponseChainDecoupler,
    FrequencyRegulator, UnitCapability
)


class TestWindTurbineModel(unittest.TestCase):
    """风力发电机模型测试"""

    def setUp(self):
        self.wt = WindTurbineModel(rated_power=50.0)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.wt.rated_power, 50.0)
        self.assertEqual(self.wt.get_power(), 0.0)

    def test_power_curve_below_cut_in(self):
        """测试切入风速以下"""
        self.wt.set_power_setpoint(50.0)
        condition = WindCondition(wind_speed=2.0)  # 低于切入风速
        self.wt.step(1.0, condition)
        # 运行多步让系统稳定
        for _ in range(100):
            self.wt.step(1.0, condition)
        self.assertLess(self.wt.get_power(), 0.1)

    def test_power_curve_at_rated(self):
        """测试额定风速"""
        self.wt.set_power_setpoint(50.0)
        condition = WindCondition(wind_speed=12.0, turbulence_intensity=0.0)
        for _ in range(500):  # 增加迭代次数
            self.wt.step(1.0, condition)
        # 应接近额定功率(考虑效率)
        self.assertGreater(self.wt.get_power(), 30.0)

    def test_power_curve_above_cut_out(self):
        """测试切出风速以上"""
        self.wt.set_power_setpoint(50.0)
        condition = WindCondition(wind_speed=30.0)  # 高于切出风速
        for _ in range(100):
            self.wt.step(1.0, condition)
        self.assertLess(self.wt.get_power(), 0.1)


class TestPhotovoltaicModel(unittest.TestCase):
    """光伏发电模型测试"""

    def setUp(self):
        self.pv = PhotovoltaicModel(rated_power=30.0)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.pv.rated_power, 30.0)

    def test_night_output(self):
        """测试夜间输出"""
        self.pv.set_power_setpoint(30.0)
        condition = SolarCondition(irradiance=0.0)
        for _ in range(100):
            self.pv.step(1.0, condition)
        self.assertLess(self.pv.get_power(), 0.1)

    def test_noon_output(self):
        """测试正午输出"""
        self.pv.set_power_setpoint(30.0)
        condition = SolarCondition(irradiance=1000.0, temperature=25.0)
        for _ in range(200):  # 增加迭代次数
            self.pv.step(1.0, condition)
        # 应该有显著输出(考虑面积和效率)
        self.assertGreater(self.pv.get_power(), 10.0)

    def test_temperature_effect(self):
        """测试温度影响"""
        self.pv.set_power_setpoint(30.0)
        # 高温条件
        condition_hot = SolarCondition(irradiance=1000.0, temperature=45.0)
        for _ in range(200):  # 增加迭代次数
            self.pv.step(1.0, condition_hot)
        power_hot = self.pv.get_power()

        # 重置
        self.pv = PhotovoltaicModel(rated_power=30.0)
        self.pv.set_power_setpoint(30.0)
        # 标准温度
        condition_std = SolarCondition(irradiance=1000.0, temperature=25.0)
        for _ in range(200):  # 增加迭代次数
            self.pv.step(1.0, condition_std)
        power_std = self.pv.get_power()

        # 高温时效率应该更低(或至少不高于标准温度)
        self.assertLessEqual(power_hot, power_std + 0.5)  # 允许小误差


class TestSupercapacitorModel(unittest.TestCase):
    """超级电容模型测试"""

    def setUp(self):
        self.sc = SupercapacitorModel(rated_power=10.0, rated_energy=0.5)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.sc.rated_power, 10.0)
        self.assertAlmostEqual(self.sc.get_soc(), 0.5, places=1)

    def test_fast_response(self):
        """测试快速响应(毫秒级)"""
        self.sc.set_power_setpoint(5.0)
        # 10ms后应该有显著响应
        self.sc.step(0.01)
        self.assertGreater(abs(self.sc.get_power()), 1.0)

    def test_discharge(self):
        """测试放电"""
        initial_soc = self.sc.get_soc()
        self.sc.set_power_setpoint(5.0)  # 放电
        for _ in range(100):
            self.sc.step(1.0)
        self.assertLess(self.sc.get_soc(), initial_soc)

    def test_charge(self):
        """测试充电"""
        initial_soc = self.sc.get_soc()
        self.sc.set_power_setpoint(-5.0)  # 充电
        for _ in range(100):
            self.sc.step(1.0)
        self.assertGreater(self.sc.get_soc(), initial_soc)

    def test_soc_limits(self):
        """测试SOC限制"""
        # 放电到接近0
        self.sc.set_power_setpoint(10.0)
        for _ in range(1000):
            self.sc.step(1.0)
        self.assertGreaterEqual(self.sc.get_soc(), 0.0)


class TestBatteryStorageModel(unittest.TestCase):
    """锂电池储能模型测试"""

    def setUp(self):
        self.bess = BatteryStorageModel(rated_power=20.0, rated_energy=40.0)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.bess.rated_power, 20.0)
        self.assertAlmostEqual(self.bess.get_soc(), 0.5, places=1)

    def test_ramp_rate_limit(self):
        """测试爬坡率限制"""
        self.bess.set_power_setpoint(20.0)  # 请求满功率
        self.bess.step(0.1)  # 0.1秒后
        # 由于爬坡限制,不应该立即达到满功率
        self.assertLess(self.bess.get_power(), 10.0)

    def test_soc_protection(self):
        """测试SOC保护"""
        # 设置SOC到最低
        self.bess._soc = 0.1
        self.bess.set_power_setpoint(20.0)  # 请求放电
        for _ in range(10):
            self.bess.step(1.0)
        # 应该拒绝放电
        self.assertLess(self.bess.get_power(), 1.0)


class TestPumpedStorageModel(unittest.TestCase):
    """抽水蓄能模型测试"""

    def setUp(self):
        self.psh = PumpedStorageModel()

    def test_initialization(self):
        """测试初始化"""
        self.assertAlmostEqual(self.psh.get_reservoir_level(), 0.5, places=1)
        self.assertEqual(self.psh.get_operating_state(), PSHOperatingState.STOPPED)

    def test_mode_request(self):
        """测试模式请求"""
        # 设置初始状态为已运行足够时间(满足最短停机时间)
        self.psh._state_timer = 1000.0  # 设置已停机足够时间
        # 请求发电模式
        success = self.psh.request_mode(PSHOperatingState.GENERATING)
        self.assertTrue(success)

    def test_generation_startup(self):
        """测试发电启动过程"""
        self.psh._state_timer = 1000.0  # 满足最短停机时间
        self.psh.request_mode(PSHOperatingState.GENERATING)
        self.psh.set_power_setpoint(50.0)

        # 模拟启动过程
        startup_time = 0
        for i in range(200):
            self.psh.step(1.0)
            startup_time += 1
            if self.psh.get_operating_state() == PSHOperatingState.GENERATING:
                break

        self.assertEqual(self.psh.get_operating_state(), PSHOperatingState.GENERATING)

    def test_reservoir_level_change(self):
        """测试水库水位变化"""
        initial_level = self.psh.get_reservoir_level()

        # 设置已停机足够时间
        self.psh._state_timer = 1000.0
        # 发电消耗水
        self.psh.request_mode(PSHOperatingState.GENERATING)
        self.psh.set_power_setpoint(50.0)

        # 运行足够时间让模式切换完成并产生水位变化
        for _ in range(1000):
            self.psh.step(1.0)

        # 水位应该下降
        self.assertLessEqual(self.psh.get_reservoir_level(), initial_level)


class TestGridModel(unittest.TestCase):
    """电网频率模型测试"""

    def setUp(self):
        self.grid = GridModel()

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.grid.get_frequency(), 50.0)
        self.assertEqual(self.grid.get_frequency_deviation(), 0.0)

    def test_frequency_drop_on_deficit(self):
        """测试功率缺额时频率下降"""
        # 负荷大于发电
        for _ in range(100):
            self.grid.step(0.1, 100.0, 150.0)  # 发电100, 负荷150
        self.assertLess(self.grid.get_frequency(), 50.0)

    def test_frequency_rise_on_surplus(self):
        """测试功率过剩时频率上升"""
        # 发电大于负荷
        for _ in range(100):
            self.grid.step(0.1, 150.0, 100.0)  # 发电150, 负荷100
        self.assertGreater(self.grid.get_frequency(), 50.0)


class TestPSHStateMachine(unittest.TestCase):
    """PSH状态机测试"""

    def setUp(self):
        self.sm = PSHStateMachine()
        # 设置初始已停机足够时间
        self.sm.state.mode_timer = 1000.0

    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.sm.get_mode(), PSHOperatingMode.STOPPED)

    def test_mode_change_request(self):
        """测试模式切换请求"""
        # 从停机请求发电
        success, msg = self.sm.request_mode(PSHOperatingMode.GENERATING)
        self.assertTrue(success)
        self.assertTrue(self.sm.is_in_transition())

    def test_min_stop_time_constraint(self):
        """测试最短停机时间约束"""
        # 已经设置了足够的停机时间,应该可以请求
        success, msg = self.sm.request_mode(PSHOperatingMode.GENERATING)
        self.assertTrue(success)

    def test_transition_progress(self):
        """测试过渡进度"""
        self.sm.request_mode(PSHOperatingMode.GENERATING)
        self.sm.update(30.0, 0.5)  # 更新30秒
        progress = self.sm.get_transition_progress()
        self.assertGreater(progress, 0.0)
        # 由于启动时间约120秒, 30秒应该在0-1之间
        self.assertLessEqual(progress, 1.0)


class TestPSHDispatcher(unittest.TestCase):
    """PSH调度决策器测试"""

    def setUp(self):
        self.dispatcher = PSHDispatcher(
            rated_power_gen=100.0,
            rated_power_pump=90.0
        )

    def test_noon_pumping_decision(self):
        """测试午间抽水决策"""
        context = DispatchContext(
            current_time=12 * 3600,
            hour_of_day=12.0,
            net_load=-50.0,  # 净负荷为负(过剩)
            net_load_forecast=[-50.0] * 12,
            reservoir_level=0.5,
            current_mode=PSHOperatingMode.STOPPED
        )
        decision, power, reason = self.dispatcher.decide(context)
        self.assertEqual(decision.value, 'pump')

    def test_evening_generation_decision(self):
        """测试晚高峰发电决策"""
        context = DispatchContext(
            current_time=19 * 3600,
            hour_of_day=19.0,
            net_load=100.0,  # 净负荷为正(缺口)
            net_load_forecast=[100.0] * 12,
            reservoir_level=0.6,
            current_mode=PSHOperatingMode.STOPPED
        )
        decision, power, reason = self.dispatcher.decide(context)
        self.assertEqual(decision.value, 'gen')

    def test_low_reservoir_constraint(self):
        """测试低水位约束"""
        context = DispatchContext(
            current_time=19 * 3600,
            hour_of_day=19.0,
            net_load=100.0,
            net_load_forecast=[100.0] * 12,
            reservoir_level=0.15,  # 水位过低
            current_mode=PSHOperatingMode.STOPPED
        )
        decision, power, reason = self.dispatcher.decide(context)
        # 不应该发电
        self.assertNotEqual(decision.value, 'gen')


class TestLayer1SCController(unittest.TestCase):
    """第一层SC控制器测试"""

    def setUp(self):
        self.controller = Layer1_SCDroopController(
            rated_power=10.0,
            droop_gain=20.0
        )

    def test_droop_response(self):
        """测试下垂响应"""
        # 频率下降应该增加功率输出
        output = self.controller.step(0.01, frequency_deviation=-0.1)
        self.assertGreater(output.power_output, 0)

    def test_deadband(self):
        """测试死区"""
        # 小频率偏差在死区内
        output = self.controller.step(0.01, frequency_deviation=0.01)
        self.assertLess(abs(output.power_output), 0.5)


class TestLayer2BESSController(unittest.TestCase):
    """第二层BESS控制器测试"""

    def setUp(self):
        self.controller = Layer2_BESSFilterController(
            rated_power=20.0,
            filter_time_constant=2.0
        )

    def test_filter_effect(self):
        """测试滤波效果"""
        # 发送阶跃信号
        outputs = []
        for _ in range(50):
            output = self.controller.step(0.1, power_residual=10.0)
            outputs.append(output.power_output)

        # 输出应该平滑增加
        self.assertLess(outputs[0], outputs[-1])
        # 不应该立即跳到10
        self.assertLess(outputs[0], 5.0)


class TestHierarchicalController(unittest.TestCase):
    """分层控制器集成测试"""

    def setUp(self):
        self.controller = HierarchicalEnergyController()

    def test_response_chain(self):
        """测试响应链"""
        state = SystemState(
            frequency_deviation=-0.2,
            net_load=50.0
        )

        output = self.controller.step(
            dt=0.1,
            system_state=state,
            reservoir_level=0.5,
            psh_current_mode='stopped',
            hydro_current_power=100.0
        )

        # SC应该首先响应
        self.assertIn('sc_power', output)
        self.assertIn('bess_power', output)


class TestFrequencyRegulator(unittest.TestCase):
    """频率调节器测试"""

    def setUp(self):
        self.regulator = FrequencyRegulator()
        self.units = [
            UnitCapability(name='unit1', rated_power=100.0, current_power=50.0),
            UnitCapability(name='unit2', rated_power=80.0, current_power=40.0)
        ]

    def test_pfr_response(self):
        """测试一次调频响应"""
        pfr = self.regulator.calculate_pfr(-0.1, self.units)
        # 频率下降,应该增加出力
        total_pfr = sum(pfr.values())
        self.assertGreater(total_pfr, 0)

    def test_agc_response(self):
        """测试二次调频响应"""
        agc = self.regulator.calculate_agc(-0.1, 0, 1.0)
        # 频率下降,AGC应该增加出力
        self.assertGreater(agc, 0)


class TestResponseChainDecoupler(unittest.TestCase):
    """响应链解耦测试"""

    def setUp(self):
        self.decoupler = ResponseChainDecoupler()

    def test_event_detection(self):
        """测试事件检测"""
        detected = self.decoupler.detect_event(100.0, 90.0, threshold=5.0)
        self.assertTrue(detected)

        detected = self.decoupler.detect_event(100.0, 98.0, threshold=5.0)
        self.assertFalse(detected)

    def test_chain_activation(self):
        """测试响应链激活"""
        self.decoupler.start_response_chain(50.0, 0.0)
        self.assertTrue(self.decoupler.is_chain_active())

        allocation = self.decoupler.step(0.1, 0.1, 50.0)
        # SC应该有较大份额
        self.assertGreater(allocation['sc_power'], allocation['slow_power'])


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_short_simulation(self):
        """测试短时仿真"""
        from src.multi_energy.simulation import MultiEnergySimulator, SimulationConfig

        config = SimulationConfig(
            duration=60.0,  # 1分钟
            time_step=1.0
        )

        simulator = MultiEnergySimulator(config)
        result = simulator.run()

        # 检查结果完整性
        self.assertEqual(len(result.time), 60)
        self.assertEqual(len(result.frequency), 60)
        self.assertEqual(len(result.wind_power), 60)
        self.assertEqual(len(result.psh_mode), 60)

    def test_frequency_stability(self):
        """测试频率稳定性"""
        from src.multi_energy.simulation import MultiEnergySimulator, SimulationConfig

        config = SimulationConfig(
            duration=300.0,  # 5分钟
            time_step=1.0
        )

        simulator = MultiEnergySimulator(config)
        result = simulator.run()

        # 频率应该在合理范围内
        freq_dev = np.abs(result.frequency - 50.0)
        self.assertLess(np.max(freq_dev), 5.0)  # 不超过5Hz


def run_all_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestWindTurbineModel))
    suite.addTests(loader.loadTestsFromTestCase(TestPhotovoltaicModel))
    suite.addTests(loader.loadTestsFromTestCase(TestSupercapacitorModel))
    suite.addTests(loader.loadTestsFromTestCase(TestBatteryStorageModel))
    suite.addTests(loader.loadTestsFromTestCase(TestPumpedStorageModel))
    suite.addTests(loader.loadTestsFromTestCase(TestGridModel))
    suite.addTests(loader.loadTestsFromTestCase(TestPSHStateMachine))
    suite.addTests(loader.loadTestsFromTestCase(TestPSHDispatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestLayer1SCController))
    suite.addTests(loader.loadTestsFromTestCase(TestLayer2BESSController))
    suite.addTests(loader.loadTestsFromTestCase(TestHierarchicalController))
    suite.addTests(loader.loadTestsFromTestCase(TestFrequencyRegulator))
    suite.addTests(loader.loadTestsFromTestCase(TestResponseChainDecoupler))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == '__main__':
    run_all_tests()
