# yadage-fedk8ss3


```
docker run --net=host --rm -it -v $PWD:$PWD -v $HOME/.kube:/root/.kube -w $PWD yadkube bash
cd example_phenochain_nos3
kubectl create -f state
yadage-run -f spec.yml
```
