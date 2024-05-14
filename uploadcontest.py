#!/usr/bin/python3
import argparse
import datetime
import logging
import os

import contests
import omegaup.api
import repository


def _main() -> None:
    env = os.environ

    parser = argparse.ArgumentParser(description="Upsert contests to OmegaUp")
    parser.add_argument(
        '--cli',
        action='store_true',
        help='Signal that the script is being run from the CLI',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Upsert all contests, instead of only those that have changed',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verb',
    )
    parser.add_argument('--url',
                        default='https://omegaup.com',
                        help='URL of the omegaUp host.')
    parser.add_argument('--api-token',
                        type=str,
                        default=env.get('OMEGAUP_API_TOKEN'))
    parser.add_argument('-u',
                        '--username',
                        type=str,
                        default=env.get('OMEGAUPUSER'),
                        required=('OMEGAUPUSER' not in env
                                  and 'OMEGAUP_API_TOKEN' not in env))
    parser.add_argument('-p',
                        '--password',
                        type=str,
                        default=env.get('OMEGAUPPASS'),
                        required=('OMEGAUPPASS' not in env
                                  and 'OMEGAUP_API_TOKEN' not in env))
    parser.add_argument('--can-create',
                        action='store_true',
                        help=("Whether it's allowable to create the "
                              "contest if it does not exist."))
    parser.add_argument("--timeout",
                        type=int,
                        default=60,
                        help="Timeout for deploy API call (in seconds)")
    parser.add_argument('contest_paths',
                        metavar='PROBLEM',
                        type=str,
                        nargs='*')

    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s: %(message)s',
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    client = omegaup.api.Client(username=args.username,
                                password=args.password,
                                api_token=args.api_token,
                                url=args.url)

    rootDirectory = repository.repositoryRoot()

    for contest in contests.contests(allContests=args.all,
                                     rootDirectory=rootDirectory,
                                     contestPaths=args.contest_paths):
        contests.upsertContest(
            client,
            os.path.join(rootDirectory, contest.path),
            canCreate=args.can_create,
            timeout=datetime.timedelta(seconds=args.timeout))


if __name__ == '__main__':
    _main()
