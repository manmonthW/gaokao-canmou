---
name: 辽宁志愿参谋
description: 可信的招生办控制台 — 严谨、可溯源的辽宁高考志愿决策辅助界面
colors:
  trusted-blue: "#2563eb"
  trusted-blue-hover: "#1d4ed8"
  trusted-blue-soft: "#eef4ff"
  ledger-navy: "#0a2540"
  ink-secondary: "#425466"
  ink-muted: "#697386"
  paper-bg: "#f6f9fc"
  surface: "#ffffff"
  border: "#e3e8ee"
  border-strong: "#d5dbe3"
  reach-amber: "#f5a623"
  reach-amber-soft: "#fdf3e2"
  match-green: "#1bb978"
  match-green-soft: "#e7f8f0"
  safe-blue: "#2563eb"
  safe-blue-soft: "#eef4ff"
  volatile-purple: "#7a5af8"
  volatile-purple-soft: "#f1edff"
  insufficient-gray: "#8792a2"
  insufficient-gray-soft: "#eef1f4"
  danger-red: "#e25950"
typography:
  display:
    fontFamily: "\"PingFang SC\", \"Microsoft YaHei\", \"Source Han Sans SC\", \"Noto Sans CJK SC\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1.3
  headline:
    fontFamily: "\"PingFang SC\", \"Microsoft YaHei\", \"Source Han Sans SC\", \"Noto Sans CJK SC\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.35
  title:
    fontFamily: "\"PingFang SC\", \"Microsoft YaHei\", \"Source Han Sans SC\", \"Noto Sans CJK SC\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "\"PingFang SC\", \"Microsoft YaHei\", \"Source Han Sans SC\", \"Noto Sans CJK SC\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "\"PingFang SC\", \"Microsoft YaHei\", \"Source Han Sans SC\", \"Noto Sans CJK SC\", -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.4
  numeric:
    fontFamily: "\"SF Mono\", \"JetBrains Mono\", \"Roboto Mono\", Menlo, Consolas, monospace"
    fontSize: "14px"
    fontWeight: 500
    fontFeature: "tnum"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  pill: "999px"
  circle: "50%"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "20px"
  "6": "24px"
  "8": "32px"
components:
  button-primary:
    backgroundColor: "{colors.trusted-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
  button-primary-hover:
    backgroundColor: "{colors.trusted-blue-hover}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
  chip-filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.pill}"
    padding: "8px 16px"
  chip-filter-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.trusted-blue}"
    rounded: "{rounded.pill}"
    padding: "8px 16px"
  badge-risk-reach:
    backgroundColor: "{colors.reach-amber-soft}"
    textColor: "{colors.reach-amber}"
    rounded: "{rounded.pill}"
  badge-risk-match:
    backgroundColor: "{colors.match-green-soft}"
    textColor: "{colors.match-green}"
    rounded: "{rounded.pill}"
  badge-risk-safe:
    backgroundColor: "{colors.safe-blue-soft}"
    textColor: "{colors.safe-blue}"
    rounded: "{rounded.pill}"
  badge-risk-volatile:
    backgroundColor: "{colors.volatile-purple-soft}"
    textColor: "{colors.volatile-purple}"
    rounded: "{rounded.pill}"
  badge-risk-insufficient:
    backgroundColor: "{colors.insufficient-gray-soft}"
    textColor: "{colors.insufficient-gray}"
    rounded: "{rounded.pill}"
---

# Design System: 辽宁志愿参谋

## Overview

**Creative North Star: "可信的招生办控制台" (The Trusted Admissions Console)**

这套系统把 Stripe 的克制商务语言，接到辽宁考生与家长的实际场景上：数据是唯一可信来源，界面不替用户做决定，只把每一次判断的依据摆到台面上。语气是**严谨可信、控制先行**——先讲清楚"你在哪、依据是什么"，再给建议；颜色只用来传递分类信息（冲/稳/保/高波动/数据不足），不用来制造情绪或吸引点击。这不是一个营销落地页，而是考生和家长在出分后几天内反复打开、需要能立刻信任的工具。

系统明确拒绝"活泼消费品"感：不使用大块/多色/高饱和渐变背景、不用圆润卡通化图标、不追求 SaaS 营销页那种轻快跳跃的视觉能量。渐变有两类受限的合法场景，除此之外一律禁止：① 实力评估徽章（`StrengthBadges.vue`）的琥珀→橙三档配色，唯一承载真实信息的信号级渐变，严格封闭在这一个组件内；② 极克制的单色深浅过渡（如 `--color-primary-soft`→白、白→`--color-bg-subtle`、`--color-primary-soft` 半透明→透明），只用于卡片/区块背景的极轻微纵深感，透明度差和色相跨度都必须小到几乎不可察觉——这类"氛围底色"不是视觉签名，出现在 App.vue 步骤条、StepGuide.vue、Workbench 曲线卡片属于已确认的用法，新增前先问是否真的需要，而不是默认可用。

