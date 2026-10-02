#include <assert.h>
#include <stdio.h>
#include "../build/vcruntime_overrides.h"

static void merge(const char *base, const char *expected)
{
    char *actual = madeira_vcruntime_overrides(base);
    assert(actual && !strcmp(actual, expected));
    free(actual);
}

int main(void)
{
    merge(NULL, MADEIRA_VCRUNTIME_OVERRIDE);
    merge("", MADEIRA_VCRUNTIME_OVERRIDE);
    merge("dxgi=n;d3d11=b", "dxgi=n;d3d11=b;" MADEIRA_VCRUNTIME_OVERRIDE);
    merge("msvcp140=b;vcruntime140_1=;dinput8=n", "dinput8=n;" MADEIRA_VCRUNTIME_OVERRIDE);
    merge("msvcp140,dxgi,vcruntime140=b,n", "dxgi=b,n;" MADEIRA_VCRUNTIME_OVERRIDE);
    merge(" *MSVCP140.DLL , d3d11 =b; VCRUNTIME140_1.dll =n", " d3d11 =b;" MADEIRA_VCRUNTIME_OVERRIDE);
    merge("msvcp140_extra=b;;concrt140=n;msvcp140_2=b;", "msvcp140_extra=b;concrt140=n;" MADEIRA_VCRUNTIME_OVERRIDE);
    merge("msvcp140_1=n;msvcp140_1=b;vcruntime140=n", MADEIRA_VCRUNTIME_OVERRIDE);
    merge(MADEIRA_VCRUNTIME_OVERRIDE, MADEIRA_VCRUNTIME_OVERRIDE);

    unsetenv("WINEDLLOVERRIDES");
    madeira_apply_vcruntime_overrides(0);
    assert(!getenv("WINEDLLOVERRIDES"));
    madeira_apply_vcruntime_overrides(1);
    assert(!strcmp(getenv("WINEDLLOVERRIDES"), MADEIRA_VCRUNTIME_OVERRIDE));
    madeira_apply_vcruntime_overrides(1); // Repeat is idempotent.
    madeira_apply_vcruntime_overrides(0); // Next game restores absence.
    assert(!getenv("WINEDLLOVERRIDES"));

    setenv("WINEDLLOVERRIDES", "dxgi=n;msvcp140=b", 1);
    madeira_apply_vcruntime_overrides(1);
    assert(!strcmp(getenv("WINEDLLOVERRIDES"), "dxgi=n;" MADEIRA_VCRUNTIME_OVERRIDE));
    madeira_apply_vcruntime_overrides(0);
    assert(!strcmp(getenv("WINEDLLOVERRIDES"), "dxgi=n;msvcp140=b"));

    madeira_apply_vcruntime_overrides(1);
    setenv("WINEDLLOVERRIDES", "d3d11=n", 1); // Fresh global configuration wins.
    madeira_apply_vcruntime_overrides(1);
    assert(!strcmp(getenv("WINEDLLOVERRIDES"), "d3d11=n;" MADEIRA_VCRUNTIME_OVERRIDE));
    madeira_apply_vcruntime_overrides(0);
    assert(!strcmp(getenv("WINEDLLOVERRIDES"), "d3d11=n"));

    setenv("WINEDLLOVERRIDES", "", 1);
    madeira_apply_vcruntime_overrides(1);
    madeira_apply_vcruntime_overrides(0);
    assert(getenv("WINEDLLOVERRIDES") && !*getenv("WINEDLLOVERRIDES"));
    puts("PASS: VC runtime override merging, precedence, toggling, isolation and restoration");
}
