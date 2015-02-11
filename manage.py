#!/usr/bin/env python3

import os
import sys
import json
import time

import requests

from flask.ext.script import Manager
from application import app
from application.registry import Register, registers

app.config.from_object(os.environ['SETTINGS'])
manager = Manager(app)


@manager.option('-s', '--source', dest='source')
def load_data(source):
    for name in os.listdir(source):
        path = os.path.join(source, name)
        if os.path.isdir(path):
            register = Register(name, app.config['MONGO_URI'])
            register.load(path)

@manager.option('-r', '--register-name', dest='register_name')
def deploy(register_name):
    '''
        This command should *only* be run locally, not on heroku.
        It requires your heroku auth token as an environment variable called
        HEROKU_KEY.

        That can be set by running HEROKU_KEY=`heroku auth:token`.

        It uses the heroku platform api to deploy or redeploy a server
        application from master of https://github.com/openregister/server.

        The name of the application will be the argument passed in, e.g.
        'register_name-openregister'.

        If this is the first deploy it will set the hostname for the
        application to 'register_name.openregister.org'. You will need
        to set a CNAME pointing to register_name-openregister.herokuapp.com.
    '''
    heroku_key = "Bearer %s" % os.environ['HEROKU_KEY']
    headers = {"Content-Type" : "application/json",
                "Accept" : "application/vnd.heroku+json; version=3",
                "Authorization" : heroku_key}

    if _exists(register_name, headers):
        _redeploy(register_name, headers)
    else:
        _deploy(register_name, headers)


@manager.option('-r', '--repo-url', dest='repo_url')
def load(repo_url):
    '''
        Takes a url for a register repository
        e.g. https://github.com/openregister/registername.register.

        It will use the last item in the path to work out the register name.
        So in example above register name == registername.

        It will then load the data contained in the repository and
        load it into the register. Currently that means loading the data
        into the mongodb for the register.
    '''
    register_name = repo_url.split('/')[-1].split('.')[0]#ouch
    print('register:', register_name)
    print('repository:', repo_url)
    register = registers.get(register_name)
    if not register:
        register = Register(register_name.capitalize(), app.config['MONGO_URI'])
        registers[register_name] = register
    zip_url = '%s/archive/master.zip' % repo_url
    file_names = register.load_remote(zip_url)
    print('completed load of files:', file_names)


def _deploy(register_name, headers):
    url = 'https://api.heroku.com/app-setups'
    app_name = "%s-openregister" % register_name
    data = { "app": { "name": app_name, "region": "eu"},
            "source_blob": {
            "url":"https://github.com/openregister/server/tarball/master/" },
            "overrides": {"env": { "REGISTERS": register_name, "REGISTER_DOMAIN": "openregister.org"}}}
    print('deploying register:', app_name)
    resp = requests.post(url, data=json.dumps(data), headers=headers)
    deployed = _check_build_status(resp.json(), url)
    if deployed:
        print('setting domain', register_name+".openregisters.org")
        url = "https://api.heroku.com/apps/%s/domains" % app_name
        data = {"hostname": register_name+".openregisters.org"}
        resp = requests.post(url, json.dumps(data), headers=headers)
        print('result:', resp.json())


def _redeploy(register_name, headers):
    app_name = '%s-openregister' % register_name
    url = 'https://api.heroku.com/apps/%s/builds' % app_name
    data =  {"source_blob": {
                "url": "https://github.com/openregister/server/archive/master.tar.gz",
                "version": "v0.1.0"
                }
    }
    print('redeploying', app_name)
    resp = requests.post(url, data=json.dumps(data), headers=headers)
    _check_build_status(resp.json(), url)

def _exists(register_name, headers):
    app_name = '%s-openregister' % register_name
    url = 'https://api.heroku.com/apps/%s' % app_name
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        app_url = resp.json()['web_url']
        print(app_name, 'exists at url:', app_url)
    else:
        print(app_name, 'does not exist')

    return resp.status_code == 200

def _check_build_status(build_response, url):
    build_status = build_response['status']
    build_id = build_response['id']
    print('build status:', build_status)
    print('build id:', build_id)
    if build_status not in ['pending', 'succeeded']:
        print('build error:', build_status, 'message', build['failure_message'])
        sys.exit(1)

    check_url = '%s/%s' % (url, build_id)
    print('check_url:', check_url)
    heroku_key = "Bearer %s" % os.environ['HEROKU_KEY']
    headers = {"Content-Type" : "application/json","Accept" : "application/vnd.heroku+json; version=3", "Authorization" : heroku_key}

    #if not confirmed within five mins move on
    max_poll = 5
    while True and max_poll > 0:
        for i in range(60):
            print('.', end='', flush=True)
            time.sleep(1)
        print('\nchecking build status')
        resp = requests.get(check_url, headers=headers)
        build = resp.json()
        build_status = build['status']
        print('status:', build_status)
        if build_status == 'failed':
            print('build failure:', build['failure_message'])
            sys.exit(1)
        elif build_status == 'succeeded':
            print('build complete')
            app_url = build.get('resolved_success_url')
            if app_url:
                import webbrowser
                webbrowser.open(app_url)
            return True
        max_poll -= 1


if __name__ == '__main__':
    manager.run()
