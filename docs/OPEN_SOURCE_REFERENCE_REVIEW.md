# FinPilot 开源投顾项目源码拆解

审查日期：2026-08-28  
目的：为 FinPilot 的 A 股、港股 C 端智能投顾版本选择可借鉴的开源架构，同时避免把演示性计算、海外数据口径或不兼容许可证直接带入产品。

## 1. 获取结果

三个仓库已放在项目之外的独立目录：

`C:\Users\lwh\Documents\ChatGPT\金融投顾agent_开源参考`

| 项目 | 本地目录 | 审查提交 | 许可证 | 本项目使用原则 |
|---|---|---:|---|---|
| FinRobot | `FinRobot` | `d221910` | Apache-2.0，另有 NOTICE 和商标政策 | 借鉴研究流水线、报告结构和“代码算数、LLM 解释”；计算公式必须重做 |
| TradingAgents | `TradingAgents` | `a33fd4c` | Apache-2.0 | 借鉴状态图、角色分工、结构化输出、失败显式化；不照搬自动交易结论 |
| OpenBB | `OpenBB` | `3e071fc` | AGPL-3.0 | 只研究 Provider/标准模型设计；未完成许可证评估前不复制代码进 FinPilot |

三个仓库都是浅克隆，只保留当前版本，不包含完整 Git 历史。FinRobot 的 `FinNLP` 子模块尚未初始化，因为本轮关注的是公司研究、财报、估值和数据适配，并不依赖该子模块。

## 2. 先说结论

最适合我们的组合不是选择其中一个项目整体改造，而是：

```text
FinRobot 的研究流水线和报告分层
        +
TradingAgents 的可追踪状态图、正反论证和结构化输出
        +
OpenBB 的标准数据模型与 Provider 适配思想
        +
FinPilot 自己的中国官方披露源、证据门槛和用户风险约束
```

三类项目都没有直接解决我们的核心问题：面向中国投资小白，在 A 股和港股官方披露证据上，给出有边界、可解释、能被用户调整的建议。因此不能把“成功运行开源项目”当作完成产品；真正有求职展示价值的是我们如何把这些思想改造成中国市场的可信闭环。

## 3. FinRobot：最值得学研究分层，不值得照搬估值数字

### 值得借鉴

1. **确定性计算与 LLM 叙述分离**

   README 明确提出财务数字由 Python 计算，LLM 负责推理、综合和报告表达。这与 FinPilot 当前方法文档中的边界一致，应继续坚持。

2. **数据、分析、建模、综合、报告分阶段**

   研究流程被拆成不同职责，而不是让一个模型在一段 Prompt 里同时找数据、算估值和下结论。适合映射为 FinPilot 的“证据采集 → 财务归一化 → 估值 → 事件 → 反方 → 风险门槛 → 用户卡片”。

3. **报告章节和来源标注**

   `finrobot_equity/core/src/modules/report_structure.py` 定义了公司概览、财务、估值、催化剂、风险、建议等章节，并保留 `data_sources` 和 AI 内容标识。可以借鉴“每个结论都知道来自哪个证据”的数据结构。

4. **财务数据与叙述 Agent 分离**

   `finrobot_equity/core/src/modules/equity_agents/agent_manager.py` 先把财务表、同行数据和新闻整理成输入，再由不同 Agent 生成公司概览、估值、风险等文本。我们可以保留这种职责分离，但 Agent 输入应改为带证据 ID 的结构化事实，不应只拼成一大段 Markdown。

### 不能照搬

1. **估值包含演示性硬编码**

   `finrobot_equity/core/src/modules/valuation_engine.py` 中存在以下简化：

   - 没有历史倍数时默认 EV/EBITDA 为 12 倍、标准差为 3 倍；
   - 以企业价值的 10% 代替真实净负债；
   - 缺少自由现金流时，以 EBITDA 的 60% 代替；
   - DCF 默认前五年增长 10%、后五年增长 5%、WACC 10%；
   - 各估值方法的 0.5、0.6、0.7“置信度”是固定值。

   这些只能展示算法形状，不能支撑真实股票目标价。FinPilot 不应把这些数字带入真实公司研究。

2. **预测增长不是一致预期**

   `financial_data_processor.py` 和 `generate_financial_analysis.py` 接受预设收入增速、利润率改善与每年 5% PE 压缩。这是情景假设，不是动态市盈率所需的 NTM/FY1 一致预期。界面必须把“用户/模型情景”与“市场一致预期”分开。

