"""Redact the Claude Code session transcripts of this project for deposit (paper Sect. "Code written with an
AI assistant").

Reads every ``*.jsonl`` transcript under the Claude Code project folders given on the command line and writes
a redacted copy of each to ``outputs/ai_transcripts/`` (git-ignored), with a ``REDACTION.csv`` table of what
was replaced in each file. Each line stays a valid JSON record. Redacted:

- embedded images (screenshots) and any other base64 payload of 1000 characters or more, which also removes
  the token-shaped ``eyJ...`` substrings found inside them;
- JWT-shaped tokens (three base64url segments starting with ``eyJ``) anywhere else;
- email addresses, except ``noreply@anthropic.com`` of the commit trailers;
- local paths: the home folder of any user, the Claude Code temporary folder, and the user name in the encoded
  project-folder names, and the bare user name (for example in ``ls -l`` output).

Usage: pixi run python scripts/redact_transcripts.py ~/.claude/projects/<project-folder> [...]
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path("outputs/ai_transcripts")
KEEP_EMAILS = {"noreply@anthropic.com"}

JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
# The TLD list keeps code such as "\n@pytest.mark.parametrize" or "A@cN-N.ravel" from matching.
TLDS = "edu|com|org|gov|net|us|io|ai|uk|fr|ch|de|ca|info|mil"
EMAIL = re.compile(rf"(?<![\\A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+(?:{TLDS})\b")
TMP = re.compile(r"/private/tmp(?:/[^\s\"'\\]*)?|/private/var/folders/[^\s\"'\\]*|/var/folders/[^\s\"'\\]*")
HOME = re.compile(r"/Users/[A-Za-z0-9._-]+")
ENCODED_HOME = re.compile(r"-Users-[A-Za-z0-9._]+-")
USER = re.compile(rf"\b{re.escape(Path.home().name)}\b")  # e.g. the owner column of ls -l output
BASE64 = re.compile(r"^[A-Za-z0-9+/=\s]{1000,}$")


def redact_text(s: str, counts: Counter) -> str:
    s, n = JWT.subn("[token]", s)
    counts["token"] += n

    def email(m):
        if m.group(0).lower() in KEEP_EMAILS:
            return m.group(0)
        counts["email"] += 1
        return "[email]"

    s = EMAIL.sub(email, s)
    s, n = TMP.subn("[tmp]", s)
    counts["tmp_path"] += n
    s, n = HOME.subn("~", s)
    counts["home_path"] += n
    s, n = ENCODED_HOME.subn("-Users-[user]-", s)
    counts["home_path"] += n
    s, n = USER.subn("[user]", s)
    counts["user_name"] += n
    return s


def walk(x, counts: Counter):
    if isinstance(x, dict):
        if x.get("type") == "image":
            counts["image"] += 1
            return {"type": "text", "text": "[image removed]"}
        return {redact_text(k, counts): walk(v, counts) for k, v in x.items()}
    if isinstance(x, list):
        return [walk(v, counts) for v in x]
    if isinstance(x, str):
        if len(x) >= 1000 and BASE64.match(x):
            counts["base64"] += 1
            return "[base64 removed]"
        return redact_text(x, counts)
    return x


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folders", nargs="+", type=Path)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for folder in args.folders:
        for src in sorted(folder.glob("*.jsonl")):
            counts = Counter()
            with src.open() as f, (OUT / src.name).open("w") as g:
                for line in f:
                    if line.strip():
                        g.write(json.dumps(walk(json.loads(line), counts), ensure_ascii=False) + "\n")
            size = (OUT / src.name).stat().st_size
            rows.append({"file": src.name, "bytes_in": src.stat().st_size, "bytes_out": size, **counts})
            print(f"{src.name}: {dict(counts)}")
    keys = ["file", "bytes_in", "bytes_out", "image", "base64", "token", "email"]
    keys += ["home_path", "tmp_path", "user_name"]
    with (OUT / "REDACTION.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, restval=0)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
