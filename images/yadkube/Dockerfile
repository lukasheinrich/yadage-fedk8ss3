FROM alpine
RUN  apk add automake autoconf libtool && \
     apk add python-dev musl-dev libffi-dev && \
     apk add python-dev musl-dev libffi-dev gcc && \
     apk add autoconf curl gcc ipset ipset-dev iptables iptables-dev libnfnetlink libnfnetlink-dev libnl3 libnl3-dev make musl-dev openssl openssl-dev && \
     curl https://bootstrap.pypa.io/get-pip.py | python -
RUN apk add graphviz-dev imagemagick graphviz
RUN curl https://download.docker.com/linux/static/stable/x86_64/docker-18.03.1-ce.tgz|tar -xzvf - && \
    cp docker/docker /usr/local/bin && \
    rm -rf docker
RUN pip install yadage[viz] pydotplus
ADD plugins /yadage
WORKDIR /yadage
RUN cd yadage-extresult/ && pip install -e . && cd - && \
    cd yadage-objstore/ && pip install  -e . && cd - && \
    cd yadage-kube/     && pip install  -e . && cd -
RUN pip install kubernetes
RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/v1.12.0/bin/linux/amd64/kubectl && \
    mv kubectl /usr/local/bin && \
    chmod +x /usr/local/bin/kubectl
RUN apk add jq
