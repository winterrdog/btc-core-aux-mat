#!/usr/bin/env python3
"""
pr_review.py - Fast local review helper for Bitcoin Core PRs.

Fetches a PR from upstream, checks it out into a dedicated branch, then
configures/builds with CMake and runs the unit + functional tests relevant
to the chosen subsystem (http, tor, psbt). Use -n/--no-git to skip the git
step and test the current checkout as-is.

Works on Linux, FreeBSD and NetBSD (assumes `git`, `cmake`, `clang`/`clang++`
and a Python 3 interpreter for the functional test runner are on PATH).
"""

import argparse
import shlex
import subprocess
import sys
from enum import Enum

CMAKE_BASE = [
    "cmake",
    "-B",
    "build",
    "-DCMAKE_C_COMPILER=clang",
    "-DCMAKE_CXX_COMPILER=clang++",
    "-DCMAKE_BUILD_TYPE=Debug",
    "-DENABLE_IPC=OFF",
    "-DCMAKE_CXX_FLAGS_DEBUG=-O0 -ggdb3",
    "-DBUILD_GUI=OFF",
    "-DBUILD_BENCH=OFF",
    "-DBUILD_FOR_FUZZING=OFF",
    "-DBUILD_KERNEL_LIB=OFF",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DBUILD_TESTS=ON",
    "-DBUILD_TX=OFF",
    "-DBUILD_UTIL=OFF",
    "-DBUILD_WALLET_TOOL=OFF",
]

BUILD_CMD = [
    "cmake",
    "--build",
    "build",
    "-j",
    "10",
    "--target",
    "test_bitcoin",
    "bitcoind",
    "bitcoin-cli",
]


class Subsystem(Enum):
    HTTP = "http"
    TOR = "tor"
    PSBT = "psbt"

    @property
    def boost_test(self) -> str:
        return {
            Subsystem.HTTP: "httpserver_tests,netbase_tests",
            Subsystem.TOR: "torcontrol_tests",
            Subsystem.PSBT: "psbt_tests",
        }[self]

    @property
    def functional_test(self) -> list[str]:
        # Each entry is passed to test_runner.py as ONE argument. The runner
        # splits entries on spaces, so a test with extra flags (e.g.
        # "interface_http --http-unix") is simply a single string here.
        return {
            Subsystem.HTTP: [
                "interface_http",
                "interface_http --http-unix",
                "interface_bitcoin_cli",
                "rpc_bind",
            ],
            Subsystem.TOR: ["feature_torcontrol"],
            Subsystem.PSBT: ["rpc_psbt"],
        }[self]


def run(cmd, **kwargs) -> None:
    """Run a command, streaming output live, and abort on failure."""

    print(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}\n", flush=True)
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(
            f"\n[FAILED] Command exited with code {result.returncode}: "
            f"\"{' '.join(cmd)}\"",
            file=sys.stderr)
        sys.exit(result.returncode)


def parse_args() -> argparse.Namespace:
    subsystem_choices = "{" + ",".join(s.value for s in Subsystem) + "}"

    parser = argparse.ArgumentParser(
        usage=f"%(prog)s [-h] [-n] [-u] [pr_number] {subsystem_choices}",
        description="Fetch, checkout, build and test a Bitcoin Core PR "
        f"for a given subsystem {subsystem_choices}.")

    parser.add_argument(
        "target",
        nargs="+",
        metavar=f"[pr_number] {subsystem_choices}",
        help="Pull request number (e.g. 12345) followed by the subsystem to "
        f"test, one of: {', '.join(s.value for s in Subsystem)}. With "
        "-n/--no-git only the subsystem is given.",
    )

    parser.add_argument(
        "-n",
        "--no-git",
        action="store_true",
        help="Skip all git operations (fetch/checkout) and just configure, "
        "build and test whatever is currently checked out. The PR number "
        "is not needed in this mode.",
    )

    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        help="PR branch already exists locally; force-fetch the latest "
        "commits from the author and reset pr-<pr_number> to them "
        "instead of creating it fresh.",
    )

    args = parser.parse_args()
    subsystems = [s.value for s in Subsystem]

    if args.no_git:
        if args.update:
            parser.error("-u/--update cannot be combined with -n/--no-git")
        if len(args.target) != 1:
            parser.error("with -n/--no-git, give only the subsystem")
        args.pr_number = None
        args.subsystem = args.target[0]
    else:
        if len(args.target) != 2:
            parser.error("expected: pr_number subsystem")
        try:
            args.pr_number = int(args.target[0])
        except ValueError:
            parser.error(f"invalid pr_number: {args.target[0]!r}")
        if args.pr_number <= 0:
            parser.error("pr_number must be a positive integer")
        args.subsystem = args.target[1]

    if args.subsystem not in subsystems:
        parser.error(f"invalid subsystem {args.subsystem!r} "
                     f"(choose from {', '.join(subsystems)})")
    return args


def fetch_and_checkout(pr_number: int) -> None:
    branch = f"pr-{pr_number}"
    run(["git", "fetch", "upstream", f"pull/{pr_number}/head:{branch}"])
    run(["git", "checkout", branch])


def update_checkout(pr_number: int) -> None:
    """Pull in new commits the PR author has pushed since the initial fetch.

    Mirrors: git checkout master && git fetch upstream +pull/<n>/head:pr-<n>
    && git checkout pr-<n>
    The leading '+' forces the local pr-<n> branch to be reset to whatever
    upstream currently has, even if history was rewritten (force-push).
    """

    branch = f"pr-{pr_number}"
    run(["git", "checkout", "master"])
    run(["git", "fetch", "upstream", f"+pull/{pr_number}/head:{branch}"])
    run(["git", "checkout", branch])


def configure_build_and_test(subsystem: Subsystem) -> None:
    # compilation
    run(CMAKE_BASE)
    run(BUILD_CMD)

    # unit tests
    run(["./build/bin/test_bitcoin", f"--run_test={subsystem.boost_test}"])

    # functional tests
    run(["./build/test/functional/test_runner.py", *subsystem.functional_test])


def main() -> None:
    args = parse_args()
    pr_number = args.pr_number
    subsystem = Subsystem(args.subsystem)

    if not args.no_git:
        if args.update:
            update_checkout(pr_number)
        else:
            fetch_and_checkout(pr_number)

    configure_build_and_test(subsystem)

    label = "current checkout" if args.no_git else f"PR #{pr_number}"
    print(f"\n✅ {label} ({subsystem.value}) built and tests passed.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as e:
        print("\nUnexpected error: ", e, file=sys.stderr)
        sys.exit(1)
