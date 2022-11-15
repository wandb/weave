set -e

cd "$WANDB_CORE"/frontends/app/weave-ui
yarn build
cd -
rm -rf assets index.html
cp -R "$WANDB_CORE"/frontends/app/weave-ui/build/* .
