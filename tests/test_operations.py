'''
Test ldap operations on a test instance of slapd.
'''

import pytest
import slapdtest

import ezldap

@pytest.fixture(scope='module')
def slapd():
    instance = slapdtest.SlapdObject()
    instance.start()
    
    global binddn
    binddn = instance.root_dn

    global con
    config = {
        'host': instance.ldap_uri,
        'binddn': instance.root_dn,
        'bindpw': instance.root_pw}
    con = ezldap.auto_bind(config)


def test_bind_success(slapd):
    assert con.whoami_s() == 'dn:' + binddn
