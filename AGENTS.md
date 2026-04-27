# AGENTS.md

## 项目说明

- 依赖管理：使用 uv
- 安装依赖：`uv add <package>`
- 运行：`uv run python main.py`
- 无 pip 环境

## 环境变量

- `NIM_BASE_URL`: NVIDIA NIM 服务地址 (如: https://integrate.api.nvidia.com/v1)
- `MODELSCOPE_TOKEN`: ModelScope API Token
- `BIGMODEL_API_KEY`: 智谱AI API Key

## 测试命令

（待添加）

## 代码检查命令

- Lint: `uv run pyright main.py`