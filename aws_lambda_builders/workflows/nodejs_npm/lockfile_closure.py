"""
Derive a workspace member's production dependency closure from a lockfile, with no npm subprocess.

Replaces `npm ls --all --parseable --omit=dev` for the #933 artifact-narrowing step. Only
lockfileVersion 2 and 3 carry the `packages` map this needs, so callers fall back to asking npm when
this answers None.

Read npm's HIDDEN lockfile, `<project_root>/node_modules/.package-lock.json`, never the project's own
`package-lock.json`: npm writes the hidden one to describe the tree it actually reified, and the
in-source install runs `npm install --no-save`, which leaves the project lockfile untouched. A manifest
listing a dependency the project lockfile has not recorded yet therefore installs the package while the
project lockfile still denies it exists - and a closure read from that file drops it from the artifacts.
See aws/aws-lambda-builders#938.

Returns the same thing npm's --parseable output gives: absolute directories, real paths, one per
resolved package -- including workspace dependencies reported as their own source directory.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set

LOG = logging.getLogger(__name__)

# lockfileVersion 1 predates the per-path `packages` map this resolver reads
MINIMUM_LOCKFILE_VERSION = 2

# npm's record of the tree it reified, written on every install from npm 7 on
HIDDEN_LOCKFILE = os.path.join("node_modules", ".package-lock.json")


def hidden_lockfile_path(project_root: str) -> str:
    """Where npm records the tree it installed under `project_root`."""
    return os.path.join(project_root, HIDDEN_LOCKFILE)


def _describes_the_installed_tree(project_root: str) -> bool:
    """
    Is npm's hidden lockfile still a true record of `node_modules`?

    npm's own test, from its `package-lock.json` docs: the hidden lockfile counts only while its mtime
    is at least as recent as the tree it describes, because "if another CLI mutates the tree in any
    way, this will be detected, and the hidden lockfile will be ignored". Reading it without that test
    would trust a file npm itself would discard.

    `node_modules` alone, not every package folder: its mtime moves whenever a top-level entry is added
    or removed, which is what another package manager rewriting the tree does, and one `stat` keeps this
    cheaper than the `npm ls` it exists to avoid. `>=`, not `>`: a fresh install writes the two in the
    same clock tick, so `>` would send every first build down the fallback.
    """
    try:
        hidden = os.path.getmtime(hidden_lockfile_path(project_root))
        tree = os.path.getmtime(os.path.join(project_root, "node_modules"))
    except OSError:
        return False
    return hidden >= tree


def _resolve_key(packages: Dict, from_key: str, name: str) -> Optional[str]:
    """
    Find the packages-map key that `name` resolves to when required from `from_key`.

    Mirrors node's resolution: walk up the directory chain looking for node_modules/<name>, which in
    the lockfile is spelled as a key. `from_key` is "" for the root, "endpoints/orders" for a
    workspace member, or "node_modules/express" for an installed package.
    """
    prefix = from_key
    while True:
        candidate = f"{prefix}/node_modules/{name}" if prefix else f"node_modules/{name}"
        if candidate in packages:
            return candidate
        if not prefix:
            return None
        # strip one path segment and try again, which is what walking up node_modules means
        prefix = prefix.rsplit("/", 1)[0] if "/" in prefix else ""
        if prefix.endswith("/node_modules"):
            prefix = prefix[: -len("/node_modules")]


def _entry_dir(project_root: str, key: str, entry: Dict) -> str:
    """The directory a packages-map entry lives in."""
    # a workspace link points at the real source directory rather than the link's own path
    if entry.get("link") and entry.get("resolved"):
        return os.path.join(project_root, *entry["resolved"].split("/"))
    return os.path.join(project_root, *key.split("/")) if key else project_root


def production_closure(project_root: str, install_dir: str) -> Optional[List[str]]:
    """
    The production dependency closure of `install_dir`, as absolute directories.

    Returns None whenever npm's hidden lockfile cannot answer -- it is absent (npm 6, or a tree another
    package manager built), stale against `node_modules`, an unsupported version, unreadable, or does
    not describe this install directory -- so the caller falls back to asking npm.
    """
    if not _describes_the_installed_tree(project_root):
        LOG.debug("NODEJS no current hidden lockfile under %s; asking npm instead", project_root)
        return None

    try:
        with open(hidden_lockfile_path(project_root)) as handle:
            lock = json.load(handle)
    except (OSError, ValueError):
        return None

    if lock.get("lockfileVersion", 1) < MINIMUM_LOCKFILE_VERSION or "packages" not in lock:
        return None

    packages = lock["packages"]
    project_root = os.path.realpath(project_root)
    rel = os.path.relpath(os.path.realpath(install_dir), project_root).replace(os.sep, "/")
    start = "" if rel == "." else rel
    if start not in packages:
        return None

    # a link entry for a workspace member carries no dependencies; its source entry does
    def deps_of(key: str) -> Dict[str, str]:
        entry = packages.get(key) or {}
        if entry.get("link") and entry.get("resolved"):
            entry = packages.get(entry["resolved"], entry)
        # Production only, never devDependencies. Peers count: npm 7+ installs them and `npm ls --all`
        # walks them, so omitting them drops a package the function resolves - a plugin's host package,
        # typically. An optional peer the install declined is removed by the on-disk check below.
        out = dict(entry.get("dependencies") or {})
        out.update(entry.get("optionalDependencies") or {})
        out.update(entry.get("peerDependencies") or {})
        return out

    found: Set[str] = set()
    stack = [start]
    while stack:
        key = stack.pop()
        for name in deps_of(key):
            resolved = _resolve_key(packages, key, name)
            if resolved is None or resolved in found:
                continue
            entry = packages[resolved]
            if entry.get("dev"):
                continue
            found.add(resolved)
            # a link's dependencies must be resolved from its source directory, not from the
            # link's own node_modules path: walking up from the link finds the hoisted copy of
            # a package the source directory nests (node resolves through the real path too)
            if entry.get("link") and entry.get("resolved"):
                stack.append(entry["resolved"])
            else:
                stack.append(resolved)

    # An entry can be in the lockfile without being on disk: an optional dependency skipped for this
    # platform (fsevents is darwin-only), or one whose os/cpu/libc constraints excluded it. npm ls
    # reports the installed tree, so match that and keep only what is actually there. A required
    # dependency missing here means the install itself failed, which the install step surfaces.
    dirs = set()
    for key in found:
        directory = _entry_dir(project_root, key, packages[key])
        if os.path.isdir(directory):
            dirs.add(directory)
        else:
            LOG.debug("NODEJS lockfile lists %s but it is not installed; leaving it out", key)
    # npm --parseable also prints the project itself and the install dir; the caller filters those,
    # so emit them for parity
    dirs.add(project_root)
    dirs.add(os.path.realpath(install_dir))
    return sorted(dirs)
