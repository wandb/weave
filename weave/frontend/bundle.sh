set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SHA=$(cat $SCRIPT_DIR/sha1.txt)

cd $SCRIPT_DIR/..
tar --exclude='frontend/bundle.sh' --exclude='frontend/build.sh' -cvzf /tmp/$SHA.tar.gz frontend

if [[ "${IS_RELEASE_ENV}" == "true" && "${CI}" == "true" ]]; then
    echo "Uploading bundle to cloud storage..."
#    gsutil cp /tmp/$SHA.tar.gz gs://wandb-cdn-prod/weave/*
else
    echo "Upload bundle by running: gsutil cp /tmp/$SHA.tar.gz gs://wandb-cdn-prod/weave/"
fi
