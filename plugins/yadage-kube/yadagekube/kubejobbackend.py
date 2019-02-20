import copy
import json
import logging

from .kubesubmitmixin import SubmitToKubeMixin
from .kubespecmixin import KubeSpecMixin

log = logging.getLogger(__name__)

class KubernetesBackend(SubmitToKubeMixin,KubeSpecMixin):
    def __init__(self,**kwargs):
        SubmitToKubeMixin.__init__(self, **kwargs)
        KubeSpecMixin.__init__(self,**kwargs)

        self.ydgconfig =  {
          "resultstorage": kwargs['resultstore']
        }
    
    def state_mounts_and_vols(self, jobspec):
        return [
            { "name": "comms-volume",   "mountPath": jobspec['sequence_spec']['config_mounts']['comms'] },
            { "name": "workdir-volume", "mountPath": jobspec['local_workdir'] }
        ], [
            { "name": "workdir-volume", "emptyDir": {} },
            { "name": "comms-volume",   "emptyDir": {} }
        ]

    def proxy_data(self, job_uuid, kube_resources):
        jobname = "wflow-job-{}".format(job_uuid)
        resultfilename = 'result-{}.json'.format(job_uuid)
        return {
            'resultjson': resultfilename,
            'job_id': jobname,
            'resources': kube_resources
        }

    def config(self, job_uuid, jobspec):
        jobconfigname = "wflow-job-config-{}".format(job_uuid)
        resultfilename = 'result-{}.json'.format(job_uuid)
        jobspec = copy.deepcopy(jobspec)
        jobspec['resultfile'] = resultfilename

        resources, vols, mounts = [], [], []
        resources.append(self.get_cm_spec(
            jobconfigname, {
            "ydgconfig.json": json.dumps(self.ydgconfig),
            "jobconfig.json": json.dumps(jobspec)
          }
        ))
        configvols, configmounts = [
            {"name": "job-config", "configMap": { "name":  jobconfigname}}], [{
            "name": "job-config",
            "mountPath": jobspec['sequence_spec']['config_mounts']['jobconfig']
        }]
        vols += configvols
        mounts += configmounts
        return resources, vols, mounts
