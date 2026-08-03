<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api/client'
import { useProfile } from '@/composables/useProfile'
import { usePlanner } from '@/composables/usePlanner'
import type { CandidateSnapshot, RiskLabel, VolunteerPlan } from '@/types'
import DataStatusBanner from '@/components/DataStatusBanner.vue'
import StepGuide from '@/components/StepGuide.vue'

const { profile } = useProfile()
const planner = usePlanner()
const { favorites, compareIds, plans } = planner

const activeTab = ref<'fav' | 'compare' | 'plans'>('plans')

const RISK_TYPE: Record<RiskLabel, string> = {
  保: 'success', 稳: 'primary', 冲: 'warning', 高波动: 'danger', 数据不足: 'info',
}

function fmt(n: number | null | undefined) {
  return n == null ? '—' : n.toLocaleString()
}
function diffText(d: number | null) {
  if (d == null) return '—'
  if (d < 0) return `领先 ${Math.abs(d).toLocaleString()}`
  if (d > 0) return `落后 ${d.toLocaleString()}`
  return '持平'
}

// ---------- 收藏 ----------
const favRiskFilter = ref<RiskLabel | ''>('')
const favFiltered = computed(() =>
  favRiskFilter.value ? favorites.value.filter((f) => f.risk === favRiskFilter.value) : favorites.value,
)

// ---------- 对比 ----------
const compareList = computed(() => planner.compareItems())
const COMPARE_ROWS: { label: string; get: (c: CandidateSnapshot) => string }[] = [
  { label: '风险档', get: (c) => c.risk },
  { label: '批次', get: (c) => c.batch },
  { label: '省份/城市', get: (c) => `${c.province || '—'}${c.city ? '·' + c.city : ''}` },
  { label: '层次/性质/类型', get: (c) => [c.level, c.nature, c.type].filter(Boolean).join(' / ') || '—' },
  { label: '近年最低位次（2026）', get: (c) => fmt(c.last_year_rank) },
  { label: '近一年最低分', get: (c) => (c.last_year_score != null ? String(c.last_year_score) : '—') },
  { label: '最好 / 最差 / 中位', get: (c) => `${fmt(c.best_rank)} / ${fmt(c.worst_rank)} / ${fmt(c.median_rank)}` },
  { label: '位次跨度（波动）', get: (c) => `${fmt(c.span)}${c.relative_vol != null ? `（${Math.round(c.relative_vol * 100)}%）` : ''}` },
  { label: '覆盖年份', get: (c) => `${c.n_years} 年` },
  { label: '本人位次差', get: (c) => diffText(c.rank_diff_last) },
  { label: '判定依据', get: (c) => c.risk_reason },
  { label: '数据版本', get: (c) => c.data_version || '—' },
]

// ---------- 方案 ----------
const activePlanId = ref<string>(plans.value[0]?.id || '')
const activePlan = computed<VolunteerPlan | null>(
  () => plans.value.find((p) => p.id === activePlanId.value) || null,
)
const analysis = computed(() => (activePlan.value ? planner.analyzePlan(activePlan.value) : null))

const newPlanName = ref('')
function createPlan() {
  const p = planner.createPlan(newPlanName.value.trim(), profile.value, favorites.value[0]?.data_version ?? null)
  activePlanId.value = p.id
  newPlanName.value = ''
}
async function deletePlan(p: VolunteerPlan) {
  try {
    await ElMessageBox.confirm(`确定删除方案「${p.name}」？（不可恢复）`, '删除方案', { type: 'warning' })
  } catch {
    return
  }
  planner.removePlan(p.id)
  if (activePlanId.value === p.id) activePlanId.value = plans.value[0]?.id || ''
}
function onToggleCompare(snap: CandidateSnapshot) {
  const err = planner.toggleCompare(snap)
  if (err) ElMessage.warning(err)
}
function addFavToPlan(snapId: string) {
  if (!activePlan.value) {
    ElMessage.warning('请先创建/选择一个方案')
    activeTab.value = 'plans'
    return
  }
  const snap = favorites.value.find((f) => f.id === snapId)
  if (!snap) return
  const err = planner.addToPlan(activePlan.value.id, snap)
  err ? ElMessage.warning(err) : ElMessage.success(`已加入「${activePlan.value.name}」`)
}

