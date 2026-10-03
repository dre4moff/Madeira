"""Drive the production compositor placement and pointer maps with host CALayers.

No iOS device, game, or Steam session is started. This verifies geometry and
layer ownership; actual rendered iOS output still requires device acceptance.
"""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
s = (root/'app/Madeira/Winios/Winios.m').read_text()
def part(start,end):
 a=s.index(start);return s[a:s.index(end,a)]
functions = part('static int winios_desktop_fit_enabled(void)', '/* Called by IOSDisplayShim')
pointer = part('int winios_desktop_point_from_window(', '/* main thread only */')
stub = r'''
#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#import <Metal/Metal.h>
#include <assert.h>
#include <math.h>
#define UIColor NSColor
#define WINIOS_PX_TO_PT_Y (g_px_to_pt_y>0?g_px_to_pt_y:g_px_to_pt)
static NSMutableDictionary<NSNumber *,CALayer *> *g_layers;
static NSMutableDictionary<NSNumber *,NSValue *> *g_px_rects,*g_client_rects;
static NSMutableDictionary<NSNumber *,CAMetalLayer *> *g_metal_layers;
static NSNumber *g_fit_key,*g_game_key;
static CALayer *g_game_backdrop;
static NSView *g_compositor_view;
static CGRect g_fit_client_px,g_fit_view_pt,g_desk_rect;
static BOOL g_desk_rect_set;
static CGFloat g_px_to_pt,g_px_to_pt_y;
static CGPoint g_desk_origin;
static void winios_screen_size(int *w,int *h){*w=1568;*h=720;}
static void winios_place_metal_layer(NSNumber *key);
'''
main = r'''
static int close_to(CGFloat a,CGFloat b){return fabs(a-b)<0.001;}
int main(void){@autoreleasepool{
 g_compositor_view=[[NSView alloc]initWithFrame:NSMakeRect(0,0,956,440)];
 g_compositor_view.wantsLayer=YES;
 g_layers=[NSMutableDictionary new];g_px_rects=[NSMutableDictionary new];
 g_client_rects=[NSMutableDictionary new];g_metal_layers=[NSMutableDictionary new];
 g_px_to_pt=956.0/1568;
 NSNumber *key=@123;CALayer *win=[CALayer layer];CAMetalLayer *ml=[CAMetalLayer layer];
 [g_compositor_view.layer addSublayer:win];[win addSublayer:ml];
 g_layers[key]=win;g_metal_layers[key]=ml;
 g_px_rects[key]=[NSValue valueWithRect:NSMakeRect(196,30,808,638)];
 g_client_rects[key]=[NSValue valueWithRect:NSMakeRect(200,60,800,600)];
 // This smaller window fits the desktop: old desktop-fit left its caption visible.
 winios_place_metal_layer(key);assert(ml.superlayer==win&&ml.frame.size.height<440);
 winios_set_game_window(123);
 assert(ml.superlayer==g_compositor_view.layer&&g_game_backdrop&&!g_game_backdrop.hidden);
 assert(close_to(ml.frame.size.height,440)&&close_to(ml.frame.size.width,440*4.0/3));
 assert(close_to(CGRectGetMidX(ml.frame),478)&&close_to(CGRectGetMidY(ml.frame),220));
 assert(ml.zPosition>g_game_backdrop.zPosition&&ml.zPosition<10000);
 int x,y;assert(winios_desktop_point_from_window(478,220,&x,&y)&&x==600&&y==360);
 CGPoint point;CGFloat scale;
 assert(winios_desktop_fit_map(x,y,&point,&scale)&&close_to(point.x,478)&&close_to(point.y,220));
 assert(winios_desktop_point_from_window(0,220,&x,&y)&&x==200&&y==360);
 assert(winios_desktop_point_from_window(955,220,&x,&y)&&x==999&&y==360);
 // A different app's fitting window may not take the game's pointer map.
 assert(!winios_desktop_fit(@456,[CAMetalLayer layer],CGRectMake(0,0,1920,1080)));
 assert([g_fit_key isEqual:key]);
 // Rotate / change presentation mode; geometry and inverse touch map agree.
 g_desk_rect_set=YES;g_desk_rect=CGRectMake(10,20,900,400);g_px_to_pt_y=0.7;
 winios_place_metal_layer(key);assert(CGRectEqualToRect(ml.frame,g_desk_rect));
 assert(winios_desktop_point_from_window(460,220,&x,&y)&&x==600&&y==360);
 assert(winios_desktop_fit_map(600,360,&point,NULL)&&close_to(point.x,460)&&close_to(point.y,220));
 assert(winios_desktop_point_from_window(910-0.01,420-0.01,&x,&y)&&x==999&&y==659);
 win.hidden=YES;winios_place_metal_layer(key);assert(ml.hidden);win.hidden=NO;
 winios_set_game_window(0);
 assert(ml.superlayer==win&&ml.zPosition==0&&!ml.hidden&&g_game_backdrop.hidden&&!g_game_key);
 winios_set_game_window(0); // idempotent session reset
 puts("PASS: smaller Dock window fills view, caption excluded, root layer/backdrop, touch/cursor center and edges, stretch, visibility, unrelated windows, restore/idempotence");
}}
'''
# NSValue stores CGRect through the equivalent NSRect on macOS.
functions=functions.replace('.CGRectValue','.rectValue')
with tempfile.TemporaryDirectory(prefix='madeira-dock-fullscreen-') as d:
 p=Path(d)/'test.m';p.write_text(stub+functions+pointer.replace('.CGRectValue','.rectValue')+main)
 exe=Path(d)/'test'
 subprocess.run(['clang','-fobjc-arc','-O1','-g','-fsanitize=address,undefined','-framework','Cocoa','-framework','QuartzCore','-framework','Metal',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
