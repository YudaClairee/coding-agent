import re

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.content import Content, Span
from textual.css.query import NoMatches
from textual.style import Style
from textual.widgets import Markdown, Static
from textual.widgets._markdown import MarkdownFence


def _strip_background_style(style: str | Style) -> str | Style | None:
    """Keep syntax foreground styles while removing background fills."""
    if isinstance(style, str):
        cleaned = re.sub(r"\s+on\s+\S+", "", style).strip()
        return cleaned or None

    return Style(
        foreground=style.foreground,
        background=None,
        bold=style.bold,
        dim=style.dim,
        italic=style.italic,
        underline=style.underline,
        underline2=style.underline2,
        reverse=style.reverse,
        strike=style.strike,
        blink=style.blink,
        link=style.link,
        _meta=style.meta if isinstance(style.meta, bytes) else None,
        auto_color=style.auto_color,
    )


def _strip_backgrounds(content: Content) -> Content:
    spans = [Span(span.start, span.end, _strip_background_style(span.style) or "") for span in content.spans]
    return Content(content.plain, spans, cell_length=content.cell_length)


class ChatMarkdownFence(MarkdownFence):
    """Fence renderer that preserves syntax colors without background blocks."""

    @classmethod
    def highlight(cls, code: str, language: str) -> Content:
        return _strip_backgrounds(super().highlight(code, language))


class ChatMarkdown(Markdown):
    """Markdown widget tuned for compact chat rendering."""

    BLOCKS = {
        **Markdown.BLOCKS,
        "fence": ChatMarkdownFence,
        "code_block": ChatMarkdownFence,
    }


class MessageBubble(Vertical):
    """A single chat message.

    Assistant messages are composed of interleaved blocks: Markdown widgets for
    content (debounced updates) and plain Static widgets for tool calls.
    """

    DEFAULT_CSS = """
    MessageBubble {
        height: auto;
    }

    MessageBubble > .label {
        height: 1;
    }

    MessageBubble Markdown {
        background: transparent;
        margin: 0;
        padding: 0;
    }

    MessageBubble Markdown > * {
        background: transparent;
    }

    MessageBubble MarkdownParagraph,
    MessageBubble MarkdownBulletList,
    MessageBubble MarkdownOrderedList,
    MessageBubble MarkdownTable,
    MessageBubble MarkdownFence,
    MessageBubble MarkdownBlockQuote,
    MessageBubble MarkdownHeader {
        margin: 0;
    }

    MessageBubble MarkdownListItem {
        margin-right: 0;
    }

    MessageBubble .tool-call {
        color: #8f8f8f;
        text-style: italic;
        height: auto;
        padding: 0;
        margin: 0;
    }

    MessageBubble Markdown.reasoning,
    MessageBubble Markdown.reasoning > * {
        color: #8f8f8f;
        text-style: italic;
    }

    MessageBubble Markdown.reasoning {
        margin: 0;
    }
    """

    FLUSH_INTERVAL = 0.05  # 50ms debounce for markdown re-render

    def __init__(self, role: str, content: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.role = role
        self._text = content  # buffer for non-assistant bodies
        self._md_text = ""  # buffer for the *active* markdown block
        self._current_md: Markdown | None = None
        self._reasoning_text = ""  # buffer for the *active* reasoning block
        self._current_reasoning: Markdown | None = None
        self._pending_flush = False
        self._ready = False
        self._pending_ops: list[tuple[str, str]] = []
        if role == "assistant" and content:
            self._pending_ops.append(("content", content))

    def compose(self) -> ComposeResult:
        if self.role == "user":
            label = Text("❯ You", style="bold #ff9f43")
        elif self.role == "assistant":
            label = Text("◆ Agent", style="bold #ff8a1a")
        else:
            label = Text("⚙ System", style="bold #ffb15c")

        yield Static(label, classes="label")
        if self.role != "assistant":
            yield Static(self._render_plain(), classes="body")

    def on_mount(self) -> None:
        self._ready = True
        for op, text in self._pending_ops:
            if op == "content":
                self._append_assistant_content(text)
            elif op == "reasoning":
                self._append_reasoning(text)
            else:
                self._mount_tool_call(text)
        self._pending_ops.clear()

    def _render_plain(self) -> Text:
        if self.role == "user":
            return Text(self._text, style="#f5f5f5")
        return Text(self._text, style="#a3a3a3")

    def append_text(self, text: str) -> None:
        if self.role != "assistant":
            self._text += text
            try:
                self.query_one(".body", Static).update(self._render_plain())
            except NoMatches:
                pass
            return
        if not self._ready:
            self._pending_ops.append(("content", text))
            return
        self._append_assistant_content(text)

    def append_tool_call(self, text: str) -> None:
        if self.role != "assistant":
            self.append_text(f"⚙ {text}\n")
            return
        if not self._ready:
            self._pending_ops.append(("tool", text))
            return
        self._mount_tool_call(text)

    def append_reasoning(self, text: str) -> None:
        if self.role != "assistant":
            return
        if not self._ready:
            self._pending_ops.append(("reasoning", text))
            return
        self._append_reasoning(text)

    def _append_assistant_content(self, text: str) -> None:
        if self._current_md is None:
            # Starting a new content block closes any active reasoning block.
            # Flush first so the last reasoning delta is visible.
            self.flush_now()
            self._current_reasoning = None
            self._reasoning_text = ""
            md = ChatMarkdown("")
            self.mount(md)
            self._current_md = md
            self._md_text = ""
        self._md_text += text
        self._schedule_flush()

    def _append_reasoning(self, text: str) -> None:
        if self._current_reasoning is None:
            # Flush any pending markdown so reasoning renders in the correct visual order
            self.flush_now()
            # Reset the active markdown so subsequent content starts a fresh block
            self._current_md = None
            self._md_text = ""
            self._reasoning_text = "**THINKING:** "
            md = ChatMarkdown("", classes="reasoning")
            self.mount(md)
            self._current_reasoning = md
        self._reasoning_text += text
        self._schedule_flush()

    def _mount_tool_call(self, text: str) -> None:
        # Flush any pending markdown so the tool call renders in the correct visual order
        self.flush_now()
        # Reset the active markdown and reasoning so subsequent content starts fresh blocks
        self._current_md = None
        self._md_text = ""
        self._current_reasoning = None
        self._reasoning_text = ""
        self.mount(Static(Text(f"⚙ {text}", style="italic #8f8f8f"), classes="tool-call"))

    def _schedule_flush(self) -> None:
        if self._pending_flush:
            return
        self._pending_flush = True
        self.set_timer(self.FLUSH_INTERVAL, self._flush)

    def _flush(self) -> None:
        self._pending_flush = False
        if self._current_md is not None:
            self._current_md.update(self._md_text)
        if self._current_reasoning is not None:
            self._current_reasoning.update(self._reasoning_text)

    def flush_now(self) -> None:
        """Force-render any pending markdown immediately (e.g. at end of stream)."""
        self._pending_flush = False
        if self._current_md is not None:
            self._current_md.update(self._md_text)
        if self._current_reasoning is not None:
            self._current_reasoning.update(self._reasoning_text)


class ChatArea(VerticalScroll):
    """Scrollable chat message area."""

    DEFAULT_CSS = """
    ChatArea {
        height: 1fr;
        padding: 1 2;
        background: #000000;
    }

    ChatArea MessageBubble {
        margin: 0 0 1 0;
        padding: 0 1;
    }
    """

    def add_message(self, role: str, content: str) -> MessageBubble:
        bubble = MessageBubble(role, content)
        self.mount(bubble)
        self.scroll_end(animate=False)
        return bubble
