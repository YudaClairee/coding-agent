from rich.text import Text
from textual.widgets import Static

BRAILLE_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class BrailleSpinner(Static):
    """Animated braille spinner."""

    DEFAULT_CSS = """
    BrailleSpinner {
        height: 1;
        margin: 0 0 1 0;
        padding: 0 1;
        color: #ff8a1a;
    }
    """

    _frame: int = 0

    def on_mount(self) -> None:
        self.set_interval(0.08, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(BRAILLE_FRAMES)
        self.refresh()

    def render(self):
        return Text(f"{BRAILLE_FRAMES[self._frame]} Working...", style="bold #ff8a1a")
