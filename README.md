# Agent 评估平台

一个用于评估 AI Agent 能力的全栈平台，支持多种评估类型、多模型对比和排行榜功能。

## 功能特性

- **多数据集支持**：内置 9 种评估数据集类型，涵盖工具调用、多步规划、ReAct 推理等 Agent 核心能力
- **多模型评估**：支持 OpenAI、Anthropic 等主流 LLM 提供商，可同时对比多个模型表现
- **异步并发执行**：最多 10 个任务并行执行，高效完成大规模评估
- **详细评估报告**：每条评估结果包含原始响应、解析答案、得分及详细评估信息
- **排行榜系统**：按数据集筛选，直观对比各模型综合表现
- **完整 Web 界面**：基于 React + Ant Design 的现代化管理界面

## 支持的评估类型

| 类型 | 说明 | 评分维度 |
|------|------|----------|
| `tool_use` | 工具调用 - 工具选择与参数传递 | 工具名(40%) + 参数存在(30%) + 参数值(30%) |
| `multi_step` | 多步规划 - 任务分解与步骤排序 | 步骤数量(20%) + 关键步骤(50%) + 顺序(30%) |
| `react` | ReAct 推理 - 思考-行动-观察循环 | 结构(30%) + 最终行动(40%) + 推理质量(30%) |
| `instruction_following` | 指令遵循 - 多约束条件满足 | 约束通过率(100%) |
| `api_interaction` | API 交互 - API 调用构造 | 方法(25%) + 端点(25%) + 请求头(25%) + 请求体(25%) |
| `error_recovery` | 错误恢复 - 错误识别与修复 | 检测(20%) + 诊断(30%) + 恢复行动(35%) + 解释(15%) |
| `gsm8k` | 数学推理 - 小学数学应用题 | 数值精确匹配 |
| `mmlu` | 综合知识 - 多学科选择题 | 选项字母匹配 |
| `humaneval` | 代码生成 - Python 编程题 | 测试用例执行 |

## 技术栈

**后端**
- Python 3.11+ / FastAPI
- SQLAlchemy 2.0 (异步 ORM)
- SQLite + WAL 模式
- OpenAI / Anthropic SDK

**前端**
- React 18 + TypeScript
- Ant Design 5
- Recharts
- Vite

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- pip

### 安装与启动

```bash
# 克隆项目
git clone <repo-url>
cd agent_eval

# 安装所有依赖
make install

# 启动开发服务器（后端 + 前端）
make dev
```

启动后访问：
- 前端界面：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 单独启动

```bash
# 仅启动后端
make backend

# 仅启动前端
make frontend
```

### 清理

```bash
make clean
```

## 使用指南

### 1. 配置模型

进入「模型管理」页面，添加 LLM 模型配置：

```
名称: GPT-4o
提供商: openai
模型 ID: gpt-4o
API Key: sk-...
```

支持的提供商：`openai`、`anthropic`、`local`（自定义 HTTP 端点）。

### 2. 导入数据集

进入「数据集」页面，点击「导入示例数据集」，选择评估类型后导入。

也可通过「上传数据集」功能自定义导入 JSON 格式数据。

### 3. 启动评估

在数据集详情页点击「新建评估运行」，选择模型后启动。评估过程异步执行，可实时查看进度。

### 4. 查看结果

- **运行详情**：查看每条评估任务的原始响应、解析答案和详细得分
- **排行榜**：对比不同模型在同一数据集上的综合表现

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_EVAL_DATABASE_URL` | `./data/agent_eval.db` | SQLite 数据库路径 |
| `AGENT_EVAL_MAX_CONCURRENT_TASKS` | `10` | 最大并发评估任务数 |
| `AGENT_EVAL_CORS_ORIGINS` | `http://localhost:5173` | 允许的 CORS 来源 |

## 项目结构

```
agent_eval/
├── backend/
│   └── app/
│       ├── api/            # REST API 路由
│       ├── evaluation/     # 评估器模块
│       ├── models/         # 数据库 ORM 模型
│       ├── schemas/        # Pydantic 请求/响应模型
│       ├── services/       # 评估任务调度 & LLM 客户端
│       ├── config.py       # 配置管理
│       ├── database.py     # 数据库初始化
│       └── main.py         # FastAPI 应用入口
├── frontend/
│   └── src/
│       ├── api/            # 前端 API 请求层
│       └── pages/          # 页面组件
└── Makefile
```

## 自定义评估器

继承 `BaseEvaluator` 并实现 `parse_answer()` 和 `score()` 方法，然后在 `EvaluatorRegistry` 中注册：

```python
# backend/app/evaluation/my_evaluator.py
from app.evaluation.base import BaseEvaluator, EvalResult

class MyEvaluator(BaseEvaluator):
    def parse_answer(self, raw_response: str, metadata: dict | None = None) -> str:
        # 从模型响应中提取答案
        return raw_response.strip()

    def score(self, parsed_answer: str, reference_answer: str, metadata: dict | None = None) -> EvalResult:
        is_correct = parsed_answer == reference_answer
        return EvalResult(is_correct=is_correct, score=1.0 if is_correct else 0.0, details={})
```

```python
# backend/app/evaluation/registry.py 中添加：
from app.evaluation.my_evaluator import MyEvaluator

class EvaluatorRegistry:
    _evaluators = {
        ...
        "my_type": MyEvaluator,
    }
```

## License

MIT
