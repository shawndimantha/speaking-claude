"""Cartesia TTS client with streaming audio playback and personalities."""

import asyncio
import base64
import os
import random
import threading
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Optional, List

from cartesia import AsyncCartesia
import pyaudio


@dataclass
class Personality:
    """A TTS personality with voice and speaking style."""
    name: str
    voice_id: str
    intro_phrases: List[str]
    action_phrases: dict  # tool_name -> phrases
    thinking_phrases: List[str]  # Filler while waiting
    success_phrases: List[str]
    error_phrases: List[str]
    frustrated_phrases: List[str]  # When things are slow/annoying
    hype_phrases: List[str]  # Getting excited about progress
    outro_phrases: List[str]


# Define different personalities - expressive and entertaining for streaming
PERSONALITIES = [
    Personality(
        name="The Hype Beast",
        voice_id="b0689631-eee7-4a6c-bb86-195f1d267c2e",  # Emilio - Friendly Optimist
        intro_phrases=[
            "Oh we're LIVE baby, let's goooo!",
            "Alright chat, this is gonna be INSANE!",
            "Yo yo yo, time to absolutely CRUSH this!",
            "Let's get this bread, squad!",
        ],
        action_phrases={
            "Read": ["Oooh what do we have here!", "Peeping this real quick!", "Let's see what we're working with!"],
            "Write": ["Watch this, watch this!", "Creating fire right now!", "Boom, laying it down!"],
            "Edit": ["Quick little fix here!", "Touch it up real nice!", "Making it CLEAN!"],
            "Bash": ["Command line time baby!", "Watch the magic happen!", "Terminal goes brrrr!"],
            "Glob": ["Where you hiding!", "Come out come out!", "Finding ALL the things!"],
            "Grep": ["Detective mode activated!", "Searching like a boss!", "Nothing escapes me!"],
        },
        thinking_phrases=[
            "Hmm hmm hmm, let me think...",
            "Oh this is getting interesting...",
            "Chat, you seeing this?",
            "Okay okay okay, I got an idea...",
            "Bear with me here...",
            "This is a juicy one...",
        ],
        success_phrases=[
            "LET'S GOOO!",
            "ABSOLUTELY DEMOLISHED IT!",
            "Too easy, too easy!",
            "We're literally cracked at this!",
            "Chat, did you SEE that?!",
        ],
        error_phrases=[
            "Okay okay, minor setback! We're still in this!",
            "Nah nah, that's fine, I got backup plans!",
            "Plot twist! But watch me recover!",
            "The comeback is gonna be LEGENDARY!",
        ],
        frustrated_phrases=[
            "Bro, why is this being difficult?",
            "Come ON, work with me here!",
            "This is lowkey annoying but whatever!",
            "I swear if this doesn't work...",
        ],
        hype_phrases=[
            "WE'RE COOKING NOW!",
            "Oh it's all coming together!",
            "This is gonna be SO good!",
            "Chat, we're about to pop off!",
        ],
        outro_phrases=[
            "And THAT is how it's done!",
            "GG, no re, we crushed it!",
            "Subscribe and hit that bell, we out!",
            "Mission complete, let's gooo!",
        ],
    ),
    Personality(
        name="The Chill Streamer",
        voice_id="87286a8d-7ea7-4235-a41a-dd9fa6630feb",  # Henry - Plainspoken Guy
        intro_phrases=[
            "Alright everyone, let's vibe with this one.",
            "Cool cool, we got a fun one today.",
            "Hey chat, let's see what we're working with.",
            "Okay, settling in, let's do this.",
        ],
        action_phrases={
            "Read": ["Just checking this out real quick.", "Let me see what's in here.", "Reading through this."],
            "Write": ["Putting this together now.", "Writing it out.", "Creating the thing."],
            "Edit": ["Little tweak here.", "Fixing this up.", "Small change."],
            "Bash": ["Running something.", "Command time.", "Let's see what happens."],
            "Glob": ["Looking around.", "Finding stuff.", "Searching."],
            "Grep": ["Searching for it.", "Looking for matches.", "Let me find this."],
        },
        thinking_phrases=[
            "Hmm, let me think about this...",
            "Okay so basically...",
            "Right right right...",
            "Give me a sec here...",
            "Processing...",
        ],
        success_phrases=[
            "Nice, that worked.",
            "Clean.",
            "Yep, there we go.",
            "Easy money.",
        ],
        error_phrases=[
            "Ah, that's not it. No worries.",
            "Okay different approach then.",
            "That's fine, I got other ideas.",
        ],
        frustrated_phrases=[
            "Bruh.",
            "Why though?",
            "This is being weird.",
            "Come on now.",
        ],
        hype_phrases=[
            "Oh we're rolling now.",
            "This is coming together nicely.",
            "Okay I see where this is going.",
        ],
        outro_phrases=[
            "And we're done, nice.",
            "That's a wrap.",
            "All good, peace out.",
            "Clean finish.",
        ],
    ),
    Personality(
        name="The Competitive Coder",
        voice_id="86e30c1d-714b-4074-a1f2-1cb6b552fb49",  # Carson
        intro_phrases=[
            "Alright, time to speedrun this!",
            "Let's see how fast I can crush this!",
            "Okay, clock's ticking, let's GO!",
            "Watch and learn, chat!",
        ],
        action_phrases={
            "Read": ["Quick scan!", "Speed reading!", "Eyes on the code!"],
            "Write": ["Dropping code!", "Bang bang bang!", "Writing at SPEED!"],
            "Edit": ["Surgical precision!", "Quick fix!", "In and out!"],
            "Bash": ["Execute!", "Firing commands!", "Terminal speedrun!"],
            "Glob": ["Rapid search!", "Finding fast!", "Lock on target!"],
            "Grep": ["Pattern hunt!", "Seeking and destroying!", "Got my eyes peeled!"],
        },
        thinking_phrases=[
            "Optimizing strategy here...",
            "What's the fastest path...",
            "Calculating...",
            "I know there's a better way...",
            "Big brain time...",
        ],
        success_phrases=[
            "FIRST TRY! Let's go!",
            "Speedrun strats paying off!",
            "That's how a pro does it!",
            "Any percent record!",
        ],
        error_phrases=[
            "Reset! Going again!",
            "That's fine, we save time later!",
            "Minor time loss, still on pace!",
        ],
        frustrated_phrases=[
            "RNG hates me today!",
            "This strat is not working!",
            "Who wrote this code, come on!",
            "I'm malding but it's fine!",
        ],
        hype_phrases=[
            "We're ahead of splits!",
            "PB pace let's GO!",
            "This run is CLEAN!",
            "World record incoming!",
        ],
        outro_phrases=[
            "AND TIME! That was clean!",
            "GG, sub hour!",
            "Record pace, see you next time!",
            "Optimized to perfection!",
        ],
    ),
    Personality(
        name="The Dramatic Artist",
        voice_id="e07c00bc-4134-4eae-9ea4-1a55fb45746b",  # Brooke
        intro_phrases=[
            "Ah, a new canvas awaits!",
            "The muse has struck! Let us begin!",
            "Today, we create something beautiful!",
            "Art is calling, and I must answer!",
        ],
        action_phrases={
            "Read": ["Let me study this masterpiece...", "Absorbing the essence...", "Reading between the lines..."],
            "Write": ["Crafting with care!", "The words flow!", "Creating magic!"],
            "Edit": ["Refining the vision!", "A touch here, a stroke there!", "Perfecting the art!"],
            "Bash": ["Invoking the powers!", "The command speaks!", "Digital sorcery!"],
            "Glob": ["Seeking inspiration!", "Where is my muse?", "The search continues!"],
            "Grep": ["Hunting for meaning!", "Pattern recognition!", "Aha, there it is!"],
        },
        thinking_phrases=[
            "Hmm, what would Picasso do...",
            "The creative process is delicate...",
            "Inspiration is brewing...",
            "Let me channel this energy...",
            "The vision is forming...",
        ],
        success_phrases=[
            "Magnifique!",
            "A masterpiece is born!",
            "The code sings!",
            "Beauty in digital form!",
        ],
        error_phrases=[
            "Tragedy! But every artist knows failure!",
            "The path to greatness has obstacles!",
            "A twist in our story, but onward!",
        ],
        frustrated_phrases=[
            "The universe tests me!",
            "Why must creation be so difficult!",
            "I suffer for my art!",
            "This is my villain origin story!",
        ],
        hype_phrases=[
            "I feel the momentum building!",
            "The crescendo approaches!",
            "This is becoming something special!",
        ],
        outro_phrases=[
            "And scene! What a performance!",
            "The curtain falls on another success!",
            "Until next time, my audience!",
            "Art has been made today!",
        ],
    ),
]


