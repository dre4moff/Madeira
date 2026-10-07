#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 125hz
# Madeira Converter Exception: see LICENSE-EXCEPTION.md
"""Run production local-launch lifecycle with synthetic Win32 calls and no Steam."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'madeira-dock/src/launch.c').read_text()


def function(name):
    start = source.index(name)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


stubs = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <wctype.h>
#include "probe.h"
typedef uint32_t DWORD;
typedef int32_t LONG;
typedef int BOOL;
typedef void *HKEY;
typedef int LSTATUS;
typedef unsigned char BYTE;
typedef void *HANDLE;
typedef struct { HANDLE hProcess, hThread; } PROCESS_INFORMATION;
typedef struct { DWORD cb; } STARTUPINFOW;
typedef struct { struct { DWORD LimitFlags; } BasicLimitInformation; } JOBOBJECT_EXTENDED_LIMIT_INFORMATION;
typedef struct { DWORD ActiveProcesses; } JOBOBJECT_BASIC_ACCOUNTING_INFORMATION;
#define JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE 8192
#define JobObjectExtendedLimitInformation 9
#define JobObjectBasicAccountingInformation 1
#define CREATE_SUSPENDED 4

#define WINAPI
#define TRUE 1
#define FALSE 0
#define HKEY_CURRENT_USER ((HKEY)1)
#define HKEY_LOCAL_MACHINE ((HKEY)2)
#define KEY_QUERY_VALUE 1
#define KEY_SET_VALUE 2
#define KEY_WOW64_32KEY 4
#define ERROR_SUCCESS 0
#define ERROR_FILE_NOT_FOUND 2
#define REG_DWORD 4
#define INVALID_FILE_ATTRIBUTES UINT32_MAX
#define FILE_ATTRIBUTE_DIRECTORY 16
#define CTRL_C_EVENT 0
#define CTRL_BREAK_EVENT 1
#define WAIT_OBJECT_0 0
#define WAIT_TIMEOUT 258
#define WAIT_FAILED UINT32_MAX
#define _snwprintf swprintf
static int widecmp(const wchar_t *a, const wchar_t *b, size_t count) {
    while (count--) { int d = (int)towlower(*a) - (int)towlower(*b); if (d || !*a) return d; ++a; ++b; } return 0;
}
#define _wcsicmp(a,b) widecmp(a,b,(size_t)-1)
#define _wcsnicmp widecmp
static int scenario, creates, closes, terminated, waits, pumps, freed, started;
static DWORD registry[3];
static int indexof(const wchar_t *name) { return !wcscmp(name,L"pid") ? 0 : !wcscmp(name,L"ActiveUser") ? 1 : 2; }
static LSTATUS RegQueryValueExW(HKEY k, const wchar_t *n, void *r, DWORD *type, BYTE *v, DWORD *size) {
    (void)k; (void)r; *type = REG_DWORD; *size = 4; memcpy(v, &registry[indexof(n)], 4); return 0;
}
static LSTATUS RegSetValueExW(HKEY k, const wchar_t *n, DWORD r, DWORD t, const BYTE *v, DWORD size) {
    (void)k; (void)r; (void)t; assert(size == 4); DWORD value; memcpy(&value,v,4);
    int i = indexof(n); if (scenario == 5 && i == 1 && value == 123) return 55; registry[i] = value; return 0;
}
static LSTATUS RegDeleteValueW(HKEY k, const wchar_t *n) { (void)k; registry[indexof(n)] = 0; return 0; }
static LSTATUS RegOpenKeyExW(HKEY k, const wchar_t *n, DWORD r, DWORD flags, HKEY *out) {
    (void)n; (void)r; (void)flags; *out = k; return 0;
}
static void RegCloseKey(HKEY k) { assert(k); }
static DWORD GetCurrentProcessId(void) { return 99; }
static DWORD GetLastError(void) { return 5; }
static LONG InterlockedExchange(volatile LONG *p, LONG v) { LONG old = *p; *p = v; return old; }
static LONG InterlockedCompareExchange(volatile LONG *p, LONG v, LONG old) { LONG value = *p; if (value == old) *p = v; return value; }
static BOOL SetConsoleCtrlHandler(BOOL (*handler)(DWORD), BOOL add) { (void)handler; (void)add; return TRUE; }
static DWORD GetEnvironmentVariableW(const wchar_t *key, wchar_t *out, DWORD count) {
    const wchar_t *value = !wcscmp(key,L"MADEIRA_DOCK_LOCAL_PROGRAM") ? L"C:\\Games\\Local Fixture.exe" :
        !wcscmp(key,L"MADEIRA_DOCK_LOCAL_DIRECTORY") ? L"C:\\Games" : L"\"two words\" --network=&>é";
    if (scenario == 7 && !wcscmp(key,L"MADEIRA_DOCK_LOCAL_PROGRAM")) return count;
    assert(wcslen(value) < count); wcscpy(out,value); return (DWORD)wcslen(value);
}
static DWORD GetFileAttributesW(const wchar_t *name) {
    if (!wcscmp(name,L"C:\\Games")) return scenario == 4 ? 0 : FILE_ATTRIBUTE_DIRECTORY;
    return 0;
}
static HANDLE CreateJobObjectW(void *attributes, const wchar_t *name) { assert(!attributes && !name); return (HANDLE)7; }
static BOOL SetInformationJobObject(HANDLE job, int kind, void *data, DWORD size) {
    assert(job == (HANDLE)7 && kind == JobObjectExtendedLimitInformation && size == sizeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
    assert(((JOBOBJECT_EXTENDED_LIMIT_INFORMATION *)data)->BasicLimitInformation.LimitFlags == JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE); return TRUE;
}
static BOOL AssignProcessToJobObject(HANDLE job, HANDLE process) { assert(job == (HANDLE)7 && process == (HANDLE)5); return scenario != 9; }
static DWORD ResumeThread(HANDLE thread) { assert(thread == (HANDLE)6); return 1; }
static BOOL QueryInformationJobObject(HANDLE job, int kind, void *data, DWORD size, void *returned) {
    assert(job == (HANDLE)7 && kind == JobObjectBasicAccountingInformation && size == sizeof(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION) && !returned);
    ((JOBOBJECT_BASIC_ACCOUNTING_INFORMATION *)data)->ActiveProcesses = waits < (scenario == 8 ? 5 : 3);
    if (scenario == 6 && waits == 3) registry[0] = 888;
    return scenario != 10;
}
static BOOL CreateProcessW(const wchar_t *app, wchar_t *command, void *a, void *b, BOOL inherit, DWORD flags,
                          void *env, const wchar_t *cwd, STARTUPINFOW *si, PROCESS_INFORMATION *pi) {
    (void)a; (void)b; assert(!inherit && flags == CREATE_SUSPENDED && !env && si->cb == sizeof(*si));
    assert(!wcscmp(app,L"C:\\Games\\Local Fixture.exe") && !wcscmp(cwd,L"C:\\Games"));
    assert(!wcscmp(command,L"\"C:\\Games\\Local Fixture.exe\" \"two words\" --network=&>é"));
    ++creates; if (scenario == 1) return FALSE;
    pi->hProcess = (HANDLE)5; pi->hThread = (HANDLE)6; return TRUE;
}
static void CloseHandle(HANDLE h) { assert(h); ++closes; }
static BOOL TerminateProcess(HANDLE h, DWORD code) { assert(h == (HANDLE)5 && code == 1); ++terminated; return TRUE; }
static BOOL GetExitCodeProcess(HANDLE h, DWORD *code) { assert(h == (HANDLE)5); *code = 0; return TRUE; }
static DWORD WaitForSingleObject(HANDLE h, DWORD delay);
static bool get_callback(int32_t pipe, struct sh_callback *cb) {
    assert(pipe == 1 && creates == 1 && started && registry[0] == 99); ++pumps;
    if (!(pumps % 2)) return false;
    *cb = (struct sh_callback){.id = scenario == 2 ? -1 : 100, .size = 0}; return true;
}
static void free_callback(int32_t pipe) { assert(pipe == 1); ++freed; }
static void event(const char *name, int32_t value) { if (!strcmp(name,"launch-local-started")) { assert(value == 1); ++started; } }
'''
production = ('struct saved_value { HKEY key; const wchar_t *name; DWORD previous, written; bool existed, changed; };\n'
              + function('static bool publish(') + '\n' + function('static bool restore(')
              + '\nstatic volatile LONG interrupted;\n' + function('static BOOL WINAPI on_control(')
              + '\n' + function('int sh_launch_local('))
checks = r'''
static DWORD WaitForSingleObject(HANDLE h, DWORD delay) {
    assert(h == (HANDLE)5);
    if (!delay) return waits >= 3 ? WAIT_OBJECT_0 : WAIT_TIMEOUT;
    assert(delay == 50); ++waits;
    if (scenario == 3) interrupted = 1;

    return waits >= 3 ? WAIT_OBJECT_0 : WAIT_TIMEOUT;
}
static void sleep_ms(uint32_t delay) { (void)WaitForSingleObject((HANDLE)5, delay); }
int main(void) {
    struct sh_api api = {.get_callback=get_callback,.free_callback=free_callback};
    struct sh_observer observer = {.event=event,.sleep_ms=sleep_ms};
    int expected[] = {0,54,SH_CALLBACK_INVALID,44,53,42,47,53,0,54,54};
    for (scenario = 0; scenario < 11; ++scenario) {
        registry[0] = 9; registry[1] = 8; registry[2] = 7;
        creates = closes = terminated = waits = pumps = freed = started = 0; interrupted = 0;
        int result = sh_launch_local(&api,&observer,1,1,123);
        assert(result == expected[scenario]);
        if (scenario != 6) assert(registry[0] == 9 && registry[1] == 8 && registry[2] == 7);
        else assert(registry[0] == 888);
        if (!scenario) assert(creates == 1 && started == 1 && pumps == 8 && freed == 4 && closes == 3 && !terminated);
        if (scenario == 2 || scenario == 3) assert(terminated == 1 && closes == 3);
        if (scenario == 4 || scenario == 5 || scenario == 7) assert(!creates);
        if (scenario == 8) assert(waits == 5 && closes == 3 && !terminated && pumps == 12);
        if (scenario == 9) assert(creates == 1 && !started && terminated == 1 && closes == 3);
        if (scenario == 10) assert(started == 1 && terminated == 1 && closes == 3);
    }
    puts("PASS: local process lifetime, callback pumping, Unicode/quoted arguments, creation failure, invalid callbacks, interruption, invalid paths, partial registry rollback and competing Steam registration, launcher descendants and job failure cleanup");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-local-dock-') as folder:
    folder = Path(folder)
    test = folder / 'local.c'
    test.write_text(stubs + production + checks)
    binary = folder / 'local'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                    '-fsanitize=address,undefined', '-I'+str(root/'madeira-dock/src'),
                    str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

session = (root/'madeira-dock/src/session.c').read_text()
local = session.index('if (local) {', session.index('if (was_online &&'))
assert local < session.index('bool entitled =', local)
assert '!native_auth' in session and 'app != 0' in session
assert '!local && offline_abi' in session
assert 'LaunchApp' not in function('int sh_launch_local(')
assert 'SetEnvironmentVariable' not in function('int sh_launch_local(')
print('PASS: authenticated online local mode is separate from installed-app ownership and never supplies Steam game identity')
