"""Exercise the real farms/overlay for Steam's ARM64 host and direct x64 starts."""
from pathlib import Path
import subprocess
import tempfile
import re
import sys
root = Path(__file__).resolve().parents[1]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else root / "app/Madeira/WineProcessBridge.m").read_text()
start = source.index("            [fm createDirectoryAtPath:sys32Dir")
end = source.index("            /* WoW64:", start)
farms = source[start:end]
start = re.search(r"            if \([^\n]*nativeVCRuntime\) \{", source[end:]).start() + end
end = source.index("\n        }\n\n        // Build the launch path", start)
overlay = source[start:end]
harness = r'''
#import <Foundation/Foundation.h>
#include <assert.h>
#include <stdio.h>
#define LOG(...) ((void)0)
static void stage(NSString *bundlePath, NSString *prefix, BOOL use_arm64ec, int nativeVCRuntime) {
    NSFileManager *fm = NSFileManager.defaultManager;
    NSString *sys32Dir = [prefix stringByAppendingPathComponent:@"drive_c/windows/system32"];
    NSString *sysx64Dir = [prefix stringByAppendingPathComponent:@"drive_c/windows/sysx64"];
    const char *bundle_subdir = use_arm64ec ? "arm64ec-windows" : "aarch64-windows";
    NSString *dllSource = [bundlePath stringByAppendingPathComponent:[NSString stringWithUTF8String:bundle_subdir]];
''' + farms + overlay + r'''
}
static void expectLink(NSString *path, NSString *target) {
    NSString *actual = [NSFileManager.defaultManager destinationOfSymbolicLinkAtPath:path error:nil];
    if (![actual isEqualToString:target]) {
        fprintf(stderr, "Wrong DLL target: %s -> %s (expected %s)\n", path.UTF8String,
                actual.UTF8String, target.UTF8String);
        abort();
    }
    assert([NSFileManager.defaultManager fileExistsAtPath:path]);
}
int main(void) {
    @autoreleasepool {
        NSFileManager *fm = NSFileManager.defaultManager;
        NSString *root = [NSTemporaryDirectory() stringByAppendingPathComponent:NSUUID.UUID.UUIDString];
        NSString *bundle = [root stringByAppendingPathComponent:@"Madeira.app"];
        NSString *prefix = [root stringByAppendingPathComponent:@"wine"];
        NSString *sys32 = [prefix stringByAppendingPathComponent:@"drive_c/windows/system32"];
        NSString *sysx64 = [prefix stringByAppendingPathComponent:@"drive_c/windows/sysx64"];
        NSString *sysaa64 = [prefix stringByAppendingPathComponent:@"drive_c/windows/sysaa64"];
        NSString *syswow64 = [prefix stringByAppendingPathComponent:@"drive_c/windows/syswow64"];
        NSString *builtins = [bundle stringByAppendingPathComponent:@"arm64ec-windows"];
        NSString *arm64 = [bundle stringByAppendingPathComponent:@"aarch64-windows"];
        NSString *native = [bundle stringByAppendingPathComponent:@"x86_64-vcruntime"];
        NSArray *names = @[@"msvcp140.dll", @"msvcp140_1.dll", @"msvcp140_2.dll",
                           @"vcruntime140.dll", @"vcruntime140_1.dll"];
        for (NSString *dir in @[sys32, sysx64, syswow64, builtins, arm64, native])
            assert([fm createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil]);
        for (NSString *dir in @[builtins, arm64, native]) {
            for (NSString *name in names)
                assert([dir writeToFile:[dir stringByAppendingPathComponent:name]
                            atomically:YES encoding:NSUTF8StringEncoding error:nil]);
        }
        NSArray *nvext = @[@"nvapi64.dll", @"nvngx.dll"];
        for (NSString *name in nvext)
            assert([@"native extension" writeToFile:[builtins stringByAppendingPathComponent:name]
                        atomically:YES encoding:NSUTF8StringEncoding error:nil]);
        NSString *extraName = @"vcruntime140_threads.dll";
        assert([@"native extra" writeToFile:[native stringByAppendingPathComponent:extraName]
                              atomically:YES encoding:NSUTF8StringEncoding error:nil]);
        assert([@"license" writeToFile:[native stringByAppendingPathComponent:@"LICENSE.rtf"]
                         atomically:YES encoding:NSUTF8StringEncoding error:nil]);
        NSString *userTarget = [root stringByAppendingPathComponent:@"custom.dll"];
        assert([@"user data" writeToFile:userTarget atomically:YES encoding:NSUTF8StringEncoding error:nil]);
        for (NSString *dir in @[sys32, sysx64]) {
            assert([fm createSymbolicLinkAtPath:[dir stringByAppendingPathComponent:@"user.dll"]
                          withDestinationPath:userTarget error:nil]);
            assert([fm createSymbolicLinkAtPath:[dir stringByAppendingPathComponent:@"stale-runtime.dll"]
                          withDestinationPath:@"/old/Madeira.app/x86_64-vcruntime/stale-runtime.dll" error:nil]);
        }
        NSString *x86 = [syswow64 stringByAppendingPathComponent:@"msvcp140.dll"];
        assert([@"x86 runtime" writeToFile:x86 atomically:YES encoding:NSUTF8StringEncoding error:nil]);

        // Steam's explorer.exe ARM64 host is tested first.
        for (NSNumber *ec in @[@NO, @YES]) {
            for (NSNumber *enabled in @[@YES, @YES, @NO, @NO]) {
                stage(bundle, prefix, ec.boolValue, enabled.boolValue);
                for (NSString *name in names) {
                    NSString *hostSource = ec.boolValue ? builtins : arm64;
                    NSString *sys32Source = ec.boolValue && enabled.boolValue ? native : hostSource;
                    expectLink([sys32 stringByAppendingPathComponent:name], [sys32Source stringByAppendingPathComponent:name]);
                    expectLink([sysx64 stringByAppendingPathComponent:name], [(enabled.boolValue ? native : builtins) stringByAppendingPathComponent:name]);
                    expectLink([sysaa64 stringByAppendingPathComponent:name], [arm64 stringByAppendingPathComponent:name]);
                }
                for (NSString *name in nvext)
                    for (NSString *dir in @[sys32, sysx64])
                        expectLink([dir stringByAppendingPathComponent:name], [builtins stringByAppendingPathComponent:name]);
                for (NSString *dir in @[sys32, sysx64]) {
                    NSString *extra = [dir stringByAppendingPathComponent:extraName];
                    BOOL expected = enabled.boolValue && ([dir isEqualToString:sysx64] || ec.boolValue);
                    if (expected) expectLink(extra, [native stringByAppendingPathComponent:extraName]);
                    else assert(![fm destinationOfSymbolicLinkAtPath:extra error:nil] && ![fm fileExistsAtPath:extra]);
                    expectLink([dir stringByAppendingPathComponent:@"user.dll"], userTarget);
                    assert(![fm destinationOfSymbolicLinkAtPath:[dir stringByAppendingPathComponent:@"stale-runtime.dll"] error:nil]);
                    assert(![fm fileExistsAtPath:[dir stringByAppendingPathComponent:@"LICENSE.rtf"]]);
                }
                assert([[NSString stringWithContentsOfFile:x86 encoding:NSUTF8StringEncoding error:nil] isEqualToString:@"x86 runtime"]);
            }
        }
        // Repair stale links after the installed bundle path changes.
        stage(bundle, prefix, YES, 1);
        NSString *newBundle = [root stringByAppendingPathComponent:@"Updated/Madeira.app"];
        assert([fm createDirectoryAtPath:newBundle.stringByDeletingLastPathComponent
            withIntermediateDirectories:YES attributes:nil error:nil]);
        assert([fm moveItemAtPath:bundle toPath:newBundle error:nil]);
        stage(newBundle, prefix, YES, 1);
        NSString *newNative = [newBundle stringByAppendingPathComponent:@"x86_64-vcruntime"];
        for (NSString *dir in @[sys32, sysx64])
            expectLink([dir stringByAppendingPathComponent:extraName], [newNative stringByAppendingPathComponent:extraName]);
        for (NSString *name in nvext)
            for (NSString *dir in @[sys32, sysx64])
                expectLink([dir stringByAppendingPathComponent:name], [[newBundle stringByAppendingPathComponent:@"arm64ec-windows"] stringByAppendingPathComponent:name]);
        stage(newBundle, prefix, NO, 0);
        for (NSString *dir in @[sys32, sysx64])
            assert(![fm destinationOfSymbolicLinkAtPath:[dir stringByAppendingPathComponent:extraName] error:nil]);
        assert([[NSString stringWithContentsOfFile:userTarget encoding:NSUTF8StringEncoding error:nil] isEqualToString:@"user data"]);
        assert([fm removeItemAtPath:root error:nil]);
        puts("PASS: Steam ARM64 host/x64 child and direct x64 staging, on/off, arch isolation, stale links and user data");
    }
}
'''
with tempfile.TemporaryDirectory(prefix="madeira-prefix-test-") as tmp:
    path = Path(tmp) / "main.m"
    path.write_text(harness)
    executable = Path(tmp) / "test"
    subprocess.run(["clang", "-Wno-incompatible-pointer-types", "-fsanitize=address,undefined",
                    "-framework", "Foundation", str(path), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
