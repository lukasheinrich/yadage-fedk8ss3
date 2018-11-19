#!/usr/bin/env python

import logging
import json
import sys
import os
import tempfile
from minio import Minio

from yadageobjstore.localfs_publicobjects import LocalFSGlobalObjectsState
from packtivity.typedleafs import TypedLeafs
from datamgmt.publish import publish

log = logging.getLogger('==== packtivity stageout ====')

logging.basicConfig(level = logging.INFO)

def main():
    submissionspec = sys.argv[1]
    log.info('staging out data according to specfile %s', submissionspec)
    subdata = json.load(open(submissionspec))
    pubspec    = subdata['publisher_spec']
    parameters = subdata['parameters']
    state      = subdata['state']
    resultfile = subdata['resultfile']

    log.info('pub:  \n'+json.dumps(pubspec, indent=4))
    log.info('pars: \n'+json.dumps(parameters, indent=4))
    log.info('stat: \n'+json.dumps(state, indent=4))

    ydgconfig = json.load(open(os.environ.get('YDGCONFIG','ydgconfig.json')))

    state = LocalFSGlobalObjectsState.fromJSON(state)
    parameters = TypedLeafs(parameters, state.datamodel)

    teardown_spec, pubdata = publish(pubspec, parameters, state)

    for upload in teardown_spec['uploads']:
        state.put_file(upload['source'],upload['target'])

    with open('result.json','wb') as fl:
        fl.write(json.dumps(pubdata).encode('utf-8'))

    client = Minio(
        ydgconfig['resultstorage']['host'],
        access_key = ydgconfig['resultstorage']['access_key'],
        secret_key = ydgconfig['resultstorage']['secret_key'],
        secure = True
    )
    client.fput_object(ydgconfig['resultstorage']['bucket'],resultfile,'result.json')
    log.info('writing result data to: %s',resultfile)

if __name__ == '__main__':
    main()
