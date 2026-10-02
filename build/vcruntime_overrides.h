#ifndef MADEIRA_VCRUNTIME_OVERRIDES_H
#define MADEIRA_VCRUNTIME_OVERRIDES_H

#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <ctype.h>

#define MADEIRA_VCRUNTIME_OVERRIDE "msvcp140,msvcp140_1,msvcp140_2,vcruntime140,vcruntime140_1=n,b"

/* Wine's native,builtin order, for one launch. Keep unrelated overrides,
 * including names that share a clause with one of the five runtime DLLs.
 * The caller owns the returned string. No registry or prefix is modified. */
static int madeira_is_vcruntime_name(const char *name, size_t length)
{
    while (length && isspace((unsigned char)*name)) { name++; length--; }
    while (length && isspace((unsigned char)name[length - 1])) length--;
    if (length && *name == '*') { name++; length--; }
    if (length >= 4 && !strncasecmp(name + length - 4, ".dll", 4)) length -= 4;
    static const char *names[] = { "msvcp140", "msvcp140_1", "msvcp140_2", "vcruntime140", "vcruntime140_1" };
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); i++)
        if (length == strlen(names[i]) && !strncasecmp(name, names[i], length)) return 1;
    return 0;
}

static char *madeira_vcruntime_overrides(const char *base)
{
    if (!base) base = "";
    char *result = calloc(strlen(base) + sizeof(MADEIRA_VCRUNTIME_OVERRIDE) + 2, 1);
    if (!result) return NULL;
    size_t used = 0;
    for (const char *clause = base; *clause;) {
        const char *end = strchr(clause, ';');
        if (!end) end = clause + strlen(clause);
        const char *eq = memchr(clause, '=', (size_t)(end - clause));
        size_t start = used;
        if (eq) {
            for (const char *name = clause; name < eq;) {
                const char *comma = memchr(name, ',', (size_t)(eq - name));
                const char *next = comma ? comma : eq;
                if (!madeira_is_vcruntime_name(name, (size_t)(next - name))) {
                    if (used > start) result[used++] = ',';
                    memcpy(result + used, name, (size_t)(next - name)); used += next - name;
                }
                name = comma ? comma + 1 : eq;
            }
            if (used > start) { memcpy(result + used, eq, (size_t)(end - eq)); used += end - eq; }
        } else {
            memcpy(result + used, clause, (size_t)(end - clause)); used += end - clause;
        }
        if (used > start) result[used++] = ';';
        clause = *end ? end + 1 : end;
    }
    memcpy(result + used, MADEIRA_VCRUNTIME_OVERRIDE, sizeof(MADEIRA_VCRUNTIME_OVERRIDE));
    return result;
}

/* Undo only our previous value. A later user/config value wins over the saved
 * baseline, and turning this option off leaves the original environment intact. */
static void madeira_apply_vcruntime_overrides(int enabled)
{
    static char *baseline = NULL, *applied = NULL;
    const char *current = getenv("WINEDLLOVERRIDES");
    if (applied && current && !strcmp(current, applied)) {
        if (baseline) setenv("WINEDLLOVERRIDES", baseline, 1);
        else unsetenv("WINEDLLOVERRIDES");
    }
    free(baseline); free(applied); baseline = NULL; applied = NULL;
    if (!enabled) return;
    current = getenv("WINEDLLOVERRIDES");
    if (current) {
        baseline = strdup(current);
        if (!baseline) return;
    }
    applied = madeira_vcruntime_overrides(current);
    if (applied) setenv("WINEDLLOVERRIDES", applied, 1);
}

#endif
