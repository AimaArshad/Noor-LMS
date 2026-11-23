"""Run from repo root: python apply_tags.py - declares the 'voice' OpenAPI tag."""
import pathlib, re

DESC = "Voice commands and speech-to-text for the accessibility mode."
pat = re.compile(r'(?P<entry>\{\s*"name":\s*"audiobooks"\s*,\s*"description":\s*(?:"[^"]*"|\'[^\']*\')\s*,?\s*\})')
for p in pathlib.Path("backend/app").rglob("*.py"):
    raw = p.read_bytes().decode("utf-8")
    s = raw.replace("\r\n", "\n")
    if '"name": "voice"' in s:
        print("already declared in", p); raise SystemExit
    m = pat.search(s)
    if not m:
        continue
    line_start = s.rfind("\n", 0, m.start()) + 1
    indent = re.match(r"[ \t]*", s[line_start:]).group(0)
    new = s[: m.end()] + f',\n{indent}{{"name": "voice", "description": "{DESC}"}}' + s[m.end():]
    # avoid a double comma if the entry was already followed by one
    new = new.replace('"}},\n' + indent + '{"name": "voice"', '"}},\n' + indent + '{"name": "voice"')
    if "\r\n" in raw:
        new = new.replace("\n", "\r\n")
    p.write_bytes(new.encode("utf-8"))
    print("patched", p); raise SystemExit
print("Not found automatically. Run: Select-String -Path backend\\app\\*.py -Pattern 'audiobooks' -Recurse is not available; use: Get-ChildItem backend\\app -Recurse -Filter *.py | Select-String '\"name\": \"audiobooks\"'")
