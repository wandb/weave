set -e

cd "$WANDB_CORE"/frontends/app/weave
yarn build
cd -
rm -rf assets index.html
cp -R "$WANDB_CORE"/frontends/app/weave/build/* .
git -C "$WANDB_CORE" describe --match="" --always --dirty > core_version
if grep -q dirty core_version; then echo "!!! WARNING: frontend was built from dirty wandb/core !!!"; fi
