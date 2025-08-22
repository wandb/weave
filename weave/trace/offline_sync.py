"""Sync offline trace data to a remote server."""

import gzip
import json
import logging
from pathlib import Path
from typing import Any, Optional

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.offline_trace_server import DEFAULT_OFFLINE_DIR

logger = logging.getLogger(__name__)


class OfflineDataSyncer:
    """Syncs offline trace data to a remote server."""
    
    def __init__(
        self,
        remote_server: tsi.TraceServerInterface,
        offline_dir: Optional[Path] = None,
    ):
        """Initialize the syncer.
        
        Args:
            remote_server: The remote server to sync to
            offline_dir: Directory containing offline data
        """
        self.remote_server = remote_server
        self.offline_dir = Path(offline_dir or DEFAULT_OFFLINE_DIR)
        
    def _read_jsonl_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Read a JSON Lines file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of JSON objects from the file
        """
        records = []
        
        if file_path.suffix == ".gz":
            open_func = gzip.open
            mode = "rt"
        else:
            open_func = open
            mode = "r"
            
        try:
            with open_func(file_path, mode, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            
        return records
        
    def _sync_calls(self, entity: str, project: str) -> tuple[int, int]:
        """Sync call data for a project.
        
        Args:
            entity: Entity name
            project: Project name
            
        Returns:
            Tuple of (synced_count, error_count)
        """
        calls_dir = self.offline_dir / entity / project / "calls"
        if not calls_dir.exists():
            return 0, 0
            
        synced_count = 0
        error_count = 0
        
        # Process all call files
        for file_path in sorted(calls_dir.glob("*.jsonl*")):
            records = self._read_jsonl_file(file_path)
            
            for record in records:
                try:
                    if record["type"] == "call_start":
                        # Reconstruct call start request
                        req = tsi.CallStartReq(
                            start=tsi.StartedCallSchemaForInsert.model_validate(record["data"])
                        )
                        self.remote_server.call_start(req)
                        synced_count += 1
                        
                    elif record["type"] == "call_end":
                        # Reconstruct call end request
                        req = tsi.CallEndReq(
                            end=tsi.EndedCallSchemaForInsert.model_validate(record["data"])
                        )
                        self.remote_server.call_end(req)
                        synced_count += 1
                        
                    elif record["type"] == "call_update":
                        # Reconstruct call update request
                        data = record["data"]
                        req = tsi.CallUpdateReq(
                            project_id=data["project_id"],
                            call_id=data["call_id"],
                            display_name=data.get("display_name"),
                        )
                        self.remote_server.call_update(req)
                        synced_count += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing call record: {e}")
                    error_count += 1
                    
            # Optionally rename file to mark as synced
            if synced_count > 0 and error_count == 0:
                synced_path = file_path.parent / f"{file_path.stem}.synced{file_path.suffix}"
                file_path.rename(synced_path)
                
        return synced_count, error_count
        
    def _sync_ops(self, entity: str, project: str) -> tuple[int, int]:
        """Sync op data for a project.
        
        Args:
            entity: Entity name
            project: Project name
            
        Returns:
            Tuple of (synced_count, error_count)
        """
        ops_dir = self.offline_dir / entity / project / "ops"
        if not ops_dir.exists():
            return 0, 0
            
        synced_count = 0
        error_count = 0
        
        for file_path in sorted(ops_dir.glob("*.jsonl*")):
            records = self._read_jsonl_file(file_path)
            
            for record in records:
                try:
                    if record["type"] == "op_create":
                        req = tsi.OpCreateReq(
                            op_obj=tsi.OpSchemaForInsert.model_validate(record["data"])
                        )
                        self.remote_server.op_create(req)
                        synced_count += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing op record: {e}")
                    error_count += 1
                    
            if synced_count > 0 and error_count == 0:
                synced_path = file_path.parent / f"{file_path.stem}.synced{file_path.suffix}"
                file_path.rename(synced_path)
                
        return synced_count, error_count
        
    def _sync_objects(self, entity: str, project: str) -> tuple[int, int]:
        """Sync object data for a project.
        
        Args:
            entity: Entity name
            project: Project name
            
        Returns:
            Tuple of (synced_count, error_count)
        """
        objects_dir = self.offline_dir / entity / project / "objects"
        if not objects_dir.exists():
            return 0, 0
            
        synced_count = 0
        error_count = 0
        
        for file_path in sorted(objects_dir.glob("*.jsonl*")):
            records = self._read_jsonl_file(file_path)
            
            for record in records:
                try:
                    if record["type"] == "obj_create":
                        req = tsi.ObjCreateReq(
                            obj=tsi.ObjSchemaForInsert.model_validate(record["data"])
                        )
                        self.remote_server.obj_create(req)
                        synced_count += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing object record: {e}")
                    error_count += 1
                    
            if synced_count > 0 and error_count == 0:
                synced_path = file_path.parent / f"{file_path.stem}.synced{file_path.suffix}"
                file_path.rename(synced_path)
                
        return synced_count, error_count
        
    def _sync_feedback(self, entity: str, project: str) -> tuple[int, int]:
        """Sync feedback data for a project.
        
        Args:
            entity: Entity name
            project: Project name
            
        Returns:
            Tuple of (synced_count, error_count)
        """
        feedback_dir = self.offline_dir / entity / project / "feedback"
        if not feedback_dir.exists():
            return 0, 0
            
        synced_count = 0
        error_count = 0
        
        for file_path in sorted(feedback_dir.glob("*.jsonl*")):
            records = self._read_jsonl_file(file_path)
            
            for record in records:
                try:
                    if record["type"] == "feedback_create":
                        data = record["data"]
                        # Remove the offline-generated id since server will create its own
                        data.pop("id", None)
                        req = tsi.FeedbackCreateReq.model_validate(data)
                        self.remote_server.feedback_create(req)
                        synced_count += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing feedback record: {e}")
                    error_count += 1
                    
            if synced_count > 0 and error_count == 0:
                synced_path = file_path.parent / f"{file_path.stem}.synced{file_path.suffix}"
                file_path.rename(synced_path)
                
        return synced_count, error_count
        
    def _sync_files(self, entity: str, project: str) -> tuple[int, int]:
        """Sync file data for a project.
        
        Args:
            entity: Entity name
            project: Project name
            
        Returns:
            Tuple of (synced_count, error_count)
        """
        files_dir = self.offline_dir / entity / project / "files"
        metadata_dir = self.offline_dir / entity / project / "files_metadata"
        
        if not metadata_dir.exists():
            return 0, 0
            
        synced_count = 0
        error_count = 0
        
        for file_path in sorted(metadata_dir.glob("*.jsonl*")):
            records = self._read_jsonl_file(file_path)
            
            for record in records:
                try:
                    if record["type"] == "file_create":
                        data = record["data"]
                        file_id = data["file_id"]
                        
                        # Read the actual file content
                        content_path = files_dir / file_id
                        if content_path.exists():
                            content = content_path.read_bytes()
                            
                            req = tsi.FileCreateReq(
                                project_id=data["project_id"],
                                name=data["name"],
                                content=content,
                            )
                            self.remote_server.file_create(req)
                            synced_count += 1
                            
                            # Delete the synced file
                            content_path.unlink()
                            
                except Exception as e:
                    logger.error(f"Error syncing file record: {e}")
                    error_count += 1
                    
            if synced_count > 0 and error_count == 0:
                synced_path = file_path.parent / f"{file_path.stem}.synced{file_path.suffix}"
                file_path.rename(synced_path)
                
        return synced_count, error_count
        
    def sync_project(self, entity: str, project: str) -> dict[str, tuple[int, int]]:
        """Sync all data for a project.
        
        Args:
            entity: Entity name
            project: Project name
            
        Returns:
            Dict mapping data type to (synced_count, error_count)
        """
        logger.info(f"Syncing offline data for {entity}/{project}")
        
        # Ensure project exists on remote
        self.remote_server.ensure_project_exists(entity, project)
        
        results = {}
        
        # Sync different data types in order
        results["ops"] = self._sync_ops(entity, project)
        results["objects"] = self._sync_objects(entity, project)
        results["calls"] = self._sync_calls(entity, project)
        results["feedback"] = self._sync_feedback(entity, project)
        results["files"] = self._sync_files(entity, project)
        
        # Log summary
        for data_type, (synced, errors) in results.items():
            if synced > 0 or errors > 0:
                logger.info(f"  {data_type}: {synced} synced, {errors} errors")
                
        return results
        
    def sync_all(self) -> dict[str, dict[str, tuple[int, int]]]:
        """Sync all offline data.
        
        Returns:
            Nested dict of entity -> project -> data_type -> (synced_count, error_count)
        """
        if not self.offline_dir.exists():
            logger.info("No offline data to sync")
            return {}
            
        all_results = {}
        
        # Iterate through all entities and projects
        for entity_dir in self.offline_dir.iterdir():
            if entity_dir.is_dir():
                entity = entity_dir.name
                all_results[entity] = {}
                
                for project_dir in entity_dir.iterdir():
                    if project_dir.is_dir():
                        project = project_dir.name
                        results = self.sync_project(entity, project)
                        all_results[entity][project] = results
                        
        return all_results
        
    def clean_synced_files(self, older_than_days: int = 7) -> int:
        """Clean up old synced files.
        
        Args:
            older_than_days: Delete synced files older than this many days
            
        Returns:
            Number of files deleted
        """
        import time
        
        deleted_count = 0
        cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)
        
        for synced_file in self.offline_dir.rglob("*.synced.*"):
            if synced_file.stat().st_mtime < cutoff_time:
                try:
                    synced_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting {synced_file}: {e}")
                    
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old synced files")
            
        return deleted_count