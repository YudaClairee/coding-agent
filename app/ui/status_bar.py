import os

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Horizontal):
    """Bottom status bar showing model/token info."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        background: #050505;
        border-top: solid #1a1a1a;
        padding: 0 1;
    }

    StatusBar .status-left {
        width: 1fr;
        content-align: left middle;
        color: #8f8f8f;
    }

    StatusBar .status-right {
        width: auto;
        content-align: right middle;
        color: #8f8f8f;
    }
    """

    messages_count = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static("", classes="status-left", id="status-left")
        yield Static("", classes="status-right", id="status-right")

    def update_status(self, messages: int = 0, tokens: int = 0) -> None:
        self.messages_count = messages
        cwd = os.path.basename(os.getcwd())
        left = f" coding-agent  ·  {cwd}"
        right = f"{messages} messages  ·  {tokens} tokens "
        self.query_one("#status-left", Static).update(left)
        self.query_one("#status-right", Static).update(right)
