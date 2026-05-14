# Futures Quant System

国内期货量化交易系统，基于 **FastAPI + Vue 3 + TqSdk** 构建，支持回测、模拟交易、实盘交易三种模式。

## 功能模块

| 模块 | 说明 |
|------|------|
| **回测引擎** | 双均线策略，支持主力合约移仓换月（独立回测/价差调整两种策略） |
| **自动研究框架** | 参数组合搜索 + 因子挖掘（IC/IR 评估），Celery 异步执行 |
| **数据持久化** | InfluxDB 存储 K 线，PostgreSQL 存储元数据，不依赖 TqSdk DataDownloader |
| **实时行情** | WebSocket 推送，前端 ECharts 实时 K 线图 |
| **持仓监控** | 实时持仓/回测历史持仓/盈亏分析，支持 CSV 导出 |
| **数据管理** | 数据下载、质量检测（红黄绿灯）、删除管理 |

## 技术栈

- **后端**: FastAPI, SQLAlchemy 2.0 (async), Celery, PostgreSQL, InfluxDB, Redis
- **前端**: Vue 3 (Composition API), Pinia, Element Plus, ECharts, Vite
- **交易**: TqSdk 3.0+（免费版）
- **部署**: Docker Compose

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- 天勤量化账号（免费版即可）

### 部署步骤

```bash
# 1. 克隆项目
git clone https://github.com/chievan/futures-quant-system.git
cd futures-quant-system

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入天勤账号信息
#   TQ_USERNAME=你的快期账号
#   TQ_PASSWORD=你的快期密码
#   TQ_BROKER=H徽商期货
#   TQ_ACCOUNT_ID=资金账号
#   TQ_TRADE_PWD=交易密码
#   TQ_MODE=backtest   # backtest | kq | live

# 3. 启动全部服务
docker compose up --build -d

# 4. 访问
#   前端: http://localhost:5173
#   API 文档: http://localhost:8000/docs
```

### 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TQ_USERNAME` | 天勤/快期账号 | - |
| `TQ_PASSWORD` | 天勤/快期密码 | - |
| `TQ_BROKER` | 期货公司标识 | - |
| `TQ_ACCOUNT_ID` | 资金账号 | - |
| `TQ_TRADE_PWD` | 交易密码 | - |
| `TQ_MODE` | 运行模式: backtest/kq/live | backtest |
| `ROLLOVER_STRATEGY` | 移仓策略: independent/spread_adjust | independent |
| `POSTGRES_*` | PostgreSQL 配置 | 默认值 |
| `INFLUXDB_*` | InfluxDB 配置 | 默认值 |

## 运行模式

所有策略代码三套模式共用，通过 `TQ_MODE` 切换：

- **backtest**: 回测模式，使用 TqSim 模拟交易，不连接真实行情
- **kq**: 快期模拟模式，连接模拟账号，模拟资金交易
- **live**: 实盘模式，连接真实交易账号，需谨慎使用

## 端到端验证流程

部署完成后，可通过以下流程验证系统功能：

1. **数据下载**: 进入 Data Management 页面，下载螺纹钢（rb）主力合约 30 天 1min K 线
2. **策略研究**: 进入 Research 页面，提交双均线参数搜索（fast 5-20, slow 20-60）
3. **查看结果**: 进入 Backtest Results 页面，查看收益曲线和交易记录
4. **持仓分析**: 进入 Positions 页面，查看持仓变化曲线和盈亏分析
5. **数据管理**: 进入 Data Management 页面，删除部分数据并重新下载

## 移仓换月策略

主力合约切换时支持两种处理策略（通过 `ROLLOVER_STRATEGY` 配置）：

- **independent（独立回测）**: 平旧仓、开新仓分别记录为独立交易，P&L 在切换时结算
- **spread_adjust（价差调整）**: 用价差调整持仓均价，保持 P&L 连续性，价差作为单独成本记录

## 开发

```bash
# 后端测试
cd backend
python3 -m pytest tests/ -v

# 前端开发
cd frontend
npm install
npm run dev
```

## License

MIT
