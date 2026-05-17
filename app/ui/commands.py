from dataclasses import dataclass


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str


COMMANDS: list[SlashCommand] = [
    SlashCommand("help", "Show available commands"),
    SlashCommand("clear", "Clear the chat"),
    SlashCommand("new", "Start a new session"),
    SlashCommand("session", "Switch to another session"),
    SlashCommand("model", "Show current model info"),
    SlashCommand("quit", "Exit the application"),
]


def filter_commands(query: str) -> list[SlashCommand]:
    """Return commands whose name starts with `query` (without the leading `/`)."""
    q = query.lstrip("/").lower()
    if not q:
        return list(COMMANDS)
    return [c for c in COMMANDS if c.name.startswith(q)]
