# -*- coding: utf-8 -*-
"""
MBD Core - 模型驱动设计核心框架
Model-Based Design Core Framework

实现V模型开发流程、需求追溯、模型验证和代码生成
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Optional, Any, Callable, Set, Tuple
from datetime import datetime
import hashlib
import json
import copy


class VModelPhase(Enum):
    """V模型开发阶段"""
    # 左侧分支 - 开发阶段
    REQUIREMENTS = auto()           # 需求分析
    SYSTEM_DESIGN = auto()          # 系统设计
    ARCHITECTURE_DESIGN = auto()    # 架构设计
    DETAILED_DESIGN = auto()        # 详细设计
    IMPLEMENTATION = auto()         # 实现/编码

    # 右侧分支 - 验证阶段
    UNIT_TEST = auto()              # 单元测试
    INTEGRATION_TEST = auto()       # 集成测试
    SYSTEM_TEST = auto()            # 系统测试
    ACCEPTANCE_TEST = auto()        # 验收测试


class ModelType(Enum):
    """模型类型"""
    PLANT = auto()              # 被控对象模型
    CONTROLLER = auto()         # 控制器模型
    SENSOR = auto()             # 传感器模型
    ACTUATOR = auto()           # 执行器模型
    ENVIRONMENT = auto()        # 环境模型
    FAULT = auto()              # 故障模型
    HUMAN = auto()              # 人员模型
    INTERFACE = auto()          # 接口模型


class VerificationStatus(Enum):
    """验证状态"""
    NOT_VERIFIED = auto()       # 未验证
    IN_PROGRESS = auto()        # 验证中
    PASSED = auto()             # 通过
    FAILED = auto()             # 失败
    BLOCKED = auto()            # 阻塞
    WAIVED = auto()             # 豁免


@dataclass
class RequirementTrace:
    """需求追溯记录"""
    requirement_id: str                     # 需求ID
    requirement_text: str                   # 需求描述
    source: str                             # 需求来源
    priority: str = "MEDIUM"                # 优先级: HIGH/MEDIUM/LOW
    safety_related: bool = False            # 是否安全相关
    asil_level: Optional[str] = None        # ASIL等级
    derived_requirements: List[str] = field(default_factory=list)  # 派生需求
    parent_requirement: Optional[str] = None  # 父需求
    verification_method: str = "TEST"       # 验证方法: TEST/ANALYSIS/INSPECTION/DEMO
    verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    test_cases: List[str] = field(default_factory=list)  # 关联测试用例
    design_items: List[str] = field(default_factory=list)  # 关联设计项
    created_date: datetime = field(default_factory=datetime.now)
    modified_date: datetime = field(default_factory=datetime.now)

    def add_test_case(self, test_case_id: str):
        """添加关联测试用例"""
        if test_case_id not in self.test_cases:
            self.test_cases.append(test_case_id)
            self.modified_date = datetime.now()

    def add_design_item(self, design_item_id: str):
        """添加关联设计项"""
        if design_item_id not in self.design_items:
            self.design_items.append(design_item_id)
            self.modified_date = datetime.now()

    def is_fully_traced(self) -> bool:
        """检查是否完全追溯"""
        return len(self.test_cases) > 0 and len(self.design_items) > 0


@dataclass
class DesignSpecification:
    """设计规格说明"""
    spec_id: str                            # 规格ID
    name: str                               # 名称
    description: str                        # 描述
    phase: VModelPhase                      # 所属阶段
    parent_spec: Optional[str] = None       # 父规格
    child_specs: List[str] = field(default_factory=list)  # 子规格
    requirements: List[str] = field(default_factory=list)  # 关联需求
    inputs: Dict[str, Any] = field(default_factory=dict)   # 输入定义
    outputs: Dict[str, Any] = field(default_factory=dict)  # 输出定义
    constraints: List[str] = field(default_factory=list)   # 约束条件
    assumptions: List[str] = field(default_factory=list)   # 假设条件
    interfaces: List[str] = field(default_factory=list)    # 接口定义
    version: str = "1.0"
    status: str = "DRAFT"                   # DRAFT/REVIEW/APPROVED/OBSOLETE

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'spec_id': self.spec_id,
            'name': self.name,
            'description': self.description,
            'phase': self.phase.name,
            'requirements': self.requirements,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'constraints': self.constraints,
            'version': self.version,
            'status': self.status
        }


@dataclass
class ModelArtifact:
    """模型工件"""
    artifact_id: str                        # 工件ID
    name: str                               # 名称
    model_type: ModelType                   # 模型类型
    version: str = "1.0"                    # 版本
    description: str = ""                   # 描述
    parameters: Dict[str, Any] = field(default_factory=dict)  # 参数
    inputs: List[str] = field(default_factory=list)           # 输入端口
    outputs: List[str] = field(default_factory=list)          # 输出端口
    states: List[str] = field(default_factory=list)           # 状态变量
    equations: List[str] = field(default_factory=list)        # 方程/算法
    requirements: List[str] = field(default_factory=list)     # 关联需求
    verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    checksum: str = ""                      # 校验和
    created_date: datetime = field(default_factory=datetime.now)
    modified_date: datetime = field(default_factory=datetime.now)

    def compute_checksum(self) -> str:
        """计算模型校验和"""
        content = json.dumps({
            'parameters': self.parameters,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'states': self.states,
            'equations': self.equations
        }, sort_keys=True)
        self.checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        return self.checksum

    def has_changed(self) -> bool:
        """检查模型是否已更改"""
        old_checksum = self.checksum
        new_checksum = self.compute_checksum()
        return old_checksum != new_checksum


class MBDModel(ABC):
    """MBD模型基类"""

    def __init__(self, model_id: str, name: str, model_type: ModelType):
        self.model_id = model_id
        self.name = name
        self.model_type = model_type
        self.version = "1.0"
        self.artifact = ModelArtifact(
            artifact_id=f"{model_id}_artifact",
            name=name,
            model_type=model_type
        )
        self._inputs: Dict[str, Any] = {}
        self._outputs: Dict[str, Any] = {}
        self._states: Dict[str, Any] = {}
        self._parameters: Dict[str, Any] = {}
        self._time: float = 0.0
        self._dt: float = 0.001

    @abstractmethod
    def initialize(self) -> None:
        """初始化模型"""
        pass

    @abstractmethod
    def update(self, dt: float) -> None:
        """更新模型状态"""
        pass

    @abstractmethod
    def get_outputs(self) -> Dict[str, Any]:
        """获取输出"""
        pass

    def set_inputs(self, inputs: Dict[str, Any]) -> None:
        """设置输入"""
        self._inputs.update(inputs)

    def get_states(self) -> Dict[str, Any]:
        """获取状态"""
        return copy.deepcopy(self._states)

    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """设置参数"""
        self._parameters.update(parameters)
        self.artifact.parameters = self._parameters
        self.artifact.modified_date = datetime.now()

    def reset(self) -> None:
        """重置模型"""
        self._time = 0.0
        self.initialize()

    def step(self, inputs: Dict[str, Any] = None, dt: float = None) -> Dict[str, Any]:
        """执行一步仿真"""
        if inputs:
            self.set_inputs(inputs)
        if dt is None:
            dt = self._dt
        self.update(dt)
        self._time += dt
        return self.get_outputs()


class ModelValidator:
    """模型验证器"""

    def __init__(self):
        self.validation_results: List[Dict] = []
        self.validation_rules: Dict[str, Callable] = {}

    def add_rule(self, rule_name: str, rule_func: Callable[[MBDModel], Tuple[bool, str]]):
        """添加验证规则"""
        self.validation_rules[rule_name] = rule_func

    def validate_model(self, model: MBDModel) -> Dict[str, Any]:
        """验证模型"""
        results = {
            'model_id': model.model_id,
            'model_name': model.name,
            'timestamp': datetime.now().isoformat(),
            'rules_passed': [],
            'rules_failed': [],
            'overall_status': True
        }

        for rule_name, rule_func in self.validation_rules.items():
            try:
                passed, message = rule_func(model)
                if passed:
                    results['rules_passed'].append({'rule': rule_name, 'message': message})
                else:
                    results['rules_failed'].append({'rule': rule_name, 'message': message})
                    results['overall_status'] = False
            except Exception as e:
                results['rules_failed'].append({
                    'rule': rule_name,
                    'message': f"Exception: {str(e)}"
                })
                results['overall_status'] = False

        self.validation_results.append(results)
        return results

    def validate_consistency(self, model: MBDModel, spec: DesignSpecification) -> Dict[str, Any]:
        """验证模型与规格一致性"""
        results = {
            'model_id': model.model_id,
            'spec_id': spec.spec_id,
            'timestamp': datetime.now().isoformat(),
            'input_consistency': True,
            'output_consistency': True,
            'constraint_violations': [],
            'messages': []
        }

        # 检查输入一致性
        model_inputs = set(model.artifact.inputs)
        spec_inputs = set(spec.inputs.keys())
        if model_inputs != spec_inputs:
            results['input_consistency'] = False
            results['messages'].append(
                f"Input mismatch: Model has {model_inputs}, Spec expects {spec_inputs}"
            )

        # 检查输出一致性
        model_outputs = set(model.artifact.outputs)
        spec_outputs = set(spec.outputs.keys())
        if model_outputs != spec_outputs:
            results['output_consistency'] = False
            results['messages'].append(
                f"Output mismatch: Model has {model_outputs}, Spec expects {spec_outputs}"
            )

        return results


class CodeGenerator:
    """代码生成器"""

    def __init__(self):
        self.templates: Dict[str, str] = {}
        self.generated_code: List[Dict] = []

    def register_template(self, template_name: str, template_content: str):
        """注册代码模板"""
        self.templates[template_name] = template_content

    def generate_controller_code(self, model: MBDModel, language: str = "python") -> str:
        """生成控制器代码"""
        if language == "python":
            return self._generate_python_controller(model)
        elif language == "c":
            return self._generate_c_controller(model)
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _generate_python_controller(self, model: MBDModel) -> str:
        """生成Python控制器代码"""
        code = f'''# -*- coding: utf-8 -*-
"""
Auto-generated controller code from MBD model
Model ID: {model.model_id}
Model Name: {model.name}
Generated: {datetime.now().isoformat()}
"""

class {model.name.replace(" ", "")}Controller:
    """Auto-generated controller class"""

    def __init__(self):
        # Parameters
        self.parameters = {model._parameters}

        # States
        self.states = {model._states}

        # Initialize
        self.initialized = False

    def initialize(self):
        """Initialize controller"""
        self.initialized = True

    def update(self, inputs: dict, dt: float) -> dict:
        """Update controller outputs"""
        outputs = {{}}
        # TODO: Implement control logic from model
        return outputs

    def reset(self):
        """Reset controller to initial state"""
        self.initialized = False
        self.initialize()
'''
        self.generated_code.append({
            'model_id': model.model_id,
            'language': 'python',
            'timestamp': datetime.now().isoformat(),
            'code': code
        })
        return code

    def _generate_c_controller(self, model: MBDModel) -> str:
        """生成C语言控制器代码"""
        code = f'''/*
 * Auto-generated controller code from MBD model
 * Model ID: {model.model_id}
 * Model Name: {model.name}
 * Generated: {datetime.now().isoformat()}
 */

#ifndef {model.name.upper().replace(" ", "_")}_CONTROLLER_H
#define {model.name.upper().replace(" ", "_")}_CONTROLLER_H

typedef struct {{
    // Parameters
    double param1;
    double param2;

    // States
    double state1;
    double state2;

    // Flags
    int initialized;
}} {model.name.replace(" ", "")}Controller_t;

void {model.name.replace(" ", "")}_Init({model.name.replace(" ", "")}Controller_t* ctrl);
void {model.name.replace(" ", "")}_Update({model.name.replace(" ", "")}Controller_t* ctrl, double dt);
void {model.name.replace(" ", "")}_Reset({model.name.replace(" ", "")}Controller_t* ctrl);

#endif
'''
        self.generated_code.append({
            'model_id': model.model_id,
            'language': 'c',
            'timestamp': datetime.now().isoformat(),
            'code': code
        })
        return code


class MBDWorkflow:
    """MBD工作流管理器"""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.current_phase = VModelPhase.REQUIREMENTS
        self.requirements: Dict[str, RequirementTrace] = {}
        self.specifications: Dict[str, DesignSpecification] = {}
        self.models: Dict[str, MBDModel] = {}
        self.artifacts: Dict[str, ModelArtifact] = {}
        self.phase_history: List[Dict] = []
        self.traceability_matrix: Dict[str, Set[str]] = {}

    def add_requirement(self, req: RequirementTrace) -> None:
        """添加需求"""
        self.requirements[req.requirement_id] = req
        self.traceability_matrix[req.requirement_id] = set()

    def add_specification(self, spec: DesignSpecification) -> None:
        """添加设计规格"""
        self.specifications[spec.spec_id] = spec
        # 更新追溯矩阵
        for req_id in spec.requirements:
            if req_id in self.traceability_matrix:
                self.traceability_matrix[req_id].add(spec.spec_id)

    def register_model(self, model: MBDModel) -> None:
        """注册模型"""
        self.models[model.model_id] = model
        self.artifacts[model.artifact.artifact_id] = model.artifact

    def advance_phase(self, next_phase: VModelPhase) -> bool:
        """推进到下一阶段"""
        # 记录阶段历史
        self.phase_history.append({
            'from_phase': self.current_phase.name,
            'to_phase': next_phase.name,
            'timestamp': datetime.now().isoformat()
        })
        self.current_phase = next_phase
        return True

    def get_phase_status(self) -> Dict[str, Any]:
        """获取当前阶段状态"""
        return {
            'project': self.project_name,
            'current_phase': self.current_phase.name,
            'requirements_count': len(self.requirements),
            'specifications_count': len(self.specifications),
            'models_count': len(self.models),
            'phase_history': self.phase_history
        }

    def generate_traceability_report(self) -> Dict[str, Any]:
        """生成追溯报告"""
        report = {
            'project': self.project_name,
            'generated_at': datetime.now().isoformat(),
            'requirements_coverage': {},
            'orphan_requirements': [],
            'orphan_specs': []
        }

        # 检查需求覆盖
        for req_id, req in self.requirements.items():
            traced_items = self.traceability_matrix.get(req_id, set())
            report['requirements_coverage'][req_id] = {
                'text': req.requirement_text,
                'traced_to': list(traced_items),
                'test_cases': req.test_cases,
                'is_covered': len(traced_items) > 0 and len(req.test_cases) > 0
            }
            if not report['requirements_coverage'][req_id]['is_covered']:
                report['orphan_requirements'].append(req_id)

        # 检查孤立规格
        all_traced_specs = set()
        for traced in self.traceability_matrix.values():
            all_traced_specs.update(traced)

        for spec_id in self.specifications:
            if spec_id not in all_traced_specs:
                report['orphan_specs'].append(spec_id)

        return report

    def validate_phase_gate(self, phase: VModelPhase) -> Dict[str, Any]:
        """验证阶段门检查"""
        gate_check = {
            'phase': phase.name,
            'timestamp': datetime.now().isoformat(),
            'checks_passed': [],
            'checks_failed': [],
            'can_proceed': True
        }

        if phase == VModelPhase.REQUIREMENTS:
            # 需求阶段检查
            if len(self.requirements) == 0:
                gate_check['checks_failed'].append("No requirements defined")
                gate_check['can_proceed'] = False
            else:
                gate_check['checks_passed'].append(
                    f"{len(self.requirements)} requirements defined"
                )

        elif phase == VModelPhase.SYSTEM_DESIGN:
            # 系统设计阶段检查
            traced_reqs = sum(1 for r in self.requirements.values()
                             if len(r.design_items) > 0)
            if traced_reqs < len(self.requirements):
                gate_check['checks_failed'].append(
                    f"Only {traced_reqs}/{len(self.requirements)} requirements traced to design"
                )
                gate_check['can_proceed'] = False

        elif phase == VModelPhase.ACCEPTANCE_TEST:
            # 验收测试阶段检查
            verified_reqs = sum(1 for r in self.requirements.values()
                               if r.verification_status == VerificationStatus.PASSED)
            if verified_reqs < len(self.requirements):
                gate_check['checks_failed'].append(
                    f"Only {verified_reqs}/{len(self.requirements)} requirements verified"
                )
                gate_check['can_proceed'] = False

        return gate_check


# 预定义的验证规则
def rule_has_inputs(model: MBDModel) -> Tuple[bool, str]:
    """检查模型是否定义了输入"""
    if len(model.artifact.inputs) > 0:
        return True, f"Model has {len(model.artifact.inputs)} inputs defined"
    return False, "Model has no inputs defined"


def rule_has_outputs(model: MBDModel) -> Tuple[bool, str]:
    """检查模型是否定义了输出"""
    if len(model.artifact.outputs) > 0:
        return True, f"Model has {len(model.artifact.outputs)} outputs defined"
    return False, "Model has no outputs defined"


def rule_has_parameters(model: MBDModel) -> Tuple[bool, str]:
    """检查模型是否定义了参数"""
    if len(model._parameters) > 0:
        return True, f"Model has {len(model._parameters)} parameters defined"
    return False, "Model has no parameters defined"


def rule_has_requirements(model: MBDModel) -> Tuple[bool, str]:
    """检查模型是否关联了需求"""
    if len(model.artifact.requirements) > 0:
        return True, f"Model linked to {len(model.artifact.requirements)} requirements"
    return False, "Model has no linked requirements"


# 创建预配置的验证器
def create_default_validator() -> ModelValidator:
    """创建默认验证器"""
    validator = ModelValidator()
    validator.add_rule("has_inputs", rule_has_inputs)
    validator.add_rule("has_outputs", rule_has_outputs)
    validator.add_rule("has_parameters", rule_has_parameters)
    validator.add_rule("has_requirements", rule_has_requirements)
    return validator
