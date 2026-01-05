# -*- coding: utf-8 -*-
"""
参数敏感性测试 (Stress Test)
Parameter Sensitivity Analysis

根据规范实验三要求：
- 保持控制参数不变
- 连续改变虚拟管长（从1km增加到50km）
- 自动运行关阀测试
- 生成控制器的"安全适用范围图谱"
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
from dataclasses import dataclass

from ..simulator import PipeMOCModel, PipeParameters
from ..controllers import ValveController, EmergencyShutoffValve


@dataclass
class SensitivityResult:
    """敏感性测试结果"""
    parameter_name: str          # 参数名称
    parameter_value: float       # 参数值
    max_pressure: float          # 最大压力 (MPa)
    min_pressure: float          # 最小压力 (MPa)
    water_hammer_amplitude: float # 水锤幅值 (MPa)
    close_time: float            # 关闭时间 (s)
    is_safe: bool                # 是否安全
    risk_level: str              # 风险等级
    notes: str = ""              # 备注


class ParameterSensitivityAnalyzer:
    """参数敏感性分析器

    用于生成控制器的"安全适用范围图谱"
    """

    def __init__(self, design_pressure: float = 1.6):
        """初始化

        Args:
            design_pressure: 设计压力 (MPa)
        """
        self.design_pressure = design_pressure
        self.max_pressure_ratio = 1.2  # 最大允许超压比
        self.results: List[SensitivityResult] = []

    def analyze_pipe_length(self,
                            length_range: Tuple[float, float] = (1000, 50000),
                            step: float = 1000,
                            base_params: Optional[Dict] = None) -> List[SensitivityResult]:
        """分析管长敏感性

        Args:
            length_range: 管长范围 (m)
            step: 步长 (m)
            base_params: 基础参数

        Returns:
            测试结果列表
        """
        results = []
        lengths = np.arange(length_range[0], length_range[1] + step, step)

        print(f"管长敏感性分析: {length_range[0]/1000:.0f}km ~ {length_range[1]/1000:.0f}km")
        print("-" * 60)

        for length in lengths:
            result = self._test_single_length(length, base_params)
            results.append(result)

            status = "✓ 安全" if result.is_safe else f"✗ {result.risk_level}"
            print(f"  L={length/1000:5.1f}km | Pmax={result.max_pressure:.3f}MPa | "
                  f"ΔP={result.water_hammer_amplitude:.3f}MPa | {status}")

        self.results = results
        return results

    def _test_single_length(self, length: float, base_params: Optional[Dict] = None) -> SensitivityResult:
        """测试单个管长

        Args:
            length: 管长 (m)
            base_params: 基础参数

        Returns:
            测试结果
        """
        # 默认参数
        params = {
            'diameter': 2.0,
            'wave_speed': 1000.0,
            'initial_head': 100.0,
            'initial_flow': 10.0,
        }
        if base_params:
            params.update(base_params)

        # 创建管道模型
        pipe_params = PipeParameters(
            length=length,
            diameter=params['diameter'],
            wave_speed=params['wave_speed'],
            design_pressure=self.design_pressure,
        )

        # 计算合适的时间步长
        dt = min(0.01, length / params['wave_speed'] / 10)

        simulator = PipeMOCModel(pipe_params, dt=dt)
        simulator.initialize(
            upstream_head=params['initial_head'],
            initial_flow=params['initial_flow'],
            valve_opening=1.0
        )

        # 创建控制器
        controller = ValveController("IVCU-TEST")
        controller.design_pressure = self.design_pressure

        # 运行稳态
        for _ in range(int(2.0 / dt)):
            simulator.step()

        # 触发关阀
        controller.command_close(mode="two_stage")

        # 记录数据
        max_pressure = 0.0
        min_pressure = float('inf')
        close_time = None

        # 运行测试 (最多60秒)
        test_duration = min(60.0, length / params['wave_speed'] * 4)
        for i in range(int(test_duration / dt)):
            state = simulator.step()

            # 控制器
            ctrl_input = {
                'P1': state.pressure_upstream,
                'P2': state.pressure_downstream,
                'Q': state.flow_rate,
                'opening': simulator.valve_opening,
            }
            result = controller.run_cycle(ctrl_input)
            simulator.set_valve_opening(result['output'])

            # 更新统计
            max_pressure = max(max_pressure, state.pressure_downstream, state.pressure_upstream)
            min_pressure = min(min_pressure, state.pressure_downstream)

            # 检测关闭完成
            if close_time is None and simulator.valve_opening < 0.01:
                close_time = i * dt

        # 评估结果
        water_hammer = max_pressure - min_pressure
        max_allowed = self.design_pressure * self.max_pressure_ratio

        is_safe = max_pressure <= max_allowed and min_pressure >= 0.0
        risk_level = self._assess_risk(max_pressure, min_pressure, max_allowed)

        return SensitivityResult(
            parameter_name="pipe_length",
            parameter_value=length,
            max_pressure=max_pressure,
            min_pressure=min_pressure,
            water_hammer_amplitude=water_hammer,
            close_time=close_time or test_duration,
            is_safe=is_safe,
            risk_level=risk_level,
        )

    def _assess_risk(self, max_p: float, min_p: float, max_allowed: float) -> str:
        """评估风险等级"""
        if max_p > max_allowed * 1.1:
            return "CRITICAL"
        elif max_p > max_allowed:
            return "HIGH"
        elif max_p > self.design_pressure:
            return "MEDIUM"
        elif min_p < 0.05:
            return "NEGATIVE_PRESSURE"
        else:
            return "SAFE"

    def analyze_wave_speed(self,
                           speed_range: Tuple[float, float] = (800, 1200),
                           step: float = 50,
                           pipe_length: float = 20000) -> List[SensitivityResult]:
        """分析波速敏感性

        Args:
            speed_range: 波速范围 (m/s)
            step: 步长 (m/s)
            pipe_length: 管长 (m)

        Returns:
            测试结果列表
        """
        results = []
        speeds = np.arange(speed_range[0], speed_range[1] + step, step)

        print(f"波速敏感性分析: {speed_range[0]}m/s ~ {speed_range[1]}m/s")
        print("-" * 60)

        for speed in speeds:
            base_params = {'wave_speed': speed}
            result = self._test_single_length(pipe_length, base_params)
            result.parameter_name = "wave_speed"
            result.parameter_value = speed
            results.append(result)

            status = "✓ 安全" if result.is_safe else f"✗ {result.risk_level}"
            print(f"  a={speed:4.0f}m/s | Pmax={result.max_pressure:.3f}MPa | "
                  f"ΔP={result.water_hammer_amplitude:.3f}MPa | {status}")

        return results

    def analyze_initial_flow(self,
                             flow_range: Tuple[float, float] = (5, 20),
                             step: float = 1,
                             pipe_length: float = 20000) -> List[SensitivityResult]:
        """分析初始流量敏感性

        Args:
            flow_range: 流量范围 (m³/s)
            step: 步长 (m³/s)
            pipe_length: 管长 (m)

        Returns:
            测试结果列表
        """
        results = []
        flows = np.arange(flow_range[0], flow_range[1] + step, step)

        print(f"流量敏感性分析: {flow_range[0]}m³/s ~ {flow_range[1]}m³/s")
        print("-" * 60)

        for flow in flows:
            base_params = {'initial_flow': flow}
            result = self._test_single_length(pipe_length, base_params)
            result.parameter_name = "initial_flow"
            result.parameter_value = flow
            results.append(result)

            status = "✓ 安全" if result.is_safe else f"✗ {result.risk_level}"
            print(f"  Q={flow:5.1f}m³/s | Pmax={result.max_pressure:.3f}MPa | "
                  f"ΔP={result.water_hammer_amplitude:.3f}MPa | {status}")

        return results

    def get_safe_range(self, parameter_name: str = "pipe_length") -> Dict:
        """获取安全适用范围

        Args:
            parameter_name: 参数名称

        Returns:
            安全范围信息
        """
        relevant = [r for r in self.results if r.parameter_name == parameter_name]
        if not relevant:
            return {'error': 'No results found'}

        safe_results = [r for r in relevant if r.is_safe]

        if not safe_results:
            return {
                'parameter': parameter_name,
                'safe_range': None,
                'message': '所有测试点均不安全',
            }

        safe_values = [r.parameter_value for r in safe_results]

        return {
            'parameter': parameter_name,
            'safe_range': (min(safe_values), max(safe_values)),
            'safe_count': len(safe_results),
            'total_count': len(relevant),
            'pass_rate': len(safe_results) / len(relevant),
        }

    def generate_report(self) -> str:
        """生成敏感性分析报告

        Returns:
            报告文本
        """
        lines = [
            "=" * 70,
            "参数敏感性分析报告",
            "Parameter Sensitivity Analysis Report",
            "=" * 70,
            "",
            f"设计压力: {self.design_pressure} MPa",
            f"最大允许压力: {self.design_pressure * self.max_pressure_ratio} MPa",
            "",
        ]

        # 按参数分组
        params = set(r.parameter_name for r in self.results)

        for param in params:
            results = [r for r in self.results if r.parameter_name == param]
            safe_range = self.get_safe_range(param)

            lines.append("-" * 70)
            lines.append(f"参数: {param}")
            lines.append("-" * 70)

            if safe_range.get('safe_range'):
                sr = safe_range['safe_range']
                lines.append(f"  安全范围: {sr[0]:.1f} ~ {sr[1]:.1f}")
            else:
                lines.append("  安全范围: 无")

            lines.append(f"  通过率: {safe_range.get('pass_rate', 0)*100:.1f}%")
            lines.append("")

            # 风险分布
            risk_counts = {}
            for r in results:
                risk_counts[r.risk_level] = risk_counts.get(r.risk_level, 0) + 1

            lines.append("  风险分布:")
            for level, count in sorted(risk_counts.items()):
                lines.append(f"    {level}: {count}")

            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


def run_sensitivity_demo():
    """运行敏感性分析演示"""
    print("\n" + "="*70)
    print("参数敏感性压力测试 (Stress Test)")
    print("="*70 + "\n")

    analyzer = ParameterSensitivityAnalyzer(design_pressure=1.6)

    # 1. 管长敏感性
    print("\n[1/3] 管长敏感性分析\n")
    analyzer.analyze_pipe_length(
        length_range=(5000, 30000),
        step=5000
    )

    # 2. 波速敏感性
    print("\n[2/3] 波速敏感性分析\n")
    analyzer.analyze_wave_speed(
        speed_range=(800, 1200),
        step=100,
        pipe_length=20000
    )

    # 3. 流量敏感性
    print("\n[3/3] 流量敏感性分析\n")
    analyzer.analyze_initial_flow(
        flow_range=(5, 15),
        step=2,
        pipe_length=20000
    )

    # 生成报告
    print("\n")
    print(analyzer.generate_report())

    return analyzer


if __name__ == "__main__":
    run_sensitivity_demo()
