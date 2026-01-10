# -*- coding: utf-8 -*-
"""
抽水蓄能电站(PSH)状态机管理
Pumped Storage Hydropower State Machine Management

实现PSH运行模式的状态机管理，包括:
1. 模式切换约束(最短运行/停机时间、切换死区)
2. 状态转换逻辑
3. 调度决策接口
4. 调峰填谷策略

PSH调峰填谷策略说明:
========================
1. 午间光伏过剩期(11:00-15:00):
   - 新能源出力高峰,负荷相对平稳
   - PSH切换至"抽水"模式,吸收过剩电力
   - 将电能转化为势能储存

2. 晚高峰用电期(17:00-21:00):
   - 光伏出力骤降,负荷达到峰值
   - PSH切换至"发电"模式,释放储存能量
   - 填补新能源出力缺口

3. 夜间低谷期(23:00-06:00):
   - 负荷处于低谷,风电出力较好
   - PSH可进行"抽水"储能
   - 为次日高峰做准备

4. 模式切换决策:
   - 基于净负荷(负荷-新能源)预测
   - 考虑水库水位约束
   - 遵守最短运行时间/停机时间约束
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum, auto
from collections import deque


# ==================== 枚举定义 ====================

class PSHOperatingMode(Enum):
    """PSH运行模式"""
    STOPPED = "stopped"           # 停机
    PUMPING = "pumping"           # 抽水
    GENERATING = "generating"     # 发电
    SPINNING = "spinning"         # 调相(空转)


class PSHStateEvent(Enum):
    """状态转换事件"""
    START_PUMP = auto()       # 请求启动抽水
    START_GEN = auto()        # 请求启动发电
    STOP = auto()             # 请求停机
    EMERGENCY_STOP = auto()   # 紧急停机
    MODE_SWITCH = auto()      # 模式切换完成
    STARTUP_COMPLETE = auto() # 启动完成
    SHUTDOWN_COMPLETE = auto() # 停机完成


class PSHTransitionState(Enum):
    """过渡状态"""
    IDLE = "idle"                     # 空闲(可接受新指令)
    PUMP_STARTING = "pump_starting"   # 抽水启动中
    PUMP_STOPPING = "pump_stopping"   # 抽水停止中
    GEN_STARTING = "gen_starting"     # 发电启动中
    GEN_STOPPING = "gen_stopping"     # 发电停止中
    MODE_SWITCHING = "mode_switching" # 模式切换中
    EMERGENCY = "emergency"           # 紧急状态


# ==================== 约束参数 ====================

@dataclass
class PSHConstraints:
    """PSH运行约束参数"""
    # 时间约束
    min_run_time_pump: float = 1800.0    # 抽水最短运行时间(s) = 30min
    min_run_time_gen: float = 1200.0     # 发电最短运行时间(s) = 20min
    min_stop_time: float = 600.0         # 最短停机时间(s) = 10min
    mode_switch_deadband: float = 300.0  # 模式切换死区时间(s) = 5min

    # 启停时间
    startup_time_pump: float = 180.0     # 抽水启动时间(s) = 3min
    startup_time_gen: float = 120.0      # 发电启动时间(s) = 2min
    shutdown_time: float = 90.0          # 停机时间(s) = 1.5min

    # 水库约束
    reservoir_level_min: float = 0.15    # 最低水位(相对)
    reservoir_level_max: float = 0.95    # 最高水位(相对)
    level_margin: float = 0.05           # 水位余量

    # 功率约束
    min_power_ratio: float = 0.3         # 最小出力比(避免低效运行)
    ramp_rate_pump: float = 0.05         # 抽水爬坡速率(p.u./s)
    ramp_rate_gen: float = 0.08          # 发电爬坡速率(p.u./s)

    # 每日切换次数限制
    max_mode_switches_per_day: int = 6   # 每日最大模式切换次数

    def can_start_pump(self, reservoir_level: float) -> bool:
        """是否可以启动抽水"""
        return reservoir_level < self.reservoir_level_max - self.level_margin

    def can_start_gen(self, reservoir_level: float) -> bool:
        """是否可以启动发电"""
        return reservoir_level > self.reservoir_level_min + self.level_margin


# ==================== 状态机实现 ====================

@dataclass
class PSHStateInfo:
    """PSH状态信息"""
    operating_mode: PSHOperatingMode = PSHOperatingMode.STOPPED
    transition_state: PSHTransitionState = PSHTransitionState.IDLE
    mode_timer: float = 0.0           # 当前模式持续时间(s)
    transition_timer: float = 0.0     # 过渡状态计时器(s)
    power_setpoint: float = 0.0       # 功率设定值(MW)
    power_actual: float = 0.0         # 实际功率(MW)
    reservoir_level: float = 0.5      # 水库水位
    mode_switches_today: int = 0      # 今日模式切换次数
    last_switch_time: float = 0.0     # 上次切换时间


class PSHStateMachine:
    """
    抽水蓄能状态机

    状态转换图:
    ============

    STOPPED ----[START_PUMP]----> PUMP_STARTING ----> PUMPING
       ^                                                  |
       |                                                  |
       +<----------[STOP]-----------------------------<---+
       |                                                  |
       +<---[MODE_SWITCH via STOPPING]-----------------<--+
       |                                                  |
       v                                                  v
    STOPPED ----[START_GEN]-----> GEN_STARTING -----> GENERATING
       ^                                                  |
       |                                                  |
       +<----------[STOP]-----------------------------<---+

    PUMPING <--[MODE_SWITCH]--> GENERATING
             (需要先停机再切换)
    """

    def __init__(
        self,
        constraints: Optional[PSHConstraints] = None,
        rated_power_gen: float = 100.0,
        rated_power_pump: float = 90.0
    ):
        self.constraints = constraints or PSHConstraints()
        self.rated_power_gen = rated_power_gen
        self.rated_power_pump = rated_power_pump

        # 状态
        self.state = PSHStateInfo()

        # 目标模式(用于模式切换)
        self._target_mode: Optional[PSHOperatingMode] = None

        # 事件回调
        self._callbacks: Dict[str, List[Callable]] = {
            'on_mode_change': [],
            'on_transition_start': [],
            'on_transition_complete': [],
            'on_constraint_violation': []
        }

        # 调度决策历史
        self._decision_history: deque = deque(maxlen=1000)

    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _trigger_callbacks(self, event: str, **kwargs):
        """触发回调"""
        for callback in self._callbacks.get(event, []):
            callback(**kwargs)

    def get_state(self) -> PSHStateInfo:
        """获取当前状态"""
        return self.state

    def get_mode(self) -> PSHOperatingMode:
        """获取当前运行模式"""
        return self.state.operating_mode

    def is_in_transition(self) -> bool:
        """是否处于过渡状态"""
        return self.state.transition_state != PSHTransitionState.IDLE

    def can_accept_command(self) -> bool:
        """是否可接受新指令"""
        return (self.state.transition_state == PSHTransitionState.IDLE and
                self.state.transition_state != PSHTransitionState.EMERGENCY)

    def _check_min_run_time(self) -> bool:
        """检查最短运行时间约束"""
        mode = self.state.operating_mode
        timer = self.state.mode_timer

        if mode == PSHOperatingMode.PUMPING:
            return timer >= self.constraints.min_run_time_pump
        elif mode == PSHOperatingMode.GENERATING:
            return timer >= self.constraints.min_run_time_gen
        return True

    def _check_min_stop_time(self) -> bool:
        """检查最短停机时间约束"""
        if self.state.operating_mode == PSHOperatingMode.STOPPED:
            return self.state.mode_timer >= self.constraints.min_stop_time
        return True

    def _check_mode_switch_limit(self) -> bool:
        """检查每日模式切换次数限制"""
        return self.state.mode_switches_today < self.constraints.max_mode_switches_per_day

    def request_mode(
        self,
        target_mode: PSHOperatingMode,
        current_time: float = 0.0,
        force: bool = False
    ) -> Tuple[bool, str]:
        """
        请求切换到目标模式

        Args:
            target_mode: 目标运行模式
            current_time: 当前仿真时间(s)
            force: 是否强制切换(忽略部分约束)

        Returns:
            (是否接受请求, 原因描述)
        """
        current_mode = self.state.operating_mode

        # 已经是目标模式
        if current_mode == target_mode:
            return True, "Already in target mode"

        # 检查是否处于过渡状态
        if self.is_in_transition():
            return False, f"In transition: {self.state.transition_state.value}"

        # 检查约束
        if not force:
            # 最短运行时间
            if not self._check_min_run_time():
                remaining = 0
                if current_mode == PSHOperatingMode.PUMPING:
                    remaining = self.constraints.min_run_time_pump - self.state.mode_timer
                elif current_mode == PSHOperatingMode.GENERATING:
                    remaining = self.constraints.min_run_time_gen - self.state.mode_timer
                return False, f"Min run time not met, {remaining:.0f}s remaining"

            # 最短停机时间
            if current_mode == PSHOperatingMode.STOPPED:
                if not self._check_min_stop_time():
                    remaining = self.constraints.min_stop_time - self.state.mode_timer
                    return False, f"Min stop time not met, {remaining:.0f}s remaining"

            # 每日切换次数
            if not self._check_mode_switch_limit():
                return False, f"Daily mode switch limit reached ({self.constraints.max_mode_switches_per_day})"

            # 水库水位约束
            if target_mode == PSHOperatingMode.PUMPING:
                if not self.constraints.can_start_pump(self.state.reservoir_level):
                    return False, "Reservoir level too high for pumping"
            elif target_mode == PSHOperatingMode.GENERATING:
                if not self.constraints.can_start_gen(self.state.reservoir_level):
                    return False, "Reservoir level too low for generating"

        # 设置目标模式
        self._target_mode = target_mode

        # 根据当前模式确定过渡状态
        if current_mode == PSHOperatingMode.STOPPED:
            if target_mode == PSHOperatingMode.PUMPING:
                self.state.transition_state = PSHTransitionState.PUMP_STARTING
            elif target_mode == PSHOperatingMode.GENERATING:
                self.state.transition_state = PSHTransitionState.GEN_STARTING
        elif current_mode == PSHOperatingMode.PUMPING:
            if target_mode == PSHOperatingMode.STOPPED:
                self.state.transition_state = PSHTransitionState.PUMP_STOPPING
            elif target_mode == PSHOperatingMode.GENERATING:
                # 需要先停机再切换
                self.state.transition_state = PSHTransitionState.PUMP_STOPPING
        elif current_mode == PSHOperatingMode.GENERATING:
            if target_mode == PSHOperatingMode.STOPPED:
                self.state.transition_state = PSHTransitionState.GEN_STOPPING
            elif target_mode == PSHOperatingMode.PUMPING:
                # 需要先停机再切换
                self.state.transition_state = PSHTransitionState.GEN_STOPPING

        self.state.transition_timer = 0.0

        # 记录决策
        self._decision_history.append({
            'time': current_time,
            'from_mode': current_mode.value,
            'to_mode': target_mode.value,
            'accepted': True
        })

        self._trigger_callbacks(
            'on_transition_start',
            from_mode=current_mode,
            to_mode=target_mode,
            time=current_time
        )

        return True, f"Mode change initiated: {current_mode.value} -> {target_mode.value}"

    def emergency_stop(self) -> bool:
        """紧急停机"""
        self.state.transition_state = PSHTransitionState.EMERGENCY
        self._target_mode = PSHOperatingMode.STOPPED
        return True

    def update(self, dt: float, reservoir_level: float) -> PSHStateInfo:
        """
        更新状态机

        Args:
            dt: 时间步长(s)
            reservoir_level: 当前水库水位

        Returns:
            更新后的状态
        """
        self.state.reservoir_level = reservoir_level
        self.state.mode_timer += dt

        # 处理过渡状态
        if self.state.transition_state != PSHTransitionState.IDLE:
            self.state.transition_timer += dt
            self._process_transition()

        return self.state

    def _process_transition(self):
        """处理过渡状态"""
        trans = self.state.transition_state
        timer = self.state.transition_timer
        target = self._target_mode

        if trans == PSHTransitionState.PUMP_STARTING:
            if timer >= self.constraints.startup_time_pump:
                self._complete_transition(PSHOperatingMode.PUMPING)

        elif trans == PSHTransitionState.GEN_STARTING:
            if timer >= self.constraints.startup_time_gen:
                self._complete_transition(PSHOperatingMode.GENERATING)

        elif trans == PSHTransitionState.PUMP_STOPPING:
            if timer >= self.constraints.shutdown_time:
                if target == PSHOperatingMode.GENERATING:
                    # 切换到发电需要先进入模式切换状态
                    self.state.transition_state = PSHTransitionState.MODE_SWITCHING
                    self.state.transition_timer = 0.0
                    self.state.operating_mode = PSHOperatingMode.STOPPED
                    self.state.mode_timer = 0.0
                else:
                    self._complete_transition(PSHOperatingMode.STOPPED)

        elif trans == PSHTransitionState.GEN_STOPPING:
            if timer >= self.constraints.shutdown_time:
                if target == PSHOperatingMode.PUMPING:
                    self.state.transition_state = PSHTransitionState.MODE_SWITCHING
                    self.state.transition_timer = 0.0
                    self.state.operating_mode = PSHOperatingMode.STOPPED
                    self.state.mode_timer = 0.0
                else:
                    self._complete_transition(PSHOperatingMode.STOPPED)

        elif trans == PSHTransitionState.MODE_SWITCHING:
            if timer >= self.constraints.mode_switch_deadband:
                # 开始启动目标模式
                if target == PSHOperatingMode.PUMPING:
                    self.state.transition_state = PSHTransitionState.PUMP_STARTING
                elif target == PSHOperatingMode.GENERATING:
                    self.state.transition_state = PSHTransitionState.GEN_STARTING
                self.state.transition_timer = 0.0

        elif trans == PSHTransitionState.EMERGENCY:
            if timer >= self.constraints.shutdown_time / 2:  # 紧急停机更快
                self._complete_transition(PSHOperatingMode.STOPPED)

    def _complete_transition(self, new_mode: PSHOperatingMode):
        """完成过渡"""
        old_mode = self.state.operating_mode

        self.state.operating_mode = new_mode
        self.state.transition_state = PSHTransitionState.IDLE
        self.state.transition_timer = 0.0
        self.state.mode_timer = 0.0
        self._target_mode = None

        # 更新切换计数
        if old_mode != new_mode and new_mode != PSHOperatingMode.STOPPED:
            self.state.mode_switches_today += 1

        self._trigger_callbacks(
            'on_mode_change',
            old_mode=old_mode,
            new_mode=new_mode
        )
        self._trigger_callbacks('on_transition_complete', new_mode=new_mode)

    def reset_daily_counters(self):
        """重置每日计数器"""
        self.state.mode_switches_today = 0

    def get_transition_progress(self) -> float:
        """
        获取过渡进度(0-1)
        """
        trans = self.state.transition_state
        timer = self.state.transition_timer

        if trans == PSHTransitionState.IDLE:
            return 1.0

        if trans == PSHTransitionState.PUMP_STARTING:
            return min(1.0, timer / self.constraints.startup_time_pump)
        elif trans == PSHTransitionState.GEN_STARTING:
            return min(1.0, timer / self.constraints.startup_time_gen)
        elif trans in [PSHTransitionState.PUMP_STOPPING, PSHTransitionState.GEN_STOPPING]:
            return min(1.0, timer / self.constraints.shutdown_time)
        elif trans == PSHTransitionState.MODE_SWITCHING:
            return min(1.0, timer / self.constraints.mode_switch_deadband)
        elif trans == PSHTransitionState.EMERGENCY:
            return min(1.0, timer / (self.constraints.shutdown_time / 2))

        return 0.0

    def get_time_to_available(self) -> float:
        """
        获取到可调度状态的剩余时间

        Returns:
            剩余时间(s), 0表示已可调度
        """
        trans = self.state.transition_state
        timer = self.state.transition_timer

        if trans == PSHTransitionState.IDLE:
            return 0.0

        if trans == PSHTransitionState.PUMP_STARTING:
            return max(0, self.constraints.startup_time_pump - timer)
        elif trans == PSHTransitionState.GEN_STARTING:
            return max(0, self.constraints.startup_time_gen - timer)
        elif trans in [PSHTransitionState.PUMP_STOPPING, PSHTransitionState.GEN_STOPPING]:
            remaining_stop = max(0, self.constraints.shutdown_time - timer)
            if self._target_mode in [PSHOperatingMode.PUMPING, PSHOperatingMode.GENERATING]:
                # 还需要模式切换和启动
                remaining_stop += self.constraints.mode_switch_deadband
                if self._target_mode == PSHOperatingMode.PUMPING:
                    remaining_stop += self.constraints.startup_time_pump
                else:
                    remaining_stop += self.constraints.startup_time_gen
            return remaining_stop
        elif trans == PSHTransitionState.MODE_SWITCHING:
            remaining = max(0, self.constraints.mode_switch_deadband - timer)
            if self._target_mode == PSHOperatingMode.PUMPING:
                remaining += self.constraints.startup_time_pump
            elif self._target_mode == PSHOperatingMode.GENERATING:
                remaining += self.constraints.startup_time_gen
            return remaining

        return 0.0


# ==================== 调度决策器 ====================

class PSHDispatchDecision(Enum):
    """调度决策"""
    HOLD = "hold"              # 保持当前状态
    START_PUMPING = "pump"     # 启动抽水
    START_GENERATING = "gen"   # 启动发电
    STOP = "stop"              # 停机


@dataclass
class DispatchContext:
    """调度上下文"""
    current_time: float              # 当前时间(s)
    hour_of_day: float               # 一天中的小时数(0-24)
    net_load: float                  # 净负荷 = 负荷 - 新能源(MW)
    net_load_forecast: List[float]   # 净负荷预测序列
    reservoir_level: float           # 水库水位
    current_mode: PSHOperatingMode   # 当前模式
    frequency_deviation: float = 0.0  # 频率偏差(Hz)
    price: float = 0.0               # 电价(可选)


class PSHDispatcher:
    """
    PSH调度决策器

    实现基于规则和预测的调峰填谷决策:

    决策规则:
    =========
    1. 净负荷 > 阈值_high 且 水位充足 -> 发电
    2. 净负荷 < 阈值_low 且 水位未满 -> 抽水
    3. 午间时段(11-15) 且 光伏过剩 -> 优先抽水
    4. 晚高峰(17-21) -> 优先发电
    5. 夜间低谷(23-6) 且 风电过剩 -> 可以抽水
    """

    def __init__(
        self,
        rated_power_gen: float = 100.0,
        rated_power_pump: float = 90.0,
        net_load_threshold_high: float = 50.0,   # 高负荷阈值(MW)
        net_load_threshold_low: float = -30.0,   # 低负荷阈值(MW, 负值表示过剩)
        hysteresis: float = 10.0                 # 迟滞带(MW)
    ):
        self.rated_power_gen = rated_power_gen
        self.rated_power_pump = rated_power_pump
        self.threshold_high = net_load_threshold_high
        self.threshold_low = net_load_threshold_low
        self.hysteresis = hysteresis

        # 决策历史
        self._last_decision = PSHDispatchDecision.HOLD
        self._decision_count = 0

    def _get_time_period(self, hour: float) -> str:
        """判断时段"""
        if 11 <= hour < 15:
            return "noon_peak_solar"  # 午间光伏高峰
        elif 17 <= hour < 21:
            return "evening_peak_load"  # 晚间负荷高峰
        elif 23 <= hour or hour < 6:
            return "night_valley"  # 夜间低谷
        else:
            return "transition"  # 过渡时段

    def decide(self, context: DispatchContext) -> Tuple[PSHDispatchDecision, float, str]:
        """
        做出调度决策

        Args:
            context: 调度上下文

        Returns:
            (决策, 建议功率, 决策原因)
        """
        mode = context.current_mode
        net_load = context.net_load
        level = context.reservoir_level
        hour = context.hour_of_day
        period = self._get_time_period(hour)

        # 基础决策逻辑
        decision = PSHDispatchDecision.HOLD
        power = 0.0
        reason = ""

        # 水位约束检查
        can_pump = level < 0.9
        can_gen = level > 0.2

        # 紧急频率响应
        if abs(context.frequency_deviation) > 0.2:  # 超过0.2Hz
            if context.frequency_deviation < -0.2 and can_gen:
                decision = PSHDispatchDecision.START_GENERATING
                power = self.rated_power_gen * min(1.0, abs(context.frequency_deviation) / 0.5)
                reason = f"Emergency frequency support: Δf={context.frequency_deviation:.2f}Hz"
                return decision, power, reason

        # 时段策略
        if period == "noon_peak_solar":
            # 午间: 优先抽水吸收光伏
            if net_load < self.threshold_low and can_pump:
                decision = PSHDispatchDecision.START_PUMPING
                power = min(self.rated_power_pump, abs(net_load - self.threshold_low))
                reason = f"Noon solar excess absorption: net_load={net_load:.1f}MW"
            elif mode == PSHOperatingMode.GENERATING:
                decision = PSHDispatchDecision.STOP
                reason = "Stop generating during solar peak"

        elif period == "evening_peak_load":
            # 晚高峰: 优先发电填谷
            if net_load > self.threshold_high and can_gen:
                decision = PSHDispatchDecision.START_GENERATING
                power = min(self.rated_power_gen, net_load - self.threshold_high)
                reason = f"Evening peak shaving: net_load={net_load:.1f}MW"
            elif mode == PSHOperatingMode.PUMPING:
                decision = PSHDispatchDecision.STOP
                reason = "Stop pumping during load peak"

        elif period == "night_valley":
            # 夜间: 可抽水储能
            if net_load < self.threshold_low and can_pump:
                decision = PSHDispatchDecision.START_PUMPING
                power = min(self.rated_power_pump, abs(net_load - self.threshold_low) * 0.7)
                reason = f"Night valley storage: net_load={net_load:.1f}MW"

        else:  # transition
            # 过渡时段: 基于净负荷决策
            if net_load > self.threshold_high + self.hysteresis and can_gen:
                decision = PSHDispatchDecision.START_GENERATING
                power = min(self.rated_power_gen, net_load - self.threshold_high)
                reason = f"Transition period generation: net_load={net_load:.1f}MW"
            elif net_load < self.threshold_low - self.hysteresis and can_pump:
                decision = PSHDispatchDecision.START_PUMPING
                power = min(self.rated_power_pump, abs(net_load - self.threshold_low))
                reason = f"Transition period pumping: net_load={net_load:.1f}MW"

        # 应用迟滞(防止频繁切换)
        if decision != PSHDispatchDecision.HOLD:
            if decision == self._last_decision:
                pass  # 保持决策
            else:
                self._decision_count += 1
                self._last_decision = decision

        if decision == PSHDispatchDecision.HOLD:
            # 保持当前功率
            if mode == PSHOperatingMode.GENERATING:
                power = context.net_load if context.net_load > 0 else 0
            elif mode == PSHOperatingMode.PUMPING:
                power = abs(context.net_load) if context.net_load < 0 else 0
            reason = reason or "Holding current state"

        return decision, power, reason

    def get_dispatch_schedule(
        self,
        net_load_forecast: List[float],
        reservoir_level: float,
        time_resolution: float = 3600.0  # 1小时
    ) -> List[Dict]:
        """
        生成调度计划

        Args:
            net_load_forecast: 未来净负荷预测(MW)
            reservoir_level: 当前水位
            time_resolution: 时间分辨率(s)

        Returns:
            调度计划列表
        """
        schedule = []
        level = reservoir_level

        for i, net_load in enumerate(net_load_forecast):
            hour = (i * time_resolution / 3600) % 24

            context = DispatchContext(
                current_time=i * time_resolution,
                hour_of_day=hour,
                net_load=net_load,
                net_load_forecast=net_load_forecast[i:],
                reservoir_level=level,
                current_mode=PSHOperatingMode.STOPPED  # 规划时假设可自由调度
            )

            decision, power, reason = self.decide(context)

            # 更新预测水位
            if decision == PSHDispatchDecision.START_PUMPING:
                level += power * time_resolution / 3600 / 1000  # 简化水位变化
            elif decision == PSHDispatchDecision.START_GENERATING:
                level -= power * time_resolution / 3600 / 1000

            level = np.clip(level, 0.1, 1.0)

            schedule.append({
                'time_index': i,
                'hour': hour,
                'net_load': net_load,
                'decision': decision.value,
                'power': power,
                'reservoir_level': level,
                'reason': reason
            })

        return schedule
