# Native overlay client. SAM-launched native app. Does the webOS native-app
# lifecycle (registerApp via libluna-service2) so LSM foregrounds + composites it,
# then maps a fullscreen surface (test fill). Pure ctypes; no compiler/SDK.
import ctypes, os, time, struct, sys
def log(*a): print(" ".join(str(x) for x in a)); sys.stdout.flush()
RG=ctypes.RTLD_GLOBAL
C=ctypes.CDLL("libwayland-client.so.0",mode=RG)
W=ctypes.CDLL("libwayland-webos-client.so.1",mode=RG)
LS=ctypes.CDLL("libluna-service2.so.3",mode=RG)
G=ctypes.CDLL("libglib-2.0.so.0",mode=RG)
V=ctypes.c_void_p;U=ctypes.c_uint;I=ctypes.c_int;S=ctypes.c_char_p;B=ctypes.c_bool
keep=[]
APPID=os.environ.get("APPID") or os.environ.get("APP_ID") or "com.webosbrew.overlay"
Wd,Ht=1920,1080
log("overlay start appId=%s pid=%d uid=%d" % (APPID, os.getpid(), os.getuid()))

# ---- webOS native-app lifecycle: registerApp over LS2 ----
LS.LSRegister.restype=B; LS.LSRegister.argtypes=[S,ctypes.POINTER(V),V]
LS.LSRegisterApplicationService.restype=B; LS.LSRegisterApplicationService.argtypes=[S,S,ctypes.POINTER(V),V]
LS.LSGmainAttach.restype=B; LS.LSGmainAttach.argtypes=[V,V,V]
LS.LSCall.restype=B; LS.LSCall.argtypes=[V,S,S,V,V,ctypes.POINTER(ctypes.c_ulong),V]
G.g_main_loop_new.restype=V; G.g_main_loop_new.argtypes=[V,I]
G.g_main_loop_get_context.restype=V; G.g_main_loop_get_context.argtypes=[V]
G.g_main_context_iteration.restype=I; G.g_main_context_iteration.argtypes=[V,I]
lserr=(ctypes.c_byte*256)()
h=V(0)
ok=False
try:
    ok=LS.LSRegisterApplicationService(APPID.encode(), APPID.encode(), ctypes.byref(h), ctypes.byref(lserr))
    log("LSRegisterApplicationService ->", bool(ok), "handle", bool(h.value))
except Exception as e:
    log("LSRegisterApplicationService missing:", e)
if not ok or not h.value:
    h=V(0)
    ok=LS.LSRegister(APPID.encode(), ctypes.byref(h), ctypes.byref(lserr))
    log("LSRegister ->", bool(ok), "handle", bool(h.value))
loop=G.g_main_loop_new(None, 0)
ctx=G.g_main_loop_get_context(loop)
if h.value:
    log("LSGmainAttach ->", bool(LS.LSGmainAttach(h, loop, ctypes.byref(lserr))))
    CB=ctypes.CFUNCTYPE(B,V,V,V)
    def on_reg(sh,msg,c):
        log("registerApp callback fired"); return True
    cb=CB(on_reg); keep.append(cb)
    tok=ctypes.c_ulong(0)
    r=LS.LSCall(h, b"luna://com.webos.applicationManager/registerApp", b'{"subscribe":true}', cb, None, ctypes.byref(tok), ctypes.byref(lserr))
    log("LSCall registerApp ->", bool(r))
    for _ in range(6): G.g_main_context_iteration(ctx, 0); time.sleep(0.05)

