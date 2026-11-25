#!/usr/bin/env python3
"""A pretend Claude Code for a terminal inside Herdr: reports its status to Herdr (OSC 7501) and
fires the real hook, so the whole chain can be tried without Claude.

  python tools/fake_agent.py "start;prompt Maak de login af;tool Edit;sleep 5;fail Bash;blocked;sleep 9;stop;done;sleep 60"

Steps: start, prompt <text>, tool <name> [command], ok, fail, sub <id>, unsub <id>, compact,
stop, end, working | blocked | idle | done (Herdr's status), sleep <s>. Ends after the last one.
"""
import json, os, subprocess, sys, time, uuid

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "integrations", "claude-code", "frituur-hook.py")
SID = str(uuid.uuid4())


def hook(name, **kw):
    subprocess.run([sys.executable, HOOK], input=json.dumps({"session_id": SID, "hook_event_name": name, **kw}).encode())


def status(s):
    sys.stdout.write(f"\x1b]7501;state={s}:app=claude-code\x1b\\")
    sys.stdout.flush()


print("terminal", os.environ.get("HC_TERMINAL_ID"), flush=True)
for step in (sys.argv[1] if len(sys.argv) > 1 else "start;idle;sleep 600").split(";"):
    cmd, _, arg = step.strip().partition(" ")
    print(">", step.strip(), flush=True)
    if cmd == "start": hook("SessionStart", source="startup")
    elif cmd == "prompt": hook("UserPromptSubmit", prompt=arg); status("working")
    elif cmd == "tool":
        t, _, c = arg.partition(" "); hook("PreToolUse", tool_name=t, tool_input={"command": c})
    elif cmd == "ok": hook("PostToolUse", tool_name="Edit", tool_input={})
    elif cmd == "fail": hook("PostToolUseFailure", tool_name="Bash", tool_input={}, error="x")
    elif cmd == "sub": hook("SubagentStart", agent_id=arg, agent_type="Explore")
    elif cmd == "unsub": hook("SubagentStop", agent_id=arg, agent_type="Explore")
    elif cmd == "compact": hook("PreCompact", trigger="auto")
    elif cmd == "stop": hook("Stop")
    elif cmd == "end": hook("SessionEnd", reason="other")
    elif cmd == "sleep": time.sleep(float(arg))
    elif cmd in ("working", "blocked", "idle", "done"): status(cmd)
    else: print("?", step)
