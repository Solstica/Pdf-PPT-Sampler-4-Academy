"""Two-step, globally installed trans command."""
import argparse
import json
from .trans_registry import PRESETS, code_of, courses, lock, register, state_root
from .trans_publish import publish
from .terminal_progress import LANGUAGE, default_language, tr, PROGRESS_MODE, default_progress_mode


def main(argv=None):
    parser = argparse.ArgumentParser(prog="trans",
        description="Register and number course files, then render and publish to private GitHub.")
    parser.add_argument("first", nargs="?", help="raw folder or registered course code")
    parser.add_argument("second", nargs="?", help="course code or GitHub repository URL")
    parser.add_argument("-pre", "--preset-number", type=int, choices=sorted(PRESETS))
    parser.add_argument("--progress", choices=("auto", "live", "log"), default=default_progress_mode(), help="auto terminal detection, forced single-line live, or plain logs")
    parser.add_argument("--lang", choices=("en", "zh"), default=default_language(), help="terminal display language (default: en or ACADEMY_SAMPLER_LANG)")
    parser.add_argument("--group", metavar="FOLDER", help="sync only this raw subfolder and its descendants (or . for root files)")
    parser.add_argument("--list", action="store_true", help="list locally registered courses")
    parser.add_argument("--show", metavar="CODE", help="show local registration details")
    parser.add_argument("--dry-run", action="store_true", help="preview source renames only")
    parser.add_argument("--relocate", action="store_true", help="verify and register a moved source folder")
    args = parser.parse_args(argv)
    if args.lang not in ('en', 'zh'):
        parser.error('ACADEMY_SAMPLER_LANG must be en or zh')
    if args.progress not in ('auto', 'live', 'log'):
        parser.error('ACADEMY_SAMPLER_PROGRESS must be auto, live or log')
    home = state_root()
    token = LANGUAGE.set(args.lang)
    progress_token = PROGRESS_MODE.set(args.progress)
    try:
        with lock(home):
            data = courses(home)
            if args.list or args.show:
                if args.first or args.second or (args.list and args.show) or args.dry_run or args.relocate or args.preset_number is not None or args.group is not None:
                    parser.error("Use --list or --show CODE by itself")
                if args.list:
                    for code, entry in sorted(data.items()):
                        print(code, "G" + str(entry["preset"]), len(entry["documents"]),
                              tr("Synced", "已同步") if entry.get("last_commit") else tr("Registered", "已注册"))
                else:
                    print(json.dumps(data[code_of(args.show)], ensure_ascii=False, indent=2))
                return 0
            if not args.first:
                parser.error("Expected RAW CODE, CODE GITHUB_URL, or registered CODE")
            if not args.second:
                if args.dry_run or args.relocate:
                    parser.error("These options apply only to registration")
                code = code_of(args.first)
                entry = data.get(code, {})
                remote = entry.get("remote")
                if not remote:
                    raise ValueError("No bound remote; run trans CODE GITHUB_URL first")
                publish(home, data, code, remote.get("github_url", remote["url"]), args.preset_number, args.group)
                return 0
            if args.second.startswith(("git@", "ssh://", "https://", "http://")):
                if args.dry_run or args.relocate:
                    parser.error("These options apply only to registration")
                publish(home, data, code_of(args.first), args.second, args.preset_number, args.group)
            else:
                if args.group is not None:
                    parser.error('--group applies to publication only')
                result = register(home, data, args.first, args.second,
                                  args.preset_number, args.dry_run, args.relocate)
                if args.dry_run:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print(tr("Registered", "已注册"), code_of(args.second), "G" + str(result["preset"]),
                          len(result["documents"]), tr("documents", "份文档"))
            return 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(tr("Error:", "错误:"), exc)
        return 1
    finally:
        PROGRESS_MODE.reset(progress_token)
        LANGUAGE.reset(token)


if __name__ == "__main__":
    raise SystemExit(main())
