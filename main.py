"""
arXiv 论文检索与订阅推送插件。

功能：
- /paper <关键词/作者/分类> [数量]：检索 arXiv 论文
- /paper sub <查询>：订阅每日推送
- /paper unsub <查询>：取消订阅
- /paper list：查看订阅
- /paper clear：清空订阅

arXiv API 免费且无需任何 Key，用户安装即用。
"""

from __future__ import annotations

import asyncio
import datetime
import re
import traceback

import arxiv
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register

HELP_TEXT = """📄 arXiv 论文检索插件
用法：
  /paper <关键词/作者/分类> [数量]  检索论文，例如 /paper attention is all you need 5
  /paper sub <查询>                 订阅，每天定时推送最新论文
  /paper latest <查询>              按最新发表时间排序检索
  /paper recent <查询>              既相关又较新的检索
  /paper zh <查询>                  检索并翻译标题（用 LLM）
  /paper cats                      查看常用分类代码
  /paper unsub <查询>               取消订阅
  /paper list                       查看我的订阅
  /paper clear                      清空我的订阅

查询技巧：
  作者   au:Yoshua Bengio
  分类   cat:cs.AI 或 cat:cs.CL
  关键词 transformer / all:transformer
"""


CATEGORIES = [
    ("计算机科学 cs", [
        ("cs.AI", "人工智能"),
        ("cs.CL", "计算语言学 / NLP / 大语言模型"),
        ("cs.LG", "机器学习"),
        ("cs.CV", "计算机视觉"),
        ("cs.NE", "神经网络与进化计算"),
        ("cs.IR", "信息检索"),
        ("cs.SE", "软件工程"),
        ("cs.CR", "密码学与安全"),
        ("cs.DS", "数据结构与算法"),
        ("cs.DB", "数据库"),
        ("cs.DC", "分布式与并行计算"),
        ("cs.HC", "人机交互"),
        ("cs.RO", "机器人"),
        ("cs.CY", "计算机与社会"),
    ]),
    ("统计学 stat", [
        ("stat.ML", "统计机器学习"),
        ("stat.AP", "统计学应用（含生物统计）"),
    ]),
    ("电子工程 eess", [
        ("eess.AS", "音频与语音处理"),
        ("eess.IV", "图像与视频处理"),
    ]),
    ("数学 math", [
        ("math.OC", "优化与控制"),
    ]),
    ("定量生物学 q-bio", [
        ("q-bio.GN", "基因组学"),
        ("q-bio.BM", "生物分子"),
        ("q-bio.CB", "细胞行为"),
        ("q-bio.MN", "分子网络"),
        ("q-bio.NC", "神经元与认知"),
        ("q-bio.PE", "种群与进化"),
        ("q-bio.QM", "定量方法"),
        ("q-bio.SC", "亚细胞过程"),
        ("q-bio.TO", "组织与器官"),
        ("q-bio.OT", "其他定量生物学"),
    ]),
    ("物理 physics", [
        ("physics.bio-ph", "生物物理"),
        ("physics.med-ph", "医学物理"),
    ]),
]

def _now_utc_iso() -> str:
    """当前 UTC 时间，ISO 格式字符串。"""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _parse_ts(value: str | None) -> datetime.datetime:
    """把存储的时间字符串解析为带时区的 datetime，失败时返回最早时间。"""
    if not value:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    try:
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


