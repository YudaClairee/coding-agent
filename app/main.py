import asyncio
import os
from uuid import uuid4

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input

from app.agents.main import create_agent
from app.agents.streaming import StreamEvent, stream_agent
from app.core.settings import settings
from app.modules import sessions as sessions_repo
from app.ui import ChatArea, PromptInput, TitleBar
from app.ui.commands import COMMANDS
from app.ui.file_mentions import expand_mentions
from app.ui.new_session_screen import NewSessionScreen
from app.ui.sessions_screen import SessionsScreen


def _truncate_title(text: str, limit: int = 80) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


class CodingAgentApp(App):
    TITLE = "Coding Agent"
    CSS = """
    Screen {
        background: #000000;
        color: #f5f5f5;
        scrollbar-size-vertical: 1;
        scrollbar-color: #ff8a1a;
        scrollbar-color-hover: #ff9f43;
        scrollbar-color-active: #ffb15c;
        scrollbar-background: #050505;
        scrollbar-background-hover: #0a0a0a;
        scrollbar-background-active: #0a0a0a;
        scrollbar-corner-color: #050505;
    }

    #main-container {
        height: 1fr;
    }

    #welcome {
        margin: 2 4;
        padding: 1 2;
        color: #8f8f8f;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear", "Clear", show=False),
    ]

    messages: list = []

    def __init__(self) -> None:
        super().__init__()
        self.agent = None
        self.current_session_id: str | None = None
        self.current_project_path: str | None = None
        self.current_session_persisted: bool = False

    def compose(self) -> ComposeResult:
        yield TitleBar()
        yield ChatArea(id="chat-area")
        yield PromptInput()

    def on_mount(self) -> None:
        chat = self.query_one("#chat-area", ChatArea)
        chat.add_message(
            "system",
            "Welcome to Coding Agent. Choose a project path to begin.",
        )
        self.query_one("#prompt-input", Input).focus()
        self.push_screen(NewSessionScreen(default_path=os.getcwd()), self._on_initial_session)

    def _on_initial_session(self, path: str | None) -> None:
        if path is None:
            # User cancelled the startup modal — fall back to cwd so the app remains usable.
            path = os.getcwd()
        self._set_active_session(path)

    def _set_active_session(self, project_path: str, session_id: str | None = None) -> None:
        os.chdir(project_path)
        self.current_project_path = project_path
        self.current_session_id = session_id or uuid4().hex
        self.current_session_persisted = session_id is not None
        self.agent = create_agent(project_path)

        chat = self.query_one("#chat-area", ChatArea)
        chat.remove_children()
        self.messages.clear()

        label = "existing session" if session_id is not None else "new session"
        if session_id is not None:
            row = sessions_repo.get_session_row(session_id)
            if row is not None:
                label = row.title
        chat.add_message("system", f"Session: {label}\nWorking directory: {project_path}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return

        event.input.clear()
        chat = self.query_one("#chat-area", ChatArea)

        # Add user message
        chat.add_message("user", value)
        self.messages.append({"role": "user", "content": value})

        # Handle commands
        if value.startswith("/"):
            self._handle_command(value, chat)
        else:
            base_dir = self.current_project_path or os.getcwd()
            expanded = expand_mentions(value, base_dir)
            self._send_to_agent(expanded, chat)

    def _handle_command(self, command: str, chat: ChatArea) -> None:
        cmd = command.lower().strip().split(" ", 1)[0]
        if cmd == "/help":
            width = max(len(c.name) for c in COMMANDS) + 1
            lines = ["Available commands:"]
            lines += [f"  /{c.name:<{width}}  {c.description}" for c in COMMANDS]
            chat.add_message("system", "\n".join(lines))
        elif cmd == "/clear":
            self.action_clear()
        elif cmd == "/new":
            self.push_screen(
                NewSessionScreen(default_path=os.getcwd()),
                self._on_new_session,
            )
        elif cmd == "/session":
            self.push_screen(SessionsScreen(), self._on_session_picked)
        elif cmd == "/model":
            chat.add_message("system", f"Model: {settings.llm_model}\nContext: 200k tokens")
        elif cmd == "/quit":
            self.exit()
        else:
            chat.add_message("system", f"Unknown command: {command}")
        self.messages.append({"role": "system", "content": command})

    def _on_new_session(self, path: str | None) -> None:
        if path is None:
            return
        self._set_active_session(path)

    def _on_session_picked(self, session_id: str | None) -> None:
        if session_id is None:
            return
        row = sessions_repo.get_session_row(session_id)
        if row is None:
            chat = self.query_one("#chat-area", ChatArea)
            chat.add_message("system", f"Session not found: {session_id}")
            return
        self._set_active_session(row.project_path, session_id=session_id)

    def _send_to_agent(self, user_input: str, chat: ChatArea) -> None:
        if self.agent is None:
            chat.add_message("system", "No active session. Use /new to start one.")
            return
        self.query_one(PromptInput).show_loading()
        self.run_worker(self._run_agent(user_input), exclusive=True)

    async def _run_agent(self, user_input: str) -> None:
        chat = self.query_one("#chat-area", ChatArea)
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

        # Start streaming in background thread
        loop.run_in_executor(
            None,
            stream_agent,
            self.agent,
            user_input,
            loop,
            queue,
            self.current_session_id,
        )

        # Create assistant bubble, keep spinner visible throughout
        bubble = chat.add_message("assistant", "")
        full_content = ""
        while True:
            item = await queue.get()
            if item is None:
                break
            tag, text = item
            if tag == "tool_start":
                bubble.append_tool_call(text)
            elif tag == "reasoning":
                bubble.append_reasoning(text)
            elif tag == "content":
                full_content += text
                bubble.append_text(text)
            chat.scroll_end(animate=False)

        # Hide spinner when done
        await self.query_one(PromptInput).hide_loading()

        if not full_content:
            bubble.append_text("No response.")
            full_content = "No response."

        bubble.flush_now()

        self.messages.append({"role": "assistant", "content": full_content})

        # Persist or touch the session row.
        if self.current_session_id and self.current_project_path:
            if not self.current_session_persisted:
                first_user = next(
                    (m["content"] for m in self.messages if m["role"] == "user"),
                    user_input,
                )
                sessions_repo.create_session(
                    self.current_session_id,
                    title=_truncate_title(first_user),
                    project_path=self.current_project_path,
                )
                self.current_session_persisted = True
            else:
                sessions_repo.touch_session(self.current_session_id)

    def action_clear(self) -> None:
        chat = self.query_one("#chat-area", ChatArea)
        chat.remove_children()
        self.messages.clear()
        self.token_count = 0
        chat.add_message("system", "Chat cleared.")
