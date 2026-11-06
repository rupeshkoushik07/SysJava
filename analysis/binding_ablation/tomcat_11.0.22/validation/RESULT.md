# Binding arm: own graph vs. the all-roots graph (Tomcat 11.0.22, libssl.so.3)

Question: can the binding (B) result be read off the call graph rooted at every
function (A), instead of building a graph from B's start functions?

Same library file, SysPart June build (`/home/user/SysPartCode`), same
`lean_syscalls.py` BFS and the same 75 binding start functions (the FFM
downcall symbols libssl.so.3 defines); only the graph's roots differ.

| Graph rooted at | Syscalls reachable from the 75 binding functions |
|---|---:|
| every libssl function (A graph) | 59 |
| the 75 binding functions only (`run_libssl_binding_only.sh`) | **44** |
| pipeline's own FFM run (`compute_syscalls_lowmem.sh`, 200 names) | 44 |

Only via the A graph: `bind connect getpeername getsockname getsockopt poll readv
recvfrom recvmsg sendmmsg sendmsg sendto setsockopt shutdown socket`.

Cause: SysPart resolves an indirect call against the functions whose address is
taken in the code it reaches. The A graph reaches libc's getaddrinfo, which
takes the address of `rfc3484_sort` (a qsort comparator); every indirect call,
including the one in `SSL_ctrl`, then gets an edge to it, and
`rfc3484_sort -> __check_native -> socket` follows. A binding-only graph never
reaches getaddrinfo, so the edge does not exist.

In this SysPart build the address-taken indirect-target set is shared by all
indirect call sites (in both graphs ~99% of sites get the identical set), but it
is collected from the code the graph reaches, so it depends on the roots: about
3,690 targets per site in the A graph and 3,590 in the binding-only graph, which
lacks `rfc3484_sort`. Hence the binding subset of the all-roots graph is not a
valid binding measure.

Consequence: the binding arm must come from its own graph for every library.
`run_ablation.sh` (TARGETS mode) now builds one graph per arm. The earlier
all-roots binding results are kept in `../B_from_all_roots/` for reference
(libssl 59, libcrypto 62, libtcnative-2 61, libnet 107, libzip 104).

Tomcat 7.0.109 is not affected: its A and B were separate SysPart runs.
