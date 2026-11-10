import subprocess
r = subprocess.run(
    ['git', 'show', 'd45dc884dd686d8c89d8db7905e41cf8325e9bb4', '--stat'],
    capture_output=True, text=True,
    cwd='/home/brunapc/LocalAI Hub'
)
print('STDOUT:', r.stdout[:3000])
print('STDERR:', r.stderr[:1000])