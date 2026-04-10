"""
LLM wrappers that call the Claude CLI and Codex CLI instead of using API keys directly.
These allow using your existing Claude Code / Codex subscriptions without separate API keys.
"""

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class _CLIMessage:
    """Minimal message-like object compatible with LangChain's message interface."""

    def __init__(self, content: str):
        self.content = content


def _messages_to_text(messages: Any) -> str:
    """Convert a LangChain prompt (messages list, ChatPromptValue, or string) to plain text."""
    # ChatPromptValue / anything with .to_messages()
    if hasattr(messages, "to_messages"):
        messages = messages.to_messages()

    if isinstance(messages, list):
        parts = []
        for msg in messages:
            role = type(msg).__name__.replace("Message", "")
            content = msg.content if hasattr(msg, "content") else str(msg)
            if role == "System":
                parts.append(f"[System]\n{content}")
            elif role == "Human":
                parts.append(f"[User]\n{content}")
            elif role == "AI":
                parts.append(f"[Assistant]\n{content}")
            else:
                parts.append(str(content))
        return "\n\n".join(parts)

    if isinstance(messages, str):
        return messages

    if hasattr(messages, "content"):
        return str(messages.content)

    return str(messages)


class ChatClaudeCLI:
    """
    LangChain-compatible LLM wrapper that calls the `claude` CLI.
    Uses your Claude Code subscription — no ANTHROPIC_API_KEY required.

    The `--bare` flag is used to avoid loading session hooks and other overhead,
    and `--no-session-persistence` ensures no session state is saved.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def invoke(self, messages: Any, **kwargs) -> _CLIMessage:
        prompt_text = _messages_to_text(messages)
        cmd = [
            "claude",
            "-p", prompt_text,
            "--model", self.model,
            "--output-format", "json",
            "--no-session-persistence",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode != 0:
                logger.warning("Claude CLI stderr: %s", result.stderr[:500])
                return _CLIMessage(content="")

            response = json.loads(result.stdout)
            return _CLIMessage(content=response.get("result", ""))

        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out for model %s", self.model)
            return _CLIMessage(content="")
        except Exception as e:
            logger.error("Claude CLI error: %s", e)
            return _CLIMessage(content="")

    def with_structured_output(self, pydantic_model: Any, **kwargs) -> "ChatClaudeCLI":
        # Route through the non-JSON mode path (has_json_mode = False),
        # which means the caller will use extract_json_from_response on .content.
        return self


class ChatCodexCLI:
    """
    LangChain-compatible LLM wrapper that calls the `codex` CLI.
    Uses your OpenAI Codex subscription — no OPENAI_API_KEY required.

    Uses `codex exec` in non-interactive mode with JSON event output.
    """

    def __init__(self, model: str = "o3"):
        self.model = model

    def invoke(self, messages: Any, **kwargs) -> _CLIMessage:
        prompt_text = _messages_to_text(messages)
        cmd = [
            "codex", "exec",
            prompt_text,
            "--json",
            "-m", self.model,
            "--skip-git-repo-check",
            "--ephemeral",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Parse JSONL output — find the last agent_message item
            last_text = ""
            for line in result.stdout.strip().splitlines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "item.completed":
                        item = event.get("item", {})
                        if item.get("type") == "agent_message":
                            last_text = item.get("text", "")
                except json.JSONDecodeError:
                    pass

            return _CLIMessage(content=last_text)

        except subprocess.TimeoutExpired:
            logger.error("Codex CLI timed out for model %s", self.model)
            return _CLIMessage(content="")
        except Exception as e:
            logger.error("Codex CLI error: %s", e)
            return _CLIMessage(content="")

    def with_structured_output(self, pydantic_model: Any, **kwargs) -> "ChatCodexCLI":
        return self
