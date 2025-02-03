import uuid
import gradio as gr

import PIL
import dataclasses


@dataclasses.dataclass
class Prediction:
    logits: dict[str, float]
    prediction_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))


class PredictionServiceInterface:
    def predict(self, pil_image: "PIL.Image") -> Prediction:  # type: ignore
        raise NotImplementedError

    def record_feedback(self, prediction_id: str, feedback: int) -> None:
        return None


def render_app(service: PredictionServiceInterface):
    def on_predict(pil_image):
        if pil_image is None:
            return None
        prediction = service.predict(pil_image)
        return prediction.logits, prediction

    def make_feedback_callback(feedback):
        def on_feedback(current_prediction):
            if current_prediction is None:
                return
            service.record_feedback(current_prediction.prediction_id, feedback)

        return on_feedback

    with gr.Blocks() as demo:
        current_prediction = gr.State(value=None)
        with gr.Column():
            with gr.Row():
                inp = gr.Sketchpad(
                    label="Draw a number between 0 and 9",
                    brush_radius=5,
                    type="pil",
                    shape=(128, 128),
                )
                out = gr.Label(label="Prediction", num_top_classes=4)
            btn = gr.Button("Predict")
            with gr.Row():
                btns = [
                    gr.ClearButton(components=[inp, out], value=str(i))
                    for i in range(10)
                ]

        btn.click(fn=on_predict, inputs=inp, outputs=[out, current_prediction])
        for btn_ndx, fb_btn in enumerate(btns):
            fb_btn.click(
                fn=make_feedback_callback(btn_ndx),
                inputs=current_prediction,
                outputs=[],
            )

    demo.launch(quiet=True, show_api=False, height=550)
