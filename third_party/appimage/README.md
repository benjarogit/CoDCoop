# AppImage runtime

The Linux Setup AppImage embeds the unmodified upstream type-2 runtime from
https://github.com/AppImage/type2-runtime/commit/8f39b89.
`LICENSE` is copied from that exact revision and includes the runtime's MIT
copyright notice and the notices/terms for its statically linked dependencies.
The upstream repository includes the runtime source and its build workflow.

The runtime is extracted from the already pinned appimagetool AppImage:

- appimagetool: SHA-256
  `95cbe7cce9717fce90c484e34052ee7c7f1d7635b33c12525b4776826a7d29b6`,
  appimagetool build commit `854e19e`.
- embedded runtime prefix: SHA-256
  `77f59c85aa4b171adf01d1870d86a53fcdeee7e27b31d119beb420dc4f140b66`,
  runtime commit `8f39b89`.

`tools/build-portable-linux.sh` verifies these bytes. Setup packaging supplies
`--runtime-file` explicitly, preventing an implicit update from a mutable
upstream download. The ELF is a static x86-64 PIE and has no glibc symbol-version
requirements; the separately bundled Qt/Python application is checked against
the declared glibc 2.35 floor. A compatible replacement runtime can be built
from upstream source and selected when rebuilding the AppImage.
