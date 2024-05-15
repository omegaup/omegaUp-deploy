#!/usr/bin/python3
import argparse
import datetime
import json
import logging
import os
import subprocess
import tempfile
import zipfile

from typing import Any, Mapping, Set

import omegaup.api
import problems
import repository


def createProblemZip(problemConfig: Mapping[str, Any], problemPath: str,
                     zipPath: str) -> None:
    """Creates a problem .zip on the provided path."""
    with zipfile.ZipFile(zipPath, 'w',
                         compression=zipfile.ZIP_DEFLATED) as archive:

        def _addFile(f: str) -> None:
            logging.debug('writing %s', f)
            archive.write(f, os.path.relpath(f, problemPath))

        def _recursiveAdd(directory: str) -> None:
            for (root, _,
                 filenames) in os.walk(os.path.join(problemPath, directory)):
                for f in filenames:
                    _addFile(os.path.join(root, f))

        testplan = os.path.join(problemPath, 'testplan')

        if os.path.isfile(testplan):
            _addFile(testplan)

        if problemConfig['validator']['name'] == 'custom':
            validators = [
                x for x in os.listdir(problemPath) if x.startswith('validator')
            ]

            if not validators:
                raise Exception('Custom validator missing!')
            if len(validators) != 1:
                raise Exception('More than one validator found!')

            validator = os.path.join(problemPath, validators[0])

            _addFile(validator)

        for directory in ('statements', 'solutions', 'cases'):
            _recursiveAdd(directory)

        for directory in ('examples', 'interactive'):
            if not os.path.isdir(os.path.join(problemPath, directory)):
                continue
            _recursiveAdd(directory)


def uploadProblemZip(
    client: omegaup.api.Client,
    problemConfig: Mapping[str, Any],
    canCreate: bool,
    zipPath: str,
    commitMessage: str,
    timeout: datetime.timedelta,
) -> None:
    """Uploads a problem with the given .zip and configuration."""
    misc = problemConfig['misc']
    alias = misc['alias']
    limits = problemConfig['limits']
    validator = problemConfig['validator']

    payload = {
        'message': commitMessage,
        'problem_alias': alias,
        'title': problemConfig['title'],
        'source': problemConfig['source'],
        'visibility': misc['visibility'],
        'languages': misc['languages'],
        'time_limit': limits['TimeLimit'],
        'memory_limit': limits['MemoryLimit'] // 1024,
        'input_limit': limits['InputLimit'],
        'output_limit': limits['OutputLimit'],
        'extra_wall_time': limits['ExtraWallTime'],
        'overall_wall_time_limit': limits['OverallWallTimeLimit'],
        'validator': validator['name'],
        'validator_time_limit': validator['limits']['TimeLimit'],
        'email_clarifications': misc['email_clarifications'],
        'group_score_policy': misc.get('group_score_policy',
                                       'sum-if-not-zero'),
    }

    exists = client.problem.details(problem_alias=alias,
                                    check_=False)['status'] == 'ok'

    if not exists:
        if not canCreate:
            raise Exception("Problem doesn't exist!")
        logging.info("Problem doesn't exist. Creating problem.")
        endpoint = '/api/problem/create/'
    else:
        endpoint = '/api/problem/update/'

    languages = payload.get('languages', '')

    if languages == 'all':
        payload['languages'] = ','.join((
            'c11-clang',
            'c11-gcc',
            'cpp11-clang',
            'cpp11-gcc',
            'cpp17-clang',
            'cpp17-gcc',
            'cpp20-clang',
            'cpp20-gcc',
            'cs',
            'go',
            'hs',
            'java',
            'js',
            'kt',
            'lua',
            'pas',
            'py2',
            'py3',
            'rb',
            'rs',
        ))
    elif languages == 'karel':
        payload['languages'] = 'kj,kp'
    elif languages == 'none':
        payload['languages'] = ''

    files = {'problem_contents': open(zipPath, 'rb')}

    client.query(endpoint, payload, files, timeout)

    targetAdmins = misc.get('admins', [])
    targetAdminGroups = misc.get('admin-groups', [])

    if targetAdmins or targetAdminGroups:
        allAdmins = client.problem.admins(problem_alias=alias)

    if targetAdmins is not None:
        admins = {
            a['username'].lower()
            for a in allAdmins['admins'] if a['role'] == 'admin'
        }

        desiredAdmins = {admin.lower() for admin in targetAdmins}

        clientAdmin: Set[str] = set()
        if client.username:
            clientAdmin.add(client.username.lower())
        adminsToRemove = admins - desiredAdmins - clientAdmin
        adminsToAdd = desiredAdmins - admins - clientAdmin

        for admin in adminsToAdd:
            logging.info('Adding problem admin: %s', admin)
            client.problem.addAdmin(problem_alias=alias, usernameOrEmail=admin)

        for admin in adminsToRemove:
            logging.info('Removing problem admin: %s', admin)
            client.problem.removeAdmin(problem_alias=alias,
                                       usernameOrEmail=admin)

    if targetAdminGroups is not None:
        adminGroups = {
            a['alias'].lower()
            for a in allAdmins['group_admins'] if a['role'] == 'admin'
        }

        desiredGroups = {group.lower() for group in targetAdminGroups}

        groupsToRemove = adminGroups - desiredGroups
        groupsToAdd = desiredGroups - adminGroups

        for group in groupsToAdd:
            logging.info('Adding problem admin group: %s', group)
            client.problem.addGroupAdmin(problem_alias=alias, group=group)

        for group in groupsToRemove:
            logging.info('Removing problem admin group: %s', group)
            client.problem.removeGroupAdmin(problem_alias=alias, group=group)

    if 'tags' in misc:
        tags = {
            t['name'].lower()
            for t in client.problem.tags(problem_alias=alias)['tags']
        }

        desiredTags = {t.lower() for t in misc['tags']}

        tagsToRemove = tags - desiredTags
        tagsToAdd = desiredTags - tags

        for tag in tagsToRemove:
            if tag.startsWith('problemRestrictedTag'):
                logging.info('Skipping restricted tag: %s', tag)
                continue
            client.problem.removeTag(problem_alias=alias, name=tag)

        for tag in tagsToAdd:
            logging.info('Adding problem tag: %s', tag)
            client.problem.addTag(problem_alias=alias,
                                  name=tag,
                                  public=payload.get('public', False))


