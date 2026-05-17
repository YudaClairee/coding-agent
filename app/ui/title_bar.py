from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from app.core.settings import settings


class TitleBar(Horizontal):
    """Top title bar."""

    DEFAULT_CSS = """
    TitleBar {
        height: 1;
        dock: top;
        background: #050505;
        border-bottom: solid #1a1a1a;
        padding: 0 1;
    }

    TitleBar .title-left {
        width: 1fr;
        content-align: left middle;
        color: #ff8a1a;
        text-style: bold;
    }

    TitleBar .title-right {
        width: auto;
        content-align: right middle;
        color: #8f8f8f;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(" Devscale Coding Agent - Demo AI Enabled Python Web Dev", classes="title-left")
        yield Static(f"{settings.llm_model} ", classes="title-right")
