"""Test bound method metadata tracking."""
import weave


def test_bound_method_metadata(client):
    """Test that bound method metadata is tracked in call attributes."""
    # Create a class with a method decorated with @weave.op
    class MyModel(weave.Model):
        prompt: str

        @weave.op
        def predict(self, input: str) -> str:
            return self.prompt.format(input=input)

    # Create an instance and save it
    model = MyModel(prompt="input is: {input}")
    ref = weave.publish(model)

    # Call the method
    result, call = model.predict.call("test")

    # Verify the result
    assert result == "input is: test"

    # Verify that bound method metadata is present
    assert call.attributes is not None

    # Check the structure
    assert 'weave' in call.attributes
    assert 'python' in call.attributes['weave']
    assert 'bound_method' in call.attributes['weave']['python']

    bound_method = call.attributes['weave']['python']['bound_method']

    # Verify the metadata contents
    assert 'instance_id' in bound_method
    assert bound_method['instance_id'] == id(model)
    assert 'instance_class' in bound_method
    assert bound_method['instance_class'] == 'MyModel'
    assert 'instance_ref' in bound_method
    assert bound_method['instance_ref'] == ref.uri()


def test_regular_function_no_metadata(client):
    """Test that regular functions don't have bound method metadata."""
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    result, call = add.call(1, 2)

    assert result == 3

    # Verify no bound method metadata for regular functions
    if call.attributes and 'weave' in call.attributes:
        python_attrs = call.attributes.get('weave', {}).get('python', {})
        assert 'bound_method' not in python_attrs or python_attrs['bound_method'] is None


def test_class_method_metadata(client):
    """Test that class methods have bound method metadata."""
    class Calculator:
        @weave.op
        @classmethod
        def add(cls, a: int, b: int) -> int:
            return a + b

    result, call = Calculator.add.call(1, 2)

    assert result == 3

    # Verify bound method metadata for classmethod
    if call.attributes and 'weave' in call.attributes:
        python_attrs = call.attributes.get('weave', {}).get('python', {})
        if 'bound_method' in python_attrs:
            bound_method = python_attrs['bound_method']
            assert 'instance_class' in bound_method