3. **数据体系偏美国市场**

   主要依赖 FMP、yfinance、SEC EDGAR，不能替代巨潮资讯、上交所、深交所、港交所披露易和公司 IR。

4. **来源标注粒度仍然偏粗**

   现有 `ReportSection.data_sources` 主要是章节级来源列表。我们的目标应提升到结论或指标级：公告链接、披露日期、报告期、页码/表格位置、原始值、归一化值和计算公式。

### 建议重点阅读的文件

| 文件 | 用途 | 处理意见 |
|---|---|---|
| `finrobot_equity/core/src/modules/report_structure.py` | 报告分层、来源、AI 标记 | 借鉴结构 |
| `finrobot_equity/core/src/modules/financial_data_processor.py` | 财务字段抽取与派生指标 | 借鉴流程，重做中国会计字段映射 |
| `finrobot_equity/core/src/modules/equity_agents/agent_manager.py` | 多类研究文本生成 | 借鉴任务拆分，改为结构化证据输入 |
| `finrobot_equity/core/src/modules/valuation_engine.py` | 多估值方法与区间 | 仅作反例和接口参考，不采用默认假设 |
| `finrobot/data_source/sec_utils.py` | 官方文件下载与章节读取 | 映射为 CNINFO/HKEX 文件存储流程 |

## 4. TradingAgents：最值得学 Agent 工作流，但最终结论需要硬门槛

### 值得借鉴

1. **可见的状态图**

   `tradingagents/graph/setup.py` 明确连接市场、情绪、新闻、基本面、牛方、熊方、研究经理、风险角色和组合经理。它比“一个聊天框背后偷偷跑 Prompt”更适合求职展示，因为每个节点输入输出和停止条件都能解释。

2. **共享状态而不是散落文本**

   `tradingagents/agents/utils/agent_states.py` 保存各研究报告、辩论历史、投资计划、交易计划、风险讨论和最终决定。FinPilot 可以采用同类状态对象，但应增加证据集合、缺失项、口径冲突、数据新鲜度和用户风险预算。

3. **关键输出使用 Pydantic 结构**

   `tradingagents/agents/schemas.py` 把研究计划、交易提议和组合决定限制为固定字段，降低自由文本漂移。FinPilot 的最终输出也应是结构化对象，再渲染为小白可读卡片。

4. **数据失败必须显式暴露**

   `tradingagents/dataflows/interface.py` 区分限流、未配置、无数据和普通错误，并明确告诉 Agent 不得估算或编造。这个思路与 FinPilot 已有快速失败、离线降级一致，应扩展到财报和公告。

5. **确定性行情快照**

   `tradingagents/dataflows/market_data_validator.py` 用代码计算并验证行情与技术指标，再要求 LLM 将其作为精确数字的事实源。这种“事实快照”模式可以平移到财务报表和估值。

### 不能照搬

1. **最终评级仍由 LLM 综合辩论生成**

   `portfolio_manager.py` 要求模型在 Buy、Overweight、Hold、Underweight、Sell 中给出决定，但没有在该节点之前强制检查公告缺失、数据过期、审计问题、预测覆盖数量和用户集中度。对 C 端用户来说，仅靠角色辩论不能代替硬门槛。

2. **角色提示可能放大立场，而不是提高事实质量**

   Bull、Bear、Aggressive、Conservative 的 Prompt 会主动要求角色捍卫立场。该机制适合发现遗漏，但不能把“辩论更激烈”理解为“结论更准确”。每条争论都需要绑定证据 ID，裁决节点只能使用已验证证据。

3. **自动交易语义不适合当前产品**

   项目最终输出交易决定，而 FinPilot 当前定位是不连接证券账户、不自动下单。我们应改为“研究状态 + 条件 + 风险预算 + 用户确认”，而不是自动 BUY/SELL。

4. **数据提供方仍不适配中国官方披露**

   内置主要是 yfinance、Alpha Vantage、FRED、Polymarket 等。其路由和失败处理可以借鉴，数据源本身不能直接成为 A/H 股正式证据。

### 建议重点阅读的文件

