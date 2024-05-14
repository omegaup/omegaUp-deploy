import os
import logging
from typing import (
    NamedTuple,
    Mapping,
    Any,
    Sequence,
    List,
    Optional,
    Dict,
    Set,
)
import omegaup.api
import repository
import json
import datetime
import yaml

_CONFIG_FILE = 'contest.yaml'


class Contest(NamedTuple):
    """Represents a single contest."""
    path: str
    title: str
    config: Mapping[str, Any]

    @staticmethod
    def load(contestPath: str, rootDirectory: str) -> 'Contest':
        """Load a single contest from the path."""
        with open(os.path.join(rootDirectory, contestPath, _CONFIG_FILE)) as f:
            problemConfig = yaml.safe_load(f)

        return Contest(path=contestPath,
                       title=problemConfig['title'],
                       config=problemConfig)


def contests(allContests: bool = False,
             contestPaths: Sequence[str] = (),
             rootDirectory: Optional[str] = None) -> List[Contest]:
    """Gets the list of contests that will be considered.

    If `allContests` is passed, all the contests that are declared in
    `contests.json` will be returned. Otherwise, only those that have
    differences with `upstream/main`.
    """
    if rootDirectory is None:
        rootDirectory = repository.repositoryRoot()

    logging.info('Loading contests...')

    if contestPaths:
        # Generate the Contest objects from just the path. The title is ignored
        # anyways, since it's read from the configuration file in the contest
        # directory for anything important.
        return [
            Contest.load(contestPath=problemPath, rootDirectory=rootDirectory)
            for problemPath in contestPaths
        ]

    with open(os.path.join(rootDirectory, 'problems.json'), 'r') as p:
        config = json.load(p)

    configContests: List[Contest] = []
    for contest in config['contests']:
        if contest.get('disabled', False):
            logging.warning('Contest %s disabled. Skipping.', contest['title'])
            continue
        configContests.append(
            Contest.load(contestPath=contest['path'],
                         rootDirectory=rootDirectory))

    if allContests:
        logging.info('Loading everything as requested.')
        return configContests

    changes = repository.gitDiff(rootDirectory)

    contests: List[Contest] = []
    for contest in configContests:
        logging.info('Loading %s.', contest.title)

        if contest.path not in changes:
            logging.info('No changes to %s. Skipping.', contest.title)
            continue
        contests.append(contest)

    return contests


