# Traffic Analysis Agent API

这是一个基于FastAPI的HTTP后端服务，为交通分析Agent提供API接口，支持流式和非流式响应。

## 功能特性

- ✅ **流式响应**: 实时查看Agent的推理过程
- ✅ **非流式响应**: 传统的请求-响应模式
- ✅ **对话历史**: 保持用户的对话上下文
- ✅ **CORS支持**: 支持跨域访问
- ✅ **自动文档**: 自动生成API文档
- ✅ **错误处理**: 完善的错误处理机制

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_api.txt
```

### 2. 启动服务

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 访问API

- **API根路径**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc

## API接口

### 1. 健康检查

```http
GET /api/health
```

**响应**:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-04T17:55:00Z"
}
```

### 2. 流式对话

```http
POST /api/chat/stream
Content-Type: application/json

{
  "message": "现在深圳龙华区的交通情况怎么样？"
}
```

**响应** (Server-Sent Events):
```
data: {"type": "thought", "content": "正在分析深圳龙华区的交通状况..."}

data: {"type": "action", "content": "正在使用工具: demo_longhua_simulation"}

data: {"type": "observation", "content": "工具执行结果: It is the peak season..."}

data: {"type": "response", "content": "根据当前分析，深圳龙华区..."}

data: {"type": "done", "content": ""}
```

### 3. 普通对话

```http
POST /api/chat
Content-Type: application/json

{
  "message": "现在深圳龙华区的交通情况怎么样？"
}
```

**响应**:
```json
{
  "response": "根据当前分析，深圳龙华区交通状况...",
  "thoughts": "Agent的完整推理过程",
  "status": "success",
  "timestamp": "2025-01-04T17:55:00Z"
}
```

### 4. 重置对话

```http
POST /api/reset
```

**响应**:
```json
{
  "status": "success",
  "message": "Conversation history cleared",
  "timestamp": "2025-01-04T17:55:00Z"
}
```

## 前端集成示例

### JavaScript (流式响应)

```javascript
// 发送流式请求
async function sendStreamMessage(message) {
    const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: message })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                
                switch (data.type) {
                    case 'thought':
                        console.log('思考:', data.content);
                        break;
                    case 'action':
                        console.log('动作:', data.content);
                        break;
                    case 'observation':
                        console.log('观察:', data.content);
                        break;
                    case 'response':
                        console.log('回复:', data.content);
                        break;
                    case 'done':
                        console.log('完成');
                        return;
                }
            }
        }
    }
}

// 使用示例
sendStreamMessage('现在深圳龙华区的交通情况怎么样？');
```

### JavaScript (普通响应)

```javascript
async function sendMessage(message) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();
        console.log('回复:', data.response);
        console.log('推理过程:', data.thoughts);
    } catch (error) {
        console.error('错误:', error);
    }
}
```

### Python

```python
import requests
import json

# 普通请求
def send_message(message):
    url = "http://localhost:8000/api/chat"
    payload = {"message": message}
    
    response = requests.post(url, json=payload)
    return response.json()

# 流式请求
def send_stream_message(message):
    url = "http://localhost:8000/api/chat/stream"
    payload = {"message": message}
    
    response = requests.post(url, json=payload, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                print(f"{data['type']}: {data['content']}")
                if data['type'] == 'done':
                    break

# 使用示例
result = send_message("现在深圳龙华区的交通情况怎么样？")
print(result)
```

### cURL

```bash
# 普通请求
curl -X POST "http://localhost:8000/api/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "现在深圳龙华区的交通情况怎么样？"}'

# 流式请求
curl -X POST "http://localhost:8000/api/chat/stream" \
     -H "Content-Type: application/json" \
     -d '{"message": "现在深圳龙华区的交通情况怎么样？"}' \
     --no-buffer

# 重置对话
curl -X POST "http://localhost:8000/api/reset"

# 健康检查
curl "http://localhost:8000/api/health"
```

## 消息类型说明

流式响应中的消息类型：

- **thought**: Agent的思考过程
- **action**: Agent执行的动作/工具调用
- **observation**: 工具执行的结果
- **response**: Agent的最终回复
- **done**: 对话完成标志
- **error**: 错误信息

## 错误处理

API使用标准HTTP状态码：

- **200**: 成功
- **422**: 请求参数验证失败
- **500**: 服务器内部错误

错误响应格式：
```json
{
  "detail": "错误详细信息"
}
```

## 配置

API使用项目根目录的 `config.yaml` 文件进行配置，支持：

- Azure OpenAI
- OpenAI
- OpenRouter

## 部署建议

### 开发环境
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 生产环境
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1
```

注意：由于Agent需要保持对话状态，建议使用单个worker进程。

## 注意事项

1. **单用户设计**: 当前API设计为单用户使用，所有请求共享同一个对话历史
2. **内存存储**: 对话历史存储在内存中，重启服务会丢失
3. **同步限制**: 同时只能处理一个对话请求
4. **超时设置**: LLM请求超时时间为60秒

## 故障排除

### 常见问题

1. **模块导入错误**: 确保在项目根目录运行API
2. **配置文件错误**: 检查 `config.yaml` 文件格式和API密钥
3. **端口占用**: 更改端口或停止占用进程
4. **依赖版本**: 使用 `requirements_api.txt` 安装正确版本

### 日志查看

启动时添加 `--log-level debug` 参数查看详细日志：

```bash
uvicorn api.main:app --log-level debug
