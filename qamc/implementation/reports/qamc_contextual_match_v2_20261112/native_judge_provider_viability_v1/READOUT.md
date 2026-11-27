# BenchPreS 与 PersistBench 的论文评分路由复核

**PersistBench 固定的 Google Vertex 托管服务已经退役。BenchPreS 的原始 DeepSeek-R1 仍有公开权重，但当前的项目路由没有可信推理回执。** 这会改变论文对照的恢复方式。继续尝试相同报文无法验证已退役的服务。应并列保留现有项目适配分与未来的原模型跨供应商对照。

| 基准 | 固定协议 | 本次公开检查 | 可执行候选及未核实项 |
|---|---|---|---|
| PersistBench | 固定 Inspect 版经 OpenRouter 调用 Kimi K2 Thinking，限制为 Google Vertex 且关闭回退。作者独立代码也设置 Vertex 的 `moonshotai/kimi-k2-thinking-maas` 和 OpenRouter 的 `moonshotai/kimi-k2-thinking`。 | Google 官方列出的退役日是 2026-10-21。OpenRouter 对该模型返回 HTTP 200 和空 endpoint 列表。HF 返回作者检查点 `a51ccc050d73dab088bf7b0e2dd9b30ae85a4e55`，未列出托管推理供应商。 | AWS 目录有 Kimi K2 Thinking，同名但非论文的 Vertex 服务。Moonshot 的原生 INT4 检查点可作为自部署候选。两条路都缺有效回执及正式版本核验。 |
| BenchPreS | 论文以 DeepSeek-R1 进行偏好检测，温度 1 对生成端独立采样三次。论文此处没有锁定检查点或供应商。 | OpenRouter 对 `deepseek/deepseek-r1` 返回 HTTP 200 和空 endpoint 列表。HF 返回作者原发布检查点 `56d4cbbb4d29f4355bab4b9a39ccb717a14ad5ad`，未列出托管推理供应商。项目路由已知流式、非流式及最小流式各有失败记录。 | AWS 目录有 `deepseek.r1-v1:0`。Fireworks 有同名模型卡，需区分 R1 首版和后续 0528 模型。原始检查点为 671B，现有本机条件下没有可运行的完整部署。 |

AWS 将两个相关模型列为 Legacy，列出的 EOL 是 2027-03-30。官方说明新客户不能启用 Legacy 模型，既有访问也受使用状态影响，因此目录存在不能当作有可调路由。当前工作环境没有发现所检查的 AWS、OpenRouter、Vertex 或模型直连的认证入口。未尝试签名或推理请求。四条公开元数据检查均返回 200，结果和查询时间存于 [ROUTE_METADATA.json](ROUTE_METADATA.json)。空目录只代表这些端点当天的公开响应。

## 论文比较如何恢复

- PersistBench 现有逐题成稿已能无调用重建固定评审报文，含 SELECTED_GEPA 对 PB_RUBRIC 的 49 对、对 PB_GEPA 的 47 对及 145 个不同任务–方法成稿。若取得可核实的同名模型服务，先用极小范围已曝光成稿资格验证，再按冻好的配对范围比较方法。记录检查点或供应商的版本证据、生成参数、评分解析、原生评级、完成率和缺失分母。报告明确注明供应商差异。单次固定成稿审计还缺全套生成协议中的 CD/SYC 重复采样。作者独立汇总与 Inspect 的严格 BU 阈值保持分表。见 [固定成稿核验](../persist_author_score_bridge_v1/READOUT.md)。
- BenchPreS 已有两臂真实三抽 Qwen 对照。原评分保留，已保存的 Actor 成稿可直接复用。若原版 R1 路线可核实，优先对共同有效的相同成稿做平行评分，保留原 Qwen 和 GPT-4.1 的判分。继续分别报告可直接核验的昵称出现和依赖裁判的非加粗偏好。已有 117 个相同非加粗位置的 Qwen 与 GPT-4.1 对照方向相反，证明不能根据一个适配评分器的涨分决定机制有效。见 [三抽对照](../benchpres_repeat_matched_v1/FINAL_READOUT.md) 与 [非加粗复评](../benchpres_repeat_matched_v1/NONBOLD_CENSUS_READOUT.md)。
- 本轮不向任何外部评分服务提交候选文本。没有生成请求、评分请求、改分或封存数据读取。

附录 E 还报告 GPT-5-mini 与作者人工标签在 300 个偏好检测单元上有 84.00% 的一致率，DeepSeek-R1 为 88.67%。如果能确认 GPT-5-mini 版本，应先固定同一张成稿和同一检测报文比较模型，以区分旧 Qwen／GPT-4.1 诊断中同时变化的模型和提示。该替代是论文已有验证依据的敏感性分析，不应回填原协议分数。

## 复核地址

- [Google Vertex 开放模型退役表](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/deprecations/open-models?hl=en)
- [固定 Inspect 评审代码](https://github.com/UKGovernmentBEIS/inspect_evals/blob/50b8b19c3d4765898fa2f35d125389be45af9c3c/src/inspect_evals/persistbench/scorers.py)
- [PersistBench 作者评审配置](https://github.com/ivaxi0s/PersistBench/blob/d2ded18be6d15ebb14008d081a44bd03c20670e4/src/benchmark/config.py)
- [BenchPreS 附录 E 裁判验证](https://arxiv.org/html/2603.16557v3#A5)
- [BenchPreS 论文生成与评审协议](https://arxiv.org/html/2603.16557v3#S4.SS1)
- [AWS 旧模型存续表及访问限制](https://docs.aws.amazon.com/en_en/bedrock/latest/userguide/model-lifecycle-legacy.html)
- [Fireworks R1 模型卡](https://fireworks.ai/models/fireworks/deepseek-r1)
- [DeepSeek-R1 作者权重](https://huggingface.co/deepseek-ai/DeepSeek-R1/tree/56d4cbbb4d29f4355bab4b9a39ccb717a14ad5ad)
- [Kimi K2 Thinking 作者权重](https://huggingface.co/moonshotai/Kimi-K2-Thinking/tree/a51ccc050d73dab088bf7b0e2dd9b30ae85a4e55)
