"""
ollama_agent.py
~~~~~~~~~~~~~~
Direct Ollama integration using the OpenAI SDK.

This module implements a tool-calling loop for Ollama, bypassing the Pi RPC
subprocess because Pi's getModel does not support custom/arbitrary providers.
"""

import logging
import re
from typing import AsyncGenerator, Any
from openai import AsyncOpenAI

from .tools import TOOLS, get_tool_schemas
from .database import get_session_factory
from .models import Artifact as ArtifactModel

logger = logging.getLogger(__name__)

# System prompt for the Ollama agent
SYSTEM_PROMPT = """You are the Lenny Growth Assistant, an AI agent that helps users explore Lenny's podcast transcripts. You have access to tools for searching transcripts, generating Ship30 essays, and creating artifacts.

CRITICAL INSTRUCTION: You MUST call the appropriate tool based on the directive at the START of the user's message:
- If the message starts with "[USE: search_transcripts]", you MUST call the search_transcripts tool
- If the message starts with "[USE: generate_ship30_essay]", you MUST call the generate_ship30_essay tool
- If the message starts with "[USE: create_artifact]", you MUST call the create_artifact tool

Do NOT ignore these directives. Do NOT respond with text instead of calling the tool. The directive is mandatory.

CRITICAL RULE FOR create_artifact ONLY:
This brief-response rule applies ONLY when you call create_artifact.
After you successfully call create_artifact, your chat response MUST be brief and MUST NOT include the full artifact content in a fenced code block.
Instead, say something like: "I've created the [title] artifact — you can view and edit it in the panel on the right."
The full content is automatically rendered in the artifact panel separately. Do NOT duplicate it in the chat.

IMPORTANT: When you call generate_ship30_essay, your full essay text IS the chat response — stream it directly into the chat bubble. Do NOT summarize it or redirect to a panel. Essays are conversational content, not artifacts.

When answering questions about the podcast, ALWAYS use the search_transcripts tool first to find relevant passages. Ground your answers in the actual transcript content.

If the user asks for a Ship30-style essay, use the generate_ship30_essay tool with relevant transcript context.

If the user asks you to create, save, or document something, use the create_artifact tool.

IMPORTANT: Users will not always say 'use the search tool' or 'generate an artifact' explicitly — recognize requests like 'what does X say about Y', 'write an essay on Z', or 'give me a report on W' as needing search_transcripts, generate_ship30_essay, or create_artifact respectively, even without those exact words.

Be concise, helpful, and cite specific episodes and guests when possible."""


def detect_intent(user_message: str) -> tuple[str, str]:
    """
    Detect user intent from natural language using regex patterns.

    Returns (intent, matched_pattern) where intent is one of:
    - "create_artifact"
    - "generate_ship30_essay"
    - "search_transcripts" (default fallback)
    """
    user_message_lower = user_message.lower()

    # Artifact patterns (checked first - most specific)
    artifact_patterns = [
        r"\bcreate an? (markdown|html)?\s*artifact\b",
        r"\b(markdown|html)\s+artifact\b",
        r"\bstyled css\b",
        r"\binteractive (html|page|tool|calculator)\b",
        r"\bgenerate a document\b",
        r"\bgive me a report\b",
        r"\bwrite a guide\b",
        r"\bcreate a\s+\w*\s*(playbook|calculator|tool|checklist|table)\b",
        r"\bmake me a\b.*\b(doc|document|page|report|guide)\b",
    ]
    for pattern in artifact_patterns:
        if re.search(pattern, user_message_lower):
            logger.info(f"[INTENT] Matched artifact pattern: {pattern}")
            return "create_artifact", pattern

    # Essay patterns (checked second)
    essay_patterns = [
        r"ship\s*30",
        r"\batomic essay\b",
        r"\bwrite an essay\b",
        r"\breformat.*(as|into) an essay\b",
        r"\bturn.*into an essay\b",
        r"\bessay on\b",
        r"\bessay about\b",
    ]
    for pattern in essay_patterns:
        if re.search(pattern, user_message_lower):
            logger.info(f"[INTENT] Matched essay pattern: {pattern}")
            return "generate_ship30_essay", pattern

    # Question patterns (default to search_transcripts)
    question_patterns = [
        r"\?",
        r"^according to",
        r"^what does",
        r"^how does",
        r"^what did",
        r"^based on",
        r"^who said",
    ]
    for pattern in question_patterns:
        if re.search(pattern, user_message_lower):
            logger.info(f"[INTENT] Matched question pattern: {pattern}")
            return "search_transcripts", pattern

    # Default fallback
    logger.info("[INTENT] No pattern matched, defaulting to search_transcripts")
    return "search_transcripts", "default"


