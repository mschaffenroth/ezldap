'''
Test ldap operations on a test instance of slapd.
'''

import pytest
import ezldap

PREFIX = 'ezldap/templates/'
LDIF_PREFIX = 'tests/ldif/'

def test_ping(slapd, config):
    assert ezldap.ping(config['host'])
    assert not ezldap.ping('ldap://localhost:1234')


def test_dn_address():
    assert ezldap.dn_address('dc=ezldap,dc=io') == 'ezldap.io'
    assert ezldap.dn_address('ou=Hosts,dc=ezldap,dc=io') == 'hosts.ezldap.io'
    assert ezldap.dn_address('cn=spaces in,ou=Hosts,dc=ezldap,dc=io') == 'spaces-in.hosts.ezldap.io'


def test_clean_uri(slapd):
    assert ezldap.ping('ldap:///')
    assert ezldap.ping('ldap://localhost/')


def test_starttls(slapd):
    assert slapd.tls_started
    assert not slapd.server.ssl


def test_636(slapd):
    ssl = ezldap.Connection('ldaps://localhost')
    assert ssl.server.ssl


def test_bind_success(slapd):
    '''
    If this fails, the bind has failed.
    '''
    assert slapd.who_am_i() == 'dn:cn=Manager,dc=ezldap,dc=io'


def test_anon_bind(anon):
    '''
    Do several tests on the anonymous bind.
    '''
    assert anon.who_am_i() is None
    assert anon.base_dn() == 'dc=ezldap,dc=io'
    assert len(anon.search_list('(objectClass=organizationalUnit)')) == 3
    assert len(anon.search_list('(objectClass=applicationProcess)')) == 0


def test_no_cred_carryover(slapd):
    '''
    Make sure bindpw and binddn aren't passed to LDIF templates unintentionally.
    '''
    assert 'bindpw' not in slapd.conf.keys()
    assert 'binddn' not in slapd.conf.keys()


def test_base_dn(slapd):
    '''
    Do we retrieve the correct base dn?
    '''
    assert slapd.base_dn() == 'dc=ezldap,dc=io'


def test_search_list(slapd):
    '''
    Does search_list() return the correct number of entries?
    '''
    assert len(slapd.search_list('(objectClass=organizationalUnit)')) == 3
    assert len(slapd.search_list('(objectClass=applicationProcess)')) == 0


def test_search_list_encapsulation(slapd):
    '''
    Dump entire DIT and ensure every attribute of entries returned is
    encapsulated in a list.
    '''
    query = slapd.search_list()
    for res in query:
        for v in res.values():
            assert isinstance(v, list)


def test_search_list_t(slapd):
    '''
    Does search_list_t() return data properly?
    '''
    query = slapd.search_list_t('(objectClass=organizationalUnit)')
    assert set(query['ou']) == {'Group', 'People', 'Hosts'}
    fail = slapd.search_list_t('(objectClass=applicationProcess)')
    assert set(fail['dn']) == set()


def test_search_list_t_noattr(slapd):
    '''
    When not searching for an attribute, search_list_t should only return
    a dict with one entry: dn.
    '''
    query = slapd.search_list_t(attributes=None)
    assert None not in query.keys()


def test_search_list_t_attribute_nonlist(slapd):
    '''
    Does search_list_t fail if attributes is not a list?
    '''
    query = slapd.search_list_t('(objectClass=organizationalUnit)', 'ou')
    assert 'ou' in query.keys()
    query = slapd.search_list_t('(objectClass=organizationalUnit)', ['ou'])
    assert 'ou' in query.keys()


def test_search_list_t_num_unpacking(slapd):
    '''
    Does search_list_t()'s unpack_lists fail when unpacking lists of numbers?
    '''
    slapd.add_group('unpack_lists_test', ldif_path=PREFIX+'add_group.ldif')
    assert len(slapd.search_list_t('(objectClass=posixGroup)')) > 0


