from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bnpm")

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("name")
    source_group = add_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--git")
    source_group.add_argument("--path")
    ref_group = add_parser.add_mutually_exclusive_group()
    ref_group.add_argument("--tag")
    ref_group.add_argument("--branch")
    ref_group.add_argument("--rev")

    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("name")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("names", nargs="*")

    subparsers.add_parser("sync")
    subparsers.add_parser("verify")
    subparsers.add_parser("list")
    subparsers.add_parser("setup")

    return parser
