# ------------------------------------------------------------------#
# Service: gin-proc
# Project: GIN - https://gin.g-node.org
# Documentation: https://github.com/G-Node/gin-proc/blob/master/docs
# API Documentation: <GIN_SERVER_ADDR>/docs/api
# Package: Server (Flask API)
# ------------------------------------------------------------------#


from service import (configure, gin_ensure_token, ensure_key, gin_get_repos,
                     gin_get_user_data, log, drone_ensure_secrets)
from flask import Flask, request, abort, jsonify, Blueprint
from http import HTTPStatus

import errors

from flask_docs import ApiDoc

from flask_cors import CORS, cross_origin
app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

app.config['API_DOC_MEMBER'] = ['api', 'platform', 'auth']

ApiDoc(app)

api = Blueprint('api', __name__)
auth = Blueprint('auth', __name__)
platform = Blueprint('platform', __name__)


class User(object):

    def __init__(self, *args, **kwargs):
        self.username = None
        self.gin_token = None

    def login(self):
        self.username = request.json['username']
        password = request.json['password']

        try:
            self.gin_token = gin_ensure_token(user.username, password)
            log("debug", 'GIN token ensured.')
        except errors.ServerError as e:
            log('critical', e)
            return e, HTTPStatus.INTERNAL_SERVER_ERROR

        if ensure_key(self.gin_token) and drone_ensure_secrets(self.username):
            return {'token': self.gin_token}, HTTPStatus.OK
        else:
            return 'login failed', HTTPStatus.UNAUTHORIZED

    def logout(self):
        user.username = None
        user.gin_token = None
        return "logged out", HTTPStatus.OK

    def details(self):
        return gin_get_user_data(self.gin_token)

    def run(self, request):
        try:
            configure(
                repo_name=request.json['repo'],
                notifications=request.json['notifications'],
                commit_message=request.json['commitMessage'],
                user_commands=list(filter(None, list(
                        request.json['userInputs'].values()))),
                workflow=request.json['workflow'],
                input_files=list(filter(None, list(
                    request.json['annexFiles'].values()))),
                output_files=list(filter(None, list(
                    request.json['backpushFiles'].values()))),
                token=self.gin_token,
                username=self.username
            )
            msg = "Success: workflow pushed to {}".format(request.json['repo'])
            return msg, HTTPStatus.OK
        except errors.ServiceError as e:
            return e, HTTPStatus.INTERNAL_SERVER_ERROR

    def repos(self):
        return jsonify([
            {'value': repo['name'], 'text': self.username + '/' + repo['name']}
            for repo in gin_get_repos(self.username, self.gin_token)
        ])


user = User()


@auth.route('/logout', methods=['POST'])
def logout():
    """
    Clears user's credentials including auth token for the session.
    """
    return user.logout()


@auth.route('/login', methods=['POST'])
@cross_origin()
def login():
    """
    Authenticates user with their GIN credentials.

    @@@
    Ensures following checks in chronological order are passed for succesfull
    authentication:

     - #### Ensure Token
        Runs a check whether GIN already has a `personal access token (PAT)`
        installed on your account specifically for `gin-proc`.
        In case it doesnt (which is highly likely if you are logging in to
        `gin-proc` for the first time), it shall automatically create
        and install a fresh token for you.

     - #### Ensure SSH Keys
        Ensures whether a specific SSH key pair is already installed for use
        by `gin-proc` in GIN. In case it doesn't (which is highly likely if
        you are logging in to `gin-proc` for the first time),
        it shall create a fresh key pair for you and install the appropriate
        key `public key` in GIN so that gin-proc has read/write access to your
        GIN repos.

     - #### Ensure Drone Secrets
        Runs a check to ensure that all of your Drone repositories are
        activated and that they have your subsequent `private-key` installed
        in them as a **secret**. This secret is used by Drone for cloning and
        pushing operations on your GIN repos whilst its running your
        build jobs inside its runners.
    @@@
    """
    try:
        return user.login()
    except errors.ServerError as e:
        abort(e.status)


@auth.route('/user', methods=['GET'])
def get_user():
    """
    Returns logged-in user's data from GIN.
    """
    res = user.details()
    if res.ok:
        return res.json()

    return res.text, res.status_code


@api.route('/execute', methods=['POST'])
@cross_origin()
def execute_workflow():
    """
    Runs the workflow post user's submission from front-end UI.

    For complete documentation of execution steps, read
    https://github.com/G-Node/gin-proc/blob/master/docs/operations.md
    """
    try:
        return user.run(request)
    except errors.ServerError as e:
        abort(e.status)


@api.route('/repos', methods=['GET'])
@cross_origin()
def repositories():
    """
    Returns list of user's repositories from GIN.
    """
    return user.repos()


app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(auth, url_prefix='/auth')
app.register_blueprint(platform, url_prefix='/platform')


if __name__ == '__main__':
    app.run(debug=False, port=8000, host="0.0.0.0")
