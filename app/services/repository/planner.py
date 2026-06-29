import os
from typing import List, Dict, Any
from app.workflows.context import EngineeringTask
from app.utils.logger import logger

class FeaturePlanner:
    """Deterministically groups changed files into distinct EngineeringTasks."""
    
    @staticmethod
    def extract_feature_name(file_path: str) -> str:
        """Extracts a base feature/component name from a file path."""
        basename = os.path.basename(file_path)
        name, _ = os.path.splitext(basename)
        
        # Strip common prefixes/suffixes to group files (e.g. test_payment.py -> payment)
        if name.startswith("test_"):
            name = name[5:]
        if name.endswith("_test"):
            name = name[:-5]
        if name.endswith("_repository"):
            name = name[:-11]
        if name.endswith("_service"):
            name = name[:-8]
        if name.endswith("_controller"):
            name = name[:-11]
            
        return name
        
    @staticmethod
    def create_tasks(changed_files: List[str], structured_diff: Dict[str, Any]) -> List[EngineeringTask]:
        """Groups files into tasks and filters the structured diff for each task."""
        
        if not changed_files:
            return []
            
        # Group files by extracted feature name
        feature_groups: Dict[str, List[str]] = {}
        for path in changed_files:
            if not path.endswith(".py"):
                # Currently only processing Python files for features
                continue
            feature_name = FeaturePlanner.extract_feature_name(path)
            if feature_name not in feature_groups:
                feature_groups[feature_name] = []
            feature_groups[feature_name].append(path)
            
        tasks: List[EngineeringTask] = []
        
        for feature_name, files in feature_groups.items():
            # Build a structured_diff specifically for this task
            task_diff = {"added": [], "modified": [], "deleted": [], "renamed": []}
            
            for change_type in ["added", "modified", "deleted"]:
                for diff_item in structured_diff.get(change_type, []):
                    if diff_item.get("path") in files:
                        task_diff[change_type].append(diff_item)
                        
            for diff_item in structured_diff.get("renamed", []):
                if diff_item.get("new_path") in files or diff_item.get("old_path") in files:
                    task_diff["renamed"].append(diff_item)
                    
            task = EngineeringTask(
                feature_name=feature_name,
                related_files=files,
                structured_diff=task_diff
            )
            tasks.append(task)
            
        logger.info(f"Feature Planner decomposed {len(changed_files)} files into {len(tasks)} independent tasks.")
        return tasks
