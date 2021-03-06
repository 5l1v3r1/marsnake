from __future__ import absolute_import, print_function
from utils import common, file_op
from core import logger
from core import exceptions
import os
import types
import re

def whitelist(path):
    """Return information that this file was whitelisted"""
    ret = {
        # TRANSLATORS: This is the label in the log indicating was
        # skipped because it matches the whitelist
        'label': _('Skip'),
        'n_deleted': 0,
        'n_special': 0,
        'path': path,
        'size': 0}
    return ret

def whitelisted(pathname):
    """Return boolean whether file is whitelisted"""
    regexes = [
        '^/tmp/.X0-lock$',
        '^/tmp/.truecrypt_aux_mnt.*/(control|volume)$',
        '^/tmp/.vbox-[^/]+-ipc/lock$',
        '^/tmp/.wine-[0-9]+/server-.*/lock$',
        '^/tmp/gconfd-[^/]+/lock/ior$',
        '^/tmp/fsa/',  # fsarchiver
        '^/tmp/kde-',
        '^/tmp/kdesudo-',
        '^/tmp/ksocket-',
        '^/tmp/orbit-[^/]+/bonobo-activation-register[a-z0-9-]*.lock$',
        '^/tmp/orbit-[^/]+/bonobo-activation-server-[a-z0-9-]*ior$',
        '^/tmp/pulse-[^/]+/pid$',
        '^/var/tmp/kdecache-',
        '^' + re.escape(common.expanduser('~/.cache/wallpaper/')),
        # Clean Firefox cache from Firefox cleaner (LP#1295826)
        '^' + re.escape(common.expanduser('~/.cache/mozilla')),
        # Clean Google Chrome cache from Google Chrome cleaner (LP#656104)
        '^' + re.escape(common.expanduser('~/.cache/google-chrome')),
        '^' + re.escape(common.expanduser('~/.cache/gnome-control-center/')),
        # iBus Pinyin
        # https://bugs.launchpad.net/bleachbit/+bug/1538919
        '^' + re.escape(common.expanduser('~/.cache/ibus/')),
        # Linux Bluetooth daemon obexd
        '^' + re.escape(common.expanduser('~/.cache/obexd/'))]

    for regex in regexes:
        if re.match(regex, pathname) is not None:
            return True

    return False
    
class Delete:
    """Delete a single file or directory.  Obey the user
    preference regarding shredding."""
    def __init__(self, path):
        """Create a Delete instance to delete 'path'"""
        self.path = path
        self.shred = False
        
    def __str__(self):
        return 'Command to %s %s' % \
            ('shred' if self.shred else 'delete', self.path)
            
    def execute(self):
        """Make changes and return results"""
        if whitelisted(self.path):
            print("whitelist " + self.path)
            return
            
        try:
            file_op.delete(self.path, self.shred, ignore_missing = True)
        except OSError as e:
            # WindowsError: [Error 32] The process cannot access the file because it is being
            # used by another process: u'C:\\Documents and
            # Settings\\username\\Cookies\\index.dat'
            if 32 != e.args[0] and 5 != e.args[0] and 2 != e.args[0]:
                raise

            if e.args[0] == 32:
                try:
                    file_op.delete_locked_file(self.path)
                except OSError as e:
                    if e.args[0] == 5:
                        print("No permission to delete: ", self.path)
                    raise
            else:
                if self.shred:
                    import warnings
                    warnings.warn(
                        _('At least one file was locked by another process, so its contents could not be overwritten. It will be marked for deletion upon system reboot.'))
                # TRANSLATORS: The file will be deleted when the
                # system reboots

                raise

class Function:

    """Execute a simple Python function"""
    def __init__(self, path, func, label):
        """Path is a pathname that exists or None.  If
        it exists, func takes the pathname.  Otherwise,
        function returns the size."""
        self.path = path
        self.func = func
        self.label = label

        try:
            assert isinstance(func, types.FunctionType)
        except AssertionError:
            raise AssertionError('Expected MethodType but got %s' % type(func))

    def execute(self):

        if self.path and whitelisted(self.path):
            return

        ret = {
            'label': self.label,
            'n_deleted': 0,
            'n_special': 1,
            'path': self.path,
            'size': None}

        if self.path is None:
            # Function takes no path.  It returns the size.
            func_ret = self.func()
            if isinstance(func_ret, types.GeneratorType):
                # function returned generator
                for func_ret in self.func():
                    if True == func_ret or isinstance(func_ret, tuple):
                        # Return control to GTK idle loop.
                        # If tuple, then display progress.
                        yield func_ret
            # either way, func_ret should be an integer
            assert isinstance(func_ret, (int, long))
            ret['size'] = func_ret
        else:
            if os.path.isdir(self.path):
                raise RuntimeError('Attempting to run file function %s on directory %s' %
                                   (self.func.func_name, self.path))
            # Function takes a path.  We check the size.
            oldsize = file_op.getsize(self.path)

            try:
                self.func(self.path)
            except DatabaseError as e:
                if -1 == e.message.find('file is encrypted or is not a database') and \
                   -1 == e.message.find('or missing database'):
                    raise
                logger().info(e.message)
                return

            try:
                newsize = file_op.getsize(self.path)
            except OSError as e:
                from errno import ENOENT
                if e.errno == ENOENT:
                    # file does not exist
                    newsize = 0
                else:
                    raise

            ret['size'] = oldsize - newsize

