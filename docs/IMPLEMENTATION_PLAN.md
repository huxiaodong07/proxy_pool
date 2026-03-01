# Proxy Pool 分步实现计划（可执行版）

> 目标：在 2~4 周内交付一个可上线的 MVP，并可平滑演进到支持流媒体/AI 标签检测的生产版本。

## 1. 范围定义（先做什么，不做什么）

### 1.1 本期必须实现（MVP）
- 定时采集免费代理（多 source，可扩展）。
- 定时做基础可用性检测（连通、延迟、成功率、失效标记）。
- 提供 HTTPS API：随机获取代理 + 条件筛选列表。
- 基础鉴权（API Key）+ 限流（按 key/IP）。

### 1.2 本期暂不实现（Phase 2）
- 完整浏览器级流媒体检测（先做轻量 HTTP 探测）。
- AI API 真实调用检测（先做可达性与站点级探测）。
- 后台管理 UI（先留管理 API）。

---

## 2. 建议目录结构（第一天就搭好）

```text
proxy_pool/
├── app/
│   ├── api/                 # FastAPI routers
│   ├── core/                # 配置、日志、鉴权、限流
│   ├── db/                  # ORM 模型、迁移
│   ├── services/
│   │   ├── crawl/           # 采集器及 parser
│   │   ├── verify/          # 检测器
│   │   └── scoring/         # 评分逻辑
│   ├── workers/             # Celery 任务
│   └── main.py              # API 入口
├── tests/
├── scripts/                 # 本地运维脚本
├── docs/
│   └── IMPLEMENTATION_PLAN.md
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 3. 数据库设计（先稳定 schema，再写业务）

## 3.1 `proxies`（主表）
- 唯一键：`(ip, port, protocol)`
- 核心字段：
  - `status`: `new|active|suspect|inactive`
  - `latency_ms`, `success_rate`, `fail_count`
  - `first_seen_at`, `last_seen_at`, `last_checked_at`
  - `source`, `country`, `anonymity`

## 3.2 `proxy_checks`（检测流水）
- 字段：`proxy_id, check_type, target, result, response_time_ms, raw_meta, checked_at`
- 用途：追踪检测历史、统计失败原因。

## 3.3 `api_keys`（对外鉴权）
- 字段：`key_hash, owner, status, qps_limit, daily_quota, created_at`

---

## 4. 任务调度与执行策略

## 4.1 定时任务
- `crawl_sources_job`：每 15~30 分钟。
- `verify_connectivity_job`：每 5~10 分钟。
- `recheck_inactive_job`：每 2~6 小时。
- `refresh_score_job`：每 30 分钟。

## 4.2 并发策略
- Celery + Redis。
- 分队列：`crawl`, `verify_fast`, `verify_slow`, `maintenance`。
- 优先级：`new/suspect > active > inactive`。

## 4.3 状态机
- `new -> active`：首次检测成功。
- `active -> suspect`：连续失败达到阈值（如 2）。
- `suspect -> inactive`：继续失败（如 3~5）。
- `inactive -> active`：复检成功。

---

## 5. 分步实现（按 PR 切分）

## Step 1：项目骨架 + 本地开发环境
**输出**
- FastAPI + Celery + Redis + PostgreSQL 在 `docker-compose` 可一键启动。
- 健康检查接口：`GET /healthz`。

**验收标准**
- `docker compose up -d` 后 API 可访问。
- Celery worker 正常连接 broker。

---

## Step 2：数据库与迁移
**输出**
- 建立 `proxies`, `proxy_checks`, `api_keys`。
- 建立唯一索引和常用查询索引（`status`, `last_checked_at`, `country`）。

**验收标准**
- 迁移可重复执行（幂等）。
- 插入重复代理时不会产生脏数据。

---

## Step 3：采集模块（最少 2 个 source）
**输出**
- 抽象 `BaseParser`，实现 `SourceAParser`, `SourceBParser`。
- 入库前完成：格式校验、去重、协议标准化。

**验收标准**
- 单次采集可新增代理。
- 异常 source 不影响其他 source（失败隔离）。

---

## Step 4：基础连通性检测
**输出**
- TCP/HTTP 探测器。
- 记录延迟、成功/失败、失败原因。
- 更新状态机与失败计数。

**验收标准**
- 可将不可用代理自动标记 `inactive`。
- 可从 `inactive` 复活到 `active`（复检成功）。

---

## Step 5：对外 API（MVP）
**输出**
- `GET /api/v1/proxies/random`
- `GET /api/v1/proxies/list`
- 支持过滤：`protocol,country,status,min_score`

**验收标准**
- API 返回仅包含可用代理（默认 `active`）。
- 分页、排序、过滤正确。

---

## Step 6：鉴权 + 限流 + 缓存
**输出**
- API Key 中间件。
- Redis 令牌桶限流（key + IP）。
- 热门查询结果缓存（TTL 5~30 秒）。

**验收标准**
- 无 key 拒绝访问。
- 超限请求返回 429。

---

## Step 7：可观测与运维
**输出**
- Prometheus 指标：
  - 采集数、有效率、平均延迟、任务耗时、API QPS。
- 基础告警：活跃代理低于阈值。

**验收标准**
- Grafana 可见核心仪表盘。
- 告警可触发并可恢复。

---

## Step 8（Phase 2）：流媒体与 AI 检测
**输出**
- `verify_streaming_job`（轻量探测版本）。
- `verify_ai_job`（站点/API 可达性探测）。
- 标签输出：`streaming_xxx`, `ai_xxx`。

**验收标准**
- API 可按标签筛选代理。
- 探测任务失败不影响基础可用性任务。

---

## 6. 测试策略（必须落地）

## 6.1 单元测试
- parser 输入输出测试。
- 状态机迁移测试。
- 评分函数测试。

## 6.2 集成测试
- 采集 -> 入库 -> 检测 -> API 查询的端到端测试。
- 鉴权与限流测试。

## 6.3 回归清单
- 重复代理不会重复入库。
- 连续失败阈值逻辑正确。
- API 在空池场景返回可预期响应。

---

## 7. 里程碑计划（建议）

- **Week 1**：Step 1~3（骨架、DB、采集）
- **Week 2**：Step 4~6（检测、API、鉴权限流）
- **Week 3**：Step 7（监控）+ 稳定性打磨
- **Week 4**：Step 8（流媒体/AI 标签检测）

---

## 8. 每个 PR 的模板（建议严格执行）

每个 PR 必须包含：
1. 变更内容（做了什么）
2. 验收方式（如何验证）
3. 回滚方式（如何撤销）
4. 风险评估（可能影响哪里）

---

## 9. 首个可执行任务清单（今天就能开工）

1. 初始化 FastAPI/Celery 项目骨架。  
2. 编写数据库迁移并创建三张核心表。  
3. 接入 2 个代理 source parser。  
4. 实现基础连通性探测任务。  
5. 暴露 `random/list` 两个 API。  
6. 加 API Key 与限流。  
7. 补齐最小测试与 CI。  

完成以上 7 项后，即具备可用 MVP。
