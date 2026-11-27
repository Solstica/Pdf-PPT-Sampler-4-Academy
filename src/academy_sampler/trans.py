"""Two-step, globally installed trans command."""
import argparse
import json
from .trans_registry import PRESETS, code_of, courses, lock, register, state_root
from .trans_publish import publish


def main(argv=None):
    parser = argparse.ArgumentParser(prog="trans",
        description="Register and number course files, then render and publish to private GitHub.")
    parser.add_argument("first", nargs="?", help="raw folder or registered course code")
    parser.add_argument("second", nargs="?", help="course code or GitHub repository URL")
    parser.add_argument("-pre", "--preset-number", type=int, choices=sorted(PRESETS))
    parser.add_argument("--list", action="store_true", help="list locally registered courses")
    parser.add_argument("--show", metavar="CODE", help="show local registration details")
    parser.add_argument("--dry-run", action="store_true", help="preview source renames only")
    parser.add_argument("--relocate", action="store_true", help="verify and register a moved source folder")
    args = parser.parse_args(argv)
    home = state_root()
    try:
        with lock(home):
            data = courses(home)
            if args.list or args.show:
                if args.first or args.second or (args.list and args.show) or args.dry_run or args.relocate or args.preset_number is not None:
                    parser.error("Use --list or --show CODE by itself")
                if args.list:
                    for code, entry in sorted(data.items()):
                        print(code, "G" + str(entry["preset"]), len(entry["documents"]),
                              "Synced" if entry.get("last_commit") else "Registered")
                else:
                    print(json.dumps(data[code_of(args.show)], ensure_ascii=False, indent=2))
                return 0
            if not args.first or not args.second:
                parser.error("Expected RAW CODE or CODE GITHUB_URL")
            if args.second.startswith(("git@", "ssh://", "https://", "http://")):
                if args.dry_run or args.relocate:
                    parser.error("These options apply only to registration")
                publish(home, data, code_of(args.first), args.second, args.preset_number)
            else:
                result = register(home, data, args.first, args.second,
                                  args.preset_number, args.dry_run, args.relocate)
                if args.dry_run:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print("Registered", code_of(args.second), "G" + str(result["preset"]),
                          len(result["documents"]), "documents")
            return 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print("Error:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
