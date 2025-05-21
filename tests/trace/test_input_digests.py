"""
In order to effectively query/join traces, we need to operate on inputs. However, inputs
are often large and complex - reading that column is usually the worst part of a query.

`input_digests` is a new dictionary living under `attributes.weave` that contains a
digest of each input parameter for a given call.

The key thing here is that digests are stable across names / refs. 
"""

import weave

def test_basic_input_digests(client):
    @weave.op
    def op_with_2_params(a: int, b: int):
        return a + b
    
    res = op_with_2_params(a=1, b=2)
    calls = client.get_calls()
    assert len(calls) == 1
    print(calls[0].attributes)
    assert calls[0].attributes['weave']['input_digests'] == {'a': 'a4aycY80YOGda4BOY1oYV0etpOqiLx1JwB5S3beHW0s', 'b': '1HNeOiZeFu7gP1lxi5tdAwGcB9i2xRXQ2jpmbuwTqzU'}
    
    