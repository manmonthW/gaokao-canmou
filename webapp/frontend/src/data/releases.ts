export interface ProductRelease {
  version: string
  date: string
  title: string
  summary: string
  features: string[]
}

/**
 * 面向用户的版本记录。只写用户能感知的能力，不记录内部重构、迁移编号或技术术语。
 * 新版本必须插入数组顶部，并同步更新 CURRENT_VERSION。
 */
export const PRODUCT_RELEASES: ProductRelease[] = [
  {
    version: '1.4.0',
    date: '2026-09-16',
    title: '院校地域探索上线',
    summary: '院校查询增加按地域浏览，帮助还没有明确目标院校的用户从省份和城市开始筛选。',
    features: [
      '院校查询新增“搜索院校 / 按地域浏览”两种查询方式',
      '支持按省份、城市逐级浏览院校和城市画像',
      '接入全国 31 个省级地区本科高校分布图',
      '点击地域浏览结果可直接打开院校详情',
    ],
  },
  {
    version: '1.3.0',
    date: '2026-08-25',
    title: '专业冷热趋势与门槛曲线',
    summary: '用三年历史数据展示专业门槛变化，并将专业自身趋势与全省大盘变化分开呈现。',
    features: [
      '匹配结果和专业详情增加专业门槛趋势',
      '历年门槛曲线增加全省大盘基准线',
      '工作台增加趋势集中风险提醒',
      '数据中心增加专业趋势方法说明和全量数据表',
    ],
  },
  {
    version: '1.2.0',
    date: '2026-08-12',
    title: '院校学科与专业实力',
    summary: '在匹配和院校详情中补充学科评估、一流学科与一流专业等参考信息。',
    features: [
      '院校详情增加学科与专业实力明细',
      '匹配结果增加实力标签和来源说明',
      '区分官方、非官方汇总和第三方评价口径',
    ],
  },
  {
    version: '1.1.0',
    date: '2026-08-08',
    title: '资格自查与决策增强',
    summary: '增加选科要求、特殊专业标记、位次敏感度试算和备考期估位能力。',
    features: [
      '新增资格自查页面与选科要求查询',
      '中外合作、定向、预科等特殊标记可识别和筛选',
      '支持位次上下浮动情景试算',
      '工作台增加梯度模板、覆盖曲线和方案体检',
    ],
  },
  {
    version: '1.0.0',
    date: '2026-07-29',
    title: '核心志愿决策流程上线',
    summary: '完成从定位、匹配到收藏、比较、方案和导出的主要使用闭环。',
    features: [
      '分数与位次定位、省控线判断和跨年对照',
      '院校与专业查询、详情和数据来源追溯',
      '普通类冲、稳、保、高波动和数据不足分档',
      '收藏、对比、多方案、梯度分析和 Excel 导出',
    ],
  },
]

export const CURRENT_VERSION = PRODUCT_RELEASES[0].version
export const RELEASE_STORAGE_KEY = 'ln-advisor:last-seen-version'
