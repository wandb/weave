# Running in devmode

Start the weave server and frontend dev server with 
cd .. && make integration

Start cypress with 
yarn && yarn dev

# Running against built assets

Build the latest frontend with 

cd .. && ./build_frontend.sh

Start cypress with 

yarn && yarn run cypress open

Start the weave server with 

bash weave_server_test.sh
