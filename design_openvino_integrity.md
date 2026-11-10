# Design Review: OpenVINO Integrity Verification — CORREGIDO

## 1. Identificación del artefacto

### Hallazgo actual
- `artifact.backend` **sí** identifica el tipo de almacenamiento OpenVINO: se establece en `"openvino"` en `conversion.py:198` al crear el `ArtifactSpec` para artefactos OpenVINO IR.
- **No asuma que `backend` y `formato` son equivalentes.** El `formato` es `"OpenVINO IR"` (o `"Unknown"`), mientras que `backend` es `"openvino"`. Son campos independientes en `ArtifactSpec`.

### contenido_id para OpenVINO: definición corregida
- `content_id` para OpenVINO representa el **SHA-256 compuesto del paquete completo**, calculado a partir de **rutas relativas POSIX** y **contenidos de los archivos reales**, ordenados **determinísticamente**.
- **No es el hash del XML individual.** Conserva exactamente el algoritmo existente del importador `conversion.py`: recorrido de directorio `rglob("*")`, exclusión de `.git`, filtrado a archivos regulares (no symlinks), `sorted()` por ruta relativa, y SHA-256 de cada archivo. El digest final se compone de los hashes individuales en orden determinista.
- El `content_id` es la identidad CastleArq del artefacto importado, tal como lo define el importador GGUF/B9.67.

### Campo/mecanismo correcto
- Use `artifact.backend` para comprobar si un artefacto es OpenVINO IR.
- No use `artifact.format` para esta comprobación: el formato es descriptivo (lo que el usuario ve), el backend es el identificador de tipo de datos (lo que el sistema trata).
- Los valores válidos de `backend` están definidos en `models.py:48`: `{"gguf", "openvino"}`. Cualquier otro valor provoca `ValueError` en `__post_init__`.

### Recomendación
```python
def is_openvino_artifact(artifact: ArtifactSpec) -> bool:
    """Check if artifact uses OpenVINO IR backend."""
    return artifact.backend == "openvino"
```
## 2. Contrato B9.67: `content_id` y `sha256` independientes

### Principios de B9.67 (respeto total)
- `content_id` y `sha256` son **declaraciones independientes**.
- **Si ambos existen**: verificarlos independientemente. Una discrepancia en cualquiera implica rechazo.
- **Si existe solo `content_id`**: verifica el `content_id` contra los bytes observados. El `sha256` se deja como `None` (no se llena artificialmente).
- **Si existe solo `sha256`**: verifica el `sha256` contra el archivo. El `content_id` se computes y se almacena como identidad CastleArq.
- **Si ninguno existe**: el preflight **rechaza** el artefacto (no puede verificar identidad ni integridad).
- **No copie un identificador al otro**: llenar `sha256` con `content_id` haría que `inspect_manifest` comparara un valor contra sí mismo y reportara `VERIFIED` — una verificación que nunca sucedió. Del mismo modo, no compute `content_id` desde `sha256`.
- **No confunda el estado de `inspect_manifest()` con la admisión de ejecución**: `inspect_manifest()` devuelve estados de inspección (`DOWNLOADED`, `VERIFIED`, `FAILED`); `ArtifactExecutionPreflight.validate()` admite o rechaza la ejecución basándose en esos estados más verificaciones de tamaño y checksum. Uno es observación, el otro es decisión operativa.

