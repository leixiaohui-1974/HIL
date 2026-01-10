# -*- coding: utf-8 -*-
"""
并行计算支持模块
Parallel Computing Support Module

提供多能互补系统的并行计算能力:
1. 多场景并行仿真
2. 参数敏感性并行分析
3. 蒙特卡洛并行仿真
4. 批量优化并行计算
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable, Any
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing
from functools import partial
import time


@dataclass
class ParallelConfig:
    """并行计算配置"""
    max_workers: int = None       # 最大工作进程数(None=CPU数)
    use_processes: bool = True    # 使用进程(True)还是线程(False)
    chunk_size: int = 1           # 任务分块大小
    timeout: float = None         # 任务超时时间(秒)
    verbose: bool = True          # 是否打印进度


@dataclass
class TaskResult:
    """任务结果"""
    task_id: int
    success: bool
    result: Any = None
    error: str = None
    execution_time: float = 0.0


class ParallelRunner:
    """
    并行运行器

    管理并行任务的执行
    """

    def __init__(self, config: Optional[ParallelConfig] = None):
        self.config = config or ParallelConfig()

        # 自动设置工作进程数
        if self.config.max_workers is None:
            self.config.max_workers = max(1, multiprocessing.cpu_count() - 1)

        self._results: List[TaskResult] = []

    def run_parallel(
        self,
        func: Callable,
        args_list: List[Tuple],
        kwargs_list: Optional[List[Dict]] = None
    ) -> List[TaskResult]:
        """
        并行执行函数

        Args:
            func: 要执行的函数
            args_list: 参数列表
            kwargs_list: 关键字参数列表(可选)

        Returns:
            结果列表
        """
        if kwargs_list is None:
            kwargs_list = [{}] * len(args_list)

        n_tasks = len(args_list)

        if self.config.verbose:
            print(f"并行执行 {n_tasks} 个任务 (workers={self.config.max_workers})")

        results = []
        start_time = time.time()

        # 选择执行器类型
        ExecutorClass = (ProcessPoolExecutor if self.config.use_processes
                        else ThreadPoolExecutor)

        # 由于进程池序列化问题,某些情况下使用线程池
        try:
            with ExecutorClass(max_workers=self.config.max_workers) as executor:
                # 提交任务
                futures = {}
                for i, (args, kwargs) in enumerate(zip(args_list, kwargs_list)):
                    future = executor.submit(self._run_task, func, args, kwargs, i)
                    futures[future] = i

                # 收集结果
                completed = 0
                for future in as_completed(futures, timeout=self.config.timeout):
                    task_id = futures[future]
                    try:
                        result = future.result()
                        results.append(result)
                        completed += 1
                        if self.config.verbose and completed % 10 == 0:
                            print(f"  进度: {completed}/{n_tasks}")
                    except Exception as e:
                        results.append(TaskResult(
                            task_id=task_id,
                            success=False,
                            error=str(e)
                        ))

        except Exception as e:
            print(f"并行执行失败,回退到串行执行: {e}")
            # 回退到串行执行
            for i, (args, kwargs) in enumerate(zip(args_list, kwargs_list)):
                result = self._run_task(func, args, kwargs, i)
                results.append(result)

        # 按task_id排序
        results.sort(key=lambda r: r.task_id)

        total_time = time.time() - start_time
        if self.config.verbose:
            successful = sum(1 for r in results if r.success)
            print(f"完成: {successful}/{n_tasks} 成功, 总耗时: {total_time:.2f}s")

        self._results = results
        return results

    def _run_task(
        self,
        func: Callable,
        args: Tuple,
        kwargs: Dict,
        task_id: int
    ) -> TaskResult:
        """执行单个任务"""
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return TaskResult(
                task_id=task_id,
                success=True,
                result=result,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )


class ParallelScenarioRunner:
    """
    并行场景运行器

    并行执行多个场景仿真
    """

    def __init__(self, config: Optional[ParallelConfig] = None):
        self.config = config or ParallelConfig()
        self.runner = ParallelRunner(self.config)

    def run_scenarios(
        self,
        scenarios: List['ScenarioDefinition']
    ) -> List['ScenarioResult']:
        """
        并行运行多个场景

        Args:
            scenarios: 场景定义列表

        Returns:
            场景结果列表
        """
        from .scenario_analysis import ScenarioResult

        if self.config.verbose:
            print(f"\n并行场景仿真: {len(scenarios)}个场景")

        # 准备任务参数
        args_list = [(scenario,) for scenario in scenarios]

        # 并行执行
        task_results = self.runner.run_parallel(
            self._run_single_scenario,
            args_list
        )

        # 提取结果
        results = []
        for task_result in task_results:
            if task_result.success:
                results.append(task_result.result)
            else:
                print(f"场景 {task_result.task_id} 失败: {task_result.error}")

        return results

    @staticmethod
    def _run_single_scenario(scenario: 'ScenarioDefinition') -> 'ScenarioResult':
        """运行单个场景"""
        from .simulation import MultiEnergySimulator
        from .scenario_analysis import ScenarioResult
        import time

        start_time = time.time()

        # 创建仿真器并运行
        simulator = MultiEnergySimulator(scenario.config)
        sim_result = simulator.run()

        execution_time = time.time() - start_time

        # 计算指标
        freq_dev = sim_result.frequency - 50.0
        metrics = {
            'freq_dev_max': np.max(np.abs(freq_dev)),
            'freq_dev_rms': np.sqrt(np.mean(freq_dev ** 2)),
            'psh_mode_switches': sim_result.psh_mode_switches
        }

        return ScenarioResult(
            scenario_name=scenario.name,
            simulation_result=sim_result,
            execution_time=execution_time,
            metrics=metrics
        )


class ParallelParameterSweep:
    """
    并行参数扫描

    并行执行参数敏感性分析
    """

    def __init__(self, config: Optional[ParallelConfig] = None):
        self.config = config or ParallelConfig()
        self.runner = ParallelRunner(self.config)

    def sweep(
        self,
        base_config: 'SimulationConfig',
        param_name: str,
        param_values: List[float]
    ) -> Dict[float, 'SimulationResult']:
        """
        参数扫描

        Args:
            base_config: 基础配置
            param_name: 参数名
            param_values: 参数值列表

        Returns:
            {参数值: 仿真结果}
        """
        if self.config.verbose:
            print(f"\n参数扫描: {param_name}")
            print(f"  值范围: {param_values[0]} - {param_values[-1]}")
            print(f"  采样点: {len(param_values)}")

        # 准备任务
        args_list = [(base_config, param_name, value) for value in param_values]

        # 并行执行
        task_results = self.runner.run_parallel(
            self._run_with_param,
            args_list
        )

        # 组织结果
        results = {}
        for i, task_result in enumerate(task_results):
            if task_result.success:
                results[param_values[i]] = task_result.result

        return results

    def multi_sweep(
        self,
        base_config: 'SimulationConfig',
        param_ranges: Dict[str, List[float]]
    ) -> Dict[Tuple, 'SimulationResult']:
        """
        多参数扫描

        Args:
            base_config: 基础配置
            param_ranges: {参数名: 值列表}

        Returns:
            {参数组合: 仿真结果}
        """
        import itertools

        # 生成所有参数组合
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        combinations = list(itertools.product(*param_values))

        if self.config.verbose:
            print(f"\n多参数扫描")
            print(f"  参数: {param_names}")
            print(f"  组合数: {len(combinations)}")

        # 准备任务
        args_list = [(base_config, param_names, combo) for combo in combinations]

        # 并行执行
        task_results = self.runner.run_parallel(
            self._run_with_multi_params,
            args_list
        )

        # 组织结果
        results = {}
        for i, task_result in enumerate(task_results):
            if task_result.success:
                results[combinations[i]] = task_result.result

        return results

    @staticmethod
    def _run_with_param(
        base_config: 'SimulationConfig',
        param_name: str,
        param_value: float
    ) -> 'SimulationResult':
        """使用指定参数运行"""
        from .simulation import MultiEnergySimulator
        from dataclasses import replace

        # 创建配置副本并修改参数
        config = replace(base_config)
        setattr(config, param_name, param_value)

        # 运行仿真
        simulator = MultiEnergySimulator(config)
        return simulator.run()

    @staticmethod
    def _run_with_multi_params(
        base_config: 'SimulationConfig',
        param_names: List[str],
        param_values: Tuple
    ) -> 'SimulationResult':
        """使用多个参数运行"""
        from .simulation import MultiEnergySimulator
        from dataclasses import replace

        # 创建配置副本并修改参数
        config = replace(base_config)
        for name, value in zip(param_names, param_values):
            setattr(config, name, value)

        # 运行仿真
        simulator = MultiEnergySimulator(config)
        return simulator.run()


class MonteCarloSimulator:
    """
    蒙特卡洛仿真器

    并行执行蒙特卡洛仿真
    """

    def __init__(self, config: Optional[ParallelConfig] = None):
        self.config = config or ParallelConfig()
        self.runner = ParallelRunner(self.config)

    def run(
        self,
        base_config: 'SimulationConfig',
        n_samples: int,
        uncertainty_params: Dict[str, Tuple[float, float]]
    ) -> Dict[str, np.ndarray]:
        """
        运行蒙特卡洛仿真

        Args:
            base_config: 基础配置
            n_samples: 样本数
            uncertainty_params: {参数名: (均值, 标准差)}

        Returns:
            统计结果
        """
        if self.config.verbose:
            print(f"\n蒙特卡洛仿真")
            print(f"  样本数: {n_samples}")
            print(f"  不确定参数: {list(uncertainty_params.keys())}")

        # 生成随机样本
        param_samples = {}
        for param, (mean, std) in uncertainty_params.items():
            param_samples[param] = np.random.normal(mean, std, n_samples)

        # 准备任务
        args_list = []
        for i in range(n_samples):
            sample = {param: values[i] for param, values in param_samples.items()}
            args_list.append((base_config, sample))

        # 并行执行
        task_results = self.runner.run_parallel(
            self._run_with_uncertainty,
            args_list
        )

        # 收集结果
        freq_dev_max = []
        freq_dev_rms = []
        psh_switches = []

        for task_result in task_results:
            if task_result.success:
                result = task_result.result
                freq_dev_max.append(result.frequency_deviation_max)
                freq_dev_rms.append(result.frequency_deviation_rms)
                psh_switches.append(result.psh_mode_switches)

        # 统计分析
        return {
            'freq_dev_max': np.array(freq_dev_max),
            'freq_dev_rms': np.array(freq_dev_rms),
            'psh_switches': np.array(psh_switches),
            'statistics': {
                'freq_dev_max_mean': np.mean(freq_dev_max),
                'freq_dev_max_std': np.std(freq_dev_max),
                'freq_dev_max_p95': np.percentile(freq_dev_max, 95),
                'freq_dev_rms_mean': np.mean(freq_dev_rms),
                'freq_dev_rms_std': np.std(freq_dev_rms)
            }
        }

    @staticmethod
    def _run_with_uncertainty(
        base_config: 'SimulationConfig',
        param_sample: Dict[str, float]
    ) -> 'SimulationResult':
        """运行带不确定性的仿真"""
        from .simulation import MultiEnergySimulator
        from dataclasses import replace

        # 创建配置副本
        config = replace(base_config)

        # 应用不确定参数
        for param, value in param_sample.items():
            if hasattr(config, param):
                setattr(config, param, max(0, value))  # 确保非负

        # 运行仿真
        simulator = MultiEnergySimulator(config)
        return simulator.run()


# 便捷函数
def parallel_scenario_run(
    scenarios: List['ScenarioDefinition'],
    max_workers: int = None
) -> List['ScenarioResult']:
    """
    并行运行多场景

    Args:
        scenarios: 场景列表
        max_workers: 最大工作进程数

    Returns:
        结果列表
    """
    config = ParallelConfig(max_workers=max_workers)
    runner = ParallelScenarioRunner(config)
    return runner.run_scenarios(scenarios)


def parallel_parameter_sweep(
    base_config: 'SimulationConfig',
    param_name: str,
    param_values: List[float],
    max_workers: int = None
) -> Dict[float, 'SimulationResult']:
    """
    并行参数扫描

    Args:
        base_config: 基础配置
        param_name: 参数名
        param_values: 参数值列表
        max_workers: 最大工作进程数

    Returns:
        {参数值: 结果}
    """
    config = ParallelConfig(max_workers=max_workers)
    sweeper = ParallelParameterSweep(config)
    return sweeper.sweep(base_config, param_name, param_values)
