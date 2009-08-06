#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
#    Copyright 2008, 2009, Lukas Lueg, lukas.lueg@gmail.com
#
#    This file is part of Pyrit.
#
#    Pyrit is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Pyrit is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Pyrit.  If not, see <http://www.gnu.org/licenses/>.


from distutils.core import setup, Extension
from distutils.command.build_ext import build_ext
from distutils.command.clean import clean
import os
import re
import subprocess
import sys
import zlib

NVIDIA_INC_DIRS = []
NVCC = 'nvcc'
for path in ('/usr/local/cuda','/opt/cuda'):
    if os.path.exists(path):
        NVIDIA_INC_DIRS.append(os.path.join(path, 'include'))
        NVCC = os.path.join(path, 'bin', 'nvcc')
        break
else:
    print >>sys.stderr, "The CUDA compiler and headers required to build the kernel were not found. Trying to continue anyway..."


try:
    svn_info = subprocess.Popen(('svn', 'info'), stdout=subprocess.PIPE).stdout.read()
    version_string = '0.2.4-dev (svn r%i)' % int(re.compile('Revision: ([0-9]*)').findall(svn_info)[0])
except:
    version_string = '0.2.4-dev'
EXTRA_COMPILE_ARGS = ['-DVERSION="%s"' % version_string]


class GPUBuilder(build_ext):
    def _call(self, comm):
        p = subprocess.Popen(comm, stdout=subprocess.PIPE, shell=True)
        stdo, stde = p.communicate()
        if p.returncode == 0:
            return stdo
        else:
            print >>sys.stderr, "%s\nFailed to execute command '%s'" % (stde, comm)
            return None
            
    def _makedirs(self, pathname):
        try:
            os.makedirs(pathname)
        except OSError:
            pass

    def run(self):
        if '_cpyrit_cudakernel.cubin.h' in os.listdir('./'):
            print "Skipping rebuild of Nvidia CUDA kernel ..."
        else:
            nvcc_o = self._call(NVCC + ' -V')
            if nvcc_o is not None:
                nvcc_version = nvcc_o.split('release ')[-1].strip()
            else:
                raise SystemError, "Nvidia's CUDA-compiler 'nvcc' can't be found. Make sure it's available to $PATH. " \
                                    "It is part of the CUDA Toolkit (not the SDK)."
            print "Compiling CUDA module using nvcc %s..." % nvcc_version
            subprocess.check_call(NVCC + ' --host-compilation C -Xptxas "-v" -Xcompiler "-fPIC" --cubin ./_cpyrit_cudakernel.cu', shell=True)
            f = open("_cpyrit_cudakernel.cubin", "rb")
            cubin = f.read() + '\x00'
            f.close()
            cubin_inc = ",".join(("0x%02X%s" % (ord(c), "\n" if i % 32 == 0 else "") for i, c in enumerate(zlib.compress(cubin,9))))
            f = open("_cpyrit_cudakernel.cubin.h", "wb")
            f.write("unsigned char __cudakernel_packedmodule[] = {")
            f.write(cubin_inc)
            f.write("};\nsize_t cudakernel_modulesize = %i;\n" % len(cubin))
            f.close()
        print "Building modules..."
        build_ext.run(self)


class GPUCleaner(clean):
    def _unlink(self, node):
        try:
            if os.path.isdir(node):
                os.rmdir(node)
            else:
                os.unlink(node)
        except OSError:
            pass
    
    def run(self):
        print "Removing temporary files and pre-built GPU-kernels..."
        try:
            for f in ('_cpyrit_cudakernel.linkinfo', '_cpyrit_cudakernel.cubin', '_cpyrit_cudakernel.cubin.h'):
                self._unlink(f)
        except Exception, (errno, sterrno):
            print >>sys.stderr, "Exception while cleaning temporary files ('%s')" % sterrno
        clean.run(self)


cuda_extension = Extension('cpyrit._cpyrit_cuda',
                    libraries = ['ssl', 'cuda', 'z'],
                    sources = ['_cpyrit_cuda.c'],
                    include_dirs = NVIDIA_INC_DIRS,
                    extra_compile_args = EXTRA_COMPILE_ARGS)

setup_args = dict(
        name = 'CPyrit-CUDA',
        version = '0.2.4',
        description = 'GPU-accelerated attack against WPA-PSK authentication',
        license = 'GNU General Public License v3',
        author = 'Lukas Lueg',
        author_email = 'lukas.lueg@gmail.com',
        url = 'http://pyrit.googlecode.com',
        ext_modules = [cuda_extension],
        cmdclass = {'build_ext':GPUBuilder, 'clean':GPUCleaner},
        options = {'install':{'optimize':1},'bdist_rpm':{'requires':'Pyrit = 0.2.4-1'}}
        )
        
if __name__ == "__main__":
    setup(**setup_args)
