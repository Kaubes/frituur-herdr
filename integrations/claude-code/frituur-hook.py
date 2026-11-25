#!/usr/bin/env python3
"""Frituur (Herdr layout): what each Claude Code session is doing, for the scene.

Async Claude Code command hook. Writes ~/.local/state/frituur/<HC_TERMINAL_ID>.json, which
mods/frituur/staat.js joins to agents()[i].address. Outside Herdr (no HC_TERMINAL_ID) it does
nothing. It prints nothing: stdout of SessionStart and UserPromptSubmit would end up in Claude's
context. The plumbing follows World of Codecraft's wocc-activity.py (MIT, Kevin Pardo).

  session_id, ticket   the ticket is drawn when a new session starts in the terminal (1..99)
  act      denkt | diepvries (reading, searching, web) | bakt (editing) | schudt (commands)
           | test | olie (compacting) | klaar (turn over)        sinds  when act started (ms)
  tool     last tool                       snacks  ids of the running subagents
  prompt   first 40 characters             bestelling  prompt counter (0 = nothing ordered yet)
  fouten   consecutive tool failures       foutT  the last one      klaarT  last turn end
  t        last event (ms)
"""
import json, os, re, sys, time

TERM = os.environ.get("HC_TERMINAL_ID")
if not TERM or not re.fullmatch(r"[\w.-]+", TERM):
    sys.exit(0)
NOW = int(time.time() * 1000)
try:
    ev = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)

DIR = os.environ.get("FRITUUR_STATE") or os.path.join(os.path.expanduser("~"), ".local", "state", "frituur")
PATH = os.path.join(DIR, TERM + ".json")
NAME = ev.get("hook_event_name", "")
TOOL = ev.get("tool_name") or ""
SID = ev.get("session_id") or ""

READ = {"Read", "Grep", "Glob", "LS", "NotebookRead", "LSP", "ToolSearch", "WebSearch", "WebFetch"}
EDIT = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL = {"Bash", "PowerShell"}
# only real commands: at the start of a command line or after ; & | (
TEST = re.compile(
    r"(?:^|[;&|(]\s*)(?:\w+=\S+\s+)*((bun|npm|pnpm|yarn|npx|bunx)\s+(run\s+)?test|vitest|jest|"
    r"(python3?\s+-m\s+)?pytest|python3?\s+-m\s+unittest|playwright\s+test|cargo\s+test|go\s+test|"
    r"dotnet\s+test|flutter\s+test|rspec|phpunit|mix\s+test|deno\s+test)\b", re.M)


def command():
    c = str((ev.get("tool_input") or {}).get("command") or "") if TOOL in SHELL else ""
    c = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\b", " ", c, flags=re.S)  # heredoc bodies
    return re.sub(r"'[^']*'|\"(?:\\.|[^\"\\])*\"", "''", c)  # quoted text


def kind():
    if TOOL in EDIT:
        return "bakt"
    if TOOL in READ or (TOOL.startswith("mcp__") and re.search(r"search|fetch|read|docs|get_", TOOL)):
        return "diepvries"
    if TOOL in SHELL:
        return "test" if TEST.search(command()) else "schudt"
    return None  # Agent, TodoWrite, Skill...: the scene stays as it was


class Lock:
    """One writer at a time: hooks of one session run in parallel. Gives up after 2 s."""

    def __enter__(self):
        self.f = open(os.path.join(DIR, ".lock"), "a+b")
        end = time.time() + 2
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.time() > end:
                    sys.exit(0)
                time.sleep(0.01)

    def __exit__(self, *_):
        if os.name == "nt":
            import msvcrt
            self.f.seek(0)
            msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        self.f.close()


def replace(path, text):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    for _ in range(20):  # Windows refuses while the mod is reading the file
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.01)
    os.remove(tmp)


def next_ticket():
    p = os.path.join(DIR, "teller.txt")
    try:
        with open(p) as f:
            n = int(f.read().strip())
    except Exception:
        n = 0
    n = n % 99 + 1
    replace(p, str(n))
    return n


def main():
    os.makedirs(DIR, exist_ok=True)
    with Lock():
        try:
            with open(PATH, encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            s = {}
        if NAME == "SessionEnd":
            # an older session's goodbye must not remove the one that replaced it
            if s.get("session_id") in (None, SID):
                try:
                    os.remove(PATH)
                except OSError:
                    pass
            return
        if s.get("session_id") != SID:
            s = {"session_id": SID, "ticket": next_ticket(), "act": "klaar", "sinds": NOW, "snacks": [],
                 "bestelling": 0, "fouten": 0, "prompt": ""}

        def act(a):
            if s.get("act") != a:
                s["act"], s["sinds"] = a, NOW

        aid = ev.get("agent_id")
        if NAME == "SubagentStart":
            s["snacks"] = [x for x in s["snacks"] if x != aid] + [aid]
        elif NAME == "SubagentStop":
            s["snacks"] = [x for x in s["snacks"] if x != aid]
        elif aid:
            pass  # a subagent's own tools: the customer's order stays as it is
        elif NAME == "UserPromptSubmit":
            p = " ".join(str(ev.get("prompt") or "").split())
            s.update(prompt=p[:39] + "…" if len(p) > 40 else p, bestelling=s["bestelling"] + 1, fouten=0)
            act("denkt")
        elif NAME == "PreToolUse":
            k = kind()
            if k:
                act(k)
            s["tool"] = TOOL
        elif NAME == "PostToolUse":
            s["fouten"] = 0
        elif NAME == "PostToolUseFailure":
            if not ev.get("is_interrupt"):
                s["fouten"] = s["fouten"] + 1
                s["foutT"] = NOW
        elif NAME == "PreCompact":
            act("olie")
        elif NAME == "PostCompact":
            act("denkt")
        elif NAME in ("Stop", "StopFailure"):
            if not ev.get("background_tasks"):
                s["snacks"] = []
            s["klaarT"] = NOW
            act("klaar")
        s["t"] = max(NOW, s.get("t", 0))
        replace(PATH, json.dumps(s, ensure_ascii=False))


try:
    main()
except Exception:
    pass  # never in Claude's way