@register(
    "astrbot_plugin_arxiv",
    "redflood111",
    "按关键词/作者/分类检索 arXiv 论文，并支持订阅后每日定时推送最新论文。",
    "v1.1.0",
)
class ArxivPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.client = arxiv.Client()
        self.max_results = int(config.get("max_results", 5))
        self.push_enabled = bool(config.get("push_enabled", True))
        self.push_time = str(config.get("push_time", "08:00"))
        self._push_task: asyncio.Task | None = None

        if self.push_enabled:
            self._push_task = asyncio.create_task(self._push_loop())

        logger.info("arXiv 论文检索插件已加载")

    async def terminate(self) -> None:
        if self._push_task:
            self._push_task.cancel()
        logger.info("arXiv 论文检索插件已卸载")

    # ---------- 指令 ----------

    @filter.command("paper", alias={"arxiv"})
    async def paper(self, event: AstrMessageEvent):
        try:
            arg = self._strip_command(event.message_str)
            if not arg:
                yield event.plain_result(HELP_TEXT)
                return

            cmd, rest = self._split_cmd(arg)
            if cmd in ("help", "帮助", "h", "?"):
                yield event.plain_result(HELP_TEXT)
            elif cmd in ("sub", "subscribe", "订阅"):
                yield event.plain_result(await self._subscribe(event, rest))
            elif cmd in ("unsub", "unsubscribe", "取消订阅", "退订"):
                yield event.plain_result(await self._unsubscribe(event, rest))
            elif cmd in ("list", "ls", "列表", "订阅列表"):
                yield event.plain_result(await self._list_subs(event))
            elif cmd in ("clear", "清空"):
                yield event.plain_result(await self._clear_subs(event))
            elif cmd in ("latest", "new", "最新"):
                query, count = self._parse_search(rest)
                yield event.plain_result(await self._search_latest(query, count))
            elif cmd in ("recent", "近期", "相关新"):
                query, count = self._parse_search(rest)
                yield event.plain_result(await self._search_recent(query, count))
            elif cmd in ("zh", "中文", "翻译"):
                query, count = self._parse_search(rest)
                yield event.plain_result(await self._search_zh(event, query, count))
            elif cmd in ("cats", "categories", "分类"):
                yield event.plain_result(await self._list_categories())
            else:
                query, count = self._parse_search(arg)
                yield event.plain_result(await self._search(query, count))
        except Exception as e:
            logger.error(f"[arxiv] 处理指令失败: {e}\n{traceback.format_exc()}")
            yield event.plain_result(f"出错了：{e}")

    # ---------- 工具方法 ----------

    @staticmethod
    def _strip_command(text: str) -> str:
        """去掉消息开头的指令名（如 paper / arxiv），返回剩余参数。"""
        text = text.strip()
        parts = text.split(None, 1)
        if not parts:
            return ""
        return parts[1].strip() if len(parts) > 1 else ""

    @staticmethod
    def _split_cmd(arg: str) -> tuple[str, str]:
        """把参数拆成（子命令, 剩余参数）。"""
        parts = arg.split(None, 1)
        cmd = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""
        return cmd, rest

    def _parse_search(self, arg: str) -> tuple[str, int]:
        """从参数中解析出（查询词, 数量）。末尾的数字作为返回数量。"""
        tokens = arg.split()
        count = self.max_results
        if tokens and tokens[-1].isdigit():
            count = int(tokens[-1])
            tokens = tokens[:-1]
        query = " ".join(tokens).strip()
        return query, min(max(count, 1), 20)

    async def _search(self, query: str, count: int) -> str:
        if not query:
            return HELP_TEXT
        search = arxiv.Search(
            query=query,
            max_results=count,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = list(self.client.results(search))
        if not results:
            return f"没有找到与「{query}」相关的论文。"
        return self._format_results(f"检索「{query}」", results)

    async def _search_latest(self, query: str, count: int) -> str:
        if not query:
            return "用法：/paper latest <关键词>，按最新发表时间排序检索。"
        search = arxiv.Search(
            query=query,
            max_results=count,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        results = list(self.client.results(search))
        if not results:
            return f"没有找到与「{query}」相关的论文。"
        return self._format_results(f"最新检索「{query}」", results)

    async def _search_recent(self, query: str, count: int) -> str:
        if not query:
            return "用法：/paper recent <关键词>，优先返回既相关又较新的论文。"
        pool = max(count * 6, 30)
        search = arxiv.Search(
            query=query,
            max_results=pool,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = list(self.client.results(search))
        if not results:
            return f"没有找到与「{query}」相关的论文。"
        min_dt = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        results = sorted(
            results,
            key=lambda r: r.published or min_dt,
            reverse=True,
        )
        results = results[:count]
        return self._format_results(f"相关且较新检索「{query}」", results)

    async def _search_zh(self, event: AstrMessageEvent, query: str, count: int) -> str:
        if not query:
            return "用法：/paper zh <关键词>，检索并翻译论文标题。"

        search = arxiv.Search(
            query=query,
            max_results=count,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = list(self.client.results(search))
        if not results:
            return f"没有找到与「{query}」相关的论文。"

        provider = self.context.get_using_provider(event.unified_msg_origin)
        if provider is None:
            return (
                "⚠️ 当前未配置对话模型（LLM），无法翻译。返回英文结果：\n"
                + self._format_results(f"检索「{query}」", results)
            )

        try:
            provider_id = provider.meta().id
            titles = [r.title for r in results]
            numbered = "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1))
            resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=f"请把以下论文标题翻译成简洁准确的中文，每行一个，保持编号：\n{numbered}",
                system_prompt="你是专业的学术论文翻译助手，擅长翻译论文标题。只输出翻译结果，每行一个，不要添加任何解释或额外文字。",
            )
            translated_text = resp.completion_text or ""
            translated_titles = self._parse_translated_titles(
                translated_text, len(results)
            )
            if not any(t for t in translated_titles):
                raise ValueError("翻译结果为空")
        except Exception as e:
            logger.error(f"[arxiv] 翻译标题失败: {e}")
            return (
                "⚠️ 翻译失败，返回英文结果：\n"
                + self._format_results(f"检索「{query}」", results)
            )

        return self._format_results_zh(
            f"检索「{query}」（标题已翻译）", results, translated_titles
        )

    async def _list_categories(self) -> str:
        lines = ["📚 arXiv 常用分类代码", ""]
        for group, cats in CATEGORIES:
            lines.append(f"【{group}】")
            for code, name in cats:
                lines.append(f"  {code:<10} {name}")
            lines.append("")
        lines.append("用法示例：/paper cat:cs.CL 10")
        lines.append("完整分类列表：https://arxiv.org/category_taxonomy")
        return "\n".join(lines)

    @staticmethod
    def _parse_translated_titles(text: str, count: int) -> list[str]:
        titles = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^\d+[\.、\)）:：]\s*", "", line).strip()
            if line:
                titles.append(line)
        while len(titles) < count:
            titles.append("")
        return titles[:count]

    @staticmethod
    def _format_results_zh(title: str, results: list, translated_titles: list[str]) -> str:
        lines = [f"📄 {title}（{len(results)} 条）"]
        for i, r in enumerate(results, 1):
            authors = ", ".join(a.name for a in r.authors[:3])
            if len(r.authors) > 3:
                authors += " 等"
            pub = r.published.strftime("%Y-%m-%d") if r.published else "未知"
            cn = translated_titles[i - 1] if i - 1 < len(translated_titles) else ""
            cn = cn.strip() if cn else ""
            if cn:
                lines.append(
                    f"\n{i}. {cn}\n"
                    f"   原标题: {r.title}\n"
                    f"   作者: {authors}\n"
                    f"   发表: {pub}\n"
                    f"   {r.entry_id}"
                )
            else:
                lines.append(
                    f"\n{i}. {r.title}\n"
                    f"   作者: {authors}\n"
                    f"   发表: {pub}\n"
                    f"   {r.entry_id}"
                )
        return "\n".join(lines)

    @staticmethod
    def _format_results(title: str, results: list) -> str:
        lines = [f"📄 {title}（{len(results)} 条）"]
        for i, r in enumerate(results, 1):
            authors = ", ".join(a.name for a in r.authors[:3])
            if len(r.authors) > 3:
                authors += " 等"
            pub = r.published.strftime("%Y-%m-%d") if r.published else "未知"
            lines.append(
                f"\n{i}. {r.title}\n"
                f"   作者: {authors}\n"
                f"   发表: {pub}\n"
                f"   {r.entry_id}"
            )
        return "\n".join(lines)

    # ---------- 订阅 ----------

    async def _load_subs(self) -> list:
        data = await self.get_kv_data("subscriptions", [])
        return data if isinstance(data, list) else []

    async def _save_subs(self, subs: list) -> None:
        await self.put_kv_data("subscriptions", subs)

    async def _subscribe(self, event: AstrMessageEvent, query: str) -> str:
        query = query.strip()
        if not query:
            return "用法：/paper sub <关键词/作者/分类>，例如 /paper sub cat:cs.CL"

        session = event.unified_msg_origin
        subs = await self._load_subs()
        for s in subs:
            if s.get("session") == session and s.get("query", "").lower() == query.lower():
                return f"你已经订阅过「{query}」了。"

        subs.append(
            {
                "query": query,
                "session": session,
                "last_pushed": _now_utc_iso(),
            }
        )
        await self._save_subs(subs)

        preview = await self._search_latest(query, self.max_results)
        return f"✅ 已订阅「{query}」，每天 {self.push_time} 推送最新论文。当前最新：\n{preview}"

    async def _unsubscribe(self, event: AstrMessageEvent, query: str) -> str:
        query = query.strip()
        if not query:
            return "用法：/paper unsub <查询>。清空全部订阅请用 /paper clear。"
        session = event.unified_msg_origin
        subs = await self._load_subs()
        new_subs = [
            s
            for s in subs
            if not (
                s.get("session") == session
                and s.get("query", "").lower() == query.lower()
            )
        ]
        if len(new_subs) == len(subs):
            return f"没有找到订阅「{query}」。用 /paper list 查看订阅列表。"
        await self._save_subs(new_subs)
        return f"已取消订阅「{query}」。"

    async def _list_subs(self, event: AstrMessageEvent) -> str:
        session = event.unified_msg_origin
        subs = [s for s in await self._load_subs() if s.get("session") == session]
        if not subs:
            return "你还没有订阅任何内容。用法：/paper sub <关键词/作者/分类>"
        lines = ["你的订阅："]
        for i, s in enumerate(subs, 1):
            lines.append(f"{i}. {s.get('query')}")
        return "\n".join(lines)

    async def _clear_subs(self, event: AstrMessageEvent) -> str:
        session = event.unified_msg_origin
        subs = await self._load_subs()
        new_subs = [s for s in subs if s.get("session") != session]
        removed = len(subs) - len(new_subs)
        await self._save_subs(new_subs)
        return f"已清空 {removed} 条订阅。"

    # ---------- 定时推送 ----------

    def _seconds_until_next_push(self) -> float:
        now = datetime.datetime.now()
        try:
            hh, mm = self.push_time.split(":")
            next_push = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except Exception:
            next_push = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if next_push <= now:
            next_push += datetime.timedelta(days=1)
        return (next_push - now).total_seconds()

    async def _push_loop(self) -> None:
        while True:
            try:
                seconds = self._seconds_until_next_push()
                logger.info(f"[arxiv] 下次推送将在 {seconds / 3600:.2f} 小时后")
                await asyncio.sleep(seconds)
                await self._do_daily_push()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error(f"[arxiv] 定时任务出错: {traceback.format_exc()}")
                await asyncio.sleep(300)

    async def _do_daily_push(self) -> None:
        subs = await self._load_subs()
        if not subs:
            return

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        pushed_any = False

        for s in subs:
            query = s.get("query", "")
            session = s.get("session", "")
            if not query or not session:
                continue
            try:
                last = _parse_ts(s.get("last_pushed"))
                search = arxiv.Search(
                    query=query,
                    max_results=self.max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                )
                results = list(self.client.results(search))
                new_papers = [r for r in results if r.published and r.published > last]
                if new_papers:
                    msg = self._format_results(f"订阅「{query}」新论文", new_papers)
                    chain = MessageChain().message(msg)
                    await self.context.send_message(session, chain)
                    s["last_pushed"] = now_utc.isoformat()
                    pushed_any = True
                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"[arxiv] 推送订阅「{query}」失败: {e}")

        if pushed_any:
            await self._save_subs(subs)
