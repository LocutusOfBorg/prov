'''Test cases for the prov.server Django app

@author: Trung Dong Huynh <trungdong@donggiang.com>
@copyright: University of Southampton 2012
'''
import unittest, logging, sys, json
from prov.model.test import examples


from django.contrib.auth.models import User,Group
from tastypie.models import ApiKey
from prov.server.models import Container
from django.db import IntegrityError,DatabaseError
from guardian.shortcuts import assign, remove_perm
from django.test.client import Client

logger = logging.getLogger(__name__)       

class AuthenticationTest(unittest.TestCase):
    USER_COUNT = 2
    users = {}
    client = Client()
    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName=methodName)
    
    @classmethod
    def setUpClass(cls):
        super(AuthenticationTest, cls).setUpClass()
        try:
            logging.debug('Creating users...')
            for u in range(cls.USER_COUNT):
                cls.users[u] = User.objects.create_user(username='test'+`u`, password='pass')
        except IntegrityError, DatabaseError:
            sys.exit('Users already exist!')
    
    @classmethod
    def tearDownClass(cls):
        logging.debug('Deleting users...')
        for u in range(cls.USER_COUNT):
            cls.users[u].delete()
    
    def testApiKeyAuth(self):
        logging.debug('Creating API Key for user test0...')
        api_key = ApiKey.objects.create(user=self.users[0]).key
        auth = 'ApiKey ' + self.users[0].username + ':' + api_key
        logging.debug('Executing GET method with the authentication...')
        response = self.client.get('/api/v0/bundle/?format=json', **{'HTTP_AUTHORIZATION': auth})
        self.assertEqual(response.status_code, 200)
        fake_key = ApiKey().generate_key()
        fake_auth = 'ApiKey ' + self.users[0].username + ':' + fake_key
        logging.debug('Executing GET method with same username and fake authentication...')
        response = self.client.get('/api/v0/bundle/?format=json', **{'HTTP_AUTHORIZATION': fake_auth})
        self.assertEqual(response.status_code, 401)
        
    def testAnonymousAuth(self):
        logging.debug('Executing GET method with anonymous user...')
        response = self.client.get('/api/v0/bundle/?format=json')
        self.assertEqual(response.status_code, 200)
        
    def testUserPermissions(self):
        logging.debug('Creating API Key for user test1...')
        api_key = ApiKey.objects.create(user=self.users[1]).key
        auth = 'ApiKey ' + self.users[1].username + ':' + api_key
        bundle = examples.bundles1()
        data="""{"rec_id": "#mockup","content": """+bundle.JSONEncoder().encode(bundle)+'}'
        logging.debug('Executing POST method with the authentication...')
        response = self.client.post('/api/v0/bundle/',data=data,content_type='application/json',
                                    **{'HTTP_AUTHORIZATION': auth})
        
        self.assertEqual(response.status_code, 201)
        bundle = Container.objects.get(id=json.JSONDecoder().decode(response.content)['id'])
        logging.debug('Bundle created with id '+`bundle.id`)
        logging.debug('Checking all raw permissions...')
        self.assertTrue(self.users[1].has_perm('view_container', bundle))
        self.assertTrue(self.users[1].has_perm('change_container', bundle))
        self.assertTrue(self.users[1].has_perm('delete_container', bundle))
        self.assertTrue(self.users[1].has_perm('admin_container', bundle))
        self.assertTrue(self.users[1].has_perm('ownership_container', bundle))
        
        destination = '/api/v0/bundle/' + `bundle.id` + '/?format=json'
        logging.debug('Checking API permissions...')
        response = self.client.get(destination, **{'HTTP_AUTHORIZATION': auth})
        self.assertEqual(response.status_code, 200)
#        response = self.client.put(destination,data=data,content_type='application/json',
#                                    **{'HTTP_AUTHORIZATION': auth})
#        self.assertEqual(response.status_code, 202)
        
        logging.debug('Checking other users raw permissions...')
        self.assertFalse(self.users[0].has_perm('view_container', bundle))
        self.assertFalse(self.users[0].has_perm('change_container', bundle))
        self.assertFalse(self.users[0].has_perm('delete_container', bundle))
        self.assertFalse(self.users[0].has_perm('admin_container', bundle))
        self.assertFalse(self.users[0].has_perm('ownership_container', bundle))
        
        try:
            fake_key = ApiKey.objects.get(user=self.users[0]).key
        except ApiKey.DoesNotExist:
            fake_key = ApiKey.objects.create(user=self.users[0]).key
        fakeauth = 'ApiKey ' + self.users[0].username + ':' + fake_key
        logging.debug('Checking API permissions for other user...')
        response = self.client.get(destination, **{'HTTP_AUTHORIZATION': fakeauth})
        self.assertEqual(response.status_code, 403)
        
        logging.debug('Checking group permissions...')
        public = Group.objects.get(name='public')
        assign('view_container', public, bundle)
        self.assertTrue(self.users[0].has_perm('view_container', bundle))
        self.assertFalse(self.users[0].has_perm('change_container', bundle))
        self.assertFalse(self.users[0].has_perm('delete_container', bundle))
        self.assertFalse(self.users[0].has_perm('admin_container', bundle))
        self.assertFalse(self.users[0].has_perm('ownership_container', bundle))
        response = self.client.get(destination, **{'HTTP_AUTHORIZATION': fakeauth})
        self.assertEqual(response.status_code, 200)
        
        remove_perm('view_container', public, bundle)
        self.assertFalse(self.users[0].has_perm('view_container', bundle))
        self.assertFalse(self.users[0].has_perm('change_container', bundle))
        self.assertFalse(self.users[0].has_perm('delete_container', bundle))
        self.assertFalse(self.users[0].has_perm('admin_container', bundle))
        self.assertFalse(self.users[0].has_perm('ownership_container', bundle))
        
        logging.debug('Deleteing the bundle from the API...')
        response = self.client.delete(destination, **{'HTTP_AUTHORIZATION': auth})
        self.assertEqual(response.status_code, 204)
        self.assertRaises(Container.DoesNotExist, Container.objects.get, id=bundle.id)

if __name__ == "__main__":
    from django.test.utils import setup_test_environment
    setup_test_environment()
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()