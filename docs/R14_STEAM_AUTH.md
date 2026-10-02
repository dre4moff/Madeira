# Local 0.1.1 r14 — Steam sign-in investigation

The supplied r13 log reaches genuine client loading, two successful TLS
handshakes, native token submission and logon-start result 1. It never reports
`session-authenticated-online` or a game launch. The app remains responsive.
The user reports the wait continues beyond two minutes, exceeding the session's
90-second loop bound. This is consistent with an unreturned guest call; the
existing log cannot name the call. The initial native playtime request reports
URL error -1009, but the later TLS handshakes mean it is insufficient evidence
of a continuing connection outage. No GPU/game bottleneck can be measured in
this run because the game does not start. DLSS is off in the supplied attempt;
the user also reproduced the wait with it on.

## Corrections

Wine's iOS poll classifier cached socket families by poll slot and descriptor
number. Both numbers can be recycled, without invalidation on object removal
or creation. A new IPv4/IPv6 socket could then take the synthetic pipe event
path, skipping real network readiness polling. r14 invalidates entries on both
poll-slot lifetime boundaries. Hot cache hits still avoid `getsockname`; there
is no per-tick socket census or full cache purge. This is a proven source defect,
but the supplied log does not prove it caused this particular device wait.

The old classifier separately reallocated two arrays: failure of the second
allocation after the first moved could leave a dangling pointer. The new cache
uses one allocation and publishes it only after successful growth. Allocation
failure classifies the actual descriptor directly, preserves existing entries
and retries growth later. Classification preserves caller errno. FD handoff
captures sendmsg errno before diagnostics so logging cannot change EPIPE handling.

The original genuine-client authentication, pinned ABI/hash checks, callback
pump, 90-second wait, subscription-list gate and launch decision are retained.
There is no fabricated login, offline ownership fallback or token retry/replay.

## Bounded diagnosis and recovery

Dock now writes numeric checkpoints once per ten seconds while waiting:

- `session-auth-wait-ms`: elapsed guest wait;
- `session-auth-step`: 1 callback pump, 2 public logged-on query, 3 private
  logged-on query, 4 connected query, 5 all queried calls returned;
- `session-auth-state`: bits 1 public online, 2 private online, 4 connected.
  A missing bit may reflect short-circuit evaluation; it is not an independent
  failed query result.

No callback payload, token, account name or identifier is included. The app's
bounded report parser whitelists only numeric versions of these fields.
`[srv-poll-live]` reports poll-loop liveness and aggregate event counts every ten
seconds, using the existing server clock. It remains available in quiet mode.
After 120 seconds from observing token submission, the native starting screen
surfaces a sign-in-not-responding message and existing Close session controls,
even if a guest query never returns. It does not kill a client behind the user's
back or grant authentication on timeout. The message clears if login succeeds.

## Verification and limits

- The exact baseline classifier misclassifies an IPv4 socket after a real host
  Unix descriptor is reused via dup2. Production add/remove hooks with the new
  classifier pass 200 alternating socket-family reuses and 10,000 hot cache
  hits without repeated syscalls, plus growth allocation failure and IPv6.
- The production Dock session with synthetic client interfaces/clock times out
  unauthenticated at 90 seconds, emits nine checkpoint groups, preserves query
  short-circuiting and launches only after online/subscription-list confirmation.
- FD handoff tests deliberately overwrite errno from the logger and verify the
  captured EPIPE behavior; existing wire format and quiet-mode policy stay intact.
- Production Swift parser and starting-screen recovery rules are host tested.
  The stale Dock host test pin is updated to the actual official 0.1.1 gitlink;
  macOS tests use Darwin and its SDK-provided zlib, retaining Linux fallbacks.
- Existing synthetic VC runtime, controllers, DX11/DLSS D3D11+D3D12, cache and
  runtime tests pass. Unsigned iOS build, PE imports and IPA resources inspected.

Only synthetic tests and cross compilation are performed. No app, Wine session,
game, simulator, GPU or live Steam authentication is run. Recovery on iPhone and
any FPS change remain unverified. Graphics modules and the shader converter are
unchanged from r13, so this release preserves warm shader-cache identity.
