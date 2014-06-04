#!/usr/bin/python
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>
#

"""
brand_hunter

searches SRPM content for possible Red Hat branding issues
"""

try:
  import magic 
except ImportError as e:
  raise ImportError("%s: please install the 'python-magic' package" % e)

import os
import re
import shutil
import sys
import subprocess
import tarfile
import yum 

from optparse import OptionParser 

REPOS = { 
  'Client': 
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/Client/source/tree',

  'Client-optional': 
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/Client-optional/source/tree',

  'ComputeNode': 
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/ComputeNode/source/tree',

  'ComputeNode-optional': 
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/ComputeNode-optional/source/tree',

  'Server': 
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/Server/source/tree',

  'Server-optional': 
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/Server-optional/source/tree',

  'Workstation': 
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/Workstation/source/tree',

  'Workstation-optional':
  'ftp://ftp.redhat.org/redhat/rhel/rc/7/Workstation-optional/source/tree',
  }

YUMCONF = '''
[main]
cachedir=/yum_cache
persistdir=/yum_persist
logfile=/yum.log
gpgcheck=0
reposdir=/
'''

DEVNULL=open('/dev/null', 'w')

MIME = magic.open(magic.MAGIC_MIME)
MIME.load()

RE = re.compile(r'[Rr][Ee][Dd]\s?[Hh][Aa][Tt]', flags=re.M)

TAR_OPEN_MODE = {
  'application/x-bzip2' : 'r:bz2',
  'application/x-gzip'  : 'r:gz',
  }

def main(opts, args):
    if not os.path.exists(opts.working_dir):
      print "creating cachedir at %s" % opts.working_dir
      os.makedirs(opts.working_dir)

    noissues_file = '%s/noissues.txt' % opts.working_dir
    if os.path.exists(noissues_file): os.remove(noissues_file)

    # create yumconf
    text = YUMCONF.split()
    for k,v in REPOS.items():
      text.append('\n')
      text.append('[%s]' % k)
      text.append('name = %s' % k)
      text.append('baseurl = %s' % v.strip())

    yumconf = opts.working_dir + '/yum.conf'
    with open(yumconf, 'w') as f:
      f.write('\n'.join(text))

    yb = yum.YumBase()
    yb.preconf.fn = yumconf 
    yb.preconf.root = opts.working_dir
    yb.preconf.init_plugins = False

    yb.doSackSetup(archlist=['src'])

    processed = set()

    count = 0
    for pkg in sorted(yb.pkgSack.returnPackages(patterns=args)):
      # if count == 100: break
      if not str(pkg) in processed:

        print str(pkg)

        topdir = '%s/SRPMS/%s' % (opts.working_dir, str(pkg))
        srcdir = '%s/SOURCES' % topdir
        issues_file = '%s/issues.txt' % topdir

        if os.path.exists(issues_file): os.remove(issues_file)
        shutil.rmtree(srcdir, ignore_errors=True)

        yb.downloadPkgs([pkg])
        subprocess.check_call("rpm --define '_topdir %s' -i %s" % 
                              (topdir, pkg.localPkg()), shell=True,
                              stdout=DEVNULL, stderr=DEVNULL)

        issues = []
        for path,_,files in os.walk(srcdir, topdown=False):
          for file in files:
            find_issues(issues, srcdir, os.path.join(path, file))

        if issues:
          with open(issues_file, 'w') as f:
            f.write("\n".join(issues) + '\n')
            print "* see %s\n" % issues_file
        else:
          with open(noissues_file, 'a+') as f:
            print "* no issues\n" 
            f.write('%s\n' % pkg)
          
        processed.add(str(pkg))
        count += 1

def find_issues(issues, root, file):
  relpath = file.replace(root + '/', '')

  if not os.path.exists(file):
    return

  mimetype=MIME.file(file)

  if 'application/x-empty' in mimetype:
    return

  elif not 'charset=binary' in mimetype:
    with open(file, 'r') as fo:
      s = fo.read()
      for m in RE.finditer(s):
        lineno = s.count('\n',0,m.start())
        issues.append('%s:%s:%s' % (relpath, lineno+1, s.split('\n')[lineno]))

  elif ('application/x-bzip2' in mimetype or 
        'application/x-gzip' in mimetype):
    try:
      tf = tarfile.open(file, TAR_OPEN_MODE[mimetype.split(';')[0]])
    except tarfile.ReadError:
      # we can't decompress the file, so treat it as an unknown binary file
      issues.append('%s:binary file' % relpath) 
    else:  
      tf.extractall(os.path.dirname(file))
      os.remove(file)
      for n in tf.getnames():
        mp = '%s/%s' % (os.path.dirname(file), n)
        if 'application/x-directory' not in MIME.file(mp):
          find_issues(issues, root, mp)

  else:
    issues.append('%s:binary file' % relpath) 

if __name__ == '__main__': 

    parser = OptionParser("usage: %prog [options] [srpm ...]",
                          description=(
    "Search srpms for Red Hat branding or binary files. Srpms may be listed "
    "using standard package patterns including glob characters. If no srpms "
    "are specified, all srpms will be searched."
    "\n"
    "At the completion of processing, a list of srpms with no issues will be "
    "written to a file located at <working-dir>/noissues.txt."
    "\n"
    "Issues for individual srpms will be written to file located at "
    "<working-dir>/SRPMS/<srpm>/issues.txt"
    ))

    # not implemented
    # parser.add_option('-i', '--ignore', metavar='PATH',
    #   action='append',
    #   dest='ignore_files',
    #   default=[],
    #   help="file containing srpms to ignore")
 
    parser.add_option('-w', '--working-dir', metavar='PATH',
      dest='working_dir',
      default=os.path.expanduser('~/brand-hunter'),
      help="defaults to ~/brand-hunter")

    opts,args = parser.parse_args(args=sys.argv[1:])
  
    main(opts, args)
    sys.exit()
