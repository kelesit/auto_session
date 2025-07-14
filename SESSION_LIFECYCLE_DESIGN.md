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

## 5. 数据模型设计

### 5.1 核心表结构
```sql
-- 会话表 (已有，需扩展)
ALTER TABLE sessions ADD COLUMN priority INT DEFAULT 3;
ALTER TABLE sessions ADD COLUMN external_task_id VARCHAR(100);
ALTER TABLE sessions ADD COLUMN timeout_at DATETIME;
ALTER TABLE sessions ADD COLUMN transferred_at DATETIME;
ALTER TABLE sessions ADD COLUMN transfer_reason TEXT;

-- 会话转交记录表
CREATE TABLE session_transfers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(50) NOT NULL,
    from_type ENUM('robot', 'human') NOT NULL,
    to_type ENUM('robot', 'human') NOT NULL,
    transfer_reason TEXT,
    transfer_data JSON,
    transferred_by VARCHAR(50),
    transferred_at DATETIME DEFAULT NOW(),
    accepted_by VARCHAR(50),
    accepted_at DATETIME,
    status ENUM('pending', 'accepted', 'rejected') DEFAULT 'pending',
    urgency_level ENUM('low', 'medium', 'high', 'urgent') DEFAULT 'medium',
    INDEX idx_session_id (session_id),
    INDEX idx_transferred_at (transferred_at),
    INDEX idx_status (status)
);

-- 外部任务关联表
CREATE TABLE external_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    session_id VARCHAR(50),
    task_type ENUM('bargain', 'follow_up', 'custom') NOT NULL,
    task_status ENUM('pending', 'running', 'completed', 'failed', 'transferred') DEFAULT 'pending',
    task_data JSON,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    INDEX idx_task_id (task_id),
    INDEX idx_session_id (session_id)
);

-- 会话操作日志表
CREATE TABLE session_operations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(50) NOT NULL,
    operation_type ENUM('create', 'pause', 'resume', 'transfer', 'complete', 'cancel') NOT NULL,
    operator_id VARCHAR(50) NOT NULL,
    operator_type ENUM('robot', 'human', 'system') NOT NULL,
    operation_data JSON,
    operation_at DATETIME DEFAULT NOW(),
    INDEX idx_session_id (session_id),
    INDEX idx_operation_at (operation_at)
);
```

### 5.2 数据关系图
```
accounts (账号) 1:N sessions (会话)
shops (店铺) 1:N sessions (会话)
sessions (会话) 1:N messages (消息)
sessions (会话) 1:N session_transfers (转交记录)
sessions (会话) 1:1 external_tasks (外部任务)
sessions (会话) 1:N session_operations (操作日志)
```

## 6. 安全和监控

### 6.1 安全机制
```
1. 权限控制: 
   - 机器人只能操作自己创建的会话
   - API密钥认证
   - 请求频率限制

2. 时间限制: 
   - 机器人会话最大存活时间 (默认1小时)
   - 人工会话最大存活时间 (默认8小时)
   - 转交等待超时 (默认5分钟)

3. 操作审计: 
   - 记录所有会话操作
   - 敏感操作需要双重验证
   - 定期审计报告

4. 异常处理: 
   - 机器人异常自动转人工
   - 系统异常告警
   - 自动恢复机制

5. 资源保护: 
   - 限制机器人并发会话数量
   - 内存和CPU使用监控
   - 数据库连接池管理
```

### 6.2 监控指标
```
业务指标:
- 活跃会话数量
- 会话创建/完成速率
- 平均会话时长
- 转交成功率
- 任务完成率
- 会话冲突率

技术指标:
- API响应时间
- 数据库查询性能
- 内存使用率
- CPU使用率
- 错误率

告警规则:
- 活跃会话超过阈值 (>1000)
- API响应时间超过500ms
- 错误率超过5%
- 转交等待超过10分钟
- 会话冲突率超过10%
- 数据库连接池耗尽
```

### 6.3 异常处理策略
```
网络异常:
- 自动重试机制 (最多3次)
- 降级服务 (只读模式)
- 会话状态保护

系统异常:
- 自动故障转移
- 数据一致性检查
- 服务健康检查

业务异常:
- 超时会话自动清理
- 异常会话自动转人工
- 数据修复工具
```