| 文件 | 用途 | 处理意见 |
|---|---|---|
| `tradingagents/graph/setup.py` | Agent 图和边 | 重构为 FinPilot 研究图 |
| `tradingagents/agents/utils/agent_states.py` | 跨节点状态 | 增加 Evidence、Gate、UserConstraint |
| `tradingagents/agents/schemas.py` | 结构化决策输出 | 借鉴字段约束，不采用交易指令语义 |
| `tradingagents/dataflows/interface.py` | 多数据源路由与失败类型 | 借鉴显式错误与配置顺序 |
| `tradingagents/dataflows/market_data_validator.py` | 确定性事实快照 | 扩展到财报和估值快照 |
| `tradingagents/agents/managers/portfolio_manager.py` | 最终综合 | 作为需要增加硬门槛的反例 |

## 5. OpenBB：最值得学数据层，但许可证和中国数据覆盖是限制

### 值得借鉴

OpenBB 的关键不是某个数据接口，而是统一的 TET 流程：

```text
标准查询参数
  → Provider 专属查询转换
  → 原始数据提取
  → 标准数据转换
  → 统一结果模型
```

`openbb_core/provider/abstract/fetcher.py` 把这个过程定义为 `transform_query → extract_data → transform_data`；`query_executor.py` 负责按 Provider 和模型名称找到实现并检查凭证。

这套设计非常适合我们同时接入：

- 行情：东方财富公开行情或后续授权行情；
- A 股公告：巨潮资讯、上交所、深交所；
- 港股公告：港交所披露易；
- 公司材料：公司 IR；
- 预测数据：未来可能接入的授权一致预期提供方。

OpenBB 还已经定义了 `EquityHistorical`、`CompanyFilings`、`IncomeStatement`、`ForwardPeEstimates` 等标准模型，说明行情、公告、报表和动态估值本来就应该是不同的数据契约，而不是混在一张字典里。

### 不能直接使用的原因

1. **仓库采用 AGPL-3.0**

   若复制或修改其代码并以网络服务方式提供，可能产生提供相应源码的义务。这里不是法律意见；在进行正式许可证评估前，FinPilot 应只学习接口思想，自己实现轻量 Provider 层。

2. **没有现成中国官方披露 Provider**

   当前 Provider 列表没有 CNINFO、SSE、SZSE 或 HKEX。即使引入 OpenBB，也仍需自己完成中国证券身份、公告检索、文件缓存和报表字段归一化。

3. **体量远大于求职 MVP 所需**

   OpenBB 平台覆盖数千文件和大量资产类别。为两个真实公司样例引入整个平台，会增加安装、许可证、部署和排错成本，不利于形成稳定可复现的作品演示。

### 建议重点阅读的文件

| 文件 | 用途 | 处理意见 |
|---|---|---|
| `openbb_platform/core/openbb_core/provider/abstract/fetcher.py` | TET Provider 抽象 | 学习接口思想，自主实现 |
| `openbb_platform/core/openbb_core/provider/query_executor.py` | Provider 选择与凭证检查 | 简化为本项目 Registry |
| `openbb_platform/core/openbb_core/provider/standard_models/company_filings.py` | 公告标准字段 | 扩充 source、period、location、hash |
| `openbb_platform/core/openbb_core/provider/standard_models/income_statement.py` | 报表标准字段 | 建立中国会计准则/IFRS 映射 |
| `openbb_platform/core/openbb_core/provider/standard_models/forward_pe_estimates.py` | 动态估值数据契约 | 只在授权数据存在时启用 |
| `openbb_platform/providers/sec/openbb_sec/models/company_filings.py` | 官方公告抓取、分页、缓存、转换 | 映射为 CNINFO/HKEX Adapter |

## 6. 与 FinPilot 当前代码的对应关系

| 当前模块 | 已有能力 | 下一步改造 |
|---|---|---|
| `advisor/china_market_data.py` | 中国证券身份、A/H 来源注册、行情快速失败 | 拆出 Provider 接口；加入 CNINFO/HKEX 公告 Provider 和缓存状态 |
| `advisor/stock_research.py` | 动态 PE、预测修正、来源缺失和硬门槛 | 扩充真实报表字段、结论级引用、证据新鲜度和口径冲突 |
| `advisor/agent.py` | 用户风险到资产配置、解释和护栏 | 接入个股风险预算，不让个股建议突破资产配置上限 |
| `app.py` | C 端旅程、配置建议、研究卡展示 | 首屏改为行动卡；研究过程放入工作底稿；增加替换、调仓和复查交互 |

值得保留的是：当前 `stock_research.py` 对动态 PE 的定义和数据不足降级，比 FinRobot 的默认估值假设更谨慎。不要为了显得功能丰富而倒退到“缺数据也生成目标价”。

