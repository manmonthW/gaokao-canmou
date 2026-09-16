"""AI 参谋助手（Agentic）后端包。

邀请制内测：总开关 AGENT_ENABLED 默认关闭；模型只依赖 LangChain BaseChatModel，
由 llm.make_model 依配置切换提供方；所有工具只读、结论可溯源（evidence 证据账本）。
"""
