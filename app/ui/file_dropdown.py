import os

from textual.widgets import OptionList
from textual.widgets.option_list import Option

from app.ui.file_mentions import FileEntry, filter_files, list_repo_files


class FileMentionDropdown(OptionList):
    """Dropdown showing filtered file mentions above the input."""

    DEFAULT_CSS = """
    FileMentionDropdown {
        height: auto;
        max-height: 8;
        background: #050505;
        border: round #1a1a1a;
        padding: 0 1;
        margin: 0 0 0 0;
    }

    FileMentionDropdown > .option-list--option-highlighted {
        background: #1a1208;
        color: #ff8a1a;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cache: list[FileEntry] | None = None
        self._entries: list[FileEntry] = []
        self.can_focus = False
        self.display = False

    def update_for(self, query: str) -> None:
        if self._cache is None:
            self._cache = list_repo_files(os.getcwd())
        self._entries = filter_files(query, self._cache)
        self.clear_options()
        if not self._entries:
            self.display = False
            return
        for entry in self._entries:
            self.add_option(Option(entry.relpath, id=entry.relpath))
        self.display = True
        self.highlighted = 0

    def selected_entry(self) -> FileEntry | None:
        if not self._entries or self.highlighted is None:
            return None
        try:
            return self._entries[self.highlighted]
        except IndexError:
            return None

    def move_cursor(self, delta: int) -> None:
        if not self._entries:
            return
        n = len(self._entries)
        cur = self.highlighted if self.highlighted is not None else 0
        self.highlighted = (cur + delta) % n

    def close(self) -> None:
        self.display = False
        self._cache = None
