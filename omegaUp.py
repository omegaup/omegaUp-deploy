import requests
import logging
import sys

class omegaUp:
    url = "https://omegaup.com"
    auth_token = None

    def query(self, method, endpoint, payload={}, files=None, canFail=False):
        def filterKey(x, k):
            tmp = dict(x)
            if k in tmp:
                tmp[k] = 'REMOVED'
            return tmp

        logging.info('Calling endpoint: ' + endpoint)
        logging.info('Payload: ' + str(filterKey(payload, 'password')))

        if self.auth_token is not None:
            payload['ouat'] = self.auth_token

        longTime = 60 * 10 # 10 minutes

        if method == 'GET':
            r = requests.get(self.url + endpoint, params=payload, timeout=longTime)
        elif method == 'POST':
            r = requests.post(self.url + endpoint, params=payload, files=files, timeout=longTime)
        else:
            raise Exception(method)

        try:
            response = r.json()
        except Exception:
            logging.exception(r.text)
            raise

        logging.info('Response: ' + str(filterKey(response, 'auth_token')))

        if not canFail and response['status'] != 'ok':
            raise Exception(response)

        return response

    def login(self):
        payload = {"usernameOrEmail": self.user, "password": self.pwd}

        response = self.query("GET", "/api/user/login", payload)

        self.auth_token = response['auth_token']

    def session(self):
        return self.query("GET", "/api/session/currentsession")

    def isProblemAdmin(self, alias):
        return True  # welp
        # payload = { 'problem_alias': alias }
        # response = self.query("GET", "/api/problem/stats", payload, canFail = True)
        # return response['status'] == 'ok'

    def problemExists(self, alias):
        payload = {'problem_alias': alias}
        response = self.query(
            "GET", "/api/problem/details", payload, canFail=True)
        return response.get('status') == 'ok'

    def problemTags(self, alias):
        payload = {'problem_alias': alias}
        return self.query("GET", "/api/problem/tags", payload)

    def addProblemTag(self, alias, tag, visibility):
        payload = {'problem_alias': alias,
                   'name': tag,
                   'public': visibility}
        return self.query("GET", "/api/problem/addTag", payload)

    def removeProblemTag(self, alias, tag):
        payload = {'problem_alias': alias,
                   'name': tag}
        return self.query("GET", "/api/problem/removeTag", payload)

    def problemAdmins(self, alias):
        payload = {'problem_alias': alias}
        return self.query("GET", "/api/problem/admins", payload)

    def addAdmin(self, alias, user):
        payload = {'problem_alias': alias,
                   "usernameOrEmail": user}
        return self.query("GET", "/api/problem/addAdmin", payload)

    def removeAdmin(self, alias, user):
        payload = {'problem_alias': alias,
                   "usernameOrEmail": user}
        return self.query("GET", "/api/problem/removeAdmin", payload)

    def addAdminGroup(self, alias, group):
        payload = {'problem_alias': alias,
                   "group": group}
        return self.query("GET", "/api/problem/addGroupAdmin", payload)

    def removeAdminGroup(self, alias, group):
        payload = {'problem_alias': alias,
                   "group": group}
        return self.query("GET", "/api/problem/removeGroupAdmin", payload)

    def uploadProblem(self, problem, canCreate, zipPath, message):
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
            payload['languages'] = 'c11-gcc,c11-clang,cpp11-gcc,cpp11-clang,cpp17-gcc,cpp17-clang,cs,hs,java,lua,pas,py2,py3,rb'
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
            admins = {a['username'].lower()
                      for a in allAdmins['admins']
                      if a['role'] == 'admin'}

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
            adminGroups = {a['alias'].lower()
                           for a in allAdmins['group_admins']
                           if a['role'] == 'admin'}

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
            tags = {t['name'].lower() for t in
                    self.problemTags(alias)['tags']}

            restrictedTags = {'karel', 'lenguaje', 'solo-salida', 'interactive'}

            desiredTags = {t.lower() for t in misc['tags']}

            tagsToRemove = tags - desiredTags - restrictedTags
            tagsToAdd = desiredTags - tags - restrictedTags

            for tag in tagsToAdd:
                logging.info('Adding problem tag: ' + tag)
                self.addProblemTag(alias, tag,
                                   payload.get('visibility', '0'))

            for tag in tagsToRemove:
                logging.info('Removing problem tag: ' + tag)
                self.removeProblemTag(alias, tag)

    def __init__(self, user, pwd):
        self.user = user
        self.pwd = pwd
