for i in `seq 1 6`; do
  npx ds run --parallel --record --browser chrome &
done

wait
