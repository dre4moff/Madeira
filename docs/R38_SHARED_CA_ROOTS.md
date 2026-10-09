# r38: preserve trusted CA roots across Windows processes

The r37 phone session keeps Steam authenticated and no longer drops Darwin
UDP TOS messages. The game still cannot browse, join or create online rooms.
Its own Unity Player.log reports repeated `SSL CA certificate error` responses
from its backend; its Discord SDK also reports TLS handshake failures. The same
game works in CrossOver on the Mac using the same network.

Read-only inspection of the installed app's registry finds only Wine's five
built-in Microsoft root certificates and no host-imported certificates. The
session log records 121 Mozilla CA roots loaded earlier in the session.
No account identifiers, tickets, game files or private logs are distributed.

The iOS crypt32 unix shim is shared by every Windows process. Its native root
enumerator copied and freed each root once, as desktop Wine does in separate
Unix processes. The later game's import therefore observed an empty host list.
Wine's root synchronization removes previously imported certificates absent
from that list, explaining the observed registry contents. Its WoW64 enumerator
already avoided consuming roots, but native enumeration could empty that shared
list before a 32-bit caller used it.

r38 retains the immutable list and gives every calling thread its own native
or WoW64 enumeration position. It advances only after a successful copy, resets
after completing the list, and preserves the existing ten-second idle recovery.
Thread-local cursors are released when their threads exit, without a shared
32-caller limit. Standard Wine certificate import and TLS validation remain in
use; the bundled Mozilla certificate set is unchanged. No game, service identity
or certificate acceptance result is patched.

`tests/test_shared_ca_roots.py` compiles the production native enumerator and
32-bit thunk with ASan/UBSan. The r37 fixture reproduces 121 roots on the first
native import and zero on the second. The correction preserves the byte-identical
DER certificates across repeated native/WoW64 imports and 64 concurrent callers,
including buffer-sizing retries, exact capacities and a genuinely empty store.

Only `crypt32_unixlib.o` in the existing iOS `libntdll_unix.a` is rebuilt with
`MADEIRA_ONLY=crypt32_unixlib`. Other archive members, the 15 other native
archives, all Windows DLLs and Dock remain byte-identical to the verified r37
inputs. Optimized unsigned Release build 23 retains the existing runtimes,
Mono, licenses and separate debug symbols. Public packaging compares every
resource with the verified r37 IPA and checks PE import closure.

The source defect and affected r37 device trust store are verified. Installing
r38 and restarting Madeira should let Wine repopulate the normal trusted roots
without deleting user data. Successful backend TLS and real lobby creation/joining
on that new phone build still require a fresh device session; the generic Photon
`Error` alone does not establish whether a further issue will remain.

Unity documents that default
[UnityWebRequest certificate validation uses the available trusted root store](https://docs.unity.com/en-us/engine/6000.6/script-reference/unityengine/networking/unitywebrequest/certificatehandler).
The deletion behavior is in the pinned `wine/dlls/crypt32/rootstore.c`,
`sync_trusted_roots_from_known_locations`.
