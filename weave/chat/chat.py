from weave.chat.completions import Completions


class Chat:
    def __init__(self, entity: str, project: str):
        self.completions = Completions(entity, project)
