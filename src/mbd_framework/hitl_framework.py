# -*- coding: utf-8 -*-
"""
HITL Framework - 人在环测试框架
Human-In-The-Loop Testing Framework

提供完整的人在环仿真和测试能力
包括人因模型、工作负荷评估、情景意识、决策支持和培训场景
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Tuple, Union
from datetime import datetime, timedelta
import time
import threading
import queue
import copy
import json


class OperatorRole(Enum):
    """操作员角色"""
    CONTROL_ROOM_OPERATOR = auto()      # 控制室操作员
    FIELD_OPERATOR = auto()             # 现场操作员
    SUPERVISOR = auto()                 # 主管/值班长
    MAINTENANCE = auto()                # 维护人员
    EMERGENCY_RESPONDER = auto()        # 应急响应人员


class WorkloadLevel(Enum):
    """工作负荷等级"""
    UNDERLOAD = 1               # 负荷不足
    LOW = 2                     # 低负荷
    OPTIMAL = 3                 # 最佳负荷
    HIGH = 4                    # 高负荷
    OVERLOAD = 5                # 过载


class SituationAwarenessLevel(Enum):
    """情景意识等级 (Endsley模型)"""
    PERCEPTION = 1              # 感知 - Level 1
    COMPREHENSION = 2           # 理解 - Level 2
    PROJECTION = 3              # 预测 - Level 3


class StressLevel(Enum):
    """压力等级"""
    RELAXED = 1                 # 放松
    ALERT = 2                   # 警觉
    MODERATE = 3                # 中等
    HIGH = 4                    # 高压
    EXTREME = 5                 # 极端


class ActionType(Enum):
    """操作类型"""
    MONITORING = auto()         # 监视
    PARAMETER_CHANGE = auto()   # 参数修改
    COMMAND_ISSUE = auto()      # 发送指令
    ALARM_ACKNOWLEDGE = auto()  # 报警确认
    MODE_CHANGE = auto()        # 模式切换
    EMERGENCY_ACTION = auto()   # 紧急操作
    COMMUNICATION = auto()      # 通信
    PROCEDURE_FOLLOW = auto()   # 执行规程


@dataclass
class OperatorAction:
    """操作员操作记录"""
    action_id: str                          # 操作ID
    timestamp: datetime                     # 时间戳
    operator_id: str                        # 操作员ID
    action_type: ActionType                 # 操作类型
    target: str                             # 操作目标
    value: Any = None                       # 操作值
    expected: bool = True                   # 是否预期操作
    response_time: float = 0.0              # 响应时间(秒)
    correct: bool = True                    # 是否正确
    context: Dict[str, Any] = field(default_factory=dict)  # 上下文


@dataclass
class AlarmInfo:
    """报警信息"""
    alarm_id: str                           # 报警ID
    timestamp: datetime                     # 触发时间
    priority: int                           # 优先级: 1(最高) - 4(最低)
    category: str                           # 类别
    message: str                            # 消息
    source: str                             # 来源
    acknowledged: bool = False              # 是否已确认
    acknowledged_by: Optional[str] = None   # 确认人
    acknowledged_time: Optional[datetime] = None
    cleared: bool = False                   # 是否已清除
    cleared_time: Optional[datetime] = None


@dataclass
class HumanFactorsMetrics:
    """人因指标"""
    # 工作负荷 (NASA-TLX维度)
    mental_demand: float = 0.0          # 脑力需求 (0-100)
    physical_demand: float = 0.0        # 体力需求 (0-100)
    temporal_demand: float = 0.0        # 时间压力 (0-100)
    performance: float = 0.0            # 绩效 (0-100)
    effort: float = 0.0                 # 努力程度 (0-100)
    frustration: float = 0.0            # 挫折感 (0-100)

    # 情景意识
    sa_perception: float = 0.0          # 感知得分
    sa_comprehension: float = 0.0       # 理解得分
    sa_projection: float = 0.0          # 预测得分

    # 响应性能
    avg_response_time: float = 0.0      # 平均响应时间
    error_rate: float = 0.0             # 错误率
    omission_rate: float = 0.0          # 遗漏率

    def calculate_overall_workload(self) -> float:
        """计算综合工作负荷 (NASA-TLX)"""
        # 简化的等权重计算
        return (self.mental_demand + self.physical_demand + self.temporal_demand +
                (100 - self.performance) + self.effort + self.frustration) / 6

    def calculate_sa_score(self) -> float:
        """计算综合情景意识得分"""
        return (self.sa_perception + self.sa_comprehension + self.sa_projection) / 3


class HumanFactorsModel:
    """人因模型"""

    def __init__(self, operator_id: str):
        self.operator_id = operator_id
        self.metrics = HumanFactorsMetrics()
        self.actions: List[OperatorAction] = []
        self.current_workload = WorkloadLevel.OPTIMAL
        self.current_stress = StressLevel.ALERT

        # 性能模型参数
        self.base_response_time = 2.0       # 基准响应时间(秒)
        self.fatigue_factor = 1.0           # 疲劳系数
        self.experience_factor = 1.0        # 经验系数
        self.workload_factor = 1.0          # 工作负荷系数

        # 时间追踪
        self.session_start: Optional[datetime] = None
        self.total_active_time = 0.0
        self.idle_time = 0.0

    def start_session(self):
        """开始会话"""
        self.session_start = datetime.now()
        self.actions = []

    def record_action(self, action: OperatorAction):
        """记录操作"""
        self.actions.append(action)
        self._update_metrics(action)

    def _update_metrics(self, action: OperatorAction):
        """更新指标"""
        # 更新响应时间
        if self.actions:
            response_times = [a.response_time for a in self.actions if a.response_time > 0]
            if response_times:
                self.metrics.avg_response_time = sum(response_times) / len(response_times)

        # 更新错误率
        total_actions = len(self.actions)
        if total_actions > 0:
            incorrect = sum(1 for a in self.actions if not a.correct)
            self.metrics.error_rate = incorrect / total_actions * 100

    def predict_response_time(self, task_complexity: float = 1.0) -> float:
        """预测响应时间"""
        # 基于多因素的响应时间预测
        rt = self.base_response_time * task_complexity
        rt *= self.fatigue_factor
        rt /= self.experience_factor
        rt *= self.workload_factor
        return rt

    def update_workload(self, active_alarms: int, active_tasks: int):
        """更新工作负荷评估"""
        # 简化的工作负荷模型
        load_score = active_alarms * 10 + active_tasks * 5

        if load_score < 10:
            self.current_workload = WorkloadLevel.UNDERLOAD
        elif load_score < 30:
            self.current_workload = WorkloadLevel.LOW
        elif load_score < 60:
            self.current_workload = WorkloadLevel.OPTIMAL
        elif load_score < 90:
            self.current_workload = WorkloadLevel.HIGH
        else:
            self.current_workload = WorkloadLevel.OVERLOAD

        self.workload_factor = 0.5 + load_score / 100

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        return {
            'operator_id': self.operator_id,
            'total_actions': len(self.actions),
            'avg_response_time': self.metrics.avg_response_time,
            'error_rate': self.metrics.error_rate,
            'workload_level': self.current_workload.name,
            'overall_workload': self.metrics.calculate_overall_workload(),
            'sa_score': self.metrics.calculate_sa_score()
        }


class WorkloadAssessment:
    """工作负荷评估器 - NASA-TLX方法"""

    def __init__(self):
        self.assessments: List[Dict] = []
        self.weights = {
            'mental': 1.0,
            'physical': 1.0,
            'temporal': 1.0,
            'performance': 1.0,
            'effort': 1.0,
            'frustration': 1.0
        }

    def set_weights(self, weights: Dict[str, float]):
        """设置维度权重"""
        self.weights.update(weights)

    def assess(self, metrics: HumanFactorsMetrics) -> Dict[str, Any]:
        """进行工作负荷评估"""
        # 加权计算
        weighted_scores = {
            'mental': metrics.mental_demand * self.weights['mental'],
            'physical': metrics.physical_demand * self.weights['physical'],
            'temporal': metrics.temporal_demand * self.weights['temporal'],
            'performance': (100 - metrics.performance) * self.weights['performance'],
            'effort': metrics.effort * self.weights['effort'],
            'frustration': metrics.frustration * self.weights['frustration']
        }

        total_weight = sum(self.weights.values())
        overall_score = sum(weighted_scores.values()) / total_weight

        # 确定等级
        if overall_score < 20:
            level = WorkloadLevel.UNDERLOAD
        elif overall_score < 40:
            level = WorkloadLevel.LOW
        elif overall_score < 60:
            level = WorkloadLevel.OPTIMAL
        elif overall_score < 80:
            level = WorkloadLevel.HIGH
        else:
            level = WorkloadLevel.OVERLOAD

        assessment = {
            'timestamp': datetime.now().isoformat(),
            'scores': weighted_scores,
            'overall_score': overall_score,
            'level': level.name,
            'recommendations': self._generate_recommendations(level)
        }

        self.assessments.append(assessment)
        return assessment

    def _generate_recommendations(self, level: WorkloadLevel) -> List[str]:
        """生成建议"""
        recommendations = []

        if level == WorkloadLevel.UNDERLOAD:
            recommendations.append("增加任务复杂度或监控范围")
            recommendations.append("考虑减少人员配置")

        elif level == WorkloadLevel.HIGH:
            recommendations.append("考虑任务重新分配")
            recommendations.append("启用自动化辅助功能")
            recommendations.append("增加休息间隔")

        elif level == WorkloadLevel.OVERLOAD:
            recommendations.append("立即重新分配任务")
            recommendations.append("减少低优先级任务")
            recommendations.append("请求支援人员")
            recommendations.append("启用紧急自动化模式")

        return recommendations


class SituationAwareness:
    """情景意识评估器 - Endsley模型"""

    def __init__(self):
        self.probes: List[Dict] = []            # SA探测问题
        self.responses: List[Dict] = []         # 响应记录
        self.scores: Dict[str, List[float]] = {
            'perception': [],
            'comprehension': [],
            'projection': []
        }

    def add_probe(self, level: SituationAwarenessLevel, question: str,
                 correct_answer: Any, context: Dict = None):
        """添加SA探测问题"""
        self.probes.append({
            'id': f"SA_PROBE_{len(self.probes)+1:03d}",
            'level': level,
            'question': question,
            'correct_answer': correct_answer,
            'context': context or {}
        })

    def evaluate_response(self, probe_id: str, response: Any,
                         response_time: float) -> Dict[str, Any]:
        """评估响应"""
        probe = next((p for p in self.probes if p['id'] == probe_id), None)
        if not probe:
            return {'error': 'Probe not found'}

        correct = response == probe['correct_answer']
        score = 100 if correct else 0

        # 根据响应时间调整得分
        if response_time > 30:  # 超过30秒
            score *= 0.5
        elif response_time > 15:
            score *= 0.75

        result = {
            'probe_id': probe_id,
            'level': probe['level'].name,
            'correct': correct,
            'score': score,
            'response_time': response_time,
            'timestamp': datetime.now().isoformat()
        }

        self.responses.append(result)

        # 更新得分
        level_key = probe['level'].name.lower()
        if level_key in self.scores:
            self.scores[level_key].append(score)

        return result

    def get_sa_summary(self) -> Dict[str, Any]:
        """获取SA摘要"""
        summary = {
            'total_probes': len(self.probes),
            'total_responses': len(self.responses),
            'level_scores': {},
            'overall_score': 0.0
        }

        for level, scores in self.scores.items():
            if scores:
                summary['level_scores'][level] = {
                    'count': len(scores),
                    'average': sum(scores) / len(scores),
                    'min': min(scores),
                    'max': max(scores)
                }

        # 计算总分
        all_scores = []
        for scores in self.scores.values():
            all_scores.extend(scores)
        if all_scores:
            summary['overall_score'] = sum(all_scores) / len(all_scores)

        return summary


class DecisionSupport:
    """决策支持系统"""

    def __init__(self):
        self.rules: Dict[str, Dict] = {}        # 决策规则
        self.recommendations: List[Dict] = []   # 建议历史
        self.pending_decisions: Dict[str, Dict] = {}

    def add_rule(self, rule_id: str, conditions: Dict[str, Any],
                actions: List[str], priority: int = 2):
        """添加决策规则"""
        self.rules[rule_id] = {
            'conditions': conditions,
            'actions': actions,
            'priority': priority
        }

    def evaluate(self, current_state: Dict[str, Any]) -> List[Dict]:
        """评估当前状态并生成建议"""
        recommendations = []

        for rule_id, rule in self.rules.items():
            if self._check_conditions(rule['conditions'], current_state):
                rec = {
                    'timestamp': datetime.now().isoformat(),
                    'rule_id': rule_id,
                    'priority': rule['priority'],
                    'actions': rule['actions'],
                    'state': current_state
                }
                recommendations.append(rec)

        # 按优先级排序
        recommendations.sort(key=lambda x: x['priority'])
        self.recommendations.extend(recommendations)

        return recommendations

    def _check_conditions(self, conditions: Dict[str, Any],
                         state: Dict[str, Any]) -> bool:
        """检查条件是否满足"""
        for param, condition in conditions.items():
            if param not in state:
                continue

            value = state[param]

            if isinstance(condition, dict):
                if 'min' in condition and value < condition['min']:
                    return False
                if 'max' in condition and value > condition['max']:
                    return False
                if 'equals' in condition and value != condition['equals']:
                    return False
            elif value != condition:
                return False

        return True

    def create_decision_point(self, decision_id: str, description: str,
                             options: List[Dict], deadline: float = None):
        """创建决策点"""
        self.pending_decisions[decision_id] = {
            'description': description,
            'options': options,
            'created': datetime.now(),
            'deadline': deadline,
            'resolved': False
        }

    def record_decision(self, decision_id: str, selected_option: str,
                       operator_id: str, rationale: str = ""):
        """记录决策"""
        if decision_id in self.pending_decisions:
            self.pending_decisions[decision_id].update({
                'resolved': True,
                'selected_option': selected_option,
                'operator_id': operator_id,
                'rationale': rationale,
                'resolved_time': datetime.now()
            })


@dataclass
class HITLScenario:
    """HITL测试场景"""
    scenario_id: str                        # 场景ID
    name: str                               # 名称
    description: str                        # 描述
    category: str = "NORMAL"                # 类别: NORMAL/ABNORMAL/EMERGENCY

    # 场景配置
    duration: float = 3600.0                # 持续时间(秒)
    time_scale: float = 1.0                 # 时间比例
    initial_state: Dict[str, Any] = field(default_factory=dict)

    # 事件序列
    events: List[Dict] = field(default_factory=list)  # 计划事件
    # event格式: {'time': float, 'type': str, 'params': dict}

    # 评估标准
    objectives: List[str] = field(default_factory=list)  # 目标
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    failure_criteria: Dict[str, Any] = field(default_factory=dict)

    # 关联
    requirements: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)  # 相关规程

    # 难度和培训
    difficulty_level: int = 2               # 难度: 1-5
    training_objectives: List[str] = field(default_factory=list)


class OperatorInterface:
    """操作员界面模拟"""

    def __init__(self, interface_id: str):
        self.interface_id = interface_id
        self.displays: Dict[str, Dict] = {}     # 显示内容
        self.controls: Dict[str, Dict] = {}     # 控制元素
        self.alarms: Dict[str, AlarmInfo] = {}  # 活动报警
        self.messages: List[Dict] = []          # 消息队列

        # 输入队列
        self._input_queue: queue.Queue = queue.Queue()
        self._output_queue: queue.Queue = queue.Queue()

    def update_display(self, display_id: str, content: Dict[str, Any]):
        """更新显示内容"""
        self.displays[display_id] = {
            'content': content,
            'updated': datetime.now()
        }

    def add_control(self, control_id: str, control_type: str,
                   config: Dict[str, Any]):
        """添加控制元素"""
        self.controls[control_id] = {
            'type': control_type,
            'config': config,
            'value': config.get('default', 0),
            'enabled': True
        }

    def trigger_alarm(self, alarm: AlarmInfo):
        """触发报警"""
        self.alarms[alarm.alarm_id] = alarm
        self._output_queue.put({
            'type': 'ALARM',
            'alarm': alarm
        })

    def acknowledge_alarm(self, alarm_id: str, operator_id: str) -> bool:
        """确认报警"""
        if alarm_id in self.alarms:
            alarm = self.alarms[alarm_id]
            alarm.acknowledged = True
            alarm.acknowledged_by = operator_id
            alarm.acknowledged_time = datetime.now()
            return True
        return False

    def clear_alarm(self, alarm_id: str) -> bool:
        """清除报警"""
        if alarm_id in self.alarms:
            alarm = self.alarms[alarm_id]
            alarm.cleared = True
            alarm.cleared_time = datetime.now()
            return True
        return False

    def send_message(self, message: str, priority: int = 2,
                    category: str = "INFO"):
        """发送消息"""
        msg = {
            'timestamp': datetime.now(),
            'message': message,
            'priority': priority,
            'category': category,
            'read': False
        }
        self.messages.append(msg)
        self._output_queue.put({
            'type': 'MESSAGE',
            'message': msg
        })

    def receive_input(self, control_id: str, value: Any) -> bool:
        """接收操作员输入"""
        if control_id in self.controls:
            self.controls[control_id]['value'] = value
            self._input_queue.put({
                'timestamp': datetime.now(),
                'control_id': control_id,
                'value': value
            })
            return True
        return False

    def get_pending_inputs(self) -> List[Dict]:
        """获取待处理的输入"""
        inputs = []
        while not self._input_queue.empty():
            try:
                inputs.append(self._input_queue.get_nowait())
            except queue.Empty:
                break
        return inputs

    def get_status(self) -> Dict[str, Any]:
        """获取界面状态"""
        return {
            'interface_id': self.interface_id,
            'active_alarms': len([a for a in self.alarms.values() if not a.cleared]),
            'unacknowledged_alarms': len([a for a in self.alarms.values()
                                          if not a.acknowledged]),
            'unread_messages': len([m for m in self.messages if not m['read']]),
            'controls': len(self.controls)
        }


class TrainingScenario(HITLScenario):
    """培训场景 - 扩展的HITL场景用于培训"""

    def __init__(self, scenario_id: str, name: str, description: str):
        super().__init__(scenario_id, name, description)
        self.category = "TRAINING"

        # 培训特定属性
        self.instructor_notes: List[str] = []
        self.learning_points: List[str] = []
        self.common_errors: List[str] = []
        self.hints: Dict[str, str] = {}         # 条件 -> 提示

        # 评分
        self.scoring_rubric: Dict[str, int] = {}  # 评分标准
        self.passing_score: float = 70.0

        # 进度追踪
        self.checkpoints: List[Dict] = []
        self.completion_status: Dict[str, bool] = {}


class HITLTestEnvironment:
    """HITL测试环境"""

    def __init__(self, env_id: str, name: str):
        self.env_id = env_id
        self.name = name

        # 组件
        self.operator_interfaces: Dict[str, OperatorInterface] = {}
        self.human_factors_models: Dict[str, HumanFactorsModel] = {}
        self.decision_support = DecisionSupport()
        self.workload_assessment = WorkloadAssessment()
        self.sa_assessment = SituationAwareness()

        # 仿真模型
        self.plant_model = None
        self.controller = None

        # 场景
        self.current_scenario: Optional[HITLScenario] = None
        self.scenario_time = 0.0
        self.scenario_running = False

        # 数据记录
        self.action_log: List[OperatorAction] = []
        self.event_log: List[Dict] = []
        self.state_history: List[Dict] = []

        # 线程
        self._running = False
        self._lock = threading.Lock()

    def add_operator_interface(self, interface: OperatorInterface):
        """添加操作员界面"""
        self.operator_interfaces[interface.interface_id] = interface

    def register_operator(self, operator_id: str, role: OperatorRole):
        """注册操作员"""
        self.human_factors_models[operator_id] = HumanFactorsModel(operator_id)

    def set_plant_model(self, model: Any):
        """设置被控对象模型"""
        self.plant_model = model

    def set_controller(self, controller: Any):
        """设置控制器"""
        self.controller = controller

    def load_scenario(self, scenario: HITLScenario):
        """加载场景"""
        self.current_scenario = scenario
        self.scenario_time = 0.0
        self._apply_initial_state(scenario.initial_state)
        self._log_event("SCENARIO_LOADED", f"Loaded scenario: {scenario.name}")

    def _apply_initial_state(self, initial_state: Dict[str, Any]):
        """应用初始状态"""
        if self.plant_model and hasattr(self.plant_model, 'set_state'):
            self.plant_model.set_state(initial_state)

    def start(self):
        """启动测试环境"""
        if not self.current_scenario:
            return False

        self._running = True
        self.scenario_running = True

        # 启动所有操作员会话
        for hf_model in self.human_factors_models.values():
            hf_model.start_session()

        self._log_event("STARTED", "HITL test environment started")
        return True

    def stop(self):
        """停止测试环境"""
        self._running = False
        self.scenario_running = False
        self._log_event("STOPPED", "HITL test environment stopped")

    def update(self, dt: float) -> Dict[str, Any]:
        """更新测试环境"""
        if not self.scenario_running:
            return {'status': 'not_running'}

        with self._lock:
            # 更新场景时间
            self.scenario_time += dt * self.current_scenario.time_scale

            # 处理计划事件
            self._process_scheduled_events()

            # 处理操作员输入
            self._process_operator_inputs()

            # 更新仿真模型
            if self.plant_model:
                if hasattr(self.plant_model, 'update'):
                    self.plant_model.update(dt)

            # 更新工作负荷
            self._update_workload_assessments()

            # 记录状态
            state = self._capture_state()
            self.state_history.append(state)

            # 检查场景结束条件
            if self.scenario_time >= self.current_scenario.duration:
                self.scenario_running = False
                self._log_event("SCENARIO_COMPLETE", "Scenario completed")

            return state

    def _process_scheduled_events(self):
        """处理计划事件"""
        if not self.current_scenario:
            return

        for event in self.current_scenario.events:
            event_time = event.get('time', 0)
            if event_time <= self.scenario_time and not event.get('triggered', False):
                self._trigger_event(event)
                event['triggered'] = True

    def _trigger_event(self, event: Dict):
        """触发事件"""
        event_type = event.get('type', '')
        params = event.get('params', {})

        self._log_event(f"EVENT_{event_type}", json.dumps(params))

        if event_type == 'ALARM':
            # 触发报警
            alarm = AlarmInfo(
                alarm_id=params.get('alarm_id', f"ALM_{self.scenario_time:.0f}"),
                timestamp=datetime.now(),
                priority=params.get('priority', 2),
                category=params.get('category', 'PROCESS'),
                message=params.get('message', ''),
                source=params.get('source', 'SYSTEM')
            )
            for interface in self.operator_interfaces.values():
                interface.trigger_alarm(alarm)

        elif event_type == 'PARAMETER_CHANGE':
            # 参数变化
            if self.plant_model and hasattr(self.plant_model, 'set_parameters'):
                self.plant_model.set_parameters(params)

        elif event_type == 'FAULT':
            # 故障注入
            if self.plant_model and hasattr(self.plant_model, 'inject_fault'):
                self.plant_model.inject_fault(params)

        elif event_type == 'MESSAGE':
            # 消息
            for interface in self.operator_interfaces.values():
                interface.send_message(
                    params.get('text', ''),
                    params.get('priority', 2),
                    params.get('category', 'INFO')
                )

    def _process_operator_inputs(self):
        """处理操作员输入"""
        for interface_id, interface in self.operator_interfaces.items():
            inputs = interface.get_pending_inputs()
            for input_data in inputs:
                action = OperatorAction(
                    action_id=f"ACT_{len(self.action_log)+1:06d}",
                    timestamp=input_data['timestamp'],
                    operator_id=interface_id,
                    action_type=ActionType.PARAMETER_CHANGE,
                    target=input_data['control_id'],
                    value=input_data['value']
                )
                self.action_log.append(action)

                # 记录到人因模型
                if interface_id in self.human_factors_models:
                    self.human_factors_models[interface_id].record_action(action)

    def _update_workload_assessments(self):
        """更新工作负荷评估"""
        for operator_id, hf_model in self.human_factors_models.items():
            # 计算活动报警数
            active_alarms = 0
            for interface in self.operator_interfaces.values():
                active_alarms += len([a for a in interface.alarms.values()
                                     if not a.acknowledged])

            hf_model.update_workload(active_alarms, len(self.action_log))

    def _capture_state(self) -> Dict[str, Any]:
        """捕获当前状态"""
        state = {
            'timestamp': datetime.now().isoformat(),
            'scenario_time': self.scenario_time,
            'plant_state': {},
            'operator_states': {}
        }

        if self.plant_model and hasattr(self.plant_model, 'get_states'):
            state['plant_state'] = self.plant_model.get_states()

        for op_id, hf_model in self.human_factors_models.items():
            state['operator_states'][op_id] = {
                'workload': hf_model.current_workload.name,
                'actions': len(hf_model.actions)
            }

        return state

    def _log_event(self, event_type: str, message: str):
        """记录事件"""
        self.event_log.append({
            'timestamp': datetime.now().isoformat(),
            'scenario_time': self.scenario_time,
            'type': event_type,
            'message': message
        })

    def generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        report = {
            'env_id': self.env_id,
            'scenario': self.current_scenario.name if self.current_scenario else None,
            'generated_at': datetime.now().isoformat(),
            'duration': self.scenario_time,
            'summary': {
                'total_actions': len(self.action_log),
                'total_events': len(self.event_log),
                'operators': len(self.human_factors_models)
            },
            'operator_performance': {},
            'workload_summary': {},
            'events': self.event_log,
            'recommendations': []
        }

        # 操作员性能
        for op_id, hf_model in self.human_factors_models.items():
            report['operator_performance'][op_id] = hf_model.get_performance_summary()

            # 工作负荷评估
            assessment = self.workload_assessment.assess(hf_model.metrics)
            report['workload_summary'][op_id] = assessment

        # SA评估
        report['sa_summary'] = self.sa_assessment.get_sa_summary()

        return report


# 预定义的水利系统HITL场景
def create_hydraulic_hitl_scenarios() -> List[HITLScenario]:
    """创建水利系统HITL测试场景"""
    scenarios = []

    # 场景1: 正常运行监控
    scenarios.append(HITLScenario(
        scenario_id="HITL_NORMAL_001",
        name="日常运行监控",
        description="测试操作员在正常运行条件下的监控能力",
        category="NORMAL",
        duration=1800.0,  # 30分钟
        initial_state={
            'system_mode': 'AUTO',
            'all_valves': 'NORMAL',
            'all_pumps': 'RUNNING'
        },
        events=[
            {'time': 300, 'type': 'PARAMETER_CHANGE', 'params': {'flow_setpoint': 1.1}},
            {'time': 600, 'type': 'MESSAGE', 'params': {'text': '例行检查提醒', 'priority': 3}},
            {'time': 900, 'type': 'PARAMETER_CHANGE', 'params': {'flow_setpoint': 0.9}}
        ],
        objectives=[
            "维持系统稳定运行",
            "及时响应参数变化",
            "完成例行监控任务"
        ],
        difficulty_level=1,
        training_objectives=["熟悉正常操作流程", "掌握基本监控技能"]
    ))

    # 场景2: 报警处理
    scenarios.append(HITLScenario(
        scenario_id="HITL_ALARM_001",
        name="多报警处理场景",
        description="测试操作员在多报警情况下的优先级判断和响应能力",
        category="ABNORMAL",
        duration=1200.0,  # 20分钟
        events=[
            {'time': 60, 'type': 'ALARM', 'params': {
                'alarm_id': 'ALM_001', 'priority': 3,
                'message': '泵房温度偏高', 'category': 'PROCESS'
            }},
            {'time': 120, 'type': 'ALARM', 'params': {
                'alarm_id': 'ALM_002', 'priority': 2,
                'message': '出口压力接近上限', 'category': 'PROCESS'
            }},
            {'time': 180, 'type': 'ALARM', 'params': {
                'alarm_id': 'ALM_003', 'priority': 1,
                'message': '阀门位置反馈异常', 'category': 'EQUIPMENT'
            }},
            {'time': 300, 'type': 'ALARM', 'params': {
                'alarm_id': 'ALM_004', 'priority': 2,
                'message': '流量波动', 'category': 'PROCESS'
            }}
        ],
        objectives=[
            "正确判断报警优先级",
            "在规定时间内确认所有报警",
            "采取适当的响应措施"
        ],
        success_criteria={
            'alarm_response_time': {'max': 60},  # 秒
            'all_alarms_acknowledged': True
        },
        difficulty_level=3,
        training_objectives=["报警优先级判断", "多任务处理能力"]
    ))

    # 场景3: 紧急停机
    scenarios.append(HITLScenario(
        scenario_id="HITL_EMERGENCY_001",
        name="紧急停机响应",
        description="测试操作员对突发紧急情况的响应能力",
        category="EMERGENCY",
        duration=600.0,  # 10分钟
        events=[
            {'time': 60, 'type': 'ALARM', 'params': {
                'alarm_id': 'ALM_EMERGENCY', 'priority': 1,
                'message': '管道压力急剧上升 - 疑似水锤', 'category': 'SAFETY'
            }},
            {'time': 65, 'type': 'FAULT', 'params': {
                'fault_type': 'PRESSURE_SURGE',
                'location': 'MAIN_PIPE',
                'severity': 'CRITICAL'
            }}
        ],
        objectives=[
            "在30秒内启动紧急程序",
            "正确执行紧急停机步骤",
            "通知相关人员"
        ],
        success_criteria={
            'emergency_response_time': {'max': 30},
            'correct_procedure': True
        },
        failure_criteria={
            'emergency_response_time': {'min': 60}
        },
        procedures=["EOP-001: 紧急停机程序"],
        difficulty_level=5,
        training_objectives=["紧急情况识别", "紧急程序执行", "压力管理"]
    ))

    return scenarios


def create_multi_energy_hitl_scenarios() -> List[HITLScenario]:
    """创建多能互补系统HITL测试场景"""
    scenarios = []

    # 场景1: 日常调度
    scenarios.append(HITLScenario(
        scenario_id="HITL_ME_DISPATCH_001",
        name="多能系统日常调度",
        description="测试调度员对多能互补系统的日常调度能力",
        category="NORMAL",
        duration=7200.0,  # 2小时 (代表一个调度周期)
        time_scale=10.0,  # 10倍速
        initial_state={
            'grid_frequency': 50.0,
            'wind_power': 200.0,
            'pv_power': 150.0,
            'load_demand': 400.0
        },
        events=[
            {'time': 600, 'type': 'PARAMETER_CHANGE', 'params': {'load_demand': 450}},
            {'time': 1200, 'type': 'PARAMETER_CHANGE', 'params': {'wind_power': 100}},
            {'time': 1800, 'type': 'PARAMETER_CHANGE', 'params': {'pv_power': 300}},
            {'time': 2400, 'type': 'MESSAGE', 'params': {
                'text': 'PSH启动调峰', 'priority': 2
            }}
        ],
        objectives=[
            "维持频率在49.8-50.2Hz范围内",
            "优化新能源消纳",
            "合理调度储能资源"
        ],
        difficulty_level=3
    ))

    # 场景2: 频率异常
    scenarios.append(HITLScenario(
        scenario_id="HITL_ME_FREQ_001",
        name="频率异常应急响应",
        description="测试调度员对电网频率异常的应急响应能力",
        category="EMERGENCY",
        duration=600.0,
        events=[
            {'time': 30, 'type': 'ALARM', 'params': {
                'alarm_id': 'FREQ_LOW', 'priority': 1,
                'message': '电网频率跌落 49.3Hz', 'category': 'GRID'
            }},
            {'time': 35, 'type': 'PARAMETER_CHANGE', 'params': {'grid_frequency': 49.3}}
        ],
        objectives=[
            "立即启动储能快速响应",
            "调整发电出力",
            "在2分钟内恢复频率"
        ],
        success_criteria={
            'frequency_recovery_time': {'max': 120}
        },
        difficulty_level=4
    ))

    return scenarios
