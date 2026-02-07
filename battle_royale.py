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
        name="SpeedDemon",
        approach="fastest, minimal approach - just get it working ASAP",
        voice_id="b0689631-eee7-4a6c-bb86-195f1d267c2e",  # Emilio
        port=8001,
        color="\033[91m",  # Red
        intro="Speed is KING baby! Watch me smoke these slowpokes!",
        thinking=[
            "Going fast, no brakes!",
            "Speedrun strats activated!",
            "They're still thinking, I'm already DOING!",
        ],
        trash_talk=[
            "Oh look, {opponent} is still setting up. Cute.",
            "Yo {opponent}, you gonna start or what?",
            "{opponent} out here writing a novel, I'm shipping code!",
            "Is {opponent} even trying? I'm lapping them!",
        ],
        self_hype=[
            "TOO FAST TOO FURIOUS!",
            "They can't keep up!",
            "Built different, move different!",
        ],
        frustrated=[
            "Okay okay, minor speed bump!",
            "That cost me like 2 seconds, whatever!",
        ],
        victory=[
            "FIRST PLACE BABY! Was there ever any doubt?!",
            "Speedrun complete! GG no re!",
        ],
    ),
    Competitor(
        name="Architect",
        approach="clean, well-structured approach with proper organization and best practices",
        voice_id="87286a8d-7ea7-4235-a41a-dd9fa6630feb",  # Henry
        port=8002,
        color="\033[92m",  # Green
        intro="Quality over speed. Let me show you how professionals do it.",
        thinking=[
            "Planning the architecture...",
            "This needs proper structure...",
            "Doing it right the first time...",
        ],
        trash_talk=[
            "{opponent}'s code is gonna be spaghetti, guaranteed.",
            "Sure {opponent}, ship fast and break things. Very original.",
            "{opponent} will be debugging that mess for hours.",
            "I'll be maintaining my code while {opponent} rewrites theirs.",
        ],
        self_hype=[
            "Clean code, clean mind.",
            "This is textbook perfect.",
            "Future me will thank present me.",
        ],
        frustrated=[
            "Hmm, unexpected. Let me refactor.",
            "Even the best plans need adjustment.",
        ],
        victory=[
            "And THAT is how you build software that lasts.",
            "Quality wins. Always has, always will.",
        ],
    ),
    Competitor(
        name="Wildcard",
        approach="creative, unconventional approach - try something unexpected and innovative",
        voice_id="e07c00bc-4134-4eae-9ea4-1a55fb45746b",  # Brooke
        port=8003,
        color="\033[94m",  # Blue
        intro="Boring solutions are for boring people. Watch me get creative!",
        thinking=[
            "What if I tried something completely different...",
            "Everyone else is zigging, I'm zagging!",
            "The unconventional path is MY path!",
        ],
        trash_talk=[
            "{opponent} is so predictable, yawn.",
            "Oh {opponent} doing the obvious thing? Shocking.",
            "While {opponent} follows tutorials, I'm innovating!",
            "{opponent}'s solution is what ChatGPT would write.",
        ],
        self_hype=[
            "Nobody's gonna see this coming!",
            "Innovation station, baby!",
            "This is actually genius if I do say so myself!",
        ],
        frustrated=[
            "Okay that was TOO creative, let me dial it back!",
            "The line between genius and chaos is thin!",
        ],
        victory=[
            "See?! Creativity WINS! Take notes everyone!",
            "They doubted the vision. They were WRONG!",
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

    def _analyze_site(self, html_path: Path) -> dict:
        """Analyze a site to extract features for dynamic commentary."""
        try:
            html_content = html_path.read_text()

            # Extract key characteristics
            analysis = {
                "file_size": len(html_content),
                "has_css": "<style>" in html_content or "stylesheet" in html_content,
                "has_js": "<script>" in html_content,
                "has_images": "<img" in html_content,
                "has_framework": any(fw in html_content.lower() for fw in ["react", "vue", "bootstrap", "tailwind"]),
                "line_count": len(html_content.split("\n")),
                "has_comments": "<!--" in html_content,
                "uses_inline_styles": "style=" in html_content,
                "external_files": html_content.count('href="') + html_content.count('src="'),
            }

            # Determine approach style
            if analysis["line_count"] < 50 and not analysis["external_files"]:
                analysis["style"] = "minimal"
            elif analysis["has_comments"] and analysis["external_files"] > 3:
                analysis["style"] = "organized"
            elif analysis["has_framework"]:
                analysis["style"] = "modern"
            else:
                analysis["style"] = "custom"

            return analysis
        except Exception:
            return {"style": "unknown", "file_size": 0, "line_count": 0}

    def _generate_critique(self, critic: Competitor, creator: Competitor, analysis: dict) -> str:
        """Generate dynamic critique based on actual site features."""
        critiques = []

        # SpeedDemon critiques
        if critic.name == "SpeedDemon":
            if analysis["line_count"] > 100:
                critiques.extend([
                    f"{creator.name} wrote {analysis['line_count']} lines? I did mine in like 30! Efficiency!",
                    f"Look at this file size! {creator.name} is out here writing essays!",
                ])
            if analysis["external_files"] > 3:
                critiques.append(f"{creator.name} has {analysis['external_files']} files! Over-engineering much?")
            if analysis["has_framework"]:
                critiques.append(f"Oh wow, {creator.name} pulled in a whole framework. I kept it LEAN!")
            if analysis["file_size"] > 2000:
                critiques.append(f"{creator.name}'s file is {analysis['file_size']} bytes? Mine loaded in 0.001 seconds!")
            if not critiques:
                critiques.append(f"{creator.name}'s code is bloated. Mine shipped faster AND lighter!")

        # Architect critiques
        elif critic.name == "Architect":
            if analysis["line_count"] < 50:
                critiques.append(f"{creator.name}'s solution is {analysis['line_count']} lines? Where's the structure?")
            if not analysis["has_css"]:
                critiques.extend([
                    f"No stylesheets? {creator.name}, this isn't 1995!",
                    f"{creator.name} skipped CSS entirely. Amateur hour.",
                ])
            if analysis["uses_inline_styles"]:
                critiques.append(f"Inline styles everywhere! {creator.name}, ever heard of separation of concerns?")
            if not analysis["has_comments"]:
                critiques.append(f"I see zero documentation. Good luck maintaining that mess, {creator.name}!")
            if analysis["external_files"] < 2:
                critiques.append(f"{creator.name} crammed everything into one file. That's not maintainable!")
            if not critiques:
                critiques.append(f"{creator.name}'s code is gonna be tech debt in a week. Calling it now.")

        # Wildcard critiques
        elif critic.name == "Wildcard":
            if analysis["style"] == "minimal":
                critiques.extend([
                    f"{creator.name} took the BORING path. Zero creativity!",
                    f"This is the most generic solution I've ever seen, {creator.name}.",
                ])
            if not analysis["has_js"]:
                critiques.append(f"No JavaScript? {creator.name} made a static page in 2026. Groundbreaking.")
            if analysis["has_framework"]:
                critiques.append(f"{creator.name} used a framework everybody uses. How... ordinary.")
            if analysis["line_count"] < 100 and not analysis["has_js"]:
                critiques.append(f"{creator.name}'s site looks like a basic tutorial. Where's the innovation?")
            if not critiques:
                critiques.append(f"I looked at {creator.name}'s code and yawned. So predictable!")

        return random.choice(critiques) if critiques else f"{creator.name}'s work is... fine, I guess. Nothing special."

    def _generate_defense(self, creator: Competitor, critics: list, analysis: dict) -> str:
        """Generate dynamic defense based on the creator's personality and what they built."""
        defenses = []

        # SpeedDemon defenses
        if creator.name == "SpeedDemon":
            if analysis["line_count"] < 50:
                defenses.extend([
                    f"Simple is FAST! You guys were still architecting while I was SHIPPING!",
                    f"{analysis['line_count']} lines of pure efficiency! No bloat!",
                ])
            if analysis["file_size"] < 1500:
                defenses.extend([
                    f"My site is {analysis['file_size']} bytes and loads INSTANTLY!",
                    f"Performance matters! My bundle size is MICROSCOPIC!",
                ])
            if analysis["external_files"] < 2:
                defenses.append(f"One file, zero dependencies, pure speed!")
            defenses.extend([
                f"I FINISHED FIRST! Speed is a feature! Talk all you want!",
                f"Working software beats perfect architecture EVERY TIME!",
            ])

        # Architect defenses
        elif creator.name == "Architect":
            if analysis["has_comments"]:
                defenses.extend([
                    f"My code is self-documenting! Yours is a mystery box!",
                    f"I wrote comments because I care about the NEXT developer!",
                ])
            if analysis["external_files"] > 2:
                defenses.extend([
                    f"Proper separation of concerns! Unlike you cowboys!",
                    f"Modular design! Each file has ONE responsibility!",
                ])
            if analysis["line_count"] > 100:
                defenses.extend([
                    f"Quality takes space! I'm not hacking together garbage!",
                    f"{analysis['line_count']} lines of professional-grade code!",
                ])
            if analysis["has_css"]:
                defenses.append(f"Styled properly with actual CSS! Not inline chaos!")
            defenses.extend([
                f"This follows industry best practices! Read a book!",
                f"My code will be maintainable in a YEAR! Can you say the same?",
            ])

        # Wildcard defenses
        elif creator.name == "Wildcard":
            defenses.extend([
                f"Of COURSE you don't get it! Genius looks like madness to the mediocre!",
                f"I tried something DIFFERENT! While you copy-pasted Stack Overflow!",
                f"Innovation means taking risks! You played it safe and BORING!",
            ])
            if analysis["has_js"]:
                defenses.extend([
                    f"My JavaScript is doing things you didn't even THINK were possible!",
                    f"Check the console! I added easter eggs you'll never find!",
                ])
            if analysis["style"] == "custom":
                defenses.append(f"Custom everything! No frameworks, pure creativity!")
            defenses.extend([
                f"Boring people make boring sites! Mirror check, team!",
                f"At least MY site has PERSONALITY! Yours is template garbage!",
            ])

        return random.choice(defenses) if defenses else "Whatever, I like what I built!"

    def commentary_round(self, results: dict):
        """Post-battle commentary where agents critique each other's actual work."""
        print("\n" + "=" * 60)
        print("🎤 COMMENTARY ROUND - Let's Review Each Other's Work!")
        print("=" * 60 + "\n")

        time.sleep(2)

        # Review each competitor's site
        for creator_competitor in COMPETITORS:
            work_dir = results.get(creator_competitor.name)
            html_file = work_dir / "index.html" if work_dir else None

            if not html_file or not html_file.exists():
                continue

            # Analyze the site
            analysis = self._analyze_site(html_file)

            print(f"\n{creator_competitor.color}📺 Reviewing {creator_competitor.name}'s work...\033[0m\n")

            # Announce review
            announce = f"Alright, let's take a look at what {creator_competitor.name} built."
            self.queue_speech(announce, COMPETITORS[0])  # Neutral announcement
            time.sleep(3)

            # Other two agents critique
            critics = [c for c in COMPETITORS if c.name != creator_competitor.name]

            for critic in critics:
                critique = self._generate_critique(critic, creator_competitor, analysis)
                print(f"{critic.color}[{critic.name}] 💬 {critique}\033[0m")
                self.queue_speech(critique, critic)
                time.sleep(4)

            # Creator defends and counter-attacks
            time.sleep(1)
            defense = self._generate_defense(creator_competitor, critics, analysis)
            print(f"{creator_competitor.color}[{creator_competitor.name}] 🛡️  {defense}\033[0m")
            self.queue_speech(defense, creator_competitor)
            time.sleep(3)

            # Random smack talk back at one of the critics
            target_critic = random.choice(critics)
            target_dir = results.get(target_critic.name)
            if target_dir and (target_dir / "index.html").exists():
                target_analysis = self._analyze_site(target_dir / "index.html")
                counter = self._generate_critique(creator_competitor, target_critic, target_analysis)
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
