'''
Test the ezldap CLI and ensure it works properly.
'''

import re
import subprocess
import ezldap
import pytest

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
    return syscall('EZLDAP_CONFIG=tests/openldap_config.yml ezldap ' + call)


def add_testuser(username):
    return cli('add_user '
        '--ldif-user {}/add_user.ldif '
        '--ldif-group {}/add_group.ldif '
        '--ldif-add-to-group {}/add_to_group.ldif '
        '{}'.format(PREFIX, PREFIX, PREFIX, username))


def add_testgroup(groupname):
    return cli('add_group --ldif {}/add_group.ldif {}'.format(PREFIX, groupname))


def test_parser_syntax():
    '''
    If this test fails, theres a bug in the argparse syntax.
    '''
    stdout = cli('')
    assert 'Valid commands:' in stdout


def test_search(slapd):
    '''
    Does the search CLI successfully spit out a nice LDIF?
    '''
    stdout = cli('search "(objectClass=organizationalUnit)"')
    assert 'dn: ou=Group,dc=ezldap,dc=io' in stdout
    assert 'dn: ou=People,dc=ezldap,dc=io' in stdout


def test_search_w_attributes(slapd):
    '''
    Test out search with attributes as well.
    '''
    stdout = cli('search ou=People ou')
    assert 'People' in stdout
    assert 'objectClass' not in stdout


def test_search_no_paren(slapd):
    '''
    Does the search CLI successfully spit out a nice LDIF?
    '''
    stdout = cli('search objectClass=organizationalUnit')
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


def test_add_user_pw_matches(slapd):
    stdout = add_testuser('pw_should_work')
    pw = re.findall(r'Password: (\S+)', stdout)[0]
    ssha = slapd.get_user('pw_should_work')['userPassword'][0]
    assert ezldap.ssha_check(ssha, pw)


def test_add_to_group(slapd):
    username = 'cli_ag_user'
    groupname = 'cli_ag'
    add_testuser(username)
    add_testgroup(groupname)
    cli('add_to_group --ldif {}/add_to_group.ldif {} {}'.format(PREFIX, username, groupname))
    group = slapd.get_group(groupname)
    assert username in group['memberUid']


def test_add_host_short(slapd):
    hostname = 'host_cli'
    cli('add_host --ldif {}/add_host.ldif {} {}'.format(PREFIX, hostname, '244.1.2.3'))
    host = slapd.get_host(hostname)
    assert 'host_cli' in host['cn']
    assert 'host_cli.ezldap.io' in host['cn']
    assert '244.1.2.3' in host['ipHostNumber']


def test_add_host_fq(slapd):
    hostname = 'host_cli_fq.ezldap.io'
    cli('add_host --ldif {}/add_host.ldif {} {}'.format(PREFIX, hostname, '244.1.2.4'))
    host = slapd.get_host(hostname)
    assert 'host_cli_fq' in host['cn']
    assert 'host_cli_fq.ezldap.io' in host['cn']
    assert '244.1.2.4' in host['ipHostNumber']


def test_add_arbitrary_key(slapd):
    '''
    Test both "--key value" and "--key=value" syntax for arbitrary arguments
    added by the user.
    '''
    cli('add_user '
        '--ldif-user tests/ldif/test_add_user_extra_keys.ldif '
        '--ldif-group {}/add_group.ldif '
        '--ldif-add-to-group {}/add_to_group.ldif '
        '--email=some.email@somewhere.com '
        '--fname=first --lname=last '
        'arb_keys_user'.format(PREFIX, PREFIX))

    user = slapd.get_user('arb_keys_user')
    assert user['mail'][0] == 'some.email@somewhere.com'
    assert user['gecos'][0] == 'first last'
    assert user['givenName'][0] == 'first'
    assert user['sn'][0] == 'last'

    # parsing can go weird depending on where positional arguments are, so
    # lets check that too
    cli('add_user other_arb_user '
        '--ldif-user tests/ldif/test_add_user_extra_keys.ldif '
        '--ldif-group {}/add_group.ldif '
        '--ldif-add-to-group {}/add_to_group.ldif '
        '--email=some.email@somewhere.com '
        '--fname=first --lname=last '.format(PREFIX, PREFIX))
    assert slapd.get_user('other_arb_user') is not None


