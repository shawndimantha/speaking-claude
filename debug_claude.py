#!/usr/bin/env python3
"""Debug script to test Claude subprocess without TTS."""

import json
import os
import subprocess
import sys


def test_claude(prompt: str):
    """Run Claude and show all output."""
    cmd = [
        "claude",
        "--output-format", "stream-json",
        "--verbose",
        "-p", prompt
    ]

    print(f"\n[Running] {' '.join(cmd)}")
    print(f"[CWD] {os.getcwd()}")
    print()

    # Get full path to claude
    import shutil
    claude_path = shutil.which("claude")
    print(f"[Claude path] {claude_path}\n")

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=os.environ.copy()  # Explicitly pass environment
    )

    line_count = 0
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break

        line_str = line.strip()
        if not line_str:
            continue

        line_count += 1

        try:
            event = json.loads(line_str)
            event_type = event.get("type", "unknown")

            if event_type == "assistant":
                message = event.get("message", {})
                content = message.get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        print(f"[RESPONSE] {text}")
                    elif block.get("type") == "tool_use":
                        print(f"[TOOL] {block.get('name')}")
            else:
                print(f"[{event_type}] {line_str[:80]}...")

        except json.JSONDecodeError:
            print(f"[RAW] {line_str[:80]}")

    process.wait()
    stderr = process.stderr.read()
    if stderr:
        print(f"\n[STDERR - full output]")
        print(stderr)

    print(f"\n[Done] {line_count} lines, return code: {process.returncode}")


def main():
    print("Debug Claude Subprocess")
    print("=" * 40)
    print("Type prompts to test. Type 'quit' to exit.\n")

    while True:
        try:
            prompt = input("Prompt: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not prompt:
            continue
        if prompt.lower() in ['quit', 'exit', 'q']:
            break

        test_claude(prompt)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single prompt mode
        test_claude(" ".join(sys.argv[1:]))
    else:
        main()
