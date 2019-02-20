import os
import uuid
import copy
import json
import logging

from .kubesubmitmixin import SubmitToKubeMixin
from .kubespecmixin import KubeSpecMixin

log = logging.getLogger(__name__)

class KubernetesBackend(SubmitToKubeMixin,KubeSpecMixin):
    def __init__(self,**kwargs):
        self.svcaccount = kwargs.get('svcaccount','default')

        kwargs.setdefault('namespace','default')
        SubmitToKubeMixin.__init__(self, **kwargs)
        KubeSpecMixin.__init__(self,**kwargs)

        self.specopts   = {'type': 'single_ctr_job'}
        self.resource_labels = kwargs.get('resource_labels',{'component': 'yadage'})
        self.resources_opts = kwargs.get('resource_opts',{
            'requests': {
                'memory': "0.1Gi",
                'cpu': "100m"
            }
        })
        self.cvmfs_repos = ['atlas.cern.ch','sft.cern.ch','atlas-condb.cern.ch']

        self.base = kwargs.get('path_base','')
        self.claim_name =  kwargs.get('claim_name','yadagedata')

    def determine_readiness(self, job_proxy):
        ready = job_proxy.get('ready',False)
        if ready:
            return True

        log.debug('actually checking job %s', job_proxy['job_id'])

        job_id  = job_proxy['job_id']
        jobstatus = self.check_k8s_job_status(job_id)
        job_proxy['last_success'] = jobstatus.succeeded
        job_proxy['last_failed']  = jobstatus.failed
        ready =  job_proxy['last_success'] or job_proxy['last_failed']
        if ready:
            log.debug('job %s is ready and successful. success: %s failed: %s', job_id,
                job_proxy['last_success'], job_proxy['last_failed']
            )
        return ready

    def state_mounts_and_vols(self, jobspec):
        container_mounts_state, volumes_state = [],[]
        for i,ro in enumerate(jobspec['state']['readonly']):
            subpath = ro.replace(self.base,'')   
            ctrmnt = {
                "name": "state",
                "mountPath": ro,
                "subPath": subpath,
            }
            container_mounts_state.append(ctrmnt)

        for i,rw in enumerate(jobspec['state']['readwrite']):
            subpath = rw.replace(self.base,'')   
            ctrmnt = {
                "name": "state",
                "mountPath": rw,
                "subPath": subpath,
            }
            container_mounts_state.append(ctrmnt)

        volumes_state.append({
            "name": "state",
            "persistentVolumeClaim": {
                "claimName": self.claim_name,
                "readOnly": False
            }
        })
        return container_mounts_state, volumes_state

    def plan_kube_resources(self, jobspec):
        job_uuid = str(uuid.uuid4())

        kube_resources = []

        env           = jobspec['spec']['environment']
        cvmfs         = 'CVMFS' in env['resources']
        parmounts     = env['par_mounts']
        auth          = 'GRIDProxy' in env['resources']
        sequence_spec = jobspec['sequence_spec']

        container_mounts, volumes = [], []

        container_mounts_state, volumes_state = self.state_mounts_and_vols(jobspec)

        container_mounts += container_mounts_state
        volumes          += volumes_state

        resources, mounts, vols = self.get_job_mounts(cvmfs, auth, parmounts)
        container_mounts += mounts
        volumes += vols
        kube_resources += resources

        jobname = "wflow-job-{}".format(job_uuid)
        config_mounts = []

        container_sequence = self.container_sequence_fromspec(
            sequence_spec, mainmounts = container_mounts, configmounts = config_mounts
        )
        
        jobspec = self.get_job_spec_for_sequence(jobname,
            sequence = container_sequence,
            volumes = volumes
        )
        kube_resources.append(jobspec)

        log.debug(json.dumps(kube_resources, indent = 4))
        proxy_data = {
            'job_id': jobname,
            'resources': kube_resources
        }
        return proxy_data, kube_resources