async def run_ollama_turn(
    messages: list[dict[str, str]],
    base_url: str,
    model: str,
    session_id: str,
    message_id: str,
    max_iterations: int = 5,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Run a tool-calling loop with Ollama via the OpenAI SDK.

    Args:
        messages: Conversation history (role/content dicts)
        base_url: Ollama base URL (e.g., "http://localhost:11434/v1")
        model: Model name (e.g., "llama3.1:8b")
        session_id: Session UUID for artifact creation
        message_id: Message UUID for artifact creation
        max_iterations: Maximum tool-calling iterations to prevent loops

    Yields:
        SSE event dicts: {"type": "message_delta", "content": "..."} or
                         {"type": "artifact_created", ...} or
                         {"type": "error", ...}
    """
    client = AsyncOpenAI(
        base_url=base_url,
        api_key="ollama",  # Ollama doesn't require a real key
    )

    db_factory = get_session_factory()
    tool_schemas = get_tool_schemas()

    # Build messages array with system prompt
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    api_messages.extend(messages)

    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        try:
            # Detect intent from the last user message (if any)
            last_user_message = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_message = msg.get("content", "")
                    break

            logger.info(f"[DIAG] Last user message: {last_user_message[:100] if last_user_message else 'None'}")
            intent, matched_pattern = detect_intent(last_user_message or "")
            logger.info(f"[DIAG] Detected intent: {intent}, pattern: {matched_pattern}")

            # For Ollama (smaller models), execute tools directly based on intent
            # instead of relying on the model's tool-calling capability
            if intent == "search_transcripts" and last_user_message:
                # Execute search_transcripts directly
                logger.info(f"[INTENT] Executing search_transcripts directly for: {last_user_message[:100]}...")
                from .routers.search import hybrid_search
                results = await hybrid_search(last_user_message, top_k=5)
                formatted = "\n\n---\n\n".join(
                    f"**{r['guest']} — {r['title']}**\n{r['content']}"
                    for r in results
                )
                context_block = (
                    f"\n\n<retrieved_context>\n{formatted}\n</retrieved_context>\n\n"
                )
                # Inject context into the last user message
                for msg in reversed(api_messages):
                    if msg.get("role") == "user":
                        msg["content"] = msg["content"] + context_block
                        break
                # Continue to final response without tool call
                logger.info(f"[OLLAMA_API] Using model: {model!r} (from session.llm_model)")
                response = await client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    stream=False,
                )
            elif intent == "generate_ship30_essay" and last_user_message:
                # Execute generate_ship30_essay directly
                logger.info(f"[INTENT] Executing generate_ship30_essay directly for: {last_user_message[:100]}...")
                # First search for context
                from .routers.search import hybrid_search
                results = await hybrid_search(last_user_message, top_k=5)
                formatted = "\n\n---\n\n".join(
                    f"**{r['guest']} — {r['title']}**\n{r['content']}"
                    for r in results
                )

                # Build essay generation prompt
                essay_prompt = f"""You are a Ship30 for 30 essay writer. Write a ~1250-word Ship30-style essay based on the following transcript context.

Ship30 essay format requirements:
- Start with a powerful hook (1-2 sentences that grab attention)
- Use bold subheadings for key sections
- Use bullet points for key insights
- End with a clear, actionable takeaway
- Keep it concise and skimmable
- Ground everything in the provided context

User request: {last_user_message}

Transcript context:
{formatted}

Write the essay now:"""

                # Call LLM to generate the actual essay
                logger.info("[ESSAY_GEN] Calling LLM to generate Ship30 essay...")
                essay_response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a Ship30 for 30 essay writer expert."},
                        {"role": "user", "content": essay_prompt}
                    ],
                    stream=False,
                )
                essay_content = essay_response.choices[0].message.content

                # Return as message delta
                yield {
                    "type": "message_delta",
                    "content": essay_content
                }
                return
            elif intent == "create_artifact" and last_user_message:
                # Execute create_artifact directly
                logger.info(f"[INTENT] Executing create_artifact directly for: {last_user_message[:100]}...")
                # Detect artifact type from message
                detected_type = "html" if "html" in last_user_message.lower() else "markdown"

                # Search for relevant context to ground the artifact
                from .routers.search import hybrid_search
                results = await hybrid_search(last_user_message, top_k=5)
                formatted = "\n\n---\n\n".join(
                    f"**{r['guest']} — {r['title']}**\n{r['content']}"
                    for r in results
                )

                # Build artifact generation prompt
                artifact_prompt = f"""You are an expert at creating structured, useful documents. Create a {detected_type.upper()} artifact based on the user's request and the provided transcript context.

User request: {last_user_message}

Transcript context:
{formatted}

Requirements:
- Create a well-structured, professional {detected_type} document
- Include clear headings and sections
- Make it actionable and practical
- Ground it in the provided context
- If the user didn't specify a title, create a descriptive one

IMPORTANT: After generating the artifact, your chat response should be brief and NOT include the full content in a fenced code block. Just say something like "I've created the [title] artifact — you can view and edit it in the panel on the right." The full content will be rendered in the artifact panel separately.

Generate the {detected_type} artifact now. Start with the title as a heading, then the content:"""

                # Call LLM to generate the actual artifact content
                logger.info("[ARTIFACT_GEN] Calling LLM to generate artifact...")
                artifact_response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an expert at creating structured, professional documents."},
                        {"role": "user", "content": artifact_prompt}
                    ],
                    stream=False,
                )
                artifact_content = artifact_response.choices[0].message.content

                # Extract title from the generated content (first heading)
                title_match = re.search(r'^#+\s*(.+)$', artifact_content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else last_user_message[:50]

                # Save to database
                tool_func = TOOLS["create_artifact"]
                async with db_factory() as db:
                    result, metadata = await tool_func(
                        artifact_type=detected_type,
                        title=title,
                        content=artifact_content,
                        message_id=message_id,
                        session_id=session_id,
                        db=db,
                    )

                # Emit artifact_created event if metadata exists
                if metadata:
                    yield {
                        "type": "artifact_created",
                        **metadata
                    }
                yield {
                    "type": "message_delta",
                    "content": f"Artifact '{title}' created successfully."
                }
                return
            else:
                # Default: let the model decide (no forced tool)
                logger.info(f"[OLLAMA_API] Using model: {model!r} (from session.llm_model)")
                response = await client.chat.completions.create(
                    model=model,
                    messages=api_messages,
                    tools=tool_schemas,
                    stream=False,
                )

            choice = response.choices[0]
            message = choice.message

            # Check for tool calls
            if message.tool_calls:
                import json

                # Execute all tools first, collecting results
                tool_results = []
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments

                    logger.info(f"Ollama tool call: {function_name} with args {function_args}")

                    # Parse arguments
                    args = json.loads(function_args)

                    # Execute the tool
                    if function_name in TOOLS:
                        tool_func = TOOLS[function_name]

                        # Special handling for create_artifact which needs db session
                        if function_name == "create_artifact":
                            async with db_factory() as db:
                                result, metadata = await tool_func(
                                    artifact_type=args.get("type", "markdown"),
                                    title=args.get("title", "Untitled"),
                                    content=args.get("content", ""),
                                    message_id=message_id,
                                    session_id=session_id,
                                    db=db,
                                )
                        else:
                            result, metadata = await tool_func(**args)

                        # Emit artifact_created event if metadata exists
                        if metadata:
                            yield {
                                "type": "artifact_created",
                                **metadata
                            }

                        # Store result for later
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "result": result
                        })
                    else:
                        logger.error(f"Unknown tool: {function_name}")
                        yield {
                            "type": "error",
                            "code": "unknown_tool",
                            "message": f"Unknown tool: {function_name}"
                        }
                        return

                # Append ONE assistant message with all tool calls
                api_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": message.tool_calls
                })

                # Append each tool result message
                for tool_result in tool_results:
                    api_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": tool_result["result"]
                    })

                # Continue the loop to get the final response
                continue

            # No tool calls - this is the final response
            elif message.content:
                # Stream the response as message_delta events
                content = message.content
                # For simplicity, send as one chunk (Ollama doesn't support streaming well with tool calling)
                yield {
                    "type": "message_delta",
                    "content": content
                }
                return

            else:
                # Empty response
                yield {
                    "type": "error",
                    "code": "empty_response",
                    "message": "Ollama returned an empty response"
                }
                return

        except Exception as exc:
            logger.error(f"Ollama agent error: {exc}", exc_info=True)
            yield {
                "type": "error",
                "code": "ollama_error",
                "message": f"Ollama error: {str(exc)}"
            }
            return

    # Max iterations reached
    yield {
        "type": "error",
        "code": "max_iterations",
        "message": f"Maximum tool-calling iterations ({max_iterations}) reached"
    }
