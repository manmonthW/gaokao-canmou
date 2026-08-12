# 院校学科实力 / 专业强度数据接入报告（一期，migration 0014）

日期：2026-08-12　任务 #12（一期收尾：文档与清理）

本次为「院校学科实力与专业强度」模块一期：五个数据源入库、院校级实力标签
聚合、后端三接口附加式输出、前端 StrengthBadges 三挂载点。全部改动对既有
契约「只增不改」——所有新增键位于响应对象末尾，既有键集合与顺序不变。

## 输入审计（五数据源，来源与实际获取方式）

| 数据源 | 文件 | 来源与实际获取方式 | 口径 | 行数 |
|---|---|---|---|---|
| eval4 | `etl/data/eval4_official.csv` | 第四轮学科评估结果（2017 公布）：acabridge 官方授权数据整理，**与教育部学位中心公布结果一致** | 官方 | 5212 |
| dfc2022 | `etl/data/dfc2022.csv` | 第二轮「双一流」建设高校及建设学科名单（2022 公布），教育部/财政部/国家发展改革委 **教研函〔2022〕1号** | 官方 | 435 |
| swyc | `etl/data/swyc_batches.csv` | 「双万计划」国家级/省级一流本科专业建设点（2019–2021 三批）：**eol 静态 API 汇总**；官方名单为分送制、无统一完整公开库，本表**覆盖率约 97%**；批次公布年仅广东 2021 可考 | 官方 | 11738（国 11445 / 省 293） |
| ruanke2026 | `etl/data/ruanke2026.csv` | 软科 2026 中国大学专业排名评级，**软科内部 API** 抓取 | **第三方·仅供参考** | 30301 |
| eval5a | `etl/data/eval5_a_transcript.csv` | 第五轮学科评估 A 类汇总（网络流传版）：**18 张微信截图双轨转录** | **非官方·流传版** | 881 行 |

### eval5a 第五轮门禁流程（入库前强制）

- 教育部未向社会公布第五轮学科评估结果（2022-12 仅发抵各高校），流传版
  截图来源不明、可能含缺漏与档位误读 → 只能作辅助参考，禁止以官方名义呈现；
- **三重校验**（`etl/verify_eval5.py` 自动生成报告，纯只读可重跑，
  见 `docs/eval5a-verification-report.md`）：
  ① 对照第四轮官方全量（四轮 A 类 747 对，转录存续率 77.11%）；
  ② 双轨转录比对（`eval5a_track_diff.md`，分歧行进审核队列）；
  ③ 院校自披露/公开信源抽查核对；
- **用户签字确认**：审核队列（`eval5a_review_queue.csv`）逐项人工裁决，
  签字栏 S1–S8 全部确认；
- 裁决结果（`etl/data/eval5a_adjudication.csv`，879 行裁决）：
  **verified 845 / disputed 34**；加载器默认只加载 verified 行
  （disputed 34 行不入库、留档备查）。

## 加载结果（psql 实查核对，2026-08-12）

| 表 | 行数 | 构成 |
|---|---|---|
| school_disciplines | **6492** | eval4_official 5212 + dfc2022 435 + eval5_a 845（全部 verified） |
| major_strengths | **42039** | ruanke 30301 + swyc_national 11445 + swyc_provincial 293 |
| school_profiles.strength_tags 非空 | **732 所** | 由 build_strength_tags.py 全量聚合重算 |

标签分布（按校计数，实查）：

| 标签 | 校数 | 标签 | 校数 |
|---|---|---|---|
| 四轮A+ | 71 | 五轮A+ | 68 |
| 四轮A | 55 | 五轮A | 86 |
| 四轮A- | 101 | 五轮A- | 110 |
| 双一流学科 | 138 | 多源印证 | 189 |
| 国一流专业 | 714 | 省一流专业 | 40 |

- 「软科评级」标签**刻意不挂到校级**：第三方评级覆盖 3 万+ 专业条目、
  几乎校校有份，挂到校上无区分度且有误导风险；词表保留该 tag 供未来
  专业级展示（见 build_strength_tags.py 文件头规则说明）。
- source_files 登记 5 行（id 7844–7847、7853），note 含真实来源与免责说明，
  src_file_id 已回填明细行。
- **swyc data_year=0 哨兵语义**：双万计划批次公布年约 96% 不可考
  （官方分送制无统一公布），空值一律记 **0 =「批次公布年未知」**，
  不虚构 2019/2020/2021；0 不参与唯一键去重歧义。实查：swyc_national
  data_year=0 共 11326 行，2021 共 119 行；swyc_provincial 2021 共 293 行。

## 代码适配（附加式，契约只增不改）

