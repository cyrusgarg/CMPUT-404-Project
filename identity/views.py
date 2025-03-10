import json
from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from posts.models import Post  
from identity.models import Author
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from .models import Author, GitHubActivity, Following, FollowRequests
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Author
from .forms import AuthorProfileForm
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import UserSignUpForm
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView


class AuthorProfileView(DetailView):
    model = Author
    template_name = 'identity/author_profile.html'
    context_object_name = 'author'
    
    def get_object(self):
        return get_object_or_404(Author, user__username=self.kwargs['username'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author = self.get_object()
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
    model = Author
    template_name = 'authors/author_list.html'
    context_object_name = 'authors'
    paginate_by = 10

class Requests(ListView):
    model = FollowRequests
    template_name = 'identity/follow_requests.html'
    context_object_name = 'requests'

    def get_queryset(self):
        return FollowRequests.objects.filter(receiver__username=self.kwargs['username']).order_by('-created_at')

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
        return redirect(reverse('identity:author-profile', kwargs={'username': followee.username}))
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