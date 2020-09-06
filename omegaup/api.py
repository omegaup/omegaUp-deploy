"""A Python implementation of the omegaUp API."""
import datetime
import logging
import requests
import urllib.parse

from typing import Any, BinaryIO, Dict, Iterable, Mapping, Optional

_DEFAULT_TIMEOUT = datetime.timedelta(minutes=1)


def _filterKeys(d: Mapping[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    """Returns a copy of the mapping with certain values redacted.

    Any of values mapped to the keys in the `keys` iterable will be replaced
    with the string '[REDACTED]'.
    """
    result: Dict[str, Any] = dict(d)
    for key in keys:
        if key in result:
            result[key] = '[REDACTED]'
    return result


ApiReturnType = Dict[str, Any]
"""The return type of any of the API requests."""


class Session:
    """The Session API."""
    def __init__(self, api: 'API') -> None:
        self._api = api

    def currentSession(self,
                       timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
                       check: bool = True) -> ApiReturnType:
        """Returns information about the current session."""
        return self._api.query('/api/session/currentsession/',
                               timeout=timeout,
                               check=check)


class Problem:
    """The Problem API."""
    def __init__(self, api: 'API') -> None:
        self._api = api

    def details(self,
                alias: str,
                timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
                check: bool = True) -> ApiReturnType:
        """Returns the chosen problem's details."""
        return self._api.query('/api/problem/details/',
                               payload={'problem_alias': alias},
                               timeout=timeout,
                               check=check)

    def admins(self,
               alias: str,
               timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
               check: bool = True) -> ApiReturnType:
        """Returns the chosen problem's administrator users."""
        return self._api.query('/api/problem/admins/',
                               payload={'problem_alias': alias},
                               timeout=timeout,
                               check=check)

    def tags(self,
             alias: str,
             timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
             check: bool = True) -> ApiReturnType:
        """Returns the chosen problem's tag list."""
        return self._api.query('/api/problem/tags/',
                               payload={'problem_alias': alias},
                               timeout=timeout,
                               check=check)

    def addTag(self,
               alias: str,
               tag: str,
               public: bool,
               timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
               check: bool = True) -> ApiReturnType:
        """Add a tag to the chosen problem."""
        return self._api.query('/api/problem/addTag/',
                               payload={
                                   'problem_alias': alias,
                                   'name': tag,
                                   'public': 'true' if public else 'false',
                               },
                               timeout=timeout,
                               check=check)

    def exists(self, alias: str) -> bool:
        """Returns whether a problem exists."""
        return self.details(alias=alias, check=False).get('status') == 'ok'

    def removeTag(self,
                  alias: str,
                  tag: str,
                  timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
                  check: bool = True) -> ApiReturnType:
        """Removes a tag from the problem."""
        return self._api.query('/api/problem/removeTag/',
                               payload={
                                   'problem_alias': alias,
                                   'name': tag,
                               },
                               timeout=timeout,
                               check=check)

    def addAdmin(self,
                 alias: str,
                 user: str,
                 timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
                 check: bool = True) -> ApiReturnType:
        """Adds an administrator user to the chosen problem."""
        return self._api.query('/api/problem/addAdmin/',
                               payload={
                                   'problem_alias': alias,
                                   'usernameOrEmail': user
                               },
                               timeout=timeout,
                               check=check)

    def removeAdmin(self,
                    alias: str,
                    user: str,
                    timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
                    check: bool = True) -> ApiReturnType:
        """Removes an administrator user to the chosen problem."""
        return self._api.query('/api/problem/removeAdmin/',
                               payload={
                                   'problem_alias': alias,
                                   'usernameOrEmail': user
                               },
                               timeout=timeout,
                               check=check)

    def addGroupAdmin(self,
                      alias: str,
                      group: str,
                      timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
                      check: bool = True) -> ApiReturnType:
        """Adds an administrator group to the chosen problem."""
        return self._api.query('/api/problem/addGroupAdmin/',
                               payload={
                                   'problem_alias': alias,
                                   'group': group
                               },
                               timeout=timeout,
                               check=check)

    def removeGroupAdmin(self,
                         alias: str,
                         group: str,
                         timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
                         check: bool = True) -> ApiReturnType:
        """Removes an administrator group to the chosen problem."""
        return self._api.query('/api/problem/removeGroupAdmin/',
                               payload={
                                   'problem_alias': alias,
                                   'group': group
                               },
                               timeout=timeout,
                               check=check)


class API:
    def __init__(self,
                 *,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 auth_token: Optional[str] = None,
                 url: str = 'https://omegaup.com') -> None:
        self._url = url
        self.auth_token: Optional[str] = None
        self.username = username
        if auth_token is not None:
            self.auth_token = auth_token
        elif password is not None:
            self.auth_token = self.query('/api/user/login/',
                                         payload={
                                             'usernameOrEmail': username,
                                             'password': password,
                                         })['auth_token']
        self._session: Optional[Session] = None
        self._problem: Optional[Problem] = None

    def query(self,
              endpoint: str,
              payload: Optional[Mapping[str, str]] = None,
              files: Optional[Mapping[str, BinaryIO]] = None,
              timeout: datetime.timedelta = _DEFAULT_TIMEOUT,
              check: bool = True) -> ApiReturnType:
        """Issues a raw query to the omegaUp API."""
        logger = logging.getLogger('omegaup')
        if payload is None:
            payload = {}
        else:
            payload = dict(payload)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('Calling endpoint: %s', endpoint)
            logger.debug('Payload: %s', _filterKeys(payload, {'password'}))

        if self.auth_token is not None:
            payload['ouat'] = self.auth_token

        r = requests.post(urllib.parse.urljoin(self._url, endpoint),
                          params=payload,
                          files=files,
                          timeout=timeout.total_seconds())

        try:
            response: ApiReturnType = r.json()
        except:
            logger.exception(r.text)
            raise

        if logger.isEnabledFor(logging.DEBUG):
            logger.info('Response: %s', _filterKeys(response, {'auth_token'}))

        if check and response['status'] != 'ok':
            raise Exception(response)

        return response

    @property
    def session(self) -> Session:
        """Returns the Session API."""
        if self._session is None:
            self._session = Session(self)
        return self._session

    @property
    def problem(self) -> Problem:
        """Returns the Problem API."""
        if self._problem is None:
            self._problem = Problem(self)
        return self._problem
