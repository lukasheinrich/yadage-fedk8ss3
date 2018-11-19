import logging
import uuid
from six import string_types
import os
import copy
import glob2

import yadageobjstore.known_types
from packtivity.utils import leaf_iterator
from packtivity.typedleafs import TypedLeafs

log = logging.getLogger(__name__)


def interpolated_pub_handler(publisher,parameters,state):
    workdir = state.local_workdir
    forinterp = {}

    for p, v in parameters.leafs():
        if isinstance(v, yadageobjstore.known_types.SimpleFile):
            continue
        p.set(forinterp,v)

    log.info('interpolation dict: %s', forinterp)

    result = copy.deepcopy(publisher['publish'])

    for path,value in leaf_iterator(publisher['publish']):
        if not isinstance(value, string_types):
            continue
        resultval = value.format(**forinterp)
        resultval = resultval.format(workdir = workdir)
        globexpr = resultval
        log.info('value: %s  | expression %s', value, globexpr)
        if publisher['relative_paths'] and os.path.commonprefix([workdir,globexpr]) == '':
            globexpr = os.path.join(workdir,resultval)

        if publisher['glob']:
            globbed = glob2.glob(globexpr)
            if globbed:
                resultval = [yadageobjstore.known_types.SimpleFile(local_path = p) for p in globbed]
        else:
             #if it's a string and the full path exists replace relative path
             resultval = yadageobjstore.known_types.SimpleFile(local_path = globexpr)
        log.info('result value: %s', resultval)
        path.set(result,resultval)
    log.info('returning result: %s', result)
    return TypedLeafs(result, state.datamodel)

def fromparpub_handler(spec,parameters,state):
    topublish = {}
    for targetname, sourcename in spec['outputmap'].items():
        value = parameters[sourcename]
        if type(value) == yadageobjstore.known_types.SimpleFile:
            value.local_path = value.local_path.format(workdir = state.local_workdir)
        topublish[targetname] = value
    return TypedLeafs(topublish, state.datamodel)

def upload_spec(fileobj, state):
    global_path = 'global-'+str(uuid.uuid4())
    fileobj.path = global_path
    return {
        'source': fileobj.local_path, 'target': fileobj.path
    }

def teardown_spec(topublish,state):
    teardown_spec = {'uploads': []}
    for p,value in topublish.leafs():
        if type(value) == yadageobjstore.known_types.SimpleFile:
            if not value.path:
                log.info('this has no public path, so we need to upload it %s', value.json())
                teardown_spec['uploads'].append(upload_spec(value, state))
            topublish.replace(p,TypedLeafs(value,state.datamodel).json())

    log.info('topublish:\n%s',topublish.json())
    return teardown_spec

def publish(spec, parameters, state):
    assert spec['publisher_type'] in ['frompar-pub','interpolated-pub']

    if spec['publisher_type'] == 'interpolated-pub':
        topublish = interpolated_pub_handler(spec,parameters,state)

    if spec['publisher_type'] == 'frompar-pub':
        topublish = fromparpub_handler(spec,parameters,state)

    assert topublish
    teardown = teardown_spec(topublish,state)
    return teardown, topublish.json()
