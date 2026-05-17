import os

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class NewSessionScreen(ModalScreen[str | None]):
    """Modal that prompts the user for a project path for a new session."""

    DEFAULT_CSS = """
    NewSessionScreen {
        align: center middle;
        background: #000000 80%;
    }

    NewSessionScreen #dialog {
        width: 70;
        height: auto;
        padding: 1 2;
        background: #050505;
        border: round #ff8a1a;
    }

    NewSessionScreen .title {
        height: 1;
        text-style: bold;
        color: #ff8a1a;
    }

    NewSessionScreen .hint {
        height: 1;
        color: #8f8f8f;
        margin-top: 1;
    }

    NewSessionScreen Input {
        margin-top: 1;
        background: #0a0a0a;
        color: #f5f5f5;
        border: tall #1a1a1a;
    }

    NewSessionScreen Input:focus {
        border: tall #ff8a1a;
    }

    NewSessionScreen .error {
        height: auto;
        color: #ffb15c;
        margin-top: 1;
    }
    """

    def __init__(self, default_path: str | None = None) -> None:
        super().__init__()
        self._default_path = default_path or os.getcwd()

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("New session", classes="title")
            yield Input(
                value=self._default_path,
                placeholder="Project path",
                id="path-input",
            )
            yield Static("", id="error", classes="error")
            yield Static("enter accept · esc cancel", classes="hint")

    def on_mount(self) -> None:
        inp = self.query_one("#path-input", Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        if not raw:
            self._show_error("Path cannot be empty")
            return
        path = os.path.abspath(os.path.expanduser(raw))
        if not os.path.exists(path):
            self._show_error(f"Path does not exist: {path}")
            return
        if not os.path.isdir(path):
            self._show_error(f"Not a directory: {path}")
            return
        self.dismiss(path)

    def _show_error(self, message: str) -> None:
        self.query_one("#error", Static).update(message)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)