## 7. 建议的 FinPilot V5 研究架构

```text
用户目标与风险预算
        ↓
证券身份解析
        ↓
官方公告检索与本地缓存
        ↓
PDF/HTML/表格解析
        ↓
财务字段归一化与口径校验
        ↓
代码计算：TTM、现金流质量、增长、基础估值
        ↓
事件映射：收入 / 利润率 / 现金流 / 资本结构 / 风险
        ↓
证据约束的正方与反方论证
        ↓
硬门槛：缺失、陈旧、冲突、审计、流动性、集中度
        ↓
研究状态：继续研究 / 等待价格 / 等待验证 / 数据不足 / 暂不考虑
        ↓
用户动作：加入观察、比较、调整金额、设置复查条件
```

建议新增的轻量模块边界：

```text
advisor/research_models.py       # Filing、Metric、Estimate、Evidence、Gate
advisor/research_providers.py    # Provider 协议与 Registry
advisor/cninfo_provider.py       # A 股公告与财报
advisor/hkex_provider.py         # 港股公告与财报
advisor/filing_store.py          # 下载、哈希、缓存、版本
advisor/financial_normalizer.py  # 中国会计准则/IFRS 字段归一化
advisor/research_workflow.py     # 有限状态流程，不负责页面渲染
advisor/research_gates.py        # 数据和风险硬门槛
```

为了控制求职 MVP 的复杂度，第一版不需要引入 LangGraph 或 OpenBB 依赖。用 dataclass/Pydantic 加普通 Python 状态机即可完整展示输入、输出、失败和证据边界；等真实证据链稳定后，再评估是否需要通用 Agent 框架。

## 8. 第一批真实证据包

建议先完成两家公司：

| 市场 | 公司 | 代码 | 第一批材料 | 目标 |
|---|---|---:|---|---|
| A 股 | 贵州茅台 | 600519 | 最新年报、最新季报、关键经营公告 | 跑通巨潮/上交所披露、白酒经营指标、现金流和 TTM PE |
| 港股 | 腾讯控股 | 00700 | 最新年报、中报/季报、业绩公告 | 跑通披露易/公司 IR、分部收入、非 IFRS 与 IFRS 口径、港币估值 |

每份缓存证据至少保存：

```text
security_id
source
source_url
document_type
published_at
fiscal_period
retrieved_at
local_path
content_hash
page_or_section
reported_currency
accounting_basis
```

演示时默认读取本地缓存，联网仅用于“刷新”。这样即使公开网站临时不可访问，页面也不会卡住，且面试官能够复现证据。

## 9. 实施顺序

1. 建立 Provider 协议、证据模型和本地缓存清单。
2. 获取并缓存贵州茅台、腾讯控股的官方年报和最近一期业绩材料。
3. 手工校验第一版字段映射，再实现确定性归一化与指标计算。
4. 给每个展示指标绑定文档、日期、页码/章节和计算过程。
5. 把正反 Agent 限制为只能引用现有 Evidence ID；缺证据时输出待验证问题。
6. 在最终结论前运行硬门槛；动态预测未接入时明确显示“动态估值数据不足”。
7. 重做结果首屏：先显示用户现在能做什么、金额、主要风险和复查时间，再折叠研究工作底稿。
8. 最后增加产品替换、风险调低、市场下跌模拟、保存观察与复查触发器。

## 10. 开源合规要求

- 参考代码保留在独立目录，不提交进 FinPilot 仓库。
- 记录参考项目、版本、许可证和受影响的设计决策。
- Apache-2.0 代码若发生实际复制或修改，保留版权、许可证和适用的 NOTICE。
- 不使用 FinRobot 名称、Logo 或商标包装派生产品。
- OpenBB 代码在完成 AGPL 合规评估前不复制、不修改后并入应用。
- 数据接口可公开不代表数据可商业使用；行情、新闻和一致预期还需分别核对服务条款和授权范围。
- 面试与 README 中说明哪些是独立实现、哪些是架构参考，不把开源项目能力冒充为自己的实现成果。

## 11. 最终取舍

本轮最应该立即吸收的不是“更多 Agent”，而是三项工程纪律：

1. 每个数字由确定性代码计算并能追溯到证据；
2. 每个 Agent 节点有结构化输入、输出和停止条件；
3. 每个数据源通过统一契约接入，失败时明确降级而不是编造。

在这三项完成前，增加更多角色、新闻情绪或目标价，只会让页面看起来更复杂，不会让用户更信任。
