#!/usr/bin/env python3
"""Interactive Speaking Claude - Real-time TTS for interactive Claude Code sessions."""

import asyncio
import json
import os
import pty
import re
import select
import sys
import termios
import tty
from typing import Optional

from tts_client import TTSClient


class InteractiveSpeakingClaude:
    """Run Claude Code interactively with real-time TTS narration."""

    def __init__(self):
        self.tts: Optional[TTSClient] = None
        self._running = False
        self._speech_queue: asyncio.Queue = asyncio.Queue()
        self._text_buffer = ""
        self._in_code_block = False
        self._last_spoken = ""

    async def start(self):
        """Initialize TTS client."""
        self.tts = TTSClient()
        await self.tts.start()
        self._running = True

        # Announce personality
        intro = self.tts.get_intro()
        print(f"\n🎙️  [{self.tts.personality.name}]: {intro}\n")
        await self.tts.speak(intro)

        # Wait for intro to finish
        import asyncio
        await asyncio.sleep(2)

    async def stop(self):
        """Clean up."""
        self._running = False
        if self.tts:
            outro = self.tts.get_outro()
            await self.tts.speak(outro)
            await asyncio.sleep(1)
            await self.tts.stop()

    async def run(self):
        """Run interactive Claude session with TTS."""
        await self.start()

        # Save terminal settings
        old_settings = termios.tcgetattr(sys.stdin)

        try:
            # Create pseudo-terminal for Claude
            master_fd, slave_fd = pty.openpty()

            # Start Claude process
            pid = os.fork()
            if pid == 0:
                # Child process - run Claude
                os.close(master_fd)
                os.setsid()
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)
                os.close(slave_fd)
                os.execlp("claude", "claude")
            else:
                # Parent process - handle I/O
                os.close(slave_fd)

                # Set terminal to raw mode for proper key handling
                tty.setraw(sys.stdin.fileno())

                # Start speech worker
                speech_task = asyncio.create_task(self._speech_worker())

                # Main I/O loop
                await self._io_loop(master_fd, pid)

                self._running = False
                await speech_task

        except Exception as e:
            print(f"\nError: {e}")
        finally:
            # Restore terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            await self.stop()

    async def _io_loop(self, master_fd: int, pid: int):
        """Handle I/O between user, Claude, and TTS."""
        loop = asyncio.get_event_loop()

        while True:
            # Check if Claude is still running
            result = os.waitpid(pid, os.WNOHANG)
            if result[0] != 0:
                break

            # Use select to check for available data
            rlist, _, _ = select.select([sys.stdin, master_fd], [], [], 0.1)

            for fd in rlist:
                if fd == sys.stdin:
                    # User input - forward to Claude
                    try:
                        data = os.read(sys.stdin.fileno(), 1024)
                        if data:
                            os.write(master_fd, data)
                    except OSError:
                        break

                elif fd == master_fd:
                    # Claude output - display and queue for TTS
                    try:
                        data = os.read(master_fd, 4096)
                        if data:
                            # Write to terminal
                            os.write(sys.stdout.fileno(), data)

                            # Process for TTS
                            text = data.decode("utf-8", errors="ignore")
                            # Debug: show raw text chunks (uncomment to debug)
                            # clean = text.replace('\x1b', '<ESC>').replace('\n', '<NL>')
                            # if len(clean) > 10:
                            #     print(f"\n[RAW] {clean[:100]}")
                            await self._process_output(text)
                    except OSError:
                        break

            # Small delay to prevent busy-waiting
            await asyncio.sleep(0.01)

    async def _process_output(self, text: str):
        """Process Claude's output and extract speakable content."""
        self._text_buffer += text

        # Handle code blocks - don't speak code
        if "```" in self._text_buffer:
            if not self._in_code_block:
                # Entering code block - speak what we have before it
                parts = self._text_buffer.split("```", 1)
                if parts[0].strip():
                    await self._queue_speech(parts[0])
                self._in_code_block = True
                self._text_buffer = parts[1] if len(parts) > 1 else ""
            else:
                # Check for end of code block
                if "```" in self._text_buffer:
                    parts = self._text_buffer.split("```", 1)
                    self._in_code_block = False
                    self._text_buffer = parts[1] if len(parts) > 1 else ""

        # If not in code block, look for complete sentences
        if not self._in_code_block:
            await self._extract_sentences()

    async def _extract_sentences(self):
        """Extract complete sentences from buffer and queue for speech."""
        # Look for sentence endings
        sentence_pattern = re.compile(r'([.!?])\s+')

        while True:
            match = sentence_pattern.search(self._text_buffer)
            if not match:
                break

            # Extract sentence
            end_pos = match.end()
            sentence = self._text_buffer[:end_pos].strip()
            self._text_buffer = self._text_buffer[end_pos:]

            if sentence:
                await self._queue_speech(sentence)

    async def _queue_speech(self, text: str):
        """Queue text for TTS, filtering out non-speakable content."""
        # Clean up the text
        text = self._clean_text(text)

        if not text or len(text) < 3:
            return

        # Skip if we just spoke this (avoid repetition)
        if text == self._last_spoken:
            return

        # Skip ANSI escape sequences and control characters
        if text.startswith("\x1b") or text.startswith("\033"):
            return

        # Skip lines that look like file paths or technical output
        if re.match(r'^[\w/\\.-]+\.(py|js|ts|json|md)$', text):
            return

        self._last_spoken = text
        print(f"\n🔊 [SPEAKING] {text[:80]}{'...' if len(text) > 80 else ''}")
        await self._speech_queue.put(text)

    def _clean_text(self, text: str) -> str:
        """Clean text for speech."""
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        text = ansi_escape.sub('', text)

        # Remove markdown formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'`([^`]+)`', r'\1', text)        # Inline code
        text = re.sub(r'#{1,6}\s*', '', text)           # Headers

        # Remove bullet points
        text = re.sub(r'^\s*[-*•]\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s*', '', text, flags=re.MULTILINE)

        # Clean up whitespace
        text = ' '.join(text.split())

        return text.strip()

    async def _speech_worker(self):
        """Process speech queue."""
        while self._running or not self._speech_queue.empty():
            try:
                text = await asyncio.wait_for(
                    self._speech_queue.get(),
                    timeout=0.5
                )
                if self.tts and text:
                    await self.tts.speak(text)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"\nTTS error: {e}")


async def main():
    print("🎙️  Speaking Claude Code - Interactive Mode")
    print("=" * 45)
    print("Claude will narrate what it's doing!")
    print("Press Ctrl+C to exit\n")

    speaker = InteractiveSpeakingClaude()
    try:
        await speaker.run()
    except KeyboardInterrupt:
        print("\n\nExiting...")


if __name__ == "__main__":
    asyncio.run(main())
