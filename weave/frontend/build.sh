set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
JS_DIR=$SCRIPT_DIR/../../weave-js
SHA1=$(find $JS_DIR -not -path "*/.vite-cache/*" -not -path "*/node_modules/*" -not -path "*/build/*" -type f -print0 | sort -z | xargs -0 sha1sum | cut -d " " -f1 | sha1sum | cut -d " " -f1)

yarn --cwd=$JS_DIR install --frozen-lockfile
yarn --cwd=$SCRIPT_DIR/../../weave-js build
cd $SCRIPT_DIR
rm -rf assets index.html
cp -R ../../weave-js/build/* .
echo $SHA1 > sha1.txt
