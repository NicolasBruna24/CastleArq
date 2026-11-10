with open('/home/brunapc/LocalAI Hub/tests/test_gpu_offload_evidence.py', 'r') as f:
    content = f.read()

old = 'runtime_version=f"version: {VERSION}")'
new = 'runtime_version=f"version: {VERSION}", backend="CPU")'

content = content.replace(old, new)

with open('/home/brunapc/LocalAI Hub/tests/test_gpu_offload_evidence.py', 'w') as f:
    f.write(content)

print('Fix applied')