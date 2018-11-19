import os
import uuid
import copy
import json
import logging


log = logging.getLogger(__name__)

from .kubesubmitmixin import SubmitToKubeMixin
from kubernetes import client, config

class KubernetesBackend_Direct(SubmitToKubeMixin):
    def __init__(self,
                 resultstore,
                 kubeconfig = None,
                 stateopts = None,
                 resources_opts = None,
                 resource_labels = None,
                 svcaccount = 'default',
                 namespace = 'default',
                 ):
        self.svcaccount = svcaccount

        self.namespace  = namespace
        kwargs = {
            'namespace': namespace,
            'kubeconfig': kubeconfig,
        }
        SubmitToKubeMixin.__init__(self, **kwargs)

    def determine_readiness(self, job_proxy):
        raise RuntimeError

    def plan_kube_resources(self, jobspec):
        kube_resources = []

        
        containers = None
        volumes = None
        jobname = None

        kube_resources.append({
          "apiVersion": "batch/v1",
          "kind": "Job",
          "spec": {
            "backoffLimit": 0,
            "template": {
              "spec": {
                "restartPolicy": "Never",
                "securityContext" : {
                    "runAsUser": 0
                },
                "containers": containers,
                "volumes": volumes
              },
              "metadata": { "name": jobname }
            }
          },
          "metadata": { "name": jobname }
        })

        return {
            'resultjson': resultfilename,
            'job_id': jobname,
            'resources': kube_resources
        }, kube_resources

