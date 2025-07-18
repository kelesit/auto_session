
# 🔌 API 接口文档

## 核心API接口

### 1. 创建会话任务
```http
POST /api/sessions/create
Content-Type: application/json

{
  "account_id": "test_account_001",
  "shop_id": "12345", 
  "shop_name": "测试店铺",
  "task_type": "auto_bargain",
  "external_task_id": "ext_task_001",
  "send_content": "您好，这个商品可以再便宜点吗？",
  "platform": "淘天",
  "level": ‘level3’,
  "max_inactive_minutes": 120
}
```

**任务类型说明**:
- `auto_bargain`: 自动砍价
- `auto_follow_up`: 自动跟单  
- `manual_customer_service`: 人工客服
- `manual_complaint`: 人工投诉处理
- `manual_urgent`: 人工紧急处理

**响应示例**:
```json
{
  "success": true,
  "message": "会话任务创建成功",
  "data": {
    "session_id": "sess_12345",
    "external_task_id": "ext_task_001", 
    "task_type": "auto_bargain",
    "created_at": "2025-07-18T10:00:00"
  }
}
```

**冲突响应示例**:
```json
{
  "success": false,
  "message": "当前有活跃的机器人会话sess_99579086f173，无法创建新的机器人会话",
  "data": {
    "conflict_session_id": "sess_99579086f173"
  },
  "error_code": "UNAVAILABLE"
}
```

### 2. 完成会话任务
```http
POST /api/sessions/{session_id}/complete
Content-Type: application/json

{
  "success": true,
  "error_message": null
}
```

### 3. 获取Redis任务队列
```http
GET /api/tasks/next_id
```

**响应示例（有任务）**:
```json
{
  "success": true,
  "message": "获取任务成功",
  "data": {
    "task_id": "5566",
    "timestamp": "2025-07-18T10:00:00"
  }
}
```

**响应示例（无任务）**:
```json
{
  "success": false,
  "message": "当前没有待处理的任务",
  "data": {
    "task_id": null
  }
}
```

### 4. 获取任务发送信息
```http
GET /api/tasks/{task_id}/send_info
```

**响应示例**:
```json
{
  "success": true,
  "message": "获取发送信息成功",
  "data": {
    "send_content": "您好，这个商品可以再便宜点吗？",
    "send_url": "https://example.com/chat",
    "shop_name": "测试店铺"
  }
}
```

**错误响应示例**:
```json
{
  "success": false,
  "message": "未找到对应的发送信息",
  "error_code": "TASK_NOT_FOUND"
}
```

### 5. 批量处理消息
```http
POST /api/messages/batch
Content-Type: application/json

{
  "shop_name": "测试店铺",
  "platform": "淘天",
  "max_inactive_minutes": 120,
  "messages": [
    {
      "id": "msg_001",
      "content": "你好，在吗？",
      "nick": "customer_001",
      "time": "2025-07-18T10:00:00"
    },
    {
      "id": "msg_002", 
      "content": "这个商品还有库存吗？",
      "nick": "t-2217567810350-0",
      "time": "2025-07-18T10:01:00"
    }
  ]
}
```

**字段说明**:
- `nick`: 发送者昵称，以 `t-` 开头的为账号，其他为客户
- `time`: 消息时间，ISO格式字符串
- `content`: 消息内容
- `id`: 消息唯一标识

**响应示例**:
```json
{
  "success": true,
  "message": "消息批处理成功",
  "data": {
    "processed_messages": 2,
    "skipped_messages": 0,
    "active_session_id": "sess_12345",
    "session_operations": ["updated"],
    "errors": []
  }
}
```

## 监控API

### 1. 健康检查
```http
GET /
```
**响应示例**:
```json
{
  "message": "Auto Session API is running", 
  "version": "1.0.0"
}
```

```http
GET /health
```
**响应示例**:
```json
{
  "status": "healthy", 
  "timestamp": "2025-07-18T10:00:00"
}
```