def test_search_df(slapd):
    '''
    Does the search_df function return a Pandas DataFrame and is it collapsing
    lists to a "|" delimited string correctly?
    '''
    # dump entire DIT
    df = slapd.search_df()
    ezldapio = df[df['dn'] == 'dc=ezldap,dc=io']
    assert '|' not in ezldapio['dc'].iloc[0]
    assert '|' in ezldapio['objectClass'].iloc[0]
    assert 'organization' in ezldapio['objectClass'].iloc[0]
    assert 'dcObject' in ezldapio['objectClass'].iloc[0]


def test_exists(slapd):
    '''
    Can we properly detect if entities exist or not.
    '''
    assert slapd.exists('dc=ezldap,dc=io')
    assert not slapd.exists('uid=ooga,ou=booga,dc=ezldap,dc=io')


def test_add_group(slapd):
    '''
    Test adding a group.
    '''
    slapd.add_group('testgroup', ldif_path=PREFIX+'add_group.ldif')
    assert slapd.get_group('testgroup')['dn'][0] == 'cn=testgroup,ou=Group,dc=ezldap,dc=io'
    slapd.add_group('testgroup2', gid=50000, ldif_path=PREFIX+'add_group.ldif')
    assert slapd.get_group('testgroup2')['gidNumber'][0] == 50000


def test_add_user(slapd):
    '''
    Test adding a user to an existing group.
    '''
    slapd.add_group('adduser', gid=50001, ldif_path=PREFIX+'add_group.ldif')
    # by groupname
    slapd.add_user('user1', 'adduser', 'test1234', ldif_path=PREFIX+'add_user.ldif')
    assert slapd.get_user('user1')['uid'][0] == 'user1'

    # by gid
    slapd.add_user('user2', None, 'test1234', gid=50001, ldif_path=PREFIX+'add_user.ldif')
    query = slapd.get_user('user2')
    assert query['dn'][0] == 'uid=user2,ou=People,dc=ezldap,dc=io'

    # is the password set correctly?
    passwd = query['userPassword'][0].decode()
    assert ezldap.ssha_check(passwd, 'test1234')


def test_add_to_group(slapd):
    '''
    Test adding a user to a group using ldif templates.
    '''
    slapd.add_group('group_for_user', ldif_path=PREFIX+'add_group.ldif')
    slapd.add_user('user1234', 'group_for_user', 'password123456', ldif_path=PREFIX+'add_user.ldif')
    slapd.add_to_group('user1234', 'group_for_user', ldif_path=PREFIX+'add_to_group.ldif')
    assert 'user1234' in slapd.get_group('group_for_user')['memberUid']


def test_add_host_short(slapd):
    '''
    Test adding a host to a directory with short hostname.
    '''
    slapd.add_host('host_short', '1.2.3.123', ldif_path=PREFIX+'add_host.ldif')
    host = slapd.get_host('host_short')
    assert 'host_short.ezldap.io' in host['cn']
    assert 'host_short' in host['cn']
    assert '1.2.3.123' in host['ipHostNumber']


def test_add_host_fq(slapd):
    '''
    Test adding a host to a directory with short hostname.
    '''
    slapd.add_host('host_fq', '1.2.3.124', hostname_fq='host_fq.test.com',
        ldif_path=PREFIX+'add_host.ldif')
    host = slapd.get_host('host_fq')
    assert 'host_fq.test.com' in host['cn']
    assert 'host_fq' in host['cn']
    assert '1.2.3.124' in host['ipHostNumber']


def test_add_host_invalid_ip(slapd):
    '''
    Test adding a host to a directory with short hostname.
    '''
    with pytest.raises(ValueError) as error:
        slapd.add_host('host_short2', '1.2.1.12312355',
            ldif_path=PREFIX+'add_host.ldif')
        assert 'does not appear to be an IPv4' in error.value


def test_modify_add(slapd):
    '''
    Does modify_add() add entries properly?
    '''
    slapd.add_group('modify_add', ldif_path=PREFIX+'add_group.ldif')
    slapd.modify_add('cn=modify_add,ou=Group,dc=ezldap,dc=io', 'cn', 'added')
    group = slapd.get_group('modify_add')
    assert len(group['cn']) == 2
    assert 'added' in group['cn']


