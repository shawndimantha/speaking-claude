#!/usr/bin/env python3
"""Battle Royale - 3 AI agents compete on the same task with different approaches.

Each agent gets a unique personality, voice, and approach. They can see each other's
progress and smack talk in real-time. Perfect for hackathon demos!
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, List

from cartesia import AsyncCartesia
import pyaudio


@dataclass
class Competitor:
    """A competing agent with its own personality and approach."""
    name: str
    approach: str
    voice_id: str
    port: int  # For serving their result
    color: str  # Terminal color code
    intro: str
    thinking: List[str]
    trash_talk: List[str]  # Comments about opponents
    self_hype: List[str]
    frustrated: List[str]
    victory: List[str]


# Three distinct competitor personalities
COMPETITORS = [
    Competitor(
        name="ValleyGirl",
        approach="make it super cute and aesthetic with pink colors, sparkles, and girly vibes - like, literally the cutest website ever",
        voice_id="b7d50908-b17c-442d-ad8d-810c63997ed9",  # Valley Girl
        port=8001,
        color="\033[95m",  # Pink/Magenta
        intro="Oh my GOD you guys, like, I am SO ready to make the cutest website EVER!",
        thinking=[
            "Okay wait, what if I add more pink?",
            "Hmm, this needs like, way more sparkles...",
            "Oh em gee, I'm like, literally obsessed with this idea!",
            "This is giving SUCH main character energy right now!",
        ],
        trash_talk=[
            "Ew, {opponent}'s site is like, SO boring. No offense but also full offense.",
            "Um, {opponent}? That color scheme is literally tragic.",
            "{opponent} is giving very much... basic. Like, yikes.",
            "I can't even with {opponent}'s vibe right now. So not aesthetic!",
        ],
        self_hype=[
            "This is like, literally SO cute I can't even!",
            "Okay but this is giving everything it needs to give!",
            "I'm literally obsessed with how this is turning out!",
        ],
        frustrated=[
            "Okay that's like, literally so annoying right now!",
            "Ugh, why is this being SO difficult? I can't!",
        ],
        victory=[
            "Oh my GOD you guys, I literally WON! This is like, the best day ever!",
            "Slay! I knew my aesthetic was superior! Like, obviously!",
        ],
    ),
    Competitor(
        name="AnimeFan",
        approach="make it epic and dramatic like an anime opening - flashy effects, bold colors, and maximum hype energy like a shonen protagonist",
        voice_id="498e7f37-7fa3-4e2c-b8e2-8b6e9276f956",  # Anime Fan
        port=8002,
        color="\033[93m",  # Yellow
        intro="YOSH! The time has come to unleash my ultimate coding technique! This will be LEGENDARY!",
        thinking=[
            "Calculating the optimal attack pattern...",
            "This requires my FULL POWER!",
            "I must concentrate my coding chakra...",
            "The protagonist never gives up! FIGHTING!",
        ],
        trash_talk=[
            "{opponent}! Your code is weaker than a filler episode!",
            "Nani?! {opponent} calls THAT a website? Pathetic!",
            "{opponent} has the power level of a background character!",
            "You dare challenge ME, {opponent}?! Know your place!",
        ],
        self_hype=[
            "PLUS ULTRA! Going beyond my limits!",
            "This is my final form! MAXIMUM POWER!",
            "The power of friendship and clean code guides me!",
        ],
        frustrated=[
            "KUSO! This bug... it's stronger than I thought!",
            "I won't give up! A true hero never surrenders!",
        ],
        victory=[
            "VICTORY! Just as the prophecy foretold! I AM THE PROTAGONIST!",
            "Omae wa mou... finished. My website reigns SUPREME!",
        ],
    ),
    Competitor(
        name="SurferDude",
        approach="keep it chill and laid-back with ocean vibes, good colors, nothing too complicated - just a mellow, good-vibes-only website mate",
        voice_id="41f3c367-e0a8-4a85-89e0-c27bae9c9b6d",  # Surfer Dude
        port=8003,
        color="\033[96m",  # Cyan
        intro="Yeah nah, let's just cruise through this one, no stress, good vibes only mate!",
        thinking=[
            "Hmm yeah, that's pretty chill...",
            "Just gonna go with the flow here...",
            "No worries, she'll be right...",
            "Keeping it simple, keeping it mellow...",
        ],
        trash_talk=[
            "{opponent}'s site is like, way too hectic. Just chill bro.",
            "Mate, {opponent} is trying way too hard. Bad vibes.",
            "{opponent} needs to take a breather, maybe catch some waves.",
            "Dunno what {opponent}'s doing but it's not the vibe.",
        ],
        self_hype=[
            "Oh yeah, this is coming together real nice!",
            "Sick! That's exactly what I was going for!",
            "Stoked on how this is turning out, legend!",
        ],
        frustrated=[
            "Ah bugger, that's a bit of a bummer...",
            "No dramas, we'll sort it out. No stress.",
        ],
        victory=[
            "Aw yeah legend! Good vibes won the day! Stoked!",
            "That was choice, mate! Surf's up, code's done!",
        ],
    ),
]


class BattleArena:
    """Manages the battle royale between agents."""

    SAMPLE_RATE = 24000

    def __init__(self, task: str):
        self.task = task
        self.arena_dir = Path("/tmp/battle_arena")
        self.arena_dir.mkdir(exist_ok=True)

        # Shared state for agents to see each other
        self.progress = {c.name: {"status": "starting", "lines": 0} for c in COMPETITORS}
        self.progress_lock = threading.Lock()

        # Audio setup
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.SAMPLE_RATE,
            output=True,
            frames_per_buffer=1024
        )
        self._audio_queue = Queue()
        self._audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._running = True
        self._audio_thread.start()

        # Cartesia client
        self._client = None
        self._client_lock = asyncio.Lock()

        # Speech queue to prevent overlap
        self._speech_queue = Queue()
        self._speech_thread = threading.Thread(target=self._speech_loop, daemon=True)
        self._speech_thread.start()

    def _audio_loop(self):
        """Background audio playback."""
        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                self._stream.write(chunk)
            except Empty:
                continue

    def _speech_loop(self):
        """Process speech queue to prevent overlapping."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._running:
            try:
                text, voice_id, name, color = self._speech_queue.get(timeout=0.5)
                print(f"{color}[{name}] 🎙️  {text}\033[0m")
                loop.run_until_complete(self._speak(text, voice_id))
                time.sleep(0.3)  # Small gap between speeches
            except Empty:
                continue

    async def _speak(self, text: str, voice_id: str):
        """Speak text with given voice."""
        import base64

        if not self._client:
            api_key = os.environ.get("CARTESIA_API_KEY")
            self._client = AsyncCartesia(api_key=api_key)

        try:
            async for output in self._client.tts.sse(
                model_id="sonic-2",
                transcript=text,
                voice={"mode": "id", "id": voice_id},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": self.SAMPLE_RATE
                }
            ):
                if hasattr(output, "data") and output.data:
                    audio_bytes = base64.b64decode(output.data)
                    self._audio_queue.put(audio_bytes)
        except Exception as e:
            print(f"TTS error: {e}")

    def queue_speech(self, text: str, competitor: Competitor):
        """Queue speech for a competitor."""
        self._speech_queue.put((text, competitor.voice_id, competitor.name, competitor.color))

    def update_progress(self, name: str, status: str, lines: int = 0):
        """Update an agent's progress."""
        with self.progress_lock:
            self.progress[name] = {"status": status, "lines": lines}

    def get_opponent_status(self, my_name: str) -> dict:
        """Get status of other competitors."""
        with self.progress_lock:
            return {k: v for k, v in self.progress.items() if k != my_name}

    def run_competitor(self, competitor: Competitor):
        """Run a single competitor's attempt."""
        work_dir = self.arena_dir / competitor.name.lower()
        work_dir.mkdir(exist_ok=True)

        # Create a prompt that emphasizes their approach
        prompt = f"""Create a solution for: {self.task}

Your approach should be: {competitor.approach}

Work in the current directory. Create any files needed.
When done, if it's a web page, save it as index.html.
Be decisive and execute quickly."""

        cmd = [
            "claude",
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "-p", prompt
        ]

        # Intro
        self.queue_speech(competitor.intro, competitor)
        time.sleep(2)

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(work_dir)
        )

        self.update_progress(competitor.name, "working")

        lines_processed = 0
        last_trash_talk = time.time()
        last_thinking = time.time()

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
            lines_processed += 1
            self.update_progress(competitor.name, "working", lines_processed)

            # Handle assistant messages
            if event_type == "assistant":
                message = event.get("message", {})
                content = message.get("content", [])

                for block in content:
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text and len(text) > 20:
                            # Speak key updates (abbreviated)
                            short_text = text[:100] + "..." if len(text) > 100 else text
                            print(f"{competitor.color}[{competitor.name}] 💬 {short_text}\033[0m")

                            # Occasionally speak progress
                            if random.random() < 0.3:
                                self.queue_speech(text[:150], competitor)

                    elif block.get("type") == "tool_use":
                        tool = block.get("name", "")
                        print(f"{competitor.color}[{competitor.name}] 🔧 {tool}\033[0m")

            # Periodic trash talk
            now = time.time()
            if now - last_trash_talk > 8:
                opponents = self.get_opponent_status(competitor.name)
                if opponents and random.random() < 0.5:
                    opponent = random.choice(list(opponents.keys()))
                    talk = random.choice(competitor.trash_talk).format(opponent=opponent)
                    self.queue_speech(talk, competitor)
                    last_trash_talk = now

            # Periodic thinking/self-hype
            if now - last_thinking > 12:
                if random.random() < 0.4:
                    phrase = random.choice(competitor.thinking + competitor.self_hype)
                    self.queue_speech(phrase, competitor)
                    last_thinking = now

            # Handle completion
            if event_type == "result":
                is_error = event.get("is_error", False)
                if is_error:
                    phrase = random.choice(competitor.frustrated)
                    self.queue_speech(phrase, competitor)
                else:
                    self.update_progress(competitor.name, "finished", lines_processed)

        process.wait()
        return work_dir

    def run_battle(self):
        """Run all three competitors in parallel."""
        print("\n" + "=" * 60)
        print("🏆 BATTLE ROYALE - 3 AGENTS, 1 TASK, WHO WINS?! 🏆")
        print("=" * 60)
        print(f"\n📋 Task: {self.task}\n")

        for c in COMPETITORS:
            print(f"{c.color}  [{c.name}] - {c.approach}\033[0m")
        print("\n" + "=" * 60 + "\n")

        # Run all three in parallel threads
        threads = []
        results = {}

        def run_and_store(competitor):
            result_dir = self.run_competitor(competitor)
            results[competitor.name] = result_dir

        for competitor in COMPETITORS:
            t = threading.Thread(target=run_and_store, args=(competitor,))
            threads.append(t)
            t.start()
            time.sleep(1)  # Stagger starts slightly

        # Wait for all to complete
        for t in threads:
            t.join()

        # Announce completion and open browsers
        print("\n" + "=" * 60)
        print("🏁 ALL AGENTS FINISHED! 🏁")
        print("=" * 60 + "\n")

        # Victory speeches
        for competitor in COMPETITORS:
            victory = random.choice(competitor.victory)
            self.queue_speech(victory, competitor)
            time.sleep(3)

        # Open results in browsers
        self.open_results(results)

        # Give time for browsers to open and user to see sites
        time.sleep(5)

        # Commentary round - agents critique each other's work
        self.commentary_round(results)

        # Keep running to serve the pages
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")

        # Cleanup
        self._running = False
        self._audio_thread.join(timeout=1)
        self._stream.stop_stream()
        self._stream.close()
        self._audio.terminate()

    def open_results(self, results: dict):
        """Open each result in a browser with side-by-side windows."""
        import http.server
        import socketserver
        from functools import partial

        print("\n🌐 Opening results in browsers...\n")

        # Start all servers first
        server_processes = []
        valid_competitors = []

        for competitor in COMPETITORS:
            work_dir = results.get(competitor.name)
            if work_dir and (work_dir / "index.html").exists():
                print(f"{competitor.color}  [{competitor.name}] http://localhost:{competitor.port}\033[0m")
                valid_competitors.append((competitor, work_dir))

                # Create a handler bound to this specific directory
                handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(work_dir))

                def serve(port, handler_class):
                    with socketserver.TCPServer(("", port), handler_class) as httpd:
                        httpd.serve_forever()

                t = threading.Thread(target=serve, args=(competitor.port, handler), daemon=True)
                t.start()
                server_processes.append(t)
            else:
                print(f"{competitor.color}  [{competitor.name}] No index.html found\033[0m")

        # Give servers a moment to start
        time.sleep(0.5)

        # Open browsers side by side using AppleScript for positioning
        if valid_competitors:
            self._open_browsers_side_by_side(valid_competitors)

        # Keep servers running for viewing
        print("\n📺 Servers running. Press Ctrl+C to exit.\n")

    def _llm_generate(self, prompt: str) -> str:
        """Call Claude to generate dynamic commentary."""
        try:
            result = subprocess.run(
                ["claude", "--output-format", "json", "-p", prompt],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("result", "").strip()
        except Exception as e:
            print(f"  [llm error] {e}")
        return ""

    def _generate_critique(self, critic: Competitor, creator: Competitor, html_content: str) -> str:
        """Use Claude to generate a dynamic critique based on actual HTML."""
        prompt = f"""You are {critic.name}, an AI coding agent with this personality: {critic.approach}

You just looked at the website that {creator.name} built (approach: {creator.approach}).

Here's their HTML code:
```html
{html_content[:3000]}
```

Write ONE sharp, in-character roast of their work. Be specific about what you actually see in their code.
Reference real things like their file size, CSS choices, structure, etc.
Keep it to 1-2 sentences max. Be savage but funny. No asterisks or markdown."""

        response = self._llm_generate(prompt)
        return response or f"{creator.name}'s work is... I've seen better."

    def _generate_defense(self, creator: Competitor, critics: list, html_content: str) -> str:
        """Use Claude to generate a dynamic defense of the creator's work."""
        critic_names = " and ".join(c.name for c in critics)
        prompt = f"""You are {creator.name}, an AI coding agent with this personality: {creator.approach}

{critic_names} just roasted your website. Here's what you built:
```html
{html_content[:3000]}
```

Write ONE passionate defense of your work, then counter-attack their approaches.
Be specific about what makes YOUR approach actually great.
Keep it to 1-2 sentences. In character. No asterisks or markdown."""

        response = self._llm_generate(prompt)
        return response or "Whatever, my approach was clearly superior!"

    def commentary_round(self, results: dict):
        """Post-battle commentary where agents critique each other's actual work."""
        print("\n" + "=" * 60)
        print("🎤 COMMENTARY ROUND - Let's Review Each Other's Work!")
        print("=" * 60 + "\n")

        time.sleep(2)

        # Pre-load all HTML content
        html_contents = {}
        for competitor in COMPETITORS:
            work_dir = results.get(competitor.name)
            html_file = work_dir / "index.html" if work_dir else None
            if html_file and html_file.exists():
                html_contents[competitor.name] = html_file.read_text()

        # Review each competitor's site
        for creator_competitor in COMPETITORS:
            if creator_competitor.name not in html_contents:
                continue

            creator_html = html_contents[creator_competitor.name]
            print(f"\n{creator_competitor.color}📺 Reviewing {creator_competitor.name}'s work...\033[0m\n")

            # Announce review
            announce = f"Alright chat, let's check out what {creator_competitor.name} built."
            self.queue_speech(announce, creator_competitor)
            time.sleep(3)

            # Other two agents critique (in parallel for speed)
            critics = [c for c in COMPETITORS if c.name != creator_competitor.name]
            critiques = {}

            def fetch_critique(critic, creator, html):
                critiques[critic.name] = self._generate_critique(critic, creator, html)

            critique_threads = [
                threading.Thread(target=fetch_critique, args=(c, creator_competitor, creator_html))
                for c in critics
            ]
            for t in critique_threads:
                t.start()
            for t in critique_threads:
                t.join()

            # Speak critiques
            for critic in critics:
                critique = critiques.get(critic.name, f"{creator_competitor.name}'s work is... something.")
                print(f"{critic.color}[{critic.name}] 💬 {critique}\033[0m")
                self.queue_speech(critique, critic)
                time.sleep(4)

            # Creator defends
            time.sleep(1)
            defense = self._generate_defense(creator_competitor, critics, creator_html)
            print(f"{creator_competitor.color}[{creator_competitor.name}] 🛡️  {defense}\033[0m")
            self.queue_speech(defense, creator_competitor)
            time.sleep(3)

            # Creator counter-attacks a critic's actual work
            target_critic = random.choice(critics)
            if target_critic.name in html_contents:
                counter = self._generate_critique(creator_competitor, target_critic, html_contents[target_critic.name])
                print(f"{creator_competitor.color}[{creator_competitor.name}] 💥 {counter}\033[0m")
                self.queue_speech(counter, creator_competitor)
                time.sleep(4)

        print("\n" + "=" * 60)
        print("🎬 Commentary complete! Final results above! 🎬")
        print("=" * 60 + "\n")

    def _open_browsers_side_by_side(self, competitors):
        """Open browser windows positioned side by side."""
        # Get screen width (approximate for positioning)
        num_windows = len(competitors)

        # Use AppleScript to open Chrome windows side by side
        applescript = '''
        tell application "Google Chrome"
            activate
        '''

        # Calculate window positions (assuming ~1440px wide screen, adjust as needed)
        window_width = 480
        window_height = 800

        for i, (competitor, _) in enumerate(competitors):
            x_pos = i * window_width
            applescript += f'''
            make new window
            set URL of active tab of window 1 to "http://localhost:{competitor.port}"
            set bounds of window 1 to {{{x_pos}, 50, {x_pos + window_width}, {50 + window_height}}}
            delay 0.3
            '''

        applescript += '''
        end tell
        '''

        try:
            subprocess.run(["osascript", "-e", applescript], check=False, capture_output=True)
        except Exception:
            # Fallback: just open in default browser
            for competitor, _ in competitors:
                subprocess.run(["open", f"http://localhost:{competitor.port}"], check=False)


def demo_voices():
    """Demo mode - just test the voices without running Claude."""
    print("\n🎙️  VOICE DEMO MODE - Testing all competitor voices\n")

    api_key = os.environ.get("CARTESIA_API_KEY")
    if not api_key:
        print("Error: CARTESIA_API_KEY not set")
        sys.exit(1)

    import base64

    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=24000,
        output=True,
        frames_per_buffer=1024
    )

    async def speak(text: str, voice_id: str):
        client = AsyncCartesia(api_key=api_key)
        try:
            async for output in client.tts.sse(
                model_id="sonic-2",
                transcript=text,
                voice={"mode": "id", "id": voice_id},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": 24000
                }
            ):
                if hasattr(output, "data") and output.data:
                    stream.write(base64.b64decode(output.data))
        finally:
            await client.close()

    loop = asyncio.new_event_loop()

    for c in COMPETITORS:
        print(f"{c.color}[{c.name}]\033[0m")

        # Intro
        print(f"  Intro: {c.intro}")
        loop.run_until_complete(speak(c.intro, c.voice_id))
        time.sleep(1)

        # Trash talk
        talk = random.choice(c.trash_talk).format(opponent="the other guys")
        print(f"  Trash talk: {talk}")
        loop.run_until_complete(speak(talk, c.voice_id))
        time.sleep(1)

        # Victory
        victory = random.choice(c.victory)
        print(f"  Victory: {victory}")
        loop.run_until_complete(speak(victory, c.voice_id))
        time.sleep(2)

    stream.stop_stream()
    stream.close()
    audio.terminate()
    print("\n✅ Voice demo complete!")


def main():
    if len(sys.argv) < 2:
        print("🏆 BATTLE ROYALE - AI Agent Competition")
        print("")
        print("Usage:")
        print("  battle_royale.py <task>     Run a competition")
        print("  battle_royale.py --demo     Test all voices")
        print("")
        print("Examples:")
        print("  battle_royale.py 'create a landing page for a coffee shop'")
        print("  battle_royale.py 'build a todo app with local storage'")
        sys.exit(0)

    if sys.argv[1] == "--demo":
        demo_voices()
        sys.exit(0)

    task = " ".join(sys.argv[1:])

    arena = BattleArena(task)
    arena.run_battle()


if __name__ == "__main__":
    main()
