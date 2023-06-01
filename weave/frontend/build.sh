set -e

cd ../../weave-js
yarn build
cd -
rm -rf assets index.html
cp -R ../../weave-js/build/* .
