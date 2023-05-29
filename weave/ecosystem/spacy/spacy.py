import weave
import spacy as spacy_lib
import pickle


class SpacyDocType(weave.types.Type):
    instance_classes = spacy_lib.tokens.doc.Doc

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.pickle", binary=True) as f:
            pickle.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.pickle", binary=True) as f:
            return pickle.load(f)


@weave.op(render_info={"type": "function"})
def spacy(text: str) -> spacy_lib.tokens.doc.Doc:
    # TODO: Make this into a package that loads all the models from spacy,
    # has types, and supports different Components (similar to HF). For now,
    # this is just a simple english model
    import spacy as spacy_lib

    nlp = spacy_lib.load("en_core_web_sm")
    return nlp(text)


@weave.op()
def spacy_doc_dep_to_html(spacy_doc: spacy_lib.tokens.doc.Doc) -> weave.ops.Html:
    from spacy import displacy

    html = displacy.render(
        list(spacy_doc.sents), style="dep", jupyter=False, options={"compact": True}
    )
    return weave.ops.Html(html)


@weave.op()
def spacy_doc_ent_to_html(spacy_doc: spacy_lib.tokens.doc.Doc) -> weave.ops.Html:
    from spacy import displacy

    html = displacy.render(spacy_doc, style="ent", jupyter=False)
    return weave.ops.Html(html)


@weave.type()
class SpacyDocPanel(weave.Panel):
    id = "SpacyDocPanel"
    input_node: weave.Node[spacy_lib.tokens.doc.Doc]

    @weave.op()
    def render(self) -> weave.panels.Card:
        return weave.panels.Card(
            title="Spacy Visualization",
            subtitle="",
            content=[
                weave.panels.CardTab(
                    name="Dependencies",
                    content=weave.panels.PanelHtml(spacy_doc_dep_to_html(self.input_node)),  # type: ignore
                ),
                weave.panels.CardTab(
                    name="Named Entities",
                    content=weave.panels.PanelHtml(spacy_doc_ent_to_html(self.input_node)),  # type: ignore
                ),
            ],
        )
