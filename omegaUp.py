import requests

class omegaUp:
    url = "https://omegaup.com"
    auth_token = None

    def query(self, method, endpoint, payload = {}, files = None):
        if self.auth_token is not None:
            payload['auth_token'] = self.auth_token

        if method == 'GET':
            r = requests.get(self.url + endpoint, params = payload)
        elif method == 'POST':
            r = requests.post(self.url + endpoint, params = payload, files = files)
        else:
            raise Exception(method)

        response = r.json()

        if response['status'] != 'ok':
            raise Exception(response)

        return response

    def login(self):
        payload = {"usernameOrEmail": self.user, "password": self.pwd}

        response = self.query("GET", "/api/user/login", payload)

        self.auth_token = response['auth_token']

    def session(self):
        return self.query("GET", "/api/session/currentsession")

    def uploadProblem(self, problem, zipPath, message):
        payload = {
            'problem_alias': problem.config['alias'],
            'message': message,
        }

        payload.update(problem.config.get('params', {}))

        languages = payload.get('languages', '')

        if languages == 'all':
            payload['languages'] = 'c,cpp,cpp11,cs,hs,java,pas,py,rb,lua'
        elif languages == 'karel':
            payload['languages'] = 'kp,kj'

        print(payload)

        files = { 'problem_contents': open(zipPath, 'rb') }

        return self.query("POST", "/api/problem/update", payload, files)

    def __init__(self, user, pwd):
        self.user = user
        self.pwd = pwd
