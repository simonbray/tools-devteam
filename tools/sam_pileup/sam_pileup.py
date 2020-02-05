#!/usr/bin/env python

"""
Creates a pileup file from a bam file and a reference.

usage: %prog [options]
   -p, --input1=p: bam file
   -o, --output1=o: Output pileup
   -R, --ref=R: Reference file type
   -n, --ownFile=n: User-supplied fasta reference file
   -b, --bamIndex=b: BAM index file
   -g, --index=g: Path of the indexed reference genome
   -s, --lastCol=s: Print the mapping quality as the last column
   -i, --indels=i: Only output lines containing indels
   -M, --mapCap=M: Cap mapping quality
   -c, --consensus=c: Call the consensus sequence using MAQ consensu model
   -T, --theta=T: Theta paramter (error dependency coefficient)
   -N, --hapNum=N: Number of haplotypes in sample
   -r, --fraction=r: Expected fraction of differences between a pair of haplotypes
   -I, --phredProb=I: Phred probability of an indel in sequencing/prep

"""

import os
import shutil
import subprocess
import sys
import tempfile
from bx.cookbook import doc_optparse


def stop_err(msg, e=None):
    if e is not None:
        raise e
    sys.exit('%s\n' % msg)


def __main__():
    # Parse Command Line
    options, args = doc_optparse.parse(__doc__)
    # output version # of tool
    try:
        tmp = tempfile.NamedTemporaryFile().name
        tmp_stdout = open(tmp, 'wb')
        proc = subprocess.Popen(args='samtools 2>&1', shell=True, stdout=tmp_stdout)
        tmp_stdout.close()
        returncode = proc.wait()
        stdout = None
        for line in open(tmp_stdout.name, 'rb'):
            if line.lower().find('version') >= 0:
                stdout = line.strip()
                break
        if stdout:
            sys.stdout.write('Samtools %s\n' % stdout)
        else:
            raise Exception
    except Exception:
        sys.stdout.write('Could not determine Samtools version\n')
    # prepare file names
    tmpDir = tempfile.mkdtemp()
    tmpf0 = tempfile.NamedTemporaryFile(dir=tmpDir)
    tmpf0_name = tmpf0.name
    tmpf0.close()
    tmpf0bam_name = '%s.bam' % tmpf0_name
    tmpf0bambai_name = '%s.bam.bai' % tmpf0_name
    tmpf1 = tempfile.NamedTemporaryFile(dir=tmpDir)
    tmpf1_name = tmpf1.name
    tmpf1.close()
    # link bam and bam index to working directory (can't move because need to leave original)
    os.symlink(options.input1, tmpf0bam_name)
    os.symlink(options.bamIndex, tmpf0bambai_name)
    # get parameters for pileup command
    if options.lastCol == 'yes':
        lastCol = '-s'
    else:
        lastCol = ''
    if options.indels == 'yes':
        indels = '-i'
    else:
        indels = ''
    opts = '%s %s -M %s' % (lastCol, indels, options.mapCap)
    if options.consensus == 'yes':
        opts += ' -c -T %s -N %s -r %s -I %s' % (options.theta, options.hapNum, options.fraction, options.phredProb)
    # prepare basic pileup command
    cmd = 'samtools pileup %s -f %s %s > %s'
    try:
        # have to nest try-except in try-finally to handle 2.4
        try:
            # index reference if necessary and prepare pileup command
            if options.ref == 'indexed':
                if not os.path.exists("%s.fai" % options.index):
                    raise Exception("Indexed genome %s not present, request it by reporting this error." % options.index)
                cmd = cmd % (opts, options.index, tmpf0bam_name, options.output1)
            elif options.ref == 'history':
                os.symlink(options.ownFile, tmpf1_name)
                cmdIndex = 'samtools faidx %s' % (tmpf1_name)
                tmp = tempfile.NamedTemporaryFile(dir=tmpDir).name
                tmp_stderr = open(tmp, 'wb')
                proc = subprocess.Popen(args=cmdIndex, shell=True, cwd=tmpDir, stderr=tmp_stderr.fileno())
                returncode = proc.wait()
                tmp_stderr.close()
                # get stderr, allowing for case where it's very large
                tmp_stderr = open(tmp, 'rb')
                stderr = ''
                buffsize = 1048576
                try:
                    while True:
                        stderr += tmp_stderr.read(buffsize)
                        if not stderr or len(stderr) % buffsize != 0:
                            break
                except OverflowError:
                    pass
                tmp_stderr.close()
                # did index succeed?
                if returncode != 0:
                    raise Exception('Error creating index file\n' + stderr)
                cmd = cmd % (opts, tmpf1_name, tmpf0bam_name, options.output1)
            # perform pileup command
            tmp = tempfile.NamedTemporaryFile(dir=tmpDir).name
            tmp_stderr = open(tmp, 'wb')
            proc = subprocess.Popen(args=cmd, shell=True, cwd=tmpDir, stderr=tmp_stderr.fileno())
            returncode = proc.wait()
            tmp_stderr.close()
            # did it succeed?
            # get stderr, allowing for case where it's very large
            tmp_stderr = open(tmp, 'rb')
            stderr = ''
            buffsize = 1048576
            try:
                while True:
                    stderr += tmp_stderr.read(buffsize)
                    if not stderr or len(stderr) % buffsize != 0:
                        break
            except OverflowError:
                pass
            tmp_stderr.close()
            if returncode != 0:
                raise Exception(stderr)
        except Exception as e:
            stop_err('Error running Samtools pileup tool', e)
    finally:
        # clean up temp files
        if os.path.exists(tmpDir):
            shutil.rmtree(tmpDir)
    # check that there are results in the output file
    if os.path.getsize(options.output1) > 0:
        sys.stdout.write('Converted BAM to pileup')
    else:
        stop_err('The output file is empty. Your input file may have had no matches, or there may be an error with your input file or settings.')


if __name__ == "__main__":
    __main__()
