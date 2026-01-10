# -*- coding: utf-8 -*-
"""
多能互补系统联合仿真主程序
Multi-Energy Complementary System Joint Simulation

实现全天候工况下的系统级联合仿真:
1. 风-光-水-储-抽五种能源协同运行
2. 分层控制架构协调
3. 典型日负荷曲线仿真
4. 数据记录与分析

仿真场景:
=========
- 时间范围: 0-24小时
- 时间步长: 可配置(推荐1s用于详细分析, 10s用于快速仿真)
- 负荷曲线: 典型日负荷曲线
- 风光资源: 典型日风速和辐照度曲线
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum, auto

from .energy_models import (
    WindTurbineModel, PhotovoltaicModel,
    SupercapacitorModel, BatteryStorageModel,
    PumpedStorageModel, ConventionalHydroModel,
    GridModel, GridParameters, WindCondition, SolarCondition,
    PSHOperatingState, PSHParameters, HydroPlantParameters
)
from .psh_state_machine import (
    PSHStateMachine, PSHConstraints, PSHOperatingMode,
    PSHDispatcher, DispatchContext
)
from .hierarchical_control import (
    Layer1_SCDroopController, Layer2_BESSFilterController,
    Layer3_MPCCoordinator, HierarchicalEnergyController,
    SystemState, MPCConfig
)
from .parameter_tuning import (
    OptimizedControllerParams, DefaultControllerParams,
    get_recommended_params_for_system
)


# ==================== 仿真配置 ====================

@dataclass
class SimulationConfig:
    """仿真配置"""
    # 时间配置
    duration: float = 86400.0        # 仿真时长(s) = 24h
    time_step: float = 1.0           # 时间步长(s)
    start_hour: float = 0.0          # 起始小时

    # 系统配置
    base_load: float = 250.0         # 基础负荷(MW) - 降低以匹配发电容量
    load_peak_ratio: float = 1.3     # 峰值负荷比 - 降低峰谷差
    load_valley_ratio: float = 0.7   # 低谷负荷比 - 提高谷值

    # 可再生能源配置
    wind_capacity: float = 50.0      # 风电装机容量(MW)
    solar_capacity: float = 30.0     # 光伏装机容量(MW)

    # 储能配置
    sc_power: float = 10.0           # 超级电容功率(MW)
    sc_energy: float = 0.5           # 超级电容能量(MWh)
    bess_power: float = 20.0         # 电池储能功率(MW)
    bess_energy: float = 40.0        # 电池储能能量(MWh)

    # 抽水蓄能配置
    psh_power_gen: float = 100.0     # PSH发电功率(MW)
    psh_power_pump: float = 90.0     # PSH抽水功率(MW)
    psh_initial_level: float = 0.5   # PSH初始水位

    # 常规水电配置
    hydro_power: float = 250.0       # 水电装机容量(MW) - 增加调峰能力
    hydro_min_power: float = 80.0    # 水电最小出力(MW)

    # 电网配置
    nominal_frequency: float = 50.0
    system_inertia: float = 6.0

    # 随机扰动
    wind_turbulence: float = 0.1     # 风速湍流强度
    load_noise: float = 0.02         # 负荷噪声强度

    # 控制器参数模式
    use_optimized_params: bool = True  # 使用优化后的参数
    controller_params: Optional[OptimizedControllerParams] = None  # 自定义参数


@dataclass
class SimulationResult:
    """仿真结果"""
    time: np.ndarray = field(default_factory=lambda: np.array([]))
    frequency: np.ndarray = field(default_factory=lambda: np.array([]))

    # 发电功率
    wind_power: np.ndarray = field(default_factory=lambda: np.array([]))
    solar_power: np.ndarray = field(default_factory=lambda: np.array([]))
    hydro_power: np.ndarray = field(default_factory=lambda: np.array([]))
    psh_power: np.ndarray = field(default_factory=lambda: np.array([]))

    # 储能功率
    sc_power: np.ndarray = field(default_factory=lambda: np.array([]))
    bess_power: np.ndarray = field(default_factory=lambda: np.array([]))

    # 负荷
    load: np.ndarray = field(default_factory=lambda: np.array([]))
    net_load: np.ndarray = field(default_factory=lambda: np.array([]))

    # 状态
    sc_soc: np.ndarray = field(default_factory=lambda: np.array([]))
    bess_soc: np.ndarray = field(default_factory=lambda: np.array([]))
    psh_level: np.ndarray = field(default_factory=lambda: np.array([]))
    psh_mode: List[str] = field(default_factory=list)

    # 统计指标
    frequency_deviation_max: float = 0.0
    frequency_deviation_rms: float = 0.0
    renewable_curtailment: float = 0.0
    psh_mode_switches: int = 0


# ==================== 资源曲线生成 ====================

class ResourceProfileGenerator:
    """
    资源曲线生成器

    生成典型日的:
    - 负荷曲线(双峰特征)
    - 风速曲线(日夜差异)
    - 辐照度曲线(日出日落)
    """

    @staticmethod
    def generate_load_profile(
        hours: np.ndarray,
        base_load: float,
        peak_ratio: float = 1.5,
        valley_ratio: float = 0.6,
        noise_level: float = 0.02
    ) -> np.ndarray:
        """
        生成典型日负荷曲线

        特征:
        - 早高峰: 7:00-9:00
        - 午间平: 12:00-14:00 (略有下降)
        - 晚高峰: 18:00-21:00 (最高)
        - 夜间低谷: 0:00-6:00

        Args:
            hours: 小时数组
            base_load: 基础负荷(MW)
            peak_ratio: 峰值比
            valley_ratio: 低谷比
            noise_level: 噪声水平

        Returns:
            负荷曲线(MW)
        """
        load = np.zeros_like(hours)

        for i, h in enumerate(hours):
            # 基础负荷曲线(双峰)
            h_mod = h % 24

            # 夜间低谷
            if 0 <= h_mod < 6:
                factor = valley_ratio + 0.1 * np.sin(np.pi * h_mod / 6)
            # 早高峰上升
            elif 6 <= h_mod < 9:
                factor = valley_ratio + (1.0 - valley_ratio) * (h_mod - 6) / 3
            # 上午平稳
            elif 9 <= h_mod < 12:
                factor = 1.0 + 0.1 * np.sin(np.pi * (h_mod - 9) / 3)
            # 午间小降
            elif 12 <= h_mod < 14:
                factor = 1.0 - 0.1 * (h_mod - 12) / 2
            # 下午上升
            elif 14 <= h_mod < 18:
                factor = 0.9 + (peak_ratio - 0.9) * (h_mod - 14) / 4
            # 晚高峰
            elif 18 <= h_mod < 21:
                factor = peak_ratio * (1 - 0.1 * np.sin(np.pi * (h_mod - 18) / 3))
            # 夜间下降
            else:  # 21-24
                factor = peak_ratio - (peak_ratio - valley_ratio) * (h_mod - 21) / 3

            load[i] = base_load * factor

        # 添加随机噪声
        noise = np.random.normal(0, noise_level * base_load, len(hours))
        load += noise

        return np.maximum(load, 0)

    @staticmethod
    def generate_wind_profile(
        hours: np.ndarray,
        mean_speed: float = 8.0,
        turbulence: float = 0.1
    ) -> np.ndarray:
        """
        生成典型日风速曲线

        特征:
        - 夜间风速较高
        - 午后风速较低
        - 有湍流波动

        Args:
            hours: 小时数组
            mean_speed: 平均风速(m/s)
            turbulence: 湍流强度

        Returns:
            风速曲线(m/s)
        """
        wind_speed = np.zeros_like(hours)

        for i, h in enumerate(hours):
            h_mod = h % 24

            # 日变化模式: 夜间风大,午后风小
            daily_factor = 1.0 - 0.3 * np.sin(np.pi * (h_mod - 6) / 12)
            if h_mod < 6 or h_mod > 18:
                daily_factor = 1.0 + 0.2 * np.abs(np.sin(np.pi * h_mod / 12))

            base_speed = mean_speed * daily_factor

            # 添加湍流(考虑时间相关性)
            turbulence_component = turbulence * mean_speed * np.random.normal()

            wind_speed[i] = base_speed + turbulence_component

        # 确保非负且合理范围
        wind_speed = np.clip(wind_speed, 0, 25)

        return wind_speed

    @staticmethod
    def generate_solar_profile(
        hours: np.ndarray,
        max_irradiance: float = 1000.0,
        sunrise: float = 6.0,
        sunset: float = 18.0,
        cloud_variability: float = 0.1
    ) -> np.ndarray:
        """
        生成典型日辐照度曲线

        Args:
            hours: 小时数组
            max_irradiance: 最大辐照度(W/m²)
            sunrise: 日出时间
            sunset: 日落时间
            cloud_variability: 云遮变异性

        Returns:
            辐照度曲线(W/m²)
        """
        irradiance = np.zeros_like(hours)

        for i, h in enumerate(hours):
            h_mod = h % 24

            if sunrise <= h_mod <= sunset:
                # 太阳高度角近似
                solar_progress = (h_mod - sunrise) / (sunset - sunrise)
                irradiance[i] = max_irradiance * np.sin(np.pi * solar_progress)

                # 云遮随机影响
                cloud_factor = 1 - cloud_variability * np.abs(np.random.normal())
                irradiance[i] *= max(0, cloud_factor)

        return np.maximum(irradiance, 0)


# ==================== 联合仿真器 ====================

class MultiEnergySimulator:
    """
    多能互补系统联合仿真器

    集成所有能源组件和控制器,执行全天候仿真
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()

        # 创建能源组件
        self._create_components()

        # 创建控制器
        self._create_controllers()

        # 仿真状态
        self._current_time = 0.0
        self._result = SimulationResult()

        # 资源曲线生成器
        self._profile_gen = ResourceProfileGenerator()

        # 数据记录
        self._data_buffer: Dict[str, List] = {
            'time': [], 'frequency': [],
            'wind_power': [], 'solar_power': [],
            'hydro_power': [], 'psh_power': [],
            'sc_power': [], 'bess_power': [],
            'load': [], 'net_load': [],
            'sc_soc': [], 'bess_soc': [],
            'psh_level': [], 'psh_mode': []
        }

    def _create_components(self):
        """创建能源组件"""
        cfg = self.config

        # 波动电源
        self.wind_turbine = WindTurbineModel(
            name="WT",
            rated_power=cfg.wind_capacity,
            time_constant=2.0
        )

        self.solar_pv = PhotovoltaicModel(
            name="PV",
            rated_power=cfg.solar_capacity,
            time_constant=0.1
        )

        # 混合储能
        self.supercapacitor = SupercapacitorModel(
            name="SC",
            rated_power=cfg.sc_power,
            rated_energy=cfg.sc_energy,
            time_constant=0.01
        )

        self.battery = BatteryStorageModel(
            name="BESS",
            rated_power=cfg.bess_power,
            rated_energy=cfg.bess_energy,
            time_constant=0.5
        )

        # 抽水蓄能
        psh_params = PSHParameters(
            rated_power_gen=cfg.psh_power_gen,
            rated_power_pump=cfg.psh_power_pump,
            rated_head=300.0
        )
        self.psh = PumpedStorageModel(name="PSH", params=psh_params)
        self.psh._reservoir_level = cfg.psh_initial_level

        # PSH状态机
        self.psh_state_machine = PSHStateMachine(
            rated_power_gen=cfg.psh_power_gen,
            rated_power_pump=cfg.psh_power_pump
        )

        # PSH调度器
        self.psh_dispatcher = PSHDispatcher(
            rated_power_gen=cfg.psh_power_gen,
            rated_power_pump=cfg.psh_power_pump
        )

        # 常规水电
        # 注意: HydroPlantParameters.min_power 是比例值(p.u.)
        hydro_min_power_ratio = cfg.hydro_min_power / cfg.hydro_power
        hydro_params = HydroPlantParameters(
            rated_power=cfg.hydro_power,
            min_power=hydro_min_power_ratio
        )
        self.hydro = ConventionalHydroModel(name="Hydro", params=hydro_params)
        self.hydro.start()

        # 电网模型 - 使用优化后的参数
        if cfg.use_optimized_params:
            grid_params = GridParameters(
                nominal_frequency=cfg.nominal_frequency,
                system_inertia=8.0,       # 增加惯量
                damping_coefficient=2.0,   # 增加阻尼
                base_power=1000.0
            )
        else:
            grid_params = GridParameters(
                nominal_frequency=cfg.nominal_frequency,
                system_inertia=cfg.system_inertia,
                damping_coefficient=1.0,
                base_power=1000.0
            )
        self.grid = GridModel(params=grid_params)

    def _create_controllers(self):
        """创建控制器"""
        cfg = self.config

        # 获取控制器参数
        if cfg.controller_params is not None:
            params = cfg.controller_params
        elif cfg.use_optimized_params:
            params = OptimizedControllerParams()
        else:
            params = DefaultControllerParams()

        # 分层控制器 - 第一层: SC下垂控制
        layer1 = Layer1_SCDroopController(
            rated_power=params.sc_rated_power,
            rated_energy=params.sc_rated_energy,
            droop_gain=params.sc_droop_gain,
            damping_gain=params.sc_damping_gain,
            time_constant=params.sc_time_constant,
            deadband=params.sc_deadband
        )

        # 第二层: BESS滤波控制
        layer2 = Layer2_BESSFilterController(
            rated_power=params.bess_rated_power,
            rated_energy=params.bess_rated_energy,
            filter_time_constant=params.bess_filter_tau,
            response_time_constant=params.bess_response_tau,
            ramp_rate=params.bess_ramp_rate
        )

        # 第三层: MPC协同控制
        mpc_config = MPCConfig(
            frequency_weight=params.mpc_freq_weight,
            power_weight=params.mpc_power_weight
        )
        layer3 = Layer3_MPCCoordinator(
            psh_rated_power_gen=cfg.psh_power_gen,
            psh_rated_power_pump=cfg.psh_power_pump,
            hydro_rated_power=cfg.hydro_power,
            hydro_min_power=cfg.hydro_min_power,
            config=mpc_config
        )

        # 保存参数以供频率校正使用
        self._controller_params = params

        self.hierarchical_controller = HierarchicalEnergyController(
            layer1=layer1,
            layer2=layer2,
            layer3=layer3
        )

    def generate_profiles(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        生成仿真所需的资源曲线

        Returns:
            (时间, 负荷, 风速, 辐照度)
        """
        cfg = self.config
        n_steps = int(cfg.duration / cfg.time_step)
        time = np.linspace(0, cfg.duration, n_steps)
        hours = time / 3600 + cfg.start_hour

        load = self._profile_gen.generate_load_profile(
            hours, cfg.base_load, cfg.load_peak_ratio,
            cfg.load_valley_ratio, cfg.load_noise
        )

        wind_speed = self._profile_gen.generate_wind_profile(
            hours, 8.0, cfg.wind_turbulence
        )

        irradiance = self._profile_gen.generate_solar_profile(
            hours, 1000.0, 6.0, 18.0, 0.1
        )

        return time, load, wind_speed, irradiance

    def run(
        self,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> SimulationResult:
        """
        执行全天候仿真

        Args:
            progress_callback: 进度回调函数

        Returns:
            SimulationResult
        """
        cfg = self.config
        dt = cfg.time_step

        # 生成资源曲线
        time_array, load_array, wind_array, irradiance_array = self.generate_profiles()
        n_steps = len(time_array)

        # 初始化
        self._current_time = 0.0
        self._clear_data_buffer()
        psh_mode_switches = 0
        last_psh_mode = "stopped"

        # 初始设置
        self.wind_turbine.set_power_setpoint(cfg.wind_capacity)
        self.solar_pv.set_power_setpoint(cfg.solar_capacity)
        self.hydro.set_power_setpoint(cfg.hydro_power * 0.5)  # 初始50%负荷

        print("开始多能互补系统仿真...")
        print(f"仿真时长: {cfg.duration/3600:.1f}小时, 时间步长: {dt}秒")

        # 预热阶段: 让系统稳定到初始状态
        print("预热系统...")
        warmup_steps = 100
        for _ in range(warmup_steps):
            hour = cfg.start_hour
            wind_condition = WindCondition(wind_speed=wind_array[0], turbulence_intensity=0.0)
            solar_condition = SolarCondition(irradiance=irradiance_array[0], temperature=25.0)
            self.wind_turbine.step(dt, wind_condition)
            self.solar_pv.step(dt, solar_condition)
            self.hydro.step(dt)
            # 更新电网到稳态
            total_gen = self.wind_turbine.get_power() + self.solar_pv.get_power() + self.hydro.get_power()
            self.grid.step(dt, total_gen, load_array[0])

        # 主仿真循环
        for i in range(n_steps):
            t = time_array[i]
            hour = (t / 3600 + cfg.start_hour) % 24
            load = load_array[i]
            wind_speed = wind_array[i]
            irradiance = irradiance_array[i]

            # ===== 更新波动电源 =====
            wind_condition = WindCondition(
                wind_speed=wind_speed,
                turbulence_intensity=cfg.wind_turbulence
            )
            solar_condition = SolarCondition(
                irradiance=irradiance,
                temperature=25.0
            )

            self.wind_turbine.step(dt, wind_condition)
            self.solar_pv.step(dt, solar_condition)

            renewable_power = self.wind_turbine.get_power() + self.solar_pv.get_power()
            net_load = load - renewable_power

            # ===== 获取当前频率 =====
            frequency = self.grid.get_frequency()
            freq_dev = self.grid.get_frequency_deviation()

            # ===== 构建系统状态 =====
            system_state = SystemState(
                time=t,
                frequency=frequency,
                frequency_deviation=freq_dev,
                total_generation=0,  # 将在后面更新
                total_load=load,
                total_renewable=renewable_power,
                net_load=net_load,
                power_imbalance=0
            )

            # ===== PSH调度决策 =====
            psh_level = self.psh.get_reservoir_level()
            psh_current_mode = self.psh.get_operating_state().name.lower()

            # 生成未来几小时的净负荷预测
            forecast_steps = min(12, n_steps - i)
            net_load_forecast = []
            for j in range(forecast_steps):
                future_i = min(i + j * 60, n_steps - 1)  # 每分钟一个预测点
                future_load = load_array[future_i]
                future_renewable = wind_array[future_i] * 0.3 + irradiance_array[future_i] * 0.02  # 简化估计
                net_load_forecast.append(future_load - future_renewable)

            # 调度决策
            dispatch_context = DispatchContext(
                current_time=t,
                hour_of_day=hour,
                net_load=net_load,
                net_load_forecast=net_load_forecast,
                reservoir_level=psh_level,
                current_mode=PSHOperatingMode(psh_current_mode) if psh_current_mode in ['stopped', 'pumping', 'generating'] else PSHOperatingMode.STOPPED,
                frequency_deviation=freq_dev
            )

            decision, suggested_power, reason = self.psh_dispatcher.decide(dispatch_context)

            # 执行PSH模式切换
            if decision.value == 'pump' and psh_current_mode != 'pumping':
                self.psh.request_mode(PSHOperatingState.PUMPING)
            elif decision.value == 'gen' and psh_current_mode != 'generating':
                self.psh.request_mode(PSHOperatingState.GENERATING)
            elif decision.value == 'stop' and psh_current_mode not in ['stopped', 'pump_stopping', 'gen_stopping']:
                self.psh.request_mode(PSHOperatingState.STOPPED)

            # 设置PSH功率
            if decision.value == 'gen':
                self.psh.set_power_setpoint(suggested_power)
            elif decision.value == 'pump':
                self.psh.set_power_setpoint(-suggested_power)

            # ===== 分层控制 =====
            control_output = self.hierarchical_controller.step(
                dt=dt,
                system_state=system_state,
                reservoir_level=psh_level,
                psh_current_mode=psh_current_mode,
                hydro_current_power=self.hydro.get_power(),
                net_load_forecast=net_load_forecast
            )

            # 应用控制输出
            self.supercapacitor.set_power_setpoint(control_output['sc_power'])
            self.battery.set_power_setpoint(control_output['bess_power'])

            # ===== 直接功率平衡控制 =====
            # 计算当前功率缺口并用水电直接补偿
            psh_power_current = self.psh.get_power()
            current_gen_no_hydro = (renewable_power +
                                   self.supercapacitor.get_power() +
                                   self.battery.get_power() +
                                   (psh_power_current if psh_power_current > 0 else 0))
            current_consumption = load + (abs(psh_power_current) if psh_power_current < 0 else 0)
            power_deficit = current_consumption - current_gen_no_hydro

            # 获取控制器参数
            if hasattr(self, '_controller_params'):
                params = self._controller_params
                hydro_droop_gain = 60.0  # MW/Hz for hydro (increased)
            else:
                hydro_droop_gain = 40.0

            # 方案1: 基于功率缺口直接设置水电(优先)
            # 水电目标 = 净负荷 - PSH出力
            hydro_from_balance = net_load - (psh_power_current if psh_power_current > 0 else 0)

            # 方案2: 频率偏差下垂控制叠加
            hydro_freq_correction = -freq_dev * hydro_droop_gain

            # 综合控制: 取两种方法的较大值(确保发电充足)
            hydro_base = control_output['hydro_power']
            hydro_target = max(
                hydro_base + hydro_freq_correction,
                hydro_from_balance * 1.05  # 多发5%作为备用
            )
            hydro_target = np.clip(hydro_target, cfg.hydro_min_power, cfg.hydro_power)
            self.hydro.set_power_setpoint(hydro_target)

            # ===== 更新各组件 =====
            self.supercapacitor.step(dt)
            self.battery.step(dt)
            self.psh.step(dt)
            self.hydro.step(dt)

            # ===== 计算总发电 =====
            sc_power = self.supercapacitor.get_power()
            bess_power = self.battery.get_power()
            psh_power = self.psh.get_power()
            hydro_power = self.hydro.get_power()

            total_generation = (renewable_power + hydro_power +
                              sc_power + bess_power +
                              (psh_power if psh_power > 0 else 0))
            total_consumption = load + (abs(psh_power) if psh_power < 0 else 0)

            # ===== 更新电网频率 =====
            self.grid.step(dt, total_generation, total_consumption)

            # ===== 统计PSH模式切换 =====
            current_psh_mode = self.psh.get_operating_state().name.lower()
            if current_psh_mode != last_psh_mode:
                if current_psh_mode in ['pumping', 'generating'] and last_psh_mode in ['stopped', 'pumping', 'generating']:
                    psh_mode_switches += 1
                last_psh_mode = current_psh_mode

            # ===== 记录数据 =====
            self._data_buffer['time'].append(t)
            self._data_buffer['frequency'].append(frequency)
            self._data_buffer['wind_power'].append(self.wind_turbine.get_power())
            self._data_buffer['solar_power'].append(self.solar_pv.get_power())
            self._data_buffer['hydro_power'].append(hydro_power)
            self._data_buffer['psh_power'].append(psh_power)
            self._data_buffer['sc_power'].append(sc_power)
            self._data_buffer['bess_power'].append(bess_power)
            self._data_buffer['load'].append(load)
            self._data_buffer['net_load'].append(net_load)
            self._data_buffer['sc_soc'].append(self.supercapacitor.get_soc())
            self._data_buffer['bess_soc'].append(self.battery.get_soc())
            self._data_buffer['psh_level'].append(psh_level)
            self._data_buffer['psh_mode'].append(current_psh_mode)

            # 进度回调
            if progress_callback and i % 1000 == 0:
                progress_callback(i / n_steps)

        # 构建结果
        self._result = self._build_result(psh_mode_switches)

        print(f"\n仿真完成!")
        print(f"频率偏差最大值: {self._result.frequency_deviation_max:.4f} Hz")
        print(f"频率偏差RMS: {self._result.frequency_deviation_rms:.4f} Hz")
        print(f"PSH模式切换次数: {self._result.psh_mode_switches}")

        return self._result

    def _clear_data_buffer(self):
        """清空数据缓冲"""
        for key in self._data_buffer:
            self._data_buffer[key] = []

    def _build_result(self, psh_mode_switches: int) -> SimulationResult:
        """构建仿真结果"""
        freq_array = np.array(self._data_buffer['frequency'])
        freq_dev = freq_array - self.config.nominal_frequency

        return SimulationResult(
            time=np.array(self._data_buffer['time']),
            frequency=freq_array,
            wind_power=np.array(self._data_buffer['wind_power']),
            solar_power=np.array(self._data_buffer['solar_power']),
            hydro_power=np.array(self._data_buffer['hydro_power']),
            psh_power=np.array(self._data_buffer['psh_power']),
            sc_power=np.array(self._data_buffer['sc_power']),
            bess_power=np.array(self._data_buffer['bess_power']),
            load=np.array(self._data_buffer['load']),
            net_load=np.array(self._data_buffer['net_load']),
            sc_soc=np.array(self._data_buffer['sc_soc']),
            bess_soc=np.array(self._data_buffer['bess_soc']),
            psh_level=np.array(self._data_buffer['psh_level']),
            psh_mode=self._data_buffer['psh_mode'].copy(),
            frequency_deviation_max=np.max(np.abs(freq_dev)),
            frequency_deviation_rms=np.sqrt(np.mean(freq_dev**2)),
            psh_mode_switches=psh_mode_switches
        )

    def get_result(self) -> SimulationResult:
        """获取仿真结果"""
        return self._result


# ==================== 快速仿真函数 ====================

def run_quick_simulation(
    duration_hours: float = 24.0,
    time_step: float = 10.0,
    **kwargs
) -> SimulationResult:
    """
    快速运行一次仿真

    Args:
        duration_hours: 仿真时长(小时)
        time_step: 时间步长(秒)
        **kwargs: 其他配置参数

    Returns:
        SimulationResult
    """
    config = SimulationConfig(
        duration=duration_hours * 3600,
        time_step=time_step,
        **kwargs
    )

    simulator = MultiEnergySimulator(config)
    return simulator.run()


def run_scenario_simulation(scenario: str = "typical") -> SimulationResult:
    """
    运行预设场景仿真

    Args:
        scenario: 场景名称
            - "typical": 典型日
            - "high_renewable": 高新能源出力
            - "peak_load": 高负荷日
            - "low_wind": 低风速日

    Returns:
        SimulationResult
    """
    scenarios = {
        "typical": SimulationConfig(),
        "high_renewable": SimulationConfig(
            wind_capacity=80.0,
            solar_capacity=50.0
        ),
        "peak_load": SimulationConfig(
            base_load=400.0,
            load_peak_ratio=1.8
        ),
        "low_wind": SimulationConfig(
            wind_turbulence=0.05
        )
    }

    config = scenarios.get(scenario, SimulationConfig())
    simulator = MultiEnergySimulator(config)
    return simulator.run()
