# Auto Session 智能会话管理系统

会话管理平台，支持机器人客服和人工客服的智能协作与无缝转接。

## 🌟 核心功能

- **智能会话管理**: 自动创建、管理和监控客服会话
- **无缝转接**: 机器人和人工客服间的智能转接
- **批量消息处理**: 高效处理历史对话记录
- **优先级管理**: 基于任务类型的智能优先级调度
- **完整日志**: 详细的会话操作记录和审计
- **冲突解决**: 智能的会话冲突检测和解决

## 💼 业务场景

在电商采购、砍价、跟单等场景中：

- **🤖 机器人**: 负责砍价任务和跟单任务等标准化操作，主动发起对话进行协商
- **👨‍💼 人工客服**: 处理复杂问题，如退款换款、售后服务、投诉处理等
- **🔄 智能转接**: 当机器人无法处理时，自动转接到合适的人工客服
- **📊 统一管理**: 多账号、多店铺的统一会话管理

## 📋 系统要求

- Python 3.12+
- MySQL 8.0+
- 推荐使用 `uv` 进行包管理
- 依赖库：`uv`, `sqlalchemy`, `pydantic`, `fastapi`, `uvicorn`

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 uv 安装
uv install

# 或使用 pip
pip install -e .
```

### 2. 配置数据库

复制配置文件模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，配置数据库连接信息：
```env
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=auto_session
DATABASE_USER=root
DATABASE_PASSWORD=your_password
```

### 3. 创建数据库表

```bash
python scripts/create_tables.py
```

### 4. 运行系统

```bash
# 启动系统
python run.py

# 或运行测试
python test_system.py
```

## 💡 使用示例

### 基本用法

```python
from auto_session.main import AutoSessionManager
from auto_session.models import TaskType, Priority

# 初始化管理器
manager = AutoSessionManager()

# 创建机器人会话
session = manager.create_robot_session(
    shop_id=1,
    user_id="user123",
    task_type=TaskType.CONSULTATION,
    priority=Priority.MEDIUM
)

# 处理消息
messages = [
    {
        "session_id": session.session_id,
        "user_id": "user123",
        "message_type": "text",
        "content": "你好，我需要帮助",
        "timestamp": "2024-01-01T10:00:00"
    }
]

result = manager.process_chat_messages(messages)
print(f"处理了 {result.processed_count} 条消息")
```

### 转交人工客服

```python
# 转交到人工客服
transfer_result = manager.transfer_to_human(
    session_id=session.session_id,
    human_user_id="agent001",
    reason="用户需要专业咨询",
    urgency=Priority.HIGH
)

print(f"转交成功: {transfer_result.transfer_id}")
```

### 批量处理历史消息

```python
# 批量处理历史消息
result = manager.process_chat_messages(historical_messages)
print(f"成功处理 {result.processed_count} 条消息")
print(f"创建了 {result.sessions_created} 个新会话")
```

## 📊 系统架构

```
Auto Session 系统
├── 数据层 (database.py)
│   ├── 会话表 (sessions)
│   ├── 消息表 (messages)
│   ├── 转交记录表 (session_transfers)
│   └── 操作日志表 (session_operations)
├── 模型层 (models.py)
│   ├── 数据类型定义
│   ├── 枚举类型
│   └── 业务逻辑
├── 业务层 (session_api.py)
│   ├── 会话管理
│   ├── 转交处理
│   └── 状态管理
├── 处理层 (message_processor.py)
│   ├── 消息批处理
│   ├── 会话分组
│   └── 转交判断
└── 接口层 (main.py)
    └── 统一API接口
