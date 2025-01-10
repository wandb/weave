import numpy as np
from tensorflow import keras
from tensorflow.keras import layers
from PIL import Image
import numpy as np

# Model / data parameters
num_classes = 10
input_shape = (28, 28, 1)


def image_from_array(image_arr):
    return Image.fromarray((image_arr.reshape(28, 28) * 255).astype("uint8")).resize(
        (112, 112)
    )


def get_dataset():
    # Load the data and split it between train and test sets
    (x_train, y_train), (x_test, y_test) = keras.datasets.mnist.load_data()

    # Scale images to the [0, 1] range
    x_train = x_train.astype("float32") / 255
    x_test = x_test.astype("float32") / 255
    # Make sure images have shape (28, 28, 1)
    x_train = np.expand_dims(x_train, -1)
    x_test = np.expand_dims(x_test, -1)
    print("x_train shape:", x_train.shape)
    print(x_train.shape[0], "train samples")
    print(x_test.shape[0], "test samples")

    return x_train, y_train, x_test, y_test


def train_model(
    x_train, y_train, x_test, y_test, conv_layers=2, batch_size=128, epochs=15
):
    # Exmaple from: https://keras.io/examples/vision/mnist_convnet/

    # convert class vectors to binary class matrices
    y_train = keras.utils.to_categorical(y_train, num_classes)
    y_test = keras.utils.to_categorical(y_test, num_classes)

    s_layers = [keras.Input(shape=input_shape)]
    for i in range(conv_layers):
        s_layers.append(layers.Conv2D(32, kernel_size=(3, 3), activation="relu"))
        s_layers.append(layers.MaxPooling2D(pool_size=(2, 2)))
    s_layers.append(layers.Flatten())
    s_layers.append(layers.Dropout(0.5))
    s_layers.append(layers.Dense(num_classes, activation="softmax"))
    model = keras.Sequential(s_layers)

    print(model.summary())

    model.compile(
        loss="categorical_crossentropy", optimizer="adam", metrics=["accuracy"]
    )

    model.fit(
        x_train, y_train, batch_size=batch_size, epochs=epochs, validation_split=0.1
    )

    score = model.evaluate(x_test, y_test, verbose=0)
    print("Test loss:", score[0])
    print("Test accuracy:", score[1])

    return model


import gradio as gr


def render_interface(predict):
    def on_predict(pil_image):
        if pil_image is None:
            return None
        return predict(pil_image)

    def on_correct(pil_image, prediction):
        pass

    def on_incorrect(pil_image, prediction):
        pass

    with gr.Blocks() as demo:
        with gr.Row():
            inp = gr.Sketchpad(
                label="Draw a number between 0 and 9",
                brush_radius=5,
                type="pil",
                shape=(128, 128),
            )
            out = gr.Label(label="Prediction", num_top_classes=4)
        with gr.Row():
            with gr.Column():
                btn = gr.Button("Predict")
            with gr.Row():
                btn2 = gr.Button("Correct   ✅", variant="primary")
                btn3 = gr.Button("Incorrect   🚫", variant="stop")
        btn.click(fn=on_predict, inputs=inp, outputs=out)
        btn2.click(fn=on_correct, inputs=[inp, out], outputs=[])
        btn3.click(fn=on_incorrect, inputs=[inp, out], outputs=[])

    demo.launch(quiet=True, show_api=False, height=320)
