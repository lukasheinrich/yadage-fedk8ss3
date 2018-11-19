import logging

from packtivity.asyncbackends import ExternalAsyncMixin, RemoteResultMixin
from packtivity.syncbackends import publish, packconfig, finalize_outputs, finalize_inputs
from packtivity.backendutils import backend
from packtivity.statecontexts import load_state
from packtivity.typedleafs import TypedLeafs

from yadagekube.kubejobbackend import KubernetesBackend
from yadagekube.kubejobbackend2 import KubernetesBackend as KubernetesBackend2

from .jobspec import JobSequenceMakerMixin, DirectJobMakerMixin
from .S3ResultStore import S3ResultStore

log = logging.getLogger(__name__)

class RemoteResultExternalBackend(
    JobSequenceMakerMixin,
    ExternalAsyncMixin,
    RemoteResultMixin,
):
    def __init__(self, **kwargs):
        kwargs['job_backend']   = KubernetesBackend(kwargs['resultstore'])
        kwargs['resultbackend'] = S3ResultStore(kwargs['resultstore'])
        JobSequenceMakerMixin.__init__(self, **kwargs)
        ExternalAsyncMixin.__init__(self,**kwargs)
        RemoteResultMixin.__init__(self,**kwargs)

@backend('kubernetes')
def k8s_backend(backendstring, backendopts):
    backend = RemoteResultExternalBackend(**backendopts)
    return False, backend


class DirectExternalKubernetesBackend(
    DirectJobMakerMixin,
    ExternalAsyncMixin,
):
    def __init__(self, **kwargs):
        kwargs['job_backend']   = KubernetesBackend2(**kwargs)
        DirectJobMakerMixin.__init__(self, **kwargs)
        ExternalAsyncMixin.__init__(self,**kwargs)
        self.config = packconfig()

    def result(self,resultproxy):
        state = load_state(resultproxy.statedata, self.deserialization_opts)

        if resultproxy.resultdata is not None:
            return  TypedLeafs(resultproxy.resultdata, state.datamodel)

        parameters = TypedLeafs(resultproxy.pardata, state.datamodel)


        parameters, state = finalize_inputs(parameters, state)

        pubdata = publish(resultproxy.spec['publisher'], parameters,state,self.config)
        log.info('publishing data: %s',pubdata)
        pubdata = finalize_outputs(pubdata)
        resultproxy.resultdata = pubdata.json()
        return pubdata

@backend('kubedirectjob')
def k8s_direct_backend(backendstring, backendopts):
    backend = DirectExternalKubernetesBackend(**backendopts)
    return False, backend
