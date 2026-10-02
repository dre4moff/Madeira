"""Production texture diagnostic policy; FEX is restored and no longer locally gated."""
from pathlib import Path
import subprocess,tempfile,os
root=Path(__file__).resolve().parents[1]
texture=(root/'dxmt/src/util/util_madeira_switch.hpp').read_text()
texgate=texture[texture.index('inline bool madeiraTextureDiagnosticsEnabled() {'):texture.index('\n\n} // namespace dxmt')]
src=r'''
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <string>
#include <cassert>
#include <cstdio>
namespace env {std::string getEnvVar(const char *name) {const char *v=getenv(name);return v?v:"";} }
'''+texgate+r'''
int main(int argc,char **argv) {
 assert(argc==2);bool enabled=!strcmp(argv[1],"1");
 assert(madeiraTextureDiagnosticsEnabled()==enabled);
 puts(enabled ? "PASS: explicit texture diagnostics enabled" : "PASS: quiet texture diagnostics disabled");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-hot-diag-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(src)
 subprocess.run(['clang++','-std=c++20','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 for quiet,choice,enabled in [('1',None,False),('1','1',True),('0','0',False),(None,None,True),('1','0',False),('1','invalid',False)]:
  e=os.environ.copy();e.pop('MADEIRA_QUIET',None);e.pop('MADEIRA_RUNTIME_PROFILING',None)
  if quiet is not None:e['MADEIRA_QUIET']=quiet
  if choice is not None:e['MADEIRA_RUNTIME_PROFILING']=choice
  subprocess.run([str(p/'test'),'1' if enabled else '0'],env=e,check=True)
print('PASS: texture cached opt-in policy retained; FEX restoration has a separate test')
