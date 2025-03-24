import base64
import json
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import exceptions
from identity.models import RemoteNode, FollowRequests, Following, Author, RemoteFollower
from posts.models import Post
from identity.authentication import NodeBasicAuthentication
from identity.forms import RemoteNodeForm
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

User = get_user_model()

class NodeAdminTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.factory = RequestFactory()
        # Create a system admin user (used for node auth)
        self.admin_user = User.objects.create_superuser(
            username='test', email='test@gmail.com', password='test'
        )
        # Create an active remote node
        self.node = RemoteNode.objects.create(
            name='Test Node',
            host_url='http://[2605:fd00:4:1001:f816:3eff:fed0:ce37]',
            username='test1',
            password='Smriti21!',
            is_active=True
        )
        # Prepare a valid auth header
        self.valid_auth_header = self.get_basic_auth_header(self.node.username, self.node.password)

    def get_basic_auth_header(self, username, password):
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return f"Basic {encoded}"

    def test_node_auth_test_view_authenticated(self):
        """
        Test the NodeAuthTestView returns the expected message upon successful authentication.
        """
        # Create the proper Basic auth header using the node's username and password.
        credentials = f"{self.node.username}:{self.node.password}"
        auth_header = "Basic " + base64.b64encode(credentials.encode()).decode('utf-8')
        
        # Assuming you have a URL name for NodeAuthTestView, e.g., 'node-auth-test-view'
        url = '/api/node-auth-test/'  # hardcoded URL
        response = self.client.get(url, HTTP_AUTHORIZATION=auth_header)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("message"), "Authentication successful")
        self.assertEqual(data.get("node"), self.node.name)
    
    def test_node_api_view_authenticated(self):
        """
        Test the NodeAPIView returns the expected message and node URL for authenticated nodes.
        """
        url = '/api/node-api/'  # hardcoded URL
        # Build the Basic auth header from the node's credentials
        credentials = f"{self.node.username}:{self.node.password}"
        auth_header = "Basic " + base64.b64encode(credentials.encode()).decode('utf-8')
        
        response = self.client.get(url, HTTP_AUTHORIZATION=auth_header)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Verify the response content
        self.assertIn("Hello", data.get("message"))
        self.assertEqual(data.get("node_url"), self.node.host_url)

    def test_node_api_view_with_invalid_credentials(self):
        """
        Ensure that accessing the API views with invalid credentials results in an authentication failure.
        """
        url = '/api/node-api/'
        invalid_auth_header = self.get_basic_auth_header('wronguser', 'wrongpass')
        response = self.client.get(url, HTTP_AUTHORIZATION=invalid_auth_header)
        self.assertIn(response.status_code, [401, 403])

    def test_prevent_invalid_node_connection(self):
        """
        Story: As a node admin, I can prevent nodes from connecting if they don't have a valid username and password.
        This test ensures that an invalid auth header causes authentication to fail.
        """
        # Create a request with invalid credentials.
        auth_header = self.get_basic_auth_header('wronguser', 'wrongpass')
        request = self.factory.get('/dummy-endpoint/')
        request.META['HTTP_AUTHORIZATION'] = auth_header

        auth_instance = NodeBasicAuthentication()
        with self.assertRaises(Exception):
            # Should raise an AuthenticationFailed exception for invalid credentials.
            auth_instance.authenticate(request)

    def test_valid_node_basic_authentication(self):
        """
        Story: As a node admin, node to node connections can be authenticated with HTTP Basic Auth.
        This test ensures that valid credentials return a tuple of (system_user, node).
        """
        auth_header = self.get_basic_auth_header(self.node.username, self.node.password)
        request = self.factory.get('/dummy-endpoint/')
        request.META['HTTP_AUTHORIZATION'] = auth_header

        auth_instance = NodeBasicAuthentication()
        user, node = auth_instance.authenticate(request)
        self.assertEqual(node, self.node)
        self.assertTrue(user.is_superuser)

    def test_disable_node_interface(self):
        """
        Story: As a node admin, I can disable the node to node interfaces for connections I no longer want.
        This test deactivates the node and then ensures that authentication fails.
        """
        # Deactivate the node.
        self.node.is_active = False
        self.node.save()

        auth_header = self.get_basic_auth_header(self.node.username, self.node.password)
        request = self.factory.get('/dummy-endpoint/')
        request.META['HTTP_AUTHORIZATION'] = auth_header

        auth_instance = NodeBasicAuthentication()
        with self.assertRaises(Exception):
            auth_instance.authenticate(request)

    def test_remove_node(self):
        """
        Story: As a node admin, I want to be able to remove nodes and stop sharing with them.
        This test deletes a node and checks that it is removed from the database.
        """
        node_id = self.node.id
        self.node.delete()
        with self.assertRaises(RemoteNode.DoesNotExist):
            RemoteNode.objects.get(id=node_id)

    def test_add_node(self):
        """
        Story: As a node admin, I want to be able to add nodes to share with.
        This test creates a new RemoteNode instance and verifies its data.
        """
        new_node_data = {
            'name': 'New Node',
            'host_url': 'http://[2605:fd00:4:1001:f816:3eff:fe39:c1b6]',
            'username': 'youu',
            'password': 'youu12345',
            'is_active': True
        }
        new_node = RemoteNode.objects.create(**new_node_data)
        self.assertIsNotNone(new_node.id)
        self.assertEqual(new_node.name, 'New Node')

    def test_connect_remote_node_via_form(self):
        """
        Story: As a node admin, I want to be able to connect to remote nodes by entering only the URL, username, and password.
        This test uses the RemoteNodeForm to simulate the admin adding a new node.
        """
        form_data = {
            'name': 'Form Node',
            'host_url': 'https://[2605:fd00:4:1001:f816:3eff:fe1a:a199]',
            'username': 'noder',
            'password': 'Ashlyn#1234',
            'is_active': True
        }
        form = RemoteNodeForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        node = form.save()
        self.assertEqual(node.name, 'Form Node')


class AuthorAndFollowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Create two authors (users)
        self.user1 = User.objects.create_user(username='author1', password='pass1', email='a1@example.com')
        self.user2 = User.objects.create_user(username='author2', password='pass2', email='a2@example.com')
        self.author1 = self.user1.author_profile
        self.author2 = self.user2.author_profile

    def test_follow_remote_author(self):
        """
        Story: As an author, I want to follow remote authors so that I can see their public posts.
        This test simulates sending a follow request from user1 to user2.
        """
        follow_url = reverse('identity:follow') 
        response = self.client.post(follow_url, {'sender': self.user1.username, 'receiver': self.user2.username})
        # Expecting a redirect on success.
        self.assertEqual(response.status_code, 302)
        # Confirm that a follow request was created.
        self.assertTrue(FollowRequests.objects.filter(sender=self.user1, receiver=self.user2).exists())

    # def test_share_public_image(self):
    #     """
    #     Story: As a node admin, I want to share public images with users on other nodes so that they are visible externally.
    #     This test simulates sharing a public post that contains an image.
    #     NOTE: This test assumes that a Post model exists and that the share_post_with_nodes view works as expected.
    #     """
    #     # Create a dummy image file using SimpleUploadedFile
    #     dummy_image = SimpleUploadedFile(
    #         "test.jpg",
    #         b"dummyimagecontent",  # Replace with valid image binary data if needed
    #         content_type="image/jpeg"
    #     )

    #     # Create a dummy public post with the image in the image field and plain content.
    #     post = Post.objects.create(
    #         title='Test Public Post',
    #         description='A public post with an image',
    #         content='Test content without markdown image',
    #         contentType='text/plain',
    #         visibility='PUBLIC',
    #         author=self.user1,
    #         image=dummy_image
    #     )

    #     # Create a dummy remote follower to simulate an external recipient.
    #     # This follower_id should be a URL that includes the recipient's author id.
    #     dummy_follower_url = "http://remotehost.com/authors/1234"
    #     RemoteFollower.objects.create(
    #         follower_id=dummy_follower_url,
    #         followee_id=1 # dummy followee_id
    #     )

    #     # Create a dummy request using RequestFactory.
    #     request = self.factory.get('/dummy/')

    #     # Patch the requests.request call to avoid making an actual HTTP request.
    #     with patch('posts.views.requests.request') as mock_req:
    #         # Configure the mock to return a dummy response with status_code 200.
    #         dummy_response = type("DummyResponse", (), {"status_code": 200, "text": "OK"})
    #         mock_req.return_value = dummy_response

    #         # Import and call the function that sends the post to remote recipients.
    #         from posts.views import send_post_to_remote_recipients
    #         send_post_to_remote_recipients(post, request)

    #         # Assert that requests.request was called (meaning at least one remote recipient was processed).
    #         self.assertTrue(mock_req.called)
    #         # Retrieve the URL from the call arguments to validate it includes the expected recipient's inbox endpoint.
    #         called_args, called_kwargs = mock_req.call_args
    #         # The second positional argument is the inbox_url.
    #         inbox_url = called_args[1]
    #         self.assertIn("http://remotehost.com/api/authors/1234/inbox", inbox_url)