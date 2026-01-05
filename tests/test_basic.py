# -*- coding: utf-8 -*-
"""
基础测试 - 验证HIL平台核心组件
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """测试所有模块可以正确导入"""
    # 仿真器
    from src.simulator import (
        HydraulicModel, PipeMOCModel, ChannelSaintVenantModel,
        PumpCharacteristics, PipeParameters, ChannelParameters
    )

    # 控制器
    from src.controllers import (
        BaseController, ValveController, PumpController, GateController
    )

    # 传感器
    from src.sensors import (
        VirtualSensor, VirtualPressureSensor, VirtualFlowSensor,
        VirtualLevelSensor, SensorArray
    )

    # 测试用例
    from src.test_cases import (
        ValveTestSuite, PumpTestSuite, GateTestSuite
    )

    # HIL平台
    from src.hil_platform import HILPlatform, create_platform

    print("✓ 所有模块导入成功")
    return True


def test_pipe_model():
    """测试管道MOC模型"""
    from src.simulator import PipeMOCModel, PipeParameters

    params = PipeParameters(
        length=1000,
        diameter=1.0,
        wave_speed=1000,
        design_pressure=1.0
    )

    model = PipeMOCModel(params, dt=0.01)
    model.initialize(upstream_head=50, initial_flow=5.0)

    # 运行几步
    for _ in range(100):
        state = model.step()

    assert state.time > 0, "时间应该增加"
    assert state.pressure_upstream >= 0, "压力应该非负"

    print("✓ 管道MOC模型测试通过")
    return True


def test_valve_controller():
    """测试阀门控制器"""
    from src.controllers import ValveController

    controller = ValveController("IVCU-TEST")

    # 模拟传感器输入
    sensor_data = {
        'P1': 0.8,  # 上游压力 MPa
        'P2': 0.5,  # 下游压力 MPa
        'Q': 5.0,   # 流量 m³/s
        'opening': 1.0,  # 开度
    }

    result = controller.run_cycle(sensor_data)

    assert 'output' in result, "应返回输出指令"
    assert 0 <= result['output'] <= 1, "输出应在0-1范围内"

    print("✓ 阀门控制器测试通过")
    return True


def test_pump_controller():
    """测试水泵控制器"""
    from src.controllers import PumpController

    controller = PumpController("IPCU-TEST")

    sensor_data = {
        'speed': 0,
        'flow': 0,
        'P_suction': 0.1,
        'P_discharge': 0.5,
        'vibration': 2.0,
        'temperature': 40.0,
    }

    # 启动水泵
    controller.command_start(1450)

    result = controller.run_cycle(sensor_data)

    assert controller.state.is_running, "水泵应该在运行"

    print("✓ 水泵控制器测试通过")
    return True


def test_gate_controller():
    """测试闸门控制器"""
    from src.controllers import GateController

    controller = GateController("IGCU-TEST")

    sensor_data = {
        'opening': 1.0,
        'Z_up': 3.0,
        'Z_down': 2.0,
        'Q': 50.0,
    }

    result = controller.run_cycle(sensor_data)

    assert 'output' in result, "应返回输出指令"

    print("✓ 闸门控制器测试通过")
    return True


def test_sensor_array():
    """测试虚拟传感器阵列"""
    from src.sensors import SensorArray, VirtualPressureSensor, VirtualFlowSensor

    array = SensorArray()
    array.add_sensor(VirtualPressureSensor("upstream", 2.5))
    array.add_sensor(VirtualPressureSensor("downstream", 2.5))
    array.add_sensor(VirtualFlowSensor(50.0))

    sim_state = {
        'pressure_upstream': 0.8,
        'pressure_downstream': 0.5,
        'flow_rate': 10.0,
    }

    readings = array.update_all(sim_state, 0.01)

    assert len(readings) == 3, "应返回3个传感器读数"

    print("✓ 虚拟传感器阵列测试通过")
    return True


def test_hil_platform():
    """测试HIL平台"""
    from src.hil_platform import HILPlatform, HILMode

    platform = HILPlatform()
    platform.setup_valve_test()

    status = platform.get_status()

    assert status['mode'] == 'idle', "初始模式应为idle"
    assert 'valve' in status['available_suites'], "应包含阀门测试套件"

    print("✓ HIL平台测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*50)
    print("HIL 水利枢纽仿真平台 - 基础测试")
    print("="*50 + "\n")

    tests = [
        test_imports,
        test_pipe_model,
        test_valve_controller,
        test_pump_controller,
        test_gate_controller,
        test_sensor_array,
        test_hil_platform,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {test_func.__name__} 失败: {e}")
            failed += 1

    print("\n" + "-"*50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("-"*50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
