import sys
sys.path.insert(0, '/home/brunapc/LocalAI Hub')
from castlearq.models import ArtifactSpec
from castlerq.model_store import ModelStore
from pathlib import Path
import tempfile

CONTENT = b'model'
tempdir = tempfile.TemporaryDirectory()
store = ModelStore(Path(tempdir.name) / 'models')
final = Path(tempdir.name) / 'qwen2.5-coder-7b-instruct-Q4_K_M.gguf'
final.write_bytes(CONTENT)

spec = ArtifactSpec(
    model_id='qwen2.5-coder-7b-instruct',
    source='huggingface',
    repository='Qwen/Qwen2.5-Coder-7B-Instruct-GGUF',
    filename='qwen2.5-coder-7b-instruct-Q4_K_M.gguf',
    format='GGUF',
    quantization='Q4_K_M',
    sha256='0' * 64,
)

manifest = store.save_manifest(spec)
print('Manifest saved')

inspected = store.inspect_manifest(manifest)
print(f'Inspected state: {inspected.state}')
print(f'Inspected message: {inspected.message}')

from castlerq.resolver import ModelArtifactResolver
model_spec = type('m', (), {'name': 'Qwen2.5 Coder 7B Instruct', 'id': 'qwen2.5-coder-7b-instruct', 'family': 'qwen', 'context_length': 32768})()
resolver = ModelArtifactResolver(store, (model_spec,))

try:
    resolved = resolver.resolve('qwen2.5-coder-7b-instruct')
    print(f'Resolution succeeded: {resolved}')
except Exception as e:
    print(f'Resolution failed: {type(e).__name__}: {e}')