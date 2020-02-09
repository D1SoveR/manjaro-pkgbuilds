import ctypes
import ctypes.util
import os
import os.path
from shutil import rmtree
import sys
from tempfile import mkdtemp

_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
_libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)
_libc.umount2.argtypes = (ctypes.c_char_p, ctypes.c_ulong)

def bind_mount(source, target):

    """
    Helper method used to bind mount the source directory to target one.
    Used primarily for bind mounting the root directory for creating
    nspawn directories with full system presence.
    """

    ret = _libc.mount(source.encode(), target.encode(), b"none", 4096, b"")
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"Error bind mounting {source} on {target}: {os.strerror(errno)}")

def bind_unmount(target):

    """
    Helper method used to unmount previously created bind mounting.
    """

    ret = _libc.umount2(target.encode(), 0)
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"Error umounting {target}: {os.strerror(errno)}")

class TempDirectory:

    """
    Helper context manager to handle creation of temporary directories
    and automatic clean-up once they're no longer used.
    Used primarily with creating temporary bind mount for nspawn container,
    as well as bound destination for depositing built packages into.
    """

    __slots__ = ("mount", "tempdir")

    def __init__(self, mount=None):
        if mount and not os.path.isdir(mount):
            raise RuntimeError(f"{mount} is not a valid bind mount source")
        self.mount = mount

    def __enter__(self, mount=None):
        self.tempdir = mkdtemp()
        if self.mount:
            bind_mount(self.mount, self.tempdir)
        return self.tempdir

    def __exit__(self, *args):
        if self.mount:
            bind_unmount(self.tempdir)
        rmtree(self.tempdir)
        del self.tempdir

_original_excepthook = sys.excepthook
def custom_exception_handler(exctype, value, tb):

    """
    Custom exception handler set up to provide bit
    clearer print-out of some expected errors; RuntimeErrors
    used in this code occur in known scenarios, so we don't
    need entire stack trace.
    """

    if exctype == RuntimeError:
        print(value, file=sys.stderr)
    else:
        _original_excepthook(exctype, value, tb)