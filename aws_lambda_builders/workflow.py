"""
Implementation of a base workflow
"""
import functools
import os
import logging

from collections import namedtuple

from aws_lambda_builders.binary_path import BinaryPath
from aws_lambda_builders.path_resolver import PathResolver
from aws_lambda_builders.validator import RuntimeValidator
from aws_lambda_builders.registry import DEFAULT_REGISTRY
from aws_lambda_builders.exceptions import (
    WorkflowFailedError,
    WorkflowUnknownError,
    MisMatchRuntimeError,
    RuntimeValidatorError,
)
from aws_lambda_builders.actions import ActionFailedError
from aws_lambda_builders.architecture import X86_64


LOG = logging.getLogger(__name__)


# Named tuple to express the capabilities supported by the builder.
# ``Language`` is the programming language. Ex: Python
# ``LangageFramework`` is the framework of particular language. Ex: PIP
# ``ApplicationFramework`` is the specific application framework used to write the code. Ex: Chalice
Capability = namedtuple("Capability", ["language", "dependency_manager", "application_framework"])


class BuildMode(object):

    DEBUG = "debug"
    RELEASE = "release"


# TODO: Move sanitize out to its own class.
def sanitize(func):  # pylint: disable=too-many-statements
    """
    sanitize the executable path of the runtime specified by validating it.
    :param func: Workflow's run method is sanitized
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):  # pylint: disable=too-many-statements
        valid_paths = {}
        invalid_paths = {}
        validation_errors = []
        # NOTE: we need to access binaries to get paths and resolvers, before validating.
        for binary, binary_checker in self.binaries.items():
            invalid_paths[binary] = []
            try:
                exec_paths = (
                    binary_checker.resolver.exec_paths
                    if not binary_checker.path_provided
                    else binary_checker.binary_path
                )
            except ValueError as ex:
                raise WorkflowFailedError(workflow_name=self.NAME, action_name="Resolver", reason=str(ex))
            for executable_path in exec_paths:
                try:
                    valid_path = binary_checker.validator.validate(executable_path)
                    if valid_path:
                        valid_paths[binary] = valid_path
                except MisMatchRuntimeError as ex:
                    LOG.debug("Invalid executable for %s at %s", binary, executable_path, exc_info=str(ex))
                    invalid_paths[binary].append(executable_path)

                except RuntimeValidatorError as ex:
                    LOG.debug("Runtime validation error for %s", binary, exc_info=str(ex))
                    if str(ex) not in validation_errors:
                        validation_errors.append(str(ex))

                if valid_paths.get(binary, None):
                    binary_checker.binary_path = valid_paths[binary]
                    break
        if validation_errors:
            raise WorkflowFailedError(
                workflow_name=self.NAME, action_name="Validation", reason="\n".join(validation_errors)
            )

        if len(self.binaries) != len(valid_paths):
            validation_failed_binaries = set(self.binaries.keys()).difference(valid_paths.keys())
            for validation_failed_binary in validation_failed_binaries:
                message = "Binary validation failed for {0}, searched for {0} in following locations  : {1} which did not satisfy constraints for runtime: {2}. Do you have {0} for runtime: {2} on your PATH?".format(
                    validation_failed_binary, invalid_paths[validation_failed_binary], self.runtime
                )
                validation_errors.append(message)
            raise WorkflowFailedError(
                workflow_name=self.NAME, action_name="Validation", reason="\n".join(validation_errors)
            )
        func(self, *args, **kwargs)

    return wrapper


class _WorkflowMetaClass(type):
    """
    A metaclass that maintains the registry of loaded builders
    """

    def __new__(mcs, name, bases, class_dict):
        """
        Add the builder to registry when loading the class
        """

        cls = type.__new__(mcs, name, bases, class_dict)

        # We don't want to register the base classes, so we simply return here.
        # Also, skip further steps if the class is marked for testing
        if cls.__name__ == "BaseWorkflow" or cls.__TESTING__:
            return cls

        # Validate class variables

        # All classes must provide a name
        if not isinstance(cls.NAME, str):
            raise ValueError("Workflow must provide a valid name")

        # All workflows must express their capabilities
        if not isinstance(cls.CAPABILITY, Capability):
            raise ValueError("Workflow '{}' must register valid capabilities".format(cls.NAME))

        LOG.debug("Registering workflow '%s' with capability '%s'", cls.NAME, cls.CAPABILITY)
        DEFAULT_REGISTRY[cls.CAPABILITY] = cls

        return cls


class BaseWorkflow(object, metaclass=_WorkflowMetaClass):
    """
    Default implementation of the builder workflow. It provides several useful capabilities out-of-box that help
    minimize the scope of build actions.
    """

    # Set this property if you are in the process of testing a workflow class. This will prevent the class from
    # being added to registry.
    __TESTING__ = False

    NAME = None

    # Capabilities supported by this builder. Must be an instance of `Capability` named tuple
    CAPABILITY = None

    # Optional list of manifests file/folder names supported by this workflow.
    SUPPORTED_MANIFESTS = []

    def __init__(
        self,
        source_dir,
        artifacts_dir,
        scratch_dir,
        manifest_path,
        runtime=None,
        executable_search_paths=None,
        optimizations=None,
        options=None,
        mode=BuildMode.RELEASE,
        download_dependencies=True,
        dependencies_dir=None,
        combine_dependencies=True,
        architecture=X86_64,
        is_building_layer=False,
        experimental_flags=None,
    ):
        # pylint: disable-msg=too-many-locals
        """
        Initialize the builder with given arguments. These arguments together form the "public API" that each
        build action must support at the minimum.

        Parameters
        ----------
        source_dir : str
            Path to a folder containing the source code
        artifacts_dir : str
            Path to a folder where the built artifacts should be placed
        scratch_dir : str
            Path to a directory that the workflow can use as scratch space. Workflows are expected to use this directory
            to write temporary files instead of ``/tmp`` or other OS-specific temp directories.
        manifest_path : str
            Path to the dependency manifest
        runtime : str, optional
            Optional, name of the AWS Lambda runtime that you are building for. This is sent to the builder for
            informational purposes, by default None
        executable_search_paths : list, optional
            Additional list of paths to search for executables required by the workflow, by default None
        optimizations : dict, optional
            dictionary of optimization flags to pass to the build action. **Not supported**, by default None
        options : dict, optional
            dictionary of options ot pass to build action. **Not supported**., by default None
        mode : str, optional
            Mode the build should produce, by default BuildMode.RELEASE
        download_dependencies: bool, optional
            Should download dependencies when building
        dependencies_dir : str, optional
            Path to folder the dependencies should be downloaded to
        combine_dependencies: bool, optional
            This flag will only be used if dependency_folder is specified. False will not copy dependencies
            from dependency_folder into build folder
        architecture : str, optional
            Architecture type either arm64 or x86_64 for which the build will be based on in AWS lambda, by default X86_64

        is_building_layer: bool, optional
            Boolean flag which will be set True if current build operation is being executed for layers

        experimental_flags: list, optional
            List of strings, which will indicate enabled experimental flags for the current build session
        """

        self.source_dir = source_dir
        self.artifacts_dir = artifacts_dir
        self.scratch_dir = scratch_dir
        self.manifest_path = manifest_path
        self.runtime = runtime
        self.optimizations = optimizations
        self.options = options
        self.executable_search_paths = executable_search_paths
        self.mode = mode
        self.download_dependencies = download_dependencies
        self.dependencies_dir = dependencies_dir
        self.combine_dependencies = combine_dependencies
        self.architecture = architecture
        self.is_building_layer = is_building_layer
        self.experimental_flags = experimental_flags if experimental_flags else []

        # Actions are registered by the subclasses as they seem fit
        self.actions = []
        self._binaries = {}

    def is_supported(self):
        """
        Is the given manifest supported? If the workflow exposes no manifests names, then we it is assumed that
        we don't have a restriction
        """

        if self.SUPPORTED_MANIFESTS:
            return os.path.basename(self.manifest_path) in self.SUPPORTED_MANIFESTS

        return True

    def get_resolvers(self):
        """
        Non specialized path resolver that just returns the list of executable for the runtime on the path.
        """
        return [
            PathResolver(
                runtime=self.runtime,
                binary=self.CAPABILITY.language,
                executable_search_paths=self.executable_search_paths,
            )
        ]

    def get_validators(self):
        """
        No-op validator that does not validate the runtime_path.
        """
        return [RuntimeValidator(runtime=self.runtime, architecture=self.architecture)]

    @property
    def binaries(self):
        if not self._binaries:
            resolvers = self.get_resolvers()
            validators = self.get_validators()
            self._binaries = {
                resolver.binary: BinaryPath(resolver=resolver, validator=validator, binary=resolver.binary)
                for resolver, validator in zip(resolvers, validators)
            }
        return self._binaries

    @binaries.setter
    def binaries(self, binaries):
        self._binaries = binaries

    @sanitize
    def run(self):
        """
        Actually perform the build by executing registered actions.

        :raises WorkflowFailedError: If the workflow does not contain any actions or if one of the actions ran into
            an error

        :raises WorkflowUnknownError: If one of the actions in the workflow raised an unhandled exception
        """

        LOG.debug("Running workflow '%s'", self.NAME)

        if not self.actions:
            raise WorkflowFailedError(
                workflow_name=self.NAME, action_name=None, reason="Workflow does not have any actions registered"
            )

        for action in self.actions:
            action_info = "{}:{}".format(self.NAME, action.NAME)

            LOG.info("Running %s", action_info)

            try:
                action.execute()

                LOG.debug("%s succeeded", action_info)

            except ActionFailedError as ex:
                LOG.debug("%s failed", action_info, exc_info=ex)

                raise WorkflowFailedError(workflow_name=self.NAME, action_name=action.NAME, reason=str(ex))
            except Exception as ex:

                LOG.debug("%s raised unhandled exception", action_info, exc_info=ex)

                raise WorkflowUnknownError(workflow_name=self.NAME, action_name=action.NAME, reason=str(ex))

    def __repr__(self):
        """
        Pretty prints information about this workflow.

        Sample output:
            Workflow=MyWorkflow
            Actions=
                Name=Action1, Purpose=COPY_SOURCE, Description=Copies source code
                Name=Action2, Purpose=RESOLVE_DEPENDENCIES, Description=Resolves dependencies
                Name=Action3, Purpose=COMPILE_SOURCE, Description=Compiles code
        """
        return "Workflow={}\nActions=\n\t{}".format(self.NAME, "\n\t".join(map(str, self.actions)))
