# Native Method Detection

This directory contains EchoTrace's bytecode analysis detectors. Each detector targets a different mechanism by which Java code invokes native (C/C++) functions.

For a **deep dive on JNI static detection**, **`PrototypeFinal`**, **application vs JDK natives**, and **cross-JDK JUnit results**, see **[JNI_INTERFACE_DETECTION.md](./JNI_INTERFACE_DETECTION.md)**.

For the end-to-end overview, see **[docs/NATIVE_METHOD_ANALYSIS.md](../../../../../../../docs/NATIVE_METHOD_ANALYSIS.md)** (and its PDF): a short guide with one simple example per mechanism showing how it is found and how its library and C function are resolved, why we require a call site (hit), and the status of known limitations. Per-detector phase details are in this README.

## Overview

Java applications reach native code through several interfaces. Each has a distinct bytecode signature that requires a specialized detection strategy:

| Type | Detector | What it finds |
|------|----------|---------------|
| JNI Static | `PrototypeFinal` | `native` keyword declarations |
| JNI Dynamic | `scripts/extract_registernatives_binary.py`, `scripts/extract_jni_bindings.py` (binary-level, not in this package) | `JNINativeMethod[]` tables passed to `RegisterNatives()` |
| JNA Interface Mapping | `JnaIfaceDetector` | Call sites on interfaces extending `com.sun.jna.Library` |
| JNA Dynamic | `JnaDynDetector` | `NativeLibrary.getInstance().getFunction()` |
| JNA Direct Mapping | `JnaDirectMapDetector` | Classes calling `Native.register()` |
| Panama FFI | `FfiDetector` | `java.lang.foreign` / `jdk.incubator.foreign` |
| jnr-ffi | `JnrFfiDetector` | `LibraryLoader.create().load()` |

---

## 1. JNI Static Binding

**File:** `PrototypeFinal.java`

**Java pattern:**
```java
public class System {
    public static native long nanoTime();
}
```

**How we detect it (Mode `--1`, ASM — the mode `JNADetector` runs):**
- Sweep every `.class` file in the target JARs; any method with the `ACC_NATIVE` (0x100) flag is recorded
- Follow every `invoke*` instruction into the callee's class (loaded from an isolated, parent-less `URLClassLoader` over the target JARs + `--runtime` JARs) and record the callee if it is native; recurse into callees that have bodies
- `--runtime` JARs (the container JDK) are **not** swept, so a JDK native is reported only when application bytecode reaches it
- Mode `--2` does the same reachability with a SootUp worklist and `MethodModifier.NATIVE` (output: `sootup_visitor_natives.txt`)

**Symbol naming convention:**
The JVM resolves these automatically to `Java_<package>_<Class>_<method>`:
```
java.lang.System.nanoTime  →  Java_java_lang_System_nanoTime (in libjava.so)
```

**Output:** `native_methods.txt` (one `fully.qualified.Class.method` per line, no descriptor)

