# Speaking Claude Code 🎙️

**AI agents that narrate their work like Twitch streamers.** Built for the Cartesia Voice AI Hackathon.

Turn Claude Code into an entertaining, voice-enabled coding companion. Agents have distinct personalities, trash-talk each other, and compete in real-time.

## Features

- **Real-time TTS narration** of Claude Code's actions using [Cartesia](https://cartesia.ai) Sonic voice AI
- **4 expressive personalities** - The Hype Beast, Chill Streamer, Competitive Coder, Dramatic Artist
- **Background thinking** - Agents vocalize their thought process while working
- **Battle Royale mode** - 3 agents compete on the same task with different approaches, trash-talking each other

## Demo

```bash
# Single agent with personality
./speaking-claude-interactive

# Battle Royale - 3 agents compete!
./battle "create a landing page for a coffee shop"
```

## Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/speaking-claude.git
cd speaking-claude

# Install dependencies
pip install -r requirements.txt

# Set your Cartesia API key
export CARTESIA_API_KEY="your-key-here"
```

### Requirements

- Python 3.9+
- [Claude Code CLI](https://claude.ai/claude-code) installed
- [Cartesia API key](https://cartesia.ai)
- PyAudio (for audio playback)

On macOS, you may need:
```bash
brew install portaudio
pip install pyaudio
```

## Usage

### Interactive Mode

Chat with a personality-infused Claude that narrates everything:

```bash
./speaking-claude-interactive
```

Or with the alias (after adding to ~/.zshrc):
```bash
claude-speak
```

### Battle Royale

3 agents compete on the same task with different approaches:

```bash
./battle "build a todo app"
```

**The competitors:**
- 🔴 **SpeedDemon** - Fastest, minimal approach
- 🟢 **Architect** - Clean, well-structured with best practices
- 🔵 **Wildcard** - Creative, unconventional solutions

They trash-talk each other while working, and at the end, 3 browser windows open to compare results.

Test the voices first:
```bash
./battle --demo
```

### Single Prompt Mode

```bash
./speaking-claude-interactive "fix the bug in auth.py"
```

## How It Works

1. Runs Claude Code with `--output-format stream-json` to capture structured output
2. Parses events in real-time (assistant messages, tool use, errors)
3. Streams text to Cartesia TTS with personality-appropriate voice
4. Plays audio via PyAudio with low latency

## Personalities

Each session gets a random personality with unique:
- Voice (Cartesia voice ID)
- Intro/outro phrases
- Tool action narration style
- Thinking filler phrases
- Success/error reactions
- Trash talk (for Battle Royale)

## Files

| File | Description |
|------|-------------|
| `speaking_claude_multi.py` | Main interactive agent with TTS |
| `battle_royale.py` | 3-agent competition mode |
| `tts_client.py` | Cartesia TTS client with personalities |
| `speaking-claude-interactive` | Shell wrapper for interactive mode |
| `battle` | Shell wrapper for Battle Royale |

## Vision

This is a prototype for **AI coding streams** - imagine multiple agents working on a project together, narrating their work, debating approaches, and entertaining viewers. Perfect for:

- Hackathon demos
- Educational content
- AI entertainment/streaming
- Collaborative agent workflows

## License

MIT

## Credits

Built with:
- [Claude Code](https://claude.ai/claude-code) by Anthropic
- [Cartesia](https://cartesia.ai) Voice AI
