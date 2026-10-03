"""Actual native packet/ring/endpoint code, synthetic samples only (ASan/UBSan)."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'build/ntdll-unix/audio_null_ios.c').read_text()
def part(a,b): return s[s.index(a):s.index(b,s.index(a))]
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <stdatomic.h>
#include "audio_route.h"
#define LOG_FN_CALL(...) ((void)0)
#define IOS_AUDIO_CHANNELS 2
#define IOS_AUDIO_SAMPLE_RATE 48000
#define IOS_AUDIO_BITS 32
#define IOS_AUDIO_FRAME_BYTES 8
static struct madeira_audio_routes routes;
void madeira_audio_get_routes(struct madeira_audio_routes *out) { *out=routes; }
static uint64_t mach_absolute_time(void) {return 1000000000;}
static uint64_t mach_to_ns(uint64_t n) {return n;}
'''+part('typedef int NTSTATUS;','struct main_loop_params')+part('struct get_endpoint_ids_params {','struct set_volumes_params {')+part('struct ios_stream {','/* ml739: one stream')+r'''
static struct ios_stream live;
static struct ios_stream *stream_from_handle(stream_handle h) {return h==1?&live:NULL;}
'''+part('static int ios_fmt_is_float(','/* Create the ONE')+part('static void ios_capture_samples(','/* Core Audio real-time')+part('static NTSTATUS ios_get_endpoint_ids(','static NTSTATUS ios_create_stream(')+part('static NTSTATUS ios_get_capture_buffer(','static NTSTATUS ios_get_loopback_capture_device(')+part('static NTSTATUS ios_get_mix_format(','static NTSTATUS ios_get_device_period(')+part('static NTSTATUS ios_get_next_packet_size(','static NTSTATUS ios_get_frequency(')+r'''
int main(void) {
 struct get_endpoint_ids_params e={.flow=eCapture}; ios_get_endpoint_ids(&e);assert(!e.num && e.result==S_OK);
 routes.microphone=1;routes.capture_count=2;routes.capture_default=1;
 strcpy(routes.capture[0].uid,"builtin");strcpy(routes.capture[1].uid,"headset");routes.capture[0].name[0]='M';routes.capture[1].name[0]='H';
 ios_get_endpoint_ids(&e);assert(e.num==2 && e.default_idx==1 && (uint32_t)e.result==0x8007007a);
 unsigned needed=e.size;BYTE *buf=calloc(1,needed+16);memset(buf+needed,0xab,16);e.endpoints=(void*)buf;e.size=needed-1;ios_get_endpoint_ids(&e);assert(e.size==needed && buf[0]==0);
 e.size=needed;ios_get_endpoint_ids(&e);assert(e.result==S_OK && !strcmp((char*)buf+e.endpoints[1].device,"headset"));assert(*(WCHAR*)(buf+e.endpoints[0].name)=='M');for(unsigned i=0;i<16;i++)assert(buf[needed+i]==0xab);free(buf);
 struct WAVEFORMATEX_stub f={.wFormatTag=1,.nChannels=1,.nSamplesPerSec=16000,.nAvgBytesPerSec=32000,.nBlockAlign=2,.wBitsPerSample=16};assert(ios_capture_format_supported(&f));f.nChannels=6;assert(!ios_capture_format_supported(&f));f.nChannels=1;
 BYTE fmt[40];struct get_mix_format_params m={.flow=eCapture,.fmt=fmt};ios_get_mix_format(&m);assert(ios_capture_format_supported((void*)fmt));assert(((struct WAVEFORMATEX_stub*)fmt)->nChannels==1);
 f.wFormatTag=3;assert(!ios_capture_format_supported(&f));
 live=(struct ios_stream){.flow=eCapture,.started=1,.sample_rate=16000,.channels=1,.frame_bytes=2,.sample_bits=16,.buffer_frames=8,.scratch_frames=8};live.ring=calloc(8,2);live.render_scratch=calloc(8,2);
 float input[24];for(int i=0;i<24;i++)input[i]=i<12?.5f:-.5f;
 ios_capture_samples(&live,input,24,48000);assert(atomic_load(&live.write_pos)==8);
 BYTE *data=NULL;UINT32 n=0;UINT flags=0;UINT64 pos=99,qpc=0;struct get_capture_buffer_params g={.stream=1,.frames=&n,.data=&data,.flags=&flags,.devpos=&pos,.qpcpos=&qpc};ios_get_capture_buffer(&g);assert(g.result==S_OK && n==8 && pos==0 && qpc>0);int16_t *pcm=(void*)data;assert(pcm[0]==16384 && pcm[7]==-16384);
 ios_capture_samples(&live,input,3,48000);assert(atomic_load(&live.write_pos)==8 && pcm[0]==16384 && atomic_load(&live.capture_discontinuity)==1);
 ios_get_capture_buffer(&g);assert((uint32_t)g.result==0x88890007);
 struct release_capture_buffer_params r={.stream=1,.done=3};ios_release_capture_buffer(&r);assert((uint32_t)r.result==0x88890009 && live.pending_frames==8);r.done=0;ios_release_capture_buffer(&r);assert(r.result==S_OK && !atomic_load(&live.play_pos));ios_get_capture_buffer(&g);assert(n==8 && flags==1);
 r.done=8;ios_release_capture_buffer(&r);assert(r.result==S_OK);ios_get_capture_buffer(&g);assert((uint32_t)g.result==0x08890001 && !data && !n);
 ios_capture_samples(&live,input,6,48000);struct get_next_packet_size_params next={.stream=1,.frames=&n};ios_get_next_packet_size(&next);assert(n==2);ios_get_capture_buffer(&g);assert(pos==8 && n==2 && ((int16_t*)data)[0]==16384);r.done=2;ios_release_capture_buffer(&r);
 free(live.ring);free(live.render_scratch);
 live=(struct ios_stream){.flow=eCapture,.started=1,.sample_rate=48000,.channels=2,.frame_bytes=8,.is_float=1,.sample_bits=32,.buffer_frames=8,.scratch_frames=8};live.ring=calloc(8,8);live.render_scratch=calloc(8,8);
 float specials[]={NAN,2,-2,.25};ios_capture_samples(&live,specials,4,48000);ios_get_capture_buffer(&g);float *v=(void*)data;assert(n==4 && v[0]==0 && v[2]==1 && v[4]==-1 && v[6]==.25 && v[7]==.25);
 free(live.ring);free(live.render_scratch);
 puts("PASS: real routes, sizing/bounds/default selection, formats, captured PCM/float, resampling, wrap, overflow/held packet, discontinuity, empty/order/size HRESULTs, finite clamping");
}
'''
with tempfile.TemporaryDirectory(prefix='madeira-audio-capture-') as folder:
 p=Path(folder);(p/'test.c').write_text(code)
 subprocess.run(['clang','-Wno-macro-redefined','-fsanitize=address,undefined','-I'+str(root/'build/ntdll-unix'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
