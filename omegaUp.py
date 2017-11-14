import requests

class omegaUp:
    url = "https://omegaup.com"
    auth_token = None

    def query(self, method, endpoint, payload = {}, files = None, canFail = False):
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
            print(r.text)
            raise

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
        payload = { 'problem_alias': alias }
        response = self.query("GET", "/api/problem/stats", payload, canFail = True)
        return response['status'] == 'ok'

    def problemExists(self, alias):
        payload = { 'problem_alias': alias }
        response = self.query("GET", "/api/problem/details", payload, canFail = True)
        return response['status'] == 'ok'

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
            payload['languages'] = 'c,cpp,cpp11,cs,hs,java,pas,py,rb,lua'
        elif languages == 'karel':
            payload['languages'] = 'kp,kj'

        files = { 'problem_contents': open(zipPath, 'rb') }

        if create:
            endpoint = "/api/problem/create"
            payload['alias'] = problem.alias
        else:
            endpoint = "/api/problem/update"
            payload['problem_alias'] = problem.alias

        print('Calling endpoint: ' + endpoint)
        print('Payload: ' + str(payload))

        return self.query("POST", endpoint, payload, files)

    def __init__(self, user, pwd):
        self.user = user
        self.pwd = pwd