```

## 🔧 主要配置

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `DEFAULT_SESSION_TIMEOUT` | 会话超时时间(秒) | 1800 |
| `MAX_CONCURRENT_SESSIONS` | 最大并发会话数 | 10 |
| `TRANSFER_TIMEOUT` | 转交超时时间(秒) | 300 |
| `BATCH_SIZE` | 批处理大小 | 100 |

## 📈 性能特点

- **高效处理**: 批量处理支持，单次可处理数千条消息
- **智能分组**: 自动将消息按会话分组处理
- **冲突检测**: 智能检测和解决会话冲突
- **优先级调度**: 基于任务类型的优先级管理
- **资源优化**: 数据库连接池和索引优化

## 🔍 核心业务逻辑

### 会话状态管理

- **PENDING**: 等待中
- **ACTIVE**: 活跃中
- **COMPLETED**: 已完成
- **TRANSFERRED**: 已转交
- **PAUSED**: 已暂停
- **CANCELLED**: 已取消
- **TIMEOUT**: 超时

### 任务类型和优先级

```python
class TaskType(Enum):
    CONSULTATION = "consultation"    # 咨询
    COMPLAINT = "complaint"          # 投诉
    ORDER_INQUIRY = "order_inquiry"  # 订单查询
    NEGOTIATION = "negotiation"      # 砍价
    FOLLOW_UP = "follow_up"         # 跟单

class Priority(Enum):
    EMERGENCY = 1  # 紧急
    HIGH = 2       # 高
    MEDIUM = 3     # 中
    LOW = 4        # 低
```

### 关键约束

- **唯一性约束**: 一个账号ID和店家ID组合只能有一个活跃会话
- **优先级管理**: 基于任务类型自动分配优先级
- **智能转交**: 自动识别需要人工介入的场景

# 聊天会话生命周期管理设计文档

## 1. 核心需求分析

### 1.1 业务目标
- **会话路由管理**: 为上游机器人任务（砍价、跟单等）提供安全的会话环境
- **人工介入机制**: 当需要人工处理时，能够及时转交给人工客服
- **会话隔离**: 机器人会话与人工会话相互独立，互不干扰
- **生命周期管理**: 为不同类型的任务提供完整的会话生命周期支持
- **冲突处理**: 智能处理会话冲突，确保系统稳定运行

### 1.2 系统定位
- **不实现具体任务逻辑**: 砍价、跟单等任务逻辑由上游系统实现
- **专注会话管理**: 提供会话的创建、路由、状态管理、转交等基础能力
- **支持外部集成**: 通过API为上游任务系统提供会话管理服务
- **人工介入桥梁**: 处理机器人任务需要转人工的场景
- **智能冲突处理**: 处理不同优先级会话之间的冲突场景

### 1.3 关键约束
- **单会话约束**: 同一账号-店铺下只能有一个活跃会话
- **优先级原则**: 人工客服会话优先级高于机器人会话
- **安全隔离**: 严格控制会话访问权限
- **人工自由**：只有机器人发送会话才会创建session，人工可以随时发起聊天，该会话系统无法及时记录

## 2. 会话类型设计

### 2.1 会话创建者分类
```
Human Session (人工会话)
├── MANUAL_CUSTOMER_SERVICE  # 人工客服
├── MANUAL_COMPLAINT        # 人工投诉处理
└── MANUAL_URGENT           # 人工紧急处理

Robot Session (机器人会话)  
├── AUTO_BARGAIN           # 自动砍价
└── AUTO_FOLLOW_UP         # 自动跟单
```

### 2.2 会话状态机
```
会话状态转换:
PENDING        -> ACTIVE           # 等待激活 -> 激活
ACTIVE         -> COMPLETED        # 激活 -> 完成
ACTIVE         -> TRANSFERRED      # 激活 -> 转交人工
ACTIVE         -> PAUSED           # 激活 -> 暂停
PAUSED         -> ACTIVE           # 暂停 -> 恢复
TRANSFERRED    -> COMPLETED        # 转交 -> 完成
ANY            -> CANCELLED        # 任何状态 -> 取消
ANY            -> TIMEOUT          # 任何状态 -> 超时
```

### 2.3 会话优先级定义
```
优先级层级:
1. EMERGENCY (紧急)     - MANUAL_URGENT
2. HIGH (高)           - MANUAL_CUSTOMER_SERVICE, MANUAL_COMPLAINT  
3. MEDIUM (中)         - AUTO_BARGAIN
4. LOW (低)            - AUTO_FOLLOW_UP
```

## 3. 生命周期管理策略

### 3.1 机器人会话生命周期（由上游系统驱动）

#### 3.1.1 砍价任务会话支持
```
阶段1: 会话创建
- 上游砍价系统请求创建 AUTO_BARGAIN 会话
- 检查冲突（是否有活跃会话）
- 如有冲突则返回失败，由上游决定重试策略
- 创建成功则返回会话ID

