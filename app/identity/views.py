import json
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from django.contrib.auth.models import User
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import user_passes_test
from posts.models import Post  
from identity.models import Author
from .models import Author, GitHubActivity, Following, FollowRequests, Friendship, RemoteNode, RemoteFollowRequests, RemoteFollower, RemoteAuthor, RemoteFollowee, RemoteFriendship
from .forms import AuthorProfileForm, UserSignUpForm, RemoteNodeForm
from .utils import send_to_node
from django.http import JsonResponse
import requests

class AuthorProfileView(DetailView):
    model = Author
    template_name = 'identity/author_profile.html'
    context_object_name = 'author'
    
    def get_object(self):
        return get_object_or_404(Author, user__username=self.kwargs['username'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author = self.get_object()
        print(author.author_id)
        # Add public posts to profile
        context['posts'] = Post.objects.filter(
            author=author.user,
            visibility='PUBLIC'
        ).order_by('-published')
        # include the latest 10 GitHub activities for this author:
        context['public_posts'] = self.get_object().github_activities.order_by('-created_at')
        context['is_current_user'] = author.user == self.request.user
        context['is_follow_requested'] = FollowRequests.objects.filter(sender=self.request.user, receiver=author.user).exists()
        context['is_following'] = Following.objects.filter(follower=self.request.user, followee=author.user).exists()
        return context

class AuthorListView(ListView):
    template_name = 'identity/author_list.html'
    context_object_name = 'authors'
    paginate_by = 15  # Increased to accommodate both local and remote authors
    
    def get_queryset(self):
        # Get local authors
        local_authors = Author.objects.all()
        
        # Get remote authors from all active nodes
        remote_authors = RemoteAuthor.objects.filter(node__is_active=True)
        
        # Combine local and remote authors into a single queryset
        combined_authors = []
        
        # Add local authors
        for author in local_authors:
            combined_authors.append({
                'id': str(author.author_id),  # Ensure string representation
                'display_name': author.display_name,
                'bio': author.bio,
                'profile_image': author.profile_image.url if author.profile_image else None,
                'github': author.github,
                'host': author.host,
                'is_local': True,
                'username': author.user.username,
                # Generate profile URL for local authors
                'profile_url': reverse_lazy('identity:author-profile', 
                                kwargs={'username': author.user.username})
            })
        
        # Add remote authors
        for author in remote_authors:
            # Try to extract numeric ID if possible
            try:
                # Attempt to extract a numeric ID from the author_id
                numeric_id = int(''.join(filter(str.isdigit, str(author.id))))
            except:
                numeric_id = author.id
            
            combined_authors.append({
                'id': numeric_id,  # Use a numeric ID if possible
                'display_name': author.display_name,
                'bio': '',  # Remote authors might not have bios
                'profile_image': author.profile_image if author.profile_image else None,
                'github': author.github,
                'host': author.host,
                'is_local': False,
                'node_id': author.node.id,
                'node_name': author.node.name,
                # Generate profile URL for remote authors
                'profile_url': reverse_lazy('identity:remote-author-detail', 
                                kwargs={'node_id': author.node.id, 'pk': numeric_id})
            })
        
        # Sort by display name
        combined_authors.sort(key=lambda x: x['display_name'])
        
        return combined_authors
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add profile URL for each author
        for author in context['authors']:
            # For local authors
            if author.get('is_local', False):
                profile_url = reverse_lazy('identity:author-profile', 
                                        kwargs={'username': author.get('username')})
            else:
                # For remote authors
                profile_url = reverse_lazy('identity:remote-author-detail', 
                                        kwargs={'node_id': author.get('node_id'), 'pk': author.get('id')})
            
            author['profile_url'] = profile_url
        
        return context

class Requests(ListView):
    model = FollowRequests
    template_name = 'identity/follow_requests.html'
    context_object_name = 'requests'

    def get_queryset(self):
        return FollowRequests.objects.filter(receiver__username=self.kwargs['username']).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['remote_requests'] = RemoteFollowRequests.objects.filter(receiver__username=self.kwargs['username']).order_by('-created_at')
        return context

# --- GitHub Webhook View ---
@csrf_exempt
def github_webhook(request):
    """
    This view receives POST requests from GitHub webhooks.
    GitHub sends the event type in the HTTP_X_GITHUB_EVENT header.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method.")

    try:
        payload = json.loads(request.body)
        # Get the event type from header:
        event_type = request.META.get('HTTP_X_GITHUB_EVENT', 'unknown')
        event_id = payload.get('id')
        created_at_str = payload.get('created_at')
        created_at = parse_datetime(created_at_str) if created_at_str else None

        # Here, we assume the payload contains the repository owner’s GitHub username.
        github_username = payload.get('repository', {}).get('owner', {}).get('login')
        if not github_username:
            return HttpResponseBadRequest("GitHub username not found in payload.")

        try:
            author = Author.objects.get(github_username=github_username)
        except Author.DoesNotExist:
            return HttpResponse("No matching author found.", status=404)

        # Prevent duplicate processing:
        if GitHubActivity.objects.filter(event_id=event_id).exists():
            return HttpResponse("Event already processed.", status=200)

        # Create a new GitHubActivity record:
        GitHubActivity.objects.create(
            author=author,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            created_at=created_at
        )
        return HttpResponse("GitHub event processed.", status=200)

    except Exception as e:
        return HttpResponseBadRequest("Error processing webhook: " + str(e))

def follow(request):
    # query user DB to get the sender and receiver
    sender = get_object_or_404(User, username=request.POST["sender"])
    receiver = get_object_or_404(User, username=request.POST["receiver"])

    # ensure database is consistent
    if(not FollowRequests.objects.filter(sender=sender, receiver=receiver).exists() and not Following.objects.filter(follower=sender, followee=receiver).exists()):
        FollowRequests.objects.create(sender=sender, receiver=receiver)
        return redirect(reverse('identity:author-profile', kwargs={'username': receiver.username}))
    return HttpResponse("Error in sending a follow request")

def unfollow(request):
    # query user DB to get the follower and followee
    follower = get_object_or_404(User, username=request.POST.get('follower'))
    followee = get_object_or_404(User, username=request.POST.get('followee'))
    follow = Following.objects.filter(follower=follower, followee=followee)

    # ensure database is consistent
    if(follow.exists()):
        follow.delete()

        # check if there is a corresponding friendship that needs to be deleted
        user1, user2 = sorted([follower, followee], key=lambda user: user.id)
        friendship = Friendship.objects.filter(user1=user1, user2=user2)
        if(friendship.exists()):
            friendship.delete()

        return redirect(reverse('identity:author-profile', kwargs={'username': followee.username}))
    return HttpResponse("Error during unfollowing")

def remoteFollow(request):
    follower = get_object_or_404(Author, user__username=request.POST["follower"])
    local_followee = get_object_or_404(RemoteAuthor, author_id=request.POST["followee_id"])
    
    followee_response = requests.get(local_followee.host + "/api/authors/" + local_followee.author_id)

    if followee_response.status_code != 200:
        return HttpResponse("Error retrieving remote user:", response.text)
    
    followee = followee_response.json()

    url = followee.get("id") + "/inbox"
    headers = {"Content-Type": "application/json"}
    body = {
        "type": "follow",
        "summary": f"{follower.display_name} wants to follow {followee.get("display_name")}",
        "actor": follower.to_dict(),
        "object": followee
    }

    response = requests.post(url, headers=headers, json=body)

    if not RemoteFollowee.objects.filter(follower=follower.user, followee_id=followee.get("id")).exists():
        RemoteFollowee.objects.create(follower=follower.user, followee_id=followee.get("id"))

    if RemoteFollower.objects.filter(follower_id=followee.get("id"), followee=follower.user).exists() and not RemoteFriendship.objects.filter(local=follower.user, remote=followee.get("id")).exists():
        RemoteFriendship.objects.create(local=follower.user, remote=followee.get("id"))

    return redirect(reverse('identity:remote-author-detail', kwargs={'node_id':local_followee.node.id, 'pk':local_followee.id}))
    
def remoteUnfollow(request):
    follower = get_object_or_404(User, username=request.POST["follower"]) 
    followee = get_object_or_404(RemoteAuthor, author_id=request.POST["followee_id"])
    followee_id = followee.host + "/api/authors/" + followee.author_id

    follow = RemoteFollowee.objects.filter(follower=follower, followee_id=followee_id)
    if follow.exists():
        follow.delete()

        friendship = RemoteFriendship.objects.filter(local=follower, remote=followee_id)
        if(friendship.exists()):
            friendship.delete()
        return redirect(reverse('identity:remote-author-detail', kwargs={'node_id':followee.node.id, 'pk':followee.id}))
    return HttpResponse("Error during unfollowing")

def accept(request):
    # query user DB to get the sender and receiver
    sender = get_object_or_404(User, username=request.POST["sender"])
    receiver = get_object_or_404(User, username=request.POST["receiver"])
    
    # ensure database is consistent
    request = FollowRequests.objects.filter(sender=sender, receiver=receiver)
    if(request.exists() and not Following.objects.filter(follower=sender, followee=receiver).exists()):
        request.delete()
        Following.objects.create(follower=sender, followee=receiver)

        # check if there is a corresponding friendship to be created
        user1, user2 = sorted([sender, receiver], key=lambda user: user.id)
        if(Following.objects.filter(follower=receiver, followee=sender).exists() and not Friendship.objects.filter(user1=user1, user2=user2)):
            Friendship.objects.create(user1=user1, user2=user2)

        return redirect(reverse('identity:requests', kwargs={'username': receiver.username}))
    return HttpResponse("Error in accepting the follow request")

def decline(request):
    # query user DB to get the sender and receiver
    sender = get_object_or_404(User, username=request.POST["sender"])
    receiver = get_object_or_404(User, username=request.POST["receiver"])
    request = FollowRequests.objects.filter(sender=sender, receiver=receiver)

    # ensure database is consistent
    if(request.exists()):
        request.delete()
        return redirect(reverse('identity:requests', kwargs={'username': receiver.username}))
    return HttpResponse("Error in declining the follow request")

def remoteAccept(request):
    # query user DB to get the sender and receiver
    sender_id = request.POST["sender_id"]
    sender_name = request.POST["sender_name"]
    receiver = get_object_or_404(User, username=request.POST["receiver"])
    
    # ensure database is consistent
    request = RemoteFollowRequests.objects.filter(sender_id=sender_id, sender_name=sender_name, receiver=receiver)
    if(request.exists() and not RemoteFollower.objects.filter(follower_id=sender_id, followee=receiver).exists()):
        request.delete()
        RemoteFollower.objects.create(follower_id=sender_id, followee=receiver)

        # check if there is a corresponding friendship to be created
        if(RemoteFollowee.objects.filter(follower=receiver, followee_id=sender_id).exists() and not RemoteFriendship.objects.filter(local=receiver, remote=sender_id)):
            RemoteFriendship.objects.create(local=receiver, remote=sender_id)

        return redirect(reverse('identity:requests', kwargs={'username': receiver.username}))
    return HttpResponse("Error in accepting the follow request")

def remoteDecline(request):
    # query user DB to get the sender and receiver
    sender_id = request.POST["sender_id"]
    sender_name = request.POST["sender_name"]
    receiver = get_object_or_404(User, username=request.POST["receiver"])
    request = RemoteFollowRequests.objects.filter(sender_id=sender_id, sender_name=sender_name, receiver=receiver)

    # ensure database is consistent
    if(request.exists()):
        request.delete()
        return redirect(reverse('identity:requests', kwargs={'username': receiver.username}))
    return HttpResponse("Error in declining the follow request")

class AuthorProfileEditView(LoginRequiredMixin, UpdateView):
    model = Author
    form_class = AuthorProfileForm
    template_name = 'identity/author_edit_profile.html'
    
    def get_object(self, queryset=None):
        # Get the current user's author profile
        return self.request.user.author_profile
    
    def get_success_url(self):
        messages.success(self.request, "Your profile has been updated successfully!")
        return reverse_lazy('identity:author-profile', kwargs={'username': self.request.user.username})
    
class UserSignUpView(CreateView):
    form_class = UserSignUpForm
    template_name = 'identity/signup.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Import settings to check if approval is required
        from django.conf import settings
        
        # Show appropriate message based on approval requirement
        if getattr(settings, 'REQUIRE_AUTHOR_APPROVAL', True):
            messages.success(self.request, 
                "Your account has been created but requires admin approval before you can log in.")
        else:
            messages.success(self.request, 
                "Your account has been created successfully! You can now log in.")
        
        return response
    
class CustomLoginView(LoginView):
    template_name = 'identity/login.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Add bootstrap classes to form fields
        for field_name, field in form.fields.items():
            field.widget.attrs['class'] = 'form-control'
        return form
        
    def form_valid(self, form):
        user = form.get_user()
        # Import settings to check if approval is required
        from django.conf import settings
        
        # Only check approval if it's required
        if getattr(settings, 'REQUIRE_AUTHOR_APPROVAL', True):
            # Check if user has an author profile and if it's approved
            if hasattr(user, 'author_profile') and not user.author_profile.is_approved:
                # If not approved, add error message and redirect to waiting page
                messages.error(self.request, "Your account is pending admin approval.")
                return redirect('identity:waiting_approval')
        # If approved or admin user, proceed with login
        return super().form_valid(form)
    
def waiting_approval_view(request):
    return render(request, 'identity/waiting_approval.html')



class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

class RemoteNodeListView(AdminRequiredMixin, ListView):
    model = RemoteNode
    template_name = 'identity/remote_node_list.html'
    context_object_name = 'nodes'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add author counts for each node
        for node in context['nodes']:
            node.author_count = RemoteAuthor.objects.filter(node=node).count()
        return context


class RemoteNodeCreateView(AdminRequiredMixin, CreateView):
    model = RemoteNode
    form_class = RemoteNodeForm
    template_name = 'identity/remote_node_form.html'
    success_url = reverse_lazy('identity:remote-node-list')

class RemoteNodeUpdateView(AdminRequiredMixin, UpdateView):
    model = RemoteNode
    form_class = RemoteNodeForm
    template_name = 'identity/remote_node_form.html'
    success_url = reverse_lazy('identity:remote-node-list')

class RemoteNodeDeleteView(AdminRequiredMixin, DeleteView):
    model = RemoteNode
    template_name = 'identity/remote_node_confirm_delete.html'
    success_url = reverse_lazy('identity:remote-node-list')

@user_passes_test(lambda u: u.is_superuser)
def share_post_with_nodes(request, post_id):
    """Share a post with all connected nodes"""
    try:
        post = Post.objects.get(id=post_id)
        
        # Only share public posts
        if post.visibility != 'PUBLIC':
            return JsonResponse({"error": "Only public posts can be shared"}, status=400)
        
        # Get all active nodes
        nodes = RemoteNode.objects.filter(is_active=True)
        
        results = []
        for node in nodes:
            # Format the post data for the remote node
            post_data = {
                "type": "post",
                "title": post.title,
                "description": post.description,
                "content": post.content,
                "contentType": post.contentType,
                "visibility": post.visibility,
                "author": {
                    "id": str(post.author.author_profile.id),
                    "displayName": post.author.author_profile.display_name,
                    "host": post.author.author_profile.host
                }
            }
            
            # Send to remote node
            response = send_to_node(
                node.id, 
                'api/posts/', 
                method='POST', 
                data=post_data
            )
            
            results.append({
                "node": node.name,
                "success": response and 200 <= response.status_code < 300,
                "status_code": response.status_code if response else "Failed to connect"
            })
        
        return JsonResponse({"results": results})
        
    except Post.DoesNotExist:
        return JsonResponse({"error": "Post not found"}, status=404)
    
from django.http import HttpResponse
import requests
import base64
from .models import RemoteNode


def test_basic_auth(request):
    """Simple test for Basic Auth"""
    return HttpResponse("Basic Auth test endpoint is working")

def fetch_remote_authors(request, node_id):
    """Fetch authors from a remote node and save them to the database"""
    try:
        node = RemoteNode.objects.get(id=node_id, is_active=True)
        
        # Start with the first page
        next_page_url = f"api/authors/"
        total_authors_count = 0
        
        while next_page_url:
            # Send request to the remote node's authors endpoint
            response = send_to_node(node.id, next_page_url, method='GET')
            
            if response and response.status_code == 200:
                authors_data = response.json()
                
                # Based on the API structure in your curl output
                if 'type' in authors_data and authors_data['type'] == 'authors' and 'src' in authors_data:
                    authors_list = authors_data['src']
                    
                    authors_count = 0
                    for author_data in authors_list:
                        # Extract ID from the full URL
                        author_id = author_data.get('id', '')
                        if '/' in author_id:
                            author_id = author_id.split('/')[-1]
                        
                        # Update or create the remote author
                        RemoteAuthor.objects.update_or_create(
                            node=node,
                            author_id=author_id,
                            defaults={
                                'display_name': author_data.get('displayName', 'Unknown'),
                                'host': author_data.get('host', ''),
                                'github': author_data.get('github', ''),
                                'profile_image': author_data.get('profileImage', '')
                            }
                        )
                        authors_count += 1
                    
                    total_authors_count += authors_count
                    
                    # Check if there's a next page
                    if 'next' in authors_data and authors_data['next']:
                        # Extract the relative path from the next URL
                        full_next_url = authors_data['next']
                        if full_next_url.startswith("http"):
                            # Extract just the path and query string
                            from urllib.parse import urlparse
                            parsed_url = urlparse(full_next_url)
                            next_page_url = parsed_url.path
                            if parsed_url.query:
                                next_page_url += "?" + parsed_url.query
                        else:
                            next_page_url = full_next_url
                    else:
                        next_page_url = None
                else:
                    next_page_url = None
                    messages.warning(request, f"Unexpected API response format from {node.name}")
            else:
                next_page_url = None
                status = response.status_code if response else "Connection failed"
                error_detail = response.text if response else "No response received"
                messages.error(request, f"Failed to fetch authors from {node.name}. Status: {status}. Details: {error_detail}")
        
        messages.success(request, f"Successfully fetched {total_authors_count} authors from {node.name}")
        return redirect('identity:remote-authors-list', node_id=node_id)
    
    except RemoteNode.DoesNotExist:
        messages.error(request, "Remote node not found")
        return redirect('identity:remote-node-list')
    except Exception as e:
        messages.error(request, f"Error fetching authors: {type(e).__name__} - {str(e)}")
        return redirect('identity:remote-node-list')
    
class RemoteAuthorListView(LoginRequiredMixin, ListView):
    """View to display authors from a specific remote node"""
    model = RemoteAuthor
    template_name = 'identity/remote_author_list.html'
    context_object_name = 'authors'
    paginate_by = 20
    
    def get_queryset(self):
        self.node = get_object_or_404(RemoteNode, id=self.kwargs['node_id'], is_active=True)
        return RemoteAuthor.objects.filter(node=self.node)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['node'] = self.node
        return context
    


class RemoteAuthorDetailView(LoginRequiredMixin, DetailView):
    model = RemoteAuthor
    template_name = 'identity/remote_author_profile.html'
    context_object_name = 'remote_author'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        remote_author = self.get_object()
        
        # Check if the current user is following this remote author
        context['is_following'] = RemoteFollowee.objects.filter(
            follower=self.request.user,
            followee_id=remote_author.host + "/api/authors/" + remote_author.author_id
        ).exists()
        
        # Fetch posts and other details as before
        try:
            # Your existing code to fetch posts
            node = remote_author.node
            posts_endpoint = f'api/authors/{remote_author.author_id}/posts/'
            posts_response = send_to_node(
                node.id, 
                posts_endpoint, 
                method='GET'
            )
            
            if posts_response and posts_response.status_code == 200:
                posts_data = posts_response.json()
                
                if 'type' in posts_data and posts_data['type'] == 'posts' and 'src' in posts_data:
                    context['posts'] = posts_data['src']
                else:
                    context['posts'] = []
            else:
                context['posts'] = []
        
        except Exception as e:
            messages.error(self.request, f"Error fetching remote author details: {str(e)}")
            context['posts'] = []
        
        return context