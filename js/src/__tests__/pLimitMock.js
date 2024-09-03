// Have to mock this for testing, jest doesn't like the module style
// of the p-limit package. I'm sure there's some way to get jest to
// correctly transform it. I just mocked it out instead.

function pLimit(concurrency) {
    return (fn) => {
        return fn();
    }
}

module.exports = pLimit;
