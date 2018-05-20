'''
Test the ezldap CLI and ensure it works properly.
'''

import re
import subprocess
import pytest
import ezldap

PREFIX = 'ezldap/templates/'


def syscall(call):
    '''
    Run syscall and return output.
    '''
    proc = subprocess.Popen(call, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            shell=True, universal_newlines=True)
    stdout, stderr = proc.communicate()
    if proc.returncode > 0:
        raise subprocess.SubprocessError(stdout)

    return stdout


def cli(call):
    return syscall('EZLDAP_CONFIG=tests/ezldap_config.yml ezldap ' + call)


def add_testuser(username):
    cli('add_user '
        '--ldif-user {}/add_user.ldif '
        '--ldif-group {}/add_group.ldif '
        '--ldif-add-to-group {}/add_to_group.ldif '
        '{}'.format(PREFIX, PREFIX, PREFIX, username))


def test_search(slapd):
    '''
    Does the search CLI successfully spit out a nice LDIF?
    '''
    stdout = cli('search "(objectClass=organizationalUnit)"')
    assert 'dn: ou=Group,dc=ezldap,dc=io' in stdout
    assert 'dn: ou=People,dc=ezldap,dc=io' in stdout


def test_search_dn(slapd):
    stdout = cli('search_dn Manager')
    assert 'cn=Manager,dc=ezldap,dc=io' in stdout


def test_add_group(slapd):
    cli('add_group --ldif {}/add_group.ldif cli_testgroup'.format(PREFIX))
    group1 = slapd.get_group('cli_testgroup')
    assert group1['cn'][0] == 'cli_testgroup'


def test_add_group_bygid(slapd):
    cli('add_group --ldif {}/add_group.ldif cli_testgroup2 44444'.format(PREFIX))
    group2 = slapd.get_group('cli_testgroup2')
    assert group2['cn'][0] == 'cli_testgroup2'
    assert group2['gidNumber'][0] == 44444


def test_add_user_nogroup(slapd):
    '''
    Are users properly created when no group exists?
    '''
    username = 'cli_testuser'
    add_testuser(username)
    user = slapd.get_user(username)
    assert user['uid'][0] == username
    group = slapd.get_group(username)
    assert group['cn'][0] == username
    assert username in group['memberUid']


def test_add_user_wgroup(slapd):
    '''
    Are users properly created and added to the group when the group already exists?
    '''
    username, groupname = 'cli_testuser_wgroup', 'cli_user_wgroup'
    cli('add_group --ldif {}/add_group.ldif {}'.format(PREFIX, groupname))
    cli('add_user '
        '--ldif-user {}/add_user.ldif '
        '--ldif-group {}/add_group.ldif '
        '--ldif-add-to-group {}/add_to_group.ldif '
        '{} {}'.format(PREFIX, PREFIX, PREFIX, username, groupname))
    group = slapd.get_group(groupname)
    assert username in group['memberUid']
    user = slapd.get_user(username)
    assert user['uid'][0] == username


def test_add_to_group(slapd):
    username = 'cli_ag_user'
    groupname = 'cli_ag'
    add_testuser(username)
    cli('add_group --ldif {}/add_group.ldif {}'.format(PREFIX, groupname))
    cli('add_to_group --ldif {}/add_to_group.ldif {} {}'.format(PREFIX, username, groupname))
    group = slapd.get_group(groupname)
    assert username in group['memberUid']


def test_change_home(slapd):
    username = 'cli_change_home'
    add_testuser(username)
    cli('change_home {} /mnt/data/username'.format(username))
    user = slapd.get_user(username)
    assert user['homeDirectory'][0] == '/mnt/data/username'


def test_change_shell(slapd):
    username = 'cli_change_shell'
    add_testuser(username)
    cli('change_shell {} /usr/sbin/nologin'.format(username))
    user = slapd.get_user(username)
    assert user['loginShell'][0] == '/usr/sbin/nologin'


def test_change_pw(slapd):
    username = 'cli_change_pw'
    add_testuser(username)
    stdout = cli('change_pw {}'.format(username))
    pw = re.findall(r'- (\w+)', stdout.strip())[0]
    user = slapd.get_user(username)
    assert ezldap.ssha_check(user['userPassword'][0], pw)


@pytest.mark.skip
def test_check_pw(slapd):
    pass


def test_delete(slapd):
    groupname = 'deleteme'
    cli('add_group --ldif {}/add_group.ldif {}'.format(PREFIX, groupname))
    group = slapd.get_group(groupname)
    assert group is not None
    groupdn = group['dn'][0]
    cli('delete -f {}'.format(groupdn))
    assert slapd.get_group('deleteme') is None


def test_modify_add(slapd):
    user = 'modadd'
    add_testuser(user)
    cli('modify uid={},ou=People,dc=ezldap,dc=io add mail test@test.com'.format(user))
    testme = slapd.get_user(user)
    assert 'test@test.com' in testme['mail']


def test_modify_replace_with(slapd):
    user = 'modreplace_with'
    add_testuser(user)
    cli('modify uid={},ou=People,dc=ezldap,dc=io replace gecos {} work_please'.format(user, user))
    testme = slapd.get_user(user)
    print(testme)
    assert 'work_please' == testme['gecos'][0]


def test_modify_replace_nowith(slapd):
    user = 'modreplace_nowith'
    add_testuser(user)
    cli('modify uid={},ou=People,dc=ezldap,dc=io replace shadowWarning 31'.format(user))
    testme = slapd.get_user(user)
    assert 31 == testme['shadowWarning'][0]


def test_modify_delete(slapd):
    '''
    Test deleting a named value.
    '''
    user = 'moddelete'
    add_testuser(user)
    cli('modify uid={},ou=People,dc=ezldap,dc=io delete gecos {}'.format(user, user))
    assert 'gecos' not in slapd.get_user(user).keys()


def test_modify_delete_all(slapd):
    '''
    Test deleting all values when nothing is named.
    '''
    user = 'moddelete_all'
    add_testuser(user)
    cli('modify uid={},ou=People,dc=ezldap,dc=io delete gecos -'.format(user))
    assert 'gecos' not in slapd.get_user(user).keys()


@pytest.mark.skip
def test_modify_dn(slapd):
    pass
