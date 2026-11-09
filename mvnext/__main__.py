"""Offline JSON replay CLI. It cannot call a paid model or queue GPU work."""
import argparse
import json
from pathlib import Path
from .pipeline import prepare, inspect


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'inspect'):
        p=sub.add_parser(name)
        p.add_argument('--project', required=True)
        p.add_argument('--song', required=True)
        p.add_argument('--picture', action='append', required=True)
        if name=='prepare':
            p.add_argument('--story', required=True)
            p.add_argument('--song-frames', type=int, required=True)
            p.add_argument('--screenplay', required=True)
            p.add_argument('--camera', required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        def replay(role, payload):
            path=args.screenplay if role=='screenplay' else args.camera
            return Path(path).read_text(encoding='utf-8')
        result=prepare(args.project, Path(args.story).read_text(encoding='utf-8'),
                       args.song, args.song_frames, args.picture, replay)
    else:
        result=inspect(args.project, args.song, args.picture)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__=='__main__':
    main()
