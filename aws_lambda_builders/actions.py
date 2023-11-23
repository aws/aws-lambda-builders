"""
Definition of actions used in the workflow
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Iterator, Optional, Set, Tuple, Union

from aws_lambda_builders import utils
from aws_lambda_builders.utils import copytree, create_symlink_or_copy

LOG = logging.getLogger(__name__)


class ActionFailedError(Exception):
    """
    Base class for exception raised when action failed to complete. Use this to express well-known failure scenarios.
    """

    pass


class Purpose(object):
    """
    Enum like object to describe the purpose of each action.
    """

    # Action is identifying dependencies, downloading, compiling and resolving them
    RESOLVE_DEPENDENCIES = "RESOLVE_DEPENDENCIES"

    # Action is copying source code
    COPY_SOURCE = "COPY_SOURCE"

    # Action is linking source code
    LINK_SOURCE = "LINK_SOURCE"

    # Action is copying dependencies
    COPY_DEPENDENCIES = "COPY_DEPENDENCIES"

    # Action is moving dependencies
    MOVE_DEPENDENCIES = "MOVE_DEPENDENCIES"

    # Action is compiling source code
    COMPILE_SOURCE = "COMPILE_SOURCE"

    # Action is cleaning up the target folder
    CLEAN_UP = "CLEAN_UP"

    @staticmethod
    def has_value(item):
        return item in Purpose.__dict__.values()


class _ActionMetaClass(type):
    def __new__(mcs, name, bases, class_dict):
        cls = type.__new__(mcs, name, bases, class_dict)

        if cls.__name__ in ["BaseAction", "NodejsNpmInstallOrUpdateBaseAction"]:
            return cls

        # Validate class variables
        # All classes must provide a name
        if not isinstance(cls.NAME, str):
            raise ValueError("Action must provide a valid name")

        if not Purpose.has_value(cls.PURPOSE):
            raise ValueError("Action must provide a valid purpose")

        return cls


class BaseAction(object, metaclass=_ActionMetaClass):
    """
    Base class for all actions. It does not provide any implementation.
    """

    # Every action must provide a name
    NAME = None

    # Optional description explaining what this action is about. Used to print help text
    DESCRIPTION = ""

    # What is this action meant for? Must be a valid instance of `Purpose` class
    PURPOSE = None

    def execute(self):
        """
        Runs the action. This method should complete the action, and if it fails raise appropriate exceptions.

        :raises lambda_builders.actions.ActionFailedError: Instance of this class if something went wrong with the
            action
        """
        raise NotImplementedError("execute")

    def __repr__(self):
        return "Name={}, Purpose={}, Description={}".format(self.NAME, self.PURPOSE, self.DESCRIPTION)


class CopySourceAction(BaseAction):
    NAME = "CopySource"

    DESCRIPTION = "Copying source code while skipping certain commonly excluded files"

    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, source_dir, dest_dir, excludes=None, maintain_symlinks=False):
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.excludes = excludes or []
        self.maintain_symlinks = maintain_symlinks

    def execute(self):
        copytree(
            self.source_dir,
            self.dest_dir,
            ignore=shutil.ignore_patterns(*self.excludes),
            maintain_symlinks=self.maintain_symlinks,
        )


class LinkSourceAction(BaseAction):
    NAME = "LinkSource"

    DESCRIPTION = "Linking source code to the target folder"

    PURPOSE = Purpose.LINK_SOURCE

    def __init__(self, source_dir, dest_dir):
        self._source_dir = source_dir
        self._dest_dir = dest_dir

    def execute(self):
        source_files = set(os.listdir(self._source_dir))

        for source_file in source_files:
            source_path = Path(self._source_dir, source_file)
            destination_path = Path(self._dest_dir, source_file)
            if destination_path.exists():
                os.remove(destination_path)
            else:
                os.makedirs(destination_path.parent, exist_ok=True)
            utils.create_symlink_or_copy(str(source_path), str(destination_path))


class LinkSinglePathAction(BaseAction):
    NAME = "LinkSource"

    DESCRIPTION = "Creates symbolic link at destination, pointing to source"

    PURPOSE = Purpose.LINK_SOURCE

    def __init__(self, source: Union[str, os.PathLike], dest: Union[str, os.PathLike]):
        self._source = source
        self._dest = dest

    def execute(self):
        source_path = Path(self._source)
        destination_path = Path(self._dest)
        if not source_path.exists():
            # Source path doesn't exist, nothing to symlink
            LOG.debug("Source path %s does not exist, skipping generating symlink", source_path)
            return
        if not destination_path.exists():
            os.makedirs(destination_path.parent, exist_ok=True)
        utils.create_symlink_or_copy(str(self._source), str(destination_path))


class CopyDependenciesAction(BaseAction):
    NAME = "CopyDependencies"

    DESCRIPTION = "Copying dependencies while skipping source file"

    PURPOSE = Purpose.COPY_DEPENDENCIES

    def __init__(self, source_dir, artifact_dir, destination_dir, maintain_symlinks=False, manifest_dir=None):
        self.source_dir = source_dir
        self.artifact_dir = artifact_dir
        self.dest_dir = destination_dir
        self.manifest_dir = manifest_dir
        self.maintain_symlinks = maintain_symlinks

    def execute(self):
        deps_manager = DependencyManager(self.source_dir, self.artifact_dir, self.dest_dir, self.manifest_dir)

        for dependencies_source, new_destination in deps_manager.yield_source_dest():
            if os.path.islink(dependencies_source) and self.maintain_symlinks:
                os.makedirs(os.path.dirname(new_destination), exist_ok=True)
                linkto = os.readlink(dependencies_source)
                create_symlink_or_copy(linkto, new_destination)
                shutil.copystat(dependencies_source, new_destination, follow_symlinks=False)
            elif os.path.isdir(dependencies_source):
                copytree(dependencies_source, new_destination, maintain_symlinks=self.maintain_symlinks)
            else:
                os.makedirs(os.path.dirname(new_destination), exist_ok=True)
                shutil.copy2(dependencies_source, new_destination)


class MoveDependenciesAction(BaseAction):
    NAME = "MoveDependencies"

    DESCRIPTION = "Moving dependencies while skipping source file"

    PURPOSE = Purpose.MOVE_DEPENDENCIES

    def __init__(self, source_dir, artifact_dir, destination_dir, manifest_dir=None):
        self.source_dir = source_dir
        self.artifact_dir = artifact_dir
        self.dest_dir = destination_dir
        self.manifest_dir = manifest_dir

    def execute(self):
        deps_manager = DependencyManager(self.source_dir, self.artifact_dir, self.dest_dir, self.manifest_dir)

        for dependencies_source, new_destination in deps_manager.yield_source_dest():
            # shutil.move can't create subfolders if this is the first file in that folder
            if os.path.isfile(dependencies_source):
                os.makedirs(os.path.dirname(new_destination), exist_ok=True)

            shutil.move(dependencies_source, new_destination)


class CleanUpAction(BaseAction):
    """
    Class for cleaning the directory. It will clean all the files in the directory but doesn't delete the directory
    """

    NAME = "CleanUp"

    DESCRIPTION = "Cleaning up the target folder"

    PURPOSE = Purpose.CLEAN_UP

    def __init__(self, target_dir):
        self.target_dir = target_dir

    def execute(self):
        if not os.path.isdir(self.target_dir):
            LOG.debug("Clean up action: %s does not exist and will be skipped.", str(self.target_dir))
            return
        targets = os.listdir(self.target_dir)
        LOG.debug("Clean up action: folder %s will be cleaned", str(self.target_dir))

        for name in targets:
            target_path = os.path.join(self.target_dir, name)
            LOG.debug("Clean up action: %s is deleted", str(target_path))

            if os.path.islink(target_path):
                os.unlink(target_path)
            elif os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)


class DependencyManager:
    """
    Class for handling the management of dependencies between directories
    """

    # Ignore these files when comparing against which dependencies to move
    # This allows for the installation of dependencies in the source directory
    IGNORE_LIST = ["node_modules"]

    def __init__(self, source_dir, artifact_dir, destination_dir, manifest_dir=None) -> None:
        self._source_dir: str = source_dir
        self._artifact_dir: str = artifact_dir
        self._dest_dir: str = destination_dir
        self._manifest_dir: Optional[str] = manifest_dir
        self._dependencies: Set[str] = set()

    def yield_source_dest(self) -> Iterator[Tuple[str, str]]:
        self._set_dependencies()
        for dep in self._dependencies:
            yield os.path.join(self._artifact_dir, dep), os.path.join(self._dest_dir, dep)

    def _set_dependencies(self) -> None:
        source = self._get_source_files_exclude_deps(self._source_dir)
        manifest = self._get_source_files_exclude_deps(self._manifest_dir) if self._manifest_dir else set()
        artifact = set(os.listdir(self._artifact_dir))
        self._dependencies = artifact - (source.union(manifest))

    def _get_source_files_exclude_deps(self, dir_path: str) -> Set[str]:
        source_files = set(os.listdir(dir_path))
        for item in self.IGNORE_LIST:
            if item in source_files:
                source_files.remove(item)
        return source_files
