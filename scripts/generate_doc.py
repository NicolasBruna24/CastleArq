#!/usr/bin/env python3
import os
filepath = '/home/brunapc/informe_A2.6.6.26_documentacion_multi_runtime.md'
os.makedirs(os.path.dirname(filepath), exist_ok=True)
with open(filepath, 'w') as f:
    f.write('# A2.6.6.26 - Documentacion de arquitectura multi-runtime\n')
print('Part 1 written')