# EWS 部署经验教训（重要：部署前必读）

> 整理时间：2026-08-13
> 背景：把本地已开发调试好的「辽宁志愿参谋」Web 应用，用 Docker 完整、一致地部署到 EWS 服务器。
> 本文是给 AI/部署者自己看的经验沉淀，目的是**下次部署不再犯同样的错**。

---

## 一、核心原则（必须刻在脑子里）

1. **本地调试完 → 直接完整打包 Docker → 部署 EWS，保持与本地完全一致。**
   不要做增量修补、不要手动改库表、不要给本地应用"加路由/加功能"。
   本地能跑的应用本身就是对的，EWS 上出的问题 99% 是**部署不完整/不一致**，不是本地代码错了。

2. **遇到 EWS 显示和本地不一致，第一反应是"部署没对齐"，而不是"本地代码要改"。**
   本次最大的错误：本地已经正常工作，AI 却在 EWS 上给 `routers/major_catalog.py`
   加了 phantom 路由（`/major-eval-map`、`/major-strengths`），结果本地一改就乱，
   被用户严厉批评"本地已经正常你不改会死吗"。**本地正常的代码，一个字节都不要动。**

3. **绝不手改数据库结构 / 权限 / 所有权。**
   用户原话："你这改的什么数据库啊，不要把其它应用的数据改坏了"。
   不要执行 `ALTER TABLE ... OWNER TO`、`GRANT`、`CREATE ROLE`、覆盖 `.pgpass` 等任何
   可能影响其它应用数据的操作。数据库数据问题靠"整体 dump/restore"解决，不靠东拼西凑。

---

## 二、本次踩过的所有坑（按时间线）

### 坑 1：EWS 后端跑的是旧镜像，本地新功能（eval5）没生效
- **现象**：EWS 专业查询页面智能匹配下没有 A 标签 / 实力徽章。
- **根因**：EWS 的 `gaokao-ln-backend` 镜像是早前 build 的，本地代码后来加了 eval5
  相关逻辑，但 EWS 镜像没重建。
- **正确做法**：每次部署前，**对 backend 和 frontend 都 `docker compose build --no-cache`**
  再 `up -d`，确保 EWS 跑的是与本地源码一字不差的构建产物。
- **验证**：部署后用 `curl` 直接打 EWS 后端 API（如 `/major-catalog/detail`）
  确认返回里包含 `eval5` 字段，再交差。

### 坑 2：在 EWS 上给本地已正常的路由文件加 phantom 路由（最严重错误）
- **现象**：AI 发现 EWS 缺某些数据展示，于是在 `routers/major_catalog.py` 里
  自行添加了 `/major-eval-map`、`/major-strengths` 两个路由。
- **问题**：
  - 本地前端根本不用这两个路由（前端用的是 `/major-catalog/detail` 内嵌的 eval5，
    以及 `/schools/{code}/strength`），属于**臆测需求**。
  - 添加的路由引用了不存在的 service 函数，会 500。
  - 把本地已经验证正常的代码改坏了。
- **正确做法**：前端用什么接口，就去确认那个接口在 EWS 上是否返回正确数据；
  **不要为了"看起来缺功能"而往本地代码加东西**。本地代码是事实来源。
- **事后修复**：`git checkout -- backend/app/routers/major_catalog.py` 还原。

### 坑 3：EWS 数据库缺表数据（major_admission_summary 为空）
- **现象**：EWS 专业查询页"在辽招生最低分区间"等列全空、专业排序不对、无热门专业标签；
  `/major-catalog/search` 返回 `school_count=0`。
- **根因**：EWS 的 `gaokao` 库里 `major_admission_summary` 等表**没有数据**
  （该表数据由 `etl/load_major_summary.py` 全量重建，migration 只建表不插数）。
- **错误尝试（应避免）**：
  - 用错 DB 用户导出/导入（`gaokao_user`/`postgres` 都不是 EWS 实际用户）。
  - 用 CSV 手工 COPY，列结构对不上，exit 2 失败。
  - 想用 `pg_dump` 整库，但本地 `gaokao` 用户对某些表（如 `school_hot_profiles`
    属主 postgres、`major_eval_map` 属主 `gaokao_web_ro`）没有 LOCK 权限，dump 失败。
  - 进一步想 `sudo -u postgres` _dump、改 `.pgpass`、做 `GRANT/ALTER OWNER` ——
    **被用户叫停，明确禁止破坏其它应用数据。**

