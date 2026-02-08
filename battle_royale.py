#!/usr/bin/env python3
"""Battle Royale - AI agents compete on the same task with different approaches.

Pick 3 from 6 fighters in Street Fighter style, watch them code in real-time,
hear them trash-talk each other, and see HP drop during the commentary round.
"""

import asyncio
import base64
import http.server
import json
import os
import random
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, List

from cartesia import AsyncCartesia
import pyaudio


# Wrestling announcer voice (deep/dramatic)
ANNOUNCER_VOICE_ID = "ee5b6a37-8fb4-d49f-a1c1-8b3f71c0edcf"  # Deep announcer

PRINT_LOCK = threading.Lock()


def safe_print(msg: str, end: str = "\n"):
    with PRINT_LOCK:
        sys.stdout.write(msg + end)
        sys.stdout.flush()


@dataclass
class Competitor:
    name: str
    emoji: str
    approach: str
    voice_id: str
    port: int
    color: str
    tagline: str
    intro: List[str]
    thinking: List[str]
    trash_talk: List[str]
    self_hype: List[str]
    frustrated: List[str]
    victory: List[str]


ALL_COMPETITORS = [
    Competitor(
        name="ValleyGirl",
        emoji="💅",
        approach="make it super cute and aesthetic with pink colors, sparkles, and girly vibes - like, literally the cutest website ever",
        voice_id="b7d50908-b17c-442d-ad8d-810c63997ed9",
        port=8001,
        color="\033[95m",
        tagline="Aesthetic queen, like literally",
        intro=["Oh my GOD you guys, I am SO ready to make the cutest website EVER!",
               "Like, this is literally my moment to SLAY!"],
        thinking=["Okay but what if I add more pink?",
                  "This needs way more sparkles...",
                  "Oh em gee, I'm obsessed with this idea!"],
        trash_talk=["{opponent}'s site is SO boring. No offense but also full offense.",
                    "Um, {opponent}? That color scheme is literally tragic.",
                    "{opponent} is giving very much... basic. Like, yikes."],
        self_hype=["This is giving everything it needs to give!",
                   "Okay but this is literally SO cute I can't even!"],
        frustrated=["Okay that's like, SO annoying right now!",
                    "Ugh, why is this being difficult? I can't!"],
        victory=["Oh my GOD I literally WON! This is the best day ever!",
                 "Slay! I knew my aesthetic was superior! Like, obviously!"],
    ),
    Competitor(
        name="AnimeFan",
        emoji="⚡",
        approach="make it epic and dramatic like an anime opening - flashy effects, bold colors, maximum hype like a shonen protagonist",
        voice_id="498e7f37-7fa3-4e2c-b8e2-8b6e9276f956",
        port=8002,
        color="\033[93m",
        tagline="Ultimate protagonist energy",
        intro=["YES! The time has come to unleash my ultimate coding technique! This will be LEGENDARY!",
               "I have trained my whole life for this moment!"],
        thinking=["Calculating the optimal attack pattern...",
                  "This requires my FULL POWER!",
                  "The protagonist never gives up!"],
        trash_talk=["{opponent}! Your code is weaker than a filler episode!",
                    "WHAT?! {opponent} calls THAT a website? Pathetic!",
                    "{opponent} has the power level of a background character!"],
        self_hype=["PLUS ULTRA! Going beyond my limits!",
                   "This is my final form! MAXIMUM POWER!"],
        frustrated=["DARN IT! This bug is stronger than I thought!",
                    "I won't give up! A true hero never surrenders!"],
        victory=["VICTORY! Just as the prophecy foretold! I AM THE PROTAGONIST!",
                 "It is already over! My website reigns SUPREME!"],
    ),
    Competitor(
        name="SurferDude",
        emoji="🏄",
        approach="keep it chill and laid-back with ocean vibes, good colors, nothing too complicated - just mellow good-vibes-only mate",
        voice_id="41f3c367-e0a8-4a85-89e0-c27bae9c9b6d",
        port=8003,
        color="\033[96m",
        tagline="Chill vibes only, no stress",
        intro=["Yeah nah, let's just cruise through this one, no stress, good vibes only mate!",
               "Aw sweet, this'll be easy. Just gonna flow with it."],
        thinking=["Hmm yeah, that's pretty chill...",
                  "Just gonna go with the flow here...",
                  "No worries, she'll be right..."],
        trash_talk=["{opponent}'s site is way too hectic. Just chill bro.",
                    "Mate, {opponent} is trying way too hard. Bad vibes.",
                    "{opponent} needs to catch some waves and calm down."],
        self_hype=["Oh yeah, this is coming together real nice!",
                   "Stoked on how this is turning out, legend!"],
        frustrated=["Ah bugger, that's a bit of a bummer...",
                    "No dramas, we'll sort it. No stress."],
        victory=["Aw yeah legend! Good vibes won the day! Stoked!",
                 "That was choice mate! Surf's up, code's done!"],
    ),
    Competitor(
        name="GamerBro",
        emoji="🎮",
        approach="dark mode, neon accents, gaming aesthetic - edgy, high contrast, with gaming references and energy",
        voice_id="e3827ec5-697a-4b7c-9704-1a23041bbc51",  # Gamer voice
        port=8001,
        color="\033[92m",
        tagline="Skill issue if you can't read this",
        intro=["GG let's GO! This is gonna be no diff for me!",
               "Booting up, loading in, about to absolutely destroy this task!"],
        thinking=["Calculating the meta strat...",
                  "No one plays like this, big brain move incoming...",
                  "Speed bridging my way through this..."],
        trash_talk=["{opponent}'s code? Skill issue.",
                    "LOL {opponent} is literally inting right now.",
                    "{opponent} would get hard stuck in Bronze with that approach."],
        self_hype=["CLIP THAT! This is insane!",
                   "No diff, this is just too easy for me!"],
        frustrated=["WHAT?! This is actual trash! RAGE!",
                    "I'm not tilted, YOU'RE tilted!"],
        victory=["GG EZ! Literally no diff! Get rekt!",
                 "World record pace! I'm built different!"],
    ),
    Competitor(
        name="CorporateShill",
        emoji="💼",
        approach="clean enterprise SaaS aesthetic - professional, blue/white palette, lots of CTAs, synergized value propositions",
        voice_id="c45bc1d0-0571-4be7-a642-23b943e99611",  # Professional voice
        port=8002,
        color="\033[94m",
        tagline="Leveraging synergies since Q1",
        intro=["Per my last commit, I'm excited to leverage this opportunity to deliver stakeholder value.",
               "Let's circle back on this task and ideate a best-in-class solution."],
        thinking=["Synergizing the architecture...",
                  "Aligning the value proposition...",
                  "Leveraging key deliverables here..."],
        trash_talk=["{opponent} needs to circle back on that design. Not aligned with the vision.",
                    "With all due respect, {opponent}'s approach lacks enterprise scalability.",
                    "{opponent}'s code doesn't pass our quality gate. Full stop."],
        self_hype=["This is a best-in-class implementation!",
                   "Moving the needle with this one!"],
        frustrated=["This is a blocker on my critical path.",
                    "Let's take this offline and regroup."],
        victory=["Crushing KPIs! This is the deliverable stakeholders deserve!",
                 "Synergy achieved! The ROI on this speaks for itself!"],
    ),
    Competitor(
        name="GrandmaCozy",
        emoji="🧶",
        approach="warm, cozy, readable website - large text, cream and brown warm colors, like a comfy knitting blog with heart",
        voice_id="f785af04-229c-4a7c-b71b-f3194c7f08bb",  # Warm grandma voice
        port=8003,
        color="\033[97m",
        tagline="Made with love and cookie recipes",
        intro=["Oh how lovely, let me put on my reading glasses and get started dear!",
               "This reminds me of when I used to knit - one stitch at a time!"],
        thinking=["Now where did I put that CSS property...",
                  "Hmm, my grandson showed me this trick once...",
                  "Just like my apple pie recipe - patience dear!"],
        trash_talk=["Oh sweetie, {opponent}'s website is a bit... harsh on the eyes isn't it?",
                    "Now I don't want to be rude but {opponent}'s colors gave me a headache dear.",
                    "Bless {opponent}'s heart but that design needs some TLC."],
        self_hype=["Oh I'm quite pleased with how this is coming along!",
                   "My bridge club will love this!"],
        frustrated=["Oh dear, this isn't cooperating is it...",
                    "Well fiddle-dee-dee, let's try something else!"],
        victory=["Oh how wonderful! First place! Wait till I tell Dorothy!",
                 "Warm and cozy wins the race! Just like my cobbler!"],
    ),
]


