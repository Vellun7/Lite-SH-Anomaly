# 设计总说明（可直接 CV 至 Word，引用已上标）

---

随着智能摄像头、智能门锁、智能插座、环境传感器等设备在家庭场景中的广泛部署，智能家居网络逐渐呈现出设备数量多、通信协议复杂、运行环境开放和安全边界模糊等特征¹˒²。一旦设备遭受恶意扫描、越权控制、分布式拒绝服务攻击或异常指令注入，不仅会造成家庭网络性能下降，还可能引发隐私泄露、设备失控及联动系统异常等安全风险³˒⁴。因此，围绕智能家居场景构建一套具备实时性、轻量化和工程可落地性的异常检测方法与应用系统，具有较强的理论意义和现实价值⁵。

本课题以"面向智能家居的轻量化异常检测算法设计与实现"为研究对象，面向家庭网关、嵌入式终端及低算力边缘节点的资源约束特性，围绕"数据构建—模型设计—系统实现—实验验证"四个环节展开系统性研究。全文组织结构如下：

**在数据层面**，课题结合公开网络安全数据集与场景化模拟数据，完成了智能家居异常流量数据集的构建工作。具体包括：原始数据的采集与整合、数据清洗与缺失值处理、类别特征的编码映射、衍生统计特征的设计与提取，以及特征标准化处理，最终形成统一规范的特征矩阵，为后续模型训练提供高质量的数据基础⁶˒⁷。

**在算法层面**，针对传统检测模型参数规模大、推理开销高、难以直接部署于轻量级设备的问题⁸，本课题设计了两套核心检测模型：一是**轻量化孤立森林模型**，通过限制树的最大深度、优化采样策略和校准异常分数输出，在保证检测精度的同时显著降低计算复杂度；二是**轻量化自编码器模型**，采用瓶颈层压缩结构配合重构误差判定机制，实现对异常模式的有效捕捉⁹˒¹⁰。在此基础上，进一步设计了**集成检测框架**，融合两种模型的优势输出，并引入规则前置过滤、自适应阈值调整和增量优化机制，形成适用于智能家居场景的完整异常检测方法链路¹¹˒¹²。

**在系统层面**，基于 Django 4.2 后端框架与 Django REST Framework 接口框架、Vue 3 前端框架与 Element Plus 组件库、ECharts 可视化引擎及 WebSocket 实时通信协议等技术栈¹³⁻¹⁶，完成了集用户认证与权限管理、设备信息管理与状态监控、实时流量异常检测、历史记录查询与回溯、检测性能可视化监控、告警联动推送与审计日志追踪于一体的智能家居异常检测系统。系统采用前后端分离架构，后端提供 RESTful API 与模型推理服务接口，前端实现响应式布局的多功能交互界面¹⁷˒¹⁸。

**在验证层面**，通过模型对比评估实验、系统功能测试与性能压力测试三个维度，对所设计的轻量化异常检测方法和实现的工程系统进行了综合验证¹⁹˒²⁰。实验结果表明，轻量化模型在精度指标上接近或达到主流基线水平的同时，参数量和推理延迟得到有效控制；系统各功能模块运行稳定，能够满足实时检测与可视化监控的实际需求²¹˒²²。

本课题研究的重点与创新点在于：**第一**，兼顾检测精度与部署代价的平衡，在保证异常检出能力的前提下严格控制模型的参数规模与推理延迟，使之适配边缘设备的资源约束条件²³；**第二**，建立了一套适合智能家居网络流量特点的轻量化特征体系，涵盖基础流量属性、类别编码信息和衍生统计量三类特征，并通过特征重要性分析筛选出对异常识别贡献最大的关键特征子集²⁴；**第三**，打通了从数据处理到模型训练、从接口服务到前端展示的完整技术链路，实现了可视化、可交互、可验证的一体化异常检测平台²⁵。现阶段研究工作表明，所构建的方法与系统已经具备较好的工程基础与实践价值，能够为智能家居环境下的异常行为识别、安全态势感知与主动防御响应提供有效支撑²⁶⁻³⁰。

---

## 中文摘要

面向智能家居场景的异常检测是当前物联网安全领域的重要研究方向¹。随着智能终端设备在家庭环境中的快速普及，其面临的安全威胁日益严峻²，而传统异常检测方法因计算开销大、部署门槛高，难以直接适用于资源受限的家庭网关与边缘节点³˒⁴。为此，本文设计并实现了一种面向智能家居的轻量化异常检测方法及其配套应用系统⁵。

