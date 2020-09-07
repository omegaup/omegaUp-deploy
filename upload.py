#!/usr/bin/python3
import argparse
import json
import logging
import os
import subprocess
import tempfile
import zipfile

from typing import Any, Mapping

import omegaup.api
import problems


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


def uploadProblemZip(api: omegaup.api.API, problemConfig: Mapping[str, Any],
                     canCreate: bool, zipPath: str, message: str) -> None:
    """Uploads a problem with the given .zip and configuration."""
    misc = problemConfig['misc']
    alias = misc['alias']
    limits = problemConfig['limits']
    validator = problemConfig['validator']

    payload = {
        'message': message,
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
    }

    exists = api.problem.exists(alias)

    if not exists:
        if not canCreate:
            raise Exception("Problem doesn't exist!")
        logging.info("Problem doesn't exist. Creating problem.")
        endpoint = '/api/problem/create/'
    else:
        endpoint = '/api/problem/update/'

    languages = payload.get('languages', '')

    if languages == 'all':
        payload['languages'] = ''.join((
            'c11-gcc',
            'c11-clang',
            'cpp11-gcc',
            'cpp11-clang',
            'cpp17-gcc',
            'cpp17-clang',
            'cs',
            'hs',
            'java',
            'lua',
            'pas',
            'py2',
            'py3',
            'rb',
        ))
    elif languages == 'karel':
        payload['languages'] = 'kj,kp'
    elif languages == 'none':
        payload['languages'] = ''

    files = {'problem_contents': open(zipPath, 'rb')}

    api.query(endpoint, payload, files)

    targetAdmins = misc.get('admins', [])
    targetAdminGroups = misc.get('admin-groups', [])

    if targetAdmins or targetAdminGroups:
        allAdmins = api.problem.admins(alias)

    if targetAdmins is not None:
        admins = {
            a['username'].lower()
            for a in allAdmins['admins'] if a['role'] == 'admin'
        }

        desiredAdmins = {admin.lower() for admin in targetAdmins}

        adminsToRemove = admins - desiredAdmins - {api.username.lower()}
        adminsToAdd = desiredAdmins - admins - {api.username.lower()}

        for admin in adminsToAdd:
            logging.info('Adding problem admin: %s', admin)
            api.problem.addAdmin(alias, admin)

        for admin in adminsToRemove:
            logging.info('Removing problem admin: %s', admin)
            api.problem.removeAdmin(alias, admin)

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
            api.problem.addGroupAdmin(alias, group)

        for group in groupsToRemove:
            logging.info('Removing problem admin group: %s', group)
            api.problem.removeGroupAdmin(alias, group)

    if 'tags' in misc:
        tags = {t['name'].lower() for t in api.problem.tags(alias)['tags']}

        desiredTags = {t.lower() for t in misc['tags']}

        tagsToRemove = tags - desiredTags
        tagsToAdd = desiredTags - tags

        for tag in tagsToRemove:
            if tag.startsWith('problemRestrictedTag'):
                logging.info('Skipping restricted tag: %s', tag)
                continue
            api.problem.removeTag(alias, tag)

        for tag in tagsToAdd:
            logging.info('Adding problem tag: %s', tag)
            api.problem.addTag(alias, tag, public=payload.get('public', False))


def uploadProblem(api: omegaup.api.API, problemPath: str, commit: str,
                  canCreate: bool) -> None:
    with open(os.path.join(problemPath, 'settings.json'), 'r') as f:
        problemConfig = json.load(f)

    logging.info('Uploading problem: %s', problemConfig['title'])

    with tempfile.NamedTemporaryFile() as tempFile:
        createProblemZip(problemConfig, problemPath, tempFile.name)

        uploadProblemZip(
            api,
            problemConfig,
            canCreate,
            tempFile.name,
            message=f'Deployed automatically from commit {commit}')

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
    parser.add_argument('-u',
                        '--username',
                        type=str,
                        default=env.get('OMEGAUPUSER'),
                        required='OMEGAUPUSER' not in env)
    parser.add_argument('-p',
                        '--password',
                        type=str,
                        default=env.get('OMEGAUPPASS'),
                        required='OMEGAUPPASS' not in env)
    parser.add_argument(
        '--can-create',
        action='store_true',
        help=
        "Whether it's allowable to create the problem if it does not exist.")
    parser.add_argument('problem_paths',
                        metavar='PROBLEM',
                        type=str,
                        nargs='*')
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s: %(message)s',
                        level=logging.DEBUG if args.verbose else logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    api = omegaup.api.API(username=args.username,
                          password=args.password,
                          url=args.url)

    if env.get('GITHUB_ACTIONS'):
        commit = env['GITHUB_SHA']
    else:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                         universal_newlines=True).strip()

    if args.problem_paths:
        # Generate the Problem objects from just the path. The title is ignored
        # anyways, since it's read from the configuration file in the problem
        # directory.
        problemList = [
            problems.Problem(path=problemPath,
                             title=os.path.basename(problemPath),
                             disabled=False)
            for problemPath in args.problem_paths
        ]
    else:
        problemList = problems.problems(allProblems=args.all)

    for problem in problemList:
        uploadProblem(api,
                      problem.path,
                      commit=commit,
                      canCreate=args.can_create)


if __name__ == '__main__':
    _main()