class ProgressDisplay:
    """Thread-safe in-place ASCII progress bar renderer."""

    BAR_WIDTH = 25

    def __init__(self, competitors: List[Competitor]):
        self._competitors = competitors
        self._data = {c.name: {"status": "waiting", "events": 0} for c in competitors}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._lines_reserved = len(competitors) + 2  # header + bars + separator

    def start(self):
        safe_print("\n" + "─" * 60)
        safe_print("📊 LIVE PROGRESS")
        for c in self._competitors:
            safe_print(f"{c.color}  {c.name:15s} [{'░' * self.BAR_WIDTH}]   0 events\033[0m")
        safe_print("─" * 60)
        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def update(self, name: str, status: str, events: int):
        with self._lock:
            self._data[name] = {"status": status, "events": events}

    def _render_loop(self):
        while self._running:
            self._redraw()
            time.sleep(0.3)

    def _redraw(self):
        with PRINT_LOCK:
            # Move cursor up to the progress bars
            lines_up = self._lines_reserved
            sys.stdout.write(f"\033[{lines_up}A")
            sys.stdout.write("\033[2K" + "─" * 60 + "\n")
            sys.stdout.write("\033[2K📊 LIVE PROGRESS\n")
            with self._lock:
                for c in self._competitors:
                    d = self._data[c.name]
                    filled = min(self.BAR_WIDTH, d["events"] // 3)
                    bar = "█" * filled + "░" * (self.BAR_WIDTH - filled)
                    status = d["status"][:20]
                    line = f"  {c.name:15s} [{bar}] {d['events']:3d} events - {status}"
                    sys.stdout.write(f"\033[2K{c.color}{line}\033[0m\n")
            sys.stdout.write("\033[2K" + "─" * 60 + "\n")
            sys.stdout.flush()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)


