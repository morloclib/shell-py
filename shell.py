import os
import os.path
import stat
import shutil
import subprocess
import signal
import time
import platform
import fnmatch
import re
import sys


# ============================================================================
# A. Pure path operations
# ============================================================================

def morloc_path_join(a, b):
    return os.path.join(a, b)

def morloc_path_split(p):
    d, f = os.path.split(p)
    return (d, f)

def morloc_path_dir(p):
    return os.path.dirname(p)

def morloc_path_base(p):
    return os.path.basename(p)

def morloc_path_ext(p):
    _, ext = os.path.splitext(p)
    return ext

def morloc_path_stem(p):
    return os.path.splitext(os.path.basename(p))[0]

def morloc_replace_ext(p, ext):
    root, _ = os.path.splitext(p)
    return root + ext

def morloc_add_ext(p, ext):
    return p + ext

def morloc_drop_ext(p):
    root, _ = os.path.splitext(p)
    return root

def morloc_norm_path(p):
    return os.path.normpath(p)

def morloc_is_absolute(p):
    return os.path.isabs(p)

def morloc_is_relative(p):
    return not os.path.isabs(p)

def morloc_path_components(p):
    parts = []
    while True:
        head, tail = os.path.split(p)
        if tail:
            parts.append(tail)
        elif head and head != p:
            p = head
            continue
        else:
            if head:
                parts.append(head)
            break
        p = head
    parts.reverse()
    return parts


# ============================================================================
# B. Filesystem navigation
# ============================================================================

def morloc_pwd():
    return os.getcwd()

def morloc_cd(d):
    os.chdir(d)
    return None

def morloc_realpath(p):
    return os.path.realpath(p)

def morloc_home_dir():
    return os.path.expanduser("~")

def morloc_tmp_dir():
    import tempfile
    return tempfile.gettempdir()


# ============================================================================
# C. Directory listing
# ============================================================================

def morloc_ls(d):
    return sorted(os.listdir(d))

def morloc_ls_with(opts, d):
    entries = os.listdir(d)
    if not opts["showAll"]:
        entries = [e for e in entries if not e.startswith(".")]
    if opts["followSymlinks"]:
        pass  # listdir already returns names regardless
    if opts["sortByTime"]:
        entries.sort(key=lambda e: os.path.getmtime(os.path.join(d, e)), reverse=True)
    else:
        entries.sort()
    if opts["reverseOrder"]:
        entries.reverse()
    return entries

def morloc_ls_stat(d):
    result = []
    for name in sorted(os.listdir(d)):
        full = os.path.join(d, name)
        try:
            st = os.lstat(full)
            result.append({
                "name": name,
                "path": full,
                "isFile": stat.S_ISREG(st.st_mode),
                "isDir": stat.S_ISDIR(st.st_mode),
                "isSymlink": stat.S_ISLNK(st.st_mode),
            })
        except OSError:
            result.append({
                "name": name,
                "path": full,
                "isFile": False,
                "isDir": False,
                "isSymlink": False,
            })
    return result


# ============================================================================
# D. File management
# ============================================================================

def morloc_cp(opts, src, dst):
    if opts["recursive"]:
        if os.path.isdir(src):
            if opts["noClobber"] and os.path.exists(dst):
                return None
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            if opts["noClobber"] and os.path.exists(dst):
                return None
            shutil.copy2(src, dst) if opts["preserve"] else shutil.copy(src, dst)
    else:
        if opts["noClobber"] and os.path.exists(dst):
            return None
        shutil.copy2(src, dst) if opts["preserve"] else shutil.copy(src, dst)
    return None

def morloc_mv(src, dst):
    shutil.move(src, dst)
    return None

def morloc_rm(opts, p):
    if os.path.isdir(p):
        if opts["recursive"]:
            shutil.rmtree(p)
        else:
            os.rmdir(p)
    else:
        try:
            os.remove(p)
        except FileNotFoundError:
            if not opts["force"]:
                raise
    return None

def morloc_mkdir(d):
    os.makedirs(d, exist_ok=True)
    return None

def morloc_touch(p):
    if os.path.exists(p):
        os.utime(p, None)
    else:
        open(p, "a").close()
    return None

def morloc_chmod(mode, p):
    os.chmod(p, mode)
    return None

def morloc_chown(uid, gid, p):
    os.chown(p, uid, gid)
    return None

def morloc_symlink(target, link):
    os.symlink(target, link)
    return None

def morloc_hardlink(target, link):
    os.link(target, link)
    return None

def morloc_readlink(p):
    return os.readlink(p)

