# Agent 评估平台

一个用于评估 AI Agent 能力的全栈平台，支持多种评估类型、多模型对比和排行榜功能。

## 功能特性

- **10 种评估类型**：涵盖工具调用、多步规划、ReAct 推理等 Agent 核心能力，以及 LLM 裁判评分（开放式任务）
- **真实基准数据**：GSM8K / MMLU / HumanEval 支持一键从 HuggingFace 导入真实数据（无需 Token）
- **LLM-as-Judge**：指定裁判模型按评分标准给开放式回答打分，保留评分理由
- **可解析的输出格式**：内置数据集自动附带输出格式指令，规则评估器解析成功率大幅提升；支持数据集级 system prompt
- **多模型评估**：支持 OpenAI（及兼容接口）、Anthropic、本地端点，可批量对比多个模型
- **运行对比**：勾选 2-4 个同数据集运行，逐题对比各模型回答，自动高亮结果分歧行
- **失败重跑 / CSV 导出**：失败任务一键重跑（保留已完成结果）；全部结果可导出 CSV
- **异步并发执行**：全局并发上限（默认 10，可配置）跨所有运行生效；HTTP 连接池复用，429/5xx/超时自动指数退避重试
- **排行榜与图表**：每次运行等权重聚合，总览与排行榜提供模型得分对比图
- **中文 Web 界面**：基于 React + Ant Design，运行中自动刷新进度
- **测试覆盖**：83 项 pytest 测试覆盖评估器、LLM 客户端与 API 全链路（`make test`）

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
| `humaneval` | 代码生成 - Python 编程题 | 测试用例执行（隔离子进程 + 超时） |
| `llm_judge` | 开放式任务 - 由裁判模型打分 | 裁判模型按评分标准给出 0~1 分及理由 |

`gsm8k` / `mmlu` / `humaneval` 除内置示例外，还支持从 HuggingFace `datasets-server` 直接导入真实数据（默认 50 条，最多 500 条）。`llm_judge` 类型的数据集在创建运行时必须指定 `judge_model_config_id`（裁判模型），题目的 `reference_answer` 填写评分标准（rubric）。

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

### 运行测试

```bash
make test
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

进入「数据集」页面，点击「导入数据集」，选择评估类型：

- **内置示例**：所有 10 种类型均可用，题目已附带输出格式指令
- **HuggingFace 真实数据**：`gsm8k` / `mmlu` / `humaneval` 可选，从 HuggingFace 拉取真实基准题目

也可通过「上传自定义」提交 JSON 题目列表，支持设置数据集级系统提示词（system prompt）。

### 3. 启动评估

进入「新建评估」，可多选数据集与模型批量创建（数据集 × 模型 笛卡尔积）。若包含 `llm_judge` 类型数据集，需额外指定裁判模型。评估异步执行，进度自动刷新。

### 4. 查看与分析结果

- **运行详情**：逐题查看原始响应、解析答案、评分细节（裁判理由），支持失败任务重跑与 CSV 导出
- **运行对比**：在运行列表勾选 2-4 个同数据集运行，逐题对比模型回答，分歧行自动高亮
- **排行榜**：按数据集筛选，图表 + 表格对比各模型综合表现

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_EVAL_DATABASE_URL` | `./data/agent_eval.db` | SQLite 数据库路径 |
| `AGENT_EVAL_MAX_CONCURRENT_TASKS` | `10` | 全局最大并发 LLM 调用数（跨所有运行） |
| `AGENT_EVAL_CORS_ORIGINS` | `http://localhost:5173` | 允许的 CORS 来源 |
| `AGENT_EVAL_LLM_TIMEOUT_SECONDS` | `120` | 单次 LLM 请求超时（也可在参数中传 `timeout` 覆盖） |
| `AGENT_EVAL_LLM_MAX_RETRIES` | `3` | 遇到 429/5xx/超时时的最大重试次数（指数退避） |
| `AGENT_EVAL_CODE_EXEC_TIMEOUT_SECONDS` | `5` | HumanEval 代码执行沙箱超时 |

模型参数（`default_params` / 运行时 `params_override`）中还支持两个客户端级别的键：`system`（系统提示词，OpenAI 转为 system 消息，Anthropic 转为顶层 `system` 字段）和 `timeout`（单次请求超时秒数），它们不会透传给提供商 API。

安全说明：API 返回的模型配置只包含掩码后的 API Key（如 `sk-...abcd`）；更新模型时提交空值或掩码值均会保留原 Key 不变。

## 项目结构

```
agent_eval/
├── backend/
│   ├── app/
│   │   ├── api/            # REST API 路由
│   │   ├── evaluation/     # 评估器模块
│   │   ├── models/         # 数据库 ORM 模型
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── services/       # 评估任务调度 & LLM 客户端
│   │   ├── config.py       # 配置管理
│   │   ├── database.py     # 数据库初始化
│   │   └── main.py         # FastAPI 应用入口
│   └── tests/              # pytest 测试套件
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
