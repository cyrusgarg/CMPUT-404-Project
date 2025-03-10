from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from posts.models import Post, Like, Comment
from identity.models import Following
from rest_framework import status
from rest_framework.test import APIClient
import uuid
from django.conf import settings

import json
from io import BytesIO


class PostVisibilityTestCase(TestCase):
    """
    API Test Cases for Visibility Stories.
    用于测试帖子可见性相关的 API 端点。（GJ）
    """

    def setUp(self):
        """
        Set up test users and posts.
        初始化测试用户和帖子。（GJ）
        """

        self.old_approval_setting = getattr(settings, 'REQUIRE_AUTHOR_APPROVAL', True)
        settings.REQUIRE_AUTHOR_APPROVAL = False

        self.author = User.objects.create_user(username="author", password="test123")
        self.follower = User.objects.create_user(username="follower", password="test123")
        self.friend = User.objects.create_user(username="friend", password="test123")
        self.non_follower = User.objects.create_user(username="random", password="test123")
        self.admin = User.objects.create_superuser(username="admin", password="admin123")

        # Ensure authors are approved
        self.author.author_profile.is_approved = True
        self.author.author_profile.save()
        self.follower.author_profile.is_approved = True
        self.follower.author_profile.save()
        self.friend.author_profile.is_approved = True
        self.friend.author_profile.save()
        self.non_follower.author_profile.is_approved = True
        self.non_follower.author_profile.save()
        self.admin.author_profile.is_approved = True
        self.admin.author_profile.save()
        # `follower` 关注 `author`
        Following.objects.create(follower=self.follower, followee=self.author)

        # `friend` 互相关注 `author`
        Following.objects.create(follower=self.friend, followee=self.author)
        Following.objects.create(follower=self.author, followee=self.friend)

        # 创建不同可见性的帖子
        self.public_post = Post.objects.create(
            id=uuid.uuid4(),
            author=self.author,
            title="Public Post",
            description="This is a public post.",
            content="Public content",
            visibility="PUBLIC"
        )

        self.unlisted_post = Post.objects.create(
            id=uuid.uuid4(),
            author=self.author,
            title="Unlisted Post",
            description="This is an unlisted post.",
            content="Unlisted content",
            visibility="UNLISTED"
        )

        self.friends_post = Post.objects.create(
            id=uuid.uuid4(),
            author=self.author,
            title="Friends Only Post",
            description="This is a friends-only post.",
            content="Friends-only content",
            visibility="FRIENDS"
        )

        self.deleted_post = Post.objects.create(
            id=uuid.uuid4(),
            author=self.author,
            title="Deleted Post",
            description="This post is deleted.",
            content="Deleted content",
            visibility="DELETED"
        )

        # Initialize the API client and log in as the author by default.
        self.client = APIClient()
        self.client.force_authenticate(user=self.author)
        self.client.force_authenticate(user=self.follower)
        self.client.force_authenticate(user=self.friend)
        self.client.force_authenticate(user=self.non_follower)
        self.client.force_authenticate(user=self.admin)
        

    def test_public_post_visibility(self):
        """
        Test that all users can see public posts.
        测试所有用户都能看到 PUBLIC 级别的帖子。（GJ）
        """
        self.client.login(username="follower", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Public Post")  # Public posts should be visible / 公开帖子应该可见（GJ）

        self.client.logout()
        self.client.login(username="author", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Public Post")  # author users can also see PUBLIC posts

        self.client.logout()
        self.client.login(username="friend", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Public Post")  # friend users can also see PUBLIC posts

        self.client.logout()
        self.client.login(username="random", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Public Post")  # Random users can also see PUBLIC posts / 随机用户也能看到 PUBLIC 贴（GJ）

        self.client.logout()
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Public Post")  # Administrators should be able to see PUBLIC posts / 管理员应该可以看到 PUBLIC 贴（GJ）


    def test_unlisted_post_visibility(self):
        """
        Test that only followers of the author can see UNLISTED posts.
        测试只有关注作者的用户能看到 UNLISTED 帖子。（GJ）
        """
        self.client.login(username="follower", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Unlisted Post")  # Followers can see UNLISTED posts / 关注者可以看到 UNLISTED 贴（GJ）

        self.client.logout()
        self.client.login(username="random", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertNotContains(response, "Unlisted Post")  # Random users should not see UNLISTED posts  / 随机用户不应该看到 UNLISTED 贴（GJ）

        self.client.logout()
        self.client.login(username="friend", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Unlisted Post") # friend should be able to see UNLISTED posts 

        self.client.logout()
        self.client.login(username="author", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Unlisted Post") # friend should be able to see UNLISTED posts 

        self.client.logout()
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Unlisted Post") # Administrators should be able to see UNLISTED posts / 管理员应该可以看到 UNLISTED 贴（GJ）


    def test_unlisted_post_by_link(self):
        """
        Test that an unlisted post is visible if accessed by direct link.
        测试 UNLISTED 贴如果直接访问链接，则可以查看。（GJ）
        """
        self.client.login(username="random", password="test123")
        response = self.client.get(reverse("posts:post_detail", args=[self.unlisted_post.id]))
        self.assertEqual(response.status_code, 200)  # Direct access URL should be visible / 直接访问链接应该可见（GJ）

        self.client.logout()
        self.client.login(username="follower", password="test123")
        response = self.client.get(reverse("posts:post_detail", args=[self.unlisted_post.id]))
        self.assertEqual(response.status_code, 200)  # Direct access URL should be visible # follower

        self.client.logout()
        self.client.login(username="friend", password="test123")
        response = self.client.get(reverse("posts:post_detail", args=[self.unlisted_post.id]))
        self.assertEqual(response.status_code, 200)  # Direct access URL should be visible # friend

        self.client.logout()
        self.client.login(username="author", password="test123")
        response = self.client.get(reverse("posts:post_detail", args=[self.unlisted_post.id]))
        self.assertEqual(response.status_code, 200)  # Direct access URL should be visible # author

        self.client.logout()
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("posts:post_detail", args=[self.unlisted_post.id]))
        self.assertEqual(response.status_code, 200)  # Direct access URL should be visible # admin

    def test_friends_post_visibility(self):
        """
        Test that FRIENDS posts are only visible to mutual followers.
        测试 FRIENDS 级别的帖子仅对互相关注的好友可见。（GJ）
        """
        self.client.login(username="friend", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Friends Only Post")  # Visible to people who follow each other / 互相关注者可见（GJ）

        self.client.logout()
        self.client.login(username="follower", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertNotContains(response, "Friends Only Post")  # One-way followers are not visible / 单向关注者不可见（GJ）

        self.client.logout()
        self.client.login(username="random", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertNotContains(response, "Friends Only Post")  # Not visible to non-followers / 非关注者不可见（GJ）

        self.client.logout()
        self.client.login(username="author", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Friends Only Post")  # AUTHOR CAN SEE ALL POSTS

        self.client.logout()
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Friends Only Post")  # Admins should be able to see FRIENDS posts / 管理员应该可以看到 FRIENDS 贴（GJ）


    def test_deleted_post_visibility(self):
        """
        Test that only admin can see DELETED posts.
        测试只有管理员可以看到 DELETED 帖子。（GJ）
        """
        self.client.login(username="follower", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertNotContains(response, "Deleted Post")  # Ordinary users cannot see DELETED posts / 普通用户看不到 DELETED 贴（GJ）

        self.client.logout()
        self.client.login(username="friend", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertNotContains(response, "Deleted Post")  # Ordinary users cannot see DELETED posts 

        self.client.logout()
        self.client.login(username="random", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertNotContains(response, "Deleted Post")  # Ordinary users cannot see DELETED posts 

        self.client.logout()
        self.client.login(username="author", password="test123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertNotContains(response, "Deleted Post")  # author cannot see DELETED posts 

        self.client.logout()
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("posts:view_posts"))
        self.assertContains(response, "Deleted Post")  # Admins should be able to see DELETED posts / 管理员应该可以看到 DELETED 贴（GJ）

