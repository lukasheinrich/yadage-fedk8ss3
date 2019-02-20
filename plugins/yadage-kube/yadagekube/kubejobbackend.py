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

        self.ydgconfig =  {
          "resultstorage": kwargs['resultstore']
        }
    
    def determine_readiness(self, job_proxy):
        ready = job_proxy.get('ready',False)
        if ready:
            return True

        log.info('actually checking job %s', job_proxy['job_id'])

        job_id  = job_proxy['job_id']
        jobstatus = self.check_k8s_job_status(job_id)
        job_proxy['last_success'] = jobstatus.succeeded
        job_proxy['last_failed']  = jobstatus.failed
        ready =  job_proxy['last_success'] or job_proxy['last_failed']
        if ready:
            log.info('job %s is ready and successful. success: %s failed: %s', job_id,
                job_proxy['last_success'], job_proxy['last_failed']
            )
        return ready

    def state_mounts_and_vols(self, jobspec):
        return [
            { "name": "comms-volume",   "mountPath": jobspec['sequence_spec']['config_mounts']['comms'] },
            { "name": "workdir-volume", "mountPath": jobspec['local_workdir'] }
        ], [
            { "name": "workdir-volume", "emptyDir": {} },
            { "name": "comms-volume",   "emptyDir": {} }
        ]

    def config(self, configname, jobspec):
        resources, vols, mounts = [], [], []
        resources.append({
          "apiVersion": "v1",
          "kind": "ConfigMap",
          "data": {
            "ydgconfig.json": json.dumps(self.ydgconfig),
            "jobconfig.json": json.dumps(jobspec)
          },
          "metadata": {
            "name": configname
          }
        })
        configvols, configmounts = [
            {"name": "job-config", "configMap": { "name":  configname}}], [{
            "name": "job-config",
            "mountPath": jobspec['sequence_spec']['config_mounts']['jobconfig']
        }]
        return resources, vols, mounts

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

        #---
        jobconfigname = "wflow-job-config-{}".format(job_uuid)
        resultfilename = 'result-{}.json'.format(job_uuid)

        jobconfig = copy.deepcopy(jobspec)
        jobconfig['resultfile'] = resultfilename

        config_resources, config_vols, config_mounts = self.config(jobconfigname, jobspec)
        kube_resources += config_resources
        volumes = volumes + config_vols
        #---

        container_sequence = self.container_sequence_fromspec(
            sequence_spec, mainmounts = container_mounts, configmounts = config_mounts
        )


        jobspec = self.get_job_spec_for_sequence(jobname,
            sequence = container_sequence,
            volumes = volumes
        )
        kube_resources.append(jobspec)
        proxy_data = {
            'resultjson': resultfilename,
            'job_id': jobname,
            'resources': kube_resources
        }
        return proxy_data, kube_resources
