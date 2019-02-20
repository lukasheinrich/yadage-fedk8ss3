import os
from kubernetes import client, config
import logging

log = logging.getLogger(__name__)

class SubmitToKubeMixin(object):
    def __init__(self, **kwargs):
        self.namespace = kwargs['namespace']
        if kwargs.get('kubeconfig') == 'incluster':
            log.info('load incluster config')
            config.load_incluster_config()
        else:
            cfg = kwargs.get('kubeconfig')
            log.info('load config %s', cfg)
            if not cfg:
                config.load_kube_config()
            else:
                config.load_kube_config(cfg)
            import urllib3
            urllib3.disable_warnings()

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

    def delete_created_resources(self, resources):
        for r in resources:
            if r['kind'] == 'Job':
                resource_name = r['metadata']['name']
                try:
                    j = client.BatchV1Api().read_namespaced_job(resource_name,self.namespace)
                    client.BatchV1Api().delete_namespaced_job(resource_name,self.namespace,j.spec)
                except client.rest.ApiException:
                    pass

                try:
                    client.CoreV1Api().delete_collection_namespaced_pod(self.namespace, label_selector = 'job-name={}'.format(resource_name))
                except client.rest.ApiException:
                    pass

            elif r['kind'] == 'ConfigMap':
                resource_name = r['metadata']['name']
                try:
                    client.CoreV1Api().delete_namespaced_config_map(resource_name,self.namespace,client.V1DeleteOptions())
                except client.rest.ApiException:
                    pass

    def submit(self, jobspec):
        proxy_data, kube_resources = self.plan_kube_resources(jobspec)
        self.create_kube_resources(kube_resources)
        return proxy_data

    def ready(self, job_proxy):
        ready = self.determine_readiness(job_proxy)
        if ready and not 'ready' in job_proxy:
            log.debug('is first time ready %s', job_proxy['job_id'])
            job_proxy['ready'] = ready
            if job_proxy['last_success']:
                log.debug('is first success %s delete resources', job_proxy['job_id'])
                self.delete_created_resources(job_proxy['resources'])
        return ready

    def successful(self,job_proxy):
        return job_proxy['last_success']

    def fail_info(self,resultproxy):
        pass


    def check_k8s_job_status(self, name):
        return client.BatchV1Api().read_namespaced_job(name,self.namespace).status

    def sequence_from_spec(self, mainmounts, configmounts = None):
        configmounts = configmounts or []
        mainmounts = mainmounts or []
        return [{
          "name": seqname,
          "image": sequence_spec[seqname]['image'],
          "command": sequence_spec[seqname]['cmd'],
          "env": sequence_spec['config_env'] if sequence_spec[seqname]['iscfg'] else [],
          "volumeMounts":  mainmounts + (configmounts if sequence_spec[seqname]['iscfg'] else [])
        } for seqname in sequence_spec["sequence"]]