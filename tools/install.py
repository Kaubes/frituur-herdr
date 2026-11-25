#!/usr/bin/env python3
"""Installs or updates Frituur in the Herdr app's home (real copies: Herdr loads no symlinked art).

  python tools/install.py           mod, layout, theme and the layout's keys
  python tools/install.py --hook    also the Claude Code hook: copies it to ~/.claude/hooks and
                                    registers it in ~/.claude/settings.json (a backup is kept)
  python tools/install.py --bel     also makes Herdr's "blocked" sound the frituur's bell
  python tools/install.py --no-copy --hook   only the hook, nothing into Herdr
  python tools/install.py --unhook  takes the hook out of settings.json again

HERDR_APP_HOME picks another Herdr home (default ~/.config/herdr-app).
"""
import filecmp, json, os, shutil, sys, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")
DEST = os.environ.get("HERDR_APP_HOME") or os.path.join(HOME, ".config", "herdr-app")
KEYS = {"ctrl-shift-j": "frituur.lade", "ctrl-shift-b": "layout.toggle:rail"}
EVENTS = ["SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
          "PreCompact", "PostCompact", "SubagentStart", "SubagentStop", "Stop", "StopFailure"]


def load(p, default):
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


def mirror(src, dst):
    """An exact copy that only writes what changed, so Herdr reloads once."""
    n = 0
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(dst):
        # .d.ts and jsconfig.json are Herdr's own
        if not os.path.exists(os.path.join(src, name)) and not name.endswith((".d.ts", "jsconfig.json")):
            p = os.path.join(dst, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            n += 1
    for name in os.listdir(src):
        a, b = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(a):
            n += mirror(a, b)
        elif not os.path.exists(b) or not filecmp.cmp(a, b, shallow=False):
            shutil.copyfile(a, b)
            n += 1
    return n


def copy():
    if not os.path.isdir(DEST):
        sys.exit(f"Herdr home not found: {DEST} (open Herdr once first)")
    n = mirror(os.path.join(REPO, "mods", "frituur"), os.path.join(DEST, "mods", "frituur"))
    for f in ("layouts/Frituur.json", "layouts/Frituur.png", "themes/Frituur.json"):
        a, b = os.path.join(REPO, f), os.path.join(DEST, f)
        if os.path.exists(a) and not (os.path.exists(b) and filecmp.cmp(a, b, shallow=False)):
            os.makedirs(os.path.dirname(b), exist_ok=True)
            shutil.copyfile(a, b)
            n += 1
    keys_path = os.path.join(DEST, "keys.json")
    keys = load(keys_path, {})
    mine = keys.setdefault("layout:Frituur", {})
    if any(k not in mine for k in KEYS):
        for k, v in KEYS.items():
            mine.setdefault(k, v)
        save(keys_path, keys)
        n += 1
    print(f"{n} file(s) updated in {DEST}")


def main():
    if "--no-copy" not in sys.argv:
        copy()

    if "--bel" in sys.argv:
        p = os.path.join(DEST, "settings.json")
        s = load(p, {})
        s.setdefault("sounds", {}).update(blocked="mods/frituur/sounds/bel.mp3")
        save(p, s)
        print("Herdr's blocked sound is now the bell")

    if "--hook" in sys.argv or "--unhook" in sys.argv:
        path = os.path.join(HOME, ".claude", "settings.json")
        hook = os.path.join(HOME, ".claude", "hooks", "frituur-hook.py")
        s = load(path, {})
        before = json.dumps(s)
        hooks = s.setdefault("hooks", {})
        for ev in list(hooks):  # drop our own earlier entries, nobody else's
            hooks[ev] = [g for g in hooks[ev] if not any("frituur-hook.py" in json.dumps(h) for h in g.get("hooks", []))]
            if not hooks[ev]:
                del hooks[ev]
        if "--hook" in sys.argv:
            os.makedirs(os.path.dirname(hook), exist_ok=True)
            shutil.copyfile(os.path.join(REPO, "integrations", "claude-code", "frituur-hook.py"), hook)
            for ev in EVENTS:
                h = {"type": "command", "command": sys.executable.replace("\\", "/"), "args": [hook.replace("\\", "/")], "timeout": 5}
                if ev != "SessionEnd":  # at the end Claude would kill a background hook
                    h["async"] = True
                hooks.setdefault(ev, []).append({"hooks": [h]})
        if not hooks:
            del s["hooks"]
        if json.dumps(s) != before:
            if os.path.exists(path):
                shutil.copyfile(path, path + time.strftime(".frituur-backup-%Y%m%d-%H%M%S"))
            save(path, s)
            print(f"{path}: hook {'registered for ' + ', '.join(EVENTS) if '--hook' in sys.argv else 'removed'}")
        else:
            print("settings.json already right")


main()
