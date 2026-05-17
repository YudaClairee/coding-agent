from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai.like import OpenAILike
from agno.tools.websearch import WebSearchTools

from app.agents.prompt import SYSTEM_PROMPT
from app.agents.tools.commands import CommandTools
from app.agents.tools.file_system import FileSystemTools
from app.core.settings import settings


def create_agent(project_path: str) -> Agent:
    db = SqliteDb(db_file=settings.db_path)
    return Agent(
        model=OpenAILike(
            id=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        ),
        tools=[
            WebSearchTools(),
            FileSystemTools(base_dir=project_path),
            CommandTools(project_path=project_path),
        ],
        enable_agentic_memory=True,
        enable_session_summaries=True,
        instructions=SYSTEM_PROMPT,
        db=db,
        add_history_to_context=True,
        reasoning=True,
        markdown=False,
    )
