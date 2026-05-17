from datetime import UTC, datetime

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from app.modules import sessions as sessions_repo


def _relative_time(when: datetime) -> str:
    now = datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    delta = now - when
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    return f"{days // 365}y ago"


class SessionsScreen(ModalScreen[str | None]):
    """Modal picker that lists all known sessions."""

    DEFAULT_CSS = """
    SessionsScreen {
        align: center middle;
        background: #000000 80%;
    }

    SessionsScreen #dialog {
        width: 90;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        background: #050505;
        border: round #ff8a1a;
    }

    SessionsScreen .title {
        height: 1;
        text-style: bold;
        color: #ff8a1a;
    }

    SessionsScreen .hint {
        height: 1;
        color: #8f8f8f;
        margin-top: 1;
    }

    SessionsScreen OptionList {
        height: auto;
        max-height: 20;
        margin-top: 1;
        background: #050505;
        border: round #1a1a1a;
        padding: 0 1;
    }

    SessionsScreen OptionList > .option-list--option-highlighted {
        background: #1a1208;
        color: #ff8a1a;
    }

    SessionsScreen .empty {
        height: auto;
        color: #8f8f8f;
        margin-top: 1;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Sessions", classes="title")
            sessions = sessions_repo.list_sessions()
            if not sessions:
                yield Static("(no saved sessions yet)", classes="empty")
            else:
                option_list = OptionList(id="sessions-list")
                for s in sessions:
                    title = s.title if len(s.title) <= 60 else s.title[:57] + "..."
                    label = f"{title}  ·  {s.project_path}  ·  {_relative_time(s.updated_at)}"
                    option_list.add_option(Option(label, id=s.id))
                yield option_list
            yield Static("↑/↓ navigate · enter select · esc cancel", classes="hint")

    def on_mount(self) -> None:
        try:
            self.query_one(OptionList).focus()
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.dismiss(None)