def morloc_rename(src, dst):
    os.rename(src, dst)
    return None


# ============================================================================
# E. File I/O
# ============================================================================

def morloc_read_file(p):
    with open(p, "r") as f:
        return f.read()

def morloc_write_file(p, content):
    with open(p, "w") as f:
        f.write(content)
    return None

def morloc_append_file(p, content):
    with open(p, "a") as f:
        f.write(content)
    return None

def morloc_read_lines(p):
    with open(p, "r") as f:
        return [line.rstrip("\n") for line in f]

def morloc_write_lines(p, lines):
    with open(p, "w") as f:
        for line in lines:
            f.write(line + "\n")
    return None

def morloc_read_bytes(p):
    with open(p, "rb") as f:
        return list(f.read())

def morloc_write_bytes(p, data):
    with open(p, "wb") as f:
        f.write(bytes(data))
    return None

def morloc_read_head(p, n):
    lines = []
    with open(p, "r") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            lines.append(line.rstrip("\n"))
    return lines


# ============================================================================
# F. File information
# ============================================================================

def _stat_to_dict(p):
    st = os.lstat(p)
    try:
        import pwd as pwd_mod
        owner = pwd_mod.getpwuid(st.st_uid).pw_name
    except (ImportError, KeyError):
        owner = str(st.st_uid)
    try:
        import grp
        group = grp.getgrgid(st.st_gid).gr_name
    except (ImportError, KeyError):
        group = str(st.st_gid)
    return {
        "size": st.st_size,
        "mtime": int(st.st_mtime),
        "atime": int(st.st_atime),
        "ctime": int(st.st_ctime),
        "mode": stat.S_IMODE(st.st_mode),
        "uid": st.st_uid,
        "gid": st.st_gid,
        "owner": owner,
        "group": group,
        "nlinks": st.st_nlink,
        "isFile": stat.S_ISREG(st.st_mode),
        "isDir": stat.S_ISDIR(st.st_mode),
        "isSymlink": stat.S_ISLNK(st.st_mode),
    }

def morloc_stat(p):
    return _stat_to_dict(p)

def morloc_file_size(p):
    return os.path.getsize(p)

def morloc_path_exists(p):
    return os.path.exists(p) or os.path.islink(p)

def morloc_is_file(p):
    return os.path.isfile(p)

def morloc_is_dir(p):
    return os.path.isdir(p)


# ============================================================================
# G. Directory traversal
# ============================================================================

def morloc_glob(pattern):
    import glob as glob_mod
    return sorted(glob_mod.glob(pattern, recursive=True))

def morloc_find(opts, d):
    results = []
    max_depth = opts["maxDepth"]
    name_pat = opts["namePattern"]
    files_only = opts["filesOnly"]
    dirs_only = opts["dirsOnly"]
    follow = opts["followSymlinks"]
    base_depth = d.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(d, followlinks=follow):
        current_depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        if max_depth >= 0 and current_depth > max_depth:
            dirnames[:] = []
            continue
        if not dirs_only:
            for f in filenames:
                if fnmatch.fnmatch(f, name_pat):
                    results.append(os.path.join(dirpath, f))
        if not files_only:
            for dn in dirnames:
                if fnmatch.fnmatch(dn, name_pat):
                    results.append(os.path.join(dirpath, dn))
    return sorted(results)

def morloc_walk(d):
    results = []
    for dirpath, dirnames, filenames in os.walk(d):
        results.append((dirpath, list(dirnames), list(filenames)))
    return results

def morloc_walk_filter(pred, d):
    results = []
    for dirpath, dirnames, filenames in os.walk(d):
        kept_dirs = []
        for dn in dirnames:
            full = os.path.join(dirpath, dn)
            entry = {
                "name": dn,
                "path": full,
                "isFile": False,
                "isDir": True,
                "isSymlink": os.path.islink(full),
            }
            if pred(entry):
                kept_dirs.append(dn)
        kept_files = []
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            entry = {
                "name": fn,
                "path": full,
                "isFile": True,
                "isDir": False,
                "isSymlink": os.path.islink(full),
            }
            if pred(entry):
                kept_files.append(fn)
        dirnames[:] = kept_dirs
        results.append((dirpath, kept_dirs, kept_files))
    return results


# ============================================================================
# H. Process execution
# ============================================================================

