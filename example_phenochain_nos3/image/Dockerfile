FROM fedora
RUN dnf install -y gcc gcc-c++ graphviz-devel ImageMagick python python-devel libffi-devel openssl openssl-devel unzip nano autoconf automake libtool redhat-rpm-config make; dnf clean all 
RUN curl https://bootstrap.pypa.io/get-pip.py | python -
WORKDIR /code
RUN pip install yadage[viz] kubernetes
