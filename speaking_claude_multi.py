#!/usr/bin/env python3
"""Speaking Claude Code - Multi-turn mode with expressive TTS narration.

Designed for streaming/entertainment - agents narrate their work with personality.
"""

import asyncio
import json
import random
import subprocess
import sys
import threading
import time
from typing import Optional

from tts_client import TTSClient


class SpeakingClaudeMulti:
    """Run multiple Claude Code prompts with expressive TTS narration."""

    def __init__(self, streaming_mode: bool = True):
        self.tts: Optional[TTSClient] = None
        self._session_id = None
        self._loop = None
        self._streaming_mode = streaming_mode  # Skip permissions for demo/streaming
        self._thinking_thread: Optional[threading.Thread] = None
        self._stop_thinking = threading.Event()
        self._tool_count = 0  # Track tool uses for hype moments
        self._error_count = 0  # Track errors for frustration

    def _run_async(self, coro):
        """Run async code from sync context."""
        return self._loop.run_until_complete(coro)

    def start(self):
        """Initialize TTS client with a random personality."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self.tts = TTSClient()
        self._run_async(self.tts.start())

        # Welcome message
        intro = self.tts.get_intro()
        print(f"\n🎙️  [{self.tts.personality.name}] {intro}")
        self._run_async(self.tts.speak(intro))
        time.sleep(2)

    def stop(self):
        """Clean up resources."""
        self._stop_thinking.set()
        if self._thinking_thread:
            self._thinking_thread.join(timeout=1)

        if self.tts:
            outro = self.tts.get_outro()
            print(f"\n🎙️  {outro}")
            self._run_async(self.tts.speak(outro))
            time.sleep(2)
            self._run_async(self.tts.stop())
        if self._loop:
            self._loop.close()

    def _start_thinking(self):
        """Start background thinking thread."""
        self._stop_thinking.clear()
        self._thinking_thread = threading.Thread(target=self._thinking_loop, daemon=True)
        self._thinking_thread.start()

    def _thinking_loop(self):
        """Background thread that occasionally speaks thinking phrases."""
        # Wait a bit before first thinking phrase
        time.sleep(3)

        while not self._stop_thinking.is_set():
            # Random interval between thinking phrases (5-12 seconds)
            wait_time = random.uniform(5, 12)
            if self._stop_thinking.wait(timeout=wait_time):
                break  # Stop requested

            if not self._stop_thinking.is_set() and self.tts:
                # Occasionally say a thinking phrase
                if random.random() < 0.6:  # 60% chance
                    thinking = self.tts.get_thinking()
                    print(f"  💭 {thinking}")
                    self._run_async(self.tts.speak(thinking))

    def _stop_thinking_thread(self):
        """Stop the thinking thread."""
        self._stop_thinking.set()
        if self._thinking_thread:
            self._thinking_thread.join(timeout=1)
            self._thinking_thread = None

    def run_prompt(self, prompt: str):
        """Run a single prompt and speak the response."""
        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "-p", prompt
        ]

        # Continue session if we have one
        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        # Streaming mode skips permission prompts
        if self._streaming_mode:
            cmd.append("--dangerously-skip-permissions")

        # Start background thinking
        self._start_thinking()

        # Run subprocess synchronously with line buffering
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Process output - read line by line
        full_response = []
        last_was_tool = False
        consecutive_tools = 0

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break

            line_str = line.strip()
            if not line_str:
                continue

            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")

            # Capture session ID for continuation
            if event_type == "system" and event.get("session_id"):
                self._session_id = event.get("session_id")

            # Extract text from assistant messages
            if event_type == "assistant":
                message = event.get("message", {})
                content = message.get("content", [])

                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            # Stop thinking while speaking response
                            self._stop_thinking_thread()

                            full_response.append(text)
                            # Show abbreviated text in console
                            display_text = text[:150] + ('...' if len(text) > 150 else '')
                            print(f"  💬 {display_text}")
                            sys.stdout.flush()

                            if self.tts:
                                self._run_async(self.tts.speak(text))

                            last_was_tool = False
                            consecutive_tools = 0

                            # Occasionally add hype after good progress
                            self._tool_count += 1
                            if self._tool_count % 5 == 0 and self.tts:
                                hype = self.tts.get_hype()
                                print(f"  🔥 {hype}")
                                self._run_async(self.tts.speak(hype))

                    elif block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        if tool_name and self.tts:
                            consecutive_tools += 1

                            # Only narrate some tool uses to keep it natural
                            # Skip if we just did a tool, or randomly skip some
                            should_speak = (
                                not last_was_tool or
                                consecutive_tools >= 3 or  # Speak after several silent ones
                                random.random() < 0.3  # 30% chance anyway
                            )

                            if should_speak:
                                action_text = self.tts.get_action(tool_name)
                                print(f"  🔧 {action_text}")
                                self._run_async(self.tts.speak_action(action_text))
                                consecutive_tools = 0
                            else:
                                # Silent tool use - just show in console
                                print(f"  🔧 [{tool_name}]")

                            last_was_tool = True

                            # Restart thinking after tool narration
                            if not self._thinking_thread or not self._thinking_thread.is_alive():
                                self._start_thinking()

            # Handle errors with personality
            if event_type == "result" and event.get("is_error"):
                self._stop_thinking_thread()
                self._error_count += 1

                if self.tts:
                    # Alternate between error and frustrated phrases
                    if self._error_count > 2:
                        error_text = self.tts.get_frustrated()
                    else:
                        error_text = self.tts.get_error()
                    print(f"  ❌ {error_text}")
                    self._run_async(self.tts.speak(error_text))

            # Handle success results
            if event_type == "result" and not event.get("is_error"):
                self._stop_thinking_thread()
                self._error_count = 0  # Reset error count on success

                # Occasionally add success reaction
                if self.tts and random.random() < 0.4:
                    success = self.tts.get_success()
                    print(f"  ✨ {success}")
                    self._run_async(self.tts.speak(success))

        # Stop thinking and wait for process
        self._stop_thinking_thread()
        process.wait()

        # Give audio time to finish playing
        if full_response:
            total_chars = sum(len(r) for r in full_response)
            wait_time = min(max(total_chars / 12.5, 1), 10)
            time.sleep(wait_time)

        return "\n".join(full_response)

    def interactive_loop(self):
        """Run an interactive loop taking user prompts."""
        self.start()

        mode_text = "STREAMING MODE (permissions bypassed)" if self._streaming_mode else "Standard Mode"
        print(f"\n{'=' * 50}")
        print(f"🎤 Speaking Claude Code - {self.tts.personality.name}")
        print(f"{'=' * 50}")
        print(f"Mode: {mode_text}")
        print("Type prompts and hear Claude respond with personality!")
        print("Commands: 'quit' to exit, 'new' for new session")
        print(f"{'=' * 50}\n")

        try:
            while True:
                try:
                    prompt = input("\n📝 You: ").strip()
                except EOFError:
                    break

                if not prompt:
                    continue

                if prompt.lower() in ['quit', 'exit', 'q']:
                    break

                if prompt.lower() == 'new':
                    self._session_id = None
                    self._tool_count = 0
                    self._error_count = 0
                    print("🔄 Starting new session...")
                    if self.tts:
                        self._run_async(self.tts.speak("Fresh start, let's go!"))
                    continue

                personality_name = self.tts.personality.name if self.tts else "Agent"
                print(f"\n🤖 Claude ({personality_name}):")
                sys.stdout.flush()

                # Run the prompt
                self.run_prompt(prompt)
                sys.stdout.flush()

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted!")
        finally:
            self.stop()


def main():
    # Check for --safe flag to disable streaming mode
    streaming_mode = "--safe" not in sys.argv
    args = [a for a in sys.argv[1:] if a != "--safe"]

    if args:
        # Single prompt mode
        prompt = " ".join(args)
        speaker = SpeakingClaudeMulti(streaming_mode=streaming_mode)
        speaker.start()
        speaker.run_prompt(prompt)
        speaker.stop()
    else:
        # Interactive loop mode
        speaker = SpeakingClaudeMulti(streaming_mode=streaming_mode)
        speaker.interactive_loop()


if __name__ == "__main__":
    main()
