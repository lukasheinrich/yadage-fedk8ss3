#!/usr/bin/env python

import logging
import json
import sys
import time

import yadageobjstore.register_packtivity
from packtivity.statecontexts import load_state

log = logging.getLogger('==== packtivity stagein ====')

logging.basicConfig(level = logging.INFO)

def main():
    submissionspec = sys.argv[1]
    payloadscript  = sys.argv[2]
    log.info('staging in data according to specfile %s', submissionspec)

    subdata             = json.load(open(submissionspec))
    setup_spec          = subdata['setup_spec']
    state               = subdata['state']
    rendered_process    = subdata['rendered_process']

    log.info('stat: \n'+json.dumps(state, indent=4))

    state = load_state(state)

    for acq in setup_spec['acquisitions']:
        state.get_file(acq['target'], acq['source'])

    log.info('required acqs:\n%s', json.dumps(setup_spec['acquisitions']))
    log.info('the script is:\n{}'.format(rendered_process['command']))

    log.info('writing payload script to: %s', payloadscript)
    with open(payloadscript,'w') as f:
        f.write(rendered_process['command'])

if __name__ == '__main__':
    main()
