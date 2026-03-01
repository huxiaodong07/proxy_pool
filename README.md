# proxy_pool

## 项目目标
构建一个可持续运行的代理池系统，包含两条核心能力：

1. **定时采集 + 定时质检**
   - 自动检索互联网免费代理并入库。
   - 自动检测代理有效性并标记状态。
   - 检测维度包含：
     - 基础可连通性（IP:Port 能否握手、延迟、成功率）
     - 流媒体解锁能力（例如 Netflix/Disney+/YouTube Premium）
     - AI 平台可用性（例如 OpenAI/Claude/Gemini 站点或 API 可达性）

2. **对外 HTTPS API 服务**
   - 提供代理池查询接口（按协议、地区、匿名级别、可用性标签筛选）。
   - 支持面向业务侧的稳定提取能力（限流、鉴权、可观测）。

---

## 推荐总体架构

建议采用“**采集层 → 评估层 → 存储层 → 服务层**”分层架构：

```text
[Scheduler]
   ├── Crawl Jobs（采集任务）
   ├── Verify Jobs（连通性验证）
   ├── Streaming Check Jobs（流媒体检测）
   └── AI Check Jobs（AI平台检测）

[Workers]
   ├── Crawler Worker
   ├── TCP/HTTP Probe Worker
   ├── Streaming Probe Worker
   └── AI Probe Worker

[Storage]
   ├── MySQL/PostgreSQL（主数据）
   ├── Redis（热点缓存/队列/限流）
   └── Object Storage（可选：检测日志快照）

[HTTPS API]
   ├── 查询代理
   ├── 统计报表
   ├── 管理接口（可选）
   └── 鉴权/限流
```

---

## 核心模块设计

### 1) 代理采集模块（Crawler）

**职责**
- 支持多源抓取：公开代理网站、GitHub 列表、论坛/文本源。
- 统一解析成标准格式：`ip, port, protocol, source, country, anonymity`。
- 做首轮去重与格式校验后写入数据库。

**关键点**
- 对每个 source 建立可插拔 parser（便于扩展）。
- 记录 `source` 与 `first_seen_at`，便于后续质量统计。
- 写入前做幂等（`ip + port + protocol` 唯一索引）。

---

### 2) 代理检测模块（Verifier）

建议拆分为三阶段，避免一次检测过慢：

#### A. 基础连通检测
- TCP 握手 + HTTP 请求测试（例如访问 `https://httpbin.org/ip`）。
- 输出指标：`connect_ok`, `latency_ms`, `last_checked_at`, `fail_count`。
- 连续失败 N 次（如 3~5 次）标记为 `inactive`。

#### B. 流媒体解锁检测
- 针对目标站点构造轻量请求（尽量避免高成本页面渲染）。
- 根据状态码/响应特征判断：
  - `unlocked`
  - `partial`
  - `blocked`
- 结果按平台分别存储（例如 `streaming_netflix_status`）。

#### C. AI 平台可用性检测
- 站点可达性检测（DNS/TLS/HTTP）。
- API 可用性（如仅做 `/v1/models` 或轻量探针请求，注意密钥隔离）。
- 结果标签化（`ai_openai=ok/blocked/timeout`）。

**调度建议**
- A 高频（5~15 分钟）
- B 中频（1~6 小时）
- C 中频（1~6 小时）
- 使用任务队列（Celery/RQ/Sidekiq/Kafka consumer）提高吞吐。

---

### 3) 数据库模型（建议）

#### `proxies`（主表）
- `id`
- `ip`
- `port`
- `protocol` (http/https/socks5)
- `country`, `region`, `city`（可选）
- `anonymity`
- `source`
- `status` (active/inactive)
- `latency_ms`
- `success_rate`
- `fail_count`
- `first_seen_at`, `last_seen_at`, `last_checked_at`
- 唯一索引：`(ip, port, protocol)`

#### `proxy_checks`（检测明细表）
- `id`, `proxy_id`
- `check_type` (connectivity/streaming/ai)
- `target` (netflix/openai/...)
- `result` (ok/blocked/timeout/error)
- `response_time_ms`
- `checked_at`
- `raw_meta` (json)

#### `proxy_tags`（可选）
- `proxy_id`
- `tag_key`, `tag_value`
- 如：`streaming_netflix=unlocked`, `ai_openai=ok`

---

### 4) HTTPS API 设计

#### 面向消费者接口
- `GET /api/v1/proxies/random`
  - 返回一条可用代理，可按 query 过滤：
  - `protocol=https&country=US&streaming_netflix=unlocked&ai_openai=ok`
- `GET /api/v1/proxies/list`
  - 分页列表，支持排序（延迟、成功率、最近检测时间）。