def morloc_run(cmd, args):
    r = subprocess.run([cmd] + args, capture_output=True, text=True)
    return {"exitCode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}

def morloc_run_with(opts, cmd, args):
    cwd = opts["cwd"] if opts["cwd"] != "." else None
    env = None
    if opts["env"]:
        env = dict(os.environ)
        for pair in opts["env"]:
            k, _, v = pair.partition("=")
            env[k] = v
    timeout = opts["timeout"] if opts["timeout"] > 0 else None
    merge = opts["mergeStderr"]
    try:
        r = subprocess.run(
            [cmd] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge else subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
        return {
            "exitCode": r.returncode,
            "stdout": r.stdout,
            "stderr": "" if merge else r.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exitCode": -1, "stdout": "", "stderr": "timeout"}

def morloc_shell(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return {"exitCode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}

def morloc_capture(cmd, args):
    r = subprocess.run([cmd] + args, capture_output=True, text=True)
    return r.stdout


# ============================================================================
# I. Process information
# ============================================================================

def morloc_get_pid():
    return os.getpid()

def morloc_get_parent_pid():
    return os.getppid()

# Process listings come from ps(1), whose POSIX fields read the same on Linux
# and macOS, so one code path serves both. Two calls: the command name is the
# last field of one, the full command line of the other, since either may
# contain spaces.
_PS_FIELDS = ["pid", "ppid", "uid", "pcpu", "pmem", "vsz", "rss", "nice", "pri", "time", "stat"]


def _ps(args):
    r = subprocess.run(["ps"] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return r.stdout.splitlines()


def _ps_seconds(text):
    """Seconds in a ps TIME field: [[DD-]HH:]MM:SS[.ss]."""
    days = 0
    if "-" in text:
        d, text = text.split("-", 1)
        days = int(d)
    secs = 0.0
    for part in text.split(":"):
        secs = secs * 60 + float(part)
    return days * 86400 + secs


def _ps_int(text):
    try:
        return int(text)
    except ValueError:
        return 0  # e.g. "-" for the nice value of a real-time process


def _shared_bytes(pid):
    """File-backed and shared resident memory, where the platform reports it."""
    total = 0
    try:
        with open("/proc/{}/status".format(pid)) as f:
            for line in f:
                if line.startswith(("RssFile:", "RssShmem:")):
                    total += int(line.split()[1]) * 1024
    except OSError:
        pass
    return total


def _user_name(uid):
    try:
        import pwd as pwd_mod
        return pwd_mod.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


def _processes(pids=None):
    """ProcessInfo records for `pids`, or for every process when None."""
    select = ["-A"] if pids is None else ["-p", ",".join(str(p) for p in pids)]
    cols = ["-o", ",".join(f + "=" for f in _PS_FIELDS) + ",comm="]
    args_by_pid = {}
    for line in _ps(select + ["-o", "pid=,args="]):
        parts = line.split(None, 1)
        if parts:
            args_by_pid[int(parts[0])] = parts[1] if len(parts) > 1 else ""
    result = []
    for line in _ps(select + cols):
        parts = line.split(None, len(_PS_FIELDS))
        if len(parts) <= len(_PS_FIELDS):
            continue
        f = dict(zip(_PS_FIELDS, parts))
        pid = int(f["pid"])
        result.append({
            "pid": pid,
            "ppid": int(f["ppid"]),
            "user": _user_name(int(f["uid"])),
            "state": f["stat"],
            "cpuPercent": float(f["pcpu"]),
            "memPercent": float(f["pmem"]),
            "virt": int(f["vsz"]) * 1024,
            "rss": int(f["rss"]) * 1024,
            "shared": _shared_bytes(pid),
            "nice": _ps_int(f["nice"]),
            "priority": _ps_int(f["pri"]),
            "cpuTime": _ps_seconds(f["time"]),
            "command": os.path.basename(parts[-1].strip()),
            "cmdline": args_by_pid.get(pid, "").strip(),
        })
    return result


def morloc_list_processes():
    return _processes()

def morloc_get_process(pid):
    found = _processes([pid])
    if not found:
        raise RuntimeError("Process {} not found".format(pid))
    return found[0]

def morloc_process_children(pid):
    return [p for p in _processes() if p["ppid"] == pid]

def morloc_kill(sig, pid):
    os.kill(pid, sig)
    return None

def morloc_wait_pid(pid):
    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    return -1


# ============================================================================
# J. System information
# ============================================================================

def morloc_uname():
    u = platform.uname()
    return {
        "osName": u.system,
        "nodeName": u.node,
        "release": u.release,
        "version": u.version,
        "machine": u.machine,
    }

def morloc_hostname():
    return platform.node()

def morloc_uptime():
    if sys.platform == "darwin":
        out = subprocess.run(["sysctl", "-n", "kern.boottime"], stdout=subprocess.PIPE, text=True).stdout
        return time.time() - _parse_boottime(out)
    with open("/proc/uptime", "r") as f:
        return float(f.read().split()[0])


def _parse_boottime(text):
    """Seconds since the epoch from `sysctl -n kern.boottime`:
    "{ sec = 1700000000, usec = 250000 } Tue Nov 14 ..."."""
    m = re.search(r"sec = (\d+), usec = (\d+)", text)
    if not m:
        raise RuntimeError("cannot read the boot time: " + text.strip())
    return int(m.group(1)) + int(m.group(2)) / 1e6

def morloc_cpu_count():
    return os.cpu_count() or 1

def morloc_mem_info():
    if sys.platform == "darwin":
        run = lambda *a: subprocess.run(list(a), stdout=subprocess.PIPE, text=True).stdout
        return _parse_darwin_mem(
            int(run("sysctl", "-n", "hw.memsize")), run("vm_stat"), run("sysctl", "-n", "vm.swapusage")
        )
    info = {}
    with open("/proc/meminfo", "r") as f:
        for line in f:
            parts = line.split()
            info[parts[0].rstrip(":")] = int(parts[1]) * 1024  # kB to bytes
    total, free = info.get("MemTotal", 0), info.get("MemFree", 0)
    buffers, cached = info.get("Buffers", 0), info.get("Cached", 0)
    swap_total, swap_free = info.get("SwapTotal", 0), info.get("SwapFree", 0)
    return {
        "total": total, "available": info.get("MemAvailable", free), "used": total - free - buffers - cached,
        "free": free, "buffers": buffers, "cached": cached,
        "swapTotal": swap_total, "swapUsed": swap_total - swap_free, "swapFree": swap_free,
    }


def _parse_darwin_mem(total, vm_stat, swapusage):
    """MemInfo from macOS's hw.memsize, `vm_stat` and vm.swapusage."""
    page = int(re.search(r"page size of (\d+) bytes", vm_stat).group(1))
    pages = {}
    for line in vm_stat.splitlines()[1:]:
        key, _, val = line.partition(":")
        if val.strip().rstrip(".").isdigit():
            pages[key.strip()] = int(val.strip().rstrip(".")) * page
    free = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
    cached = pages.get("File-backed pages", 0)
    available = free + pages.get("Pages inactive", 0) + pages.get("Pages purgeable", 0)
    unit = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30}
    swap = {k: float(v) * unit[u] for k, v, u in re.findall(r"(total|used|free) = ([\d.]+)([KMG])", swapusage)}
    return {
        "total": total, "available": available, "used": total - available,
        "free": free, "buffers": 0, "cached": cached,
        "swapTotal": int(swap.get("total", 0)), "swapUsed": int(swap.get("used", 0)),
        "swapFree": int(swap.get("free", 0)),
    }

def morloc_disk_info():
    """Mounted filesystems, from POSIX `df -P -k` and the `mount` listing,
    which both Linux and macOS provide."""
    out = subprocess.run(["df", "-P", "-k"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    types = _parse_mount(subprocess.run(["mount"], stdout=subprocess.PIPE, text=True).stdout)
    result = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        mount = parts[5]
        try:
            pct = float(parts[4].rstrip("%"))
        except ValueError:
            pct = 0.0
        result.append({
            "mountPoint": mount,
            "fsType": types.get(mount, ""),
            "total": int(parts[1]) * 1024,
            "used": int(parts[2]) * 1024,
            "free": int(parts[3]) * 1024,
            "usagePercent": pct,
        })
    return result


def _parse_mount(text):
    """Mount point -> filesystem type from `mount` output, in either the
    Linux form "dev on /path type ext4 (rw,...)" or the macOS form
    "dev on /path (apfs, local, ...)"."""
    types = {}
    for line in text.splitlines():
        m = re.match(r".+? on (.+) type (\S+) \(", line) or re.match(r".+? on (.+) \(([^,)]+)", line)
        if m:
            types[m.group(1)] = m.group(2)
    return types

def morloc_load_avg():
    load1, load5, load15 = os.getloadavg()
    return {"load1": load1, "load5": load5, "load15": load15}


# ============================================================================
# K. Environment variables
# ============================================================================

def morloc_get_env(var):
    val = os.environ.get(var)
    if val is None:
        raise RuntimeError("Environment variable '{}' not set".format(var))
    return val

def morloc_set_env(var, val):
    os.environ[var] = val
    return None

def morloc_unset_env(var):
    os.environ.pop(var, None)
    return None

def morloc_environ():
    return list(os.environ.items())

def morloc_has_env(var):
    return var in os.environ
