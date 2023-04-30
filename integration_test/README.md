# Running in devmod

You want to run the frontend vite server and the weave server so you can develop. Here's how.

change baseUrl to 'http://localhost:3000' in cypress.config.js

Add "--host ::1" to weave_server_test.sh. Why is this needed? I have no idea.

run the weave server with `./weave_server_test.sh`

change the url you visit in your test to '/?...' instead of an absolute URL.

This is way too much work! Someone should fix this so its automatic!