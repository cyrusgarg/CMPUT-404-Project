import base64
import uuid
import json
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import exceptions
from identity.models import RemoteNode, FollowRequests, Following, Author, RemoteFollower, RemoteAuthor, RemoteFollowee, RemoteFriendship
from posts.models import Post
from identity.authentication import NodeBasicAuthentication
from identity.forms import RemoteNodeForm
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from identity.views import AuthorListView
from identity.api_views import inbox
from django.shortcuts import get_object_or_404

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

        # Create a dummy remote node (ensuring node is not null)
        self.remote_node = RemoteNode.objects.create(
            name="Remote Node",
            host_url="http://remotehost.com",
            username="remoteuser",
            password="remotepass",
            is_active=True
        )

        # Create a RemoteAuthor for user2 so that remote follow can be tested.
        self.remote_author = RemoteAuthor.objects.create(
            author_id=self.author2.author_id,
            display_name=self.author2.display_name,
            host="http://remotehost.com",
            node=self.remote_node  # supply the dummy remote node here
        )

    @patch('identity.views.requests.get')
    @patch('identity.views.requests.post')
    def test_follow_remote_author(self, mock_post, mock_get):
        """
        Story: As an author, I want to follow remote authors so that I can see their public posts.
        This test simulates sending a follow request from a local author to a remote author.
        """
        # Build the expected followee URL based on the remote author's data.
        followee_url = f"http://remotehost.com/api/authors/{self.remote_author.author_id}"
        
        # Simulate a successful GET request to retrieve remote author info.
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id": followee_url,
            "display_name": self.remote_author.display_name
        }
        
        # Simulate a successful POST request to the remote inbox.
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "OK"
        
        # Use the URL for the remote follow view
        follow_url = reverse('identity:remote-follow')

        # Send POST data using the keys expected by remoteFollow: "follower" and "followee_id"
        response = self.client.post(follow_url, {
            "follower": self.user1.username,
            "followee_id": self.remote_author.author_id
        })
        
        # Expect a redirect upon success.
        self.assertEqual(response.status_code, 302)
        
        # Confirm that a RemoteFollowee object was created with the correct remote followee ID.
        self.assertTrue(RemoteFollowee.objects.filter(
            follower=self.user1,
            followee_id=followee_url
        ).exists())

