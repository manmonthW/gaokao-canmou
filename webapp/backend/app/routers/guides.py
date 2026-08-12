"""报考说明：辽宁省 2026 官方招考文件 + 配套参考资料在线阅读（只读、不落库）。

文件来自 2026allmaterial/ 目录（含子目录，filename 用相对路径），
按「阅读习惯」分组：先读总政策 → 填报操作 → 军校/公安专项 →
体检与招飞标准 → 助学与专项计划 → 官方信源与滑档警示案例。

端点：
  GET /guides            分组元数据（标题/简介/要点/文件大小）
  GET /guides/{id}/pdf   PDF 流式下载（仅白名单内文件）
"""
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(prefix="/guides", tags=["guides"])

# 官方文件根目录（与 hot_schools 图片根目录同一套推导），
# Docker 部署时可用 GUIDE_PDF_ROOT 环境变量覆盖。
_PDF_ROOT = os.environ.get(
    "GUIDE_PDF_ROOT",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))),
        "2026allmaterial",
    ),
)


def _item(id, title, filename, summary, points, tag):
    return {
        "id": id, "title": title, "filename": filename,
        "summary": summary, "points": points, "tag": tag,
    }


# 由 etl/build_guide_html.py 预先生成的排版 HTML（自包含样式）
# Docker 部署时 static 挂载在 /app/static，可用 GUIDE_HTML_DIR 环境变量覆盖。
_HTML_DIR = os.environ.get(
    "GUIDE_HTML_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))),
        "webapp", "backend", "static", "guides",
    ),
)


_GROUPS = [
    {
        "key": "policy",
        "title": "总政策 · 先把规则读懂",
        "desc": "建议最先阅读：理解今年招生的整体规则与最新变化，再动手填志愿。",
        "items": [
            _item(
                "zhaosheng-jianzhang", "辽宁省2026年普通高等学校招生简章",
                "辽宁省2026年普通高等学校招生简章.pdf",
                "今年在辽招生的总纲领：报名条件、考试安排、录取规则与时间节点的权威说明。",
                ["报名与考试安排", "录取规则与批次", "重要时间节点"], "必读",
            ),
            _item(
                "zhiyuan-wenda", "辽宁省2026年普通高校招生志愿填报及招生录取问答",
                "辽宁省2026年普通高校招生志愿填报及招生录取问答.pdf",
                "官方以问答形式解释填报与录取中的常见疑问，规则细节的权威解答。",
                ["平行志愿怎么投", "退档与征集", "常见疑问官方答"], "必读",
            ),
            _item(
                "tiqian-tiaozheng", "我省高考普通类本科提前批批次及志愿设置调整政策解读",
                "我省高考普通类本科提前批批次及志愿设置调整政策解读.pdf",
                "本科提前批的批次划分与志愿设置有新调整，本文件是官方逐条解读。",
                ["提前批新变化", "志愿设置调整", "受影响考生"], "最新变化",
            ),
        ],
    },
    {
        "key": "filling",
        "title": "填报操作 · 动手前看",
        "desc": "正式填报系统开放前后阅读：填报流程、操作规范与注意事项。",
        "items": [
            _item(
                "tianbao-xuzhi", "辽宁省2026年普通高校招生志愿填报须知",
                "辽宁省2026年普通高校招生志愿填报须知.pdf",
                "志愿填报系统的操作流程、时间安排与纪律要求，填报当天照着做即可。",
                ["填报时间与入口", "操作步骤", "注意事项"], "操作指南",
            ),
        ],
    },
    {
        "key": "military",
        "title": "专项通道 · 军队院校",
        "desc": "报考军校的考生必读：政治考核有明确时间窗口，务必提前准备。",
        "items": [
            _item(
                "junxiao-zhinan", "2026年辽宁省军队院校招生报考指南",
                "2026年辽宁省军队院校招生报考指南.pdf",
                "军校招生全流程指南：报考条件、政审、军检、面试与录取办法。",
                ["报考条件", "军检与面试", "录取流程"], "军校必读",
            ),
            _item(
                "junxiao-zhengshen", "关于做好2026年军队院校招收辽宁省普通高中毕业生政治考核工作的通知",
                "关于做好2026年军队院校招收辽宁省普通高中毕业生政治考核工作的通知.pdf",
                "军校政治考核（政审）的表格下载、办理流程与截止时间。",
                ["政审表格与流程", "时间节点", "材料要求"], "有截止时限",
            ),
        ],
    },
    {
        "key": "police",
        "title": "专项通道 · 公安院校",
        "desc": "报考公安院校公安专业的考生必读：体测与体检有硬性标准。",
        "items": [
            _item(
                "gongan-xuzhi", "2026年辽宁省公安院校公安专业招生政治考察、面试、体检、体能测评须知",
                "2026年辽宁省公安院校公安专业招生政治考察、面试、体检、体能测评须知.pdf",
                "公安专业加试全流程：政治考察、面试、体检标准与体能测评项目。",
                ["体测项目与标准", "体检要求", "考察与面试"], "公安必读",
            ),
        ],
    },
    {
        "key": "checkup",
        "title": "专项通道 · 体检与招飞标准",
        "desc": "军校、警校、招飞、定向士官均有特殊体检硬标准，报考前先自查身体条件，避免白忙一场。",
        "items": [
            _item(
                "junxiao-tijian", "军队院校招收学员体格检查标准（军校体检规定）",
                "2025高考志愿填报资料汇总/军校体检规定.pdf",
                "军校体检的逐条合格标准：视力、身高体重、内外科等，先对照再报。",
                ["视力与体重标准", "常见不合格项", "军检流程"], "体检标准",
            ),
            _item(
                "kongjun-zhaofei", "空军招飞体检规定",
                "2025高考志愿填报资料汇总/空军招飞体检规定.pdf",
                "空军飞行员选拔的体检标准，是所有招生通道里最严格的一档。",
                ["眼科硬标准", "初选与复选", "淘汰项自查"], "招飞",
            ),
            _item(
                "sanda-zhaofei", "三大招飞报考流程及体检",
                "2025高考志愿填报资料汇总/三大招飞报考流程及体检.pdf",
                "空军、海军、民航三大招飞通道的报考流程与体检差异对比。",
                ["三类招飞区别", "报名时间线", "体检差异"], "招飞",
            ),
            _item(
                "jingshi-tijian", "警校高考体检规定",
                "2025高考志愿填报资料汇总/警校高考体检规定.pdf",
                "公安/司法类院校体检标准：视力、体重、外观等硬性门槛。",
                ["视力标准", "体测衔接", "常见淘汰项"], "体检标准",
            ),
            _item(
                "shiguan-tijian", "定向士官生体检规定",
                "2025高考志愿填报资料汇总/定向士官生体检规定.pdf",
                "定向培养军士（原定向士官）招生体检标准，参照军检但略有放宽。",
                ["体检项目", "与军检差异", "报考流程"], "体检标准",
            ),
        ],
    },
    {
        "key": "aid",
        "title": "助学与专项计划",
        "desc": "家庭经济困难考生与农村户籍考生重点关注：资助政策与降分专项通道。",
        "items": [
            _item(
                "zhuxue-zhengce", "国家助学政策",
                "国家助学政策.pdf",
                "国家助学金、助学贷款、绿色通道等资助体系全览，经济困难不影响上大学。",
                ["助学金与贷款", "绿色通道", "申请办法"], "资助政策",
            ),
            _item(
                "sanda-zhuanxiang", "三大专项计划",
                "三大专项计划.pdf",
                "国家/地方/高校三大专项计划：农村与贫困地区考生的降分升学通道，有户籍学籍门槛。",
                ["三类专项区别", "报考条件", "与资格页联动"], "降分通道",
            ),
        ],
    },
    {
        "key": "sources",
        "title": "权威信源与警示案例",
        "desc": "官方信息以各省考试院为准；100 个真实滑档案例是最便宜的教训课。",
        "items": [
            _item(
                "kaoshiyuan-huizong", "全国31省市教育考试院官方网站汇总",
                "全国31省市教育考试院官方网站汇总.pdf",
                "各省招生考试机构官网名录，查政策、查录取只认官方域名，谨防仿冒网站。",
                ["各省官网名录", "防仿冒提示", "信息查询入口"], "官方信源",
            ),
            _item(
                "huadang-anli", "全国31省市100个高考填报滑档真实案例",
                "全国31省市100个高考填报滑档真实案例.pdf",
                "100 个真实滑档/退档案例复盘：梯度失衡、不服从调剂、体检受限等高频坑点。",
                ["真实案例复盘", "高频失误原因", "避坑清单"], "警示必读",
            ),
        ],
    },
]