def test_add_arbitrary_key_fail(slapd):
    '''
    Do lone keys properly fail?
    '''
    with pytest.raises(subprocess.SubprocessError) as e:
        cli('add_group --ldif {}/add_group.ldif --ignoreme {}'.format(PREFIX, 'arb_key_ignored'))
        assert 'will be ignored' in e.value


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
    pw = re.findall(r': (\w+)', stdout.strip())[0]
    user = slapd.get_user(username)
    assert ezldap.ssha_check(user['userPassword'][0], pw)


def test_delete(slapd):
    groupname = 'deleteme'
    add_testgroup(groupname)
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


def test_modify_dn_relative(slapd):
    add_testgroup('mdn_relative')
    cli('modify_dn cn=mdn_relative,ou=Group,dc=ezldap,dc=io cn=mdn_new,ou=Group,dc=ezldap,dc=io')
    assert slapd.exists('cn=mdn_new,ou=Group,dc=ezldap,dc=io')


def test_modify_dn_superior(slapd):
    add_testgroup('mdn_superior')
    cli('modify_dn cn=mdn_superior,ou=Group,dc=ezldap,dc=io cn=mdn_superior,ou=People,dc=ezldap,dc=io')
    assert slapd.exists('cn=mdn_superior,ou=People,dc=ezldap,dc=io')


def test_modify_dn_complete(slapd):
    add_testgroup('mdn_complete')
    cli('modify_dn cn=mdn_complete,ou=Group,dc=ezldap,dc=io cn=complete,ou=People,dc=ezldap,dc=io')
    assert slapd.exists('cn=complete,ou=People,dc=ezldap,dc=io')


def test_add_ldif(slapd):
    cli('add_ldif tests/ldif/test_ldif_add_cli.ldif')
    assert slapd.exists('uid=someuser,ou=People,dc=ezldap,dc=io')
    assert slapd.exists('cn=somegroup,ou=Group,dc=ezldap,dc=io')
    cli('add_ldif tests/ldif/test_ldif_add_cli_replace.ldif --username_cli=work_tyvm')
    assert slapd.exists('uid=work_tyvm,ou=People,dc=ezldap,dc=io')
    assert slapd.exists('cn=work_tyvm,ou=Group,dc=ezldap,dc=io')


def test_modify_ldif(slapd):
    add_testuser('shrek')
    ezldap.ldif_print([slapd.get_user('shrek')])
    cli('modify_ldif tests/ldif/test_ldif_change_cli.ldif')
    user = slapd.get_user('shrek')
    assert 'test1@ezldap.io' in user['mail']
    assert 'test2@ezldap.io' in user['mail']
    assert 'shadowLastChange' not in user.keys()
    assert 'gecos' not in user.keys()
    assert user['cn'][0] == 'New name'


def test_bind_info(slapd):
    stdout = cli('bind_info')
    assert 'user: cn=Manager,dc=ezldap,dc=io' in stdout
    stdout = cli('bind_info -a')
    assert 'user: None' in stdout


def test_server_info(slapd):
    stdout = cli('server_info')
    assert 'dc=ezldap,dc=io' in stdout
    assert 'StartTLS' in stdout


def test_class_info(slapd):
    stdout = cli('class_info inetOrgPerson')
    assert 'Internet Organizational Person' in stdout
    assert '2.5.6.0' in stdout  # make sure we fetched all the way to top

    stdout = cli('class_info inetOrgPerson --no-superior')
    assert 'Internet Organizational Person' in stdout
    assert '2.5.6.0' not in stdout  # make sure we fetched all the way to top

    with pytest.raises(subprocess.SubprocessError) as err:
        stdout = cli('class_info asdf')
        assert 'not found' in err.value


def test_assert_dn_exists(slapd):
    with pytest.raises(subprocess.SubprocessError) as err:
        cli('delete sldkjafldfjka')
        assert 'not found' in err.value
        cli('delete cn=asdfjaksfsjdflkj')
        assert 'not found' in err.value
