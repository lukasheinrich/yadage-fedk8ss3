import os
from setuptools import setup, find_packages

setup(
  name = 'yadage-kube',
  version = '0.0.1',
  description = 'yadage backends and mixins for Kubernetes',
  url = '',
  author = 'Lukas Heinrich',
  author_email = 'lukas.heinrich@cern.ch',
  packages = find_packages(),
  include_package_data = True,
  install_requires = ['yadage','minio','packtivity'],
  entry_points = {
  },
  dependency_links = [
  ]
)
