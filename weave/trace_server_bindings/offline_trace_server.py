"""Offline trace server that writes call data to local files for later syncing."""

import datetime
import gzip
import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ids import generate_id
from weave.trace_server_bindings.models import ServerInfoRes

logger = logging.getLogger(__name__)

DEFAULT_OFFLINE_DIR = Path.home() / ".weave" / "offline"


class OfflineTraceServer(tsi.TraceServerInterface):
    """A trace server that writes call data to local files for offline operation.
    
    This server stores trace data in JSON Lines format (.jsonl) files that can be
    synced to a remote server later. Files are organized by date and compressed
    with gzip to save space.
    """
    
    def __init__(
        self,
        offline_dir: Optional[Path] = None,
        compress: bool = True,
        max_file_size_mb: int = 100,
    ):
        """Initialize the offline trace server.
        
        Args:
            offline_dir: Directory to store offline data. Defaults to ~/.weave/offline
            compress: Whether to compress files with gzip
            max_file_size_mb: Maximum size of each file in MB before rotation
        """
        self.offline_dir = Path(offline_dir or DEFAULT_OFFLINE_DIR)
        self.offline_dir.mkdir(parents=True, exist_ok=True)
        self.compress = compress
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        
        # Track current file handles
        self._current_files: dict[str, Any] = {}
        self._file_sizes: dict[str, int] = {}
        
    def _get_file_path(self, entity: str, project: str, data_type: str = "calls") -> Path:
        """Get the file path for storing data.
        
        Args:
            entity: Entity name
            project: Project name  
            data_type: Type of data (calls, ops, objects, etc.)
            
        Returns:
            Path to the file
        """
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        project_dir = self.offline_dir / entity / project / data_type
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Find the next available file number
        file_num = 0
        while True:
            ext = ".jsonl.gz" if self.compress else ".jsonl"
            file_path = project_dir / f"{date_str}_{file_num:04d}{ext}"
            
            # Check if file exists and is under size limit
            if not file_path.exists():
                return file_path
            
            file_size = file_path.stat().st_size
            if file_size < self.max_file_size_bytes:
                return file_path
                
            file_num += 1
            
    def _write_to_file(self, entity: str, project: str, data_type: str, data: dict[str, Any]) -> None:
        """Write data to the appropriate file.
        
        Args:
            entity: Entity name
            project: Project name
            data_type: Type of data  
            data: Data to write
        """
        file_path = self._get_file_path(entity, project, data_type)
        file_key = str(file_path)
        
        # Open file handle if not already open
        if file_key not in self._current_files:
            if self.compress:
                self._current_files[file_key] = gzip.open(file_path, "at", encoding="utf-8")
            else:
                self._current_files[file_key] = open(file_path, "a", encoding="utf-8")
            self._file_sizes[file_key] = file_path.stat().st_size if file_path.exists() else 0
            
        # Write data as JSON line
        json_line = json.dumps(data, default=str) + "\n"
        self._current_files[file_key].write(json_line)
        self._current_files[file_key].flush()
        
        # Update tracked file size
        self._file_sizes[file_key] += len(json_line.encode("utf-8"))
        
        # Close file if it exceeds size limit
        if self._file_sizes[file_key] >= self.max_file_size_bytes:
            self._current_files[file_key].close()
            del self._current_files[file_key]
            del self._file_sizes[file_key]
            
    def close(self) -> None:
        """Close all open file handles."""
        for file_handle in self._current_files.values():
            try:
                file_handle.flush()
                file_handle.close()
            except Exception as e:
                logger.warning(f"Error closing file: {e}")
        self._current_files.clear()
        self._file_sizes.clear()
        
    def __del__(self) -> None:
        """Ensure files are closed when object is destroyed."""
        self.close()
        
    def ensure_project_exists(
        self, entity: str, project: str
    ) -> tsi.EnsureProjectExistsRes:
        """Ensure project directory exists for offline storage."""
        project_dir = self.offline_dir / entity / project
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Store project metadata
        metadata = {
            "entity": entity,
            "project": project,
            "created_at": datetime.datetime.now().isoformat(),
        }
        self._write_to_file(entity, project, "metadata", metadata)
        
        return tsi.EnsureProjectExistsRes(project_name=project)
        
    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        """Record call start to offline storage."""
        call_id = req.start.id or generate_id()
        trace_id = req.start.trace_id or generate_id()
        
        # Extract entity and project from project_id
        parts = req.start.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.start.project_id
            
        # Store call start data
        data = {
            "type": "call_start",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": req.start.model_dump(mode="json"),
        }
        data["data"]["id"] = call_id
        data["data"]["trace_id"] = trace_id
        
        self._write_to_file(entity, project, "calls", data)
        
        return tsi.CallStartRes(id=call_id, trace_id=trace_id)
        
    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        """Record call end to offline storage."""
        # Extract entity and project from project_id  
        parts = req.end.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.end.project_id
            
        # Store call end data
        data = {
            "type": "call_end",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": req.end.model_dump(mode="json"),
        }
        
        self._write_to_file(entity, project, "calls", data)
        
        return tsi.CallEndRes()
        
    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        """Read calls from offline storage."""
        # This would need to scan through offline files to find the call
        # For now, return empty result
        logger.warning("call_read not fully implemented in offline mode")
        return tsi.CallReadRes(call=None)
        
    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        """Query calls from offline storage."""
        # This would need to scan through offline files
        # For now, return empty results
        logger.warning("calls_query not fully implemented in offline mode")
        return tsi.CallsQueryRes(calls=[])
        
    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        """Stream query calls from offline storage."""
        logger.warning("calls_query_stream not fully implemented in offline mode")
        return iter([])
        
    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        """Delete calls from offline storage."""
        logger.warning("calls_delete not supported in offline mode")
        return tsi.CallsDeleteRes()
        
    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        """Query call stats from offline storage."""
        logger.warning("calls_query_stats not fully implemented in offline mode")
        return tsi.CallsQueryStatsRes(count=0)
        
    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        """Update call in offline storage."""
        # Extract entity and project
        parts = req.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.project_id
            
        # Store call update
        data = {
            "type": "call_update",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {
                "project_id": req.project_id,
                "call_id": req.call_id,
                "display_name": req.display_name,
            },
        }
        
        self._write_to_file(entity, project, "calls", data)
        
        return tsi.CallUpdateRes()
        
    def call_start_batch(self, req: tsi.CallCreateBatchReq) -> tsi.CallCreateBatchRes:
        """Handle batch call creation in offline mode."""
        results = []
        for item in req.batch:
            if hasattr(item, "start"):
                res = self.call_start(tsi.CallStartReq(start=item.start))
                results.append(res)
            elif hasattr(item, "end"):
                res = self.call_end(tsi.CallEndReq(end=item.end))
                results.append(res)
        return tsi.CallCreateBatchRes(calls=results)
        
    # Op API
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        """Create op in offline storage."""
        parts = req.op_obj.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.op_obj.project_id
            
        data = {
            "type": "op_create",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": req.op_obj.model_dump(mode="json"),
        }
        
        self._write_to_file(entity, project, "ops", data)
        
        digest = generate_id()
        return tsi.OpCreateRes(digest=digest)
        
    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        """Read op from offline storage."""
        logger.warning("op_read not fully implemented in offline mode")
        return tsi.OpReadRes(op_obj=None)
        
    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        """Query ops from offline storage."""
        logger.warning("ops_query not fully implemented in offline mode")
        return tsi.OpQueryRes(op_objs=[])
        
    # Object API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        """Create object in offline storage."""
        parts = req.obj.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.obj.project_id
            
        data = {
            "type": "obj_create", 
            "timestamp": datetime.datetime.now().isoformat(),
            "data": req.obj.model_dump(mode="json"),
        }
        
        self._write_to_file(entity, project, "objects", data)
        
        digest = generate_id()
        return tsi.ObjCreateRes(digest=digest)
        
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        """Read object from offline storage."""
        logger.warning("obj_read not fully implemented in offline mode")
        return tsi.ObjReadRes(obj=None)
        
    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        """Query objects from offline storage."""
        logger.warning("objs_query not fully implemented in offline mode")
        return tsi.ObjQueryRes(objs=[])
        
    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        """Create table in offline storage."""
        parts = req.table.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.table.project_id
            
        data = {
            "type": "table_create",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": req.table.model_dump(mode="json"),
        }
        
        self._write_to_file(entity, project, "tables", data)
        
        digest = generate_id()
        return tsi.TableCreateRes(digest=digest)
        
    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        """Query table from offline storage."""
        logger.warning("table_query not fully implemented in offline mode")
        return tsi.TableQueryRes(rows=[])
        
    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        """Stream table query from offline storage."""
        logger.warning("table_query_stream not fully implemented in offline mode")
        return iter([])
        
    # Refs API
    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """Read refs batch from offline storage."""
        logger.warning("refs_read_batch not fully implemented in offline mode")
        return tsi.RefsReadBatchRes(vals=[])
        
    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        """Create file in offline storage."""
        parts = req.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.project_id
            
        # Save file content to disk
        file_id = generate_id()
        files_dir = self.offline_dir / entity / project / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = files_dir / file_id
        file_path.write_bytes(req.content)
        
        # Record file metadata
        data = {
            "type": "file_create",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {
                "project_id": req.project_id,
                "file_id": file_id,
                "name": req.name,
                "size": len(req.content),
            },
        }
        
        self._write_to_file(entity, project, "files_metadata", data)
        
        return tsi.FileCreateRes(digest=file_id)
        
    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        """Read file content from offline storage."""
        logger.warning("file_content_read not fully implemented in offline mode")
        return tsi.FileContentReadRes(content=b"")
        
    # Feedback API
    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        """Create feedback in offline storage."""
        parts = req.project_id.split("/")
        if len(parts) == 2:
            entity, project = parts
        else:
            entity = "offline"
            project = req.project_id
            
        feedback_id = generate_id()
        data = {
            "type": "feedback_create",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {
                **req.model_dump(mode="json"),
                "id": feedback_id,
            },
        }
        
        self._write_to_file(entity, project, "feedback", data)
        
        return tsi.FeedbackCreateRes(
            id=feedback_id,
            created_at=datetime.datetime.now(),
            wb_user_id="offline",
            payload=req.feedback,
        )
        
    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        """Query feedback from offline storage."""
        logger.warning("feedback_query not fully implemented in offline mode")
        return tsi.FeedbackQueryRes(result=[])
        
    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        """Purge feedback from offline storage."""
        logger.warning("feedback_purge not supported in offline mode")
        return tsi.FeedbackPurgeRes()
        
    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        """Create cost in offline storage."""
        logger.warning("cost_create not implemented in offline mode")
        return tsi.CostCreateRes()
        
    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        """Query costs from offline storage."""
        logger.warning("cost_query not implemented in offline mode")
        return tsi.CostQueryRes(results=[])
        
    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        """Purge costs from offline storage."""
        logger.warning("cost_purge not supported in offline mode")
        return tsi.CostPurgeRes()
        
    def server_info(self) -> ServerInfoRes:
        """Get server info for offline mode."""
        return ServerInfoRes(
            min_required_weave_python_version="0.0.0",
        )