# This test case is for extended functionality beyond the basic node authentication tests.
class ExtendedFunctionalityTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.factory = RequestFactory()
        # Create a local user and associated author profile.
        self.user = User.objects.create_user(
            username="test", password="test", email="test@gmail.com"
        )
        self.author = self.user.author_profile
        # Create an initial public post.
        self.post = Post.objects.create(
            title="Original Title",
            description="Test description",
            content="Test content",
            contentType="text/plain",
            visibility="PUBLIC",
            author=self.user,
        )
        # Create an active remote node.
        self.node = RemoteNode.objects.create(
            name="Test Node",
            host_url="http://[2605:fd00:4:1001:f816:3eff:fed0:ce37]",
            username="test1",
            password="Smriti21!",
            is_active=True
        )

        # Build the inbox URL for our local author using their unique author_id.
        self.inbox_url = f"/api/authors/{self.author.author_id}/inbox/"
    
    def _post_to_inbox(self, payload):
        """
        Helper method: use RequestFactory to build a POST request and call the inbox view directly.
        """
        request = self.factory.post(self.inbox_url,
                                    data=json.dumps(payload),
                                    content_type='application/json')
        # Call the inbox view directly.
        response = inbox(request, author_id=self.author.author_id)
        return response

    def _remote_author_payload(self, extra_payload):
        """
        Helper: Returns a dictionary with remote author data added.
        """
        remote_author_data = {
            "id": f"http://[2605:fd00:4:1001:f816:3eff:fed0:ce37]/api/authors/{self.author.author_id}",
            "displayName": self.author.display_name,
            "host": "http://[2605:fd00:4:1001:f816:3eff:fed0:ce37]"
        }
        payload = extra_payload.copy()
        payload["author"] = remote_author_data
        return payload

    def test_resend_edited_post(self):
        """
        As an author, when I edit a post my node should resend the updated post data to remote nodes.
        Here we simulate that by POSTing an updated post payload to our inbox endpoint.
        """
        # Prepare a payload that mimics a remote node sending an updated post.
        payload = self._remote_author_payload({
            "type": "post",
            "id": f"http://[2605:fd00:4:1001:f816:3eff:fed0:ce37]/api/posts/{self.post.id}",  # full URL ending with post id
            "title": "Edited Title",
            "description": "Updated description",
            "content": "Updated content",
            "contentType": "text/plain",
            "visibility": "PUBLIC",
        })
        response = self._post_to_inbox(payload)
        # The inbox view should update the existing post and return status 200.
        self.assertEqual(response.status_code, 200)
        # Verify that the post has been updated.
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Edited Title")
        self.assertEqual(self.post.description, "Updated description")

    def test_send_post_to_remote_followers(self):
        """
        As an author, when I create a new post my node should send it to my remote followers.
        Here we simulate a remote node sending a new post to our inbox.
        """
        # Generate a valid UUID for the new post.
        new_post_uuid = str(uuid.uuid4())
        payload = self._remote_author_payload({
            "type": "post",
            "id": f"http://[2605:fd00:4:1001:f816:3eff:fed0:ce37]/api/posts/{new_post_uuid}",
            "title": "New Post Title",
            "description": "New post description",
            "content": "New post content",
            "contentType": "text/plain",
            "visibility": "PUBLIC",
        })
        response = self._post_to_inbox(payload)
        # Expecting creation (HTTP 201) because the post didn't exist.
        self.assertEqual(response.status_code, 201)
        # Verify that the new post exists in the database.
        new_post = Post.objects.filter(id=new_post_uuid).first()
        self.assertIsNotNone(new_post)
        self.assertEqual(new_post.title, "New Post Title")

    def test_resend_deleted_post(self):
        """
        As an author, when I delete a post my node should resend a notification (via the inbox)
        so that remote nodes no longer show the deleted post.
        Here we simulate that by sending an update with visibility set to "DELETED".
        """
        payload = self._remote_author_payload({
            "type": "post",
            "id": f"http://example.com/api/posts/{self.post.id}",
            "title": self.post.title,
            "description": self.post.description,
            "content": self.post.content,
            "contentType": self.post.contentType,
            "visibility": "DELETED",
        })
        response = self._post_to_inbox(payload)
        self.assertEqual(response.status_code, 200)
        # Verify that the post's visibility is updated to DELETED.
        self.post.refresh_from_db()
        self.assertEqual(self.post.visibility, "DELETED")

    def test_api_object_identification(self):
        """
        As a node admin, I want API objects (like authors and posts) to be identified by their full URL,
        to prevent collisions between different nodes' numbering schemes.
        This test checks that the API view for authors includes a profile_url for each object.
        """
        # We'll simulate calling the AuthorListView to get the list of authors.
        view = AuthorListView()
        request = self.factory.get('/dummy/')
        view.request = request
        view.kwargs = {}    # Set empty kwargs to avoid AttributeError
        
        # Calling get_queryset() will combine local and remote authors.
        # (Ensure at least one local and, if possible, one remote author exist.)
        object_list = view.get_queryset()
        view.object_list = object_list
        context = view.get_context_data()
        
        # Check that each author object in the context has a non-empty profile_url.
        for author_data in context.get("authors", []):
            self.assertIn("profile_url", author_data)
            self.assertTrue(author_data["profile_url"])

    def test_share_public_image(self):
        """
        As a node admin, when a public post includes an image it should be sent (via the inbox)
        so that remote nodes can display the image.
        In this test we simulate a remote node sending a post with an image URL.
        """
        # Instead of uploading a file, we simulate sending an image URL as part of the payload.
        new_post_uuid = str(uuid.uuid4())   # Generate a valid UUID for the new post.
        image_url = "http://example.com/media/test.jpg"
        payload = self._remote_author_payload({
            "type": "post",
            "id": f"http://example.com/api/posts/{new_post_uuid}",
            "title": "Post with Image",
            "description": "Image post description",
            "content": "Content with image",
            "contentType": "text/plain",
            "visibility": "PUBLIC",
            "image": image_url
        })
        response = self._post_to_inbox(payload)
        # Expecting creation (HTTP 201) since it's a new post.
        self.assertEqual(response.status_code, 201)
        new_post = Post.objects.filter(id=new_post_uuid).first()
        self.assertIsNotNone(new_post)
        # Verify that the image field is set
        self.assertEqual(new_post.image, image_url)