## 7. 接口设计详细

### 7.1 会话管理接口 (对外API)
```python
class SessionAPI:
    def create_robot_session(
        self, 
        account_id: str, 
        shop_id: str, 
        task_type: TaskType,
        external_task_id: str,
        timeout_minutes: int = 60,
        priority: int = 3
    ) -> SessionCreationResult
    
    def complete_session(
        self, 
        session_id: str, 
        result: dict,
        external_task_id: str
    ) -> bool
    
    def transfer_to_human(
        self,
        session_id: str,
        reason: str,
        context_data: dict,
        external_task_id: str,
        urgency_level: str = 'medium'
    ) -> TransferResult
    
    def get_session_status(
        self, 
        session_id: str
    ) -> SessionStatusInfo
    
    def check_session_availability(
        self, 
        account_id: str, 
        shop_id: str, 
        task_type: TaskType
    ) -> AvailabilityResult
    
    def pause_session(
        self,
        session_id: str,
        external_task_id: str
    ) -> bool
    
    def resume_session(
        self,
        session_id: str,
        external_task_id: str
    ) -> bool
```

### 7.2 消息处理接口 (内部使用)
```python
class MessageProcessor:
    def process_chat_messages(
        self,
        account_id: str,
        shop_id: str,
        messages: List[MessageData]
    ) -> ProcessResult
    
    def add_message_to_session(
        self,
        session_id: str,
        message: MessageData
    ) -> bool
    
    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[MessageData]
```

### 7.3 数据模型定义
```python
@dataclass
class SessionCreationResult:
    success: bool
    session_id: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    conflict_session_id: Optional[str]

@dataclass
class TransferResult:
    success: bool
    transfer_id: Optional[str]
    estimated_wait_time: Optional[int]  # 分钟
    error_message: Optional[str]
    notification_sent: bool = False

@dataclass  
class AvailabilityResult:
    available: bool
    current_session_id: Optional[str]
    current_session_type: Optional[TaskType]
    estimated_available_at: Optional[datetime]
    
@dataclass
class MessageData:
    message_id: str
    content: str
    from_source: str  # "shop" or "account"
    sent_at: datetime
    platform_data: Optional[dict] = None
```

### 第一阶段 (核心会话管理) - 2周
1. 扩展数据模型
   - 创建转交记录表
   - 创建外部任务关联表  
   - 创建操作日志表
   - 扩展会话表字段

2. 实现会话管理核心功能
   - 会话创建和冲突检测
   - 会话状态管理
   - 优先级处理

3. 实现消息处理机制
   - 消息批次处理
   - 消息去重
   - 会话关联逻辑

## 第二阶段 (API完善) - 3周  
1. FastAPI接口实现
   - RESTful API设计
   - 请求验证和错误处理
   - API文档生成

2. 转交机制实现
   - 转交流程管理
   - 人工通知系统集成
   - 上下文数据传递

3. 监控和告警
   - 指标收集
   - 告警规则配置
   - 健康检查接口

### 第三阶段 (集成优化) - 2周
1. 与上游任务系统集成测试
   - 接口联调
   - 压力测试
   - 容错测试

2. 性能优化和稳定性增强
   - 数据库优化
   - 缓存策略
   - 连接池配置

3. 监控指标和运维工具
   - 监控仪表板
   - 日志分析工具
   - 数据修复工具

## 8. 风险评估和缓解措施

### 8.1 技术风险
```
风险1: 会话状态不一致
缓解: 定期一致性检查 + 自动修复

风险2: 高并发下的性能问题  
缓解: 连接池 + 缓存 + 分库分表

风险3: 转交失败导致会话丢失
缓解: 重试机制 + 降级处理 + 异常记录

风险4: 外部系统依赖故障
缓解: 断路器模式 + 本地缓存
```

### 8.2 业务风险
```
风险1: 机器人异常导致客户流失
缓解: 自动转人工 + 快速故障恢复

风险2: 会话冲突导致任务失败
缓解: 精确的冲突检测 + 重试机制

风险3: 人工处理能力不足
缓解: 负载均衡 + 弹性扩容 + 优先级排队
```