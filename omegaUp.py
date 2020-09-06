import logging
import requests
import sys
import urllib.parse

from typing import Any, BinaryIO, Dict, Mapping, Optional


def _filterKey(x: Mapping[str, Any], k: str) -> Dict[str, Any]:
    tmp: Dict[str, Any] = dict(x)
    if k in tmp:
        tmp[k] = 'REMOVED'
    return tmp


ApiReturnType = Dict[str, Any]


class omegaUp:
    def __init__(self, user: str, pwd: str):
        self.user = user
        self.pwd = pwd
        self.auth_token: Optional[str] = None
        self.url= 'https://omegaup.com'

    def query(self,
              method: str,
              endpoint: str,
              payload: Optional[Mapping[str, str]] = None,
              files: Optional[Mapping[str, BinaryIO]] = None,
              canFail: bool = False) -> ApiReturnType:
        if payload is None:
            payload = {}
        else:
            payload = dict(payload)

        logging.info('Calling endpoint: %s', endpoint)
        logging.info('Payload: %s', _filterKey(payload, 'password'))

        if self.auth_token is not None:
            payload['ouat'] = self.auth_token

        longTime = 60 * 10  # 10 minutes

        if method == 'GET':
            r = requests.get(urllib.parse.urljoin(self.url, endpoint),
                             params=payload,
                             timeout=longTime)
        elif method == 'POST':
            r = requests.post(urllib.parse.urljoin(self.url, endpoint),
                              params=payload,
                              files=files,
                              timeout=longTime)
        else:
            raise NotImplementedError(method)

        try:
            response: ApiReturnType = r.json()
        except:
            logging.exception(r.text)
            raise

        logging.info('Response: %s', _filterKey(response, 'auth_token'))

        if not canFail and response['status'] != 'ok':
            raise Exception(response)

        return response

    def login(self) -> None:
        payload = {"usernameOrEmail": self.user, "password": self.pwd}

        response = self.query("GET", "/api/user/login", payload)

        self.auth_token = response['auth_token']

    def session(self) -> ApiReturnType:
        return self.query("GET", "/api/session/currentsession")

    def isProblemAdmin(self, alias: str) -> bool:
        return True  # welp
        # payload = { 'problem_alias': alias }
        # response = self.query("GET", "/api/problem/stats", payload, canFail = True)
        # return response['status'] == 'ok'

    def problemExists(self, alias: str) -> bool:
        payload = {'problem_alias': alias}
        response = self.query("GET",
                              "/api/problem/details",
                              payload,
                              canFail=True)
        return response.get('status') == 'ok'

    def problemTags(self, alias: str) -> ApiReturnType:
        payload = {'problem_alias': alias}
        return self.query("GET", "/api/problem/tags", payload)

    def addProblemTag(self, alias: str, tag: str,
                      visibility: bool) -> ApiReturnType:
        payload = {
            'problem_alias': alias,
            'name': tag,
            'public': 'true' if visibility else 'false',
        }
        return self.query("GET", "/api/problem/addTag", payload)

    def removeProblemTag(self, alias: str, tag: str) -> ApiReturnType:
        payload = {'problem_alias': alias, 'name': tag}
        return self.query("GET", "/api/problem/removeTag", payload)

    def problemAdmins(self, alias: str) -> ApiReturnType:
        payload = {'problem_alias': alias}
        return self.query("GET", "/api/problem/admins", payload)

    def addAdmin(self, alias: str, user: str) -> ApiReturnType:
        payload = {'problem_alias': alias, "usernameOrEmail": user}
        return self.query("GET", "/api/problem/addAdmin", payload)

    def removeAdmin(self, alias: str, user: str) -> ApiReturnType:
        payload = {'problem_alias': alias, "usernameOrEmail": user}
        return self.query("GET", "/api/problem/removeAdmin", payload)

    def addAdminGroup(self, alias: str, group: str) -> ApiReturnType:
        payload = {'problem_alias': alias, "group": group}
        return self.query("GET", "/api/problem/addGroupAdmin", payload)

    def removeAdminGroup(self, alias: str, group: str) -> ApiReturnType:
        payload = {'problem_alias': alias, "group": group}
        return self.query("GET", "/api/problem/removeGroupAdmin", payload)

    def uploadProblem(self, problem: Mapping[str, Any], canCreate: bool,
                      zipPath: str, message: str) -> None:
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
            'email_clarifications': misc['email_clarifications']
        }

        sys.stderr.write(str(problem))

        exists = self.problemExists(alias)
        isAdmin = self.isProblemAdmin(alias)

        if exists and not isAdmin:
            raise Exception("Problem exists but user can't edit.")

        if not exists:
            if not canCreate:
                raise Exception("Problem doesn't exist!")
            logging.info("Problem doesn't exist. Creating problem.")
            endpoint = "/api/problem/create"
        else:
            endpoint = "/api/problem/update"

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

        self.query("POST", endpoint, payload, files)

        targetAdmins = misc.get('admins', [])
        targetAdminGroups = misc.get('admin-groups', [])

        if targetAdmins or targetAdminGroups:
            allAdmins = self.problemAdmins(alias)

        if targetAdmins is not None:
            admins = {
                a['username'].lower()
                for a in allAdmins['admins'] if a['role'] == 'admin'
            }

            desiredAdmins = {admin.lower() for admin in targetAdmins}

            adminsToRemove = admins - desiredAdmins - {self.user.lower()}
            adminsToAdd = desiredAdmins - admins - {self.user.lower()}

            for admin in adminsToAdd:
                logging.info('Adding problem admin: ' + admin)
                self.addAdmin(alias, admin)

            for admin in adminsToRemove:
                logging.info('Removing problem admin: ' + admin)
                self.removeAdmin(alias, admin)

        if targetAdminGroups is not None:
            adminGroups = {
                a['alias'].lower()
                for a in allAdmins['group_admins'] if a['role'] == 'admin'
            }

            desiredGroups = {group.lower() for group in targetAdminGroups}

            groupsToRemove = adminGroups - desiredGroups
            groupsToAdd = desiredGroups - adminGroups

            for group in groupsToAdd:
                logging.info('Adding problem admin group: ' + group)
                self.addAdminGroup(alias, group)

            for group in groupsToRemove:
                logging.info('Removing problem admin group: ' + group)
                self.removeAdminGroup(alias, group)

        if 'tags' in misc:
            tags = {t['name'].lower() for t in self.problemTags(alias)['tags']}

            desiredTags = {t.lower() for t in misc['tags']}

            tagsToRemove = tags - desiredTags
            tagsToAdd = desiredTags - tags

            for tag in tagsToRemove:
                if 'problemRestrictedTag' in tag:
                    logging.info('Skipping restricted tag: ' + tag)
                else:
                    self.removeProblemTag(alias, tag)

            for tag in tagsToAdd:
                logging.info('Adding problem tag: ' + tag)
                self.addProblemTag(alias, tag, payload.get('visibility', '0'))
