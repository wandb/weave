import importlib
from typing import Union

from weave.integrations.google_genai.gemini_utils import (
    google_genai_gemini_wrapper_async,
    google_genai_gemini_wrapper_sync,
)
from weave.integrations.google_genai.imagen_utils import (
    google_genai_imagen_wrapper_async,
    google_genai_imagen_wrapper_sync,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings


def get_google_genai_patcher(
    settings: Union[IntegrationSettings, None] = None,
) -> Union[MultiPatcher, NoOpPatcher]:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    base = settings.op_settings

    generate_content_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.Models.generate_content"}
    )
    count_tokens_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.Models.count_tokens"}
    )
    generate_content_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.AsyncModels.generate_content"}
    )
    count_tokens_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.AsyncModels.count_tokens"}
    )
    chat_settings = base.model_copy(
        update={"name": base.name or "google.genai.chats.Chat.send_message"}
    )
    chat_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.chats.AsyncChat.send_message"}
    )
    generate_content_stream_settings = base.model_copy(
        update={
            "name": base.name or "google.genai.models.Models.generate_content_stream"
        }
    )
    generate_content_stream_async_settings = base.model_copy(
        update={
            "name": base.name
            or "google.genai.models.AsyncModels.generate_content_stream"
        }
    )
    generate_images_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.Models.generate_images"}
    )
    generate_images_async_settings = base.model_copy(
        update={"name": base.name or "google.genai.models.AsyncModels.generate_images"}
    )

    _google_genai_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.generate_content",
                google_genai_gemini_wrapper_sync(generate_content_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "AsyncModels.generate_content",
                google_genai_gemini_wrapper_async(generate_content_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.count_tokens",
                google_genai_gemini_wrapper_sync(count_tokens_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "AsyncModels.count_tokens",
                google_genai_gemini_wrapper_async(count_tokens_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.chats"),
                "Chat.send_message",
                google_genai_gemini_wrapper_sync(chat_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.chats"),
                "AsyncChat.send_message",
                google_genai_gemini_wrapper_async(chat_async_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.generate_content_stream",
                google_genai_gemini_wrapper_sync(generate_content_stream_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "AsyncModels.generate_content_stream",
                google_genai_gemini_wrapper_async(
                    generate_content_stream_async_settings
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "Models.generate_images",
                google_genai_imagen_wrapper_sync(generate_images_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("google.genai.models"),
                "AsyncModels.generate_images",
                google_genai_imagen_wrapper_async(generate_images_async_settings),
            ),
        ]
    )

    return _google_genai_patcher