DASHBOARD_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>⚔️ Battle Royale</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0a0a1a; color: #fff; font-family: 'Courier New', monospace; height: 100vh; display: flex; flex-direction: column; }}
.header {{ text-align: center; padding: 8px; background: linear-gradient(135deg, #1a1a3e, #2d1b69); font-size: 20px; font-weight: bold; letter-spacing: 3px; text-shadow: 0 0 20px gold; }}
.arena {{ display: flex; flex: 1; gap: 3px; padding: 3px; background: #111; }}
.panel {{ flex: 1; display: flex; flex-direction: column; position: relative; border: 2px solid #333; border-radius: 4px; overflow: hidden; }}
.hp-section {{ padding: 6px 10px; background: rgba(0,0,0,0.9); border-bottom: 1px solid #333; }}
.fighter-name {{ font-size: 13px; font-weight: bold; margin-bottom: 4px; display: flex; justify-content: space-between; }}
.hp-track {{ width: 100%; height: 14px; background: #1a1a1a; border-radius: 7px; overflow: hidden; border: 1px solid #333; }}
.hp-fill {{ height: 100%; border-radius: 7px; transition: width 0.4s ease, background-color 0.4s ease; }}
iframe {{ flex: 1; border: none; background: #fff; }}
.overlay {{ display: none; position: absolute; inset: 0; align-items: center; justify-content: center; flex-direction: column; z-index: 100; }}
.overlay.winner {{ display: flex; background: radial-gradient(ellipse, rgba(255,215,0,0.3) 0%, rgba(0,0,0,0.7) 100%); animation: pulse 1s infinite alternate; }}
.overlay.loser {{ display: flex; background: rgba(0,0,0,0.6); }}
.overlay-text {{ font-size: 48px; font-weight: bold; text-shadow: 0 0 30px currentColor; animation: flicker 0.5s infinite alternate; }}
.overlay-sub {{ font-size: 18px; margin-top: 10px; opacity: 0.8; }}
@keyframes pulse {{ from {{ box-shadow: inset 0 0 30px rgba(255,215,0,0.3); }} to {{ box-shadow: inset 0 0 60px rgba(255,215,0,0.6); }} }}
@keyframes flicker {{ from {{ opacity: 0.9; }} to {{ opacity: 1; }} }}
.damage-flash {{ animation: flash 0.3s; }}
@keyframes flash {{ 0% {{ background: rgba(255,0,0,0.5); }} 100% {{ background: transparent; }} }}
</style>
</head>
<body>
<div class="header">⚔️ BATTLE ROYALE — {task} ⚔️</div>
<div class="arena" id="arena"></div>
<script>
const competitors = {competitors_json};
const arena = document.getElementById('arena');
const prevHp = {{}};

competitors.forEach((c, i) => {{
    prevHp[c.name] = 100;
    arena.innerHTML += `
    <div class="panel" id="panel-${{c.name}}">
      <div class="hp-section" style="border-top: 3px solid ${{c.color}}">
        <div class="fighter-name" style="color: ${{c.color}}">
          <span>${{c.emoji}} ${{c.name}}</span>
          <span id="hp-text-${{c.name}}">❤️ 100</span>
        </div>
        <div class="hp-track">
          <div class="hp-fill" id="hp-bar-${{c.name}}" style="width:100%; background: ${{c.color}}"></div>
        </div>
      </div>
      <iframe src="http://localhost:${{c.port}}" id="frame-${{c.name}}"></iframe>
      <div class="overlay" id="overlay-${{c.name}}">
        <div class="overlay-text" id="overlay-text-${{c.name}}"></div>
        <div class="overlay-sub" id="overlay-sub-${{c.name}}"></div>
      </div>
    </div>`;
}});

async function poll() {{
    try {{
        const r = await fetch('/state');
        const state = await r.json();
        state.competitors.forEach(c => {{
            const hp = Math.max(0, c.hp);
            const bar = document.getElementById('hp-bar-' + c.name);
            const txt = document.getElementById('hp-text-' + c.name);
            const panel = document.getElementById('panel-' + c.name);
            if (bar) {{
                if (hp < prevHp[c.name]) {{
                    panel.classList.add('damage-flash');
                    setTimeout(() => panel.classList.remove('damage-flash'), 300);
                }}
                prevHp[c.name] = hp;
                bar.style.width = hp + '%';
                bar.style.backgroundColor = hp > 60 ? c.color : hp > 30 ? '#ffa500' : '#ff2200';
                txt.textContent = '❤️ ' + hp;
            }}
        }});
        if (state.winner) {{
            state.competitors.forEach(c => {{
                const overlay = document.getElementById('overlay-' + c.name);
                const txt = document.getElementById('overlay-text-' + c.name);
                const sub = document.getElementById('overlay-sub-' + c.name);
                if (c.name === state.winner) {{
                    overlay.classList.add('winner');
                    txt.textContent = '🏆 WINNER!';
                    txt.style.color = 'gold';
                    sub.textContent = c.name.toUpperCase();
                }} else {{
                    overlay.classList.add('loser');
                    txt.textContent = '💀';
                    txt.style.color = '#666';
                    sub.textContent = 'ELIMINATED';
                }}
            }});
        }}
    }} catch(e) {{}}
    setTimeout(poll, 500);
}}
poll();
</script>
</body>
</html>"""


class BattleArena:
    """Manages the battle royale between agents."""

    SAMPLE_RATE = 24000

    def __init__(self, task: str, competitors: List[Competitor]):
        self.task = task
        self.competitors = competitors
        self.arena_dir = Path("/tmp/battle_arena")
        self.arena_dir.mkdir(exist_ok=True)

        # HP tracking
        self.hp = {c.name: 100 for c in competitors}
        self.hp_lock = threading.Lock()
        self.winner = None

        # Shared progress state
        self.progress = {c.name: {"status": "starting", "events": 0} for c in competitors}
        self.progress_lock = threading.Lock()

        # Audio setup
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16, channels=1, rate=self.SAMPLE_RATE,
            output=True, frames_per_buffer=1024
        )
        self._audio_queue = Queue()
        self._audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._running = True
        self._audio_thread.start()

        self._client = None
        self._speech_queue = Queue()
        self._speech_thread = threading.Thread(target=self._speech_loop, daemon=True)
        self._speech_thread.start()

        self._progress_display = ProgressDisplay(competitors)

    def _audio_loop(self):
        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                self._stream.write(chunk)
            except Empty:
                continue

    def _speech_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self._running:
            try:
                text, voice_id, name, color = self._speech_queue.get(timeout=0.5)
                safe_print(f"{color}[{name}] 🎙️  {text}\033[0m")
                loop.run_until_complete(self._speak(text, voice_id))
                time.sleep(0.2)
            except Empty:
                continue

    async def _speak(self, text: str, voice_id: str):
        if not self._client:
            self._client = AsyncCartesia(api_key=os.environ.get("CARTESIA_API_KEY"))
        try:
            async for output in self._client.tts.sse(
                model_id="sonic-2", transcript=text,
                voice={"mode": "id", "id": voice_id},
                output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": self.SAMPLE_RATE}
            ):
                if hasattr(output, "data") and output.data:
                    self._audio_queue.put(base64.b64decode(output.data))
        except Exception as e:
            safe_print(f"  [tts error] {e}")

    def queue_speech(self, text: str, competitor: Competitor):
        self._speech_queue.put((text, competitor.voice_id, competitor.name, competitor.color))

    def queue_announcer(self, text: str):
        self._speech_queue.put((text, ANNOUNCER_VOICE_ID, "ANNOUNCER", "\033[91m"))

    def update_progress(self, name: str, status: str, events: int = 0):
        with self.progress_lock:
            self.progress[name] = {"status": status, "events": events}
        self._progress_display.update(name, status, events)

    def get_dashboard_state(self) -> dict:
        with self.hp_lock:
            hp_copy = dict(self.hp)
        with self.progress_lock:
            prog_copy = dict(self.progress)
        return {
            "competitors": [
                {"name": c.name, "hp": hp_copy.get(c.name, 100),
                 "status": prog_copy.get(c.name, {}).get("status", ""), "emoji": c.emoji}
                for c in self.competitors
            ],
            "winner": self.winner
        }

    def _apply_damage(self, name: str, amount: int):
        with self.hp_lock:
            self.hp[name] = max(0, self.hp[name] - amount)
        safe_print(f"  💥 {name} takes {amount} damage! HP: {self.hp[name]}")

    def _restore_hp(self, name: str, amount: int = 5):
        with self.hp_lock:
            self.hp[name] = min(100, self.hp[name] + amount)

    def _declare_winner(self) -> str:
        with self.hp_lock:
            winner_name = max(self.hp, key=self.hp.get)
            self.winner = winner_name
        return winner_name

    def run_competitor(self, competitor: Competitor):
        work_dir = self.arena_dir / competitor.name.lower()
        work_dir.mkdir(exist_ok=True)

        prompt = f"""Create a solution for: {self.task}

Your approach must be: {competitor.approach}

Work in the current directory. Create any files needed.
Save the main page as index.html. Be decisive and execute quickly."""

        cmd = ["claude", "--output-format", "stream-json", "--verbose",
               "--dangerously-skip-permissions", "-p", prompt]

        intro = random.choice(competitor.intro)
        self.queue_speech(intro, competitor)
        time.sleep(1.5)

        process = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, cwd=str(work_dir)
        )

        self.update_progress(competitor.name, "coding", 0)

        events = 0
        last_trash = time.time()
        last_hype = time.time()

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
            events += 1
            self.update_progress(competitor.name, "coding", events)

            if event_type == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text and len(text) > 30:
                            safe_print(f"{competitor.color}[{competitor.name}] 💬 {text[:120]}\033[0m")
                            if random.random() < 0.25:
                                self.queue_speech(text[:120], competitor)
                    elif block.get("type") == "tool_use":
                        safe_print(f"{competitor.color}[{competitor.name}] 🔧 {block.get('name')}\033[0m")

            now = time.time()
            if now - last_trash > 10 and random.random() < 0.4:
                with self.progress_lock:
                    opponents = [k for k in self.progress if k != competitor.name]
                if opponents:
                    opp = random.choice(opponents)
                    talk = random.choice(competitor.trash_talk).format(opponent=opp)
                    self.queue_speech(talk, competitor)
                    last_trash = now

            if now - last_hype > 15 and random.random() < 0.3:
                phrase = random.choice(competitor.thinking + competitor.self_hype)
                self.queue_speech(phrase, competitor)
                last_hype = now

            if event_type == "result":
                if event.get("is_error"):
                    self.queue_speech(random.choice(competitor.frustrated), competitor)
                else:
                    self.update_progress(competitor.name, "finished ✓", events)

        process.wait()
        return work_dir

    def _llm_generate(self, prompt: str) -> str:
        try:
            result = subprocess.run(
                ["claude", "--output-format", "json", "-p", prompt],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return json.loads(result.stdout).get("result", "").strip()
        except Exception as e:
            safe_print(f"  [llm error] {e}")
        return ""

    def _generate_critique(self, critic: Competitor, creator: Competitor, html: str) -> str:
        if critic.name == creator.name:
            return ""
        prompt = f"""You are {critic.name}. Personality: {critic.approach}

Roast {creator.name}'s HTML in ONE sentence under 15 words. Reference their actual code. Stay in character. English only. No quotes or markdown.

Their code:
{html[:2000]}"""
        return self._llm_generate(prompt).strip("\"'") or f"{creator.name}'s work is mid."

    def _generate_defense(self, creator: Competitor, critics: List[Competitor], html: str) -> str:
        names = " and ".join(c.name for c in critics)
        prompt = f"""You are {creator.name}. Personality: {creator.approach}

{names} roasted you. Defend in ONE sentence under 15 words. Reference your actual code. Stay in character. English only. No quotes or markdown.

Your code:
{html[:2000]}"""
        return self._llm_generate(prompt).strip("\"'") or "My approach was clearly superior!"

    def _score_damage(self, critique: str) -> int:
        prompt = f"""Rate how savage this critique is from 1-10. Respond with a single integer only.

"{critique}" """
        try:
            score = int(self._llm_generate(prompt).strip())
            return max(1, min(10, score)) * 3
        except (ValueError, TypeError):
            return 9  # default

    def start_dashboard(self):
        """Start HTTP dashboard server on port 8000."""
        arena_ref = self
        comp_data = [{"name": c.name, "emoji": c.emoji, "color": c.color.replace("\033[", "\\033["),
                      "port": c.port} for c in self.competitors]

        # Build proper color mapping for JS (ANSI -> CSS color)
        color_map = {
            "\033[95m": "#ff79c6", "\033[93m": "#f1fa8c", "\033[96m": "#8be9fd",
            "\033[92m": "#50fa7b", "\033[94m": "#6272a4", "\033[97m": "#f8f8f2",
        }
        js_comps = [{"name": c.name, "emoji": c.emoji,
                     "color": color_map.get(c.color, "#ffffff"), "port": c.port}
                    for c in self.competitors]

        dashboard_html = DASHBOARD_HTML_TEMPLATE.format(
            task=self.task,
            competitors_json=json.dumps(js_comps)
        )

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/state":
                    body = json.dumps(arena_ref.get_dashboard_state()).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    body = dashboard_html.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(body)

            def log_message(self, *args):
                pass

        def serve():
            with http.server.ThreadingHTTPServer(("", 8000), Handler) as s:
                s.serve_forever()

        t = threading.Thread(target=serve, daemon=True)
        t.start()

    def start_competitor_servers(self, results: dict):
        """Start HTTP servers for each competitor's site."""
        for competitor in self.competitors:
            work_dir = results.get(competitor.name)
            if work_dir and (work_dir / "index.html").exists():
                handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(work_dir))

                def serve(port, h):
                    with http.server.ThreadingHTTPServer(("", port), h) as s:
                        s.serve_forever()

                t = threading.Thread(target=serve, args=(competitor.port, handler), daemon=True)
                t.start()

    def commentary_round(self, results: dict):
        safe_print("\n" + "═" * 60)
        safe_print("🎤 COMMENTARY ROUND - Let's Review Each Other's Work!")
        safe_print("═" * 60 + "\n")
        time.sleep(2)

        html_contents = {}
        for c in self.competitors:
            wd = results.get(c.name)
            if wd and (wd / "index.html").exists():
                html_contents[c.name] = (wd / "index.html").read_text()

        for creator in self.competitors:
            if creator.name not in html_contents:
                continue
            creator_html = html_contents[creator.name]
            safe_print(f"\n{creator.color}📺 Reviewing {creator.name}'s work...\033[0m\n")

            self.queue_speech(f"Let's see what {creator.name} built!", creator)
            time.sleep(2)

            critics = [c for c in self.competitors if c.name != creator.name]
            critiques = {}
            damages = {}

            def fetch(critic, creator_c, html, name):
                c_text = self._generate_critique(critic, creator_c, html)
                critiques[name] = c_text
                damages[name] = self._score_damage(c_text)

            threads = [threading.Thread(target=fetch, args=(c, creator, creator_html, c.name))
                       for c in critics]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            for critic in critics:
                critique = critiques.get(critic.name, "No comment.")
                dmg = damages.get(critic.name, 9)
                safe_print(f"{critic.color}[{critic.name}] 💬 {critique}\033[0m")
                self.queue_speech(critique, critic)
                time.sleep(0.5)
                self._apply_damage(creator.name, dmg)
                time.sleep(2.5)

            defense = self._generate_defense(creator, critics, creator_html)
            safe_print(f"{creator.color}[{creator.name}] 🛡️  {defense}\033[0m")
            self.queue_speech(defense, creator)
            self._restore_hp(creator.name, 5)
            time.sleep(3)

            target = random.choice(critics)
            if target.name in html_contents:
                counter = self._generate_critique(creator, target, html_contents[target.name])
                dmg = self._score_damage(counter)
                safe_print(f"{creator.color}[{creator.name}] 💥 {counter}\033[0m")
                self.queue_speech(counter, creator)
                self._apply_damage(target.name, dmg)
                time.sleep(3)

        safe_print("\n" + "═" * 60)
        safe_print("🎬 Commentary complete!")
        safe_print("═" * 60 + "\n")

    def run_battle(self):
        safe_print("\n" + "═" * 60)
        safe_print("🏆 BATTLE ROYALE - 3 AGENTS, 1 TASK, WHO WINS?! 🏆")
        safe_print("═" * 60)
        safe_print(f"\n📋 Task: {self.task}\n")
        for c in self.competitors:
            safe_print(f"{c.color}  {c.emoji} [{c.name}] - {c.approach[:60]}\033[0m")
        safe_print("\n" + "═" * 60 + "\n")

        self._progress_display.start()

        threads = []
        results = {}

        def run_and_store(competitor):
            results[competitor.name] = self.run_competitor(competitor)

        for c in self.competitors:
            t = threading.Thread(target=run_and_store, args=(c,))
            threads.append(t)
            t.start()
            time.sleep(1)

        for t in threads:
            t.join()

        self._progress_display.stop()

        safe_print("\n" + "═" * 60)
        safe_print("🏁 ALL AGENTS FINISHED CODING!")
        safe_print("═" * 60 + "\n")

        for c in self.competitors:
            self.queue_speech(random.choice(c.victory), c)
            time.sleep(2.5)

        # Start servers and open dashboard
        self.start_competitor_servers(results)
        self.start_dashboard()
        time.sleep(1)

        safe_print("\n🌐 Dashboard: http://localhost:8000\n")
        self._open_dashboard()

        time.sleep(4)

        # Commentary round with HP damage
        self.commentary_round(results)

        # Declare winner
        winner_name = self._declare_winner()
        winner_comp = next(c for c in self.competitors if c.name == winner_name)

        safe_print("\n" + "═" * 60)
        safe_print(f"🏆 WINNER: {winner_comp.emoji} {winner_name.upper()} 🏆")
        safe_print("═" * 60)
        with self.hp_lock:
            for c in self.competitors:
                safe_print(f"  {c.color}{c.name}: {self.hp[c.name]} HP remaining\033[0m")

        announcement = (f"LADIES AND GENTLEMEN... after an INCREDIBLE battle... "
                        f"the winner with {self.hp[winner_name]} HP remaining... "
                        f"IT IS... {winner_name.upper()}!! WHAT A PERFORMANCE TONIGHT!")
        self.queue_announcer(announcement)
        time.sleep(5)
        self.queue_speech(random.choice(winner_comp.victory), winner_comp)

        # Keep servers running
        safe_print("\n📺 Servers running at http://localhost:8000 - Press Ctrl+C to exit\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            safe_print("\n\n👋 Shutting down...")

        self._running = False
        self._audio_thread.join(timeout=1)
        self._stream.stop_stream()
        self._stream.close()
        self._audio.terminate()

    def _open_dashboard(self):
        try:
            subprocess.run(["open", "http://localhost:8000"], check=False)
        except Exception:
            pass


def character_select() -> List[Competitor]:
    """Street Fighter style character selection from terminal."""
    safe_print("\n" + "╔" + "═" * 58 + "╗")
    safe_print("║" + " " * 15 + "🎮  SELECT YOUR FIGHTERS  🎮" + " " * 15 + "║")
    safe_print("╠" + "═" * 58 + "╣")

    # Display characters in 2 columns
    for i in range(0, len(ALL_COMPETITORS), 2):
        left = ALL_COMPETITORS[i]
        right = ALL_COMPETITORS[i + 1] if i + 1 < len(ALL_COMPETITORS) else None
        left_str = f"  [{i+1}] {left.emoji} {left.name:12s} {left.tagline[:22]}"
        if right:
            right_str = f"  [{i+2}] {right.emoji} {right.name:12s} {right.tagline[:22]}"
            safe_print(f"║{left.color}{left_str:30s}\033[0m {right.color}{right_str:28s}\033[0m║")
        else:
            safe_print(f"║{left.color}{left_str:30s}\033[0m" + " " * 29 + "║")

    safe_print("╚" + "═" * 58 + "╝")

    while True:
        try:
            raw = input("\nSelect 3 fighters by number (e.g. 1 3 5): ").strip()
            picks = list(dict.fromkeys(int(x) for x in raw.split()))  # unique, ordered
            if len(picks) != 3 or not all(1 <= p <= len(ALL_COMPETITORS) for p in picks):
                safe_print(f"  ⚠️  Pick exactly 3 unique numbers from 1-{len(ALL_COMPETITORS)}")
                continue
        except (ValueError, EOFError):
            safe_print("  ⚠️  Enter numbers separated by spaces")
            continue

        selected = [ALL_COMPETITORS[p - 1] for p in picks]
        for i, comp in enumerate(selected):
            comp.port = 8001 + i

        safe_print("\n" + "─" * 60)
        safe_print("⚔️  YOUR FIGHTERS:")
        for c in selected:
            safe_print(f"  {c.color}{c.emoji} {c.name} — {c.tagline}\033[0m")
        safe_print("─" * 60)

        confirm = input("\nFight? [Y/n]: ").strip().lower()
        if confirm in ("", "y", "yes"):
            return selected
        safe_print("  Re-selecting...\n")


def demo_voices():
    """Demo mode - test all 6 voices."""
    safe_print("\n🎙️  VOICE DEMO - Testing all fighters\n")
    api_key = os.environ.get("CARTESIA_API_KEY")
    if not api_key:
        safe_print("Error: CARTESIA_API_KEY not set")
        sys.exit(1)

    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True, frames_per_buffer=1024)

    async def speak(text, voice_id):
        client = AsyncCartesia(api_key=api_key)
        try:
            async for output in client.tts.sse(
                model_id="sonic-2", transcript=text, voice={"mode": "id", "id": voice_id},
                output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": 24000}
            ):
                if hasattr(output, "data") and output.data:
                    stream.write(base64.b64decode(output.data))
        finally:
            await client.close()

    loop = asyncio.new_event_loop()
    for c in ALL_COMPETITORS:
        safe_print(f"{c.color}{c.emoji} [{c.name}]\033[0m")
        phrase = random.choice(c.intro)
        safe_print(f"  {phrase}")
        loop.run_until_complete(speak(phrase, c.voice_id))
        time.sleep(0.8)

    safe_print(f"\n\033[91m[ANNOUNCER]\033[0m")
    announcement = "LADIES AND GENTLEMEN, welcome to BATTLE ROYALE! Let the coding begin!"
    safe_print(f"  {announcement}")
    loop.run_until_complete(speak(announcement, ANNOUNCER_VOICE_ID))

    stream.stop_stream()
    stream.close()
    audio.terminate()
    safe_print("\n✅ Voice demo complete!")


def main():
    if len(sys.argv) < 2:
        safe_print("🏆 BATTLE ROYALE - AI Agent Competition")
        safe_print("")
        safe_print("Usage:")
        safe_print("  battle_royale.py <task>     Run a competition (select fighters interactively)")
        safe_print("  battle_royale.py --demo     Test all voices")
        safe_print("")
        safe_print("Examples:")
        safe_print("  battle_royale.py 'create a landing page for a coffee shop'")
        sys.exit(0)

    if sys.argv[1] == "--demo":
        demo_voices()
        sys.exit(0)

    task = " ".join(sys.argv[1:])

    # Character select
    selected = character_select()

    arena = BattleArena(task, selected)
    arena.run_battle()


if __name__ == "__main__":
    main()
