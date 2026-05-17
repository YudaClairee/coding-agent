from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from app.ui.commands import SlashCommand, filter_commands
from app.ui.file_dropdown import FileMentionDropdown
from app.ui.file_mentions import find_mention_token
from app.ui.spinner import BrailleSpinner


class CommandDropdown(OptionList):
    """Dropdown showing filtered slash commands above the input."""

    DEFAULT_CSS = """
    CommandDropdown {
        height: auto;
        max-height: 8;
        background: #050505;
        border: round #1a1a1a;
        padding: 0 1;
        margin: 0 0 0 0;
    }

    CommandDropdown > .option-list--option-highlighted {
        background: #1a1208;
        color: #ff8a1a;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._commands: list[SlashCommand] = []
        self.can_focus = False
        self.display = False

    def update_for(self, query: str) -> None:
        self._commands = filter_commands(query)
        self.clear_options()
        if not self._commands:
            self.display = False
            return
        width = max(len(c.name) for c in self._commands) + 1
        for cmd in self._commands:
            label = f"/{cmd.name:<{width}}  {cmd.description}"
            self.add_option(Option(label, id=cmd.name))
        self.display = True
        self.highlighted = 0

    def selected_command(self) -> SlashCommand | None:
        if not self._commands or self.highlighted is None:
            return None
        try:
            return self._commands[self.highlighted]
        except IndexError:
            return None

    def move_cursor(self, delta: int) -> None:
        if not self._commands:
            return
        n = len(self._commands)
        cur = self.highlighted if self.highlighted is not None else 0
        self.highlighted = (cur + delta) % n


class PromptTextInput(Input):
    """Input that forwards navigation keys to the active dropdown when visible."""

    def __init__(
        self,
        dropdown: CommandDropdown,
        file_dropdown: FileMentionDropdown,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._dropdown = dropdown
        self._file_dropdown = file_dropdown

    def _complete_with_selection(self) -> bool:
        cmd = self._dropdown.selected_command()
        if cmd is None:
            return False
        self.value = f"/{cmd.name}"
        self._dropdown.display = False
        self.post_message(self.Submitted(self, self.value))
        return True

    def _complete_with_file(self) -> bool:
        entry = self._file_dropdown.selected_entry()
        if entry is None:
            return False
        token = find_mention_token(self.value, self.cursor_position)
        if token is None:
            return False
        at_idx, end_idx, _ = token
        replacement = f"@{entry.relpath} "
        self.value = self.value[:at_idx] + replacement + self.value[end_idx:]
        self.cursor_position = at_idx + len(replacement)
        self._file_dropdown.close()
        return True

    async def _on_key(self, event: events.Key) -> None:
        if self._file_dropdown.display:
            key = event.key
            if key == "up":
                self._file_dropdown.move_cursor(-1)
                event.prevent_default()
                event.stop()
                return
            if key == "down":
                self._file_dropdown.move_cursor(1)
                event.prevent_default()
                event.stop()
                return
            if key in ("tab", "enter"):
                if self._complete_with_file():
                    event.prevent_default()
                    event.stop()
                return
            if key == "escape":
                self._file_dropdown.close()
                event.prevent_default()
                event.stop()
                return
            return

        if not self._dropdown.display:
            return
        key = event.key
        if key == "up":
            self._dropdown.move_cursor(-1)
            event.prevent_default()
            event.stop()
        elif key == "down":
            self._dropdown.move_cursor(1)
            event.prevent_default()
            event.stop()
        elif key in ("tab", "enter"):
            if self._complete_with_selection():
                event.prevent_default()
                event.stop()
        elif key == "escape":
            self._dropdown.display = False
            event.prevent_default()
            event.stop()


class PromptInput(Vertical):
    """The input area at the bottom."""

    DEFAULT_CSS = """
    PromptInput {
        height: auto;
        max-height: 14;
        dock: bottom;
        padding: 0 1;
        background: #000000;
    }

    PromptInput Static.hint {
        height: 1;
        color: #8f8f8f;
        padding: 0 1;
        text-align: right;
    }

    PromptInput Input {
        margin: 0 0 0 0;
        border: tall #1a1a1a;
        background: #050505;
        color: #f5f5f5;
        padding: 0 1;
    }

    PromptInput Input:focus {
        border: tall #ff8a1a;
    }
    """

    def compose(self) -> ComposeResult:
        dropdown = CommandDropdown(id="command-dropdown")
        file_dropdown = FileMentionDropdown(id="file-dropdown")
        yield dropdown
        yield file_dropdown
        yield PromptTextInput(
            dropdown,
            file_dropdown,
            placeholder="Ask anything...  (@ for files, / for commands)",
            id="prompt-input",
        )
        yield Static(
            "enter send · @ files · / commands · ctrl+c quit", classes="hint"
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "prompt-input":
            return
        dropdown = self.query_one(CommandDropdown)
        file_dropdown = self.query_one(FileMentionDropdown)
        value = event.value
        if value.startswith("/") and " " not in value:
            dropdown.update_for(value)
            if file_dropdown.display:
                file_dropdown.close()
            return
        dropdown.display = False
        cursor = getattr(event.input, "cursor_position", len(value))
        token = find_mention_token(value, cursor)
        if token is None:
            if file_dropdown.display:
                file_dropdown.close()
            return
        _, _, query = token
        file_dropdown.update_for(query)

    def show_loading(self) -> None:
        spinner = BrailleSpinner(id="loading")
        self.mount(spinner, before=self.query_one("#prompt-input"))

    async def hide_loading(self) -> None:
        try:
            loader = self.query_one("#loading", BrailleSpinner)
            await loader.remove()
        except Exception:
            pass