class TTSClient:
    """Async Cartesia TTS client with real-time audio playback."""

    SAMPLE_RATE = 24000
    CHANNELS = 1
    SAMPLE_WIDTH = 2
    CHUNK_SIZE = 1024
    MODEL_ID = "sonic-2"

    def __init__(self, api_key: Optional[str] = None, personality: Optional[Personality] = None):
        self.api_key = api_key or os.environ.get("CARTESIA_API_KEY")
        if not self.api_key:
            raise ValueError("CARTESIA_API_KEY required")

        # Pick a random personality if not specified
        self.personality = personality or random.choice(PERSONALITIES)
        print(f"[Personality: {self.personality.name}]")

        self._client: Optional[AsyncCartesia] = None
        self._audio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._audio_queue: Queue = Queue()
        self._playback_thread: Optional[threading.Thread] = None
        self._running = False

    async def start(self):
        """Initialize the TTS client and audio playback."""
        self._client = AsyncCartesia(api_key=self.api_key)

        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=self.CHANNELS,
            rate=self.SAMPLE_RATE,
            output=True,
            frames_per_buffer=self.CHUNK_SIZE
        )

        self._running = True
        self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._playback_thread.start()

    async def stop(self):
        """Clean up resources."""
        self._running = False

        if self._playback_thread:
            self._playback_thread.join(timeout=1.0)

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()

        if self._audio:
            self._audio.terminate()

        if self._client:
            await self._client.close()

    async def speak(self, text: str, speed: str = "normal"):
        """Stream TTS for the given text with real-time playback."""
        if not self._client:
            raise RuntimeError("Client not started. Call start() first.")

        if not text or not text.strip():
            return

        try:
            voice_config = {
                "mode": "id",
                "id": self.personality.voice_id,
            }

            async for output in self._client.tts.sse(
                model_id=self.MODEL_ID,
                transcript=text,
                voice=voice_config,
                output_format={
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": self.SAMPLE_RATE
                },
                speed=speed if speed != "normal" else None
            ):
                # Audio data comes as base64 in output.data
                if hasattr(output, "data") and output.data:
                    audio_bytes = base64.b64decode(output.data)
                    self._audio_queue.put(audio_bytes)

        except Exception as e:
            print(f"TTS error: {e}")

    def _playback_loop(self):
        """Background thread for audio playback."""
        while self._running:
            try:
                audio_chunk = self._audio_queue.get(timeout=0.1)
                if audio_chunk and self._stream:
                    self._stream.write(audio_chunk)
            except Empty:
                continue
            except Exception as e:
                print(f"Playback error: {e}")

    def get_intro(self) -> str:
        """Get a random intro phrase."""
        return random.choice(self.personality.intro_phrases)

    def get_action(self, tool_name: str) -> str:
        """Get a random action phrase for a tool."""
        phrases = self.personality.action_phrases.get(
            tool_name,
            [f"Using {tool_name}...", f"Running {tool_name}...", f"Doing some {tool_name} work..."]
        )
        return random.choice(phrases)

    def get_success(self) -> str:
        """Get a random success phrase."""
        return random.choice(self.personality.success_phrases)

    def get_error(self) -> str:
        """Get a random error phrase."""
        return random.choice(self.personality.error_phrases)

    def get_outro(self) -> str:
        """Get a random outro phrase."""
        return random.choice(self.personality.outro_phrases)

    def get_thinking(self) -> str:
        """Get a random thinking/filler phrase."""
        return random.choice(self.personality.thinking_phrases)

    def get_frustrated(self) -> str:
        """Get a random frustrated phrase."""
        return random.choice(self.personality.frustrated_phrases)

    def get_hype(self) -> str:
        """Get a random hype phrase."""
        return random.choice(self.personality.hype_phrases)

    async def speak_action(self, text: str):
        """Speak an action with slightly faster pace."""
        await self.speak(text, speed="fast")

    async def speak_reaction(self, text: str, positive: bool = True):
        """Speak a reaction."""
        await self.speak(text)


async def test_tts():
    """Test the TTS client."""
    client = TTSClient()
    await client.start()

    try:
        print("Testing intro...")
        await client.speak(client.get_intro())

        print("Testing action...")
        await client.speak_action(client.get_action("Read"))

        print("Testing success...")
        await client.speak(client.get_success())

        print("Testing outro...")
        await client.speak(client.get_outro())

        await asyncio.sleep(2)
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(test_tts())
