import os
import uuid
import copy
import json
import logging

from kubernetes import client, config
from .kubesubmitmixin import SubmitToKubeMixin

log = logging.getLogger(__name__)

class KubernetesBackend(SubmitToKubeMixin):
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

        self.stateopts  = stateopts or {'type': 'hostpath'}
        self.specopts   = {'type': 'single_ctr_job'}
        self.resource_labels = resource_labels or {'component': 'yadage'}
        self.resources_opts = resources_opts or {
            'requests': {
                'memory': "0.1Gi",
                'cpu': "100m"
            }
        }
        self.ydgconfig =  {
          "resultstorage": resultstore
        }
        self.cvmfs_repos = ['atlas.cern.ch','sft.cern.ch','atlas-condb.cern.ch']


    def create_kube_resources(self, resources):
        for r in resources:
            if r['kind'] == 'Job':
                thejob = client.V1Job(
                    kind        = r['kind'],
                    api_version = r['apiVersion'],
                    metadata    = r['metadata'],
                    spec        = r['spec']
                )
                client.BatchV1Api().create_namespaced_job(self.namespace,thejob)
                log.info('created job %s', r['metadata']['name'])
            elif r['kind'] == 'ConfigMap':
                cm = client.V1ConfigMap(
                    api_version = 'v1',
                    kind = r['kind'],
                    metadata = {'name': r['metadata']['name'], 'namespace': self.namespace, 'labels': self.resource_labels},
                    data = r['data']
                )
                client.CoreV1Api().create_namespaced_config_map(self.namespace,cm)
                log.info('created configmap %s', r['metadata']['name'])


    def determine_readiness(self, job_proxy):
        ready = job_proxy.get('ready',False)
        if ready:
            return True

        log.info('actually checking job %s', job_proxy['job_id'])

        job_id  = job_proxy['job_id']
        jobstatus = client.BatchV1Api().read_namespaced_job(job_id,self.namespace).status
        job_proxy['last_success'] = jobstatus.succeeded
        job_proxy['last_failed']  = jobstatus.failed
        ready =  job_proxy['last_success'] or job_proxy['last_failed']
        if ready:
            log.info('job %s is ready and successful. success: %s failed: %s', job_id,
                job_proxy['last_success'], job_proxy['last_failed']
            )
        return ready

    def successful(self,job_proxy):
        return job_proxy['last_success']

    def fail_info(self,resultproxy):
        pass

    def auth_binds(self,authmount):
        container_mounts = []
        volumes = []

        log.debug('binding auth')
        volumes.append({
            'name': 'hepauth',
            'secret': yaml.load(open('secret.yml'))
        })
        container_mounts.append({
            "name": 'hepauth',
            "mountPath": authmount
        })
        return container_mounts, volumes

    def cvmfs_binds(self, repos):
        container_mounts = []
        volumes = []
        log.debug('binding CVMFS')
        for repo in repos:
            reponame = repo.replace('.','').replace('-','')
            volumes.append({
                'name': reponame,
                'flexVolume': {
                'driver': "cern/cvmfs",
                    'options': {
                        'repository': repo
                    }
                }
            })
            container_mounts.append({
                "name": reponame,
                "mountPath": '/cvmfs/'+repo
            })
        return container_mounts, volumes

    def make_par_mount(self, job_uuid, parmounts):
        parmount_configmap_contmount = []
        configmapspec = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': 'parmount-{}'.format(job_uuid)},
            'data': {}
        }

        vols_by_dir_name = {}
        for i,x in enumerate(parmounts):
            configkey = 'parmount_{}'.format(i)
            configmapspec['data'][configkey] = x['mountcontent']

            dirname  = os.path.dirname(x['mountpath'])
            basename = os.path.basename(x['mountpath'])

            vols_by_dir_name.setdefault(dirname,{
                'name': 'vol-{}'.format(dirname.replace('/','-')),
                'configMap': {
                    'name': configmapspec['metadata']['name'],
                    'items': []
                }
            })['configMap']['items'].append({
                'key': configkey, 'path': basename
            })

        log.debug(vols_by_dir_name)

        for dirname,volspec in vols_by_dir_name.items():
            parmount_configmap_contmount.append({
                'name': volspec['name'],
                'mountPath':  dirname
            })
        return parmount_configmap_contmount, vols_by_dir_name.values(), configmapspec

    def plan_kube_resources(self, jobspec):
        job_uuid = str(uuid.uuid4())

        kube_resources = []

        env           = jobspec['spec']['environment']
        cvmfs         = 'CVMFS' in env['resources']
        parmounts     = env['par_mounts']
        auth          = 'GRIProxy' in env['resources']
        sequence_spec = jobspec['sequence_spec']

        container_mounts, volumes = [], []

        container_mounts_state, volumes_state = [
            { "name": "comms-volume",   "mountPath": sequence_spec['config_mounts']['comms'] },
            { "name": "workdir-volume", "mountPath": jobspec['local_workdir'] }
        ], [
            { "name": "workdir-volume", "emptyDir": {} },
            { "name": "comms-volume",   "emptyDir": {} }
        ]

        container_mounts += container_mounts_state
        volumes          += volumes_state

        if cvmfs:
            container_mounts_cvmfs, volumes_cvmfs = self.cvmfs_binds(self.cvmfs_repos)
            container_mounts += container_mounts_cvmfs
            volumes          += volumes_cvmfs

        if auth:
            container_mounts_auth, volumes_auth = self.auth_binds('/recast_auth')
            container_mounts += container_mounts_auth
            volumes          += volumes_auth

        if parmounts:
            container_mounts_pm, volumes_pm, pm_cm_spec = self.make_par_mount(job_uuid, parmounts)
            container_mounts += container_mounts_pm
            volumes += volumes_pm
            kube_resources.append(pm_cm_spec)


        jobconfigname = "wflow-job-config-{}".format(job_uuid)
        jobname = "wflow-job-{}".format(job_uuid)
        resultfilename = 'result-{}.json'.format(job_uuid)

        jobconfig = copy.deepcopy(jobspec)
        jobconfig['resultfile'] = resultfilename

        kube_resources.append({
          "apiVersion": "v1",
          "kind": "ConfigMap",
          "data": {
            "ydgconfig.json": json.dumps(self.ydgconfig),
            "jobconfig.json": json.dumps(jobconfig)
          },
          "metadata": {
            "name": jobconfigname
          }
        })

        configmounts = [{
            "name": "job-config",
            "mountPath": sequence_spec['config_mounts']['jobconfig']
        }]

        container_sequence = [{
          "name": seqname,
          "image": sequence_spec[seqname]['image'],
          "command": sequence_spec[seqname]['cmd'],
          "env": sequence_spec['config_env'] if sequence_spec[seqname]['iscfg'] else [],
          "volumeMounts":  container_mounts + (configmounts if sequence_spec[seqname]['iscfg'] else [])
        } for seqname in sequence_spec['sequence']]

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
                "initContainers": container_sequence[:-1],
                "containers": container_sequence[-1:],
                "volumes": [{
                    "name": "job-config",
                    "configMap": { "name": jobconfigname },
                }] + volumes
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