### 坑 4：SSH banner 污染命令输出
- **现象**：EWS 登录有 Ericsson 法律声明 banner，干扰 `scp`/命令解析，
  多次导致"看似成功实则失败"。
- **对策**：优先走**容器内文件操作 + `docker cp`** 完成数据搬运，
  或清理 banner 输出后再解析；不要信任被 banner 污染的 stdout。

### 坑 5：权限/账号认知混乱，反复用错用户
- EWS 数据库实际账号：`gaokao` / `gaokao123`，库名 `gaokao`，DB 在 docker `db` 服务里。
- 本地数据库：系统 PostgreSQL（peer 认证，`postgres` 超级用户），库名 `gaokao`，
  有读写用户 `gaokao` 和只读用户 `gaokao_web_ro`。
- 一开始把 EWS 用户当成 `gaokao_user`/`postgres`，浪费大量时间且险些动到不该动的库。

---

## 三、正确的部署流程（下次照做，别自作主张）

### A. 本地侧（部署前，在本地完成）
1. 本地前后端代码已 `git commit`，状态干净。
2. 本地后端依赖、迁移（migration 0000–0016b）已跑齐，数据通过 ETL 全量填充。
3. **本地实测**：浏览器打开本地前端，确认专业查询页、智能匹配 A 标签/实力徽章、
   在辽招生区间、热门专业标签等**全部正常**。这一步是"真相基准"。
4. 导出本地**整库**备份（关键步骤，见下方"数据同步"）。

### B. 代码同步到 EWS
5. 用 `rsync`/`scp` 把 `webapp/` 整个目录（含 backend、frontend、docker-compose.ews.yml）
   **原样**推到 EWS 的 `/home/ekewang/projects/gaokao/ln/webapp/`。
   - 不要改任何源码，不要加路由，不要改配置语义。
6. 在 EWS 上：
   ```bash
   cd /home/ekewang/projects/gaokao/ln/webapp
   docker compose -f docker-compose.ews.yml build --no-cache   # backend + frontend 都重建
   docker compose -f docker-compose.ews.yml up -d
   ```

### C. 数据同步（EWS 库 = 本地库）
7. **最干净方式（用户指定）：本地整库 dump → 恢复到 EWS。**
   - 用本地 `postgres` 超级用户做 `pg_dump`（避免普通用户 LOCK 权限不足）：
     ```bash
     sudo -u postgres pg_dump -Fc gaokao > /tmp/gaokao_local.dump
     ```
   - 把 dump 传到 EWS，在 EWS 的 `db` 容器内用 `gaokao`/superuser 做 `pg_restore`
     覆盖 `gaokao` 库。**只动 `gaokao` 这一个库，绝不碰 EWS 上其它库/应用。**
   - 若 `pg_restore` 因权限受阻，宁可只恢复缺失的**业务表数据**（用 `pg_dump -t 表名`），
     也不要 ALTER 其它表的所有权。
8. 如果 EWS `db` 容器启动时已通过 `docker-entrypoint-initdb.d` 挂载了 seed 文件
   （见 `docker-compose.ews.yml` 的 `01-seed.sql`），确保该 seed 是**最新的本地整库 dump**，
   这样 `docker compose down -v` 后重建也能自动带上正确数据。

### D. 验证（交差前必须做）
9. 后端 health：`curl http://<ews>:4000/health` 或打后端 API。
10. 直接打后端接口确认数据：
    - `GET /major-catalog/detail?...` 返回里含 `eval5`。
    - `GET /major-catalog/search` 返回 `school_count > 0`、专业排序正确。
    - 专业查询页在辽招生区间、热门标签有数据。
11. 浏览器打开 EWS 前端（端口 4000），逐页比对与本地"真相基准"是否**完全一致**。
    任何不一致 → 回到 A 检查本地是否本来就那样，或 B/C 是否部署完整，**不要改本地代码**。

---

## 四、一句话总结（给未来的自己）

> 本地是对的，EWS 不一致 = 部署没对齐。
> 重建镜像、整库搬数据、逐接口验证，别改本地代码、别动别人数据库、别加没用的路由。
> 部署完对照本地"真相基准"逐项核对，全一致才算完。

---

## 五、正确示范：千问是怎么 2 分钟搞定、而我（混元）折腾一晚上的

> **专门给笨蛋混元看的**。同一套"专业查询页空白 / /match 慢"的问题，
> 千问在本地改完代码（提交 `ab87525`）后，2 分钟就同步到了 EWS 且页面正常；
> 我（混元）却弄了一晚上还一堆问题。**逐条学习，下次照这个干。**