def date_to_timestamp(date: str) -> int:
    return int(
        datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ').timestamp())


def upsertContest(
    client: omegaup.api.Client,
    contestPath: str,
    canCreate: bool,
    timeout: datetime.timedelta,
) -> None:
    """Upsert a contest to omegaUp given the configuration."""
    with open(os.path.join(contestPath, _CONFIG_FILE)) as f:
        contestConfig = yaml.safe_load(f)

    logging.info('Upserting contest %s...', contestConfig['title'])

    title = contestConfig['title']
    alias = contestConfig['alias']
    misc = contestConfig['misc']
    languages = misc['languages']

    if languages == 'all':
        misc['languages'] = ','.join((
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
        misc['languages'] = 'kj,kp'
    elif languages == 'none':
        misc['languages'] = ''

    payload = {
        'title': title,
        'admission_mode': misc['admission_mode'],
        'description': contestConfig.get('description', ''),
        'feedback': misc["feedback"],
        'finish_time': date_to_timestamp(contestConfig['finish_time']),
        'languages': misc['languages'],
        'penalty': misc['penalty']['time'],
        'penalty_calc_policy': misc['penalty']['calc_policy'],
        'penalty_type': misc['penalty']['type'],
        'points_decay_factor': misc['penalty']['points_decay_factor'],
        'requests_user_information': str(misc['requests_user_information']),
        'score_mode': misc['score_mode'],
        'scoreboard': misc['scoreboard'],
        'show_scoreboard_after': misc['show_scoreboard_after'],
        'submissions_gap': misc['submissions_gap'],
        'start_time': date_to_timestamp(contestConfig['start_time']),
        'window_length': contestConfig.get('window_length', None),
    }

    exists = client.contest.details(contest_alias=alias,
                                    check_=False)["status"] == 'ok'

    if not exists:
        if not canCreate:
            raise Exception("Contest doesn't exist!")
        logging.info("Contest doesn't exist. Creating contest.")
        endpoint = '/api/contest/create/'
        payload['alias'] = alias
    else:
        endpoint = '/api/contest/update/'
        payload['contest_alias'] = alias

    client.query(endpoint, payload, timeout_=timeout)

    # Adding admins
    targetAdmins: Sequence[str] = contestConfig.get('admins',
                                                    {}).get('users', [])
    targetAdminGroups: Sequence[str] = contestConfig.get('admins',
                                                         {}).get('groups', [])

    allAdmins = client.contest.admins(contest_alias=alias)

    if len(targetAdmins) > 0:
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
            logging.info('Adding contest admin: %s', admin)
            client.contest.addAdmin(contest_alias=alias, usernameOrEmail=admin)

        for admin in adminsToRemove:
            logging.info('Removing contest admin: %s', admin)
            client.contest.removeAdmin(contest_alias=alias,
                                       usernameOrEmail=admin)

    adminGroups = {
        a['alias'].lower()
        for a in allAdmins['group_admins'] if a['role'] == 'admin'
    }

    desiredGroups = {group.lower() for group in targetAdminGroups}

    groupsToRemove = adminGroups - desiredGroups
    groupsToAdd = desiredGroups - adminGroups

    for group in groupsToAdd:
        logging.info('Adding contest admin group: %s', group)
        client.contest.addGroupAdmin(contest_alias=alias, group=group)

    for group in groupsToRemove:
        logging.info('Removing contest admin group: %s', group)
        client.contest.removeGroupAdmin(contest_alias=alias, group=group)

    # Adding problems
    targetProblems: Sequence[Dict] = contestConfig.get('problems', [])

    allProblems = client.contest.problems(contest_alias=alias)
    problems = {
        p['alias'].lower(): {
            'points': p['points'],
            'order_in_contest': p['order'],
        }
        for p in allProblems['problems']
    }

    desiredProblems = {
        problem['alias'].lower(): {
            'points': problem.get('points', 100),
            'order_in_contest': problem.get('order_in_contest', idx + 1),
        }
        for idx, problem in enumerate(targetProblems)
    }
    problemsToRemove = problems.keys() - desiredProblems
    problemsToUpsert = (desiredProblems.keys() - problems.keys()) | {
        problem
        for problem in problems
        if problem in problems and problem in desiredProblems and
        (desiredProblems[problem] != problems[problem])
    }

    for problem in problemsToUpsert:
        logging.info('Upserting contest problem: %s', problem)
        client.contest.addProblem(
            contest_alias=alias,
            problem_alias=problem,
            order_in_contest=desiredProblems[problem]['order_in_contest'],
            points=desiredProblems[problem]['points'])

    for problem in problemsToRemove:
        logging.info('Removing contest problem: %s', problem)
        client.contest.removeProblem(contest_alias=alias,
                                     problem_alias=problem)

    # Adding contestants
    targetContestants: Sequence[str] = contestConfig.get('contestants',
                                                         {}).get('users', [])
    targetContestantGroups: Sequence[str] = contestConfig.get(
        'contestants', {}).get('groups', [])

    allContestants = client.contest.users(contest_alias=alias)

    if len(targetContestants) > 0:
        contestants = {c['username'].lower() for c in allContestants['users']}

        desiredContestants = {
            contestant.lower()
            for contestant in targetContestants
        }

        contestantsToRemove = contestants - desiredContestants
        contestantsToAdd = desiredContestants - contestants

        for contestant in contestantsToAdd:
            logging.info('Adding contestant: %s', contestant)
            client.contest.addUser(contest_alias=alias,
                                   usernameOrEmail=contestant)

        for contestant in contestantsToRemove:
            logging.info('Removing contestant: %s', contestant)
            client.contest.removeUser(contest_alias=alias,
                                      usernameOrEmail=contestant)

    contestantGroups = {c['alias'].lower() for c in allContestants['groups']}

    desiredGroups = {group.lower() for group in targetContestantGroups}

    groupsToRemove = contestantGroups - desiredGroups
    groupsToAdd = desiredGroups - contestantGroups

    for group in groupsToAdd:
        logging.info('Adding contestant group: %s', group)
        client.contest.addGroup(contest_alias=alias, group=group)

    for group in groupsToRemove:
        logging.info('Removing contestant group: %s', group)
        client.contest.removeGroup(contest_alias=alias, group=group)

    logging.info("Sucessfully upserted contest %s", title)
