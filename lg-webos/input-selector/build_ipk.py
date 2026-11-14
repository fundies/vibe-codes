import io, tarfile, time, os, sys
APPID="com.webosbrew.overlay"
SRC=os.path.join(os.path.dirname(os.path.abspath(__file__)),"overlayapp")
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"overlay.ipk")
ICON=os.path.join(os.path.dirname(os.path.abspath(__file__)),"ipkinspect","usr","palm","applications","com.webosbrew.inputs","icon.png")
now=int(time.time())

def tgz(members):
    # members: list of (name, bytes, mode)
    buf=io.BytesIO()
    import gzip
    gz=gzip.GzipFile(fileobj=buf, mode="wb", mtime=0)
    tf=tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT)
    # add parent dirs explicitly for determinism
    added=set()
    def adddir(path):
        if path in added or path in ("", "."): return
        parent=os.path.dirname(path.rstrip("/"))
        if parent: adddir(parent+"/")
        ti=tarfile.TarInfo("./"+path if not path.startswith("./") else path)
        ti.type=tarfile.DIRTYPE; ti.mode=0o755; ti.mtime=now; ti.uid=ti.gid=0
        tf.addfile(ti); added.add(path)
    for name,data,mode in members:
        d=os.path.dirname(name)
        if d: adddir(d+"/")
        ti=tarfile.TarInfo("./"+name); ti.size=len(data); ti.mode=mode; ti.mtime=now; ti.uid=ti.gid=0
        tf.addfile(ti, io.BytesIO(data))
    tf.close(); gz.close()
    return buf.getvalue()

def rd(p):
    f=open(p,"rb"); d=f.read(); f.close(); return d

control=("Package: %s\nVersion: 1.0.0\nSection: misc\nPriority: optional\n"
         "Architecture: all\nInstalled-Size: 40\nMaintainer: webosbrew <nobody@example.com>\n"
         "Description: Transparent input overlay.\nwebOS-Package-Format-Version: 2\n"
         "webOS-Packager-Version: 1.0.0\n" % APPID).encode()
control_tgz=tgz([("control", control, 0o644)])

base="usr/palm/applications/%s/"%APPID
pkg="usr/palm/packages/%s/"%APPID
data_members=[
    (base+"appinfo.json", rd(os.path.join(SRC,"appinfo.json")), 0o644),
    (base+"run.sh",       rd(os.path.join(SRC,"run.sh")),       0o755),
    (base+"overlay.py",   rd(os.path.join(SRC,"overlay.py")),   0o644),
    (base+"icon.png",     rd(ICON),                             0o644),
    (pkg+"packageinfo.json", ('{"id":"%s","version":"1.0.0","app":"%s"}'%(APPID,APPID)).encode(), 0o644),
]
data_tgz=tgz(data_members)

def ar_member(name, data):
    hdr=("%-16s%-12d%-6d%-6d%-8s%-10d`\n" % (name, 0, 0, 0, "100644", len(data))).encode()
    out=hdr+data
    if len(data)%2: out+=b"\n"
    return out
ar=b"!<arch>\n"
ar+=ar_member("debian-binary", b"2.0\n")
ar+=ar_member("control.tar.gz", control_tgz)
ar+=ar_member("data.tar.gz", data_tgz)
open(OUT,"wb").write(ar)
print("wrote %s (%d bytes)" % (OUT, len(ar)))
