FROM frolvlad/alpine-glibc:alpine-3.17_glibc-2.34
LABEL MAINTAINER="danny goldstein <danny@wandb.com>"

ENV CONDA_VERSION=4.9.2 \
    CONDA_MD5=b4e46fcc8029e2cfa731b788f25b1d36 \
    PYTHON_VERSION=39 \
    PYTHONDONTWRITEBYTECODE=true \
    PATH=/opt/conda/bin/:/opt/conda/envs/base/:$PATH \
    WEAVE_LOCAL_ARTIFACT_DIR=/local-artifacts

# We do the following all in one block:
# - Create user and group weave
# - Install miniconda install dependencies
# - Download miniconda and check the md5sum
# - Install miniconda
# - Install tini
# - Remove all conda managed static libraries
# - Remove all conda managed *.pyc files
# - Cleanup conda files
# - Uninstall miniconda install dependencies
RUN mkdir /weave &&
    apk add --no-cache wget bzip2 &&
    wget --quiet https://repo.continuum.io/miniconda/Miniconda3-py${PYTHON_VERSION}_$CONDA_VERSION-Linux-x86_64.sh &&
    echo "${CONDA_MD5}  Miniconda3-py${PYTHON_VERSION}_$CONDA_VERSION-Linux-x86_64.sh" >miniconda.md5 &&
    if [ $(md5sum -c miniconda.md5 | awk '{print $2}') != "OK" ]; then exit 1; fi &&
    mv Miniconda3-py${PYTHON_VERSION}_$CONDA_VERSION-Linux-x86_64.sh miniconda.sh &&
    sh ./miniconda.sh -b -p /opt/conda &&
    rm miniconda.sh miniconda.md5 &&
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh &&
    echo ". /opt/conda/etc/profile.d/conda.sh" >>/weave/.profile &&
    echo "conda activate base" >>/weave/.profile &&
    /opt/conda/bin/conda install conda==$CONDA_VERSION &&
    echo "conda == $CONDA_VERSION" >>/opt/conda/conda-meta/pinned &&
    /opt/conda/bin/conda install --freeze-installed tini pip gunicorn python=3.9.7 -y &&
    find /opt/conda/ -follow -type f -name '*.a' -delete &&
    find /opt/conda/ -follow -type f -name '*.pyc' -delete &&
    /opt/conda/bin/conda clean -afy &&
    apk del wget bzip2

ENV PORT 9239

WORKDIR /weave
ADD . .

RUN pip install -r requirements.engine.txt
RUN mkdir /local-artifacts

EXPOSE 9239

ENTRYPOINT [ "tini", "-g", "--" ]
CMD ["gunicorn", "weave.legacy.weave.weave_server:app"]