### Flujo de verificación B9.67
| `content_id` | `sha256` | Acción |
|-------------|----------|--------|
| Presente | Presente | Verificar ambos independientemente. Cualquier discrepancia → `FAILED`. |
| Presente | Ausente | Verificar `content_id` contra bytes observados. Si coincide, `state=DOWNLOADED`. Sin verificación de `sha256`. |
| Ausente | Presente | Compute `content_id` desde bytes observados. Verificar `sha256` contra archivo. Cualquier discrepancia → `FAILED`. |
| Ausente | Ausente | **Rechazar**: no hay identidad ni integridad verificables. |
```
## 3. Verificación de `sha256` en OpenVINO

### Contrato existente (inspección de modelos, manifiestos e importación)
- **Origen del `sha256`**: Es un campo opcional en `ArtifactSpec` (models.py:53). Cuando está presente, es una **declaración de integridad** — un valor esperado SHA-256 que será comparado contra el archivo observado.
- **Quién lo pone**: El catalogador o el usuario al crear un `ArtifactSpec` con un SHA-256 declarado. No se computes automáticamente desde los bytes a menos que el diseño lo especifique explícitamente.
- **Quién lo verifica**:
  - `inspect_manifest()` (model_store.py:376-380): si `verify=True` y `artifact.sha256` está presente, computes SHA-256 del archivo y comparas contra `artifact.sha256`. Si coinciden, `state=VERIFIED`; si no, `state=FAILED` con mensaje "SHA-256 differs from manifest".
  - `ArtifactExecutionPreflight.validate()` (execution.py:301-314): mismo patrón — computes SHA-256 del archivo y compara contra `artifact.sha256`. Lanza `CHECKSUM_MISMATCH` si no coinciden.
- **Significado cuando no hay contrato inequívoco**: Si no hay una definición clara de qué representa el `sha256` (paquete completo, XML individual, ciertos archivos), se debe **documentar la ambigüedad como decisión pendiente** y no se asume ningún significado implícito.

### Decisión de diseño para OpenVINO
- **No se asume que `sha256` representa el paquete completo** ni que representa el XML individual.
- El `sha256` es un campo opcional que el usuario o catalogador puede declarar. Si está presente, se verifica contra el archivo completo que esté siendo inspeccionado en ese momento.
- Si el usuario desea verificar componentes específicos (XML, BIN, auxiliares), debe declarar checksums individuales mediante el campo `file_checksums` del manifiesto (B126 en models.py).
- **Ausencia de contrato inequívoco**: Si no hay definiciones claras en el código existente sobre qué cubre el `sha256` a nivel de paquete, documentarlo como "pending definition" y no hacer suposiciones.
## 4. Acceso seguro al paquete: enumeración por descriptores de directorio

### Cambio de diseño: sustituir `Path.rglob()` + `p.is_file()`
- **No use `Path.rglob()` ni `p.is_file()`** como mecanismo principal de enumeración. Estos métodos construyen `Path` objects y pueden introducir vulnerabilidades de symlink y path traversal si no se validan todos los componentes.
- **Use enumeración segura mediante descriptores de directorio**, consistente con las protecciones existentes de CastleArq en `execution.py` y `model_store.py`.

### Patrón de enumeración corregido
1. `root_fd = model_store._open_root(create=False)` — puntero de archivo al directorio raíz.
2. `model_fd = model_store._open_directory(root_fd, safe_model_id, create=False)` — puntero al directorio del modelo.
3. `artifact_fd = model_store._open_directory(model_fd, artifact.artifact_id, create=False)` — puntero al directorio del artefacto.
4. **Enumerar entradas usando `os.listdir(dir_fd)`** sobre el descriptor de directorio, no `rglob` sobre `Path`.
5. Para cada entrada `name` devuelta por `os.listdir`:
   - `full_path = os.path.join(".", name, dir_fd=dir_fd)` (o equivalente del sistema).
   - `mode = os.lstat(full_path, dir_fd=dir_fd).st_mode`
   - **Excluir symlinks**: `if stat.S_ISLNK(mode): continue` o `raise UnsafePathError("Symlink not allowed: " + full_path)`.
   - **Excluir no-regular-files**: `if not stat.S_ISREG(mode): continue`.
   - **Verificar path traversal**: asegurar que el archivo residente dentro del directorio del artefacto, sin componentes `..` en la ruta.
   - **Leer contenido únicamente si es necesario**: usar `os.open(full_path, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)` para lecturas seguras.

### Consistencia con protecciones existentes
- Este patrón coincide exactamente con lo que `ArtifactExecutionPreflight.validate()` ya hace en `execution.py:267-292`:
  - `root_fd = model_store._open_root(create=False)`
  - `model_fd = model_store._open_directory(root_fd, ...)`
  - `artifact_fd = model_store._open_directory(model_fd, ...)`
  - `mode = os.lstat(filename, dir_fd=artifact_fd).st_mode`
  - `if stat.S_ISLNK(mode): raise ArtifactPreflightError(...)`
  - `if not stat.S_ISREG(mode): raise ArtifactPreflightError(...)`
  - `final_fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=artifact_fd)`
- La enumeración de directorios debe usar el mismo enfoque de descriptores en lugar de construcciones `Path` libres.
## 5. Detección de modificaciones, creaciones y eliminaciones durante el cálculo de hash

### Limitaciones TOCTOU: no snapshot atómico
- **No describa el proceso como una snapshot atómica si no existe esa garantía.** El diseño actual ofrece verificación posterior a la copia, no snapshot antes de la copia.
- **Ventana de TOCTOU**: entre la enumeración de directorio y la lectura de contenido, otro proceso podría crear, modificar o eliminar archivos.

### Cómo detectar cambios reales (patrones documentados)
1. **Modificación de contenido existente**:
   - Se computes SHA-256 del archivo y se compara contra el `content_id` (identidad) o `sha256` (declaración de integridad).
   - Si los digests difieren, `FAILED` con mensaje descriptivo (checksum mismatch).

2. **Archivo creado (nuevo entry en el directorio)**:
   - Si el algoritmo de enumeración incluye archivos nuevos que no estaban en la inspección previa, se incluirán en el `content_id` computation (ya que se hashea todos los archivos regulares observados).
   - Si la expectativa es que solo ciertos archivos existan, la discrepancia entre "lo observado" y "lo esperado" se reporta mediante la diferencia de estados.

3. **Archivo eliminado**:
   - Si un archivo previamente observado ya no existe durante la lectura, `os.open()` o `os.lstat()` levantarán `FileNotFoundError`.
   - Esto se captura como `MISSING_ARTIFACT` en `ArtifactExecutionPreflight.validate()` (execution.py:321-325).
   - El `content_id` computation fallará al leer un archivo que ya no existe.

4. **Documentación de límites reales**:
   > El preflight verifica tamaño y checksum en el momento de la lectura sobre los archivos observados en ese momento. No hay garantía de snapshot atómico: un proceso concurrente podría crear, modificar o eliminar archivos entre la enumeración del directorio y la lectura de su contenido. El campo `content_id` en el manifest permite detectar discrepancias en inspecciones posteriores, pero no previene la ventana de TOCTOU en la misma ejecución.
```
## 6. Matriz de pruebas corregida

