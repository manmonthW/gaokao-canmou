"""LangGraph 图层（§6）：主图 + 子图A（find_options）/ 子图C（explain）。

主图确定性编排：guard → load_context → route_intent → {子流程} → synthesize → verify
→ deliver / repair / fallback。子图只负责取证（写 ledger），不写最终结构化答案；
结构化答案统一由 synthesize 产出、verify 把关、程序追加免责声明。
"""
from app.agent.graphs.advisor import build_advisor_graph

__all__ = ["build_advisor_graph"]
