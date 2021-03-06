#!/usr/bin/env python3

import sys
import os
import re
import json
import traceback
import pkg_resources

import anchore_engine.analyzers.utils

analyzer_name = "package_list"

py_library_file = ".*(\.(py|pyc|pyo)|(dist-info|egg-info))$"

try:
    config = anchore_engine.analyzers.utils.init_analyzer_cmdline(sys.argv, analyzer_name)
except Exception as err:
    print(str(err))
    sys.exit(1)

imgname = config['imgid']
imgid = config['imgid_full']
outputdir = config['dirs']['outputdir']
unpackdir = config['dirs']['unpackdir']
squashtar = os.path.join(unpackdir, "squashed.tar")

resultlist = {}
try:
    allfiles = {}
    if os.path.exists(unpackdir + "/anchore_allfiles.json"):
        with open(unpackdir + "/anchore_allfiles.json", 'r') as FH:
            allfiles = json.loads(FH.read())
    else:
        #fmap, allfiles = anchore_engine.analyzers.utils.get_files_from_path(unpackdir + "/rootfs")
        fmap, allfiles = anchore_engine.analyzers.utils.get_files_from_squashtar(os.path.join(unpackdir, "squashed.tar"), inpath=os.path.join(unpackdir, "rootfs"))
        with open(unpackdir + "/anchore_allfiles.json", 'w') as OFH:
            OFH.write(json.dumps(allfiles))

    pythondbdir = anchore_engine.analyzers.utils.python_prepdb_from_squashtar(unpackdir, squashtar, py_library_file)

    for f in list(allfiles.keys()):
        if allfiles[f]['type'] == 'dir':
            candidate = '/'.join([pythondbdir, f])
            distributions = pkg_resources.find_distributions(candidate)
            for distribution in distributions:
                el = {}
                try:
                    el['name'] = distribution.project_name
                    el['version'] = distribution.version
                    el['type'] = 'python'

                    #prefix = '/'.join([unpackdir, 'rootfs'])
                    el['location'] = f #re.sub("^/*"+prefix+"/*", "/", candidate)

                    # extract file info if available
                    el['files'] = []
                    try:
                        record = distribution.get_metadata('RECORD')
                        for line in record.splitlines():
                            pfile, other = line.split(",", 1)
                            el['files'].append('/'.join([el['location'], pfile]))
                    except:
                        pass

                    # extract metadata if available
                    el['license'] = 'N/A'
                    el['metadata'] = 'N/A'
                    el['origin'] = 'N/A'
                    try:
                        el['metadata'] = distribution.get_metadata(distribution.PKG_INFO)
                        for line in el['metadata'].splitlines():
                            k = v = None
                            try:
                                k, v = line.split(": ", 1)
                            except:
                                pass
                            if k and v:
                                if k == 'License':
                                    el['license'] = v
                                elif k == 'Author':
                                    author = v
                                elif k == 'Author-email':
                                    author_email = v
                        try:
                            el['origin'] = author + " <" + author_email +">"
                        except:
                            pass
                    except:
                        pass

                except Exception as err:
                    traceback.print_exc()
                    print("WARN: could not extract information about python module from distribution - exception: " + str(err))
                    el = {}

                if el:
                    resultlist[el['location'] + "/" + el['name']] = json.dumps(el)

except Exception as err:
    import traceback
    traceback.print_exc()
    print("WARN: analyzer unable to complete - exception: " + str(err))

if resultlist:
    ofile = os.path.join(outputdir, 'pkgs.python')
    anchore_engine.analyzers.utils.write_kvfile_fromdict(ofile, resultlist)

sys.exit(0)
