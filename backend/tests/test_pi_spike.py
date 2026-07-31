"""
test_pi_spike.py
~~~~~~~~~~~~~~~~
Standalone test script to verify the Pi Node subprocess RPC round-trip integration spike.

Tests:
  1. Spawning Pi Node subprocess via PiClient.
  2. Sending a sample query message.
  3. Receiving streamed events (tool_call, token, done).
  4. Verifying a stub tool_call returns correctly.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(_BACKEND_DIR / ".env")

from app.config import settings
from app.pi_client import PiClient, PiRPCError


async def main() -> None:
    print("=== Testing Pi Node Subprocess RPC Spike ===")

    api_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key:
        print("[WARNING] OPENAI_API_KEY is not set in backend/.env.")
        print("  Running with empty API key — expectation is failure or error from LLM call.")

    client = PiClient()

    messages = [
        {"role": "user", "content": "Search transcripts for Brian Chesky's advice on product management."}
    ]

    print(f"Sending prompt to Pi RPC (provider='openai', model='gpt-4o-mini')...\n")

    events = []
    tool_calls = []

    try:
        async for event in client.run_turn(
            messages=messages,
            provider="openai",
            model="gpt-4o-mini",
            api_key=api_key,
            timeout_seconds=30.0,
        ):
            events.append(event)
            event_type = event.get("type")
            if event_type == "tool_call":
                print(f"  [RPC EVENT] tool_call -> tool: {event.get('tool')}, args: {event.get('args')}")
                tool_calls.append(event)
            elif event_type == "tool_result":
                print(f"  [RPC EVENT] tool_result -> tool: {event.get('tool')}, result: {event.get('result')}")
            elif event_type == "token":
                print(f"{event.get('content')}", end="", flush=True)
            elif event_type == "done":
                print(f"\n\n  [RPC EVENT] done -> response: {event.get('content')[:100]}...")

        print("\n=== Spike Test Summary ===")
        print(f"Total RPC events received: {len(events)}")
        print(f"Tool calls captured: {len(tool_calls)}")
        if tool_calls:
            print("SUCCESS: Tool call round-trip verified!")
        else:
            print("INFO: Completed turn without tool call (or model responded directly).")

    except PiRPCError as exc:
        print(f"\n[ERROR] Pi RPC failed: {exc}")
        print("\nNotice: Per ARCHITECTURE.md §6, if Pi RPC integration is unreliable, fallback to direct OpenAI SDK client.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
