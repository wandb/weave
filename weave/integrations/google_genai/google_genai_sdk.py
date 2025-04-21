import importlib
from typing import Callable, Union

from weave.integrations.google_genai.gemini_utils import (
    google_genai_gemini_wrapper_async,
    google_genai_gemini_wrapper_sync,
)
from weave.integrations.google_genai.imagen_utils import (
    google_genai_imagen_wrapper_async,
    google_genai_imagen_wrapper_sync,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings


def get_google_genai_symbol_patcher(
    base_symbol: str, attribute_name: str, wrapper: Callable, settings: OpSettings
) -> SymbolPatcher:
    display_name = base_symbol + "." + attribute_name
    display_name = (
        display_name.replace(".__call__", "")
        if attribute_name.endswith(".__call__")
        else display_name
    )
    return SymbolPatcher(
        lambda: importlib.import_module(base_symbol),
        attribute_name,
        wrapper(settings.model_copy(update={"name": settings.name or display_name})),
    )


def get_google_genai_patcher(
    settings: Union[IntegrationSettings, None] = None,
) -> Union[MultiPatcher, NoOpPatcher]:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    base = settings.op_settings

    _google_genai_patcher = MultiPatcher(
        [
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "Models.generate_content",
                google_genai_gemini_wrapper_sync,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "AsyncModels.generate_content",
                google_genai_gemini_wrapper_async,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "Models.count_tokens",
                google_genai_gemini_wrapper_sync,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "AsyncModels.count_tokens",
                google_genai_gemini_wrapper_async,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.chats",
                "Chat.send_message",
                google_genai_gemini_wrapper_sync,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.chats",
                "AsyncChat.send_message",
                google_genai_gemini_wrapper_async,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "Models.generate_content_stream",
                google_genai_gemini_wrapper_sync,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "AsyncModels.generate_content_stream",
                google_genai_gemini_wrapper_async,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "Models.generate_images",
                google_genai_imagen_wrapper_sync,
                base,
            ),
            get_google_genai_symbol_patcher(
                "google.genai.models",
                "AsyncModels.generate_images",
                google_genai_imagen_wrapper_async,
                base,
            ),
        ]
    )

    return _google_genai_patcher
