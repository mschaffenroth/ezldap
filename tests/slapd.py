import subprocess
import pytest

config = {
    'host': 'ldap://0.0.0.0:389/',
    'binddn': 'cn=Manager,dc=ezldap,dc=io',
    'bindpw': 'password',
    'groupdn': 'ou=Group,dc=ezldap,dc=io',
    'peopledn': 'ou=People,dc=ezldap,dc=io',
    'homedir': '/home'}


@pytest.fixture(scope='session')
def slapd:
    instance = SlapdInstance()
    con = ezldap.auto_bind(config)
    yield con



class SlapdInstance:
    pass