def _file_size(filename):
    p = os.path.join(_PDF_ROOT, filename)
    try:
        return os.path.getsize(p)
    except OSError:
        return None


@router.get("")
async def guides():
    """分组元数据：含文件大小与是否存在标记（文件缺失时前端提示）。"""
    groups = []
    for g in _GROUPS:
        items = []
        for it in g["items"]:
            size = _file_size(it["filename"])
            items.append({**it, "size_bytes": size, "available": size is not None})
        groups.append({"key": g["key"], "title": g["title"],
                       "desc": g["desc"], "items": items})
    total = sum(len(g["items"]) for g in groups)
    return {
        "groups": groups,
        "total": total,
        "note": ("以辽宁省官方发布的 2026 年招考文件原件为主，辅以体检标准、助学政策与"
                 "警示案例等参考资料（均为 PDF 原件）。政策每年更新，"
                 "请以省招考办最新发布为准。"),
    }


@router.get("/{gid}/pdf")
async def guide_pdf(gid: str):
    """按 id 白名单定位 PDF 并流式返回（不接受任意路径，防目录穿越）。"""
    for g in _GROUPS:
        for it in g["items"]:
            if it["id"] == gid:
                path = os.path.join(_PDF_ROOT, it["filename"])
                if not os.path.exists(path):
                    raise HTTPException(404, "该文件尚未放入材料目录")
                return FileResponse(
                    path, media_type="application/pdf", filename=it["filename"])
    raise HTTPException(404, f"未知文件 id：{gid}")


@router.get("/{gid}/html")
async def guide_html(gid: str):
    """返回由 PDF 重新排版生成的精美 HTML 阅读页（新窗口打开用）。

    文件由 etl/build_guide_html.py 预生成到 static/guides/{id}.html；
    扫描件则内嵌原始 PDF 以保证内容准确。
    """
    # 校验 id 在白名单内，避免任意路径
    valid = any(it["id"] == gid for g in _GROUPS for it in g["items"])
    if not valid:
        raise HTTPException(404, f"未知文件 id：{gid}")
    path = os.path.join(_HTML_DIR, f"{gid}.html")
    if not os.path.exists(path):
        raise HTTPException(404, "该指南的排版页面尚未生成，请先运行 etl/build_guide_html.py")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())
