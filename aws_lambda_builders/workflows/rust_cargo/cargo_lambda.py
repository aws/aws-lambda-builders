"""
Wrapper around calling Cargo Lambda through a subprocess.
"""

import io
import json
import logging
import os
import shutil
import subprocess
import threading

from .exceptions import CargoLambdaExecutionException
from .utils import OSUtils

LOG = logging.getLogger(__name__)


class SubprocessCargoLambda(object):
    """
    Wrapper around the Cargo Lambda command line utility, making it
    easy to consume execution results.
    """

    def __init__(self, which, executable_search_paths=None, osutils=OSUtils()):
        """
        Parameters
        ----------
        which : aws_lambda_builders.utils.which
            Function to get paths which conform to the given mode on the PATH
            with the prepended additional search paths

        executable_search_paths : list, optional
            List of paths to the NPM package binary utilities. This will
            be used to find embedded esbuild at runtime if present in the package

        osutils : aws_lambda_builders.workflows.rust_cargo.utils.OSUtils, optional
            An instance of OS Utilities for file manipulation
        """
        self._which = which
        self._executable_search_paths = executable_search_paths
        self._osutils = osutils
        self._workspace_layout_cache = {}

    def check_cargo_lambda_installation(self):
        """
        Checks if Cargo Lambda is in the system

        Returns
        -------
        str
            Path to the cargo-lambda binary

        Raises
        ------
        CargoLambdaExecutionException:
            Raised when Cargo Lambda is not installed in the system to run the command.
        """

        LOG.debug("checking for cargo-lambda")
        binaries = self._which("cargo-lambda", executable_search_paths=self._executable_search_paths)
        LOG.debug("potential cargo-lambda binaries: %s", binaries)

        if binaries:
            return binaries[0]
        else:
            raise CargoLambdaExecutionException(
                message="Cannot find Cargo Lambda. "
                "Cargo Lambda must be installed on the host machine to use this feature. "
                "Follow the gettings started guide to learn how to install it: "
                "https://www.cargo-lambda.info/guide/getting-started.html"
            )

    def resolve_workspace_layout(self, cargo_path, source_dir):
        """
        Resolves the Cargo target directory and the binary produced for ``source_dir``.

        A single ``cargo metadata`` call yields both:

        - ``target_directory`` is the workspace's shared ``target`` directory.
          For a Cargo workspace member this is the workspace root's ``target``,
          which cargo shares across every member. Building each function into
          that shared directory lets cargo reuse compiled dependencies across
          the separate per-function builds that ``sam build`` runs, instead of
          recompiling the whole dependency tree once per function. For a
          standalone project it is the project's own ``target`` -- the location
          used before this change.

        - ``binary_name`` is the name of the ``bin`` target defined by the
          package whose manifest lives in ``source_dir``. Because every member
          now builds into the same ``target/lambda`` directory, the copy step
          can no longer assume that directory holds a single binary; this name
          tells it which one belongs to the function being built.

        Results are cached per ``source_dir``.

        Parameters
        ----------
        cargo_path : str
            Path to the ``cargo`` binary.

        source_dir : str
            Path to the folder containing the function's source code.

        Returns
        -------
        dict
            ``{"target_directory": str or None, "binary_name": str or None}``.
            Either value is ``None`` when it cannot be resolved, in which case
            callers fall back to the previous behavior.
        """

        if source_dir in self._workspace_layout_cache:
            return self._workspace_layout_cache[source_dir]

        layout = {"target_directory": None, "binary_name": None}
        command = [cargo_path, "metadata", "--no-deps", "--format-version", "1"]
        LOG.debug("Resolving cargo workspace layout: %s", " ".join(command))
        try:
            process = self._osutils.popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=source_dir)
            out, err = process.communicate()
            if process.returncode == 0:
                metadata = json.loads(out.decode("utf-8"))
                layout["target_directory"] = metadata.get("target_directory")
                layout["binary_name"] = self._find_binary_name(metadata, source_dir)
                self._warn_on_colliding_binaries(metadata)
            else:
                LOG.debug(
                    "Could not resolve cargo workspace layout, falling back to previous behavior: %s",
                    err.decode("utf-8", "replace").strip(),
                )
        except (OSError, ValueError, json.JSONDecodeError) as ex:
            LOG.debug("Could not run cargo metadata, falling back to previous behavior: %s", ex)

        self._workspace_layout_cache[source_dir] = layout
        return layout

    @staticmethod
    def _find_binary_name(metadata, source_dir):
        """
        Finds the bin target name of the package whose manifest is in source_dir.
        """
        # cargo metadata emits absolute, symlink-resolved manifest paths, so resolve
        # both operands the same way; os.path.normpath alone would never match a
        # relative source_dir against cargo's absolute path.
        member_manifest = os.path.realpath(os.path.join(source_dir, "Cargo.toml"))
        for package in metadata.get("packages", []):
            if os.path.realpath(package.get("manifest_path", "")) != member_manifest:
                continue
            bin_targets = [target["name"] for target in package.get("targets", []) if "bin" in target.get("kind", [])]
            if len(bin_targets) == 1:
                return bin_targets[0]
            # A package with zero or several bins is ambiguous; let the copy step
            # fall back to its directory-listing heuristic.
            LOG.debug("Package %s does not have exactly one bin target: %s", package.get("name"), bin_targets)
            return None
        return None

    @staticmethod
    def _warn_on_colliding_binaries(metadata):
        """
        Warns when workspace members share a bin target name.

        Since every member now builds into the same target/lambda directory,
        two bins with the same name (e.g. several packages each defining a
        `bootstrap` bin) compile to the same path and overwrite each other.
        `sam build` still produces correct artifacts because it copies each
        function's binary out immediately after building it, but the shared
        output is fragile; unique bin names per function avoid it.
        """
        packages_by_bin = {}
        for package in metadata.get("packages", []):
            for target in package.get("targets", []):
                if "bin" in target.get("kind", []):
                    packages_by_bin.setdefault(target["name"], []).append(package.get("name"))

        for bin_name, owners in packages_by_bin.items():
            if len(owners) > 1:
                LOG.warning(
                    "Multiple workspace packages define a bin named '%s' (%s). They build to the same path in the "
                    "shared target directory and overwrite each other; give each function a unique bin name to "
                    "avoid relying on build ordering.",
                    bin_name,
                    ", ".join(sorted(owners)),
                )

    def run(self, command, cwd):
        """
        Runs the build command.

        Parameters
        ----------
        command : str
            Cargo Lambda command to run

        cwd : str
            Directory where to execute the command (defaults to current dir)

        Returns
        -------
        str
            Text of the standard output from the command

        Raises
        ------
        CargoLambdaExecutionException:
            Raised when the command executes with a non-zero return code. The exception will
            contain the text of the standard error output from the command.
        """

        self.check_cargo_lambda_installation()

        LOG.debug("Executing cargo-lambda: %s", " ".join(command))
        if LOG.isEnabledFor(logging.DEBUG):
            if "RUST_LOG" not in os.environ:
                os.environ["RUST_LOG"] = "debug"
            LOG.debug("RUST_LOG environment variable set to `%s`", os.environ.get("RUST_LOG"))

        cargo_env = dict(os.environ)
        if not cargo_env.get("CARGO_TARGET_DIR"):
            # Point every build at the workspace's shared target directory so cargo
            # compiles dependencies once rather than once per function. For a standalone
            # project this is the project's own target directory, matching the previous
            # behavior. An explicit CARGO_TARGET_DIR in the environment is left untouched.
            # The first element of command is the cargo binary path.
            target_directory = self.resolve_workspace_layout(command[0], cwd)["target_directory"]
            # Fall back to the relative "target" the workflow used before this change when
            # metadata is unavailable, so the build still lands where the copy step (which
            # falls back the same way) looks for it.
            cargo_env["CARGO_TARGET_DIR"] = target_directory or "target"

        cargo_process = self._osutils.popen(
            command,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=cwd,
            env=cargo_env,
        )
        stdout = ""
        # Create a buffer and use a thread to gather the stderr stream into the buffer
        stderr_buf = io.BytesIO()
        stderr_thread = threading.Thread(
            target=shutil.copyfileobj, args=(cargo_process.stderr, stderr_buf), daemon=True
        )
        stderr_thread.start()

        # Log every stdout line by iterating
        for line in cargo_process.stdout:
            decoded_line = line.decode("utf-8").strip()
            LOG.info(decoded_line)
            # Gather total stdout
            stdout += decoded_line

        # Wait for the process to exit and stderr thread to end.
        return_code = cargo_process.wait()
        stderr_thread.join()

        if return_code != 0:
            # Raise an Error with the appropriate value from the stderr buffer.
            raise CargoLambdaExecutionException(message=stderr_buf.getvalue().decode("utf8").strip())
        return stdout