class Ini:

    """Remove sections or parameters from a .ini file"""

    def __init__(self, path, section, parameter):
        """Create the instance"""
        self.path = path
        self.section = section
        self.parameter = parameter

    def __str__(self):
        return 'Command to clean .ini path=%s, section=-%s, parameter=%s ' % \
            (self.path, self.section, self.parameter)

    def execute(self):
        """Make changes and return results"""

        if whitelisted(self.path):
            yield whitelist(self.path)
            return
            
        ret = {
            # TRANSLATORS: Parts of this file will be deleted
            'label': _('Clean file'),
            'n_deleted': 0,
            'n_special': 1,
            'path': self.path,
            'size': None}

        oldsize = file_op.getsize(self.path)
        file_op.clean_ini(self.path, self.section, self.parameter)
        newsize = file_op.getsize(self.path)
        ret['size'] = oldsize - newsize

class Json:

    """Remove a key from a JSON configuration file"""

    def __init__(self, path, address):
        """Create the instance"""
        self.path = path
        self.address = address

    def __str(self):
        return 'Command to clean JSON file, path=%s, address=%s ' % \
            (self.path, self.address)

    def execute(self, really_delete):
        """Make changes and return results"""

        if whitelisted(self.path):
            yield whitelist(self.path)
            return

        ret = {
            'label': _('Clean file'),
            'n_deleted': 0,
            'n_special': 1,
            'path': self.path,
            'size': None}
        if really_delete:
            oldsize = file_op.getsize(self.path)
            file_op.clean_json(self.path, self.address)
            newsize = file_op.getsize(self.path)
            ret['size'] = oldsize - newsize
        yield ret


class Shred(Delete):

    """Shred a single file"""

    def __init__(self, path):
        """Create an instance to shred 'path'"""
        Delete.__init__(self, path)
        self.shred = True

    def __str__(self):
        return 'Command to shred %s' % self.path


class Truncate(Delete):

    """Truncate a single file"""

    def __str__(self):
        return 'Command to truncate %s' % self.path

    def execute(self, really_delete):
        """Make changes and return results"""

        if whitelisted(self.path):
            yield whitelist(self.path)
            return

        ret = {
            # TRANSLATORS: The file will be truncated to 0 bytes in length
            'label': _('Truncate'),
            'n_deleted': 1,
            'n_special': 0,
            'path': self.path,
            'size': file_op.getsize(self.path)}
        if really_delete:
            f = open(self.path, 'wb')
            f.truncate(0)
        yield ret


class Winreg:

    """Clean Windows registry"""

    def __init__(self, keyname, valuename):
        """Create the Windows registry cleaner"""
        self.keyname = keyname
        self.valuename = valuename

    def __str__(self):
        return 'Command to clean registry, key=%s, value=%s ' % (self.keyname, self.valuename)

    def execute(self, really_delete):
        """Execute the Windows registry cleaner"""
        if 'nt' != os.name:
            raise StopIteration
        _str = None  # string representation
        ret = None  # return value meaning 'deleted' or 'delete-able'
        if self.valuename:
            _str = '%s<%s>' % (self.keyname, self.valuename)
            ret = bleachbit.Windows.delete_registry_value(self.keyname,
                                                self.valuename, really_delete)
        else:
            ret = bleachbit.Windows.delete_registry_key(self.keyname, really_delete)
            _str = self.keyname
        if not ret:
            # Nothing to delete or nothing was deleted.  This return
            # makes the auto-hide feature work nicely.
            raise StopIteration

        ret = {
            'label': _('Delete registry key'),
            'n_deleted': 0,
            'n_special': 1,
            'path': _str,
            'size': 0}

        yield ret
