# Model Check

一个用于测试多个 AI 模型供应商的命令行工具。支持批量测试、实时聊天、进度显示和请求取消功能。

## 功能特性

- 支持多个模型供应商（NVIDIA NIM、ModelScope、BigModel、OpenRouter）
- 批量测试所有模型
- 单模型对话测试
- 中英文界面切换
- 实时进度条显示
- ESC 键取消请求
- 自动获取可用模型列表

## 安装

确保已安装 [uv](https://github.com/astral-sh/uv)。

```bash
uv sync
```

## 配置

编辑 `models.yaml` 配置文件：

```yaml
providers:
  - name: nvidia
    display: NVIDIA NIM
    base_url: https://integrate.api.nvidia.com/v1
    api_key: ${NIM_BASE_URL}
    fetch_models: true

  - name: modelscope
    display: ModelScope
    base_url: https://api-inference.modelscope.cn/v1
    api_key: ${MODELSCOPE_TOKEN}
    fetch_models: true

  - name: bigmodel
    display: BigModel
    base_url: https://open.bigmodel.cn/api/paas/v4
    api_key: ${BIGMODEL_API_KEY}
    models:
      - glm-4-flash
      - glm-4
    headers:
      Content-Type: application/json
    auth_header: Authorization
    auth_prefix: ""

default_timeout: 30
```

### 环境变量

- `NIM_BASE_URL`: NVIDIA NIM API 地址
- `MODELSCOPE_TOKEN`: ModelScope API Token
- `BIGMODEL_API_KEY`: 智谱 AI API Key

## 使用方法

```bash
uv run python main.py
```

### 操作说明

1. 选择语言（中文/English）
2. 选择模型供应商
3. 选择模型或测试全部模型（输入 `a`）
4. 输入测试提示词
5. 按 `ESC` 可取消正在进行的请求
6. 输入 `b` 返回上一级，`q` 退出

## 依赖

- httpx
- pyyaml
- colorama (Windows 自动安装)
- nemo-microservices
- modelscope
- zai-sdk

## 代码检查

```bash
uv run pyright main.py
```