**Key Characteristics:**
- 可信蓝 (#2563eb) 为唯一强调色，其余全部是中性灰蓝与五种风险语义色
- 数字（分数/位次/位次差）一律等宽对齐，比较时不跳动
- 阴影克制、低透明度、只表达层级，不装饰
- 圆角分层：小控件用 sm/md，容器用 lg，标签/徽章用 999px 全圆角
- 页面内容统一收束在 1080px 容器内，移动端优先降级（隐藏次要文案，横向可滚动的步骤条）

## Colors

调色板整体是"银行/法律文书"式的低饱和中性灰蓝底色，叠加五种严格语义化的风险分类色——除强调色外没有第二个"自由使用"的品牌色。

### Primary
- **可信蓝 Trusted Blue** (#2563eb): 唯一的品牌强调色。用于主按钮、当前步骤高亮、链接、"保"档语义色（与安全区语义复用同一色相不是巧合：蓝色同时承担"品牌"与"保底安全"两层含义）。Hover 态加深为 #1d4ed8；柔和底色 #eef4ff 用于选中态/强调分段背景。

### Neutral
- **档案藏青 Ledger Navy** (#0a2540): 正文与标题主文字色，取自 Stripe 原版 navy，是整个系统"严肃感"的文字基调。
- **次要灰蓝 Ink Secondary** (#425466): 次级说明文字、标签文案。
- **静音灰蓝 Ink Muted** (#697386): 时间戳、来源说明、辅助元信息，视觉权重最低但仍可读。
- **纸面浅灰 Paper BG** (#f6f9fc): 页面底色。
- **纯白 Surface** (#ffffff): 卡片、输入框、弹层背景。
- **发丝边框 Border** (#e3e8ee) / **强调边框 Border Strong** (#d5dbe3): 分隔线、卡片描边、控件描边；strong 变体用于需要更明确视觉分界的场景（如资料库导航按钮描边）。

### 风险分类色（五分类，语义严格绑定）
- **警示琥珀 Reach Amber** (#f5a623 / 底色 #fdf3e2): 「冲」——历史位次通常优于考生当前位次，有风险。
- **稳健绿 Match Green** (#1bb978 / 底色 #e7f8f0): 「稳」——位次处于历史常见录取区间附近。
- **安心蓝 Safe Blue** (#2563eb / 底色 #eef4ff): 「保」——位次明显优于历史最低位次；与主色同色相，强化"安全=品牌信任"的联想。
- **警觉紫 Volatile Purple** (#7a5af8 / 底色 #f1edff): 「高波动」——历史变化较大，需单独提示，用与其他四色都不同的色相强制打断视觉惯性。
- **中性灰 Insufficient Gray** (#8792a2 / 底色 #eef1f4): 「数据不足」——只有一个年份或字段不完整，故意用最低饱和度表达"降级/不确定"。
- **警报红 Danger Red** (#e25950): 仅用于硬性错误/危险状态（如步骤条的"警"态），不用于风险分类五色之外的场景。

### Named Rules
**The Two Palettes Rule.** 风险分类五色（reach/match/safe/volatile/insufficient）只用来表达"冲/稳/保/高波动/数据不足"这一个五分类语义，在候选卡片、图表图例、Workbench 梯度分析、PlanBasket 芯片、Locate 定位徽章里必须保持完全一致的映射。Element Plus 默认语义色（success/warning/danger/info）留给通用 UI 反馈（表单校验、保存成功提示、筛选 Tab 高亮环）——两套调色板不能互相替代，混用会让"这是风险分类还是普通状态提示"变得含糊。

**The Soft-Fill Rule.** 风险色与强调色在做标签/徽章底色时，永远配对使用各自的 `-soft` 浅底版本，不直接使用饱和色打底（饱和色只用于文字/图标/描边）。

## Typography

**Display/Body/Label Font:** "PingFang SC", "Microsoft YaHei", "Source Han Sans SC", "Noto Sans CJK SC" 等中文字体栈优先，兜底至系统 UI 字体（-apple-system / Segoe UI / Roboto / Arial）
**Numeric Font:** "SF Mono", "JetBrains Mono", "Roboto Mono", Menlo, Consolas（等宽）

**Character:** 中文字重整体比 Stripe 原版上提一档（正文 400、UI 元素 500、标题 600/700），弥补 Stripe 原始 300 字重在中文渲染下发虚的问题；去除 CJK 负字距，避免中文挤压变形。

### Hierarchy
- **Display** (700, 26px, line-height 1.3): 页面主标题（如"我的定位"页 h1）。
- **Headline** (600, 20px, line-height 1.35): 区块/卡片头级标题。
- **Title** (600, 16px, line-height 1.4): 品牌名、次级标题、强调行文本。
- **Body** (400, 14px, line-height 1.6): 默认正文，全站基准字号。
- **Label** (500, 13px, line-height 1.4): 表单标签、次要说明、标签文案。

### Named Rules
**The Tabular Numbers Rule.** 任何分数、位次、位次差、年份版本号都必须使用等宽数字（`.tnum` / `font-feature-settings: "tnum"`，字体切到 mono 栈）。这不是装饰性选择——考生在同一屏比较多组数字时，数字宽度跳动会直接损害"可信"的核心体验承诺。

## Layout

内容统一收束在 **1080px** 最大宽度容器内并居中（header/stepper/main 三处保持完全一致的容器宽度与左右 padding `var(--space-4)`），这是全站唯一的栅格基准，不做多栏可变宽布局。

页面顶部是粘性玻璃态 header（`backdrop-filter: blur(8px)` + 90% 不透明白底），其下紧贴一条**决策主线步骤条**（我的定位 → 智能匹配 → 决策工作台），横向排列、带编号圆形徽章与当前/完成/警示三态，在窄屏下横向可滚动（`overflow-x: auto` + `white-space: nowrap`）而不换行——保证用户任何时候都知道自己在决策链路的哪一步。

移动端断点 **640px**：隐藏 header 副标语（`.brand__tag`），导航区域取消强制右对齐外边距。间距基准 4px（`--space-1` 至 `--space-8`：4/8/12/16/20/24/32px），卡片之间统一用 `--space-4`（16px）做垂直间隔。

## Elevation & Depth

**克制阴影（Restrained Shadow）是固定规则，不是可调选项。** 系统使用低透明度、navy 色调的阴影（阴影颜色始终是 `rgba(10, 37, 64, 0.03–0.10)`，绝不用纯黑），阴影只表达"这是一个可交互的层"或"这是当前激活态"，从不作为装饰。

### Shadow Vocabulary
- **sm** (`0 1px 1px rgba(10,37,64,.03), 0 1px 3px rgba(10,37,64,.04)`): 默认卡片、激活态的导航项/步骤条项。
- **md** (`0 1px 1px rgba(10,37,64,.03), 0 4px 10px rgba(10,37,64,.06)`): 悬浮层级更高的元素（弹层、下拉）。
- **lg** (`0 2px 5px rgba(10,37,64,.04), 0 12px 28px rgba(10,37,64,.10)`): 模态、抽屉等最高层级。

### Named Rules
**The Restrained Shadow Rule.** 阴影透明度不得超过当前三档定义的上限；静止态的普通表面（页面背景、次要分隔区块）保持完全平面，阴影只在"卡片/悬浮层"或"激活/hover 状态"两种场景下出现。

## Shapes

分层圆角策略，按元素的"密度角色"决定用哪一级：
- **sm (6px)**：小型强调元素（品牌图标方块、导航图标容器、迷你标签）。
- **md (8px)**：交互控件默认级——按钮、输入框、卡片内的行动条（`.sec__action`）。
- **lg (12px)**：卡片、容器、步骤条选中项——所有"面"级元素。
- **pill (999px)**：筛选芯片、风险徽章、档案摘要分段——所有"标签/状态"类元素。
- **circle (50%)**：头像、步骤编号徽章。

边框统一用 1px 发丝线（`--color-border` / `--color-border-strong`），不使用粗描边或双线框。

## Components

### Buttons
- **Shape:** 圆角 8px（`--radius-md`，经 Element Plus `--el-border-radius-base` 桥接）。
- **Primary:** 背景可信蓝 (#2563eb)，文字白色；hover 加深至 #1d4ed8。
- **签名变体——行动条按钮 (`.sec__action`)：** 全宽、软蓝底 (#eef4ff) + 强调边框 + 图标 + 文案 + 右侧箭头，整行可点，用于"生成候选/展开说明"这类需要更强引导但又不想用饱和主色刷屏的场景；hover 底色加深至 #dce9ff。

### Chips / Tags
- **筛选芯片 (`.chip`)：** 白底、1px 描边、999px 全圆角；激活态用 `box-shadow: 0 0 0 2px <语义色>` 的色环高亮，颜色取自 Element Plus 通用语义色（success/primary/warning/danger/info），因为这里表达的是"筛选 Tab 当前选中"而非风险分类本身。芯片内数字用等宽数字。
- **风险徽章：** 五种风险色的 soft 底 + 对应文字色，pill 圆角，出现在候选卡片、PlanBasket、Workbench 图例、Locate 定位流程徽章中，映射关系全站统一（见 Colors 的 Two Palettes Rule）。
- **实力评估徽章（`StrengthBadges.vue`，签名组件）：** 第五轮学科评估 A+/A/A- 三档，用琥珀→橙渐变家族区分档位（唯一允许渐变的场景，且封闭在这一个组件内）；非官方汇总来源（eval5 kind）用虚线描边区隔官方数据；第三方来源额外降级为灰色系并带角标免责提示；所有文案（含 tooltip 里的来源说明）都从后端词表 `meta.strength_dictionary` 解析，前端不硬编码。

### Cards / Containers
- **Corner Style:** 12px（`--radius-lg`）。
- **Background:** 纯白 (#ffffff)。
- **Shadow Strategy:** 固定用 `--shadow-sm`（见 Elevation & Depth）。
- **Border:** 通常无描边，靠阴影与留白分隔；档案摘要条（`.profile-bar`）等强调型容器额外加 1px `--color-border` 描边。
- **Internal Padding:** 卡片间垂直间距统一 `--space-4`（16px）。

### Inputs / Fields
- **Style:** Element Plus 默认描边输入框，圆角桥接到 `--radius-md`；筛选场景的下拉/输入框有固定窄宽度（150–160px）以适配横向筛选行。
- **Focus / Error:** 沿用 Element Plus 默认焦点环与校验态，不做额外定制（校验反馈属于"通用 UI 状态"，走 Element Plus 语义色，不占用风险色）。

### Navigation
- **顶部 Header：** 粘性、玻璃态（90% 白底 + 8px 模糊），品牌角标是 30px 圆角方块（`--radius-sm`）+ 可信蓝底 + 白色"辽"字；副标语在 ≤640px 时隐藏。资料库入口是图标+文字分段按钮，每个入口有独立的强调色（通过内联 CSS 变量 `--icon`/`--icon-soft` 传入），当前路由激活态用该色的 soft 底 + 描边 + `--shadow-sm`。账号区是圆形头像（可信蓝底、白字首字母）+ 下拉菜单。
- **决策主线步骤条：** header 正下方，横向排列的三步（定位/匹配/工作台），每步是编号圆形徽章（26px，`--radius-circle`）+ 标题 + 一句话摘要；默认灰底，激活态可信蓝底，完成态稳健绿底，警示态警报红底。窄屏下横向可滚动，不换行、不折叠信息层级。

## Do's and Don'ts

### Do:
- **Do** 风险分类（冲/稳/保/高波动/数据不足）永远使用五个专属 token 及其 soft 底色变体，在候选卡片、图表、图例、徽章间保持完全一致的映射（The Two Palettes Rule）。
- **Do** 任何分数/位次/位次差/版本号使用等宽数字 `.tnum`（The Tabular Numbers Rule）。
- **Do** 阴影只用三档 navy 低透明度值表达层级/激活态，不用于装饰（The Restrained Shadow Rule）。
- **Do** 颜色编码的状态（尤其风险分类）必须配文字/图形冗余，不能仅靠颜色传达——色觉友好是产品明确要求（见 PRODUCT.md Accessibility & Inclusion）。
- **Do** 页面内容宽度收束在 1080px 内并居中，与 header/stepper 保持同一容器基准。
- **Do** 移动端优先验证：家长/考生高频用手机访问，任何新组件先看窄屏表现。

### Don't:
- **Don't** 引入大块渐变背景或高饱和多色拼贴——系统明确拒绝"活泼消费品"感；渐变仅限实力评估徽章的信号级用法，或已确认的极克制单色氛围底色（见 Overview）。
- **Don't** 把风险分类五色与 Element Plus 通用语义色（success/warning/danger/info）混用表达同一件事——风险分类走专属 token，通用 UI 反馈（校验/提示/筛选高亮）走 Element Plus 默认色。
- **Don't** 用饱和色直接做标签/徽章底色，必须走对应的 `-soft` 变体（The Soft-Fill Rule）。
- **Don't** 提高阴影不透明度或改用纯黑阴影——会打破"克制"基调。
- **Don't** 为追求"活泼"而给圆角、字重、图标风格加卡通化处理；组件手感锚定"精确克制"（precise and restrained），不是"稳健厚重"。
