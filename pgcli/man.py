import subprocess

IGNORED = [
    "OR",
    "REPLACE",
    "DEFAULT",
    "UNIQUE",
    "TRUSTED",
    "PROCEDURAL",
    "TEMP",
    "TEMPORARY",
    "UNLOGGED",
    "GLOBAL",
    "LOCAL",
    "CONSTRAINT",
    "RECURSIVE",
    "WORK",
    "TRANSACTION",
    "SESSION",
]


def try_man(page):
    try:
        subprocess.run(
            f"man -I 7 {page}", shell=True, check=True, universal_newlines=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def man(query):
    words = query.strip().split()[:6]
    words = map(lambda e: e.upper(), words)
    words = list(filter(lambda e: e not in IGNORED, words))
    if not words:
        return True
    if words[0] == "RELEASE":
        words.insert(1, "SAVEPOINT")
    for i in [2, 1, 3, 4]:
        if try_man("_".join(words[0 : i + 1])):
            return True
    return False