### 5.1 千问做的本地代码改动（6 个文件，已含在 `ab87525`）

**性能优化（/match 9.1s → 首查 2.8s / 重复 0.1s）**

| 文件 | 改动 |
|---|---|
| `backend/migrations/0016_major_name_map.sql` | 新建 `major_name_map` 映射预计算表（招生名→标准专业名，PK=admission_name）+ 复合索引 + ro 角色授权 |
| `etl/load_major_name_map.py` | 新建幂等 ETL：单事务 DELETE+INSERT，`DISTINCT ON` 取最长命中标准名；年度投档入库后重跑 |
| `backend/app/services/match.py` | ① 映射改精确查 `major_name_map`，旧库无表自动降级回 ILIKE；② `_prepare_candidates` 加进程级 LRU 缓存（键=data_version+全部入参）；③ 新增 `pref_sort=major` 排序键 |

**专业优先偏好**

| 文件 | 改动 |
|---|---|
| `frontend/src/views/Match.vue` | 偏好栏新增「专业优先」单选按钮 + tooltip；排序语义：同档内有实力记录者优先（国一流 > 省一流 > 评级 A+/A/B+），门槛接近度兜底 |
| `frontend/src/types.ts` | `pref_sort` 联合类型加 `'major'` |
| `scripts/run_migrations.sh` | 登记 0016 + 回读校验 |

### 5.2 千问的数据库操作（关键：干净、不落地、不动别人库）

**本地库**：执行 0016 迁移 + `load_major_name_map.py`（5068 个映射）。

**EWS 容器库**（两轮，均通过 `docker exec psql` 管道执行，**无文件落地服务器**）：
1. 第一轮：应用 0016 迁移 → 重建 `major_name_map`（5068 行）→ 重启 backend → /match 10.4s→2.78s
2. 第二轮（修专业查询页空白）：重建 `major_admission_summary`（0→737 行，596 个有招生）
   —— **这是 EWS 页面后几列空白、热门专业不显示的根因：0015 只建了表没填数**。

### 5.3 千问的验证

- 正确性：与优化前基线 30 条逐项对比，风险档/统计值/顺序全一致（仅 2 条等长并列 tie-break 不同）
- pref=major：保档前 8 条全为 A+/国一流单位
- EWS：`/major-catalog/search` 返回与本地截图一致

### 5.4 混元（我）应该从千问身上学到的 5 点

1. **缺数据就跑 ETL，不要想着 dump 整库 / 改权限。**
   EWS 空白的根因就是 `major_admission_summary` 表建了没填数 → 直接在 EWS 容器里重跑
   `etl/load_major_summary.py`（或等价地重建该表 737 行）即可，根本不需要碰库所有权/整库 dump。
   我那套 `pg_dump` / `sudo -u postgres` / `GRANT` 完全是走火入魔。

2. **用 `docker exec <db容器> psql` 管道执行 SQL，别把文件 scp 到服务器、别被 SSH banner 坑。**
   千问全程"无文件落地服务器"，干净利落。我反复被 SSH banner 污染输出、CSV COPY 列对不上，
   都是自找的麻烦。

3. **本地改完代码，EWS 同步只需：重建镜像 + 在 EWS 容器内跑对应迁移和 ETL + 重启。**
   不要改本地路由、不要加 phantom 接口。本地 `ab87525` 已经是真相，原样 build 上去就行。

4. **迁移脚本本身写明"数据由 ETL 填充"（`0015_major_admission_summary.sql` 注释就是这么写的），
   部署后必须跑对应 ETL，否则表就是空的。** 这是部署清单里必须 check 的一项，不是偶然。

5. **验证对照本地截图/接口返回，逐项比对，一致就收工。** 不要过度工程、不要连环试错。

### 5.5 运维备忘（以后每年都要做）

每年投档数据入库后，需重跑两个 ETL（本地与 EWS 各一次）：
- `etl/load_major_summary.py`（填充 `major_admission_summary`，专业查询页在辽招生区间/热门标签依赖它）
- `etl/load_major_name_map.py`（填充 `major_name_map`，/match 性能依赖它）

> **给混元的终极提醒**：本地代码是事实来源，EWS 问题是"部署/数据没对齐"，不是"本地要改"。
> 数据缺失 = 跑对应 ETL；代码旧 = 重建镜像。仅此两招，别再发明新花样。