La matriz de pruebas debe diferenciar estos escenarios:

| Test | Descripción |
|------|-------------|
| **Ningún identificador** | `content_id=None`, `sha256=None`. Importador GGUF puro. `content_id` se computes pero `sha256` se deja `None`. `inspect_manifest(verify=False)` retorna `DOWNLOADED`. |
| **Solo `content_id`** | `content_id` presente (SHA-256 de los bytes), `sha256=None`. Verificar `content_id` contra bytes observados. No hay verificación de `sha256`. |
| **Solo `sha256`** | `content_id=None`, `sha256` declarado. Compute `content_id` desde bytes. Verificar `sha256` contra archivo. Cualquier discrepancia → `FAILED`. |
| **Ambos identificadores** | `content_id` presente y `sha256` declarado. Verificar **ambos independientemente**. Cualquier discrepancia en cualquiera → `FAILED`. |
| **`content_id` incorrecto** | `content_id` no coincide con SHA-256 de los bytes observados. `FAILED` con mensaje de identity mismatch. |
| **`sha256` incorrecto** | `sha256` declarado no coincide con SHA-256 computed del archivo. `FAILED` con mensaje de checksum mismatch. |
| **Modificación de XML** | `openvino_model.xml` modificado después de iniciar importación. El `.part` atomically copied contiene el XML original; `inspect_manifest` vería la discrepancia si `verify=True`. |
| **Modificación de BIN** | `openvino_model.bin` modificado. `_copy_atomically` verifica digest al final (importing.py:299-309); si el digest no coincide, `FAILED`. |
| **Modificación de archivos auxiliares** | Archivos en `artifact.files` y `file_checksums` modificados. `inspect_manifest` verifica checksums auxiliares (models.py:381-396) contra `file_checksums` del manifiesto. |
| **Archivo añadido** | Archivo nuevo incluido en el directorio fuente. El algoritmo de enumeración lo incluye en el `content_id` computation (ya que se hashea todo archivo regular observado). Si no estaba esperado, la identidad cambia. |
| **Archivo eliminado** | Archivo previamente presente eliminado antes de la inspección. `FileNotFoundError` → `MISSING_ARTIFACT` en preflight. |
| **Symlinks y traversal** | Symlinks al directorio fuente o archivos dentro: `os.lstat(dir_fd=...)` + `S_ISLNK` → `UnsafePathError`. `O_NOFOLLOW` en `os.open()` previene seguimiento de symlinks en kernel. |
| **Ausencia de regresiones GGUF** | Importador GGUF existente: `content_id` computed, `sha256=None`, manifest con `state=DOWNLOADED/UNKNOWN`. Cambios en OpenVINO `import_directory` no deben afectar el flujo GGUF. |
```
## 7. Funciones que cambiarían (solo diseño, sin código de producción)

1. **`conversion.py`** — `OpenVINOConversionService.convert()` reutiliza `_is_under_git_dir`, `sorted()`, y patrón devalidación de archivos. El nuevo `import_directory()` método en `OpenVINOImportService` usa enumeración por descriptores de directorio (`os.listdir(dir_fd)`) en lugar de `Path.rglob()`.

2. **`importing.py`** — Nuevo método `import_directory()` en `OpenVINOImportService` que:
   - Usa `os.listdir(dir_fd)` sobre descriptores de directorio abiertos.
   - Filtra symlinks con `stat.S_ISLNK(mode)` y no-regular files con `stat.S_ISREG(mode)`.
   - Colecta `(relative_path, size, sha256_per_file)` en orden determinista (`sorted()` + `as_posix()`).
   - Excluye `.git` directories usando `_is_under_git_dir()`.
   - Copia atómica mediante `.part` + digest verification (patrón GGUF).
## 9. Secuencia de implementación (6 steps, sin modificar código de producción)

1. **Verificar y documentar** `artifact.backend == "openvino"` es el campo correcto para identificar artefactos OpenVINO IR.
2. **Implementar `import_directory()`** en `OpenVINOImportService` usando **enumeración por descriptores de directorio** (`os.listdir(dir_fd)`), **no** `Path.rglob()` + `p.is_file()`. Incluir filtros de symlink y regular files via `stat.S_ISLNK` / `stat.S_ISREF`. Excluir `.git` directories. Colectar `(relative_path, size, sha256_per_file)` en orden determinista.
3. **Verificar separación de contratos**: `inspect_manifest()` devuelve estados de inspección; `ArtifactExecutionPreflight.validate()` admite/rechaza ejecución basándose en esos estados más verificaciones de tamaño/checksum. No confundir uno con otro.
4. **Ejecutar matriz de tests corregida**: Ningún identificador, solo `content_id`, solo `sha256`, ambos identificadores, `content_id` incorrecto, `sha256` incorrecto, modificaciones de XML/BIN/auxiliares, archivo añadido/eliminado, symlinks, GGUF sin regresiones.
5. **Documentar limitaciones TOCTOU** reales en el diseño: no snapshot atómico, ventanas de race condition inherentes, mitigaciones prácticas (`O_NOFOLLOW`, descriptores de directorio).
6. **Revisión final**: documento de diseño corregido (solo análisis y diseño), sin archivos de producción modificados, sin operaciones Git, sin expansión a SYCL.
## 8. Garantías de seguridad reales (corregidas)

| Garantía | Implementación | Limitación |
|----------|----------------|------------|
| Symlink rejection | `os.lstat(dir_fd=...)` + `S_ISLNK` (execution.py:280-284); `O_NOFOLLOW` | Ventana TOCTOU entre lstat y open — otro proceso podría reemplazar el archivo |
| Path traversal prevention | `UnsafePathError` en `model_store.py` y `inspection.py`; validación de que `relative_to(source)` no atraviesa `..` | Requiere que todos los caminos pasen por estas validaciones |
| Checksum verification | `hmac.compare_digest()` de SHA-256 (execution.py:307-308); verificación tanto de `content_id` como de `sha256` | Solo verifica lo que se leyó en ese momento — no previene cambios concurrentes |
| Atomic copy | Write to `.part` → `os.link()` → `os.unlink()` (importing.py:235-319) | Ventana de race entre `os.link()` y verification of digest — el `.part` nunca es visible como nombre final si falla |
| Identity vs declaration | `content_id` = digest computed de todos los archivos regulares en orden determinista; `sha256` = declaración del usuario (opcional) | **Diseño deliberado**: no hay confusión entre los dos; son verificaciones independientes |
| Sin snapshot atómico | Documentado: verificación posterior a la copia, no snapshot antes | Las ventanas TOCTOU son inherentes sin coordinación de proceso |
## 10. Entrega: decisiones corregidas y contratos pendientes

### Decisiones corregidas respecto al diseño anterior:

1. **`content_id` ya no se asume que es hash del XML individual**: Es el SHA-256 compuesto del paquete completo, calculado de manera determinística desde todos los archivos regulares observados, rutas relativas POSIX y ordenados.

2. **Algoritmo de enumeración cambiado**: De `Path.rglob()` + `p.is_file()` a **enumeración segura por descriptores de directorio** (`os.listdir(dir_fd)`), con filtros `S_ISLNK`/`S_ISREG` consistentes con CastleArq existentes.

3. **Contrato B9.67 aclarado**: `content_id` y `sha256` son verificaciones independientes. Si ambos existen, verificarlos ambos. Si solo uno, verificar ese uno. Si ninguno, rechazar. Nunca copiar un identificador al otro.

4. **Verificación de `sha256` sin suposiciones**: No se asume que representa el paquete completo ni el XML individual. Es un campo opcional de declaración; si está presente, se verifica contra el archivo observado. Si no hay contrato inequívoco, documentar como "pending definition" hasta que se establezca un contrato claro.

5. **Detección de cambios sin snapshot atómico**: Documentadas ventanas TOCTOU reales. No describir proceso como atomic snapshot si no existe garantía. Documentar modificaciones, creaciones y eliminaciones detectables con límites conocidos.

6. **Matriz de tests diferenciada**: 9 escenarios distintos (ningún identificador, solo `content_id`, solo `sha256`, ambos, cada uno incorrecto, modificaciones de XML/BIN/auxiliares, archivo añadido/eliminado, symlinks, GGUF sin regresiones).

### Contratos que siguen sin poder determinarse:

1. **Significado semántico exacto de `sha256` a nivel de paquete**: Si el `sha256` declarado por el usuario cubre todo el paquete, solo ciertos archivos, o tiene algún otro significado no definido en el código existente. **Decisión pendiente**: documented as "pending definition" hasta que se establezca un contrato inequívoco.

2. **Comportamiento de `content_id` cuando el usuario declara también `sha256` y estos entran en conflicto**: El diseño actual los trata como verificaciones independientes (ambos deben ser válidos), pero si surgen casos de uso que requieren una interpretación diferente, requeriría decisión de diseño explícita.

3. **Nivel de consistencia garantizado en ejecuciones concurrentes**: Se documentan las limitaciones TOCTOU, pero el nivel exacto de garantías (solo "eventualmente consistente", "consistente en la mayoría de los casos", etc.) requeriría especificaciones formales adicionales.

4. **Política de qué sucede cuando `content_id` y `sha256`both están presentes pero uno es inválido**: ¿Fallar la ejecución completamente, o advertir y continuar? El diseño actual falla (`FAILED`), pero esto podría ser un punto de ajuste según necesidades operativas.
```
   - No usa `Path.rglob()` ni `p.is_file()` como mecanismo principal.