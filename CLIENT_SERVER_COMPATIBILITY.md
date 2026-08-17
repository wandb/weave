# Client-server compatibility

Every Python and TypeScript client release is tested against the minimum
supported W&B server recorded in
[`client_server_compatibility.json`](client_server_compatibility.json).

The minimum is an explicit release boundary. CI does not calculate or advance
it from the current date. Advancing it requires a pull request that updates the
server release, trace protocol version, immutable server image, source commit,
and contract snapshot together. The default support window is 90 days.

Client changes that require a newer trace-server protocol must update
`MIN_TRACE_SERVER_VERSION` and the compatibility contract in the same pull
request. Ordinary additive request fields should remain compatible with the
minimum server by staying off the wire when they are unset or equal to their
defaults.

The compatibility smoke tests cross a real HTTP boundary and exercise
`/feedback/batch/create`, the endpoint involved in the strict-model rollback.
The Python test also sends the unfiltered request as a negative control and
requires the minimum-server contract to reject it with `extra_forbidden`.
