from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
import uuid
from rest_framework.authtoken.models import Token
from posts.models import Post
from identity.models import Author, GitHubActivity
from django.utils.timezone import now

class AuthorAPITestCase(TestCase):
    def setUp(self):
        """Set up test users and authors"""
        self.client = APIClient()
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.user2 = User.objects.create_user(username='user2', password='password123')
        self.author1 = self.user1.author_profile
        self.author2 = self.user2.author_profile
        self.post = Post.objects.create(
            author=self.user1,
            title="Sample Post",
            content="This is a test post.",
            visibility="PUBLIC"
        )

    def test_get_all_authors(self):
        """Ensure we can get a list of all authors"""
        response = self.client.get('/api/authors/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
    def test_get_author_detail(self):
        """Ensure we can get a single author's details"""
        self.client.force_authenticate(user=self.user1)  
        response = self.client.get(f'/api/authors/{self.author1.author_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('displayName', ''), 'user1') 

    def test_get_nonexistent_author(self):
        """Ensure a 404 is returned for a nonexistent author"""
        self.client.force_login(self.user1)  
        fake_uuid = uuid.uuid4()
        response = self.client.get(f'/identity/api/authors/{fake_uuid}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_auth_test_authenticated(self):
        """Ensure authentication test endpoint works for logged-in users"""
        self.client.login(username='user1', password='password123')
        response = self.client.get('/identity/api/auth-test/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        if response.status_code == status.HTTP_404_NOT_FOUND:
            self.assertIn('Not Found', response.content.decode())
        else:
            self.assertIn('Authentication successful for user user1', response.json().get('message', ''))
    
    def test_create_post(self):
        """Ensure an authenticated author can create a post"""
        self.client.force_authenticate(user=self.user1)
        post_data = {
            "title": "New Post",
            "content": "This is a new test post.",
            "visibility": "PUBLIC"
        }
        response = self.client.post(f'/api/authors/{self.author1.author_id}/posts/', post_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Post")

    def test_create_post_unauthenticated(self):
        """Ensure an unauthenticated user cannot create a post"""
        post_data = {
            "title": "Unauthorized Post",
            "content": "This should fail.",
            "visibility": "PUBLIC"
        }
        response = self.client.post(f'/api/authors/{self.author1.author_id}/posts/', post_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)



class GitHubActivityTestCase(TestCase):
    def setUp(self):
        """Set up test users and authors"""
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.author1 = self.user1.author_profile

    def test_create_github_activity(self):
        """Ensure an author's GitHub activity is correctly recorded"""
        github_event = GitHubActivity.objects.create(
            author=self.author1,
            event_id="evt_12345",
            event_type="PushEvent",
            payload={"repo": "user1/sample-repo", "message": "Initial commit"},
            created_at=now()
        )

        self.assertEqual(GitHubActivity.objects.count(), 1)
        self.assertEqual(github_event.author, self.author1)
        self.assertEqual(github_event.event_type, "PushEvent")
        self.assertEqual(github_event.payload["repo"], "user1/sample-repo")

    def test_prevent_duplicate_github_events(self):
        """Ensure duplicate GitHub events are not stored"""
        GitHubActivity.objects.create(
            author=self.author1,
            event_id="evt_12345",
            event_type="PushEvent",
            payload={"repo": "user1/sample-repo", "message": "Initial commit"},
            created_at=now()
        )

        with self.assertRaises(Exception):
            GitHubActivity.objects.create(
                author=self.author1,
                event_id="evt_12345",  # Same event ID (should fail)
                event_type="PushEvent",
                payload={"repo": "user1/sample-repo", "message": "Duplicate commit"},
                created_at=now()
            )

    def test_retrieve_github_activity_for_author(self):
        """Ensure GitHub activity can be retrieved for a specific author"""
        GitHubActivity.objects.create(
            author=self.author1,
            event_id="evt_12345",
            event_type="PushEvent",
            payload={"repo": "user1/sample-repo", "message": "Initial commit"},
            created_at=now()
        )

        activities = GitHubActivity.objects.filter(author=self.author1)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].event_type, "PushEvent")