#### 管理与观测接口（建议鉴权）
- `GET /api/v1/stats/summary`
- `GET /api/v1/stats/sources`
- `POST /api/v1/admin/recheck/{proxy_id}`

**接口治理**
- HTTPS 强制。
- API Key/JWT 鉴权（对外建议 API Key + IP 白名单）。
- 限流（令牌桶，按 key + IP）。
- 响应缓存（Redis 短 TTL）减少数据库压力。

---

## 调度与状态机建议

### 代理状态机
- `new` → `active` → `suspect` → `inactive`
- 连续失败进入 `suspect`，再失败转 `inactive`
- 一旦检测成功可从 `suspect/inactive` 回到 `active`

### 任务编排
- `crawl_job` 写入候选池。
- `verify_connectivity_job` 优先处理 `new/suspect`。
- `verify_streaming_job` 和 `verify_ai_job` 仅处理 `active` 且基础连通成功的代理。
- 对超时代理指数退避，避免无效重试风暴。

---

## 可靠性与风控

- **反爬与封禁规避**：采集源请求限速、UA 轮换、失败重试上限。
- **成本控制**：流媒体/AI 检测不宜过频，采用分层抽检 + 全量轮询结合。
- **数据质量**：
  - 引入“可用分”评分：`score = w1*success_rate - w2*latency - w3*recent_fail_penalty`
  - API 默认返回高分代理。
- **可观测性**：
  - Prometheus 指标：任务耗时、成功率、活跃代理数、各标签分布。
  - 告警：活跃代理数跌破阈值、某 source 持续失败。

---

## 推荐技术选型（可替换）

- **语言/框架**：Python + FastAPI（开发快）
- **调度与异步任务**：Celery + Redis（或 APScheduler + 自建队列）
- **数据库**：PostgreSQL/MySQL
- **缓存**：Redis
- **部署**：Docker Compose 起步，后续可迁移 K8s
- **监控**：Prometheus + Grafana

---

## 分阶段落地路线图

### Phase 1（MVP，1~2 周）
- 完成代理抓取 + 基础连通检测 + API 随机提取。
- 建立最小可用数据表和定时任务。

### Phase 2
- 增加流媒体与 AI 平台标签检测。
- 增加评分机制与多维过滤查询。

### Phase 3
- 增加可观测性、告警、管理后台。
- 实现多实例 worker 扩展与高可用。

---

## 最小可用 API 返回示例

```json
{
  "ip": "1.2.3.4",
  "port": 8080,
  "protocol": "https",
  "country": "US",
  "latency_ms": 231,
  "success_rate": 0.92,
  "tags": {
    "streaming_netflix": "unlocked",
    "ai_openai": "ok"
  },
  "last_checked_at": "2026-03-01T09:00:00Z"
}
```

---

## 当前已实现（Step 1）

- FastAPI 应用骨架与健康检查接口：`GET /healthz`
- Celery worker 骨架与示例任务：`proxy_pool.ping`
- Docker Compose 本地开发编排：`api` / `worker` / `redis` / `postgres`
- 最小化接口测试：`tests/test_health.py`
- 数据库层基础设施：SQLAlchemy 模型（`proxies/proxy_checks/api_keys`）+ Alembic 初始迁移
- 采集模块基础能力：可插拔 parser（文本/csv）、双 source 采集、候选代理规范化与入库去重
- 连通性检测基础能力：批量探测任务、状态迁移（new/suspect/inactive）、检测流水写入 `proxy_checks`
- 对外代理查询 API（MVP）：`GET /api/v1/proxies/random` 与 `GET /api/v1/proxies/list`（支持协议/国家/状态/成功率过滤）
- API 鉴权 + 限流 + 缓存：`X-API-Key` 校验、每 key+IP QPS 限流、查询结果短 TTL 缓存
- 可观测基础能力：`/metrics` Prometheus 指标（HTTP 请求量/延迟、任务执行计数）
- Phase 2 检测能力：流媒体/AI 批量检测任务（`verify_streaming`/`verify_ai`）+ 标签写入（`proxy_tags`）
- API 标签过滤：支持 `streaming_netflix` 与 `ai_openai` 条件检索

### 本地启动

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Compose 启动

```bash
docker compose up -d
```

### 数据库迁移

```bash
alembic upgrade head
```

## 实施落地

- 详细分步计划请见：[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md)

## 结论

这个项目的关键是：
1. **采集与检测解耦**（提高吞吐和可维护性）
2. **检测分层**（基础连通高频，业务能力中频）
3. **对外 API 做好鉴权、限流和缓存**（保证可用性）
4. **用评分与标签体系驱动代理选择**（保证输出质量）

按上述架构推进，可以先快速上线 MVP，再逐步增强检测深度和稳定性。
