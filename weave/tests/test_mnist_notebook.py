import weave
from weave.ecosystem import torchvision, torch_mnist_model_example


def test_mnist_notebook():
    # Cell 1:
    mnist_dataset = torchvision.mnist(
        100
    )  # Or try mnist.food101(100), but currently broken
    weave.use(mnist_dataset)

    # Cell 2:
    hyperparams = {
        "fc_layer_size": 256,
        "dropout": 0.5,
        "epochs": 5,
        "learning_rate": 0.005,
        "batch_size": 128,
    }
    train_split = mnist_dataset["data"]["train"]
    # train_split.pick('image')
    model = torch_mnist_model_example.train(
        train_split.pick("image"), train_split.pick("label"), hyperparams
    )

    # Cell 3:
    test_split_images = mnist_dataset["data"]["test"].pick("image")
    preds = model.predict(test_split_images)
    weave.use(preds)