阶段2: 会话使用
- 上游系统通过会话ID发送消息
- 本系统负责消息路由和存储
- 监控会话活跃度和异常情况

阶段3: 会话结束
- 上游系统通知任务完成（成功/失败/转人工）
- 更新会话状态为 COMPLETED/TRANSFERRED
- 记录结果并清理资源
```

### 3.2 人工会话生命周期
```
阶段1: 接管/创建
- 人工主动创建会话
- 或接管转交过来的机器人会话
- 检查是否与机器人会话冲突
- 按优先级处理冲突

阶段2: 人工处理
- 完全由人工控制
- 机器人会话自动暂停或等待
- 记录人工处理过程

阶段3: 结束
- 人工主动结束
- 自动超时结束 (默认8小时)
- 释放会话资源
```

### 3.3 消息处理机制
```
外部消息批次处理流程:
1. 消息预处理
   - 去重检查 (基于message_id)
   - 时间排序
   - 格式验证

2. 会话分组分析
   - 标志识别 (机器人标志)
   - 时间间隔分析 (超过30分钟视为新会话)
   - LLM语义分析 (可选)

3. 会话关联
   - 查找现有会话
   - 创建新会话
   - 更新会话状态

4. 消息入库
   - 批量插入消息
   - 更新会话统计
   - 触发相关事件
```

## 4. 会话优先级和冲突处理

### 4.1 优先级规则
```
优先级 (高 -> 低):
1. MANUAL_URGENT          # 紧急人工处理 (立即抢占)
2. MANUAL_CUSTOMER_SERVICE # 人工客服
3. MANUAL_COMPLAINT       # 人工投诉处理  
4. AUTO_BARGAIN          # 自动砍价
5. AUTO_FOLLOW_UP        # 自动跟单
```

### 4.2 冲突处理策略
```
情况1: 机器人会话进行中，人工要求创建会话
处理: 暂停机器人会话 -> 创建人工会话 -> 通知机器人等待

情况2: 人工会话进行中，机器人要求创建会话  
处理: 创建PENDING状态会话 -> 等待人工会话结束

情况3: 两个机器人任务冲突
处理: 按优先级决定 -> 高优先级执行 -> 低优先级等待

情况4: 紧急情况需要强制接管
处理: 立即中断当前会话 -> 创建紧急会话 -> 记录中断原因

情况5: 网络中断恢复后的会话冲突
处理: 检查会话状态 -> 恢复或重新分配 -> 通知相关系统

情况6: 机器人会话进行中，检测到需要人工处理
处理: 转交当前会话 -> 通知人工客服 -> 机器人退出会话
```

### 4.3 会话转交机制
```
转交触发条件:
- 机器人任务异常需要人工介入
- 通过消息分析检测到客户需要人工服务
- 客户明确要求人工客服
- 复杂问题超出机器人处理能力
- 系统检测到需要人工处理的场景

转交流程:
1. 检测转交需求
2. 暂停当前机器人会话
3. 创建转交记录
4. 通知人工客服系统
5. 更新会话状态为 TRANSFERRED
6. 交接上下文数据给人工

转交数据包含:
- 会话历史消息
- 当前任务执行状态
- 客户基本信息
- 转交原因和触发条件
- 机器人处理建议
- 紧急程度评级
```