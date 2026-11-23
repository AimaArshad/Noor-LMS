"""Run from the repo root: python apply_i.py
1) double-voice fix in frontend/src/voice/useSpeak.ts
2) .gitignore entries for Playwright output"""
import re, pathlib

p = pathlib.Path("frontend/src/voice/useSpeak.ts")
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
pat = re.compile(r"utterance\.onerror\s*=\s*\(\)\s*=>\s*\{\n(\s*)synthSpeakingRef\.current = false;\n(?:\s*//[^\n]*\n)?\s*void speakViaTTS\(text\);\n(\s*)\};")
def rep(m):
    i = m.group(1); o = m.group(2)
    return (f"utterance.onerror = (event) => {{\n{i}synthSpeakingRef.current = false;\n"
            f"{i}// stop()/cancel() raises 'canceled'/'interrupted': that is not a failure,\n"
            f"{i}// so do not replay the old text through the server voice (double voice).\n"
            f"{i}const err = (event as SpeechSynthesisErrorEvent).error;\n"
            f"{i}if (err === \"canceled\" || err === \"interrupted\") return;\n"
            f"{i}void speakViaTTS(text);\n{o}}};")
s2, n = pat.subn(rep, s)
print("useSpeak.ts patched" if n else "useSpeak.ts: pattern not found - edit by hand (see chat)")
if crlf: s2 = s2.replace("\n", "\r\n")
if n: p.write_bytes(s2.encode("utf-8"))

g = pathlib.Path(".gitignore")
t = g.read_text(encoding="utf-8") if g.exists() else ""
for line in ("frontend/playwright-report/", "frontend/test-results/"):
    if line not in t:
        t += ("\n" if t and not t.endswith("\n") else "") + line + "\n"
g.write_text(t, encoding="utf-8")
print(".gitignore updated")