本文首先基于公开网络安全数据集与模拟流量数据，完成智能家居异常检测数据集的构建与预处理工作⁶，设计了包含基础流量特征、类别编码特征和衍生统计特征的轻量化特征体系⁷。其次，提出了轻量化孤立森林模型与轻量化自编码器模型两种核心检测算法⁸：前者通过限制树深、优化采样策略和校准异常分数降低计算复杂度⁹；后者利用瓶颈层压缩结构与重构误差机制捕捉深层异常模式¹⁰。在此基础上，进一步设计了多模型集成检测框架¹¹，引入规则前置过滤、自适应阈值与增量优化策略¹²，提升整体检测鲁棒性。再次，基于 Django 与 Vue 3 技术栈开发了前后端分离的智能家居异常检测系统¹³⁻¹⁶，实现了设备管理、实时检测、历史查询、可视监控、告警联动与审计追踪等功能模块¹⁷˒¹⁸。最后，通过对比实验、功能测试与性能测试对方法和系统进行了综合验证¹⁹˒²⁰。

实验结果表明，本文提出的轻量化异常检测模型在保证较高检测精度的同时，参数量与推理延迟得到有效控制²¹，能够适配低算力边缘设备的部署需求²²；所实现的系统各功能模块运行稳定、交互友好²³，可为智能家居环境下的安全监测提供有效的技术支撑²⁴⁻²⁶。

**关键词：** 智能家居；异常检测；轻量化模型；孤立森林；自编码器；安全监测系统

---

## Abstract

Anomaly detection for smart home scenarios is an important research direction in the field of IoT security¹. With the rapid proliferation of smart terminal devices in home environments, the security threats they face are increasingly severe²˒³. However, traditional anomaly detection methods are difficult to apply directly to resource-constrained home gateways and edge nodes due to their high computational overhead and deployment barriers⁴˒⁵. To address this problem, this thesis designs and implements a lightweight anomaly detection approach for smart homes along with its supporting application system⁶.

Firstly, based on public cybersecurity datasets and simulated traffic data, this thesis completes the construction and preprocessing of a smart home anomaly detection dataset⁷, and designs a lightweight feature system comprising basic traffic features, categorical encoding features and derived statistical features⁸. Secondly, two core detection algorithms are proposed: a lightweight Isolation Forest model that reduces computational complexity through tree depth limitation, sampling strategy optimization and anomaly score calibration⁹; and a lightweight AutoEncoder model that captures deep anomaly patterns using bottleneck layer compression structure and reconstruction error mechanism¹⁰. On this basis, a multi-model ensemble detection framework is further designed¹¹, incorporating rule-based pre-filtering, adaptive thresholding and incremental optimization strategies to enhance overall detection robustness¹². Thirdly, a front-end and back-end separated smart home anomaly detection system is developed based on Django and Vue 3 technology stacks¹³⁻¹⁶, realizing functional modules including device management, real-time detection, historical query, visual monitoring, alert linkage and audit tracking¹⁷˒¹⁸. Finally, comprehensive verification of the proposed method and system is conducted through comparative experiments, functional tests and performance tests¹⁹˒²⁰.

Experimental results show that the lightweight anomaly detection models proposed in this thesis effectively control parameter count and inference latency while maintaining high detection accuracy²¹, meeting the deployment requirements of low-power edge devices²². The implemented system operates stably across all functional modules with user-friendly interaction²³, providing effective technical support for security monitoring in smart home environments²⁴⁻²⁶.

**Key Words:** smart home; anomaly detection; lightweight model; isolation forest; autoencoder; security monitoring system

---

> **使用说明：**
> 1. 全选上方内容 → 复制
> 2. 打开 Word → 粘贴
> 3. 引用数字已经是 **Unicode 上标字符**（如 ¹²³⁴⁵⁶⁷⁸⁹⁰），粘贴后自动以上标显示
> 4. 连续引用用间隔号 `˒` 或连字符号 `⁻` 连接（如 ¹³⁻¹⁶ 表示 [13]-[16]）
> 5. 如果 Word 中上标显示异常，可以全选 → 字体 → 勾选「上标」统一设置
