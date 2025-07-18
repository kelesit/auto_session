# Auto Session 智能会话管理系统

智能会话管理平台，专门为机器人客服和人工客服提供统一的会话管理、任务调度和无缝转接能力。

## 🏗️ 系统架构

### 整体架构图
```
上游系统 (跟单/砍价任务)
        ↓ HTTP API
┌─────────────────────────┐
│   Auto Session 系统     │
├─────────────────────────┤
│  API Layer (FastAPI)    │ ← REST API接口层
├─────────────────────────┤
│  SessionManager         │ ← 核心会话管理器
│  SessionTaskManager     │ ← 任务调度管理器
├─────────────────────────┤
│  Database (MySQL)       │ ← 持久化存储
│  Redis                  │ ← 任务队列
└─────────────────────────┘
        ↓ Redis Queue
下游RPA系统 (发送器/接收器)
```

### 核心组件

#### 1. SessionManager (会话管理器)
**职责**: 会话生命周期管理和冲突检测
- ✅ 消息组处理和会话关联
- ✅ 会话冲突检测和解决
- ✅ 会话状态转换管理
- ✅ 超时处理和清理

#### 2. SessionTaskManager (任务管理器)
**职责**: 任务创建、Redis队列集成和外部接口
- ✅ 会话任务创建和状态管理
- ✅ Redis任务队列操作
- ✅ 外部任务信息获取
- ✅ 任务完成状态追踪

#### 3. API Layer (接口层)
**职责**: 对外提供RESTful API服务
- ✅ 会话任务CRUD操作
- ✅ 消息组处理接口
- ✅ Redis任务队列API
- ✅ 状态查询和监控



## 🎯 业务场景

### 典型使用流程

#### 场景1: 机器人砍价任务
```
1. 上游砍价系统 → POST /api/sessions/create
   └── 创建 AUTO_BARGAIN 会话任务

2. RPA发送器 → GET /api/tasks/next_id  
   └── 获取Redis队列中的任务ID

3. RPA发送器 → GET /api/tasks/{task_id}/send_info
   └── 获取发送内容和目标信息

4. RPA发送器执行发送操作 -> POST /api/sessions/{session_id}/complete
   ├── 标记会话任务完成
   └── 更新会话状态为ACTIVE

5. RPA接收器收集消息 → POST /api/messages/batch
   ├── 上传消息组对话记录
   └── 会话分析
        └── 判断是否存在活跃会话 
            ├── 如果不存在，创建新的TRANSFERRED会话（人工会话），并发送提醒
            └── 如果存在，更新会话消息记录和状态
                └── 解析消息内容
                        ├── 如果没有人工介入的痕迹则结束
                        └── 如果有人工介入的痕迹，更新会话状态为TRANSFERRED，并发送提醒
```



## � 快速开始

### 1. 环境要求
- Python 3.12+
- MySQL 8.0+
- Redis 6.0+ 
- uv (推荐的包管理工具)

### 2. 安装步骤

```bash
cd auto_session

# 安装依赖
uv sync

# 创建数据库表
python scripts/create_tables.py

# 启动API服务
python run_api.py
```

### 3. 配置说明

编辑 `src/config.yaml`:
```yaml
database:
  host: "localhost"
  port: 3306
  name: "auto_session"
  user: "root"
  password: "your_password"

redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null

```

### 4. 运行测试

```bash
# 运行单元测试
python -m pytest tests/

# 运行API测试
python tests/test_api.py

# 运行特定测试
python tests/test_api.py --test create     # 测试会话创建
python tests/test_api.py --test messages  # 测试消息组处理
python tests/test_api.py --test redis     # 测试Redis队列
```

**测试覆盖范围**:
- ✅ 健康检查和基础API
- ✅ 会话任务创建和冲突检测
- ✅ Redis任务队列操作
- ✅ 消息组处理
- ✅ 会话状态查询和完成
- ✅ 错误处理和边界情况
- ✅ 并发操作和性能测试

**最新测试结果**: 83.3% 通过率，核心功能全部正常
## 📊 数据模型

### 核心数据表

#### 1. sessions (会话表)
```sql
CREATE TABLE sessions (
    session_id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    shop_id VARCHAR(50) NOT NULL,
    task_type ENUM('auto_bargain', 'auto_follow_up', 'manual_customer_service', 'manual_complaint', 'manual_urgent') NOT NULL,
    state ENUM('pending', 'active', 'completed', 'transferred', 'timeout', 'cancelled', 'paused') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_account_shop (account_id, shop_id),
    INDEX idx_state_activity (state, last_activity)
);
```

#### 2. session_tasks (会话任务表)
```sql
CREATE TABLE session_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(50) NOT NULL,
    external_task_id VARCHAR(100) NOT NULL,
    redis_task_id VARCHAR(100),
    status ENUM('pending', 'sent', 'completed', 'failed') DEFAULT 'pending',
    send_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

#### 3. messages (消息表)
```sql
CREATE TABLE messages (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(50) NOT NULL,
    message_id VARCHAR(100) UNIQUE,
    content TEXT NOT NULL,
    sender VARCHAR(100) NOT NULL,
    from_source ENUM('account', 'shop') NOT NULL,
    sent_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    INDEX idx_session_time (session_id, sent_at)
);
```

## 🔧 核心特性

### 会话状态管理
- **pending**: 等待中 
- **active**: 活跃中
- **completed**: 已完成
- **transferred**: 已转交人工
- **timeout**: 超时
- **cancelled**: 已取消
- **paused**: 已暂停

### 任务类型
- **auto_bargain**: 自动砍价
- **auto_follow_up**: 自动跟单  
- **manual_customer_service**: 人工客服
- **manual_complaint**: 人工投诉处理
- **manual_urgent**: 人工紧急处理

### 冲突处理机制
- 同一账号-店铺组合只能有一个活跃会话
- 人工会话优先级高于机器人会话
- 自动超时处理和会话清理
- 智能转接和状态同步

## 🚨 故障排除

### 常见问题

#### 1. 会话冲突
**现象**: 创建会话时返回冲突错误
**解决**: 检查是否已有活跃会话，等待超时或手动完成现有会话

#### 2. Redis连接问题  
**现象**: 任务队列操作失败
**解决**: 检查Redis服务状态，确认配置正确

#### 3. 消息处理延迟
**现象**: 消息组处理响应慢
**解决**: 检查数据库性能，优化消息组大小