def uploadProblem(
    client: omegaup.api.Client,
    problemPath: str,
    commitMessage: str,
    canCreate: bool,
    timeout: datetime.timedelta,
) -> None:
    with open(os.path.join(problemPath, 'settings.json'), 'r') as f:
        problemConfig = json.load(f)

    logging.info('Uploading problem: %s', problemConfig['title'])

    with tempfile.NamedTemporaryFile() as tempFile:
        createProblemZip(problemConfig, problemPath, tempFile.name)

        uploadProblemZip(client,
                         problemConfig,
                         canCreate,
                         tempFile.name,
                         commitMessage=commitMessage,
                         timeout=timeout)

        logging.info('Success uploading %s', problemConfig['title'])


def _main() -> None:
    env = os.environ

    parser = argparse.ArgumentParser(
        description='Deploy a problem to omegaUp.')
    parser.add_argument('--ci',
                        action='store_true',
                        help='Signal that this is being run from the CI.')
    parser.add_argument(
        '--all',
        action='store_true',
        help='Consider all problems, instead of only those that have changed')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Verbose logging')
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
                              "problem if it does not exist."))
    parser.add_argument("--timeout",
                        type=int,
                        default=60,
                        help="Timeout for deploy API call (in seconds)")
    parser.add_argument('problem_paths',
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

    if env.get('GITHUB_ACTIONS'):
        commit = env['GITHUB_SHA']
    else:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                         universal_newlines=True).strip()

    rootDirectory = repository.repositoryRoot()

    for problem in problems.problems(allProblems=args.all,
                                     rootDirectory=rootDirectory,
                                     problemPaths=args.problem_paths):
        uploadProblem(
            client,
            os.path.join(rootDirectory, problem.path),
            commitMessage=f'Deployed automatically from commit {commit}',
            canCreate=args.can_create,
            timeout=datetime.timedelta(seconds=args.timeout))


if __name__ == '__main__':
    _main()
