# -*- coding: utf-8 -*-
"""
水利枢纽硬件在环(HIL)仿真测试平台
Hardware-in-the-Loop Simulation Platform for Hydraulic Control Systems

本模块实现了针对水利枢纽关键设备的智能控制与数字验收规范，包括：
- 智能阀门控制柜 (IVCU)
- 智能泵控柜 (IPCU)
- 智能闸门控制柜 (IGCU)

核心功能：
1. 水力仿真模型 (MOC管网模型, 圣维南明渠模型)
2. 智能控制器逻辑
3. 虚拟传感器系统
4. HIL测试工况集
"""

__version__ = "1.0.0"
__author__ = "HIL Demo"
