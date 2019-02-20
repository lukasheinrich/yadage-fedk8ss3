import logging
import copy
import json
import os
import json
import logging
import uuid
import copy

from packtivity.syncbackends import build_job, packconfig, build_env
from packtivity.syncbackends import finalize_inputs, acquire_job_env, packconfig

log = logging.getLogger(__name__)

class JobSequenceMakerMixin(object):
    def __init__(self, **kwargs):
        pass

    def render_process(self, spec, local_pars):
        log.info('param object %s', local_pars)
        log.info('local pars: \n%s',json.dumps(local_pars.json(), indent=4))
        log.info('rendering process with local pars:  {}'.format(local_pars.json()))

        job = build_job(spec, local_pars, None, packconfig())
        log.info(job)

        script = '''cat << 'RECASTJOB' | {}\n{}\RECASTJOB\n'''
        return {
            'command': job['command'] if 'command' in job else script.format(
                job['interpreter'],
                job['script'])
        }

    def make_external_job(self, spec,parameters, state, metadata):
        spec      = copy.deepcopy(spec)
        parcopy   = copy.deepcopy(parameters)
        jsonpars  = copy.deepcopy(parcopy.json())

        setup_spec, local_pars = state.make_local_pars(parcopy)
        spec['environment'] = build_env(spec['environment'], local_pars, state, packconfig())

        rendered_process = self.render_process(spec['process'], local_pars)

        sequence = {
            'sequence': ['setup', 'payload', 'teardown'],
            'setup': {
                'iscfg': True,
                'cmd':  ["/code/datamgmt/stage_in.py", "/jobconfig/jobconfig.json","/comms/script.sh"],
                'image': 'lukasheinrich/datamgmt'
            },
            'payload': {
                'iscfg': False,
                'cmd': ["sh", "/comms/script.sh"],
                'image': ':'.join([
                    spec['environment']['image'],
                    spec['environment']['imagetag']
                ])
            },
            'teardown': {
                'iscfg': True,
                'cmd': ["/code/datamgmt/stage_out.py","/jobconfig/jobconfig.json"],
                'image': 'lukasheinrich/datamgmt'
            },
            'config_mounts': {
                'comms': '/comms',
                'jobconfig': '/jobconfig'
            },
            'config_env': [{
                "name": "YDGCONFIG",
                "value": "/jobconfig/ydgconfig.json",
            }]
        }

        jobspec = {
            "sequence_spec": sequence,
            "publisher_spec": spec['publisher'],
            "rendered_process": rendered_process,
            "setup_spec": setup_spec,
            "local_workdir": state.local_workdir,
            "local_pars": local_pars.json(),
            #... 
            "parameters": jsonpars,
            "spec": spec,
            "state": state.json(),
        }

        log.info('parspec spec\n%s',json.dumps(jobspec['parameters'], indent=4))
        log.info('job spec\n%s',json.dumps(jobspec, indent=4))
        return jobspec


class DirectJobMakerMixin(object):
    def __init__(self, **kwargs):
        pass

    def render_process(self, spec, state, metadata, local_pars):
        log.debug('param object %s', local_pars)
        log.debug('local pars: \n%s',json.dumps(local_pars.json(), indent=4))
        log.debug('rendering process with local pars:  {}'.format(local_pars.json()))

        job, env = acquire_job_env(spec, local_pars,state,metadata,packconfig())
        script = '''cat << 'RECASTJOB' | {}\n{}\nRECASTJOB\n'''
        return {
            'command': job['command'] if 'command' in job else script.format(
                job['interpreter'],
                job['script']),
            'env': env
        }

    def make_external_job(self, spec,parameters, state, metadata):
        pack_config = packconfig()

        spec      = copy.deepcopy(spec)
        parcopy   = copy.deepcopy(parameters)
        jsonpars  = copy.deepcopy(parcopy.json())


        parameters, state = finalize_inputs(parameters, state)
        rendered_process = self.render_process(spec, state, metadata, parameters)

        return {
            "sequence_spec": {
                'sequence': ['payload'],
                "payload": {
                        'cmd': ["sh","-c",rendered_process["command"]],
                        'iscfg': False,
                        'image': ':'.join([
                            rendered_process['env']['image'],
                            rendered_process['env']['imagetag']
                        ])
                },
            },
            #....
            "spec": spec,
            "state": state.json(),
        }

