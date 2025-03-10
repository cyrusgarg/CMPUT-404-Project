import json
from io import BytesIO

from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from posts.models import Post, Like, Comment


class PostAPITestCase(TestCase):
    def setUp(self):
        # Create two users: an author and another user
        self.author = User.objects.create_user(username="author", password="password")
        self.other = User.objects.create_user(username="other", password="password")
        
        # Create a sample public post by the author
        self.post = Post.objects.create(
            author=self.author,
            title="Sample Post",
            description="A sample description",
            content="Some content here",
            contentType="text/plain",
            visibility="PUBLIC"
        )
        
        # Initialize the API client and log in as the author by default.
        self.client = APIClient()
        self.client.force_authenticate(user=self.author)
        self.client.force_authenticate(user=self.other)
        self.client.login(username="author", password="password")
    
    def test_get_post_by_fqid(self):
        """
        Test retrieving a post by its fully qualified ID.
        """
        url = reverse("posts:get_post_by_fqid", kwargs={"post_id": self.post.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Sample Post")
    
    def test_web_update_post_by_author(self):
        """
        Test that the author can update their own post via the web endpoint.
        """
        url = reverse("posts:web_update_post", kwargs={"post_id": self.post.id})
        data = {
            "title": "Updated Post",
            "description": "Updated Description",
            "content": "Updated Content",
            "contentType": "text/markdown",
            "visibility": "PUBLIC"
        }
        response = self.client.post(url, data)
        
        # After a successful update, the post should be changed.
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Updated Post")
        self.assertEqual(self.post.contentType, "text/markdown")
    
    def test_web_update_post_not_author(self):
        """
        Test that a user who is not the post’s author cannot update the post.
        """
        # Log in as a different user
        self.client.logout()
        self.client.login(username="other", password="password")
        
        url = reverse("posts:web_update_post", kwargs={"post_id": self.post.id})
        data = {"title": "Hacked Title"}
        response = self.client.post(url, data)
        
        # Expect a forbidden response
        self.assertEqual(response.status_code, 403)
    
    def test_update_post_api(self):
        """
        Test updating a post via the JSON API endpoint.
        """
        url = reverse("posts:update_post", kwargs={"post_id": self.post.id})
        data = {
            "title": "API Updated Title",
            "description": "API Updated Description",
            "content": "API Updated Content",
            "contentType": "text/plain",
            "visibility": "PUBLIC"
        }
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")
        
        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "API Updated Title")
    
    def test_edit_post_locally(self):
        """
        Test that the author can edit a post locally to correct a typo.
        """
        url = reverse("posts:web_update_post", kwargs={"post_id": self.post.id})
        data = {
            "title": "Sample Post",
            "description": "A sample description",
            "content": "Some content with a typo corrected",
            "contentType": "text/plain",
            "visibility": "PUBLIC"
        }
        response = self.client.post(url, data)
        
        # After a successful update, the post should be changed.
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "Some content with a typo corrected")
    
    def test_stream_sorted_by_most_recent(self):
        """
        Test that the "stream" page is sorted with the most recent posts first.
        """
        # Create another post with a later publication date
        new_post = Post.objects.create(
            author=self.author,
            title="New Post",
            description="A new description",
            content="Some more content",
            contentType="text/plain",
            visibility="PUBLIC"
        )
        
        # Visit the stream page
        url = reverse("posts:view_posts")
        response = self.client.get(url)
        
        # The most recent post should appear first in the response data
        posts = response.context["posts"]
        self.assertEqual(posts[0].title, "New Post")  # New post should be first
        self.assertEqual(posts[1].title, "Sample Post")  # Old post should be second

    
    def test_delete_post_by_author(self):
        """
        Test that an author can delete (mark as DELETED) their own post.
        """
        url = reverse("posts:delete_post", kwargs={"post_id": self.post.id})
        response = self.client.post(url)
        
        self.post.refresh_from_db()
        self.assertEqual(self.post.visibility, "DELETED")
    
    def test_create_post_with_image(self):
        """
        Test creating a post with an image. The image is converted to a base64 string.
        """
        # Create a fake image file
        image_data = BytesIO(b"fake image data")
        image_file = SimpleUploadedFile("test.jpg", image_data.read(), content_type="image/jpeg")
        
        url = reverse("posts:create_post")
        data = {
            "title": "Post with Image",
            "description": "This post has an image",
            "content": "Content with image",
            "contentType": "text/plain",
            "visibility": "PUBLIC",
            "image": image_file
        }
        response = self.client.post(url, data, format="multipart")
        
        # A successful creation should result in a redirect (HTTP 302)
        self.assertEqual(response.status_code, 302)
        new_post = Post.objects.get(title="Post with Image")
        # Check that the image field starts with the expected base64 header.
        self.assertTrue(new_post.image.startswith("data:image/jpeg;base64,"))
    
    def test_like_post_toggle(self):
        """
        Test liking a post and then unliking it.
        """
        url = reverse("posts:like_post", kwargs={"post_id": self.post.id})
        
        # First, like the post
        response = self.client.post(url)
        like_count = Like.objects.filter(post=self.post).count()
        self.assertEqual(like_count, 1)
        
        # Liking again should remove the like (toggle off)
        response = self.client.post(url)
        like_count = Like.objects.filter(post=self.post).count()
        self.assertEqual(like_count, 0)
    
    def test_add_and_get_comment(self):
        """
        Test adding a comment to a post and then retrieving it via the API.
        """
        # Add a comment using the add_comment endpoint.
        url = reverse("posts:add_comment", kwargs={"post_id": self.post.id})
        comment_text = "Nice post!"
        response = self.client.post(url, {"content": comment_text})
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("Comment added successfully", response.content.decode())
        
        # Now retrieve comments using the get_comments endpoint.
        url = reverse("posts:get_comments", kwargs={"post_id": self.post.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        comments = response.data
        self.assertTrue(any(comment["comment"] == comment_text for comment in comments))

    def test_like_comment_toggle(self):
        """
        Test liking a comment and then unliking it.
        """
        # Create a comment on the post.
        comment = Comment.objects.create(
            post=self.post, 
            user=self.author, 
            content="Test comment"
        )
        
        # Construct the URL for the like_comment view.
        url = reverse("posts:like_comment", kwargs={"post_id": self.post.id, "comment_id": comment.id})
        
        # First, like the comment.
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode())
        self.assertTrue(data.get("liked"))
        self.assertEqual(data.get("like_count"), 1)
        
        # Then, unlike the comment (toggle off).
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode())
        self.assertFalse(data.get("liked"))
        self.assertEqual(data.get("like_count"), 0)

    def test_shared_post_api(self):
        """
        Test the shared_post_api endpoint for both authenticated and unauthenticated users.
        Tests:
        1. Unauthenticated user can access a public post
        2. Authenticated user can access a public post with is_liked_by_user field
        3. Neither user can access a non-public post
        """
        # Create a public post for testing
        public_post = Post.objects.create(
            author=self.author,
            title="Public Shareable Post",
            description="A public post that can be shared",
            content="Public content",
            contentType="text/plain",
            visibility="PUBLIC"
        )
        
        # Create a non-public post for testing
        private_post = Post.objects.create(
            author=self.author,
            title="Private Post",
            description="A private post",
            content="Private content",
            contentType="text/plain",
            visibility="FRIENDS"
        )
        
        # Create a comment on the public post
        comment = Comment.objects.create(
            post=public_post,
            user=self.other,
            content="A comment on the public post"
        )
        
        # Test 1: Unauthenticated user can access public post
        self.client.logout()
        url = f"/api/posts/{public_post.id}/shared/"
    
        response = self.client.get(url)
        data = response.json()
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data["post"]["title"], "Public Shareable Post")
        self.assertEqual(len(data["comments"]), 1)
        
        if "is_logged_in" in data:
            self.assertFalse(data["is_logged_in"])
        
        self.assertNotIn("is_liked_by_user", data["post"])
        
        # Test 2: Authenticated user can access public post
        self.client.force_login(self.author)
        response = self.client.get(url)
        data = response.json()
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data["post"]["title"], "Public Shareable Post")
        
        
        # If the post has is_liked_by_user field for authenticated users
        if "is_liked_by_user" in data["post"]:
            self.assertFalse(data["post"]["is_liked_by_user"]) 
        
        Like.objects.create(user=self.author, post=public_post)
        response = self.client.get(url)
        data = response.json()
        
        if "is_liked_by_user" in data["post"]:
            self.assertTrue(data["post"]["is_liked_by_user"]) 
        
        # Test 3: Cannot access a non-public post
        url = f"/api/posts/{private_post.id}/shared/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["detail"], "This post is not shareable")
        
        # Test that unauthenticated user also cannot access non-public post
        self.client.logout()
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)