def test_modify_replace(slapd):
    '''
    Does modify_replace() replace entries properly?
    '''
    slapd.add_group('modify_replace', ldif_path=PREFIX+'add_group.ldif')
    slapd.modify_add('cn=modify_replace,ou=Group,dc=ezldap,dc=io', 'memberUid', 'test')
    slapd.modify_replace('cn=modify_replace,ou=Group,dc=ezldap,dc=io', 'memberUid', 'work_please')
    group = slapd.get_group('modify_replace')
    assert len(group['memberUid']) == 1
    assert group['memberUid'][0] == 'work_please'


def test_modify_delete(slapd):
    '''
    Does modify_delete() delete entries properly?
    '''
    slapd.add_group('modify_delete', ldif_path=PREFIX+'add_group.ldif')
    # test delete from multiple attributes
    slapd.modify_add('cn=modify_delete,ou=Group,dc=ezldap,dc=io', 'cn', 'added')
    slapd.modify_delete('cn=modify_delete,ou=Group,dc=ezldap,dc=io', 'cn', 'added')
    group = slapd.get_group('modify_delete')
    assert len(group['cn']) == 1
    assert 'added' not in group['cn']

    # test delete from single, non-structural attributes
    slapd.modify_add('cn=modify_delete,ou=Group,dc=ezldap,dc=io', 'memberUid', 'test')
    group = slapd.get_group('modify_delete')
    assert 'memberUid' in group.keys()
    slapd.modify_delete('cn=modify_delete,ou=Group,dc=ezldap,dc=io', 'memberUid', 'test')
    group = slapd.get_group('modify_delete')
    assert 'memberUid' not in group.keys()


def test_modify_delete_all(slapd):
    '''
    Does modify_delete() delete entries properly?
    '''
    slapd.add_group('modify_delete', ldif_path=PREFIX+'add_group.ldif')
    # test delete from multiple attributes
    slapd.modify_add('cn=modify_delete,ou=Group,dc=ezldap,dc=io', 'memberUid', 'added')
    slapd.modify_delete('cn=modify_delete,ou=Group,dc=ezldap,dc=io', 'memberUid', None)
    group = slapd.get_group('modify_delete')
    assert 'memberUid' not in group.keys()

def test_ldif_add(slapd):
    '''
    Does Connection.ldif_add() add entries properly?
    '''
    ldif = ezldap.ldif_read(LDIF_PREFIX+'test_ldif_add.ldif')
    results = slapd.ldif_add(ldif)
    assert results[0]['result'] == 0
    assert results[1]['result'] == 0
    user = slapd.get_user('someuser')
    assert user['cn'][0] == 'someuser'
    group = slapd.get_group('somegroup')
    assert group['cn'][0] == 'somegroup'


def test_ldif_add_fail(slapd):
    '''
    Does Connection.ldif_add() add entries properly?
    '''
    ldif = ezldap.ldif_read(LDIF_PREFIX+'test_ldif_add_fail.ldif')
    results = slapd.ldif_add(ldif)
    assert results[0]['result'] != 0
    assert slapd.get_user('someuser2') is None


def test_ldif_modify(slapd):
    '''
    Add an object then modify it with a giant ldif-change LDIF to test the
    ldif_modify method.
    '''
    ldif = ezldap.ldif_read(LDIF_PREFIX+'test_ldif_change_orig.ldif')
    slapd.ldif_add(ldif)
    ldif_change = ezldap.ldif_read(LDIF_PREFIX+'test_ldif_change.ldif')
    result = slapd.ldif_modify(ldif_change)
    assert result[0]['result'] == 0
    user = slapd.get_user('ldif_mod_test')
    assert 'test1@ezldap.io' in user['mail']
    assert 'test2@ezldap.io' in user['mail']
    assert 'shadowLastChange' not in user.keys()
    assert 'gecos' not in user.keys()
    assert user['cn'][0] == 'New name'
