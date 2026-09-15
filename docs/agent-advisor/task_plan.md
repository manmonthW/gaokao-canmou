# Task Plan：AI 参谋助手（Agentic）+ 阶段 0 前置修复

> 设计依据：[../agent-advisor-plan.md](../agent-advisor-plan.md)（§ 编号均指该文档）
> 配套：[findings.md](findings.md)（发现与决策）、[progress.md](progress.md)（会话日志与测试结果）
> 跟进方式：每完成一个子任务就更新本文件的状态与 progress.md；新会话先读这三份文件再动手。

## Goal
在不改变任何既有匹配结果的前提下修掉 /match 缓存与事件循环阻塞问题，然后按规划分阶段交付
「AI 参谋助手」：邀请制内测、模型可替换（为国内已备案模型留路）、所有结论可溯源。

## Current Phase
Phase 0.1 — /match 缓存重构：**代码完成、本地验证通过，待用户确认后提交并部署 EWS**
下一步：Phase 0.2（其余前置修复）

## 已确认的决策（2026-09-15，用户）
| 决策 | 结论 |
|---|---|
| 使用范围（Gate 0） | **邀请制内测**：Agent 放在功能开关 + 登录白名单后面，公开页面不暴露入口 |
| 模型 | **必须可替换**：业务代码只依赖 LangChain `BaseChatModel`，提供方由配置切换（ericai / 国内已备案模型） |
| 开发顺序 | 先修缓存（阶段 0 前置），再做 Agent |
| 进度跟踪 | planning-with-files：本目录三份文件随开发实时更新 |

## Phases

### Phase 0.1：/match 缓存重构（§1.2 第 1 项）
- [x] 采集重构前基线：41 组调用（match / sensitivity / refresh）输出落盘，两次采集逐字节一致
- [x] 采集重构前性能：冷 2.9s、换位次 3.3s、换筛选 3.65s（均未命中）
- [x] 拆分缓存：单元集合按「数据版本 + 类别/学科类/批次/考生年 + cfg」缓存（上限 16）
- [x] 分档、选科排除、偏好筛选每次请求现算（`_classify_units`）
- [x] CPU 段移入线程池（分组统计、选科查找、分档筛选、汇总、敏感度）；同键冷启动单飞
- [x] 缓存建好后 `gc.collect()+gc.freeze()`（实测去掉热请求上百毫秒的 GC 停顿）
- [x] 删除被覆盖的 major_strengths 死查询
- [x] 回归：与「旧代码每次清空缓存」输出比对 39/41 逐字节一致，另 2 组为修复的旧 bug（见 findings）；
      pytest 58 passed（新增 `tests/test_match_cache.py` 6 个）；`etl/smoke_strength.py` golden 契约 ALL PASS
- [x] 记录重构后性能与缓存内存占用（见 progress.md）
- [ ] 用户确认后提交；按 `EWS_DEPLOY_LESSONS.md` 部署 EWS（仅重建 backend，无迁移）并在 EWS 复测
- **Status:** 代码完成，待提交/部署

### Phase 0.1 衍生待办（需用户拍板）
- [ ] 艺术类/体育类在智能匹配页的呈现：修复后艺术类返回「数据不足」列表（旧代码因 bug 恒为 0 条）。
      产品原则是「首版仅历史查询 + 限制提示」——是否改为直接显示限制提示、不出列表？

### Phase 0.2：其余前置修复（§1.2）
- [ ] 限流（nginx limit_req + 应用层）
- [ ] compose 安全（只读角色、JWT_SECRET、CORS、删 `COPY data`、`.dockerignore`）
- [ ] 后端容器非 root（UID 10001）+ 用户数据卷 chown 方案
- [ ] 方案体检规则迁到后端（`/plan/analyze`），前端改用
- **Status:** pending

### Phase 0.3：模型接入技术验证（§5、§16 阶段 0）
- [ ] 模型工厂：provider 可配置（ericai / openai 兼容的国内模型），业务只拿 BaseChatModel
- [ ] 在 EWS backend 容器内验证：普通对话、json_mode 结构化输出、tools + reasoning none、多工具调用、并发 10 请求延迟、429
- [ ] AzureChatOpenAI vs ChatOpenAI+httpx.Auth 二选一（核实 URL 拼接与请求体字段）
- [ ] sol / luna / terra 选型
- **Status:** pending

### Phase 1：MVP——选校问答 + 单条解读（§16 阶段 1）
- **Status:** pending

### Phase 2：方案体检 Agent（§16 阶段 2）
- **Status:** pending

### Phase 3：政策问答（§16 阶段 3）
- **Status:** pending

### Phase 4：灰度、压测与高峰保障（2027-01 至 07）
- **Status:** pending

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
