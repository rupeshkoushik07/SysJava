# Syscall sets behind the allowlist rows

One file per image with the sets the table generator uses: `java` (Java-library syscalls),
`binary` (observed executables), `unan_raw` (libraries loaded without a recovered binding),
`runc_raw` (container-runtime allowlist). The paper's rows count each component as an increment
over the rows above it (Java, Observed-binaries, DLL, Docker runtime):

```bash
python3 tools/syscall_increments.py <this folder>
```
