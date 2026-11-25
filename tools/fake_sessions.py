#!/usr/bin/env python3
"""Plays fake Claude Code sessions through the real hook, to test it without Claude.

  python tools/fake_sessions.py        two sessions in a temporary folder, checks the result
"""
import json, os, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "integrations", "claude-code", "frituur-hook.py")
DIR = tempfile.mkdtemp(prefix="frituur-")
fails = 0


def fire(term, sid, name, **kw):
    ev = {"session_id": sid, "hook_event_name": name, **kw}
    env = {**os.environ, "FRITUUR_STATE": DIR}
    env.pop("HC_TERMINAL_ID", None)
    if term:
        env["HC_TERMINAL_ID"] = term
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(ev, ensure_ascii=False).encode(), env=env, capture_output=True)
    if r.stdout or r.stderr or r.returncode:
        check("silent on " + name, (r.returncode, r.stdout, r.stderr), (0, b"", b""))


def state(term):
    try:
        with open(os.path.join(DIR, term + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def check(what, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(("ok   " if ok else "FAIL ") + what + ("" if ok else f": got {got!r}, want {want!r}"))


fire(None, "x", "SessionStart", source="startup")
check("nothing written outside Herdr", os.listdir(DIR), [])
fire("t1", "A", "SessionStart", source="startup")
fire("t2", "B", "SessionStart", source="startup")
check("tickets count up", (state("t1")["ticket"], state("t2")["ticket"]), (1, 2))
check("nothing ordered yet", state("t1")["bestelling"], 0)
fire("t1", "A", "UserPromptSubmit", prompt="Eén grote friet met stoofvleessaus en twee frikandellen")
check("prompt is shortened", (len(state("t1")["prompt"]), state("t1")["prompt"][:15]), (40, "Eén grote friet"))
check("thinks after a prompt", state("t1")["act"], "denkt")
for tool, inp, want in [("Read", {}, "diepvries"), ("Edit", {}, "bakt"), ("Bash", {"command": "ls -la"}, "schudt"),
                        ("Bash", {"command": "cd x && npm test"}, "test"), ("Bash", {"command": "echo 'npm test'"}, "schudt"),
                        ("PowerShell", {"command": "pytest -q"}, "test"), ("TodoWrite", {}, "test"), ("WebSearch", {}, "diepvries")]:
    fire("t1", "A", "PreToolUse", tool_name=tool, tool_input=inp)
    check(f"{tool} {inp.get('command', '')} -> {want}", state("t1")["act"], want)
fire("t1", "A", "PostToolUseFailure", tool_name="Bash", tool_input={}, error="x")
fire("t1", "A", "PostToolUseFailure", tool_name="Bash", tool_input={}, error="x", is_interrupt=True)
check("failures counted, interrupts not", state("t1")["fouten"], 1)
fire("t1", "A", "PostToolUse", tool_name="Edit", tool_input={})
check("a success clears them", state("t1")["fouten"], 0)
fire("t1", "A", "SubagentStart", agent_id="a1", agent_type="Explore")
fire("t1", "A", "PreToolUse", tool_name="Edit", tool_input={}, agent_id="a1")
check("a subagent's tools are ignored", (state("t1")["act"], state("t1")["snacks"]), ("diepvries", ["a1"]))
fire("t1", "A", "SubagentStop", agent_id="a1", agent_type="Explore")
check("snack is gone", state("t1")["snacks"], [])
fire("t1", "A", "PreCompact", trigger="auto")
check("compaction changes the oil", state("t1")["act"], "olie")
fire("t1", "A", "Stop")
check("turn over", (state("t1")["act"], "klaarT" in state("t1")), ("klaar", True))
check("the other session is untouched", (state("t2")["session_id"], state("t2")["act"], state("t2")["bestelling"]), ("B", "klaar", 0))
fire("t1", "C", "SessionStart", source="clear")
check("a new session in a terminal takes a new ticket", state("t1")["ticket"], 3)
fire("t1", "A", "SessionEnd", reason="clear")
check("the old session's goodbye keeps the new one", state("t1")["session_id"], "C")
t = time.time()
with ThreadPoolExecutor(12) as ex:
    list(ex.map(lambda i: fire("t2", "B", "SubagentStart", agent_id=f"s{i}"), range(12)))
check("12 hooks at once lose nothing", len(state("t2")["snacks"]), 12)
print(f"     (12 parallel hooks took {time.time() - t:.2f} s)")
t = time.time()
fire("t2", "B", "PreToolUse", tool_name="Read", tool_input={})
print(f"     (one hook takes {(time.time() - t) * 1000:.0f} ms)")
fire("t2", "B", "SessionEnd", reason="other")
check("session end removes the file", state("t2"), None)
check("no temp files left", [f for f in os.listdir(DIR) if f.endswith(".tmp")], [])
shutil.rmtree(DIR, ignore_errors=True)
print("all good" if not fails else f"{fails} failed")
sys.exit(bool(fails))