// ---------- 导出 ----------
const exporting = ref(false)
async function exportPlan(p: VolunteerPlan) {
  if (!p.entries.length) {
    ElMessage.warning('方案为空，无可导出内容')
    return
  }
  exporting.value = true
  try {
    const blob = await api.exportPlan({
      plan_name: p.name,
      note: p.note,
      data_version: p.data_version,
      created_at: p.created_at,
      examinee: {
        year: p.examinee.year, category: p.examinee.category,
        subject: p.examinee.subject, batch: p.examinee.batch,
        score: p.examinee.score, rank: p.examinee.rank,
      },
      items: p.entries.map((e) => ({
        risk: e.risk,
        school_code: e.school_code, school_name: e.school_name,
        major_code: e.major_code, major_name: e.major_name,
        last_year: e.last_year, last_year_score: e.last_year_score,
        last_year_rank: e.last_year_rank, rank_diff_last: e.rank_diff_last,
        level: e.level, city: e.city, note: e.note,
      })),
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${p.name}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出 xlsx（列对齐辽宁「专业+学校」平行志愿）')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="page">
    <DataStatusBanner />

    <StepGuide current="workbench" />

    <!-- 方案体检：置顶显眼位置（change 7） -->
    <el-card v-if="activePlan && activePlan.entries.length && analysis" class="checkup" shadow="never"
             :class="analysis.ok ? 'checkup--ok' : 'checkup--warn'">
      <div class="checkup__head">
        <div>
          <span class="checkup__title">方案体检 · {{ activePlan.name }}</span>
          <span class="checkup__total">共 {{ analysis.total }} 个志愿</span>
        </div>
        <el-button v-if="analysis.ok" type="primary" :loading="exporting" @click="exportPlan(activePlan)">
          方案健康 · 导出志愿表 →
        </el-button>
        <span v-else class="checkup__badge">{{ analysis.issues }} 项待优化</span>
      </div>

      <!-- 冲稳保配比条 -->
      <div class="ratio">
        <template v-for="r in (['冲','稳','保','高波动','数据不足'] as RiskLabel[])" :key="r">
          <div
            v-if="analysis.counts[r]"
            class="ratio__seg"
            :class="'ratio__seg--' + RISK_TYPE[r]"
            :style="{ flexGrow: analysis.counts[r] }"
            :title="`${r} ${analysis.counts[r]}`"
          >{{ r }}{{ analysis.counts[r] }}</div>
        </template>
      </div>

      <ul class="checkup__list" :class="{ 'checkup__list--ok': analysis.ok }">
        <li v-for="(w, i) in analysis.warnings" :key="i">{{ w }}</li>
      </ul>
    </el-card>

    <el-tabs v-model="activeTab">
      <!-- ============ 收藏 ============ -->
      <el-tab-pane :label="`收藏（${favorites.length}）`" name="fav">
        <el-card class="card" shadow="never">
          <div class="toolbar">
            <el-radio-group v-model="favRiskFilter" size="small">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button v-for="r in (['保','稳','冲','高波动','数据不足'] as RiskLabel[])" :key="r" :label="r">{{ r }}</el-radio-button>
            </el-radio-group>
            <span class="muted" v-if="activePlan">加入目标方案：{{ activePlan.name }}</span>
          </div>
          <el-empty v-if="!favFiltered.length" description="暂无收藏。到「智能匹配」结果里点 ☆ 收藏候选。" />
          <el-table v-else :data="favFiltered" size="small" border>
            <el-table-column label="档位" width="90" align="center">
              <template #default="{ row }"><el-tag :type="RISK_TYPE[row.risk as RiskLabel] as any" size="small">{{ row.risk }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="school_name" label="院校" min-width="160" show-overflow-tooltip />
            <el-table-column prop="major_name" label="专业" min-width="160" show-overflow-tooltip />
            <el-table-column label="城市" width="110">
              <template #default="{ row }">{{ row.province }}{{ row.city ? '·' + row.city : '' }}</template>
            </el-table-column>
            <el-table-column label="近年最低位次（2026）" width="130" align="right">
              <template #default="{ row }"><span class="tnum">{{ fmt(row.last_year_rank) }}</span></template>
            </el-table-column>
            <el-table-column label="位次差" width="110" align="center">
              <template #default="{ row }">{{ diffText(row.rank_diff_last) }}</template>
            </el-table-column>
            <el-table-column prop="saved_at" label="收藏时间" width="160" />
            <el-table-column label="操作" width="190" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link size="small" :type="planner.inCompare(row.id) ? 'primary' : 'default'" @click="onToggleCompare(row)">对比</el-button>
                <el-button link size="small" type="success" @click="addFavToPlan(row.id)">+方案</el-button>
                <el-button link size="small" type="danger" @click="planner.removeFavorite(row.id)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ============ 对比中心 ============ -->
      <el-tab-pane :label="`对比中心（${compareIds.length}/5）`" name="compare">
        <el-card class="card" shadow="never">
          <el-empty v-if="compareList.length < 2" description="从「收藏」或「智能匹配」加入 2–5 项后同屏对比。" />
          <template v-else>
            <div class="toolbar">
              <span class="muted">同屏对比 {{ compareList.length }} 项（位次 / 波动 / 层次 / 城市 / 依据）</span>
              <el-button size="small" @click="planner.clearCompare()">清空对比</el-button>
            </div>
            <div class="cmp-wrap">
              <table class="cmp">
                <thead>
                  <tr>
                    <th class="cmp__attr">对比项</th>
                    <th v-for="c in compareList" :key="c.id">
                      <div class="cmp__school">{{ c.school_name }}</div>
                      <div class="cmp__major">{{ c.major_name }}</div>
                      <el-button link size="small" type="danger" @click="planner.toggleCompare(c)">移除</el-button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in COMPARE_ROWS" :key="r.label">
                    <td class="cmp__attr">{{ r.label }}</td>
                    <td v-for="c in compareList" :key="c.id" :class="{ 'cmp__risk': r.label === '风险档' }">
                      <el-tag v-if="r.label === '风险档'" :type="RISK_TYPE[c.risk] as any" size="small">{{ c.risk }}</el-tag>
                      <template v-else>{{ r.get(c) }}</template>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </el-card>
      </el-tab-pane>

      <!-- ============ 我的方案 ============ -->
      <el-tab-pane :label="`我的方案（${plans.length}）`" name="plans">
        <el-card class="card" shadow="never">
          <div class="toolbar">
            <el-select v-model="activePlanId" placeholder="选择方案" style="width: 220px">
              <el-option v-for="p in plans" :key="p.id" :label="`${p.name}（${p.entries.length}）`" :value="p.id" />
            </el-select>
            <el-input v-model="newPlanName" placeholder="新方案名" style="width: 180px" @keyup.enter="createPlan" />
            <el-button @click="createPlan">新建方案</el-button>
            <template v-if="activePlan">
              <el-button type="warning" plain @click="planner.sortPlanByGradient(activePlan.id)">按冲→稳→保重排</el-button>
              <el-button type="primary" :loading="exporting" @click="exportPlan(activePlan)">导出志愿表 xlsx</el-button>
              <el-button type="danger" plain @click="deletePlan(activePlan)">删除方案</el-button>
            </template>
          </div>

          <template v-if="activePlan">
            <div class="plan-meta">
              考生：{{ activePlan.examinee.year }} 年 {{ activePlan.examinee.subject }} {{ activePlan.examinee.batch }}，
              位次 {{ fmt(activePlan.examinee.rank) }} ·
              创建于 {{ activePlan.created_at }} · 数据版本 {{ activePlan.data_version || '—' }}
            </div>

            <!-- 梯度分析已提升到顶部「方案体检」卡，此处仅保留志愿明细表 -->
            <el-empty v-if="!activePlan.entries.length" description="方案为空：从「智能匹配」或「收藏」加入志愿。" />
            <el-table v-else :data="activePlan.entries" size="small" border>
              <el-table-column type="index" label="序号" width="60" align="center" />
              <el-table-column label="档位" width="90" align="center">
                <template #default="{ row }"><el-tag :type="RISK_TYPE[row.risk as RiskLabel] as any" size="small">{{ row.risk }}</el-tag></template>
              </el-table-column>
              <el-table-column prop="school_name" label="院校" min-width="150" show-overflow-tooltip />
              <el-table-column prop="major_name" label="专业" min-width="150" show-overflow-tooltip />
              <el-table-column label="2026最低分/位次" width="150" align="right">
                <template #default="{ row }">
                  <span class="tnum">{{ row.last_year_score ?? '—' }}</span> /
                  <span class="tnum">{{ fmt(row.last_year_rank) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="位次差" width="110" align="center">
                <template #default="{ row }">{{ diffText(row.rank_diff_last) }}</template>
              </el-table-column>
              <el-table-column label="城市" width="100">
                <template #default="{ row }">{{ row.city || '—' }}</template>
              </el-table-column>
              <el-table-column label="备注" min-width="140">
                <template #default="{ row }"><el-input v-model="row.note" size="small" placeholder="备注" /></template>
              </el-table-column>
              <el-table-column label="排序/操作" width="160" align="center" fixed="right">
                <template #default="{ $index, row }">
                  <el-button link size="small" :disabled="$index === 0" @click="planner.moveEntry(activePlan!.id, $index, -1)">↑</el-button>
                  <el-button link size="small" :disabled="$index === activePlan!.entries.length - 1" @click="planner.moveEntry(activePlan!.id, $index, 1)">↓</el-button>
                  <el-button link size="small" type="danger" @click="planner.removeFromPlan(activePlan!.id, row.id)">移除</el-button>
                </template>
              </el-table-column>
            </el-table>

            <p class="hint">
              导出列对齐辽宁「专业+学校」平行志愿：序号 / 档位 / 院校代码 / 院校名称 / 专业代码 / 专业名称 /
              往年最低分 / 往年最低位次 / 位次差 / 层次 / 城市。条目保存加入时的数据版本快照；
              本表仅供参考，最终以省招考部门及院校官方发布为准。
            </p>
          </template>
          <el-empty v-else description="暂无方案：输入方案名点「新建方案」。" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.hero { margin-bottom: var(--space-5); }
.hero h1 { font-size: var(--text-2xl); }
.hero__sub { color: var(--color-text-secondary); max-width: 780px; margin-top: var(--space-2); }
.card { margin-bottom: var(--space-4); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }

/* 方案体检卡（置顶） */
.checkup {
  margin-bottom: var(--space-5);
  border-radius: var(--radius-lg);
  border-width: 1px;
  border-style: solid;
}
.checkup--ok { border-color: var(--color-match); background: var(--color-match-soft); }
.checkup--warn { border-color: var(--color-reach); background: var(--color-reach-soft); }
.checkup__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.checkup__title { font-weight: 700; font-size: var(--text-lg); color: var(--color-text); }
.checkup__total { margin-left: var(--space-3); color: var(--color-text-muted); font-size: var(--text-sm); }
.checkup__badge {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-reach);
  padding: var(--space-1) var(--space-3);
  border-radius: 999px;
  background: #fff;
}
.ratio {
  display: flex;
  gap: 3px;
  height: 28px;
  margin-bottom: var(--space-3);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.ratio__seg {
  display: grid;
  place-items: center;
  min-width: 44px;
  color: #fff;
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
}
.ratio__seg--success { background: var(--color-match); }
.ratio__seg--primary { background: var(--color-safe); }
.ratio__seg--warning { background: var(--color-reach); }
.ratio__seg--danger { background: var(--color-volatile); }
.ratio__seg--info { background: var(--color-insufficient); }
.checkup__list {
  margin: 0;
  padding-left: 1.2em;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.9;
}
.checkup__list--ok { color: var(--color-match); font-weight: 500; }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); }
.muted { color: var(--color-text-muted); font-size: var(--text-xs); }
.plan-meta { color: var(--color-text-secondary); font-size: var(--text-sm); margin-bottom: var(--space-3); }
.analysis { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); background: var(--color-bg-subtle); }
.analysis__chips { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2); }
.analysis__warn { margin: 0; padding-left: 1.2em; font-size: var(--text-sm); color: var(--color-text-secondary); line-height: 1.8; }
.cmp-wrap { overflow-x: auto; }
.cmp { border-collapse: collapse; width: 100%; font-size: var(--text-sm); }
.cmp th, .cmp td { border: 1px solid var(--color-border); padding: var(--space-2) var(--space-3); text-align: left; vertical-align: top; min-width: 160px; }
.cmp thead th { background: var(--color-bg-subtle); }
.cmp__attr { width: 140px; min-width: 140px !important; font-weight: 600; color: var(--color-text-secondary); background: var(--color-bg-subtle); }
.cmp__school { font-weight: 600; }
.cmp__major { color: var(--color-text-secondary); font-size: var(--text-xs); margin: 2px 0 4px; }
.hint { color: var(--color-text-muted); font-size: var(--text-xs); margin: var(--space-3) 0 0; line-height: 1.7; }
</style>
