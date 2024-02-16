import fetch from 'isomorphic-unfetch';

export const fetchAllCalls = async () => {
    const url = "http://127.0.0.1:6345/calls/query"
    // eslint-disable-next-line wandb/no-unprefixed-urls
    const response = await fetch(url, {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            "entity": "test_entity",
            "project": "test_project",
        }),
    });
    return response.json();
}
