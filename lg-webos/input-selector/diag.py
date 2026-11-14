import ctypes, os, time, struct, sys
ST=int(sys.argv[1]) if len(sys.argv)>1 else 1
SZ=(len(sys.argv)>2 and sys.argv[2]=='size')
C=ctypes.CDLL("libwayland-client.so.0",mode=ctypes.RTLD_GLOBAL)
W=ctypes.CDLL("libwayland-webos-client.so.1",mode=ctypes.RTLD_GLOBAL)
V=ctypes.c_void_p;U=ctypes.c_uint;I=ctypes.c_int;S=ctypes.c_char_p
C.wl_display_connect.restype=V;C.wl_display_connect.argtypes=[S]
C.wl_proxy_marshal_constructor.restype=V
C.wl_display_roundtrip.restype=I;C.wl_display_roundtrip.argtypes=[V]
C.wl_display_get_error.restype=I;C.wl_display_get_error.argtypes=[V]
C.wl_display_get_protocol_error.restype=U
C.wl_display_get_protocol_error.argtypes=[V,ctypes.POINTER(V),ctypes.POINTER(U)]
C.wl_proxy_marshal.restype=None
C.wl_proxy_add_listener.restype=I;C.wl_proxy_add_listener.argtypes=[V,V,V]
class M(ctypes.Structure): _fields_=[("name",S),("sig",S),("types",V)]
class Iface(ctypes.Structure): _fields_=[("name",S),("version",I),("mc",I),("m",ctypes.POINTER(M)),("ec",I),("e",ctypes.POINTER(M))]
class Opaque(ctypes.Structure): _fields_=[("x",ctypes.c_byte)]
def ip(lib,n): return ctypes.addressof(Opaque.in_dll(lib,n))
keep=[]
def chk(dpy,label):
    e=C.wl_display_get_error(V(dpy))
    if e==0: print("  [%s] ok"%label); return False
    msg="errno=%d"%e
    if e==71:
        iface=V(0); oid=U(0); code=C.wl_display_get_protocol_error(V(dpy),ctypes.byref(iface),ctypes.byref(oid))
        nm="?"
        if iface.value: nm=ctypes.cast(iface,ctypes.POINTER(Iface)).contents.name.decode()
        msg="PROTOCOL_ERROR code=%d interface=%s id=%d"%(code,nm,oid.value)
    print("  [%s] DIED: %s"%(label,msg)); return True

dpy=C.wl_display_connect(b"wayland-0")
reg=C.wl_proxy_marshal_constructor(V(dpy),U(1),V(ip(C,"wl_registry_interface")),V(0))
GLOBAL=ctypes.CFUNCTYPE(None,V,V,U,S,U);GREM=ctypes.CFUNCTYPE(None,V,V,U)
glob={}
cg=GLOBAL(lambda d,r,n,i,v:glob.__setitem__(i.decode("ascii","replace"),(n,v)));cr=GREM(lambda *a:None);keep+=[cg,cr]
class RL(ctypes.Structure): _fields_=[("g",GLOBAL),("r",GREM)]
rl=RL(cg,cr);keep.append(rl)
C.wl_proxy_add_listener(V(reg),ctypes.byref(rl),V(0));C.wl_display_roundtrip(V(dpy))
def bind(name):
    lib=W if name.startswith("wl_webos") else C; nm,ver=glob[name]
    return C.wl_proxy_marshal_constructor(V(reg),U(0),V(ip(lib,name+"_interface")),U(nm),S(name.encode()),U(ver),V(0))
comp=bind("wl_compositor");shm=bind("wl_shm");shell=bind("wl_webos_shell")
C.wl_display_roundtrip(V(dpy)); chk(dpy,"after binds")
surf=C.wl_proxy_marshal_constructor(V(comp),U(0),V(ip(C,"wl_surface_interface")),V(0))
C.wl_display_roundtrip(V(dpy));
if chk(dpy,"create_surface"): raise SystemExit
shsurf=C.wl_proxy_marshal_constructor(V(shell),U(1),V(ip(W,"wl_webos_shell_surface_interface")),V(0),V(surf))
C.wl_display_roundtrip(V(dpy))
if chk(dpy,"get_shell_surface"): raise SystemExit
C.wl_proxy_marshal(V(shsurf),U(2),S(b"appId"),S(b"com.webosbrew.overlay"))
C.wl_display_roundtrip(V(dpy))
if chk(dpy,"set_property appId"): raise SystemExit
C.wl_proxy_marshal(V(shsurf),U(2),S(b"_WEBOS_WINDOW_TYPE"),S(b"_WEBOS_WINDOW_TYPE_CARD"))
C.wl_display_roundtrip(V(dpy))
if chk(dpy,"set window type"): raise SystemExit
if SZ:
    C.wl_proxy_marshal(V(shsurf),U(4),I(1920),I(1080))  # set_size
    C.wl_display_roundtrip(V(dpy))
    if chk(dpy,"set_size"): raise SystemExit
C.wl_proxy_marshal(V(shsurf),U(1),U(ST))  # set_state ST
C.wl_display_roundtrip(V(dpy))
if chk(dpy,"set_state %d"%ST): raise SystemExit
# buffer
Wd,Ht=1920,1080;stride=Wd*4;size=stride*Ht
bp="/tmp/.d%d"%os.getpid();fd=os.open(bp,os.O_RDWR|os.O_CREAT|os.O_TRUNC,0600)
os.write(fd,struct.pack("<I",0x80203040)*(Wd*Ht));os.fsync(fd)
pool=C.wl_proxy_marshal_constructor(V(shm),U(0),V(ip(C,"wl_shm_pool_interface")),V(0),I(fd),I(size))
try: os.unlink(bp)
except: pass
buf=C.wl_proxy_marshal_constructor(V(pool),U(0),V(ip(C,"wl_buffer_interface")),V(0),I(0),I(Wd),I(Ht),I(stride),U(0))
C.wl_display_roundtrip(V(dpy))
if chk(dpy,"create pool+buffer"): raise SystemExit
C.wl_proxy_marshal(V(surf),U(1),V(buf),I(0),I(0))
C.wl_proxy_marshal(V(surf),U(2),I(0),I(0),I(Wd),I(Ht))
C.wl_proxy_marshal(V(surf),U(6))
C.wl_display_roundtrip(V(dpy))
if chk(dpy,"attach+commit"): raise SystemExit
print("  SURVIVED commit; waiting 2s for events")
time.sleep(2); C.wl_display_roundtrip(V(dpy)); chk(dpy,"post-wait")
