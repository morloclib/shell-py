import os
import os.path
import stat
import shutil
import subprocess
import signal
import time
import platform
import fnmatch


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
            capture_output=not merge,
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

def morloc_exec(cmd, args):
    os.execvp(cmd, [cmd] + args)
    return None


# ============================================================================
# I. Process information
# ============================================================================

def morloc_get_pid():
    return os.getpid()

def morloc_get_parent_pid():
    return os.getppid()

def _read_proc_stat(pid):
    try:
        with open("/proc/{}/stat".format(pid), "r") as f:
            parts = f.read().split()
        comm = parts[1].strip("()")
        state = parts[2]
        ppid = int(parts[3])
        nice = int(parts[18])
        priority = int(parts[17])
        utime = int(parts[13])
        stime = int(parts[14])
        virt = int(parts[22])
        rss_pages = int(parts[23])
        rss = rss_pages * os.sysconf("SC_PAGE_SIZE")
        cpu_time = (utime + stime) / os.sysconf("SC_CLK_TCK")
        return {
            "comm": comm,
            "state": state,
            "ppid": ppid,
            "nice": nice,
            "priority": priority,
            "virt": virt,
            "rss": rss,
            "cpuTime": cpu_time,
        }
    except (OSError, IndexError, ValueError):
        return None

def _read_proc_status(pid):
    info = {"uid": 0, "shared": 0}
    try:
        with open("/proc/{}/status".format(pid), "r") as f:
            for line in f:
                if line.startswith("Uid:"):
                    info["uid"] = int(line.split()[1])
                elif line.startswith("RssFile:") or line.startswith("RssShmem:"):
                    info["shared"] += int(line.split()[1]) * 1024
    except OSError:
        pass
    return info

def _read_proc_cmdline(pid):
    try:
        with open("/proc/{}/cmdline".format(pid), "r") as f:
            return f.read().replace("\x00", " ").strip()
    except OSError:
        return ""

def _build_process_info(pid):
    ps = _read_proc_stat(pid)
    if ps is None:
        return None
    status = _read_proc_status(pid)
    cmdline = _read_proc_cmdline(pid)
    try:
        import pwd as pwd_mod
        user = pwd_mod.getpwuid(status["uid"]).pw_name
    except (ImportError, KeyError):
        user = str(status["uid"])
    return {
        "pid": pid,
        "ppid": ps["ppid"],
        "user": user,
        "state": ps["state"],
        "cpuPercent": 0.0,
        "memPercent": 0.0,
        "virt": ps["virt"],
        "rss": ps["rss"],
        "shared": status["shared"],
        "nice": ps["nice"],
        "priority": ps["priority"],
        "cpuTime": ps["cpuTime"],
        "command": ps["comm"],
        "cmdline": cmdline,
    }

def morloc_list_processes():
    result = []
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            info = _build_process_info(int(entry))
            if info is not None:
                result.append(info)
    return result

def morloc_get_process(pid):
    info = _build_process_info(pid)
    if info is None:
        raise RuntimeError("Process {} not found".format(pid))
    return info

def morloc_process_children(pid):
    children = []
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            info = _build_process_info(int(entry))
            if info is not None and info["ppid"] == pid:
                children.append(info)
    return children

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
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.read().split()[0])
    except OSError:
        return 0.0

def morloc_cpu_count():
    return os.cpu_count() or 1

def morloc_mem_info():
    info = {
        "total": 0, "available": 0, "used": 0, "free": 0,
        "buffers": 0, "cached": 0,
        "swapTotal": 0, "swapUsed": 0, "swapFree": 0,
    }
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(":")
                val = int(parts[1]) * 1024  # convert kB to bytes
                if key == "MemTotal":
                    info["total"] = val
                elif key == "MemAvailable":
                    info["available"] = val
                elif key == "MemFree":
                    info["free"] = val
                elif key == "Buffers":
                    info["buffers"] = val
                elif key == "Cached":
                    info["cached"] = val
                elif key == "SwapTotal":
                    info["swapTotal"] = val
                elif key == "SwapFree":
                    info["swapFree"] = val
    except OSError:
        pass
    info["used"] = info["total"] - info["free"] - info["buffers"] - info["cached"]
    info["swapUsed"] = info["swapTotal"] - info["swapFree"]
    return info

def morloc_disk_info():
    result = []
    try:
        st_out = subprocess.run(
            ["df", "-T", "-B1", "--output=target,fstype,size,used,avail,pcent"],
            capture_output=True, text=True,
        )
        for line in st_out.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 6:
                pct_str = parts[5].rstrip("%")
                try:
                    pct = float(pct_str)
                except ValueError:
                    pct = 0.0
                result.append({
                    "mountPoint": parts[0],
                    "fsType": parts[1],
                    "total": int(parts[2]),
                    "used": int(parts[3]),
                    "free": int(parts[4]),
                    "usagePercent": pct,
                })
    except (OSError, subprocess.SubprocessError):
        pass
    return result

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
