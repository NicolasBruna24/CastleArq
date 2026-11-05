# CastleArq Core v0.6.2 - Changelog

## 0.6.2 - Unreleased

### Added

- **Artifact integrity persistence**: SHA-256 hashes of imported artifacts are now persisted (commit 349f7bb)
- **Explicit runtime backend selection**: Added capability to explicitly select and validate runtime backends (commit 4b7bfaf)
- **Backend-aware runtime version validation**: Runtime version validation is now backend-aware (commit 153e029)
- **SYCL runtime capability detection**: Experimental SYCL runtime detection added (commit 97ef1ef)
- **SYCL experimental support**: Experimental SYCL backend support added (commit de53f3b)
- **Artifact format in JSON CLI output**: JSON CLI output now includes artifact format information (commit 6e71213)
- **OpenVINO IR artifact support**: Added support for importing IR artifacts, validating them, and using them through inference service and chat/API integration (commit 54e086c)
- **Local OpenVINO model conversion**: Experimental local model conversion support to OpenVINO format (commit 6276721)
- **OpenVINO artifact chat sessions**: Experimental OpenVINO artifact chat session support added (commit 00e03dc)

### Changed

- **SYCL runner dispatch**: Integrated SYCL runner dispatch into run service (commit 3cca47b)
- **Runtime module unification**: Unified execution preparation and runner construction (commit 5708068)
- **Artifact backend contracts**: Enhanced artifact backend contract validation (commit 4e4eee2)
- **OpenVINO service lifecycle**: Improved OpenVINO service lifecycle management (commit 47a3f11)
- **Artifact import flow**: Strengthened artifact integrity enforcement during import and execution (commit a89fbf8)

### Fixed

- **OpenVINO GenAI export compatibility**: Corrected the task configuration used for GenAI exports (commit 20a4bd4)
- **Empty OpenVINO model XML rejection**: Rejection of empty model XML files during import (commit d592763)
- **Imported content identity**: Separated imported content identity from SHA-256 declaration (commit 360a47b)

### Experimental

- **SYCL backend**: Experimental SYCL runtime capability detection and dispatch capabilities
- **OpenVINO integration**: Experimental OpenVINO capabilities including local model conversion, IR artifact import, validation and manifest resolution, and inference / chat sessions

### Known Limitations

- SYCL functionality requires compatible hardware, drivers, and SYCL runtime components
- OpenVINO functionality remains experimental and not yet part of the stable runtime interface

---
*Release verification completed successfully with 65 focused tests passing. Wheel and source distribution SHA-256 integrity verified. Environment isolation confirmed.*