**Limitations:** Natives declared in the target JARs are always found. For runtime natives, each invoke is resolved like the JVM does (the instruction's owner, then its superclasses, then superinterfaces), so inherited methods are followed. Static initializers (`<clinit>`) run on first use of a class (`NEW`, static field access, `INVOKESTATIC`) are visited too. Virtual-dispatch overrides and `invokedynamic` are not explored. *Mapping* the method to a library is done downstream by `mapped_updated.py`.

---

## 2. JNI Dynamic Binding (RegisterNatives)

**Files:** `scripts/extract_registernatives_binary.py`, `scripts/extract_jni_bindings.py` (invoked from `scripts/mapped_updated.py`). There is no Java detector for this mechanism: the Java side is an ordinary `native` declaration already in `native_methods.txt`; the Java→C pairing exists only in the `.so`.

**C pattern (inside `.so`):**
```c
static JNINativeMethod methods[] = {
    {"beginRecording", "()V", (void*)jfr_begin_recording},
    {"isRecording",    "()Z", (void*)jfr_is_recording},
};

JNIEXPORT void JNI_OnLoad(JavaVM *vm, void *reserved) {
    (*env)->RegisterNatives(env, cls, methods, 3);
}
```

**How we recover it:**

`extract_registernatives_binary.py` (disassembly-driven; `libjvm.so`, JFR, Netty, ...):
1. Find registration code: exported `*registerNatives*` functions (`nm -D`), indirect calls through the JNI function table (`call *0x6b8(%reg)` = `RegisterNatives`), and known wrapper helpers
2. From the preceding instructions, recover the array address (`LEA …(%rip),%rdx`) and count (`MOV $N,%ecx`); follow `rep movsq` stack/heap copies back to the static source; also probe arrays found via data symbols
3. Decode 24-byte `{name, signature, fnPtr}` records using ELF load segments and `R_X86_64_RELATIVE` / `R_X86_64_64` relocations; reject records whose name is not Java-identifier-shaped or whose descriptor does not start with `(`
4. Attribute the owning class from the nearby `FindClass` string, or infer it from symbol/library names

`extract_jni_bindings.py` (relocation-driven; third-party libs such as Netty, tcnative, Hadoop):
1. Qualify libraries that export `JNI_OnLoad`
2. Group `R_*_RELATIVE` relocations in RELRO sections by stride 24
3. Validate each `(name, sig, fn)` triple; `fn` must resolve to a `.text` symbol
4. Derive the Java class from the C symbol prefix (`HIGH_CONF` if confirmed by a class-path string in `.rodata`, else `SYM_INFER`)

**Output:** `jni_dynamic_bindings.txt` (`<lib>|<JavaFQN>|<signature>|<C_symbol>|<confidence>`); `mapped_updated.py` tags matches `[JNI_DYNAMIC]`. OpenJDK source scanning (`JVM_SRC`) is only a fallback.

**Limitations:** Arrays built entirely at run time, or modified after copying, can be missed; class attribution is heuristic; one target is kept per (library, class, method, descriptor); decoding assumes x86-64 ELF.

---

## 3. JNA Interface Mapping

**File:** `JnaIfaceDetector.java`

**Java pattern:**
```java
public interface CLib extends Library {
    CLib INSTANCE = Native.load("c", CLib.class);
    int strlen(String s);
    int getpid();
}

// Usage:
CLib.INSTANCE.strlen("hello");
```

**How we detect it:**
1. **Diagnostic scan:** Print every raw `Native.load` / `Native.loadLibrary` call, to confirm calls exist when later phases report zero hits
2. **Fact collection (fixed point, max 4 iterations, over ALL method bodies — not only `<clinit>`):** Map synthetic accessors (`access$NNN`) to their fields, summarize helpers that return a loaded library, and propagate load facts (`Native.load` / `Native.loadLibrary` in all overloads, including `Native.load(null, Class)` → default C library) through locals and fields keyed by field signature
3. **Call-site matching:** For every invoke whose declaring type extends `com.sun.jna.Library` (memoized hierarchy walk through `StdCallLibrary`, custom intermediates), resolve the receiver's load fact and emit a hit — the invoked method name IS the native symbol (JNA convention). Interface methods with no call site in the scanned bytecode are **not** reported

**Taint tracking:**
- Tracks `Native.load()` return value through field assignments (`INSTANCE = Native.load(...)`)
- Handles `Native.synchronizedLibrary(...)` wrappers
- Handles conditional library names (`Platform.isWindows() ? "msvcrt" : "c"`) by accumulating all branch values

**Filtering:** Windows/macOS/Solaris packages and libraries (`com.sun.jna.platform.win32`, `kernel32`, `CoreFoundation`, ...) are dropped; framework JARs (`jna-*`, `jnr-*`, `jffi-*`, `hawtjni-runtime-*`) are excluded from the scan. Hits are deduplicated by `callerSig|lib|symbol|iface`.

**Output:** `jna_iface_hits.txt` (positional, pipe-separated)
```
callerSig | lib | symbol | apiPattern | interface | calleeSig | callerJar | calleeJar
```

**Limitations:** If the library name is computed at runtime (not a string constant), `lib` is `<?>`. All uses of an invoke (receiver and arguments) are checked for taint, so a `Library` passed as an argument can be misattributed.

---

## 4. JNA Dynamic Use

**File:** `JnaDynDetector.java`

**Java pattern:**
```java
NativeLibrary lib = NativeLibrary.getInstance("c");
Function fn = lib.getFunction("mmap");
fn.invoke(int.class, new Object[]{addr, length, prot, flags, fd, offset});
```

**How we detect it:**
1. **Fact collection (fixed point, max 4 iterations, all method bodies):** Summarize helpers returning strings, `NativeLibrary`, or `Function` objects, and track `NativeLibrary.getInstance("libname")` / `.getFunction("symbolName")` through locals and fields → `local/field → FuncInfo(lib, symbol)`
2. **Sink matching:** Detect `com.sun.jna.Function.invoke*()` calls and resolve the receiver back to a `FuncInfo`. Uses all classes (JNA's own classes contribute facts), but callers inside `com.sun.jna.*` are not reported (internal delegation)

**API variants detected:**
- `NativeLibrary.getInstance(String)` → lib from string constant
- `NativeLibrary.getFunction(String)` → symbol from string constant
- `Function.getFunction(String, String[, int[, String]])` → lib + symbol directly
- `Function.getFunction(Pointer[, int])` → **unresolvable** (COM vtable)

**Output:** `jna_dyn_hits.txt` (positional, pipe-separated)
```
callerSig | lib | symbol | apiPattern | sinkSig | stmt
```

**Limitations:**
- `Function.getFunction(Pointer)` with a runtime pointer (COM vtable dispatch) — `lib` and `symbol` are `<?>` because the vtable offset doesn't reveal the function name
- Dynamically computed library/symbol names

---

## 5. JNA Direct Mapping

**File:** `JnaDirectMapDetector.java`

**Java pattern:**
```java
public class CLibrary {
    static {
        Native.register("c");  // binds ALL native methods in this class to "c"
    }
    public static native int strlen(String s);
    public static native int getpid();
}
```

**How we detect it:**
1. **String-helper summaries (fixed point, max 5 iterations):** Summarize helpers that return constant strings (`static String libName() { return "c"; }`)
2. **Registration scan:** Scan **all method bodies** (not only `<clinit>`) for `Native.register(String)`, `Native.register(Class, String)`, `Native.register(NativeLibrary)`, `Native.register(Class, NativeLibrary)` — extract the library name. For the `Class` overloads, the registered class is the `Class` argument, not the calling class. One association per class; an unresolved `<?>` never overwrites a resolved name
3. **Native declaration listing:** For each registered class, enumerate all methods with `ACC_NATIVE` modifier — each method name IS the C symbol (JNA direct-mapping convention). No call site is required

**Key difference from Interface Mapping:** Direct mapping uses `native` method declarations (like JNI) but resolves them at class-load time via JNA's runtime registration, not the JVM's standard `Java_*` symbol lookup.

**Output:** `jna_directmap_hits.txt` (positional, pipe-separated)
```
methodSig | lib | symbol | apiPattern | jar
```

**Limitations:** If `Native.register(NativeLibrary.getInstance(computedName))` uses a runtime-computed name, `lib` is `<?>`.

---

## 6. Panama FFI (Foreign Function & Memory API)

**File:** `FfiDetector.java`

**Java pattern (Java 22+ finalized API):**
```java
SymbolLookup lookup = SymbolLookup.libraryLookup("ssl", arena);
MemorySegment addr = lookup.find("SSL_read").orElseThrow();
MethodHandle handle = Linker.nativeLinker().downcallHandle(addr, descriptor);
int result = (int) handle.invokeExact(ssl, buf, len);
```

**Java pattern (Java 17-21 incubator API):**
```java
LibraryLookup lookup = LibraryLookup.ofLibrary("ssl");
MemoryAddress addr = lookup.lookup("SSL_read").get();
MethodHandle handle = CLinker.getInstance().downcallHandle(addr, methodType, descriptor);
```

**How we detect it:**
1. **Fact collection (fixed point, max 4 iterations, all method bodies):**
   - library discovery: `SymbolLookup.libraryLookup("libname", ...)` / `LibraryLookup.ofLibrary("libname")`; `System.mapLibraryName(x)` passes `x` through; `System.getProperty(key, default)` contributes the default
   - symbol resolution: `.find("symbol")` / `.lookup("symbol")` and jextract's `findOrThrow(String)`, through `Optional.orElseThrow()` / `get()`
   - handle binding: `Linker.downcallHandle(addr, ...)` / `CLinker.downcallHandle(...)` connects the handle to the resolved symbol
2. **Downcall matching:** Detect `MethodHandle.invokeExact(...)` / `invoke(...)` on a tracked handle and resolve it to library+symbol. For classes whose bodies fail to build (e.g. jextract output on JDK 22+ → `VerifyError`), infer the symbol from the class name (`openssl_h$SSL_read`) and verify it against the `nm` exports of `LIBS_<IMG>/`
3. **jextract parent fallback:** For parent classes with `$<n>Holder` inner classes that downcall matching mostly missed, emit C-identifier-shaped method names (index-verified when the class has any exported symbol)

**Both API generations detected:**
- `java.lang.foreign.*` (Java 22+ finalized)
- `jdk.incubator.foreign.*` (Java 17-21 incubator)

**Output:** `ffi_hits.txt` (positional, pipe-separated)
```
callerSig | lib | symbol | downcallHandle | jar
```

**Limitations:**
- `Linker.nativeLinker().defaultLookup().find(...)` (and incubator `CLinker.getInstance()`) resolves from the default C library — library is tagged `<default-c-lib>`; `SymbolLookup.loaderLookup()` is tagged `<loader>`
- If the symbol name is computed at runtime, or the downcall handle has no fixed address, `symbol` is `<?>`

---

## 7. jnr-ffi (JRuby Native Runtime)

**File:** `JnrFfiDetector.java`

**Java pattern:**
```java
public interface LibC {
    int getpid();
    int kill(int pid, int signal);
}

LibC libc = LibraryLoader.create(LibC.class)
    .library("c")
    .load();
libc.getpid();
```

**How we detect it:**
1. **Loader discovery (two iterations, `<clinit>` only):** Find `LibraryLoader.create(Interface.class).library("libname").load()` chains or `Library.loadLibrary(...)` calls — extract interface + library names (accumulated per interface)
2. **Call-site matching (preferred):** Report call sites of methods declared by a discovered interface — each method name IS the C symbol (same convention as JNA)
3. **Interface enumeration (fallback):** For a loaded interface with no visible call site, enumerate all non-static methods of the interface and its superinterfaces

**API variants:**
- `LibraryLoader.create(I.class).library("c").load()` — chained builder
- `LibraryLoader.create(I.class).load("c")` — direct string
- `Library.loadLibrary(I.class, "c")` — legacy static factory

**Output:** `jnr_ffi_hits.txt` (positional, pipe-separated)
```
interface | lib | symbol | apiPattern | jar
```

**Limitations:** Same as JNA interface mapping — runtime-computed library names are unresolvable. Loaders outside `<clinit>` and custom symbol mappers (`FunctionMapper`) are not modeled.

---

## Running the Detectors

> Console logs label the phases above `[PASS 0]`–`[PASS 3]` (summaries → fact collection → matching → fallback).

The normal entry point runs everything (dyn → iface → directmap → ffi → jnr-ffi → `PrototypeFinal --1`) and merges the hits into `jna_hits.txt` / `ffi_all_hits.txt`:

```bash
mvn -f pom.xml -q clean compile exec:java \
  -Dexec.mainClass=com.echotrace.app.bytecode_new.JNADetector \
  -Dexec.args="<JARFILES_dir> [outputs_dir] [RUNTIME_dir]"
```

`JNADetector` passes the runtime directory to `PrototypeFinal` as `--runtime`, and to the SootUp detectors by setting `detector.runtime.dir` while they run (an explicit `-Ddetector.runtime.dir` still wins). The host JRE is only a last-resort fallback for types the runtime directory doesn't carry.

`PrototypeFinal` uses ASM; the other detectors use SootUp (Jimple IR). Each can also be run on its own against the target application's JAR directory:

```bash
# JNI static (Mode 1: scan <app-jars-dir>; add --runtime <dir> for staged java.base / modular JARs)
java -cp "target/echotrace-1.0-SNAPSHOT.jar:target/deps/*" \
  com.echotrace.app.bytecode_new.PrototypeFinal <app-jars-dir> --1 [--runtime <runtime-jars-dir>]

# JNA Interface Mapping
java -cp "target/echotrace-1.0-SNAPSHOT.jar:target/deps/*" \
  com.echotrace.app.bytecode_new.JnaIfaceDetector <jars-dir>

# JNA Dynamic
java -cp "target/echotrace-1.0-SNAPSHOT.jar:target/deps/*" \
  com.echotrace.app.bytecode_new.JnaDynDetector <jars-dir>

# JNA Direct Mapping
java -cp "target/echotrace-1.0-SNAPSHOT.jar:target/deps/*" \
  com.echotrace.app.bytecode_new.JnaDirectMapDetector <jars-dir>

# Panama FFI
java -cp "target/echotrace-1.0-SNAPSHOT.jar:target/deps/*" \
  com.echotrace.app.bytecode_new.FfiDetector <jars-dir>

# jnr-ffi
java -cp "target/echotrace-1.0-SNAPSHOT.jar:target/deps/*" \
  com.echotrace.app.bytecode_new.JnrFfiDetector <jars-dir>

# JNI Dynamic (binary-level, not bytecode; normally invoked by mapped_updated.py)
python3 scripts/extract_registernatives_binary.py <path/to/lib.so> [...]
python3 scripts/extract_jni_bindings.py --libs-dir <LIBS_dir> [--output-dir <dir>]
```

---

## How Results Feed into the Pipeline

```
 Bytecode Detectors                    Binary Analysis
 ──────────────────                    ───────────────
 PrototypeFinal ──→ native_methods.txt
 JnaIfaceDetector ──→ jna_iface_hits.txt     extract_registernatives_binary.py
 JnaDynDetector ──→ jna_dyn_hits.txt         extract_jni_bindings.py
 JnaDirectMapDetector ──→ jna_directmap_hits.txt       │
 FfiDetector ──→ ffi_hits.txt                ──→ jni_dynamic_bindings.txt
 JnrFfiDetector ──→ jnr_ffi_hits.txt                   │
        │                                              │
        ▼                                              ▼
 ┌─────────────────────────────────────────────────────────┐
 │              mapped_updated.py (mapper)                  │
 │  Maps Java methods → C symbols → owning .so library     │
 └─────────────────────────────────────────────────────────┘
                          │
                          ▼
              mapped_method_syscalls.txt
                          │
                          ▼
 ┌─────────────────────────────────────────────────────────┐
 │           SysPart (binary value-flow analysis)           │
 │     Traces C functions → reachable Linux syscalls        │
 └─────────────────────────────────────────────────────────┘
                          │
                          ▼
                  seccomp profile
```
