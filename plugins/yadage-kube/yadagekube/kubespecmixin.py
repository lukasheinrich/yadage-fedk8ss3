class KubeSpecMixin(object):
    def __init__(self, **kwargs):
        self.cvmfs_repos = ['atlas.cern.ch','sft.cern.ch','atlas-condb.cern.ch']
        self.secrets = kwargs.get('secrets', {'hepauth': 'hepauth'})
        self.authmount = '/recast_auth'

    def auth_binds(self,authmount = None):
        container_mounts = []
        volumes = []

        authmount = authmount or self.authmount
        log.debug('binding auth')
        volumes.append({
            'name': 'hepauth',
            'secret': {
                'secretName': self.secrets['hepauth'],
                'items': [
                    {
                    'key': 'getkrb.sh',
                    'path': 'getkrb.sh',
                    'mode': 493 #755
                    }
                ]
            }
        })
        container_mounts.append({
            "name": 'hepauth',
            "mountPath": authmount
        })
        return container_mounts, volumes

    def cvmfs_binds(self, repos = None):
        container_mounts = []
        volumes = []
        log.debug('binding CVMFS')
        repos = respos or self.cvmfs_repos
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

    def get_job_mounts(self, cvmfs, auth, parmounts):
        kube_resources = []
        container_mounts = []
        volumes = []

        if cvmfs:
            container_mounts_cvmfs, volumes_cvmfs = self.cvmfs_binds()
            container_mounts += container_mounts_cvmfs
            volumes          += volumes_cvmfs

        if auth:
            container_mounts_auth, volumes_auth = self.auth_binds()
            container_mounts += container_mounts_auth
            volumes          += volumes_auth

        if parmounts:
            container_mounts_pm, volumes_pm, pm_cm_spec = self.make_par_mount(job_uuid, parmounts)
            container_mounts += container_mounts_pm
            volumes += volumes_pm
            kube_resources.append(pm_cm_spec)
        return kube_resources, container_mounts, volumes

    def container_sequence_fromspec(self, sequence_spec, mainmounts  = None, configmounts = None):
        configmounts = configmounts or []
        mainmounts = mainmounts or []
        return  [{
          "name": seqname,
          "image": sequence_spec[seqname]['image'],
          "command": sequence_spec[seqname]['cmd'],
          "env": sequence_spec['config_env'] if sequence_spec[seqname]['iscfg'] else [],
          "volumeMounts":  mainmounts + (configmounts if sequence_spec[seqname]['iscfg'] else [])
        } for seqname in sequence_spec['sequence']]


    def get_job_spec_for_sequence(self, jobname,sequence, volumes):
        containers = sequence[-1:]
        initContainers = sequence[:-1]

        return self.get_job_spec(
            jobname,
            initContainers = initContainers,
            containers = containers,
            volumes = volumes
        )

    def get_job_spec(self, jobname, initContainers = None, containers = None, volumes = None):
        containers = containers or []
        initContainers = initContainers or []
        volumes = volumes or []
        return {
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
                "initContainers": initContainers,
                "containers": containers,
                "volumes": volumes
              },
              "metadata": { "name": jobname }
            }
          },
          "metadata": { "name": jobname }
    }