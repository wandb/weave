set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SHA=$(cat $SCRIPT_DIR/sha1.txt)

cd $SCRIPT_DIR/..
tar --exclude='frontend/bundle.sh' --exclude='frontend/build.sh' -cvzf /tmp/$SHA.tar.gz frontend

if [[ "${CI}" == "true" && -n "${GOOGLE_APPLICATION_CREDENTIALS}" ]]; then
    echo "Uploading bundle to cloud storage..."
    gcloud storage cp /tmp/$SHA.tar.gz gs://wandb-cdn-prod/weave/$SHA.tar.gz
else
    echo "Upload bundle by running: gcloud storage cp /tmp/$SHA.tar.gz gs://wandb-cdn-prod/weave/$SHA.tar.gz"
fi
