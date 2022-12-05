# requires cypress api key in ~/.cypress-key

CYPRESS_BUILD_ID=local-test-`echo $RANDOM | md5 -r | head -c 10`
CYPRESS_KEY=`cat ~/.cypress-key`

for i in `seq 1 6`; do
  npx cypress run --parallel --record --browser chrome --key $CYPRESS_KEY --ci-build-id $CYPRESS_BUILD_ID &
done

wait
