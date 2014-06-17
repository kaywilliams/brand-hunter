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

searches spec and source files for possible Red Hat branding issues
"""

try:
  import magic 
except ImportError as e:
  raise ImportError("%s: please install the 'python-magic' package" % e)

import os
import re
import sys
import tarfile

from optparse import OptionParser 

DEVNULL=open('/dev/null', 'w')

MIME = magic.open(magic.MAGIC_MIME)
MIME.load()

RE = re.compile(r'[Rr][Ee][Dd]\s?[Hh][Aa][Tt]', flags=re.M)
RE_EMAIL = re.compile(r'<[^@]+@redhat.com>', flags=re.M)

TAR_OPEN_MODE = {
  'application/x-bzip2' : 'r:bz2',
  'application/x-gzip'  : 'r:gz',
  }


def main(opts, args):
  # validate directory
  for topdir in args:
    if not ('SPECS' in os.listdir(topdir) and 'SOURCES' in os.listdir(topdir)):
      print ("Error: The specified directory does not contain SPECS and "
             "SOURCES folders")
      sys.exit(1)

    # setup
    print "\nprocessing %s" % topdir
    issues_file = os.path.join(topdir, 'issues.txt')

    # search files
    issues = []
    for dir in ['SPECS', 'SOURCES']:
      searchdir = os.path.join(topdir, dir)
      for path,_,files in os.walk(searchdir, topdown=False):
        for file in files:
          fp = os.path.join(path, file)
          if opts.verbose: print fp 
          find_issues(issues, topdir, fp)

    # output results
    if issues:
      with open(issues_file, 'w') as f:
        f.write("\n".join(issues) + '\n')
      print "- issues found: see %s" % issues_file
    else:
      print "- no issues found"

    print "\n" # blank line at end for readability
    

def find_issues(issues, topdir, file):
  relpath = file.replace(topdir + '/', '')

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
        line = s.split('\n')[lineno]

        # filter out lines with email only matches
        if opts.ignore_email:
          email = RE_EMAIL.findall(line)
          if email and len(email) == len(RE.findall(line)):
            continue

        issues.append('%s:%s:%s' % (relpath, lineno+1, line))

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
        mp = os.path.join(os.path.dirname(file), n)
        if not os.path.isdir(mp):
          find_issues(issues, topdir, mp)

  else:
    issues.append('%s:binary file' % relpath) 

if __name__ == '__main__': 

    parser = OptionParser("usage: %prog [options] directory...",
                          description=(
    "Searches SPEC and SOURCE folders in one or more directories for possible "
    "Red Hat branding issues."
    ))

    parser.add_option('--ignore-email',
      dest='ignore_email',
      action='store_true',
      default=False,
      help="ignore text that matches '<email@redhat.com>'")

    parser.add_option('--verbose', '-v',
      dest='verbose',
      action='store_true',
      default=False,
      help="print the names of files as they are processed")

    opts,args = parser.parse_args(args=sys.argv[1:])

    if not args:
      print "Error: no directory specified"
      sys.exit(1)
  
    main(opts, args)
    sys.exit()
