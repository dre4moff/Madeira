"""Host-only tests of production profile, argv and Steam/Dock argument paths."""
from pathlib import Path
import json
import random
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
content_actions = (root / 'app/Madeira/ContentView.swift').read_text()
control_action = content_actions[content_actions.index('enum ControlAction:'):content_actions.index('/// One on-screen control.')]

library = (root / 'app/Madeira/Library.swift').read_text()
helper = library[library.index('enum LibraryLaunchArguments {'):library.index('struct LibraryEntry:')]
fields = library[library.index('struct LibraryEntry: Codable, Identifiable {'):library.index('    var displayMode:')]
computed = library[library.index('    var launchArguments: String {'):library.index('    /// Runs on the launch worker')]
computed = re.sub(r'    var effectiveFPSMode: Int32 .*\n', '', computed)
corpus = ['', '-noaudio', '-dx11 -noaudio', '-path "Maps A"', '""', 'a\tb',
          '-label "café 日本語"', '"a""b"', r'-path "C:\Maps Folder\\"',
          r'"a\"b"', '"unterminated', 'bad\narg', 'bad\rarg']
random.seed(23)
for _ in range(500):
    corpus.append(''.join(random.choice('ab \\"\t') for _ in range(random.randrange(80))))
swift = 'import Foundation\nstruct TouchControl: Codable {}\nenum LibraryError: Error {case message(String)}\n' + control_action + helper + fields + computed + r'''
}
var entry = LibraryEntry(title: "Test", relativePath: "Games/Test.exe", bits: 64)
entry.arguments = "-noaudio -path \"Maps A\" -dx12"
entry.forceDirectX11 = true
assert(entry.launchArguments == "-noaudio -path \"Maps A\" -dx11")
try entry.validate()
entry.steamAppID = 457140
assert(!entry.startsSteamGameDirectly && entry.launchArguments == "-noaudio -path \"Maps A\" -dx11")
entry.steamStart = "game"; entry.steamProgramArguments = "-windowed"
assert(entry.launchArguments == "-windowed -noaudio -path \"Maps A\" -dx11")
entry.forceDirectX11 = false
assert(entry.launchArguments == "-windowed -noaudio -path \"Maps A\" -dx12")
let restored = try JSONDecoder().decode(LibraryEntry.self, from: JSONEncoder().encode(entry))
assert(restored.arguments == entry.arguments && restored.launchArguments == entry.launchArguments)
var old = entry; old.arguments = ""; old.forceDirectX11 = nil
let legacy = try JSONDecoder().decode(LibraryEntry.self, from: JSONEncoder().encode(old))
assert(legacy.launchArguments == "-windowed")
entry.steamStart = nil; entry.steamProgramArguments = nil
func rejected(_ text: String) -> Bool {
    var game = entry; game.arguments = text
    do {try game.validate(); return false} catch {return true}
}
assert(rejected("\"bad") && rejected("line\nbreak") && rejected("nul\0arg"))
assert(!rejected(String(repeating: "a", count:4095)) && rejected(String(repeating:"a",count:4096)))
assert(!rejected(Array(repeating:"a",count:64).joined(separator:" ")))
assert(rejected(Array(repeating:"a",count:65).joined(separator:" ")))
assert(rejected(String(repeating:"é",count:2048)))
entry.desktop = true; assert(!entry.launchArguments.contains("noaudio"))
let corpus = try JSONDecoder().decode([String].self, from: Data(contentsOf: URL(fileURLWithPath:CommandLine.arguments[1])))
for command in corpus {
    let values = LibraryLaunchArguments.tokens(command)?.map(\.value)
    print(String(data:try JSONEncoder().encode(values),encoding:.utf8)!)
}
'''
env = (root/'build/ntdll-unix/env_ios.c').read_text()
encoder = env[env.index('static WCHAR *build_command_line('):env.index('\n\n/***********************************************************************',env.index('static WCHAR *build_command_line('))]
c = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "launch_arguments.h"
typedef wchar_t WCHAR; typedef WCHAR *LPWSTR; typedef int BOOL;
#define ERR(...) ((void)0)
#define NtTerminateProcess(p,c) abort()
#define GetCurrentProcess() NULL
''' + encoder + r'''
int main(int argc,char **args) {
    if(argc!=2)return 1;
    char buffer[4096];char *argv[64];
    int count=madeira_parse_launch_arguments(args[1],buffer,sizeof buffer,argv,64);
    if(count<0){puts("INVALID");return 0;}
    for(int i=0;i<count;i++){
        for(const unsigned char *p=(unsigned char*)argv[i];*p;p++)printf("%02x",*p);
        puts("");
    }
    /* Round trip through Wine's actual command-line encoder as well. The
     * quoting algorithm is code-unit independent; map UTF-8 bytes to units. */
    WCHAR *wide[65];
    for(int i=0;i<count;i++){
        size_t n=strlen(argv[i]);wide[i]=calloc(n+1,sizeof(WCHAR));assert(wide[i]);
        for(size_t j=0;j<n;j++)wide[i][j]=(unsigned char)argv[i][j];
    }
    wide[count]=NULL;
    WCHAR *encoded=build_command_line(wide);assert(encoded);
    char command[8192];size_t length=wcslen(encoded);assert(length<sizeof command);
    for(size_t j=0;j<=length;j++)command[j]=(char)encoded[j];
    char decoded[8192];char *again[64];
    assert(madeira_parse_launch_arguments(command,decoded,sizeof decoded,again,64)==count);
    for(int i=0;i<count;i++){assert(!strcmp(argv[i],again[i]));free(wide[i]);}
    free(encoded);
    /* Exercise output and token bounds under ASan/UBSan. */
    char small[2];char *one[1];
    assert(madeira_parse_launch_arguments("aaa",small,sizeof small,one,1)==-1);
    assert(madeira_parse_launch_arguments("a b",buffer,sizeof buffer,one,1)==-1);
    return 0;
}
'''
dock = (root/'madeira-dock/src/launch.c').read_text()
reader = dock[dock.index('static bool wide_flag('):dock.index('/* Returns 0 once')]
calls = re.findall(r'^\s*(?:uint64_t )?call = (\(\(launch_fn\).+);',dock,re.M)
assert len(calls)==2
dock_test = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <wchar.h>
#include <stdlib.h>
#include <stdio.h>
typedef unsigned long DWORD;
#define __thiscall
#define CP_UTF8 65001
#define WC_ERR_INVALID_CHARS 128
static const wchar_t *custom,*flag;
static bool conversion_fail;
static DWORD GetEnvironmentVariableW(const wchar_t *name,wchar_t *out,DWORD cap){
    const wchar_t *s=!wcscmp(name,L"MADEIRA_STEAM_HOST_LAUNCH_ARGUMENTS")?custom:flag;
    if(!s)return 0;size_t n=wcslen(s);if(n>=cap)return n+1;wcscpy(out,s);return n;
}
static int WideCharToMultiByte(unsigned cp,unsigned flags,const wchar_t *in,int n,
    char *out,int cap,void *a,void *b){
    assert(cp==CP_UTF8&&flags==WC_ERR_INVALID_CHARS&&n==-1&&!a&&!b);
    if(conversion_fail)return 0;
    size_t bytes=wcstombs(out,in,cap);return bytes==(size_t)-1||bytes>=(size_t)cap?0:(int)bytes+1;
}
''' + reader + r'''
typedef uint64_t (*launch_fn)(void*,const uint64_t*,uint32_t,int32_t,const char*);
static const char *expected;static unsigned submitted;
static uint64_t fake_launch(void *manager,const uint64_t *gameid,uint32_t source,int32_t option,const char *args){
    assert(manager&&*gameid==457140&&source==0&&option==0&&!strcmp(args,expected));submitted++;return 42;
}
static void exercise(const wchar_t *setting,const wchar_t *dx11,const char *wanted){
    custom=setting;flag=dx11;expected=wanted;submitted=0;
    char user_args[4096];assert(read_user_args(user_args,sizeof user_args));
    void *vtable[]={NULL,NULL,(void*)fake_launch};void **vptr=vtable;void *manager=&vptr;
    uint64_t gameid=457140;
''' + '    uint64_t call = '+calls[0]+';\n    call = '+calls[1]+r''';
    assert(call==42&&submitted==2);
}
int main(void){
    exercise(NULL,L"1","-dx11");exercise(NULL,NULL,"");
    exercise(L"-noaudio",NULL,"-noaudio");
    exercise(L"-dx11 -noaudio -path \"Maps A\"",L"1","-dx11 -noaudio -path \"Maps A\"");
    exercise(L"",L"0","");
    wchar_t large[4097];for(int i=0;i<4096;i++)large[i]=L'a';large[4096]=0;
    custom=large;char out[4096];assert(!read_user_args(out,sizeof out));
    custom=L"-noaudio";conversion_fail=true;assert(!read_user_args(out,sizeof out));
    puts("PASS: Dock actual initial/retry LaunchApp forwards user args; legacy fallback, empty/reset, oversize/conversion fail closed");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-launch-arguments-') as folder:
    p=Path(folder);(p/'main.swift').write_text(swift);(p/'corpus.json').write_text(json.dumps(corpus))
    results=subprocess.check_output(['swift',str(p/'main.swift'),str(p/'corpus.json')],text=True).splitlines()
    assert len(results)==len(corpus)
    (p/'test.c').write_text(c)
    subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'build'),str(p/'test.c'),'-o',str(p/'test')],check=True)
    for command,result in zip(corpus,results):
        got=subprocess.check_output([str(p/'test'),command],text=True)
        values=None if got=='INVALID\n' else [bytes.fromhex(t).decode('utf8') for t in got.splitlines()]
        assert values==json.loads(result),(command,values,result)
    (p/'dock.c').write_text(dock_test)
    subprocess.run(['clang','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'dock.c'),'-o',str(p/'dock')],check=True)
    subprocess.run([str(p/'dock')],check=True)
print('PASS: saved local/Steam profiles, DX11 priority, limits, quotes/Unicode, 513 Swift/native parser parity cases under ASan/UBSan')
