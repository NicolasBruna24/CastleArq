import subprocess

commits = ["601beb7", "349f7bb", "4e4eee2", "22d0fe9", "00e03dc"]
for c in commits:
    print("=" * 60)
    print("COMMIT:", c)
    out = subprocess.run(
        ["git", "show", "--stat", "--oneline", c],
        capture_output=True, text=True, cwd="/home/brunapc/LocalAI Hub",
    )
    print(out.stdout[:1500])
    print()