# ---- Wayland surface ----
C.wl_display_connect.restype=V; C.wl_display_connect.argtypes=[S]
C.wl_proxy_marshal_constructor.restype=V
C.wl_display_roundtrip.restype=I; C.wl_display_roundtrip.argtypes=[V]
C.wl_display_get_error.restype=I; C.wl_display_get_error.argtypes=[V]
C.wl_proxy_marshal.restype=None
C.wl_proxy_add_listener.restype=I; C.wl_proxy_add_listener.argtypes=[V,V,V]
class Opaque(ctypes.Structure): _fields_=[("x",ctypes.c_byte)]
def ip(lib,n): return ctypes.addressof(Opaque.in_dll(lib,n))
dpy=C.wl_display_connect(b"wayland-0"); log("display", bool(dpy))
reg=C.wl_proxy_marshal_constructor(V(dpy),U(1),V(ip(C,"wl_registry_interface")),V(0))
GLOBAL=ctypes.CFUNCTYPE(None,V,V,U,S,U); GREM=ctypes.CFUNCTYPE(None,V,V,U)
glob={}
cg=GLOBAL(lambda d,r,n,i,v:glob.__setitem__(i.decode("ascii","replace"),(n,v))); cr=GREM(lambda *a:None); keep+=[cg,cr]
class RL(ctypes.Structure): _fields_=[("g",GLOBAL),("r",GREM)]
rl=RL(cg,cr); keep.append(rl)
C.wl_proxy_add_listener(V(reg),ctypes.byref(rl),V(0)); C.wl_display_roundtrip(V(dpy))
def bind(name):
    lib=W if name.startswith("wl_webos") else C; nm,ver=glob[name]
    return C.wl_proxy_marshal_constructor(V(reg),U(0),V(ip(lib,name+"_interface")),U(nm),S(name.encode()),U(ver),V(0))
comp=bind("wl_compositor"); shm=bind("wl_shm"); shell=bind("wl_webos_shell")
surf=C.wl_proxy_marshal_constructor(V(comp),U(0),V(ip(C,"wl_surface_interface")),V(0))
shsurf=C.wl_proxy_marshal_constructor(V(shell),U(1),V(ip(W,"wl_webos_shell_surface_interface")),V(0),V(surf))
U1=ctypes.CFUNCTYPE(None,V,V,U); II=ctypes.CFUNCTYPE(None,V,V,I,I); N0=ctypes.CFUNCTYPE(None,V,V); AR=ctypes.CFUNCTYPE(None,V,V,V)
ev=[]
cbs=[U1(lambda d,s,st:ev.append(("state",st))),II(lambda d,s,x,y:ev.append(("pos",x,y))),
     N0(lambda d,s:ev.append(("close",))),AR(lambda d,s,a:ev.append(("exposed",))),
     U1(lambda d,s,st:ev.append(("about",st)))]
keep+=cbs
class SL(ctypes.Structure): _fields_=[("a",U1),("b",II),("c",N0),("d",AR),("e",U1)]
sl=SL(*cbs); keep.append(sl)
C.wl_proxy_add_listener(V(shsurf),ctypes.byref(sl),V(0))
C.wl_proxy_marshal(V(shsurf),U(2),S(b"appId"),S(APPID.encode()))
C.wl_proxy_marshal(V(shsurf),U(2),S(b"_WEBOS_WINDOW_TYPE"),S(b"_WEBOS_WINDOW_TYPE_CARD"))
C.wl_proxy_marshal(V(shsurf),U(1),U(0))            # set_state (NO set_size: it hard-closes)
stride=Wd*4; size=stride*Ht
bufpath="/tmp/.ovl_buf.%d"%os.getpid()
fd=os.open(bufpath,os.O_RDWR|os.O_CREAT|os.O_TRUNC,0600)
os.write(fd,struct.pack("<I",0xFFFF00FF)*(Wd*Ht)); os.fsync(fd)
pool=C.wl_proxy_marshal_constructor(V(shm),U(0),V(ip(C,"wl_shm_pool_interface")),V(0),I(fd),I(size))
try: os.unlink(bufpath)
except Exception: pass
buf=C.wl_proxy_marshal_constructor(V(pool),U(0),V(ip(C,"wl_buffer_interface")),V(0),I(0),I(Wd),I(Ht),I(stride),U(0))
C.wl_proxy_marshal(V(surf),U(1),V(buf),I(0),I(0))
C.wl_proxy_marshal(V(surf),U(2),I(0),I(0),I(Wd),I(Ht))
C.wl_proxy_marshal(V(surf),U(6))
C.wl_display_roundtrip(V(dpy)); C.wl_display_roundtrip(V(dpy))
log("after commit err=%d"%C.wl_display_get_error(V(dpy)))
for i in range(12):
    G.g_main_context_iteration(ctx, 0)
    C.wl_display_roundtrip(V(dpy)); time.sleep(0.4)
    if i==4: log("events@2s", ev)
log("end events", ev, "err=%d"%C.wl_display_get_error(V(dpy)))
