#!/usr/bin/env python3
"""Speaking Claude Code - AI Coding Streamer with real-time TTS and personalities."""

import asyncio
import subprocess
import sys
from asyncio import Queue
from typing import Optional

from stream_parser import StreamParser, ContentType, SpeakableContent
from tts_client import TTSClient


class SpeakingClaude:
    """Run Claude Code with real-time TTS narration."""

    def __init__(self):
        self.parser = StreamParser()
        self.tts: Optional[TTSClient] = None
        self.speech_queue: Queue[SpeakableContent] = Queue()
        self._running = False

    async def start(self):
        """Initialize the TTS client with a random personality."""
        self.tts = TTSClient()  # Random personality selected here
        await self.tts.start()
        self._running = True

    async def stop(self):
        """Clean up resources."""
        self._running = False
        if self.tts:
            await self.tts.stop()

    async def run(self, prompt: str):
        """Run Claude Code with the given prompt and narrate the output."""
        await self.start()

        try:
            # Start speech worker
            speech_task = asyncio.create_task(self._speech_worker())

            # Run Claude Code
            await self._run_claude(prompt)

            # Wait for remaining speech to complete
            await self.speech_queue.join()
            self._running = False
            await speech_task

        finally:
            await self.stop()

    async def _run_claude(self, prompt: str):
        """Run Claude Code as a subprocess and parse its output."""
        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "-p", prompt
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Opening announcement with personality
        intro_text = self.tts.get_intro()
        await self.speech_queue.put(SpeakableContent(
            text=intro_text,
            content_type=ContentType.ACTION,
            priority=2
        ))

        # Process stdout line by line
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode("utf-8")

            # Parse and queue speakable content
            for content in self.parser.parse_line(line_str):
                # Replace generic action text with personality-specific phrases
                if content.content_type == ContentType.ACTION and self.tts:
                    tool_name = content.text.replace("...", "").strip()
                    if tool_name in ["Reading", "Writing", "Editing", "Running", "Searching for", "Searching in", "Starting", "Fetching", "Searching the web for"]:
                        # Map back to tool name
                        tool_map = {
                            "Reading": "Read",
                            "Writing": "Write",
                            "Editing": "Edit",
                            "Running": "Bash",
                            "Searching for": "Glob",
                            "Searching in": "Grep",
                            "Starting": "Task",
                            "Fetching": "WebFetch",
                            "Searching the web for": "WebSearch",
                        }
                        tool_name = tool_map.get(tool_name, tool_name)
                        content = SpeakableContent(
                            text=self.tts.get_action(tool_name),
                            content_type=ContentType.ACTION,
                            priority=content.priority
                        )
                await self.speech_queue.put(content)

        # Wait for process to complete
        await process.wait()

        # Closing announcement with personality
        outro_text = self.tts.get_outro()
        await self.speech_queue.put(SpeakableContent(
            text=outro_text,
            content_type=ContentType.REACTION,
            priority=1
        ))

    async def _speech_worker(self):
        """Process the speech queue and speak content."""
        while self._running or not self.speech_queue.empty():
            try:
                content = await asyncio.wait_for(
                    self.speech_queue.get(),
                    timeout=0.5
                )
            except asyncio.TimeoutError:
                continue

            try:
                await self._speak_content(content)
            finally:
                self.speech_queue.task_done()

    async def _speak_content(self, content: SpeakableContent):
        """Speak a piece of content with appropriate style."""
        if not self.tts:
            return

        # Show what's being spoken
        print(f"[{content.content_type.value}] {content.text}")

        if content.content_type == ContentType.ACTION:
            await self.tts.speak_action(content.text)
        elif content.content_type == ContentType.REACTION:
            # Use personality-specific error phrases for errors
            if "didn't work" in content.text.lower() or "error" in content.text.lower():
                await self.tts.speak(self.tts.get_error())
            else:
                await self.tts.speak(content.text)
        else:
            await self.tts.speak(content.text)


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python speaking_claude.py <prompt>")
        print("Example: python speaking_claude.py 'Fix the bug in auth.py'")
        print("\nEach run gets a random personality!")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])

    speaker = SpeakingClaude()
    await speaker.run(prompt)


if __name__ == "__main__":
    asyncio.run(main())
