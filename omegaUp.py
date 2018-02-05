import requests
import logging

class omegaUp:
    url = "https://omegaup.com"
    auth_token = None

    def query(self, method, endpoint, payload = {}, files = None, canFail = False):
        def filterKey(x, k):
            tmp = dict(x)
            if k in tmp:
                tmp[k] = 'REMOVED'
            return tmp

        logging.info('Calling endpoint: ' + endpoint)
        logging.info('Payload: ' + str(filterKey(payload, 'password')))

        if self.auth_token is not None:
            payload['auth_token'] = self.auth_token

        if method == 'GET':
            r = requests.get(self.url + endpoint, params = payload)
        elif method == 'POST':
            r = requests.post(self.url + endpoint, params = payload, files = files)
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
        return True # welp
        # payload = { 'problem_alias': alias }
        # response = self.query("GET", "/api/problem/stats", payload, canFail = True)
        # return response['status'] == 'ok'

    def problemExists(self, alias):
        payload = { 'problem_alias': alias }
        response = self.query("GET", "/api/problem/details", payload, canFail = True)
        return response['status'] == 'ok'

    def problemAdmins(self, alias):
        payload = { 'problem_alias': alias }
        return self.query("GET", "/api/problem/admins", payload)

    def addAdmin(self, alias, user):
        payload = { 'problem_alias': alias,
                    "usernameOrEmail": user }
        return self.query("GET", "/api/problem/addAdmin", payload)

    def removeAdmin(self, alias, user):
        payload = { 'problem_alias': alias,
                    "usernameOrEmail": user }
        return self.query("GET", "/api/problem/removeAdmin", payload)

    def addAdminGroup(self, alias, group):
        payload = { 'problem_alias': alias,
                    "group": group }
        return self.query("GET", "/api/problem/addGroupAdmin", payload)

    def removeAdminGroup(self, alias, group):
        payload = { 'problem_alias': alias,
                    "group": group }
        return self.query("GET", "/api/problem/removeGroupAdmin", payload)

    def uploadProblem(self, problem, zipPath, message):
        payload = {
            'message': message,
        }

        create = False

        exists = self.problemExists(problem.alias)
        isAdmin = self.isProblemAdmin(problem.alias)

        if exists and not isAdmin:
            raise Exception("Problem exists but user can't edit.")

        if not exists:
            if not problem.create:
                raise Exception("Problem doesn't exist but creation is disabled.")
            create = True

        payload.update(problem.config.get('params', {}))

        languages = payload.get('languages', '')

        if languages == 'all':
            payload['languages'] = 'c,cpp,cpp11,cs,hs,java,lua,pas,py,rb'
        elif languages == 'karel':
            payload['languages'] = 'kj,kp'
        elif languages == 'none':
            payload['languages'] = ''

        files = { 'problem_contents': open(zipPath, 'rb') }

        payload['problem_alias'] = problem.alias

        if create:
            endpoint = "/api/problem/create"
        else:
            endpoint = "/api/problem/update"

        self.query("POST", endpoint, payload, files)

        if problem.admins is not None or problem.adminGroups is not None:
            allAdmins = self.problemAdmins(problem.alias)

        if problem.admins is not None:
            admins = { a['username'].lower() \
                       for a in allAdmins['admins'] \
                       if a['role'] == 'admin' }

            desiredAdmins = {admin.lower() for admin in problem.admins}

            adminsToRemove = admins - desiredAdmins - {self.user.lower()}
            adminsToAdd = desiredAdmins - admins - {self.user.lower()}

            for admin in adminsToRemove:
                logging.info('Removing problem admin: ' + admin)
                self.removeAdmin(problem.alias, admin)

            for admin in adminsToAdd:
                logging.info('Adding problem admin: ' + admin)
                self.addAdmin(problem.alias, admin)

        if problem.adminGroups is not None:
            adminGroups = { a['name'].lower() \
                            for a in allAdmins['group_admins'] \
                            if a['role'] == 'admin' }

            desiredGroups = {group.lower() for group in problem.adminGroups}

            groupsToRemove = adminGroups - desiredGroups
            groupsToAdd = desiredGroups - adminGroups

            for group in groupsToRemove:
                logging.info('Removing problem admin group: ' + group)
                self.removeAdminGroup(problem.alias, group)

            for group in groupsToAdd:
                logging.info('Adding problem admin group: ' + group)
                self.addAdminGroup(problem.alias, group)

    def __init__(self, user, pwd):
        self.user = user
        self.pwd = pwd
