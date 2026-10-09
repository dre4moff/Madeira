# r37: Darwin UDP control data and local Steam connection reports

The supplied r36 phone log establishes that Dock reached real online sign-in
before starting the manually added program. Its Steam networking thread then
reported 200 unhandled IPv4 control headers of type 27. That is Darwin's
`IP_RECVTOS`, not an authentication error. No game lobby result appears in this
log, so it cannot prove that this defect is the only cause of failed matchmaking.

Wine already enables `IP_RECVTOS`, but its receive conversion recognized only
the Linux-style `IP_TOS` ancillary type. r37 recognizes both and returns the
Windows `IP_TOS` integer, preserving every DSCP and ECN bit. Sources:
[Apple's IP socket manual](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/man/man4/ip.4),
[Microsoft's IPv4 socket contract](https://learn.microsoft.com/en-us/windows/win32/winsock/ipproto-ip-socket-options).

The same receive path's 32-bit conversion incorrectly treated a complete 64-bit
message length as its payload size. It rejected a sufficient compact buffer and
could copy past the actual data. r37 separates header and payload lengths,
checks the source message and aligned destination capacity, and copies only the
payload. The per-message output changes from FIXME to TRACE.

The production conversion functions are tested with 512 actual localhost UDP
datagrams (IPv4 TOS and IPv6 traffic class values 0–255), under ASan/UBSan, in
native and compact 32-bit formats. A baseline fixture reproduces the dropped
type-27 message and the false 32-bit buffer rejection. Additional cases cover
exact capacity, insufficient space, multiple messages and malformed source
headers. These are real host socket tests, not a Steam service or phone test.

Only `socket.o` in the existing iOS `libntdll_unix.a` is rebuilt. Other archive
members and engine archives are compared byte for byte with the verified r36
inputs. All Windows Wine engine DLLs, qwave, graphics libraries and the r36
failed-import fix remain unchanged. Dock is rebuilt only for bounded numeric
logged-on/connection reports during a local program's lifetime. No game identity,
entitlement, DRM or Steamworks response is replaced.

The IPA uses optimized unsigned Release build 22. Package validation compares
every resource against the verified r36 IPA, checks PE import closure, native
architecture, stripped binaries and matching debug symbol UUIDs. Public packages
exclude user-supplied Microsoft runtime files; the local personal IPA preserves
them. Creating and joining a real online room on iPhone remains to be verified.
