from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Literal
import wave

from conversation_manager import ConversationManager
from typing import Any, cast


def _jsonify(obj):
    if hasattr(obj, "model_dump"):
        return _jsonify(obj.model_dump())
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, set):
        return list(obj)
    return obj


class ExportAdapter(Protocol):
    def export(self, manager: ConversationManager, output: str | os.PathLike[str]) -> None: ...


@dataclass
class JSONFileExportAdapter:
    """
    Exports a single JSON file snapshot of the conversation state including:
    - session, items, responses, timeline, speech markers
    - response_context map
    - response audio bytes (base64-encoded)
    """

    include_audio_bytes: bool = True

    def export(self, manager: ConversationManager, output: str | os.PathLike[str]) -> None:
        dest = Path(output)
        dest.parent.mkdir(parents=True, exist_ok=True)

        base = cast(dict[str, Any], _jsonify(manager.export_state()))
        state: dict[str, Any] = {**base, "response_context": manager.state.response_context}

        if self.include_audio_bytes:
            audio_out: dict[str, str] = {}
            for key, buf in manager.state.resp_audio_bytes.items():
                resp_id, item_id, content_index = key
                name = f"{resp_id}__{item_id}__{content_index}"
                audio_out[name] = base64.b64encode(bytes(buf)).decode("ascii")
            state["response_audio_base64"] = audio_out

        dest.write_text(json.dumps(state, indent=2))


@dataclass
class DirectoryExportAdapter:
    """
    Writes a directory with:
    - state.json (same as JSONFileExportAdapter w/o audio bytes)
    - item audio segments: item_<item_id>.pcm (if we have speech markers)
    - response audio blobs: resp_<respid>__<itemid>__<idx>.pcm
    """

    audio_format: Literal["pcm", "wav"] = "pcm"

    def _write_pcm_or_wav(self, dest: Path, data: bytes, manager: ConversationManager) -> None:
        if self.audio_format == "wav":
            buf = manager.state.input_audio_buffer
            sampwidth = buf.bytes_per_sample()
            with wave.open(str(dest), "wb") as wf:
                wf.setnchannels(buf.channels)
                wf.setsampwidth(sampwidth)
                wf.setframerate(buf.sample_rate_hz)
                wf.writeframes(data)
        else:
            dest.write_bytes(data)

    def export(self, manager: ConversationManager, output: str | os.PathLike[str]) -> None:
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)

        # state.json
        state_dest = out_dir / "state.json"
        base2 = cast(dict[str, Any], _jsonify(manager.export_state()))
        out_state: dict[str, Any] = {**base2, "response_context": manager.state.response_context}
        state_dest.write_text(json.dumps(out_state, indent=2))

        # item audio segments
        for item_id, markers in manager.state.speech_markers.items():
            start_ms = markers.get("audio_start_ms")
            end_ms = markers.get("audio_end_ms")
            if start_ms is None or end_ms is None:
                continue
            seg = manager.get_audio_segment(item_id)
            if not seg:
                continue
            ext = "wav" if self.audio_format == "wav" else "pcm"
            self._write_pcm_or_wav(out_dir / f"item_{item_id}.{ext}", seg, manager)

        # response audio buffers
        for key, buf in manager.state.resp_audio_bytes.items():
            resp_id, item_id, idx = key
            ext = "wav" if self.audio_format == "wav" else "pcm"
            self._write_pcm_or_wav(out_dir / f"resp_{resp_id}__{item_id}__{idx}.{ext}", bytes(buf), manager)
