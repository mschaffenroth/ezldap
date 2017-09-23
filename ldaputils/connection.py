"""
Bind to an LDAP directory and perform various operations.
"""

import os
import sys
import yaml
import getpass
import re
from collections import OrderedDict

import ldap
import ldap.modlist
from ldap.ldapobject import LDAPObject

def config(path='etc/config.yaml'):
    """
    Load LDAP details from config.yaml (or similar)
    """
    if not os.path.exists(path):
        sys.exit('Error: config file ({}), not found!'.format(path))
    with open(path, 'r') as settings:
        return yaml.load(settings)


def get_attrib_list(query, name):
    """
    Grab all of a certain attribute from an LDAP search query.
    """
    attrs = [obj[1][name] for obj in query]
    # determine if attrs should be unpacked and decoded
    if all([len(attr) == 1 for attr in attrs]):
        attrs = [attr[0].decode() for attr in attrs]

    return attrs


class LDAP(LDAPObject):
    """
    An object-oriented wrapper around an LDAP connection.
    Used to make pyldap's LDAPObject even easier to use.
    """

    def __init__(self, config=config()):
        """
        Create a new connection and bind.
        """
        self.config = config
        super().__init__(config['host'], trace_file=sys.stdout, trace_stack_limit=None)
        self._bind()


    def __enter__(self):
        return self


    def __exit__(self, type_, value, traceback):
        """
        Auto-unbind when used with "with"
        """
        self.unbind_s()
    

    def _bind(self):
        """
        A wrapper function to simplify connecting via a pre-existing config.
        Remember to unbind (con.unbind_s()) when done.
        """
        bind_password = self.config['binddn_pass']
        if bind_password is None:
            print('Enter bind DN password...', file=sys.stderr)
            bind_password = getpass.getpass()
    
        self.simple_bind_s(self.config['binddn'], bind_password)


    def get_placeholders(self):
        """
        Get all uppercase placeholders from config.
        """
        return {k: v for k, v in self.config.items() if k == k.upper()}


    def base_dn(self):
        """
        Detect the base DN from an LDAP connection.
        Uses the bind DN as a "hint".
        """
        whoami = self.whoami_s()
        return re.findall(r'dc=.+$', whoami)[0]


    def next_uidn(self):
        """
        Determine the next available uid number in a directory tree.
        """
        users = self.search_s(self.base_dn(), ldap.SCOPE_SUBTREE, '(uid=*)')
        if len(users) == 0:
            return self.config['uidstart']
    
        uidns = get_attrib_list(users, 'uidNumber')
        uidns = [int(uidn) for uidn in uidns]
        return max(uidns) + 1


    def next_gidn(self):
        """
        Determine the next available gid number in a directory tree.
        """
        groups = self.search_s(self.base_dn(), ldap.SCOPE_SUBTREE, '(objectClass=posixGroup)')
        if len(groups) == 0:
            return self.config['gidstart']
    
        gidns = get_attrib_list(groups, 'gidNumber')
        gidns = [int(gidn) for gidn in gidns]
        return max(gidns) + 1


    def get_user(self, user):
        """
        Return given user
        """
        query = self.search_s(self.config['people'], 
                              ldap.SCOPE_SUBTREE, 
                              '(uid={})'.format(user))
        return query


    def get_group(self, group):
        """
        Return a given group
        """
        query = self.search_s(self.config['group'],
                              ldap.SCOPE_SUBTREE,
                              '(cn={})'.format(group))
        return query


    def ldif_add(self, ldif):
        """
        Perform an add operation using an LDIF object.
        """
        for dn, attrs in ldif.entries.items():
            self.add_s(dn, ldap.modlist.addModlist(attrs))

    

    def ldif_modify(self, ldif):
        """
        Perform an LDIF modify operation from an LDIF object.
        """
        for dn, attrs in ldif.entries.items(): 
            modlist = _create_modify_modlist(attrs)
            self.modify_s(dn, modlist)


def _create_modify_modlist(attrs):
    """
    We need to carefully massage our LDIF object to a 
    pyldap modlist because the pyldap API is super awkward.
    """
    changes = OrderedDict()
    changes['delete'] = ldap.MOD_DELETE
    changes['replace'] = ldap.MOD_REPLACE
    changes['add'] = ldap.MOD_ADD
    
    modlist = []
    for change_type in changes.keys():
        # skip change types that don't occur
        if change_type not in attrs.keys():
            continue

        # else iterate over those values of change type
        for attrib_name in attrs[change_type]:
            attrib_name = attrib_name.decode()
            modlist.append((changes[change_type], 
                            attrib_name, 
                            attrs[attrib_name]))

    return modlist

