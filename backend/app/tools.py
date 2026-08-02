"""
tools.py
~~~~~~~~
Shared tool execution functions for both Pi RPC and direct Ollama paths.

These functions are called by both the Pi agent (via RPC) and the direct
Ollama agent (in-process) to execute tool calls.
"""

import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Artifact as ArtifactModel
from .routers.search import hybrid_search

logger = logging.getLogger(__name__)


async def search_transcripts(query: str, top_k: int = 5) -> tuple[str, dict[str, Any]]:
    """
    Search for relevant transcript passages using hybrid retrieval.

    Args:
        query: Search query string
        top_k: Number of results to return

    Returns:
        (result_text, metadata_dict) where metadata contains chunk_ids
    """
    results = await hybrid_search(query, top_k=top_k)
    formatted = "\n\n---\n\n".join(
        f"**{r['guest']} — {r['title']}**\n{r['content']}"
        for r in results
    )
    chunk_ids = [r["chunk_id"] for r in results]
    return formatted or "No relevant transcript passages found.", {"chunk_ids": chunk_ids}


async def generate_ship30_essay(topic: str, source_context: str) -> tuple[str, None]:
    """
    Generate a Ship30 essay (context only - actual generation by LLM).

    Args:
        topic: Essay topic
        source_context: Source context from transcripts

    Returns:
        (context_string, None) - no artifact metadata
    """
    return f"[Ship30 essay mode — topic: {topic}]\n\n{source_context}", None


async def create_artifact(
    artifact_type: str,
    title: str,
    content: str,
    message_id: str,
    session_id: str,
    db: AsyncSession
) -> tuple[str, dict[str, Any]]:
    """
    Create an artifact in the database.

    Args:
        artifact_type: Type of artifact (e.g., "markdown")
        title: Artifact title
        content: Artifact content
        message_id: UUID of the message that created this artifact
        session_id: UUID of the session
        db: Database session

    Returns:
        (success_message, artifact_dict) with keys: id, type, title, content
    """
    import uuid

    artifact = ArtifactModel(
        message_id=uuid.UUID(message_id),
        session_id=uuid.UUID(session_id),
        type=artifact_type,
        title=title,
        content=content,
        version=1,
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)

    return f"Artifact '{title}' created.", {
        "id": str(artifact.id),
        "artifact_type": artifact_type,
        "title": title,
        "content": content,
    }


# Tool registry for easy lookup
TOOLS = {
    "search_transcripts": search_transcripts,
    "generate_ship30_essay": generate_ship30_essay,
    "create_artifact": create_artifact,
}


def get_tool_schemas() -> list[dict[str, Any]]:
    """
    Return OpenAI-style tool schemas for the available tools.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "search_transcripts",
                "description": "Search the Lenny's podcast transcript database for relevant passages. Use this when the user asks about specific guests, topics, or episodes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for finding relevant transcript passages"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_ship30_essay",
                "description": "Generate a Ship30 essay on a given topic using transcript context. Use this when the user explicitly asks for a Ship30-style essay.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The topic to write the Ship30 essay about"
                        },
                        "source_context": {
                            "type": "string",
                            "description": "Relevant context from transcripts to base the essay on"
                        }
                    },
                    "required": ["topic", "source_context"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_artifact",
                "description": "Create a persistent artifact (document, code, etc.) that can be referenced later. Use this when the user asks to create, save, or document something.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Type of artifact (e.g., 'markdown', 'code', 'text')",
                            "default": "markdown"
                        },
                        "title": {
                            "type": "string",
                            "description": "Title of the artifact"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content of the artifact"
                        }
                    },
                    "required": ["title", "content"]
                }
            }
        }
    ]
