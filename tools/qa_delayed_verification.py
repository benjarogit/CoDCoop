#!/usr/bin/env python3
"""QA-only slow read-only preflight; never substitutes a verification result.

The real supervisor loop, owned game processes and complete content verifier
remain active. Only its background file-check worker waits before doing the
real work, so the native timeout/late-ACK/explicit-Retry path is repeatable.
This entry point is not packaged with the launcher.
"""
import argparse
import os
from pathlib import Path
import threading
import time

import coop_session as session


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--delay',type=int,required=True)
    options,remaining=parser.parse_known_args(argv)
    if not 120 < options.delay <= 180:
        parser.error('delay must exceed the native120s wait and remain bounded at180s')
    if os.environ.get('CODCOOP_QA')!='1' or os.environ.get('CODCOOP_QA_PROFILE')!='1':
        parser.error('requires an isolated verified QA session')
    try:
        game=Path(remaining[remaining.index('--game')+1]).resolve()
    except (ValueError,IndexError):
        parser.error('requires the owned --game directory')
    if not (game.parent/'.codcoop-switch-qa-owned').is_file():
        parser.error('refusing an installation outside the owned switch QA directory')
    original=session.check_installation
    def slow_check(game):
        if threading.current_thread() is not threading.main_thread():
            session.event('qa_verification_delay',seconds=options.delay)
            time.sleep(options.delay)
        return original(game) # no receipt, checksum, package or map bypass
    session.check_installation=slow_check
    try:
        return session.main(remaining)
    finally:
        session.check_installation=original


if __name__=='__main__':
    raise SystemExit(main())