- **迁移 0014** `webapp/backend/migrations/0014_major_strength.sql`：
  新表 school_disciplines / major_strengths / strength_dictionary（词表 11 条，
  模式同 0011 flag_dictionary）+ school_profiles.strength_tags TEXT[] + GIN
  索引 + 只读角色授权；不回填 major_profiles 预留列（粒度不匹配且
  load_major_profiles.py 全量重写该表）。
- `etl/load_major_strength.py`：五源灌库，院校名匹配复用
  load_baoyan_rate.py 惯例（精确→最长前缀→人工别名）；未匹配行不静默丢弃——
  以 school_code=NULL 入库并追加 `etl/enrich_review.jsonl` 待人工补解析；
  upsert 一律 COALESCE 只补空不覆盖，幂等；--eval5a 默认仅加载 verified。
- `etl/build_strength_tags.py`：校级 strength_tags 全量幂等重算
  （模式克隆 load_major_flags.py：先算全量→批量 UPDATE→未命中清零）；
  标签值域受 strength_dictionary 守卫，词表外标签拒绝写库。
- 后端附加式改造（既有键序不变，新键一律在对象末尾）：
  - `services/match.py`：候选单元附加 `strength_tags`（校）与
    `major_strength`（专业级明细，按 school_code+专业名内存合并）；
  - `services/schools.py` + `routers/schools.py`：新增
    `GET /api/v1/schools/{code}/strength`（学科+专业明细，eval5_a 仅
    verified，LIMIT 500 防膨胀）；`/schools/{code}` 附加 strength 块；
  - `services/meta.py` + `schemas.py`：`/meta` 末尾附加 `strength_dictionary`
    （展示文案与第三方免责口径的唯一权威来源）。
- 前端 `StrengthBadges.vue` + 三挂载点：Match.vue 结果表、SchoolDetail.vue
  院校详情、SchoolDrawer.vue 抽屉；样式按 kind 区分——官方常规色、
  eval5（非官方汇总）虚线边框+「非官方」角标、third_party 灰色系+「第三方」角标。
- **Bug 修复记录**：build_strength_tags.py L213 清零语句元组解包方向错误
  （updates 元素为 (tags, code)，曾误按 (code, tags) 解包致清零范围全错），
  已修正为 `for _, code in updates`；dry-run 复算分布一致后写库。

## 测试结果

- pytest：47 passed（既有全量，无回归）；
- smoke 全过：`smoke_backend.sh`、`smoke_match.sh`、`smoke_p1p6.sh`、
  `smoke_a1a4.sh` + 本模块 `etl/smoke_strength.py`（meta 词表 11 条、
  strength 端点结构与 verified 过滤、match 附加键、未知院校 404、
  golden JSON 键序断言、性能粗测）；
- **golden JSON 契约**：meta / schools/{code} / match 既有键集合与顺序不变，
  新键（meta.strength_dictionary；schools.strength；match 的
  strength_tags/major_strength）均位于对象末尾；
- 浏览器 E2E：StrengthBadges 三挂载点（匹配页/详情页/抽屉）渲染、
  角标与 tooltip 免责文案均通过（截图已留档后清理）；
- 幂等复跑：load_major_strength.py 与 build_strength_tags.py 重复执行
  行数与标签分布完全一致；
- 不变量：**admission_scores=66959** 行未动（实查一致）；
- 性能：/match 全量查询 warm 响应约 5s，属既有基线（任务 #11 同口径
  改动前后对照无劣化；冒烟脚本仅拦截 >8s 显著劣化）。

## 注意事项

1. **eval5_a 必须带「非官方·流传版」标**：前端 StrengthBadges 已内置
   （虚线边框 +「非官方」角标 + tooltip 口径），任何新展示点不得绕过；
   若官方正式公布第五轮结果，须以官方数据替换并改 source 语义。
2. **软科为第三方数据**：词表 third_party=true，前端灰色弱化 +「第三方」
   角标，禁止以官方口径引用。
3. **disputed 34 行留档**：`etl/data/eval5a_adjudication.csv`，不入库、
   不删除，后续如获官方/院校佐证可复核转 verified 再按既有流程加载。
4. **school_code=NULL 待人工补别名**：school_disciplines 300 行、
   major_strengths 2847 行（实查）校名未命中 schools 库，已记
   `etl/enrich_review.jsonl`，补别名后重跑加载器即可回填（COALESCE 幂等）。
5. **下一个迁移编号：0015**。schema 变更纪律沿用
   `docs/changelog-2026-08-08-d2-d5.md` §六。

## 结论

五数据源 48531 条实力记录入库（school_disciplines 6492 + major_strengths
42039），732 所院校挂实力标签；后端三接口附加式输出、前端三挂载点上线；
既有契约、数据不变量与性能基线均无破坏。一期完成，待评审通过后提交。
