import logging
import os
import sys
import subprocess
import json

from typing import List, NamedTuple, NoReturn, Optional

import omegaup.api

class Problem(NamedTuple):
    """Represents a single problem."""
    path: str
    title: str
    disabled: bool


def repositoryRoot() -> str:
    """Returns the root directory of the project.

    If this is a submodule, it gets the root of the top-level working tree.
    """
    return subprocess.check_output([
        'git', 'rev-parse', '--show-superproject-working-tree',
        '--show-toplevel'
    ],
                                   universal_newlines=True).strip().split()[0]


def enumerateFullPath(path: str) -> List[str]:
    """Returns a list of full paths for the files in `path`."""
    if not os.path.exists(path):
        return []
    return [os.path.join(path, f) for f in os.listdir(path)]


def ci_error(message: str,
             *,
             filename: Optional[str] = None,
             line: Optional[int] = None,
             col: Optional[int] = None) -> None:
    """Show an error message, only on the CI."""
    location = []
    if filename is not None:
        location.append(f'file={filename}')
    if line is not None:
        location.append(f'line={line}')
    if col is not None:
        location.append(f'col={col}')
    print(
        f'::error {",".join(location)}::' +
        message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A'))


def error(message: str,
          *,
          filename: Optional[str] = None,
          line: Optional[int] = None,
          col: Optional[int] = None,
          ci: bool = False) -> None:
    """Show an error message."""
    if ci:
        ci_error(message, filename=filename, line=line, col=col)
    logging.error(message)


def fatal(message: str,
          *,
          filename: Optional[str] = None,
          line: Optional[int] = None,
          col: Optional[int] = None,
          ci: bool = False) -> NoReturn:
    """Show a fatal message and exit."""
    error(message, filename=filename, line=line, col=col, ci=ci)
    sys.exit(1)


def problems(allProblems: bool = False,
             rootDirectory: Optional[str] = None) -> List[Problem]:
    """Gets the list of problems that will be considered.

    If `allProblems` is passed, all the problems that are declared in
    `problems.json` will be returned. Otherwise, only those that have
    differences with `upstream/master`.
    """
    env = os.environ
    if rootDirectory is None:
        rootDirectory = repositoryRoot()

    logging.info('Loading problems...')

    with open(os.path.join(rootDirectory, 'problems.json'), 'r') as p:
        config = json.load(p)

    configProblems: List[Problem] = []
    for problem in config['problems']:
        configProblems.append(
            Problem(path=problem['path'],
                    title=problem['title'],
                    disabled=problem.get('disabled', False)))

    if allProblems:
        logging.info('Loading everything as requested.')
        return configProblems

    logging.info('Loading git diff.')

    if env.get('TRAVIS_COMMIT_RANGE'):
        commitRange = env['TRAVIS_COMMIT_RANGE']
    elif env.get('CIRCLE_COMPARE_URL'):
        commitRange = env['CIRCLE_COMPARE_URL'].split('/')[6]
    elif env.get('GITHUB_BASE_COMMIT'):
        commitRange = env['GITHUB_BASE_COMMIT'] + '...HEAD'
    else:
        commitRange = 'origin/master...HEAD'

    changes = subprocess.check_output(
        ['git', 'diff', '--name-only', '--diff-filter=AMDR', commitRange],
        cwd=rootDirectory,
        universal_newlines=True)

    problems: List[Problem] = []
    for problem in configProblems:
        logging.info('Loading %s.', problem.title)

        if problem.path not in changes:
            logging.info('No changes to %s. Skipping.', problem.title)
            continue
        problems.append(problem)

    return problems


def upload(api: omegaup.api.API, problem: Mapping[str, Any],
           can_create: bool, zip_path: str, message: str) -> None:
    misc = problem['misc']
    alias = misc['alias']
    limits = problem['limits']
    validator = problem['validator']

    payload = {
        'message': message,
        'problem_alias': alias,
        'title': problem['title'],
        'source': problem['source'],
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
        if not can_create:
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

    files = {'problem_contents': open(zip_path, 'rb')}

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
            api.problem.removeGroup(Adminalias, group)

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
            api.problem.addTag(alias, tag, payload.get('visibility', '0'))
