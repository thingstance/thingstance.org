import os

class Config(object):
    DEBUG = False
    REGISTER_DOMAIN=os.environ['REGISTER_DOMAIN']
    BASE_URL=os.environ['BASE_URL']
    MONGO_URI=os.environ['MONGO_URI']
    PAGE_SIZE=int(os.environ['PAGE_SIZE'])

class DevelopmentConfig(Config):
    DEBUG = True

class TestConfig(DevelopmentConfig):
    TESTING = True
