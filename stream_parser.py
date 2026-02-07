"""Parse Claude Code stream-json output and extract speakable content."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Optional


class ContentType(Enum):
    NARRATION = "narration"  # Assistant explanations
    ACTION = "action"  # Tool use announcements
    REACTION = "reaction"  # Responses to results


@dataclass
class SpeakableContent:
    """Content ready to be spoken."""
    text: str
    content_type: ContentType
    priority: int = 1  # Higher = more important


class StreamParser:
    """Parse Claude Code stream-json and extract speakable content."""

    # Tool names to human-readable actions
    TOOL_ACTIONS = {
        "Read": "Reading",
        "Write": "Writing",
        "Edit": "Editing",
        "Bash": "Running",
        "Glob": "Searching for",
        "Grep": "Searching in",
        "Task": "Starting",
        "WebFetch": "Fetching",
        "WebSearch": "Searching the web for",
    }

    def __init__(self):
        self._text_buffer = ""
        self._current_tool = None

    def parse_line(self, line: str) -> Iterator[SpeakableContent]:
        """Parse a single line of stream-json output."""
        line = line.strip()
        if not line:
            return

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return

        yield from self._handle_event(event)

    def _handle_event(self, event: dict) -> Iterator[SpeakableContent]:
        """Route event to appropriate handler."""
        event_type = event.get("type")

        if event_type == "assistant":
            yield from self._handle_assistant(event)
        elif event_type == "content_block_start":
            yield from self._handle_content_block_start(event)
        elif event_type == "content_block_delta":
            yield from self._handle_content_block_delta(event)
        elif event_type == "content_block_stop":
            yield from self._handle_content_block_stop(event)
        elif event_type == "result":
            yield from self._handle_result(event)

    def _handle_assistant(self, event: dict) -> Iterator[SpeakableContent]:
        """Handle assistant message events."""
        message = event.get("message", {})
        content_blocks = message.get("content", [])

        for block in content_blocks:
            if block.get("type") == "text":
                text = block.get("text", "")
                speakable = self._extract_speakable_text(text)
                if speakable:
                    yield SpeakableContent(
                        text=speakable,
                        content_type=ContentType.NARRATION
                    )

    def _handle_content_block_start(self, event: dict) -> Iterator[SpeakableContent]:
        """Handle start of a content block (including tool use)."""
        content_block = event.get("content_block", {})
        block_type = content_block.get("type")

        if block_type == "tool_use":
            tool_name = content_block.get("name", "")
            self._current_tool = tool_name

            # Announce tool use
            action = self.TOOL_ACTIONS.get(tool_name, f"Using {tool_name}")
            yield SpeakableContent(
                text=f"{action}...",
                content_type=ContentType.ACTION,
                priority=2
            )

    def _handle_content_block_delta(self, event: dict) -> Iterator[SpeakableContent]:
        """Handle streaming content deltas."""
        delta = event.get("delta", {})
        delta_type = delta.get("type")

        if delta_type == "text_delta":
            text = delta.get("text", "")
            self._text_buffer += text

            # Check for complete sentences to speak
            yield from self._flush_complete_sentences()

    def _handle_content_block_stop(self, event: dict) -> Iterator[SpeakableContent]:
        """Handle end of content block."""
        # Flush any remaining text
        if self._text_buffer.strip():
            speakable = self._extract_speakable_text(self._text_buffer)
            if speakable:
                yield SpeakableContent(
                    text=speakable,
                    content_type=ContentType.NARRATION
                )
        self._text_buffer = ""
        self._current_tool = None

    def _handle_result(self, event: dict) -> Iterator[SpeakableContent]:
        """Handle result events (success/failure reactions)."""
        result = event.get("result")

        # Check for errors (result can be a string or dict)
        is_error = event.get("is_error")
        if isinstance(result, dict):
            is_error = is_error or result.get("is_error")

        if is_error:
            yield SpeakableContent(
                text="Hmm, that didn't work. Let me try something else.",
                content_type=ContentType.REACTION,
                priority=3
            )
        # Note: We don't speak the result text here since it's already
        # captured from the assistant message

    def _flush_complete_sentences(self) -> Iterator[SpeakableContent]:
        """Extract and yield complete sentences from buffer."""
        # Look for sentence endings
        sentence_endings = re.compile(r'([.!?])\s+')

        while True:
            match = sentence_endings.search(self._text_buffer)
            if not match:
                break

            # Extract the complete sentence
            end_pos = match.end()
            sentence = self._text_buffer[:end_pos].strip()
            self._text_buffer = self._text_buffer[end_pos:]

            speakable = self._extract_speakable_text(sentence)
            if speakable:
                yield SpeakableContent(
                    text=speakable,
                    content_type=ContentType.NARRATION
                )

    def _extract_speakable_text(self, text: str) -> Optional[str]:
        """Extract speakable content, filtering out code/JSON."""
        if not text or not text.strip():
            return None

        text = text.strip()

        # Skip code blocks
        if text.startswith("```") or text.endswith("```"):
            return None
        if "```" in text:
            # Remove code blocks from mixed content
            text = re.sub(r'```[\s\S]*?```', '', text)

        # Skip JSON-like content
        if text.startswith("{") or text.startswith("["):
            return None

        # Skip empty text only
        if len(text.strip()) == 0:
            return None

        # Skip lines that look like file paths or code
        if re.match(r'^[\w/\\.]+\.(py|js|ts|json|md|txt|yaml|yml)$', text):
            return None

        # Skip lines that are mostly special characters
        alphanum_ratio = len(re.findall(r'[a-zA-Z0-9\s]', text)) / len(text)
        if alphanum_ratio < 0.5:
            return None

        # Clean up the text
        text = text.strip()

        # Limit length for natural speech
        if len(text) > 300:
            # Find a good break point
            break_point = text.rfind('. ', 0, 300)
            if break_point > 100:
                text = text[:break_point + 1]
            else:
                text = text[:297] + "..."

        return text if text else None
